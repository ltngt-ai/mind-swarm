"""Twitch integration manager for Mind-Swarm server."""

from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

try:  # websockets 14+
    from websockets.asyncio.client import ClientConnection as WebSocketClientProtocol  # type: ignore[attr-defined]
    from websockets.asyncio.client import connect
except ImportError:
    try:  # websockets 10-13
        from websockets.client import WebSocketClientProtocol, connect
    except ImportError:  # websockets < 10
        from websockets import connect  # type: ignore
        from websockets.legacy.client import WebSocketClientProtocol  # type: ignore


logger = logging.getLogger(__name__)

TWITCH_IRC_URL = "wss://irc-ws.chat.twitch.tv:443"


class TwitchIntegrationError(RuntimeError):
    """Base class for Twitch integration errors."""


class TwitchConfigurationError(TwitchIntegrationError):
    """Raised when Twitch configuration is invalid or missing."""


class TwitchAuthenticationError(TwitchIntegrationError):
    """Raised when Twitch authentication fails."""


class TwitchConnectionError(TwitchIntegrationError):
    """Raised when Twitch connection cannot be established."""


@dataclass
class TwitchCredentials:
    """Twitch authentication credentials."""

    username: str
    oauth_token: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None


@dataclass
class TwitchMessage:
    """Representation of a Twitch chat message."""

    message_id: str
    user: str
    text: str
    badges: List[str] = field(default_factory=list)
    color: Optional[str] = None
    raw: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        """Convert message to API payload."""
        return {
            "id": self.message_id,
            "user": self.user,
            "message": self.text,
            "badges": self.badges,
            "color": self.color,
            "timestamp": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class TwitchConnectionState:
    """Current Twitch connection state."""

    channel: Optional[str] = None
    connected: bool = False
    mock: bool = False
    prefix: str = "!"
    connected_at: Optional[datetime] = None
    last_error: Optional[str] = None


class TwitchIntegrationManager:
    """Manage Twitch IRC connection and message queues."""

    def __init__(self) -> None:
        self._state = TwitchConnectionState()
        self._lock = asyncio.Lock()
        self._incoming_messages: "asyncio.Queue[TwitchMessage]" = asyncio.Queue()
        self._outgoing_messages: "asyncio.Queue[Optional[str]]" = asyncio.Queue()
        self._recent_commands: Deque[Dict[str, Any]] = deque(maxlen=100)
        self._message_counter = 0
        self._websocket: Optional[WebSocketClientProtocol] = None
        self._receiver_task: Optional[asyncio.Task[None]] = None
        self._sender_task: Optional[asyncio.Task[None]] = None
        self._mock_task: Optional[asyncio.Task[None]] = None

    @property
    def state(self) -> TwitchConnectionState:
        """Return a copy of the current connection state."""
        return TwitchConnectionState(
            channel=self._state.channel,
            connected=self._state.connected,
            mock=self._state.mock,
            prefix=self._state.prefix,
            connected_at=self._state.connected_at,
            last_error=self._state.last_error,
        )

    @property
    def prefix(self) -> str:
        """Return the command prefix currently configured."""
        return self._state.prefix

    async def connect(
        self,
        channel: str,
        *,
        mock: bool = False,
        prefix: str = "!",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TwitchConnectionState:
        """Connect to Twitch chat or enable mock mode."""
        async with self._lock:
            await self._shutdown_locked()

            self._state = TwitchConnectionState(
                channel=channel.lower().lstrip("#"),
                connected=False,
                mock=mock,
                prefix=prefix or "!",
                connected_at=None,
                last_error=None,
            )

            if mock:
                logger.info("Twitch manager running in mock mode for channel %s", channel)
                self._state.connected = True
                self._state.connected_at = datetime.now(timezone.utc)
                self._mock_task = asyncio.create_task(self._mock_message_pump(metadata or {}))
                return self.state

            credentials = self._load_credentials()
            if not credentials:
                error = (
                    "TWITCH_BOT_USERNAME and TWITCH_OAUTH_TOKEN must be configured to connect to Twitch"
                )
                self._state.last_error = error
                logger.error(error)
                raise TwitchConfigurationError(error)

            await self._establish_connection(credentials)
            return self.state

    async def disconnect(self) -> None:
        """Disconnect from Twitch and stop all background tasks."""
        async with self._lock:
            await self._shutdown_locked()
            self._state = TwitchConnectionState(prefix=self._state.prefix)

    async def _shutdown_locked(self) -> None:
        """Internal helper to stop tasks and close websocket."""
        if self._mock_task:
            self._mock_task.cancel()
            try:
                await self._mock_task
            except asyncio.CancelledError:
                pass
            self._mock_task = None

        if self._sender_task:
            self._sender_task.cancel()
            try:
                await self._sender_task
            except asyncio.CancelledError:
                pass
            self._sender_task = None

        if self._receiver_task:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass
            self._receiver_task = None

        if self._websocket and not self._websocket.closed:
            await self._websocket.close()
        self._websocket = None

        # Drain queues so callers do not receive stale information
        while not self._incoming_messages.empty():
            try:
                self._incoming_messages.get_nowait()
            except asyncio.QueueEmpty:
                break

        while not self._outgoing_messages.empty():
            try:
                self._outgoing_messages.get_nowait()
            except asyncio.QueueEmpty:
                break

        self._state.connected = False
        self._state.connected_at = None

    def _load_credentials(self) -> Optional[TwitchCredentials]:
        """Load Twitch credentials from environment."""
        username = os.getenv("TWITCH_BOT_USERNAME")
        token = os.getenv("TWITCH_OAUTH_TOKEN")
        if not username or not token:
            return None
        client_id = os.getenv("TWITCH_CLIENT_ID")
        client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        return TwitchCredentials(
            username=username,
            oauth_token=token,
            client_id=client_id,
            client_secret=client_secret,
        )

    async def _establish_connection(self, credentials: TwitchCredentials) -> None:
        """Open IRC websocket connection and start background tasks."""
        try:
            websocket = await connect(TWITCH_IRC_URL, ping_interval=20, ping_timeout=20)
        except Exception as exc:  # noqa: BLE001 - bubble up with context
            self._state.last_error = str(exc)
            raise TwitchConnectionError(f"Failed to connect to Twitch IRC: {exc}")

        self._websocket = websocket

        try:
            await websocket.send("CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership")
            await websocket.send(f"PASS oauth:{credentials.oauth_token}")
            await websocket.send(f"NICK {credentials.username}")
            await websocket.send(f"JOIN #{self._state.channel}")
        except Exception as exc:  # noqa: BLE001 - propagate with context
            self._state.last_error = str(exc)
            await websocket.close()
            self._websocket = None
            raise TwitchAuthenticationError(f"Failed to authenticate with Twitch IRC: {exc}")

        self._state.connected = True
        self._state.connected_at = datetime.now(timezone.utc)
        logger.info("Connected to Twitch channel #%s as %s", self._state.channel, credentials.username)

        self._receiver_task = asyncio.create_task(self._receiver_loop(websocket))
        self._sender_task = asyncio.create_task(self._sender_loop(websocket))

    async def _receiver_loop(self, websocket: WebSocketClientProtocol) -> None:
        """Receive messages from Twitch and enqueue them for polling."""
        try:
            async for raw in websocket:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", "ignore")
                raw = raw.strip()
                if not raw:
                    continue
                if raw.startswith("PING"):
                    await websocket.send("PONG :tmi.twitch.tv")
                    continue
                message = self._parse_raw_message(raw)
                if message:
                    await self._incoming_messages.put(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - log and mark disconnected
            logger.error("Twitch receiver loop exited: %s", exc)
        finally:
            self._state.connected = False
            if self._websocket and not self._websocket.closed:
                await self._websocket.close()
            self._websocket = None

    async def _sender_loop(self, websocket: WebSocketClientProtocol) -> None:
        """Send queued messages to Twitch chat."""
        try:
            while True:
                message = await self._outgoing_messages.get()
                if message is None:
                    break
                payload = f"PRIVMSG #{self._state.channel} :{message}"
                await websocket.send(payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - log and continue to shutdown
            logger.error("Twitch sender loop exited: %s", exc)
        finally:
            try:
                await websocket.close()
            except Exception:  # noqa: BLE001 - best effort
                pass

    async def _mock_message_pump(self, metadata: Dict[str, Any]) -> None:
        """Generate lightweight system messages in mock mode."""
        try:
            await self.push_system_message(
                "Twitch mock mode active. No live chat connection established.",
                metadata={"mode": "mock", **metadata},
            )
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise

    def _parse_raw_message(self, raw: str) -> Optional[TwitchMessage]:
        """Parse raw IRC payload into a TwitchMessage."""
        tags: Dict[str, str] = {}
        prefix: Optional[str] = None
        command: Optional[str] = None
        params: List[str] = []
        text: str = ""

        rest = raw
        if rest.startswith("@"):
            tag_part, rest = rest.split(" ", 1)
            for item in tag_part[1:].split(";"):
                if "=" in item:
                    key, value = item.split("=", 1)
                    tags[key] = value

        if rest.startswith(":"):
            prefix_part, rest = rest[1:].split(" ", 1)
            prefix = prefix_part

        if " :" in rest:
            rest, text = rest.split(" :", 1)

        parts = rest.split()
        if parts:
            command = parts[0]
            params = parts[1:]

        if command != "PRIVMSG" or not params:
            return None

        channel = params[0]
        if channel.lstrip("#").lower() != (self._state.channel or ""):
            return None

        user = tags.get("display-name")
        if not user and prefix:
            user = prefix.split("!", 1)[0]
        user = user or "twitch-user"

        badge_str = tags.get("badges", "")
        badges = [badge for badge in badge_str.split(",") if badge]

        color = tags.get("color") or None
        message_id = tags.get("id") or self._next_message_id("msg")

        metadata = {
            "room_id": tags.get("room-id"),
            "user_id": tags.get("user-id"),
            "emotes": tags.get("emotes"),
            "first_message": tags.get("first-msg") == "1",
            "mod": tags.get("mod") == "1",
            "subscriber": tags.get("subscriber") == "1",
        }

        return TwitchMessage(
            message_id=message_id,
            user=user,
            text=text,
            badges=badges,
            color=color,
            raw=raw,
            metadata=metadata,
        )

    def _next_message_id(self, prefix: str) -> str:
        """Generate a unique message identifier."""
        self._message_counter += 1
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        return f"{prefix}_{ts}_{self._message_counter}"

    async def drain_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return and clear queued messages up to provided limit."""
        messages: List[Dict[str, Any]] = []
        for _ in range(limit):
            try:
                message = self._incoming_messages.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                messages.append(message.to_payload())
        return messages

    async def push_system_message(
        self,
        text: str,
        *,
        username: str = "MindSwarm",
        badges: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Inject a local system message into the queue."""
        message = TwitchMessage(
            message_id=self._next_message_id("sys"),
            user=username,
            text=text,
            badges=badges or ["staff/1"],
            metadata=metadata or {},
        )
        await self._incoming_messages.put(message)

    async def queue_outbound_message(self, text: str) -> None:
        """Enqueue message to be sent to Twitch chat (or reflect in mock mode)."""
        if self._state.mock or not self._state.connected or not self._websocket:
            await self.push_system_message(text, username="MindSwarm", metadata={"direction": "outbound"})
            return
        await self._outgoing_messages.put(text)

    async def record_command(self, payload: Dict[str, Any]) -> None:
        """Record executed command for overlay consumption."""
        self._recent_commands.append(payload)
        await self._incoming_messages.put(
            TwitchMessage(
                message_id=self._next_message_id("cmd"),
                user=payload.get("user", "MindSwarm"),
                text=payload.get("message", ""),
                badges=payload.get("badges", []),
                metadata={"type": "command", **payload},
            )
        )

    def recent_commands(self) -> List[Dict[str, Any]]:
        """Return recently executed commands."""
        return list(self._recent_commands)

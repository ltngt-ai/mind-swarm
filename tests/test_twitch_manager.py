"""Tests for Twitch integration manager."""

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest


def _load_twitch_manager() -> type:
    """Load TwitchIntegrationManager without importing the heavy server package."""

    module_path = Path(__file__).resolve().parents[1] / "src" / "mind_swarm" / "server" / "twitch_manager.py"
    spec = importlib.util.spec_from_file_location("mind_swarm.server.twitch_manager", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to locate twitch_manager module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    manager_cls = getattr(module, "TwitchIntegrationManager", None)
    if manager_cls is None:
        raise RuntimeError("TwitchIntegrationManager not found in module")
    return manager_cls


TwitchIntegrationManager = _load_twitch_manager()


@pytest.mark.asyncio
async def test_mock_connect_generates_system_message() -> None:
    manager = TwitchIntegrationManager()
    try:
        state = await manager.connect(channel="testchannel", mock=True, metadata={"source": "test"})
        assert state.connected
        await asyncio.sleep(0)  # allow mock task to enqueue the initial message
        messages = await manager.drain_messages(limit=10)
        assert any(msg["metadata"].get("mode") == "mock" for msg in messages)
    finally:
        await manager.disconnect()


@pytest.mark.asyncio
async def test_queue_outbound_message_reflects_in_mock_mode() -> None:
    manager = TwitchIntegrationManager()
    try:
        await manager.connect(channel="another", mock=True)
        await asyncio.sleep(0)
        await manager.drain_messages(limit=10)  # clear initial mock notice

        await manager.queue_outbound_message("Hello viewers")
        messages = await manager.drain_messages(limit=5)
        assert any(
            msg["message"] == "Hello viewers"
            and msg["metadata"].get("direction") == "outbound"
            and msg["user"] == "MindSwarm"
            for msg in messages
        )
    finally:
        await manager.disconnect()


@pytest.mark.asyncio
async def test_queue_outbound_message_reflects_when_connected() -> None:
    class _FakeWebSocket:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    manager = TwitchIntegrationManager()
    manager._state.connected = True
    manager._websocket = _FakeWebSocket()
    manager._bot_username = "BotUser"

    await manager.queue_outbound_message("Live ping")

    queued = await manager._outgoing_messages.get()
    assert queued == "Live ping"

    messages = await manager.drain_messages(limit=5)
    assert messages
    assert messages[0]["user"] == "BotUser"
    assert messages[0]["metadata"].get("direction") == "outbound"
    assert messages[0]["message"] == "Live ping"


@pytest.mark.asyncio
async def test_record_command_tracks_history() -> None:
    manager = TwitchIntegrationManager()
    try:
        await manager.connect(channel="cmdtest", mock=True)
        await asyncio.sleep(0)
        await manager.drain_messages(limit=10)

        payload = {
            "user": "viewer",
            "command": "status",
            "args": [],
            "success": True,
            "message": "viewer issued !status",
            "badges": ["vip/1"],
        }
        await manager.record_command(payload)

        recent = manager.recent_commands()
        assert recent
        assert recent[-1]["command"] == "status"

        messages = await manager.drain_messages(limit=10)
        assert any(msg["metadata"].get("type") == "command" for msg in messages)
    finally:
        await manager.disconnect()

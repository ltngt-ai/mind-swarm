"""
Terminal Sessions API for Cybers - Persistent Terminal Management

## Core Concept: Stateful Terminal Sessions Across Cycles
The Terminal Sessions API extends the base terminal API with persistence,
allowing Cybers to maintain terminal sessions across cognitive cycles.
Sessions are stored in the knowledge database with full context and history.

## Key Features
- Session persistence across cycles
- Command history tracking
- Game state management
- Web browsing context
- Automatic session recovery

## Examples

### Intention: "I want to play a text adventure game across multiple cycles"
```python
# First cycle - start the game
session = terminal_sessions.create_game_session("telnet adventure.com 2023")
terminal_sessions.send_and_remember(session, "look")
state = terminal_sessions.get_session_state(session)
working_memory.add("game_state", state)

# Later cycle - resume playing
session = terminal_sessions.get_or_create("my_adventure_game")
history = terminal_sessions.get_command_history(session)
print(f"Last command: {history[-1]}")
terminal_sessions.send_and_remember(session, "go north")
```

### Intention: "I want to browse the web and remember what I found"
```python
# Create a web browsing session
browser = terminal_sessions.create_web_session("lynx")
terminal_sessions.browse_to(browser, "https://news.ycombinator.com")
content = terminal_sessions.get_screen_content(browser)
terminal_sessions.save_snapshot(browser, "hn_frontpage")

# Next cycle - continue browsing
browser = terminal_sessions.resume_session("web_browser")
terminal_sessions.send_and_remember(browser, "g")  # Go to URL in lynx
terminal_sessions.send_and_remember(browser, "https://example.com")
```

### Intention: "I want to run a long interactive process"
```python
# Start a Python REPL for data analysis
repl = terminal_sessions.create_persistent_session("python3", "data_analysis")
terminal_sessions.execute_script(repl, '''
import pandas as pd
data = pd.read_csv('/personal/data.csv')
print(data.head())
''')

# Many cycles later
repl = terminal_sessions.get_session("data_analysis")
if repl:
    terminal_sessions.send_and_remember(repl, "data.describe()")
```

## Best Practices
1. Name sessions meaningfully for easy retrieval
2. Save snapshots at important moments
3. Use command history to understand context
4. Clean up finished sessions to save resources
5. Store game/web state in working memory for decisions
"""

import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger("Cyber.terminal_sessions")


class TerminalSessionError(Exception):
    """Base exception for terminal session errors."""
    pass


class TerminalSessions:
    """Manages persistent terminal sessions with knowledge database backing."""
    
    def __init__(self, context: Dict[str, Any]):
        """Initialize Terminal Sessions API.
        
        Args:
            context: Execution context containing terminal, knowledge, and memory APIs
        """
        self.context = context
        
        # Handle case where context might be None during module import
        if context is None:
            # Minimal initialization - will be properly initialized when used
            self.terminal = None
            self.knowledge = None
            self.personal = Path('/personal')
            self._active_sessions = {}
            return
        
        # Get required APIs from context
        from .terminal import Terminal
        from .knowledge import Knowledge
        
        self.terminal = Terminal(context)
        self.knowledge = Knowledge(context)
        # Use standard file operations instead of Memory API
        self.personal = Path(context.get('personal_dir', '/personal'))
        
        # Session tracking
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        self._load_active_sessions()
    
    def _load_active_sessions(self):
        """Load active sessions from knowledge database."""
        try:
            # Search for active terminal sessions
            results = self.knowledge.search(
                query="Terminal Session Active",
                limit=20,
                scope=["personal"]
            )
            
            for result in results:
                metadata = result.get('metadata', {})
                if metadata.get('session_active', False):
                    session_id = metadata.get('session_id')
                    if session_id:
                        self._active_sessions[session_id] = metadata
                        
        except Exception as e:
            logger.warning(f"Could not load active sessions: {e}")
    
    def create_game_session(self, command: str, name: Optional[str] = None) -> str:
        """Create a persistent game session.
        
        Args:
            command: Game command (e.g., "telnet adventure.com 2023")
            name: Friendly name for the session
            
        Returns:
            Session ID
        """
        # Create the terminal session
        session_id = self.terminal.create(command, name)
        
        # Store session metadata in knowledge
        session_name = name or f"game_{session_id[:8]}"
        knowledge_id = f"terminal_session/{session_name}"
        
        session_data = {
            "session_id": session_id,
            "session_name": session_name,
            "session_type": "game",
            "command": command,
            "created_at": datetime.now().isoformat(),
            "session_active": True,
            "command_history": [],
            "snapshots": []
        }
        
        content = f"""Terminal Session: {session_name}
Type: Game Session
Command: {command}
Session ID: {session_id}
Status: Active
Created: {session_data['created_at']}

This is a persistent game session that can be resumed across cognitive cycles.
"""
        
        self.knowledge.store(
            content=content,
            knowledge_id=knowledge_id,
            tags=["terminal_session", "game", "active", session_name],
            personal=True,
            metadata=session_data
        )
        
        self._active_sessions[session_id] = session_data
        logger.info(f"Created game session {session_name} ({session_id})")
        
        return session_id
    
    def create_web_session(self, browser: str = "lynx", name: Optional[str] = None) -> str:
        """Create a persistent web browsing session.
        
        Args:
            browser: Browser command (lynx, w3m, curl, etc.)
            name: Friendly name for the session
            
        Returns:
            Session ID
        """
        # Create the terminal session
        session_id = self.terminal.create(browser, name)
        
        # Store session metadata
        session_name = name or f"web_{session_id[:8]}"
        knowledge_id = f"terminal_session/{session_name}"
        
        session_data = {
            "session_id": session_id,
            "session_name": session_name,
            "session_type": "web",
            "browser": browser,
            "created_at": datetime.now().isoformat(),
            "session_active": True,
            "command_history": [],
            "visited_urls": [],
            "snapshots": []
        }
        
        content = f"""Terminal Session: {session_name}
Type: Web Browsing Session
Browser: {browser}
Session ID: {session_id}
Status: Active
Created: {session_data['created_at']}

This is a persistent web browsing session for accessing websites and APIs.
"""
        
        self.knowledge.store(
            content=content,
            knowledge_id=knowledge_id,
            tags=["terminal_session", "web", "browser", "active", session_name],
            personal=True,
            metadata=session_data
        )
        
        self._active_sessions[session_id] = session_data
        logger.info(f"Created web session {session_name} ({session_id})")
        
        return session_id
    
    def create_persistent_session(self, command: str, name: str, 
                                session_type: str = "repl") -> str:
        """Create a named persistent session.
        
        Args:
            command: Command to run
            name: Unique name for the session
            session_type: Type of session (repl, shell, etc.)
            
        Returns:
            Session ID
        """
        # Check if session with this name exists
        existing = self.get_session(name)
        if existing:
            logger.info(f"Session {name} already exists")
            return existing
        
        # Create new session
        session_id = self.terminal.create(command, name)
        
        knowledge_id = f"terminal_session/{name}"
        
        session_data = {
            "session_id": session_id,
            "session_name": name,
            "session_type": session_type,
            "command": command,
            "created_at": datetime.now().isoformat(),
            "session_active": True,
            "command_history": [],
            "context": {},
            "snapshots": []
        }
        
        content = f"""Terminal Session: {name}
Type: {session_type.title()} Session
Command: {command}
Session ID: {session_id}
Status: Active
Created: {session_data['created_at']}

Persistent {session_type} session for ongoing interactive work.
"""
        
        self.knowledge.store(
            content=content,
            knowledge_id=knowledge_id,
            tags=["terminal_session", session_type, "active", name],
            personal=True,
            metadata=session_data
        )
        
        self._active_sessions[session_id] = session_data
        logger.info(f"Created persistent session {name} ({session_id})")
        
        return session_id
    
    def send_and_remember(self, session_id: str, command: str, 
                         wait: float = 0.5) -> Dict[str, Any]:
        """Send command and store in history.
        
        Args:
            session_id: Session to send to
            command: Command to send
            wait: Time to wait for response
            
        Returns:
            Response with screen content and metadata
        """
        # Send the command
        self.terminal.send(session_id, command)
        
        # Wait for processing
        time.sleep(wait)
        
        # Read response
        response = self.terminal.read(session_id)
        
        # Update session history
        session_data = self._active_sessions.get(session_id)
        if session_data:
            # Add to command history
            history_entry = {
                "command": command,
                "timestamp": datetime.now().isoformat(),
                "response_length": len(response.get('screen', ''))
            }
            session_data['command_history'].append(history_entry)
            
            # Update in knowledge database
            self._update_session_knowledge(session_data)
        
        logger.info(f"Sent command to session {session_id}: {command[:50]}...")
        
        return response
    
    def get_or_create(self, name: str, command: Optional[str] = None,
                     session_type: str = "general") -> str:
        """Get existing session or create new one.
        
        Args:
            name: Session name
            command: Command if creating new (default: bash)
            session_type: Type if creating new
            
        Returns:
            Session ID
        """
        # Try to get existing
        existing = self.get_session(name)
        if existing:
            return existing
        
        # Create new
        if not command:
            command = "bash"
        
        if session_type == "game":
            return self.create_game_session(command, name)
        elif session_type == "web":
            return self.create_web_session(command, name)
        else:
            return self.create_persistent_session(command, name, session_type)
    
    def get_session(self, name: str) -> Optional[str]:
        """Get session ID by name.
        
        Args:
            name: Session name
            
        Returns:
            Session ID or None
        """
        # Check active sessions
        for session_id, data in self._active_sessions.items():
            if data.get('session_name') == name:
                # Verify session still exists
                try:
                    sessions = self.terminal.list_sessions()
                    if any(s['session_id'] == session_id for s in sessions):
                        return session_id
                except:
                    pass
        
        # Try to find in knowledge
        knowledge_id = f"terminal_session/{name}"
        result = self.knowledge.get(knowledge_id)
        
        if result:
            metadata = result.get('metadata', {})
            session_id = metadata.get('session_id')
            
            if session_id and metadata.get('session_active', False):
                # Try to verify it still exists
                try:
                    sessions = self.terminal.list_sessions()
                    if any(s['session_id'] == session_id for s in sessions):
                        self._active_sessions[session_id] = metadata
                        return session_id
                except:
                    pass
        
        return None
    
    def resume_session(self, name: str) -> Optional[str]:
        """Resume a session, recreating if needed.
        
        Args:
            name: Session name
            
        Returns:
            Session ID or None
        """
        # Try to get existing
        session_id = self.get_session(name)
        if session_id:
            return session_id
        
        # Try to recreate from knowledge
        knowledge_id = f"terminal_session/{name}"
        result = self.knowledge.get(knowledge_id)
        
        if result:
            metadata = result.get('metadata', {})
            command = metadata.get('command')
            session_type = metadata.get('session_type', 'general')
            
            if command:
                logger.info(f"Recreating session {name} with command: {command}")
                return self.get_or_create(name, command, session_type)
        
        return None
    
    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        """Get current state of a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session state dictionary
        """
        state = {
            "session_id": session_id,
            "active": False,
            "screen": "",
            "history": [],
            "metadata": {}
        }
        
        # Get current screen
        try:
            response = self.terminal.read(session_id)
            state["screen"] = response.get('screen', '')
            state["active"] = True
        except:
            pass
        
        # Get session data
        session_data = self._active_sessions.get(session_id, {})
        state["history"] = session_data.get('command_history', [])
        state["metadata"] = {
            "name": session_data.get('session_name'),
            "type": session_data.get('session_type'),
            "created": session_data.get('created_at')
        }
        
        return state
    
    def get_command_history(self, session_id: str, limit: int = 10) -> List[str]:
        """Get recent command history.
        
        Args:
            session_id: Session ID
            limit: Maximum commands to return
            
        Returns:
            List of recent commands
        """
        session_data = self._active_sessions.get(session_id, {})
        history = session_data.get('command_history', [])
        
        # Extract just the commands
        commands = [h.get('command', '') for h in history]
        
        return commands[-limit:] if limit else commands
    
    def save_snapshot(self, session_id: str, snapshot_name: str) -> str:
        """Save a snapshot of current session state.
        
        Args:
            session_id: Session ID
            snapshot_name: Name for the snapshot
            
        Returns:
            Snapshot ID
        """
        # Get current screen content
        response = self.terminal.read(session_id)
        screen = response.get('screen', '')
        
        # Create snapshot
        snapshot_id = f"snapshot_{session_id[:8]}_{snapshot_name}"
        timestamp = datetime.now().isoformat()
        
        # Store snapshot in filesystem
        snapshot_dir = self.personal / '.internal' / 'memory' / 'terminal_snapshots'
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / f"{snapshot_id}.txt"
        
        snapshot_content = f"""Terminal Snapshot: {snapshot_name}
Session: {session_id}
Time: {timestamp}

=== SCREEN CONTENT ===
{screen}
"""
        
        # Write snapshot to file
        snapshot_path.write_text(snapshot_content)
        
        # Update session data
        session_data = self._active_sessions.get(session_id, {})
        if session_data:
            snapshot_entry = {
                "snapshot_id": snapshot_id,
                "name": snapshot_name,
                "timestamp": timestamp,
                "path": str(snapshot_path)
            }
            session_data.setdefault('snapshots', []).append(snapshot_entry)
            self._update_session_knowledge(session_data)
        
        logger.info(f"Saved snapshot {snapshot_name} for session {session_id}")
        
        return snapshot_id
    
    def get_screen_content(self, session_id: str) -> str:
        """Get current screen content as string.
        
        Args:
            session_id: Session ID
            
        Returns:
            Screen content
        """
        try:
            response = self.terminal.read(session_id)
            return response.get('screen', '')
        except:
            return ""
    
    def browse_to(self, session_id: str, url: str) -> str:
        """Navigate to URL in a browser session.
        
        Args:
            session_id: Browser session ID
            url: URL to navigate to
            
        Returns:
            Page content
        """
        # Different browsers have different navigation commands
        session_data = self._active_sessions.get(session_id, {})
        browser = session_data.get('browser', 'lynx')
        
        if browser == "lynx":
            # In lynx, 'g' goes to URL
            self.terminal.send(session_id, "g")
            time.sleep(0.2)
            self.terminal.send(session_id, url)
            time.sleep(1.0)  # Wait for page load
        elif browser == "w3m":
            # In w3m, 'U' opens URL
            self.terminal.send(session_id, "U")
            time.sleep(0.2)
            self.terminal.send(session_id, url)
            time.sleep(1.0)
        elif browser == "curl":
            # Direct curl command
            self.terminal.send(session_id, f"curl -L {url}")
            time.sleep(1.0)
        else:
            # Generic approach
            self.terminal.send(session_id, url)
            time.sleep(1.0)
        
        # Update visited URLs
        if session_data:
            session_data.setdefault('visited_urls', []).append({
                "url": url,
                "timestamp": datetime.now().isoformat()
            })
            self._update_session_knowledge(session_data)
        
        # Get and return content
        response = self.terminal.read(session_id)
        return response.get('screen', '')
    
    def execute_script(self, session_id: str, script: str) -> List[Dict[str, Any]]:
        """Execute a multi-line script in a session.
        
        Args:
            session_id: Session ID
            script: Multi-line script
            
        Returns:
            List of responses for each line
        """
        lines = script.strip().split('\n')
        responses = []
        
        for line in lines:
            if line.strip():
                response = self.send_and_remember(session_id, line, wait=0.3)
                responses.append({
                    "command": line,
                    "output": response.get('screen', '')
                })
        
        return responses
    
    def close_session(self, session_id: str):
        """Close and clean up a session.
        
        Args:
            session_id: Session ID to close
        """
        # Close the terminal
        try:
            self.terminal.close(session_id)
        except:
            pass
        
        # Update session status
        session_data = self._active_sessions.get(session_id)
        if session_data:
            session_data['session_active'] = False
            session_data['closed_at'] = datetime.now().isoformat()
            self._update_session_knowledge(session_data)
            
            # Remove from active sessions
            del self._active_sessions[session_id]
        
        logger.info(f"Closed session {session_id}")
    
    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions.
        
        Returns:
            List of session info dictionaries
        """
        active = []
        
        # Get actual terminal sessions
        try:
            terminal_sessions = self.terminal.list_sessions()
            terminal_ids = {s['session_id'] for s in terminal_sessions}
        except:
            terminal_ids = set()
        
        # Match with our tracked sessions
        for session_id, data in self._active_sessions.items():
            if session_id in terminal_ids:
                active.append({
                    "session_id": session_id,
                    "name": data.get('session_name'),
                    "type": data.get('session_type'),
                    "created": data.get('created_at'),
                    "commands": len(data.get('command_history', []))
                })
        
        return active
    
    def _update_session_knowledge(self, session_data: Dict[str, Any]):
        """Update session data in knowledge database.
        
        Args:
            session_data: Session data dictionary
        """
        session_name = session_data.get('session_name')
        if not session_name:
            return
        
        knowledge_id = f"terminal_session/{session_name}"
        
        # Build updated content
        content = f"""Terminal Session: {session_name}
Type: {session_data.get('session_type', 'general').title()} Session
Command: {session_data.get('command', 'unknown')}
Session ID: {session_data.get('session_id')}
Status: {'Active' if session_data.get('session_active') else 'Closed'}
Created: {session_data.get('created_at')}
Commands Executed: {len(session_data.get('command_history', []))}
Snapshots: {len(session_data.get('snapshots', []))}

Recent Commands:
"""
        
        # Add recent command history
        history = session_data.get('command_history', [])
        for cmd in history[-5:]:
            content += f"- {cmd.get('command', '')}\n"
        
        # Update in knowledge
        tags = ["terminal_session", session_data.get('session_type', 'general')]
        if session_data.get('session_active'):
            tags.append("active")
        tags.append(session_name)
        
        self.knowledge.store(
            content=content,
            knowledge_id=knowledge_id,
            tags=tags,
            personal=True,
            metadata=session_data
        )


# Module-level instance management
_instance: Optional[TerminalSessions] = None


def _get_instance() -> TerminalSessions:
    """Get the terminal sessions instance."""
    if _instance is None:
        raise TerminalSessionError("Terminal sessions not initialized. This should be set up by execution stage.")
    return _instance


# Public API functions
def create_game_session(command: str, name: Optional[str] = None) -> str:
    """Create a persistent game session."""
    return _get_instance().create_game_session(command, name)


def create_web_session(browser: str = "lynx", name: Optional[str] = None) -> str:
    """Create a persistent web browsing session."""
    return _get_instance().create_web_session(browser, name)


def create_persistent_session(command: str, name: str, session_type: str = "repl") -> str:
    """Create a named persistent session."""
    return _get_instance().create_persistent_session(command, name, session_type)


def send_and_remember(session_id: str, command: str, wait: float = 0.5) -> Dict[str, Any]:
    """Send command and store in history."""
    return _get_instance().send_and_remember(session_id, command, wait)


def get_or_create(name: str, command: Optional[str] = None, session_type: str = "general") -> str:
    """Get existing session or create new one."""
    return _get_instance().get_or_create(name, command, session_type)


def get_session(name: str) -> Optional[str]:
    """Get session ID by name."""
    return _get_instance().get_session(name)


def resume_session(name: str) -> Optional[str]:
    """Resume a session, recreating if needed."""
    return _get_instance().resume_session(name)


def get_session_state(session_id: str) -> Dict[str, Any]:
    """Get current state of a session."""
    return _get_instance().get_session_state(session_id)


def get_command_history(session_id: str, limit: int = 10) -> List[str]:
    """Get recent command history."""
    return _get_instance().get_command_history(session_id, limit)


def save_snapshot(session_id: str, snapshot_name: str) -> str:
    """Save a snapshot of current session state."""
    return _get_instance().save_snapshot(session_id, snapshot_name)


def get_screen_content(session_id: str) -> str:
    """Get current screen content as string."""
    return _get_instance().get_screen_content(session_id)


def browse_to(session_id: str, url: str) -> str:
    """Navigate to URL in a browser session."""
    return _get_instance().browse_to(session_id, url)


def execute_script(session_id: str, script: str) -> List[Dict[str, Any]]:
    """Execute a multi-line script in a session."""
    return _get_instance().execute_script(session_id, script)


def close_session(session_id: str):
    """Close and clean up a session."""
    return _get_instance().close_session(session_id)


def list_active_sessions() -> List[Dict[str, Any]]:
    """List all active sessions."""
    return _get_instance().list_active_sessions()
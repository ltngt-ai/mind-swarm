"""Terminal-based actions for games, web browsing, and persistent sessions."""

from typing import Dict, Any, List, Optional
import json
import time
import logging
from pathlib import Path

from .base_actions import Action, ActionResult, ActionStatus

logger = logging.getLogger("Cyber.actions.terminal")


class PlayTextAdventureAction(Action):
    """Manage text adventure game sessions."""
    
    def __init__(self):
        super().__init__("play_text_adventure", "Play or continue a text adventure game")
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Execute game commands in a persistent session."""
        game_name = self.params.get("game_name", "adventure")
        command = self.params.get("command", "look")
        action_type = self.params.get("action", "continue")  # start, continue, save, load
        
        try:
            # Get terminal_sessions from context
            terminal_sessions = context.get('terminal_sessions')
            if not terminal_sessions:
                # Try to create it
                from ..python_modules.terminal_sessions import TerminalSessions
                terminal_sessions = TerminalSessions(context)
            
            session_id = None
            
            if action_type == "start":
                # Start a new game
                game_command = self.params.get("game_command", f"telnet {game_name}")
                session_id = terminal_sessions.create_game_session(game_command, game_name)
                
                # Initial setup commands
                time.sleep(1)  # Wait for connection
                
                result = {
                    "status": "game_started",
                    "session_id": session_id,
                    "game": game_name
                }
                
            elif action_type == "continue":
                # Continue existing game
                session_id = terminal_sessions.get_session(game_name)
                
                if not session_id:
                    # Try to resume
                    session_id = terminal_sessions.resume_session(game_name)
                    
                if not session_id:
                    return ActionResult(
                        self.name,
                        ActionStatus.FAILED,
                        error=f"No game session found for {game_name}"
                    )
                
                # Send game command
                response = terminal_sessions.send_and_remember(session_id, command)
                
                # Get current game state
                state = terminal_sessions.get_session_state(session_id)
                
                result = {
                    "status": "command_sent",
                    "command": command,
                    "response": response.get('screen', ''),
                    "session_id": session_id,
                    "history_length": len(state.get('history', []))
                }
                
            elif action_type == "save":
                # Save game snapshot
                session_id = terminal_sessions.get_session(game_name)
                if session_id:
                    snapshot_name = self.params.get("snapshot_name", f"save_{time.time()}")
                    snapshot_id = terminal_sessions.save_snapshot(session_id, snapshot_name)
                    
                    result = {
                        "status": "game_saved",
                        "snapshot_id": snapshot_id,
                        "session_id": session_id
                    }
                else:
                    return ActionResult(
                        self.name,
                        ActionStatus.FAILED,
                        error=f"No active game session for {game_name}"
                    )
                    
            elif action_type == "load":
                # This would load from a snapshot - implement if needed
                result = {"status": "load_not_implemented"}
            
            else:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Unknown action type: {action_type}"
                )
            
            # Store game state in working memory
            if session_id:
                working_memory = context.get('working_memory')
                if working_memory:
                    game_state = terminal_sessions.get_session_state(session_id)
                    working_memory.add(f"game_{game_name}_state", {
                        "screen": game_state.get('screen', ''),
                        "last_command": command,
                        "session_active": game_state.get('active', False)
                    })
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result=result
            )
            
        except Exception as e:
            logger.error(f"Error in play_text_adventure: {e}")
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


class BrowseWebAction(Action):
    """Browse the web using terminal browsers."""
    
    def __init__(self):
        super().__init__("browse_web", "Browse websites using terminal browsers")
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Browse to a URL or interact with a web page."""
        url = self.params.get("url")
        browser_name = self.params.get("browser_name", "web_browser")
        browser_type = self.params.get("browser", "lynx")
        action_type = self.params.get("action", "navigate")  # navigate, interact, extract
        
        try:
            # Get terminal_sessions
            terminal_sessions = context.get('terminal_sessions')
            if not terminal_sessions:
                from ..python_modules.terminal_sessions import TerminalSessions
                terminal_sessions = TerminalSessions(context)
            
            # Get or create browser session
            session_id = terminal_sessions.get_session(browser_name)
            
            if not session_id:
                session_id = terminal_sessions.create_web_session(browser_type, browser_name)
                time.sleep(0.5)  # Wait for browser to start
            
            result = {}
            
            if action_type == "navigate" and url:
                # Navigate to URL
                content = terminal_sessions.browse_to(session_id, url)
                
                # Save snapshot of the page
                snapshot_id = terminal_sessions.save_snapshot(session_id, f"web_{url.replace('/', '_')[:30]}")
                
                result = {
                    "status": "navigated",
                    "url": url,
                    "content_preview": content[:500] if content else "",
                    "snapshot_id": snapshot_id,
                    "session_id": session_id
                }
                
            elif action_type == "interact":
                # Interact with page (follow link, fill form, etc.)
                interaction = self.params.get("interaction", "")
                
                if interaction:
                    response = terminal_sessions.send_and_remember(session_id, interaction)
                    
                    result = {
                        "status": "interacted",
                        "interaction": interaction,
                        "response": response.get('screen', '')[:500],
                        "session_id": session_id
                    }
                    
            elif action_type == "extract":
                # Extract current page content
                content = terminal_sessions.get_screen_content(session_id)
                
                # Store in working memory for processing
                working_memory = context.get('working_memory')
                if working_memory:
                    working_memory.add(f"web_content_{browser_name}", {
                        "content": content,
                        "timestamp": time.time(),
                        "url": url or "current_page"
                    })
                
                result = {
                    "status": "extracted",
                    "content_length": len(content),
                    "session_id": session_id
                }
            
            else:
                result = {
                    "status": "unknown_action",
                    "action": action_type
                }
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result=result
            )
            
        except Exception as e:
            logger.error(f"Error in browse_web: {e}")
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


class MaintainTerminalSessionAction(Action):
    """Maintain and manage terminal sessions across cycles."""
    
    def __init__(self):
        super().__init__("maintain_terminal_session", "Manage persistent terminal sessions")
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Manage terminal session lifecycle."""
        session_name = self.params.get("session_name", "default_session")
        command = self.params.get("command", "bash")
        action_type = self.params.get("action", "ensure")  # ensure, execute, check, close
        
        try:
            # Get terminal_sessions
            terminal_sessions = context.get('terminal_sessions')
            if not terminal_sessions:
                from ..python_modules.terminal_sessions import TerminalSessions
                terminal_sessions = TerminalSessions(context)
            
            result = {}
            
            if action_type == "ensure":
                # Ensure session exists
                session_id = terminal_sessions.get_or_create(session_name, command)
                
                state = terminal_sessions.get_session_state(session_id)
                
                result = {
                    "status": "session_ready",
                    "session_id": session_id,
                    "session_name": session_name,
                    "active": state.get('active', False),
                    "command_count": len(state.get('history', []))
                }
                
            elif action_type == "execute":
                # Execute command in session
                session_id = terminal_sessions.get_or_create(session_name, command)
                
                exec_command = self.params.get("execute_command", "")
                if exec_command:
                    # Handle multi-line scripts
                    if '\n' in exec_command:
                        results = terminal_sessions.execute_script(session_id, exec_command)
                        result = {
                            "status": "script_executed",
                            "session_id": session_id,
                            "results": results
                        }
                    else:
                        response = terminal_sessions.send_and_remember(session_id, exec_command)
                        result = {
                            "status": "command_executed",
                            "session_id": session_id,
                            "command": exec_command,
                            "output": response.get('screen', '')
                        }
                        
            elif action_type == "check":
                # Check session status
                active_sessions = terminal_sessions.list_active_sessions()
                
                session_info = None
                for sess in active_sessions:
                    if sess['name'] == session_name:
                        session_info = sess
                        break
                
                result = {
                    "status": "checked",
                    "session_exists": session_info is not None,
                    "session_info": session_info,
                    "total_active": len(active_sessions)
                }
                
            elif action_type == "close":
                # Close session
                session_id = terminal_sessions.get_session(session_name)
                if session_id:
                    terminal_sessions.close_session(session_id)
                    result = {
                        "status": "closed",
                        "session_name": session_name
                    }
                else:
                    result = {
                        "status": "not_found",
                        "session_name": session_name
                    }
            
            else:
                result = {
                    "status": "unknown_action",
                    "action": action_type
                }
            
            # Store session state in working memory
            if action_type in ["ensure", "execute"]:
                working_memory = context.get('working_memory')
                if working_memory and "session_id" in result:
                    state = terminal_sessions.get_session_state(result["session_id"])
                    working_memory.add(f"terminal_session_{session_name}", {
                        "session_id": result["session_id"],
                        "active": state.get('active', False),
                        "last_screen": state.get('screen', '')[:500],
                        "command_count": len(state.get('history', []))
                    })
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result=result
            )
            
        except Exception as e:
            logger.error(f"Error in maintain_terminal_session: {e}")
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


class RunTerminalWorkflowAction(Action):
    """Execute complex multi-step terminal workflows."""
    
    def __init__(self):
        super().__init__("run_terminal_workflow", "Execute multi-step terminal workflow")
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Run a workflow of terminal commands."""
        workflow_name = self.params.get("workflow_name", "workflow")
        steps = self.params.get("steps", [])
        session_type = self.params.get("session_type", "bash")
        
        if not steps:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error="No workflow steps provided"
            )
        
        try:
            # Get terminal_sessions
            terminal_sessions = context.get('terminal_sessions')
            if not terminal_sessions:
                from ..python_modules.terminal_sessions import TerminalSessions
                terminal_sessions = TerminalSessions(context)
            
            # Create or get workflow session
            session_id = terminal_sessions.get_or_create(
                f"workflow_{workflow_name}",
                session_type,
                "workflow"
            )
            
            results = []
            success_count = 0
            
            for i, step in enumerate(steps):
                if isinstance(step, str):
                    # Simple command
                    command = step
                    wait_time = 0.5
                else:
                    # Step with options
                    command = step.get("command", "")
                    wait_time = step.get("wait", 0.5)
                
                if command:
                    try:
                        response = terminal_sessions.send_and_remember(
                            session_id,
                            command,
                            wait=wait_time
                        )
                        
                        step_result = {
                            "step": i + 1,
                            "command": command,
                            "success": True,
                            "output": response.get('screen', '')[:200]
                        }
                        success_count += 1
                        
                    except Exception as e:
                        step_result = {
                            "step": i + 1,
                            "command": command,
                            "success": False,
                            "error": str(e)
                        }
                    
                    results.append(step_result)
                    
                    # Check for stop conditions
                    if isinstance(step, dict) and step.get("stop_on_error") and not step_result["success"]:
                        break
            
            # Save final state
            terminal_sessions.save_snapshot(session_id, f"workflow_{workflow_name}_complete")
            
            # Store results in working memory
            working_memory = context.get('working_memory')
            if working_memory:
                working_memory.add(f"workflow_{workflow_name}_results", {
                    "total_steps": len(steps),
                    "completed_steps": len(results),
                    "success_count": success_count,
                    "results": results
                })
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "workflow": workflow_name,
                    "total_steps": len(steps),
                    "completed": len(results),
                    "successful": success_count,
                    "session_id": session_id,
                    "results": results
                }
            )
            
        except Exception as e:
            logger.error(f"Error in run_terminal_workflow: {e}")
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )
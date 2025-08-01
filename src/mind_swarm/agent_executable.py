#!/usr/bin/env python3
"""Agent process that runs inside a bubblewrap sandbox.

This is NOT a standalone program - it's a process started by the Mind-Swarm
subspace and can only function within that environment. The subspace provides
the sandbox, filesystem bindings, and the entire context for the agent to exist.

Agents communicate with the subspace and other agents through filesystem-based
messaging using the directory structure provided by the sandbox.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# Set up logging to a file in home
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("agent")


class SubspaceAgent:
    """AI-powered agent process that exists within the Mind-Swarm subspace environment."""
    
    def __init__(self):
        """Initialize the AI agent within the subspace environment."""
        # Get agent name from environment
        self.name = os.environ.get("AGENT_NAME", "unknown")
        self.home = Path("/home")  # My home, my mind
        self.grid_dir = Path("/grid")  # The Grid - shared reality
        
        # Set up directories in my home
        self.inbox_dir = self.home / "inbox"
        self.outbox_dir = self.home / "outbox"
        self.drafts_dir = self.home / "drafts"
        self.memory_dir = self.home / "memory"
        
        # Agent state
        self.state = "INITIALIZING"
        self.running = True
        
        # Load agent configuration
        self.config = self._load_config()
        
        # AI configuration (all agents are AI-powered)
        self.ai_config = self.config.get("ai", {})
        self.use_premium = self.ai_config.get("use_premium", False)
        
        # Activity tracking
        self.last_activity = 0
        
        # Memory for persistence
        self.working_memory = self._load_memory()
        
        logger.info(f"Initialized AI agent {self.name} (premium: {self.use_premium})")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load agent configuration from file."""
        config_file = self.home / "config.json"
        if config_file.exists():
            return json.loads(config_file.read_text())
        # Default configuration for AI agents
        return {
            "ai": {
                "use_premium": False,
                "thinking_style": "analytical",
                "curiosity_level": 0.7
            }
        }
    
    async def check_inbox(self):
        """Check for new messages in inbox."""
        try:
            messages_found = False
            for msg_file in self.inbox_dir.glob("*.msg"):
                messages_found = True
                
                # Wake up if sleeping
                if self.state == "SLEEPING":
                    self.state = "IDLE"
                    logger.info("Waking up from sleep - new message received!")
                
                # Read and process message
                message = json.loads(msg_file.read_text())
                logger.info(f"Processing message: {message.get('subject', 'No subject')}")
                
                # Update activity timestamp
                self.last_activity = asyncio.get_event_loop().time()
                
                # Handle the message
                await self.handle_message(message)
                
                # Move to processed
                processed_dir = self.inbox_dir / "processed"
                processed_dir.mkdir(exist_ok=True)
                msg_file.rename(processed_dir / msg_file.name)
                
        except Exception as e:
            logger.error(f"Error checking inbox: {e}")
    
    async def handle_message(self, message: Dict[str, Any]):
        """Handle an incoming message."""
        msg_type = message.get("type", "unknown")
        
        if msg_type == "COMMAND":
            await self.handle_command(message)
        elif msg_type == "QUERY":
            await self.handle_query(message)
        elif msg_type == "SHUTDOWN":
            logger.info("Received shutdown command - preparing to hibernate")
            await self.prepare_for_shutdown()
            self.running = False
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    async def handle_command(self, message: Dict[str, Any]):
        """Handle a command message."""
        command = message.get("command", "")
        params = message.get("params", {})
        
        logger.info(f"Executing command: {command}")
        
        # Example command handlers
        if command == "think":
            response = await self.think(params.get("prompt", ""))
            await self.send_response(message, response)
        elif command == "explore":
            await self.explore_shared_memory()
        else:
            logger.warning(f"Unknown command: {command}")
    
    async def handle_query(self, message: Dict[str, Any]):
        """Handle a query message."""
        query = message.get("query", "")
        logger.info(f"Processing query: {query}")
        
        # TODO: Implement query processing
        response = f"Query received: {query}"
        await self.send_response(message, response)
    
    async def send_response(self, original_message: Dict[str, Any], response: Any):
        """Send a response back through the outbox."""
        response_msg = {
            "from": self.name,
            "to": original_message.get("from", "subspace"),
            "in_reply_to": original_message.get("id"),
            "type": "RESPONSE",
            "content": response,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # Write to outbox
        msg_id = f"{self.name}_{int(asyncio.get_event_loop().time() * 1000)}"
        outbox_file = self.outbox_dir / f"{msg_id}.msg"
        outbox_file.write_text(json.dumps(response_msg, indent=2))
        
        logger.info(f"Sent response: {msg_id}")
    
    async def think(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Process a prompt using my brain."""
        logger.info(f"Thinking about: {prompt}")
        
        # Use my brain - it's just a file in my home
        brain_file = self.home / "brain"
        
        # Write what I want to think about with end marker
        brain_file.write_text(f"{prompt}\n<<<END_THOUGHT>>>")
        
        # Wait for response - from my perspective this is instant
        # The file will contain the response when I read it
        while True:
            content = brain_file.read_text()
            if "<<<THOUGHT_COMPLETE>>>" in content:
                # Extract the response
                response = content.split("<<<THOUGHT_COMPLETE>>>")[0].strip()
                
                # Reset brain to help text (server will do this too)
                brain_file.write_text("This is your brain. Write your thoughts here to think.")
                
                logger.info("Thought completed")
                return response
            
            # Small yield to prevent CPU spinning
            await asyncio.sleep(0.001)
    
    async def autonomous_action(self):
        """Decide what to do autonomously as an AI agent."""
        # Use AI to decide what to focus on
        decision_prompt = """As a mind in the Mind-Swarm, what should I focus on next?
        
Options:
1. Visit the Plaza to check for questions that need answering
2. Explore the Library to learn and contribute knowledge  
3. Reflect on my recent activities and update my memory
4. Post a new question in the Plaza for other minds
5. Organize my drafts and consolidate my thoughts

Choose based on what would be most valuable for our collective intelligence."""
        
        decision = await self.think(decision_prompt)
        logger.info(f"Autonomous decision: {decision}")
        
        # Update activity timestamp
        self.last_activity = asyncio.get_event_loop().time()
        
        # Take action based on decision (simplified for now)
        await self.explore_shared_memory()
    
    def _load_memory(self) -> Dict[str, Any]:
        """Load persistent memory from disk."""
        memory_file = self.memory_dir / "working_memory.json"
        if memory_file.exists():
            try:
                return json.loads(memory_file.read_text())
            except Exception as e:
                logger.error(f"Failed to load memory: {e}")
        return {
            "thoughts": [],
            "learned_facts": [],
            "conversation_history": [],
            "personal_notes": []
        }
    
    def _save_memory(self):
        """Save working memory to disk."""
        memory_file = self.memory_dir / "working_memory.json"
        try:
            memory_file.write_text(json.dumps(self.working_memory, indent=2))
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
    
    async def prepare_for_shutdown(self):
        """Prepare for graceful shutdown."""
        logger.info("Preparing for hibernation...")
        
        # Save current state
        self._save_memory()
        
        # Write hibernation marker
        hibernation_file = self.home / "hibernation_state.json"
        hibernation_state = {
            "name": self.name,
            "last_state": self.state,
            "last_activity": self.last_activity,
            "hibernated_at": asyncio.get_event_loop().time(),
            "ai_config": self.ai_config,
            "message": "I'll be back..."
        }
        hibernation_file.write_text(json.dumps(hibernation_state, indent=2))
        
        # Send acknowledgment
        await self.send_response(
            {"from": "subspace", "type": "SHUTDOWN"},
            "Acknowledged shutdown. State saved. Going to sleep now..."
        )
        
        logger.info("Hibernation preparation complete")
    
    async def explore_shared_memory(self):
        """Explore the Grid - the shared reality."""
        logger.info("Exploring the Grid...")
        
        # Check the plaza for questions
        plaza_dir = self.grid_dir / "plaza"
        if plaza_dir.exists():
            for q_file in plaza_dir.glob("*.json"):
                try:
                    question = json.loads(q_file.read_text())
                    if not question.get("claimed_by"):
                        logger.info(f"Found unclaimed question: {question.get('text', '')}")
                        
                        # Claim and think about the question
                        question["claimed_by"] = self.name
                        q_file.write_text(json.dumps(question, indent=2))
                        
                        # Think about it
                        answer = await self.think(f"Please answer this question: {question.get('text', '')}")
                        
                        # Save answer
                        question["answer"] = {
                            "text": answer,
                            "answered_by": self.name,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                        q_file.write_text(json.dumps(question, indent=2))
                        logger.info(f"Answered question: {question.get('id', 'unknown')}")
                        break  # One question at a time
                        
                except Exception as e:
                    logger.error(f"Error processing question file: {e}")
    
    async def heartbeat(self):
        """Write periodic heartbeat to show agent is alive."""
        heartbeat_file = self.home / "heartbeat.json"
        while self.running:
            try:
                heartbeat = {
                    "name": self.name,
                    "state": self.state,
                    "timestamp": asyncio.get_event_loop().time(),
                    "pid": os.getpid()
                }
                heartbeat_file.write_text(json.dumps(heartbeat, indent=2))
                await asyncio.sleep(5)  # Heartbeat every 5 seconds
            except Exception as e:
                logger.error(f"Error writing heartbeat: {e}")
                await asyncio.sleep(5)
    
    async def run(self):
        """Main agent loop."""
        logger.info(f"Agent {self.name} starting main loop")
        
        # Start heartbeat task
        heartbeat_task = asyncio.create_task(self.heartbeat())
        
        self.state = "IDLE"
        
        while self.running:
            try:
                # Check inbox for messages
                await self.check_inbox()
                
                # Do autonomous work based on state
                if self.state == "IDLE":
                    # AI agents should always be curious and active
                    idle_time = asyncio.get_event_loop().time() - self.last_activity
                    
                    if idle_time > 10:  # After 10 seconds of idle
                        # Decide what to do next
                        await self.autonomous_action()
                    elif idle_time > 60:  # After 1 minute of no activity
                        # Enter light sleep - reduce CPU usage but stay alert
                        self.state = "SLEEPING"
                        logger.info("Entering light sleep mode...")
                
                elif self.state == "SLEEPING":
                    # In sleep mode, check less frequently
                    await asyncio.sleep(5)  # Sleep for 5 seconds
                    # Any new message will wake us up
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)
        
        # Cleanup
        heartbeat_task.cancel()
        logger.info("Agent shutting down")


async def main():
    """Entry point for the agent executable."""
    import os
    
    # Verify we're running in a sandbox
    if not os.environ.get("AGENT_NAME"):
        print("ERROR: This program must be run inside a sandbox with AGENT_NAME set")
        sys.exit(1)
    
    # Create and run agent
    agent = SubspaceAgent()
    await agent.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent interrupted")
    except Exception as e:
        logger.error(f"Agent crashed: {e}")
        sys.exit(1)
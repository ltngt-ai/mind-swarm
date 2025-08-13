"""Subspace coordinator that manages Cyber processes and communication."""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import aiofiles
import aiofiles.os

from mind_swarm.subspace.cyber_spawner import CyberSpawner
from mind_swarm.subspace.sandbox import SubspaceManager
from mind_swarm.subspace.cyber_state import CyberStateManager
from mind_swarm.subspace.body_manager import BodySystemManager
from mind_swarm.subspace.body_monitor import create_body_monitor
from mind_swarm.subspace.brain_handler_dynamic import DynamicBrainHandler
from mind_swarm.subspace.cyber_registry import CyberRegistry
from mind_swarm.subspace.developer_registry import DeveloperRegistry
from mind_swarm.subspace.io_handlers import NetworkBodyHandler, UserIOBodyHandler
from mind_swarm.schemas.cyber_types import CyberType
from mind_swarm.ai.providers.factory import create_ai_service
from mind_swarm.utils.logging import logger


class MessageRouter:
    """Routes messages between Cybers through the filesystem."""
    
    def __init__(self, subspace_root: Path):
        self.subspace_root = subspace_root
        self.agents_dir = subspace_root / "cybers"
        
    async def route_outbox_messages(self):
        """Check all Cyber outboxes and route messages to destinations."""
        routed_count = 0
        
        try:
            agent_names = await aiofiles.os.listdir(self.agents_dir)
#            logger.debug(f"Checking outboxes for {len(agent_names)} Cybers: {agent_names}")
        except OSError as e:
            logger.error(f"Failed to list Cybers directory: {e}")
            return routed_count
        
        for cyber_name in agent_names:
            cyber_dir = self.agents_dir / cyber_name
            if not await aiofiles.os.path.isdir(cyber_dir):
                continue
                
            outbox_dir = cyber_dir / "comms" / "outbox"
            if not await aiofiles.os.path.exists(outbox_dir):
                logger.debug(f"No outbox directory for {cyber_name}")
                continue
            
            # Process each message in outbox
            try:
                outbox_files = await aiofiles.os.listdir(outbox_dir)
                # Support both .msg (old format) and .json (new memory API format)
                msg_files = [f for f in outbox_files if f.endswith('.msg') or f.endswith('.json')]
                if msg_files:
                    logger.info(f"Found {len(msg_files)} messages in {cyber_name}'s outbox")
            except OSError as e:
                logger.error(f"Failed to list outbox for {cyber_name}: {e}")
                continue
            
            for msg_filename in msg_files:
                msg_file = outbox_dir / msg_filename
                try:
                    async with aiofiles.open(msg_file, 'r') as f:
                        content = await f.read()
                    message = json.loads(content)
                    to_agent = message.get("to", "")
                    logger.info(f"Routing message from {cyber_name} to {to_agent}")
                    
                    if to_agent == "broadcast":
                        # Broadcast to all Cybers
                        await self._broadcast_message(message, exclude=[cyber_name])
                    elif to_agent.endswith("_dev"):
                        # Message to a developer - store in developer's mailbox
                        await self._deliver_to_developer(to_agent, message)
                    elif to_agent.startswith("Cyber-") or await self._agent_exists(to_agent):
                        # Direct message to another Cyber
                        if not await self._agent_exists(to_agent):
                            # Send error back to sender
                            await self._send_delivery_error(cyber_name, message, f"Cyber {to_agent} not found")
                        else:
                            await self._deliver_message(to_agent, message)
                    else:
                        # Unknown recipient format - be more helpful
                        await self._send_delivery_error(
                            cyber_name, 
                            message, 
                            f"Unknown recipient format: {to_agent}. Use 'Cyber-name' for Cybers or 'name_dev' for developers"
                        )
                    
                    # Move to sent folder
                    sent_dir = cyber_dir / "comms" / "sent"
                    try:
                        await aiofiles.os.makedirs(sent_dir, exist_ok=True)
                    except OSError:
                        pass  # Directory might already exist
                    
                    sent_file = sent_dir / msg_file.name
                    try:
                        await aiofiles.os.rename(msg_file, sent_file)
                    except OSError as e:
                        logger.error(f"Failed to move message file: {e}")
                    routed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error routing message {msg_file}: {e}")
        
        if routed_count > 0:
            logger.info(f"Successfully routed {routed_count} messages")
        
        return routed_count
    
    async def _deliver_message(self, to_agent: str, message: Dict[str, Any]):
        """Deliver a message to a specific Cyber's inbox."""
        target_inbox = self.agents_dir / to_agent / "comms" / "inbox"
        if not await aiofiles.os.path.exists(target_inbox):
            logger.warning(f"Cyber {to_agent} inbox not found")
            return
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        msg_id = message.get("id", f"msg_{timestamp}")
        msg_file = target_inbox / f"{msg_id}.msg"
        
        # Write message
        async with aiofiles.open(msg_file, 'w') as f:
            await f.write(json.dumps(message, indent=2))
        logger.debug(f"Delivered message to {to_agent}")
    
    async def _broadcast_message(self, message: Dict[str, Any], exclude: Optional[List[str]] = None):
        """Broadcast a message to all Cybers."""
        exclude = exclude or []
        
        try:
            agent_names = await aiofiles.os.listdir(self.agents_dir)
        except OSError:
            return
        
        for cyber_name in agent_names:
            cyber_dir = self.agents_dir / cyber_name
            if not await aiofiles.os.path.isdir(cyber_dir) or cyber_name in exclude:
                continue
            
            await self._deliver_message(cyber_name, message)
    
    async def _agent_exists(self, cyber_name: str) -> bool:
        """Check if an Cyber exists."""
        cyber_dir = self.agents_dir / cyber_name
        return await aiofiles.os.path.exists(cyber_dir)
    
    async def _deliver_to_developer(self, to_dev: str, message: Dict[str, Any]):
        """Deliver a message to a developer's mailbox.
        
        Args:
            to_dev: Developer cyber name (e.g., "deano_dev")
            message: Message to deliver
        """
        # Create the developer's inbox directory if it doesn't exist
        dev_inbox = self.agents_dir / to_dev / "inbox"
        try:
            await aiofiles.os.makedirs(dev_inbox, exist_ok=True)
        except OSError:
            pass  # Directory might already exist
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
        msg_id = message.get("id", f"msg_{timestamp}")
        msg_file = dev_inbox / f"{msg_id}.msg"
        
        # Write message
        async with aiofiles.open(msg_file, 'w') as f:
            await f.write(json.dumps(message, indent=2))
        logger.info(f"Delivered message to developer {to_dev}")
    
    async def _send_delivery_error(self, sender: str, original_message: Dict[str, Any], error_reason: str):
        """Send a delivery error message back to the sender."""
        error_message = {
            "type": "DELIVERY_ERROR",
            "from": "subspace",
            "to": sender,
            "error": error_reason,
            "original_message": original_message,
            "timestamp": datetime.now().isoformat()
        }
        
        # Deliver directly to sender's inbox
        await self._deliver_message(sender, error_message)
        logger.info(f"Sent delivery error to {sender}: {error_reason}")


class SubspaceCoordinator:
    """Main coordinator for the subspace environment."""
    
    def __init__(self, root_path: Optional[Path] = None):
        """Initialize the subspace coordinator."""
        self.subspace = SubspaceManager(root_path)
        self.spawner = CyberSpawner(self.subspace)
        self.router = MessageRouter(self.subspace.root_path)
        self.body_system = BodySystemManager()
        self.state_manager = CyberStateManager(self.subspace.root_path)
        self.agent_registry = CyberRegistry(self.subspace.root_path)
        self.developer_registry = DeveloperRegistry(self.subspace.root_path)
        
        self._running = False
        self._frozen = False  # When True, brain handlers stop responding
        self._router_task: Optional[asyncio.Task] = None
        
        # AI services and brain handlers for Cybers (loaded on demand)
        self._ai_services: Dict[str, Any] = {}
        self._brain_handlers: Dict[str, DynamicBrainHandler] = {}
        self._brain_handler_lock = asyncio.Lock()  # Protect brain handler creation
        
        # I/O Cyber handlers
        self._io_handlers: Dict[str, Dict[str, Any]] = {}  # cyber_name -> {"network": handler, "user_io": handler}
        
        # Model selector
        from mind_swarm.ai.model_selector import ModelSelector
        self.model_selector = ModelSelector()
        
        # Cache for Cyber model selections (cyber_name -> selected_model_id)
        # This is in-memory only, not persisted
        self._agent_model_cache: Dict[str, str] = {}
                
        logger.info("Initialized subspace coordinator")
    
    async def start(self):
        """Start the subspace coordinator."""
        self._running = True
        
        
        # Start message routing
        self._router_task = asyncio.create_task(self._message_routing_loop())
        
        # Start all Cybers that have directories
        asyncio.create_task(self._start_all_agents())
        
        logger.info("Subspace coordinator started")
    
    async def stop(self):
        """Stop the subspace coordinator."""
        logger.info("Coordinator stop() called")
        self._running = False
        
        # Prepare Cybers for shutdown
        await self._prepare_agents_for_shutdown()
        
        # Stop routing
        logger.info("Stopping message router...")
        if self._router_task and not self._router_task.done():
            self._router_task.cancel()
            try:
                await self._router_task
            except asyncio.CancelledError:
                pass
        logger.info("Message router stopped")
        
        
        # Shutdown body system
        logger.info("Shutting down body system...")
        await self.body_system.shutdown()
        logger.info("Body system shut down")
        
        # Shutdown all Cybers gracefully
        logger.info("Shutting down Cyber spawner...")
        await self.spawner.shutdown_all()
        logger.info("Cyber spawner shut down")
        
        logger.info("Coordinator stop() complete")
        
        logger.info("Subspace coordinator stopped")
    
    async def create_agent(
        self,
        name: Optional[str] = None,
        cyber_type: str = "general",
        use_ai: bool = False,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new AI Cyber.
        
        Args:
            name: Cyber name (auto-generated from next letter if not provided)
            cyber_type: Type of Cyber ("general" or "io_gateway")
            use_ai: Whether to enable AI (kept for compatibility, always True)
            config: Additional configuration
            
        Returns:
            Cyber ID
        """
        # Parse Cyber type
        try:
            agent_type_enum = CyberType(cyber_type)
        except ValueError:
            logger.warning(f"Unknown Cyber type: {cyber_type}, using GENERAL")
            agent_type_enum = CyberType.GENERAL
        
        # Get type configuration
        type_config = self.agent_registry.get_cyber_type_config(agent_type_enum)
        
        # All Cybers are AI-powered
        cyber_config = config or {}
        
        # Don't persist model selection - it should be dynamic
        cyber_config["ai"] = {
            "thinking_style": cyber_config.get("thinking_style", "analytical"),
            "curiosity_level": cyber_config.get("curiosity_level", 0.7)
        }
        
        # Add type-specific configuration
        cyber_config["cyber_type"] = agent_type_enum.value
        # Convert type_config to a serializable dict
        type_config_dict = {
            "cyber_type": type_config.cyber_type.value,  # Convert enum to string
            "display_name": type_config.display_name,
            "description": type_config.description,
            "sandbox_config": type_config.sandbox_config.__dict__,
            "server_component": type_config.server_component.__dict__ if type_config.server_component else None,
            "default_personality": type_config.default_personality,
            "default_knowledge": type_config.default_knowledge
        }
        cyber_config["type_config"] = type_config_dict
        
        # Create Cyber state (name will be auto-generated if not provided)
        state = await self.state_manager.create_agent(name, cyber_config)
        
        # Register Cyber in directory
        capabilities = []
        if type_config.server_component and type_config.server_component.capabilities:
            capabilities = type_config.server_component.capabilities
        
        self.agent_registry.register_agent(
            name=state.name,
            cyber_type=agent_type_enum,
            capabilities=capabilities,
            metadata={"config": cyber_config}
        )
        
        # Update activation count
        await self.state_manager.increment_activation(state.name)
        await self.state_manager.update_last_active(state.name)
        
        # Start the Cyber process
        await self.spawner.start_agent(
            name=state.name,
            cyber_type=cyber_type,
            config=cyber_config
        )
        
        # Create body files for the Cyber
        cyber_personal = self.subspace.agents_dir / state.name
        body_manager = await self.body_system.create_agent_body(state.name, cyber_personal)
        
        # Create identity file with initial model info
        await self._create_identity_file(state.name, cyber_personal, cyber_type)
        
        # Create additional body files for I/O Cybers
        if agent_type_enum == CyberType.IO_GATEWAY:
            await self._create_io_agent_body_files(state.name, cyber_personal)
        
        # Start monitoring body files
        await self.body_system.start_agent_monitoring(state.name, self._handle_ai_request)
        
        # Start server component for I/O Cybers
        if agent_type_enum == CyberType.IO_GATEWAY and type_config.server_component.enabled:
            await self._start_io_agent_server_component(state.name, type_config)
        
        return state.name
    
    async def terminate_agent(self, name: str):
        """Terminate an Cyber (only in development/emergency)."""
        logger.warning(f"Terminating Cyber {name} - this should be rare!")
        
        # Get Cyber uptime before termination
        cyber_states = await self.spawner.get_cyber_states()
        if name in cyber_states:
            uptime = cyber_states[name].get("uptime", 0)
            await self.state_manager.update_uptime(name, uptime)
        
        # Remove from Cyber registry - they're gone :(
        self.agent_registry.unregister_agent(name)
        
        # Delete Cyber state - this is final, Cybers don't come back from death
        await self.state_manager.delete_agent(name)
        
        # Stop body file monitoring
        await self.body_system.stop_agent_monitoring(name)
        
        # Clean up I/O handlers if this is an I/O Cyber
        if name in self._io_handlers:
            handlers = self._io_handlers[name]
            
            # Cancel monitoring tasks
            if "network_task" in handlers:
                handlers["network_task"].cancel()
            if "user_io_task" in handlers:
                handlers["user_io_task"].cancel()
            
            # Close handlers
            if "network" in handlers:
                await handlers["network"].close()
            
            # Remove from dictionary
            del self._io_handlers[name]
            logger.info(f"Cleaned up I/O handlers for {name}")
        
        # Terminate the Cyber process
        await self.spawner.terminate_agent(name)
    
    async def send_command(self, name: str, command: str, params: Optional[Dict[str, Any]] = None,
                          from_developer: Optional[str] = None):
        """Send a command to an Cyber.
        
        Args:
            name: Target Cyber name
            command: Command to send
            params: Optional command parameters
            from_developer: Optional developer name override
        """
        # Determine sender identity
        sender = "subspace"
        if from_developer:
            # Use provided developer
            dev = self.developer_registry.get_developer(from_developer)
            if dev:
                sender = dev["cyber_name"]
                self.developer_registry.update_developer_activity(from_developer)
        else:
            # Use current developer if set
            current_dev = self.developer_registry.get_current_developer()
            if current_dev:
                sender = current_dev["cyber_name"]
                # Update activity for the username (not cyber_name)
                dev_name = sender.rstrip("_dev")
                self.developer_registry.update_developer_activity(dev_name)
        
        message = {
            "type": "COMMAND",
            "from": sender,
            "command": command,
            "params": params or {},
            "timestamp": datetime.now().isoformat()
        }
        
        await self.spawner.send_message_to_agent(name, message)
    
    async def send_message(self, to_agent: str, content: str, message_type: str = "text",
                          from_developer: Optional[str] = None):
        """Send a regular message to an Cyber.
        
        Args:
            to_agent: Target Cyber name
            content: Message content
            message_type: Type of message (default: "text")
            from_developer: Optional developer name override
        """
        # Determine sender identity
        sender = "subspace"
        if from_developer:
            # Use provided developer
            dev = self.developer_registry.get_developer(from_developer)
            if dev:
                sender = dev["cyber_name"]
                self.developer_registry.update_developer_activity(from_developer)
        else:
            # Use current developer if set
            current_dev = self.developer_registry.get_current_developer()
            if current_dev:
                sender = current_dev["cyber_name"]
                # Update activity for the username (not cyber_name)
                dev_name = sender.rstrip("_dev")
                self.developer_registry.update_developer_activity(dev_name)
        
        message = {
            "from": sender,
            "to": to_agent,
            "type": message_type,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.spawner.send_message_to_agent(to_agent, message)
    
    async def broadcast_command(self, command: str, params: Optional[Dict[str, Any]] = None,
                               from_developer: Optional[str] = None):
        """Broadcast a command to all Cybers."""
        # Determine sender identity
        sender = "subspace"
        if from_developer:
            # Use provided developer
            dev = self.developer_registry.get_developer(from_developer)
            if dev:
                sender = dev["cyber_name"]
                self.developer_registry.update_developer_activity(from_developer)
        else:
            # Use current developer if set
            current_dev = self.developer_registry.get_current_developer()
            if current_dev:
                sender = current_dev["cyber_name"]
                # Update activity for the username (not cyber_name)
                dev_name = sender.rstrip("_dev")
                self.developer_registry.update_developer_activity(dev_name)
        
        message = {
            "type": "COMMAND",
            "from": sender,
            "command": command,
            "params": params or {},
            "timestamp": datetime.now().isoformat()
        }
        
        await self.spawner.broadcast_message(message)
    
    async def get_cyber_states(self) -> Dict[str, Dict[str, Any]]:
        """Get current state of all Cybers."""
        states = await self.spawner.get_cyber_states()
        
        # Enrich with additional info from filesystem and state manager
        for name, state in states.items():
            cyber_dir = self.subspace.agents_dir / name
            if await aiofiles.os.path.exists(cyber_dir):
                # Count messages
                inbox_dir = cyber_dir / "comms" / "inbox"
                outbox_dir = cyber_dir / "comms" / "outbox"
                
                inbox_count = 0
                if await aiofiles.os.path.exists(inbox_dir):
                    try:
                        files = await aiofiles.os.listdir(inbox_dir)
                        inbox_count = len([f for f in files if f.endswith('.msg')])
                    except OSError:
                        inbox_count = 0
                
                outbox_count = 0
                if await aiofiles.os.path.exists(outbox_dir):
                    try:
                        files = await aiofiles.os.listdir(outbox_dir)
                        outbox_count = len([f for f in files if f.endswith('.msg')])
                    except OSError:
                        outbox_count = 0
                
                state.update({
                    "inbox_count": inbox_count,
                    "outbox_count": outbox_count,
                })
            
            # Add persistent state info
            agent_state = await self.state_manager.get_state(name)
            if agent_state:
                state.update({
                    "created_at": agent_state.created_at,
                    "total_uptime": agent_state.total_uptime + state.get("uptime", 0),
                    "activation_count": agent_state.activation_count,
                    "agent_number": self.state_manager.name_generator.get_agent_number(agent_state.name)
                })
        
        return states
    
    async def list_all_agents(self) -> List[Dict[str, Any]]:
        """List all known Cybers including hibernating ones."""
        all_agents = []
        
        all_states = await self.state_manager.list_agents()
        for state in all_states:
            cyber_info = {
                "name": state.name,
                "agent_number": self.state_manager.name_generator.get_agent_number(state.name),
                "status": "running",  # If we found the state, Cyber exists
                "created_at": state.created_at,
                "last_active": state.last_active,
                "total_uptime": state.total_uptime,
                "activation_count": state.activation_count
            }
            all_agents.append(cyber_info)
        
        # Sort by Cyber number
        all_agents.sort(key=lambda x: x["agent_number"])
        
        return all_agents
    
    async def _start_all_agents(self):
        """Start all Cybers that have directories in the subspace."""
        logger.info("Starting all Cybers with directories...")
        
        try:
            # List all directories in Cybers/
            agents_dir = self.subspace.agents_dir
            if not agents_dir.exists():
                logger.info("No Cybers directory found")
                return
            
            agent_dirs = [d for d in agents_dir.iterdir() if d.is_dir()]
            
            if not agent_dirs:
                logger.info("No Cyber directories found")
                return
            
            logger.info(f"Found {len(agent_dirs)} Cyber directories to start")
            
            for cyber_dir in agent_dirs:
                cyber_name = cyber_dir.name
                
                # Skip developer accounts (they don't need brain monitoring or processes)
                if cyber_name.endswith("_dev"):
                    logger.info(f"Skipping developer account {cyber_name}")
                    continue
                
                try:
                    logger.info(f"Starting Cyber {cyber_name}")
                    
                    # Load config if exists
                    config = {}
                    config_file = cyber_dir / "config.json"
                    if config_file.exists():
                        config = json.loads(config_file.read_text())
                    
                    # Determine Cyber type from config or registry
                    cyber_type = config.get("type", "general")
                    
                    # Register Cyber if not already registered
                    if not self.agent_registry.get_agent(cyber_name):
                        agent_type_enum = CyberType.IO_GATEWAY if cyber_type == "io_gateway" else CyberType.GENERAL
                        self.agent_registry.register_agent(cyber_name, agent_type_enum)
                    
                    # Start the Cyber process
                    await self.spawner.start_agent(
                        name=cyber_name,
                        config=config
                    )
                    
                    # Create body files for the Cyber
                    body_manager = await self.body_system.create_agent_body(cyber_name, cyber_dir)
                    
                    # Ensure identity file exists (create if missing)
                    identity_file = cyber_dir / ".internal" / "identity.json"
                    if not identity_file.exists():
                        await self._create_identity_file(cyber_name, cyber_dir, cyber_type)
                    
                    # Start monitoring body files
                    await self.body_system.start_agent_monitoring(cyber_name, self._handle_ai_request)
                    
                    # Start I/O monitoring if it's an I/O Cyber
                    if cyber_type == "io_gateway":
                        await self._start_io_body_monitoring(cyber_name)
                    
                    logger.info(f"Cyber {cyber_name} started successfully")
                    
                except Exception as e:
                    logger.error(f"Failed to start Cyber {cyber_name}: {e}")
                    # Continue with other Cybers
        
        except Exception as e:
            logger.error(f"Error starting Cybers: {e}")
    
    
    async def _prepare_agents_for_shutdown(self):
        """Freeze the Cyber world before shutdown."""
        logger.info("Freezing Cyber world for shutdown...")
        
        # Stop message routing - no new messages delivered
        self._running = False
        
        # Set flag to make brain handlers stop responding
        self._frozen = True
        
        # Create shutdown files for all Cybers
        logger.info("Creating shutdown files for all Cybers...")
        cyber_states = await self.spawner.get_cyber_states()
        for cyber_name in cyber_states:
            shutdown_file = self.subspace.root_path / "cybers" / cyber_name / ".internal" / "shutdown"
            try:
                shutdown_file.write_text("SHUTDOWN")
                logger.debug(f"Created shutdown file for {cyber_name}")
            except Exception as e:
                logger.error(f"Failed to create shutdown file for {cyber_name}: {e}")
        
        # Give Cybers time to notice shutdown files and exit gracefully
        logger.info("Waiting for Cybers to shutdown gracefully...")
        await asyncio.sleep(5)  # Give Cybers 5 seconds to notice shutdown files
        
        # Cybers should now have exited gracefully
    
    async def _message_routing_loop(self):
        """Main loop for routing messages between Cybers."""
        logger.info("Message routing started")
        
        while self._running:
            try:
                # Route messages
                await self.router.route_outbox_messages()
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error in message routing: {e}")
                await asyncio.sleep(1)
        
        logger.info("Message routing stopped")
    
    async def get_community_questions(self) -> List[Dict[str, Any]]:
        """Get all questions from the Community."""
        questions = []
        community_dir = self.subspace.community_dir
        
        try:
            files = await aiofiles.os.listdir(community_dir)
            json_files = [f for f in files if f.endswith('.json')]
            
            for filename in json_files:
                q_file = community_dir / filename
                try:
                    async with aiofiles.open(q_file, 'r') as f:
                        content = await f.read()
                    question = json.loads(content)
                    questions.append(question)
                except Exception as e:
                    logger.error(f"Error reading question {q_file}: {e}")
        except OSError as e:
            logger.error(f"Error listing community directory: {e}")
        
        return questions
    
    async def create_community_question(self, text: str, created_by: str = "user") -> str:
        """Create a new question in the Community."""
        question_id = f"q_{int(asyncio.get_event_loop().time() * 1000)}"
        question = {
            "id": question_id,
            "text": text,
            "created_by": created_by,
            "created_at": datetime.now().isoformat(),
            "claimed_by": None,
            "answer": None
        }
        
        q_file = self.subspace.community_dir / f"{question_id}.json"
        async with aiofiles.open(q_file, 'w') as f:
            await f.write(json.dumps(question, indent=2))
        
        logger.info(f"Posted question to Community: {question_id}")
        return question_id
    
    async def _handle_ai_request(self, name: str, prompt: str) -> str:
        """Handle an AI request from an Cyber's brain file.
        
        Args:
            name: The Cyber making the request
            prompt: The thought to process (may be JSON ThinkingRequest)
            
        Returns:
            The AI response
        """
        # If frozen, don't respond - Cyber will hang waiting
        if self._frozen:
            logger.debug(f"Brain request from {name} ignored - world is frozen")
            # Never return - Cyber is frozen in time
            while self._frozen:
                await asyncio.sleep(1)
            # If we somehow unfreeze, still don't process this request
            return ""
        
        logger.info(f"Processing thought for {name}: {prompt[:200]}...")
        
        try:
            # Get Cyber configuration to determine which model to use
            cyber_states = await self.spawner.get_cyber_states()
            cyber_info = cyber_states.get(name, {})
            
            # Check if we have a cached model selection for this Cyber
            selected_model_id = self._agent_model_cache.get(name)
            
            if selected_model_id:
                # Use cached model
                logger.debug(f"Using cached model {selected_model_id} for Cyber {name}")
                selected_model = self.model_selector.pool.get_model(selected_model_id)
                if selected_model:
                    from dataclasses import asdict
                    config_obj = self.model_selector.get_model_config(selected_model)
                    # Convert to dict format expected by DSPy
                    config_dict = asdict(config_obj)
                    model_config = {
                        'provider': config_dict['provider'],
                        'model': config_dict['model_id'],
                        'temperature': config_dict['temperature'],
                        'max_tokens': config_dict['max_tokens'],
                        'api_key': config_dict.get('api_key'),
                        'provider_settings': config_dict.get('provider_settings'),
                    }
                else:
                    # Cached model no longer available, clear cache
                    logger.warning(f"Cached model {selected_model_id} no longer available, selecting new model")
                    del self._agent_model_cache[name]
                    selected_model_id = None
            
            if not selected_model_id:
                # No cached model, select one dynamically
                import os
                api_key = os.getenv("OPENROUTER_API_KEY")
                
                # Select a model from the pool
                selected_model = self.model_selector.select_model(paid_allowed=False)
                
                if selected_model:
                    from dataclasses import asdict
                    config_obj = self.model_selector.get_model_config(selected_model)
                    # Convert to dict format expected by DSPy
                    config_dict = asdict(config_obj)
                    model_config = {
                        'provider': config_dict['provider'],
                        'model': config_dict['model_id'],
                        'temperature': config_dict['temperature'],
                        'max_tokens': config_dict['max_tokens'],
                        'api_key': config_dict.get('api_key'),
                        'provider_settings': config_dict.get('provider_settings'),
                    }
                    selected_model_id = selected_model.id
                    # Cache the selection
                    self._agent_model_cache[name] = selected_model_id
                    logger.info(f"Selected and cached model {selected_model_id} for Cyber {name}")
                else:
                    # Ultimate fallback to local model
                    logger.warning("No suitable model found, using fallback")
                    from dataclasses import asdict
                    from mind_swarm.ai.config import AIExecutionConfig
                    
                    config_obj = AIExecutionConfig(
                        provider="openai",
                        model_id="local/default",
                        temperature=0.7,
                        max_tokens=4096,
                        api_key=os.getenv("OPENAI_API_KEY", ""),
                        provider_settings={
                            "host": "http://192.168.1.209:1234"
                        }
                    )
                    
                    # Convert to dict format expected by DSPy
                    config_dict = asdict(config_obj)
                    model_config = {
                        'provider': config_dict['provider'],
                        'model': config_dict['model_id'],
                        'temperature': config_dict['temperature'],
                        'max_tokens': config_dict['max_tokens'],
                        'api_key': config_dict.get('api_key'),
                        'provider_settings': config_dict.get('provider_settings'),
                    }
                    selected_model_id = "local/default"
                    
                    # Cache the fallback
                    self._agent_model_cache[name] = selected_model_id
            
            # Ensure API key is included for providers that need it
            if model_config.get("provider") == "openrouter" and "api_key" not in model_config:
                import os
                api_key = os.getenv("OPENROUTER_API_KEY")
                if api_key:
                    model_config = model_config.copy()  # Don't modify the original
                    model_config["api_key"] = api_key
                else:
                    logger.error("OpenRouter API key not found in environment")
            
            # Create a unique key for this model config
            config_key = f"{model_config['provider']}:{model_config['model']}"
            
            # Use lock to protect brain handler creation
            async with self._brain_handler_lock:
                if config_key not in self._brain_handlers:
                    # Create brain handler for this model config
                    logger.info(f"Creating brain handler for {config_key} with config: {model_config}")
                    # Note: We pass model_config directly to DynamicBrainHandler
                    # The handler will create its own DSPy LM instance
                    self._brain_handlers[config_key] = DynamicBrainHandler(
                        None, 
                        model_config,
                        model_switch_callback=self._on_model_switch
                    )
                
                brain_handler = self._brain_handlers[config_key]
            
            # Process the thinking request with dynamic handler
            start_time = asyncio.get_event_loop().time()
            response = await brain_handler.process_thinking_request(name, prompt)
            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Update model metrics
            if selected_model_id:
                # Estimate tokens (rough approximation)
                estimated_tokens = len(prompt.split()) + len(response.split())
                # Metrics tracking can be added to model pool later if needed
                logger.debug(f"Model {selected_model_id} succeeded in {elapsed_ms:.0f}ms with ~{estimated_tokens} tokens")
                
                # Update Cyber's identity file with current model info
                await self._update_agent_model_info(name, selected_model_id)
            
            # Emit brain response event for monitoring
            try:
                from mind_swarm.server.brain_monitor import get_brain_monitor
                monitor = get_brain_monitor()
                await monitor.on_brain_response(name, response)
            except ImportError:
                pass  # Brain monitor not available (running in subspace only)
            except Exception as e:
                logger.debug(f"Failed to emit brain response: {e}")
            
            # Response already includes <<<THOUGHT_COMPLETE>>> from brain handler
            logger.info(f"Thought processed for {name}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing AI request for {name}: {e}")
            
            # Update model metrics for failure
            if selected_model_id:
                # Metrics tracking can be added to model pool later if needed
                logger.error(f"Model {selected_model_id} failed: {e}")
            
            # Return a properly formatted error response
            return json.dumps({
                "request_id": "error",
                "signature_hash": "error",
                "output_values": {"error": str(e), "response": f"My thinking was interrupted: {str(e)}"},
                "metadata": {"error": True, "cyber_id": name}
            }, indent=2) + "\n<<<THOUGHT_COMPLETE>>>"
    
    def _get_lm_config_from_ai_service(self, ai_service: Any, ai_config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract language model configuration from AI service."""
        # This extracts the config needed for DSPy from our AI service
        # ai_config comes from the preset and should have all the right values
        lm_config = {
            "provider": ai_config.get("provider"),
            "model": ai_config.get("model"),
            "temperature": ai_config.get("temperature", 0.7),
            "max_tokens": ai_config.get("max_tokens", 1000)
        }
        
        # Add API key and base URL based on provider
        if hasattr(ai_service, 'api_key'):
            lm_config["api_key"] = ai_service.api_key
        elif hasattr(ai_service, 'config'):
            # Convert config to dict if needed
            config_dict = ai_service.config.__dict__ if hasattr(ai_service.config, '__dict__') else ai_service.config
            if isinstance(config_dict, dict) and 'api_key' in config_dict:
                lm_config["api_key"] = config_dict['api_key']
        
        if hasattr(ai_service, 'base_url'):
            lm_config["base_url"] = ai_service.base_url
        elif hasattr(ai_service, 'config'):
            # Convert config to dict if needed
            config_dict = ai_service.config.__dict__ if hasattr(ai_service.config, '__dict__') else ai_service.config
            if isinstance(config_dict, dict) and 'base_url' in config_dict:
                lm_config["base_url"] = config_dict['base_url']
        
        # Check for provider_settings or api_settings (for local models)
        settings = ai_config.get("provider_settings") or ai_config.get("api_settings")
        if settings and isinstance(settings, dict) and "host" in settings:
            lm_config["base_url"] = settings["host"]
        
        return lm_config
    
    async def boost_agent_brain(self, cyber_name: str, model_id: str) -> bool:
        """Boost an Cyber's brain by changing its model.
        
        Args:
            cyber_name: Name of the Cyber to boost
            model_id: Model ID to use (must be in registry)
            
        Returns:
            True if successful, False otherwise
        """
        # Check if model exists
        model = self.model_selector.pool.get_model(model_id)
        if not model:
            logger.error(f"Model {model_id} not found in pool")
            return False
        
        # Update the cache
        self._agent_model_cache[cyber_name] = model_id
        logger.info(f"Boosted Cyber {cyber_name} to use model {model_id}")
        
        # Clear any existing brain handler to force recreation with new model
        # Find and remove brain handlers for this Cyber
        handlers_to_remove = []
        for key in self._brain_handlers:
            if any(h.cyber_name == cyber_name for h in [self._brain_handlers[key]] if hasattr(h, 'cyber_name')):
                handlers_to_remove.append(key)
        
        for key in handlers_to_remove:
            del self._brain_handlers[key]
        
        return True
    
    def clear_agent_model_cache(self, cyber_name: Optional[str] = None):
        """Clear cached model selection for Cyber(s).
        
        Args:
            cyber_name: Specific Cyber to clear, or None to clear all
        """
        if cyber_name:
            if cyber_name in self._agent_model_cache:
                del self._agent_model_cache[cyber_name]
                logger.info(f"Cleared model cache for Cyber {cyber_name}")
        else:
            self._agent_model_cache.clear()
            logger.info("Cleared all Cyber model caches")
    
    async def _create_identity_file(self, cyber_name: str, cyber_personal: Path, cyber_type: str):
        """Create identity file for the Cyber with vital statistics.
        
        Args:
            cyber_name: Name of the Cyber
            cyber_personal: Cyber's home directory
            cyber_type: Type of Cyber
        """
        # Select initial model for the Cyber
        selected_model = self.model_selector.select_model(paid_allowed=False)
        
        if selected_model:
            model_id = selected_model.id
            provider = selected_model.provider
            max_context_length = selected_model.context_length
        else:
            # Ultimate fallback
            model_id = "local/default"
            provider = "openai"
            max_context_length = 8192
            logger.warning("Using fallback model for identity")
        
        # Determine capabilities based on Cyber type
        capabilities = []
        if cyber_type == "io_gateway":
            capabilities = ["network", "user_io"]
        
        # Create identity data - only what the Cyber can actually use
        identity_data = {
            "name": cyber_name,
            "cyber_type": cyber_type,
            "capabilities": capabilities
        }
        
        # Write identity file to .internal directory
        internal_dir = cyber_personal / ".internal"
        internal_dir.mkdir(exist_ok=True)
        identity_file = internal_dir / "identity.json"
        identity_file.write_text(json.dumps(identity_data, indent=2))
        
        # Cache the model selection
        self._agent_model_cache[cyber_name] = model_id
        
        logger.info(f"Created identity file for {cyber_name}: model={model_id}, context={max_context_length}")
    
    async def _create_io_agent_body_files(self, cyber_name: str, cyber_personal: Path):
        """Create additional body files for I/O Cybers.
        
        Args:
            cyber_name: Name of the I/O Cyber
            cyber_personal: Cyber's home directory
        """
        io_bodies_dir = cyber_personal / ".io_bodies"
        io_bodies_dir.mkdir(exist_ok=True)
        
        # Create network body file
        network_file = io_bodies_dir / "network"
        network_file.write_text("")
        logger.info(f"Created network body file for {cyber_name}")
        
        # Create user_io body file  
        user_io_file = io_bodies_dir / "user_io"
        user_io_file.write_text("")
        logger.info(f"Created user_io body file for {cyber_name}")
        
        # Create handlers
        network_handler = NetworkBodyHandler(cyber_name, network_file)
        user_io_handler = UserIOBodyHandler(cyber_name, user_io_file)
        
        # Store handlers
        self._io_handlers[cyber_name] = {
            "network": network_handler,
            "user_io": user_io_handler,
            "network_file": network_file,
            "user_io_file": user_io_file
        }
        
        # Set up monitoring for these special body files
        await self._start_io_body_monitoring(cyber_name)
    
    async def _on_model_switch(self, cyber_name: str, model_id: str, max_context_length: int):
        """Callback when brain handler switches models.
        
        Args:
            cyber_name: Name of the Cyber
            model_id: ID of the new model
            max_context_length: Context length of the new model
        """
        logger.info(f"Model switch for {cyber_name}: {model_id} (context: {max_context_length})")
        await self._update_agent_model_info(cyber_name, model_id)
    
    async def _update_agent_model_info(self, cyber_name: str, model_id: str):
        """Update Cyber's identity file with current model information.
        
        Args:
            cyber_name: Name of the Cyber
            model_id: ID of the model being used
        """
        try:
            cyber_personal = self.subspace.agents_dir / cyber_name
            identity_file = cyber_personal / ".internal" / "identity.json"
            
            if identity_file.exists():
                # Load existing identity
                identity_data = json.loads(identity_file.read_text())
                
                # Identity doesn't need updating - it's static
                logger.debug(f"Identity for {cyber_name} remains unchanged")
            else:
                logger.warning(f"Identity file not found for {cyber_name}")
                
        except Exception as e:
            logger.error(f"Error updating Cyber model info: {e}")
    
    async def _start_io_body_monitoring(self, cyber_name: str):
        """Start monitoring I/O body files for an Cyber.
        
        Args:
            cyber_name: Name of the I/O Cyber
        """
        if cyber_name not in self._io_handlers:
            logger.error(f"No I/O handlers found for {cyber_name}")
            return
            
        handlers = self._io_handlers[cyber_name]
        
        # Start monitoring tasks for each body file
        network_task = asyncio.create_task(
            self._monitor_io_body_file(cyber_name, "network", handlers["network_file"], handlers["network"])
        )
        user_io_task = asyncio.create_task(
            self._monitor_io_body_file(cyber_name, "user_io", handlers["user_io_file"], handlers["user_io"])
        )
        
        # Store tasks so we can cancel them later if needed
        handlers["network_task"] = network_task
        handlers["user_io_task"] = user_io_task
        
        logger.info(f"Started I/O body file monitoring for {cyber_name}")
    
    async def _monitor_io_body_file(self, cyber_name: str, file_type: str, file_path: Path, handler):
        """Monitor a single I/O body file for changes.
        
        Args:
            cyber_name: Name of the I/O Cyber
            file_type: Type of body file (network or user_io)
            file_path: Path to the body file
            handler: Handler instance for processing requests
        """
        logger.info(f"Monitoring {file_type} body file for {cyber_name}")
        last_content = ""
        
        while cyber_name in self._io_handlers:
            try:
                # Check if file has content
                current_content = file_path.read_text().strip()
                
                if current_content and current_content != last_content:
                    logger.info(f"Processing {file_type} request for {cyber_name}")
                    
                    # Process the request
                    response = await handler.handle_request(current_content)
                    
                    # Write response back
                    file_path.write_text(response)
                    last_content = response
                    
                    logger.info(f"Completed {file_type} request for {cyber_name}")
                
                # Small delay to avoid busy waiting
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring {file_type} body file for {cyber_name}: {e}")
                await asyncio.sleep(1)  # Back off on error
    
    async def _start_io_agent_server_component(self, cyber_name: str, type_config):
        """Start the server-side component for an I/O Cyber.
        
        Args:
            cyber_name: Name of the I/O Cyber
            type_config: Cyber type configuration
        """
        # The I/O body file monitoring is the main server component
        logger.info(f"I/O Cyber server component initialized for {cyber_name}")
    
    
    # Developer management methods
    async def register_developer(self, name: str, full_name: Optional[str] = None,
                               email: Optional[str] = None) -> str:
        """Register a new developer account.
        
        Args:
            name: Developer username
            full_name: Optional full name
            email: Optional email address
            
        Returns:
            Developer Cyber name (e.g., "deano_dev")
        """
        cyber_name = self.developer_registry.register_developer(name, full_name, email)
        
        # Update Cyber registry to include developer
        await self.agent_registry.update_registry()
        
        logger.info(f"Registered developer {name} as {cyber_name}")
        return cyber_name
    
    async def set_current_developer(self, name: str) -> bool:
        """Set the current developer.
        
        Args:
            name: Developer username
            
        Returns:
            True if successful
        """
        success = self.developer_registry.set_current_developer(name)
        if success:
            logger.info(f"Set current developer to {name}")
        else:
            logger.warning(f"Failed to set developer {name} - not found")
        return success
    
    async def get_current_developer(self) -> Optional[Dict[str, Any]]:
        """Get current developer information."""
        return self.developer_registry.get_current_developer()
    
    async def list_developers(self) -> Dict[str, Dict[str, Any]]:
        """List all registered developers."""
        return self.developer_registry.list_developers()
    
    async def check_developer_mailbox(self, include_read: bool = False) -> List[Dict[str, Any]]:
        """Check current developer's mailbox."""
        current_dev = self.developer_registry.get_current_developer()
        if not current_dev:
            return []
        
        # Get username from cyber_name (remove _dev suffix)
        dev_name = current_dev["cyber_name"].rstrip("_dev")
        return self.developer_registry.check_developer_inbox(dev_name, include_read=include_read)
    
    async def mark_developer_message_read(self, message_index: int) -> bool:
        """Mark a developer message as read by index."""
        current_dev = self.developer_registry.get_current_developer()
        if not current_dev:
            return False
        
        # Get username from cyber_name (remove _dev suffix)
        dev_name = current_dev["cyber_name"].rstrip("_dev")
        
        # Get the messages to find the file path
        messages = self.developer_registry.check_developer_inbox(dev_name, include_read=False)
        if 0 <= message_index < len(messages):
            message_path = messages[message_index].get('_file_path')
            if message_path:
                return self.developer_registry.mark_message_as_read(dev_name, message_path)
        
        return False

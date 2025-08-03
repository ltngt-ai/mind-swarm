"""Subspace coordinator that manages agent processes and communication."""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import aiofiles
import aiofiles.os

from mind_swarm.subspace.agent_spawner import AgentSpawner
from mind_swarm.subspace.sandbox import SubspaceManager
from mind_swarm.subspace.agent_state import AgentStateManager, AgentLifecycle
from mind_swarm.subspace.body_manager import BodySystemManager
from mind_swarm.subspace.body_monitor import create_body_monitor
from mind_swarm.subspace.brain_handler_dynamic import DynamicBrainHandler
from mind_swarm.subspace.agent_registry import AgentRegistry
from mind_swarm.schemas.agent_types import AgentType
from mind_swarm.ai.presets import preset_manager
from mind_swarm.ai.providers.factory import create_ai_service
from mind_swarm.utils.logging import logger


class MessageRouter:
    """Routes messages between agents through the filesystem."""
    
    def __init__(self, subspace_root: Path):
        self.subspace_root = subspace_root
        self.agents_dir = subspace_root / "agents"
        
    async def route_outbox_messages(self):
        """Check all agent outboxes and route messages to destinations."""
        routed_count = 0
        
        try:
            agent_names = await aiofiles.os.listdir(self.agents_dir)
            logger.debug(f"Checking outboxes for {len(agent_names)} agents: {agent_names}")
        except OSError as e:
            logger.error(f"Failed to list agents directory: {e}")
            return routed_count
        
        for agent_name in agent_names:
            agent_dir = self.agents_dir / agent_name
            if not await aiofiles.os.path.isdir(agent_dir):
                continue
                
            outbox_dir = agent_dir / "outbox"
            if not await aiofiles.os.path.exists(outbox_dir):
                logger.debug(f"No outbox directory for {agent_name}")
                continue
            
            # Process each message in outbox
            try:
                outbox_files = await aiofiles.os.listdir(outbox_dir)
                msg_files = [f for f in outbox_files if f.endswith('.msg')]
                if msg_files:
                    logger.info(f"Found {len(msg_files)} messages in {agent_name}'s outbox")
            except OSError as e:
                logger.error(f"Failed to list outbox for {agent_name}: {e}")
                continue
            
            for msg_filename in msg_files:
                msg_file = outbox_dir / msg_filename
                try:
                    async with aiofiles.open(msg_file, 'r') as f:
                        content = await f.read()
                    message = json.loads(content)
                    to_agent = message.get("to", "")
                    logger.info(f"Routing message from {agent_name} to {to_agent}")
                    
                    if to_agent == "broadcast":
                        # Broadcast to all agents
                        await self._broadcast_message(message, exclude=[agent_name])
                    elif to_agent.startswith("agent-"):
                        # Direct message to another agent
                        if not await self._agent_exists(to_agent):
                            # Send error back to sender
                            await self._send_delivery_error(agent_name, message, f"Agent {to_agent} not found")
                        else:
                            await self._deliver_message(to_agent, message)
                    else:
                        # Unknown recipient format
                        await self._send_delivery_error(agent_name, message, f"Unknown recipient format: {to_agent}")
                    
                    # Move to sent folder
                    sent_dir = outbox_dir / "sent"
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
        """Deliver a message to a specific agent's inbox."""
        target_inbox = self.agents_dir / to_agent / "inbox"
        if not await aiofiles.os.path.exists(target_inbox):
            logger.warning(f"Agent {to_agent} inbox not found")
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
        """Broadcast a message to all agents."""
        exclude = exclude or []
        
        try:
            agent_names = await aiofiles.os.listdir(self.agents_dir)
        except OSError:
            return
        
        for agent_name in agent_names:
            agent_dir = self.agents_dir / agent_name
            if not await aiofiles.os.path.isdir(agent_dir) or agent_name in exclude:
                continue
            
            await self._deliver_message(agent_name, message)
    
    async def _agent_exists(self, agent_name: str) -> bool:
        """Check if an agent exists."""
        agent_dir = self.agents_dir / agent_name
        return await aiofiles.os.path.exists(agent_dir)
    
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
        self.spawner = AgentSpawner(self.subspace)
        self.router = MessageRouter(self.subspace.root_path)
        self.body_system = BodySystemManager()
        self.state_manager = AgentStateManager(self.subspace.root_path)
        self.agent_registry = AgentRegistry(self.subspace.root_path)
        
        self._running = False
        self._router_task: Optional[asyncio.Task] = None
        
        # AI services and brain handlers for agents (loaded on demand)
        self._ai_services: Dict[str, Any] = {}
        self._brain_handlers: Dict[str, DynamicBrainHandler] = {}
        self._brain_handler_lock = asyncio.Lock()  # Protect brain handler creation
                
        logger.info("Initialized subspace coordinator")
    
    async def start(self):
        """Start the subspace coordinator."""
        self._running = True
        
        # Start message routing
        self._router_task = asyncio.create_task(self._message_routing_loop())
        
        # Restore sleeping agents in background to not block
        asyncio.create_task(self._restore_sleeping_agents_background())
        
        logger.info("Subspace coordinator started")
    
    async def stop(self):
        """Stop the subspace coordinator."""
        self._running = False
        
        # Prepare agents for shutdown
        await self._prepare_agents_for_shutdown()
        
        # Stop routing
        if self._router_task and not self._router_task.done():
            self._router_task.cancel()
            try:
                await self._router_task
            except asyncio.CancelledError:
                pass
        
        # Shutdown body system
        await self.body_system.shutdown()
        
        # Shutdown all agents gracefully
        await self.spawner.shutdown_all()
        
        # Mark all agents as sleeping
        await self.state_manager.mark_all_sleeping()
        
        logger.info("Subspace coordinator stopped")
    
    async def create_agent(
        self,
        name: Optional[str] = None,
        agent_type: str = "general",
        use_ai: bool = False,
        use_premium: bool = False,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new AI agent.
        
        Args:
            name: Agent name (auto-generated from next letter if not provided)
            agent_type: Type of agent ("general" or "io_gateway")
            use_ai: Whether to enable AI (kept for compatibility, always True)
            use_premium: Whether to use premium AI model
            config: Additional configuration
            
        Returns:
            Agent ID
        """
        # Parse agent type
        try:
            agent_type_enum = AgentType(agent_type)
        except ValueError:
            logger.warning(f"Unknown agent type: {agent_type}, using GENERAL")
            agent_type_enum = AgentType.GENERAL
        
        # Get type configuration
        type_config = self.agent_registry.get_agent_type_config(agent_type_enum)
        
        # All agents are AI-powered
        agent_config = config or {}
        agent_config["ai"] = {
            "use_premium": use_premium,
            "thinking_style": agent_config.get("thinking_style", "analytical"),
            "curiosity_level": agent_config.get("curiosity_level", 0.7)
        }
        
        # Add type-specific configuration
        agent_config["agent_type"] = agent_type_enum.value
        # Convert type_config to a serializable dict
        type_config_dict = {
            "agent_type": type_config.agent_type.value,  # Convert enum to string
            "display_name": type_config.display_name,
            "description": type_config.description,
            "sandbox_config": type_config.sandbox_config.__dict__,
            "server_component": type_config.server_component.__dict__ if type_config.server_component else None,
            "default_personality": type_config.default_personality,
            "default_knowledge": type_config.default_knowledge
        }
        agent_config["type_config"] = type_config_dict
        
        # Create agent state (name will be auto-generated if not provided)
        state = await self.state_manager.create_agent(name, agent_config)
        
        # Register agent in directory
        capabilities = []
        if type_config.server_component and type_config.server_component.capabilities:
            capabilities = type_config.server_component.capabilities
        
        self.agent_registry.register_agent(
            name=state.name,
            agent_type=agent_type_enum,
            capabilities=capabilities,
            metadata={"config": agent_config}
        )
        
        # Update lifecycle
        await self.state_manager.update_lifecycle(state.name, AgentLifecycle.ACTIVE)
        await self.state_manager.increment_activation(state.name)
        
        # Start the agent process
        await self.spawner.start_agent(
            name=state.name,
            agent_type=agent_type,
            config=agent_config
        )
        
        # Create body files for the agent
        agent_home = self.subspace.agents_dir / state.name
        body_manager = await self.body_system.create_agent_body(state.name, agent_home)
        
        # Create additional body files for I/O agents
        if agent_type_enum == AgentType.IO_GATEWAY:
            await self._create_io_agent_body_files(state.name, agent_home)
        
        # Start monitoring body files
        await self.body_system.start_agent_monitoring(state.name, self._handle_ai_request)
        
        # Start server component for I/O agents
        if agent_type_enum == AgentType.IO_GATEWAY and type_config.server_component.enabled:
            await self._start_io_agent_server_component(state.name, type_config)
        
        return state.name
    
    async def terminate_agent(self, name: str):
        """Terminate an agent (only in development/emergency)."""
        logger.warning(f"Terminating agent {name} - this should be rare!")
        
        # Get agent uptime before termination
        agent_states = await self.spawner.get_agent_states()
        if name in agent_states:
            uptime = agent_states[name].get("uptime", 0)
            await self.state_manager.update_uptime(name, uptime)
        
        # Mark as hibernating (terminated agents can be restored later)
        await self.state_manager.update_lifecycle(name, AgentLifecycle.HIBERNATING)
        
        # Update agent registry
        self.agent_registry.update_agent_status(name, "hibernating")
        
        # Stop body file monitoring
        await self.body_system.stop_agent_monitoring(name)
        
        # Terminate the agent process
        await self.spawner.terminate_agent(name)
    
    async def send_command(self, name: str, command: str, params: Optional[Dict[str, Any]] = None):
        """Send a command to an agent."""
        message = {
            "type": "COMMAND",
            "from": "subspace",
            "command": command,
            "params": params or {},
            "timestamp": datetime.now().isoformat()
        }
        
        await self.spawner.send_message_to_agent(name, message)
    
    async def broadcast_command(self, command: str, params: Optional[Dict[str, Any]] = None):
        """Broadcast a command to all agents."""
        message = {
            "type": "COMMAND",
            "from": "subspace",
            "command": command,
            "params": params or {},
            "timestamp": datetime.now().isoformat()
        }
        
        await self.spawner.broadcast_message(message)
    
    async def get_agent_states(self) -> Dict[str, Dict[str, Any]]:
        """Get current state of all agents."""
        states = await self.spawner.get_agent_states()
        
        # Enrich with additional info from filesystem and state manager
        for name, state in states.items():
            agent_dir = self.subspace.agents_dir / name
            if await aiofiles.os.path.exists(agent_dir):
                # Count messages
                inbox_dir = agent_dir / "inbox"
                outbox_dir = agent_dir / "outbox"
                
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
        """List all known agents including hibernating ones."""
        all_agents = []
        
        all_states = await self.state_manager.list_agents()
        for state in all_states:
            agent_info = {
                "name": state.name,
                "agent_number": self.state_manager.name_generator.get_agent_number(state.name),
                "lifecycle": state.lifecycle.value,
                "created_at": state.created_at,
                "last_active": state.last_active,
                "total_uptime": state.total_uptime,
                "activation_count": state.activation_count
            }
            all_agents.append(agent_info)
        
        # Sort by agent number
        all_agents.sort(key=lambda x: x["agent_number"])
        
        return all_agents
    
    async def _restore_sleeping_agents_background(self):
        """Background task to restore sleeping agents without blocking."""
        try:
            await self._restore_sleeping_agents()
        except Exception as e:
            logger.error(f"Failed to restore sleeping agents: {e}")
    
    async def _restore_sleeping_agents(self):
        """Restore agents that were sleeping when server stopped."""
        logger.info("Checking for sleeping agents to restore...")
        
        all_states = await self.state_manager.list_agents()
        sleeping_agents = [
            state for state in all_states
            if state.lifecycle == AgentLifecycle.SLEEPING
        ]
        
        if not sleeping_agents:
            logger.info("No sleeping agents to restore")
            return
        
        logger.info(f"Found {len(sleeping_agents)} sleeping agents to restore")
        
        for state in sleeping_agents:
            try:
                logger.info(f"Restoring agent {state.name}")
                
                # Update lifecycle to active
                await self.state_manager.update_lifecycle(state.name, AgentLifecycle.ACTIVE)
                await self.state_manager.increment_activation(state.name)
                
                # Start/resume the agent process with its saved config
                await self.spawner.start_agent(
                    name=state.name,
                    config=state.config
                )
                
                # Create body files for the agent
                agent_home = self.subspace.agents_dir / state.name
                body_manager = await self.body_system.create_agent_body(state.name, agent_home)
                
                # Start monitoring body files
                await self.body_system.start_agent_monitoring(state.name, self._handle_ai_request)
                
                # The agent will restore its own memory from disk
                logger.info(f"Agent {state.name} restored successfully")
                
            except Exception as e:
                logger.error(f"Failed to restore agent {state.name}: {e}")
                # Mark as hibernating if restore fails
                await self.state_manager.update_lifecycle(state.name, AgentLifecycle.HIBERNATING)
    
    async def _prepare_agents_for_shutdown(self):
        """Prepare all agents for shutdown."""
        logger.info("Preparing agents for shutdown...")
        
        # Get list of active agents
        active_agents = await self.state_manager.prepare_shutdown()
        
        if not active_agents:
            logger.info("No active agents to notify")
            return
        
        logger.info(f"Notifying {len(active_agents)} agents of shutdown")
        
        # Send shutdown message to all active agents
        shutdown_message = {
            "type": "SHUTDOWN",
            "from": "subspace",
            "reason": "Server shutting down",
            "timestamp": datetime.now().isoformat()
        }
        
        await self.spawner.broadcast_message(shutdown_message, exclude=[])
        
        # Give agents time to save state
        logger.info("Waiting for agents to save state...")
        await asyncio.sleep(3)  # Give agents 3 seconds to save state
    
    async def _message_routing_loop(self):
        """Main loop for routing messages between agents."""
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
    
    async def get_plaza_questions(self) -> List[Dict[str, Any]]:
        """Get all questions from the Plaza."""
        questions = []
        plaza_dir = self.subspace.plaza_dir
        
        try:
            files = await aiofiles.os.listdir(plaza_dir)
            json_files = [f for f in files if f.endswith('.json')]
            
            for filename in json_files:
                q_file = plaza_dir / filename
                try:
                    async with aiofiles.open(q_file, 'r') as f:
                        content = await f.read()
                    question = json.loads(content)
                    questions.append(question)
                except Exception as e:
                    logger.error(f"Error reading question {q_file}: {e}")
        except OSError as e:
            logger.error(f"Error listing plaza directory: {e}")
        
        return questions
    
    async def create_plaza_question(self, text: str, created_by: str = "user") -> str:
        """Create a new question in the Plaza."""
        question_id = f"q_{int(asyncio.get_event_loop().time() * 1000)}"
        question = {
            "id": question_id,
            "text": text,
            "created_by": created_by,
            "created_at": datetime.now().isoformat(),
            "claimed_by": None,
            "answer": None
        }
        
        q_file = self.subspace.plaza_dir / f"{question_id}.json"
        async with aiofiles.open(q_file, 'w') as f:
            await f.write(json.dumps(question, indent=2))
        
        logger.info(f"Posted question to Plaza: {question_id}")
        return question_id
    
    async def _handle_ai_request(self, name: str, prompt: str) -> str:
        """Handle an AI request from an agent's brain file.
        
        Args:
            name: The agent making the request
            prompt: The thought to process (may be JSON ThinkingRequest)
            
        Returns:
            The AI response
        """
        logger.info(f"Processing thought for {name}: {prompt[:200]}...")
        
        try:
            # Get agent configuration to determine which model to use
            agent_states = await self.spawner.get_agent_states()
            agent_info = agent_states.get(name, {})
            
            # Check if agent uses premium model
            use_premium = False
            agent_dir = self.subspace.agents_dir / name
            config_file = agent_dir / "config.json"
            if await aiofiles.os.path.exists(config_file):
                async with aiofiles.open(config_file, 'r') as f:
                    content = await f.read()
                config = json.loads(content)
                use_premium = config.get("ai", {}).get("use_premium", False)
            
            # Get appropriate AI service
            preset_name = "smart_balanced" if use_premium else "local_explorer"
            
            # Use lock to protect brain handler creation
            async with self._brain_handler_lock:
                if preset_name not in self._ai_services:
                    # Create AI service on demand
                    ai_config = preset_manager.get_config(preset_name)
                    if ai_config:
                        self._ai_services[preset_name] = create_ai_service(ai_config)
                    else:
                        logger.error(f"AI preset {preset_name} not found")
                        return "I cannot access my thinking capabilities right now."
                
                ai_service = self._ai_services.get(preset_name)
                if not ai_service:
                    return "My thinking process is temporarily unavailable."
                
                # Get or create dynamic brain handler for this preset
                if preset_name not in self._brain_handlers:
                    # Convert AIExecutionConfig to the format expected by DSPy
                    if hasattr(ai_config, '__dict__'):
                        # ai_config is AIExecutionConfig, convert to DSPy format
                        config_dict = {
                            "provider": ai_config.provider,
                            "model": ai_config.model_id,  # DSPy expects 'model', not 'model_id'
                            "temperature": ai_config.temperature,
                            "max_tokens": ai_config.max_tokens,
                            "api_key": ai_config.api_key,
                            "base_url": ai_config.provider_settings.get("host") if ai_config.provider_settings else None
                        }
                    else:
                        config_dict = ai_config
                    logger.info(f"Creating brain handler for preset {preset_name} with config: {config_dict}")
                    self._brain_handlers[preset_name] = DynamicBrainHandler(ai_service, config_dict)
                
                brain_handler = self._brain_handlers[preset_name]
            
            # Process the thinking request with dynamic handler
            response = await brain_handler.process_thinking_request(name, prompt)
            
            # Response already includes <<<THOUGHT_COMPLETE>>> from brain handler
            logger.info(f"Thought processed for {name}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing AI request for {name}: {e}")
            # Return a properly formatted error response
            return json.dumps({
                "request_id": "error",
                "signature_hash": "error",
                "output_values": {"error": str(e), "response": f"My thinking was interrupted: {str(e)}"},
                "metadata": {"error": True, "agent_id": name}
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
    
    async def _create_io_agent_body_files(self, agent_name: str, agent_home: Path):
        """Create additional body files for I/O agents.
        
        Args:
            agent_name: Name of the I/O agent
            agent_home: Agent's home directory
        """
        io_bodies_dir = agent_home / ".io_bodies"
        io_bodies_dir.mkdir(exist_ok=True)
        
        # Create network body file
        network_file = io_bodies_dir / "network"
        network_file.write_text("")
        logger.info(f"Created network body file for {agent_name}")
        
        # Create user_io body file  
        user_io_file = io_bodies_dir / "user_io"
        user_io_file.write_text("")
        logger.info(f"Created user_io body file for {agent_name}")
        
        # TODO: Set up monitoring for these special body files
    
    async def _start_io_agent_server_component(self, agent_name: str, type_config):
        """Start the server-side component for an I/O agent.
        
        Args:
            agent_name: Name of the I/O agent
            type_config: Agent type configuration
        """
        # TODO: Implement server component initialization
        logger.info(f"I/O agent server component for {agent_name} not yet implemented")

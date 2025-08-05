"""Streamlined Cognitive Loop - Pure OODA cycle implementation.

This refactored version focuses purely on the cognitive orchestration,
delegating all supporting functionality to specialized modules.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Import supporting modules
from .memory import (
    WorkingMemoryManager, MemorySelector, ContextBuilder, ContentLoader,
    ObservationMemoryBlock, MessageMemoryBlock, CycleStateMemoryBlock,
    KnowledgeMemoryBlock, FileMemoryBlock,
    Priority, MemoryType
)
from .perception import EnvironmentScanner
from .knowledge import KnowledgeManager
from .state import AgentStateManager, ExecutionStateTracker
from .actions import Action, ActionStatus, ActionCoordinator, action_registry
from .utils import DateTimeEncoder, CognitiveUtils, FileManager

logger = logging.getLogger("agent.cognitive")


class CognitiveLoop:
    """
    Streamlined cognitive processing engine implementing the OODA loop:
    Perceive → Observe → Orient → Decide → Instruct → Act
    
    All supporting functionality is delegated to specialized managers,
    keeping this class focused purely on cognitive orchestration.
    """
    
    def __init__(self, agent_id: str, home: Path, 
                 max_context_tokens: int = 50000,
                 agent_type: str = 'base'):
        """Initialize the cognitive loop with all supporting managers.
        
        Args:
            agent_id: The agent's identifier
            home: Path to agent's home directory
            max_context_tokens: Maximum tokens for LLM context
            agent_type: Type of agent (base, io_gateway, etc.)
        """
        self.agent_id = agent_id
        self.home = Path(home)
        self.max_context_tokens = max_context_tokens
        self.agent_type = agent_type
        
        # Core file interfaces - define these first
        self.brain_file = self.home / "brain"
        self.inbox_dir = self.home / "inbox"
        self.outbox_dir = self.home / "outbox"
        self.memory_dir = self.home / "memory"
        
        # Initialize all managers
        self._initialize_managers()
        
        # Ensure directories exist
        self.file_manager.ensure_directory(self.inbox_dir)
        self.file_manager.ensure_directory(self.outbox_dir)
        self.file_manager.ensure_directory(self.memory_dir)
        
        # Initialize state
        self.cycle_count = 0
        self.last_activity = datetime.now()
        
        # Initialize systems
        self._initialize_systems()
    
    def _initialize_managers(self):
        """Initialize all supporting managers."""
        # Memory system
        self.memory_manager = WorkingMemoryManager(max_tokens=self.max_context_tokens)
        self.memory_selector = MemorySelector(
            ContextBuilder(ContentLoader(filesystem_root=self.home.parent))
        )
        self.context_builder = ContextBuilder(ContentLoader(filesystem_root=self.home.parent))
        
        # Knowledge system
        self.knowledge_manager = KnowledgeManager(agent_type=self.agent_type)
        
        # State management
        self.state_manager = AgentStateManager(self.agent_id, self.memory_dir)
        self.execution_tracker = ExecutionStateTracker(self.agent_id, self.memory_dir)
        
        # Action coordination
        self.action_coordinator = ActionCoordinator(agent_type=self.agent_type)
        
        # Perception system
        grid_path = self.home.parent.parent / "grid"
        self.environment_scanner = EnvironmentScanner(
            home_path=self.home,
            grid_path=grid_path
        )
        
        # Utilities
        self.cognitive_utils = CognitiveUtils()
        self.file_manager = FileManager()
    
    def _initialize_systems(self):
        """Initialize all systems and load initial data."""
        # Initialize managers
        self.state_manager.initialize()
        self.knowledge_manager.initialize()
        
        # Try to restore memory from snapshot first
        if not self.memory_manager.load_from_snapshot_file(self.memory_dir, self.knowledge_manager):
            # No snapshot - load ROM and init fresh
            self.knowledge_manager.load_rom_into_memory(self.memory_manager)
            self._init_cycle_state()
        
        # Load state
        existing_state = self.state_manager.load_state()
        if existing_state:
            self.cycle_count = existing_state.get("cycle_count", 0)
            logger.info(f"Resumed at cycle {self.cycle_count}")
        
        # Load execution state
        self.execution_tracker.load_execution_state()
    
    def _init_cycle_state(self):
        """Initialize a new cycle state."""
        cycle_state = CycleStateMemoryBlock(
            cycle_state="perceive",
            cycle_count=0
        )
        self.memory_manager.add_memory(cycle_state)
        self.state_manager.update_state({
            "cycle_state": "perceive",
            "cycle_count": 0
        })
        logger.info("Initialized new cycle state")
    
    async def run_cycle(self) -> bool:
        """Run one complete cognitive cycle.
        
        This is the main OODA loop implementation - clean and focused.
        
        Returns:
            True if something was processed, False if idle
        """
        # Start execution tracking
        exec_id = self.execution_tracker.start_execution("cognitive_cycle", {
            "cycle_count": self.cycle_count,
            "agent_type": self.agent_type
        })
        
        try:
            # Get current state
            current_state = self.state_manager.get_state_value("cycle_state", "perceive")
            logger.debug(f"Starting cycle {self.cycle_count} in state: {current_state}")
            
            # Increment cycle count
            self.cycle_count = self.state_manager.increment_cycle_count()
            
            # Execute the appropriate phase
            result = await self._execute_phase(current_state)
            
            # End execution tracking
            self.execution_tracker.end_execution("completed", {"phase_completed": current_state})
            
            return result
            
        except Exception as e:
            logger.error(f"Error in cognitive cycle: {e}", exc_info=True)
            self.execution_tracker.end_execution("failed", {"error": str(e)})
            
            # Reset to perceive state on error
            self.state_manager.set_cycle_state("perceive")
            return False
    
    async def _execute_phase(self, phase: str) -> bool:
        """Execute a specific phase of the cognitive cycle.
        
        Args:
            phase: Current phase name
            
        Returns:
            True if processing occurred, False if idle
        """
        # Track state transition
        self.execution_tracker.track_state_transition(
            self.state_manager.get_state_value("cycle_state", "unknown"),
            phase
        )
        
        if phase == "perceive":
            # PERCEIVE - Scan environment and update memories
            await self.perceive()
            self.state_manager.set_cycle_state("observe")
            await self._save_checkpoint()
            return True
            
        elif phase == "observe":
            # OBSERVE - Check for high-priority inputs
            observation = await self.observe()
            if observation:
                self.state_manager.set_cycle_state("orient", 
                    current_observation=observation)
                await self._save_checkpoint()
                return True
            else:
                # No observation, do maintenance and restart
                await self.maintain()
                self.state_manager.set_cycle_state("perceive")
                await self._save_checkpoint()
                return False
                
        elif phase == "orient":
            # ORIENT - Understand the situation
            observation = self.state_manager.get_state_value("current_observation")
            if not observation:
                self.state_manager.set_cycle_state("perceive")
                return True
                
            orientation = await self.orient(observation)
            logger.info(f"Oriented: {orientation.get('task_type')}")
            
            self.state_manager.set_cycle_state("decide",
                current_orientation=orientation)
            await self._save_checkpoint()
            return True
            
        elif phase == "decide":
            # DECIDE - Choose actions to take
            orientation = self.state_manager.get_state_value("current_orientation")
            if not orientation:
                self.state_manager.set_cycle_state("perceive")
                return True
                
            actions = await self.decide(orientation)
            logger.info(f"Decided on {len(actions)} actions")
            
            # Save actions as serializable data
            action_data = [{"name": a.name, "params": a.params} for a in actions]
            self.state_manager.set_cycle_state("instruct",
                current_actions=action_data)
            await self._save_checkpoint()
            return True
            
        elif phase == "instruct":
            # INSTRUCT - Prepare and validate actions
            action_data = self.state_manager.get_state_value("current_actions", [])
            
            if not action_data:
                # No actions, pause briefly and restart
                await asyncio.sleep(1.0)
                self.state_manager.set_cycle_state("perceive")
                return True
                
            instructed_actions = await self.instruct(action_data)
            
            self.state_manager.set_cycle_state("act",
                current_actions=instructed_actions)
            await self._save_checkpoint()
            return True
            
        elif phase == "act":
            # ACT - Execute actions
            observation = self.state_manager.get_state_value("current_observation")
            orientation = self.state_manager.get_state_value("current_orientation")
            action_data = self.state_manager.get_state_value("current_actions", [])
            
            if not all([observation, orientation, action_data]):
                self.state_manager.set_cycle_state("perceive")
                return True
                
            # Recreate action objects
            actions = []
            for data in action_data:
                action = self.action_coordinator.prepare_action(
                    data["name"], 
                    data.get("params", {}),
                    self.knowledge_manager
                )
                if action:
                    actions.append(action)
                    
            await self.act(observation, orientation, actions)
            
            # Cycle complete, restart
            self.state_manager.set_cycle_state("perceive")
            await self._save_checkpoint()
            return True
            
        else:
            # Unknown state, restart
            logger.warning(f"Unknown cycle state: {phase}")
            self.state_manager.set_cycle_state("perceive")
            return True
    
    # === CORE OODA LOOP METHODS ===
    
    async def perceive(self) -> Dict[str, Any]:
        """PERCEIVE - Scan environment and update memory with observations."""
        logger.info("=== PERCEIVE PHASE ===")
        
        # Scan environment
        observations = self.environment_scanner.scan_environment(full_scan=False)
        
        # Add observations to memory
        significant_count = 0
        for obs in observations:
            self.memory_manager.add_memory(obs)
            if obs.priority != Priority.LOW:
                significant_count += 1
                
        if significant_count > 0:
            logger.info(f"Perceived {significant_count} significant changes")
            
        return {"observations_count": len(observations)}
    
    async def observe(self) -> Optional[Dict[str, Any]]:
        """OBSERVE - Intelligently select the most important observation."""
        logger.info("=== OBSERVE PHASE ===")
        
        # Get recent observations and messages
        recent_observations = self._get_recent_observations()
        unread_messages = self.memory_manager.get_unread_messages()
        
        if not recent_observations and not unread_messages:
            return None
            
        # Build context for observation selection
        selected_memories = self.memory_selector.select_memories(
            symbolic_memory=self.memory_manager.symbolic_memory,
            max_tokens=self.max_context_tokens // 4,
            current_task="Deciding what to focus on",
            selection_strategy="balanced"
        )
        memory_context = self.context_builder.build_context(selected_memories)
        
        # Use brain to prioritize
        observation = await self._select_observation(
            recent_observations, 
            unread_messages,
            memory_context
        )
        
        return observation
    
    async def orient(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """ORIENT - Understand the situation and build context."""
        logger.info("=== ORIENT PHASE ===")
        
        # Create observation memory
        self._create_observation_memory(observation)
        
        # Use brain to understand the situation
        orientation = await self._analyze_situation(observation)
        
        return orientation
    
    async def decide(self, orientation: Dict[str, Any]) -> List[Action]:
        """DECIDE - Choose actions based on orientation."""
        logger.info("=== DECIDE PHASE ===")
        
        # Build decision context
        decision_context = await self._build_decision_context(orientation)
        
        # Use brain to decide on actions
        actions = await self._make_decision(orientation, decision_context)
        
        return actions
    
    async def instruct(self, action_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """INSTRUCT - Prepare and validate actions for execution."""
        logger.info("=== INSTRUCT PHASE ===")
        
        corrected_actions = []
        
        for action_spec in action_data:
            # Load action knowledge and apply corrections
            action_name = action_spec.get("name", "")
            params = action_spec.get("params", {})
            
            # Validate and prepare action
            is_valid, error = self.action_coordinator.validate_action(
                action_name, params, self.knowledge_manager
            )
            
            if is_valid:
                # Apply corrections from knowledge
                action = self.action_coordinator.prepare_action(
                    action_name, params, self.knowledge_manager
                )
                if action:
                    corrected_actions.append({
                        "name": action.name,
                        "params": action.params
                    })
            else:
                logger.warning(f"Invalid action {action_name}: {error}")
                
        return corrected_actions
    
    async def act(self, observation: Dict[str, Any], 
                  orientation: Dict[str, Any], 
                  actions: List[Action]) -> Dict[str, Any]:
        """ACT - Execute the decided actions."""
        logger.info("=== ACT PHASE ===")
        
        # Build execution context
        context = self._build_execution_context(observation, orientation)
        
        # Execute each action
        results = []
        for i, action in enumerate(actions):
            logger.info(f"Executing action {i+1}/{len(actions)}: {action.name}")
            
            result = await self.action_coordinator.execute_action(action, context)
            results.append(result)
            
            # Update context with result for subsequent actions
            if result["success"] and result.get("result"):
                context[f"action_{i}_result"] = result["result"]
                context["last_action_result"] = result["result"]
                
            # Stop on critical failure
            if not result["success"] and action.priority == Priority.HIGH:
                logger.warning("Critical action failed, stopping sequence")
                break
                
        # Process results into observations
        self.action_coordinator.process_action_results(results, self.memory_manager)
        
        logger.info(f"Completed {len(results)} actions")
        return {"actions_executed": len(results), "results": results}
    
    # === SUPPORTING METHODS ===
    
    async def maintain(self):
        """Perform maintenance tasks when idle."""
        # Cleanup old memories
        expired = self.memory_manager.cleanup_expired()
        old_observations = self.memory_manager.cleanup_old_observations(max_age_seconds=1800)
        
        if expired or old_observations:
            logger.debug(f"Cleaned up {expired} expired, {old_observations} old memories")
            
        # Save state periodically
        if self.cycle_count % 100 == 0:
            await self._save_checkpoint()
            self.execution_tracker.save_execution_state()
    
    async def _save_checkpoint(self):
        """Save current state and memory."""
        # Save memory snapshot
        await self.save_memory()
        
        # Save state
        self.state_manager.save_state()
    
    async def save_memory(self):
        """Save memory snapshot to disk."""
        try:
            snapshot = self.memory_manager.create_snapshot()
            
            memory_file = self.memory_dir / "memory_snapshot.json"
            memory_json = json.dumps(snapshot, indent=2, cls=DateTimeEncoder)
            
            self.file_manager.save_file(memory_file, memory_json, atomic=True)
            
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
    def _get_recent_observations(self, max_age_seconds: int = 300) -> List[ObservationMemoryBlock]:
        """Get recent observation memories."""
        recent_cutoff = datetime.now().timestamp() - max_age_seconds
        return [
            obs for obs in self.memory_manager.symbolic_memory
            if isinstance(obs, ObservationMemoryBlock) 
            and obs.timestamp is not None
            and obs.timestamp.timestamp() > recent_cutoff
        ]
    
    def _create_observation_memory(self, observation: Dict[str, Any]):
        """Create and store an observation memory."""
        obs_memory = ObservationMemoryBlock(
            observation_type="message_received",
            path="<inbox>",
            description=f"Received: {json.dumps(observation)}",
            priority=Priority.HIGH
        )
        self.memory_manager.add_memory(obs_memory)
    
    def _build_execution_context(self, observation: Dict[str, Any],
                               orientation: Dict[str, Any]) -> Dict[str, Any]:
        """Build context for action execution."""
        return {
            "cognitive_loop": self,
            "memory_manager": self.memory_manager,
            "agent_id": self.agent_id,
            "home_dir": self.home,
            "outbox_dir": self.outbox_dir,
            "memory_dir": self.memory_dir,
            "observation": observation,
            "orientation": orientation,
            "task_id": orientation.get("task_memory_id"),
            "original_text": observation.get("query", observation.get("command", ""))
        }
    
    # === BRAIN INTERFACE METHODS ===
    
    async def _use_brain(self, prompt: str) -> str:
        """Use the brain file interface for thinking."""
        logger.debug("Using brain for thinking...")
        
        # Escape markers
        escaped_prompt = prompt.replace("<<<THOUGHT_COMPLETE>>>", "[THOUGHT_COMPLETE]")
        escaped_prompt = escaped_prompt.replace("<<<END_THOUGHT>>>", "[END_THOUGHT]")
        
        # Write prompt
        self.brain_file.write_text(f"{escaped_prompt}\n<<<END_THOUGHT>>>")
        
        # Wait for response
        wait_count = 0
        while True:
            content = self.brain_file.read_text()
            
            if "<<<THOUGHT_COMPLETE>>>" in content:
                # Extract response
                prompt_end = content.find("<<<END_THOUGHT>>>")
                if prompt_end != -1:
                    response_start = prompt_end + len("<<<END_THOUGHT>>>")
                    response = content[response_start:].strip()
                    response = response.replace("<<<THOUGHT_COMPLETE>>>", "").strip()
                else:
                    response = content.split("<<<THOUGHT_COMPLETE>>>")[0].strip()
                    
                # Reset brain
                self.brain_file.write_text("Ready for thinking.")
                
                return response
                
            wait_count += 1
            if wait_count % 100 == 0:
                logger.warning(f"Waiting for brain response ({wait_count/100}s)")
                
            await asyncio.sleep(0.01)
    
    async def _select_observation(self, observations: List[ObservationMemoryBlock],
                                messages: List[MessageMemoryBlock],
                                context: str) -> Optional[Dict[str, Any]]:
        """Use brain to select most important observation."""
        # Prepare summaries
        obs_summaries = self._summarize_observations(observations[:10])
        msg_summaries = self._summarize_messages(messages[:5])
        
        thinking_request = {
            "signature": {
                "task": "What should I focus on right now?",
                "description": "Review observations and messages to pick the most important",
                "inputs": {
                    "observations": "Recent environmental observations and action results",
                    "messages": "Unread messages from other agents", 
                    "context": "Current working memory context"
                },
                "outputs": {
                    "focus": "Either 'message:N' or 'observation:N' where N is the index",
                    "reasoning": "Why this is most important"
                }
            },
            "input_values": {
                "observations": json.dumps(obs_summaries),
                "messages": json.dumps(msg_summaries),
                "context": context
            }
        }
        
        response = await self._use_brain(json.dumps(thinking_request, cls=DateTimeEncoder))
        
        # Parse response and return selected observation
        return self._parse_observation_selection(response, observations, messages)
    
    async def _analyze_situation(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Use brain to analyze and orient to the situation."""
        thinking_request = {
            "signature": {
                "task": "What does this mean and how should I handle it?",
                "description": "Understand the context and meaning of observations",
                "inputs": {
                    "observations": "What was observed",
                },
                "outputs": {
                    "situation_type": "What kind of situation this is",
                    "understanding": "What I understand about the situation",
                    "relevant_knowledge": "What knowledge or skills apply"
                },
                "display_field": "understanding"
            },
            "input_values": {
                "observations": json.dumps(observation),
            },
            "request_id": f"orient_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self._use_brain(json.dumps(thinking_request))
        return self._parse_orientation(response, observation)
    
    async def _build_decision_context(self, orientation: Dict[str, Any]) -> str:
        """Build context for decision making."""
        # Select relevant memories
        selected_memories = self.memory_selector.select_memories(
            symbolic_memory=self.memory_manager.symbolic_memory,
            max_tokens=self.max_context_tokens // 2,
            current_task="Making a decision",
            selection_strategy="balanced"
        )
        
        return self.context_builder.build_context(selected_memories)
    
    async def _make_decision(self, orientation: Dict[str, Any], 
                           context: str) -> List[Action]:
        """Use brain to decide on actions."""
        thinking_request = {
            "signature": {
                "task": "What actions should I take?",
                "description": "Decide what actions to take based on the situation",
                "inputs": {
                    "situation": "Current situation and understanding",
                    "working_memory": "Your memories including available actions",
                    "goal": "What needs to be accomplished"
                },
                "outputs": {
                    "actions": "JSON array of actions to take",
                    "reasoning": "Why these actions make sense"
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "situation": orientation.get("reasoning", "Need to process this request"),
                "working_memory": context,
                "goal": orientation.get("content", "unknown request")
            },
            "request_id": f"decide_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self._use_brain(json.dumps(thinking_request))
        return self._parse_action_decision(response)
    
    # === PARSING HELPER METHODS ===
    
    def _summarize_observations(self, observations: List[ObservationMemoryBlock]) -> List[Dict]:
        """Create summaries of observations for brain."""
        summaries = []
        for i, obs in enumerate(observations):
            summaries.append({
                "index": i,
                "type": obs.observation_type,
                "description": obs.description[:100],
                "age_seconds": int((datetime.now() - obs.timestamp).total_seconds()) if obs.timestamp else 0,
                "priority": obs.priority.name
            })
        return summaries
    
    def _summarize_messages(self, messages: List[MessageMemoryBlock]) -> List[Dict]:
        """Create summaries of messages for brain."""
        summaries = []
        for i, msg in enumerate(messages):
            summaries.append({
                "index": i,
                "from": msg.from_agent,
                "subject": msg.subject,
                "age_seconds": int((datetime.now() - msg.timestamp).total_seconds()) if msg.timestamp else 0
            })
        return summaries
    
    def _parse_observation_selection(self, response: str, 
                                   observations: List[ObservationMemoryBlock],
                                   messages: List[MessageMemoryBlock]) -> Optional[Dict[str, Any]]:
        """Parse brain response to select observation."""
        try:
            result = json.loads(response)
            focus = result.get("output_values", {}).get("focus", "")
            reasoning = result.get("output_values", {}).get("reasoning", "")
            
            if focus.startswith("message:") and messages:
                idx = int(focus.split(":")[1])
                msg = messages[min(idx, len(messages)-1)]
                return self._process_message(msg, reasoning)
                
            elif focus.startswith("observation:") and observations:
                idx = int(focus.split(":")[1])
                obs = observations[min(idx, len(observations)-1)]
                return self._convert_observation(obs, reasoning)
                
        except Exception as e:
            logger.error(f"Failed to parse observation selection: {e}")
            
        # Fallback to first unread message
        if messages:
            return self._process_message(messages[0], "Fallback selection")
            
        return None
    
    def _process_message(self, msg: MessageMemoryBlock, reasoning: str) -> Optional[Dict[str, Any]]:
        """Process a selected message."""
        try:
            msg_path = Path(msg.full_path)
            if msg_path.exists():
                message = json.loads(msg_path.read_text())
                
                # Mark as read
                self.memory_manager.mark_message_read(msg.id)
                self.environment_scanner.mark_message_processed(str(msg_path))
                
                # Move to processed
                processed_dir = self.inbox_dir / "processed"
                self.file_manager.ensure_directory(processed_dir)
                msg_path.rename(processed_dir / msg_path.name)
                
                message["observe_reasoning"] = reasoning
                return message
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            
        return None
    
    def _convert_observation(self, obs: ObservationMemoryBlock, reasoning: str) -> Dict[str, Any]:
        """Convert observation to standard format."""
        return {
            "from": "environment",
            "type": "OBSERVATION",
            "observation_type": obs.observation_type,
            "content": obs.description,
            "path": obs.path,
            "timestamp": obs.timestamp.isoformat() if obs.timestamp else datetime.now().isoformat(),
            "id": obs.id,
            "observe_reasoning": reasoning
        }
    
    def _parse_orientation(self, response: str, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Parse brain response for orientation."""
        try:
            result = json.loads(response)
            output = result.get("output_values", {})
            
            return {
                "task_type": output.get("situation_type", "unknown"),
                "understanding": output.get("understanding", ""),
                "approach": output.get("approach", "thinking"),
                "requires_response": True,
                "content": observation.get("command", observation.get("query", str(observation))),
                "timestamp": datetime.now(),
                "from": observation.get("from", "unknown"),
                "original_message": observation
            }
            
        except Exception as e:
            logger.error(f"Failed to parse orientation: {e}")
            return {
                "task_type": "unknown",
                "approach": "thinking",
                "requires_response": True,
                "content": str(observation),
                "timestamp": datetime.now()
            }
    
    def _parse_action_decision(self, response: str) -> List[Action]:
        """Parse brain response for action decision."""
        actions = []
        
        try:
            result = json.loads(response)
            action_data = result.get("output_values", {}).get("actions", "[]")
            
            # Clean up markdown if present
            if isinstance(action_data, str) and "```" in action_data:
                start = action_data.find("```json") + 7 if "```json" in action_data else action_data.find("```") + 3
                end = action_data.rfind("```")
                if start < end:
                    action_data = action_data[start:end].strip()
                    
            # Parse actions
            if isinstance(action_data, str):
                action_objects = json.loads(action_data)
            else:
                action_objects = action_data
                
            # Create Action objects
            for spec in action_objects:
                if isinstance(spec, dict):
                    action_name = spec.get("action")
                    params = spec.get("params", {})
                    
                    action = self.action_coordinator.prepare_action(
                        action_name, params, self.knowledge_manager
                    )
                    if action:
                        actions.append(action)
                        
        except Exception as e:
            logger.error(f"Failed to parse action decision: {e}")
            
        return actions
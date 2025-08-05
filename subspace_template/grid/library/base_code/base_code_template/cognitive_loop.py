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
                 agent_type: str = 'general'):
        """Initialize the cognitive loop with all supporting managers.
        
        Args:
            agent_id: The agent's identifier
            home: Path to agent's home directory
            max_context_tokens: Maximum tokens for LLM context
            agent_type: Type of agent (general, io_gateway, etc.)
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
            await self.observe()
            # Check if observation was found (stored in cycle state)
            cycle_state = self._get_cycle_state()
            if cycle_state and cycle_state.current_observation:
                self.state_manager.set_cycle_state("orient")
                await self._save_checkpoint()
                return True
            else:
                # No observation, do maintenance and restart
                logger.debug("😴 No work found, performing maintenance")
                await self.maintain()
                self.state_manager.set_cycle_state("perceive")
                await self._save_checkpoint()
                return False
                
        elif phase == "orient":
            # ORIENT - Understand the situation
            await self.orient()
            self.state_manager.set_cycle_state("decide")
            await self._save_checkpoint()
            return True
            
        elif phase == "decide":
            # DECIDE - Choose actions to take
            await self.decide()
            self.state_manager.set_cycle_state("instruct")
            await self._save_checkpoint()
            return True
            
        elif phase == "instruct":
            # INSTRUCT - Prepare and validate actions
            await self.instruct()
            # Check if we have actions to execute
            cycle_state = self._get_cycle_state()
            if cycle_state and cycle_state.current_actions:
                self.state_manager.set_cycle_state("act")
                await self._save_checkpoint()
                return True
            else:
                # No actions, pause briefly and restart
                await asyncio.sleep(1.0)
                self.state_manager.set_cycle_state("perceive")
                return True
            
        elif phase == "act":
            # ACT - Execute actions
            await self.act()
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
    
    async def perceive(self) -> None:
        """PERCEIVE - Scan environment and update memory with observations."""
        logger.info("=== PERCEIVE PHASE ===")
        
        # Scan environment
        observations = self.environment_scanner.scan_environment(full_scan=False)
        
        # Add observations to memory
        significant_count = 0
        high_priority_items = []
        for obs in observations:
            self.memory_manager.add_memory(obs)
            if obs.priority != Priority.LOW:
                significant_count += 1
                if obs.priority == Priority.HIGH:
                    # Handle different memory block types
                    if hasattr(obs, 'observation_type'):
                        # ObservationMemoryBlock
                        high_priority_items.append(f"{obs.observation_type}: {obs.path[:100]}")
                    elif hasattr(obs, 'from_agent'):
                        # MessageMemoryBlock
                        high_priority_items.append(f"message from {obs.from_agent}: {obs.subject[:100]}")
                    else:
                        # Other memory block types
                        high_priority_items.append(f"{obs.type.name if hasattr(obs, 'type') else 'unknown'}: {str(obs)[:100]}")
                
        if significant_count > 0:
            logger.info(f"📡 Perceived {significant_count} significant changes ({len(observations)} total)")
            for item in high_priority_items[:3]:  # Show top 3 high priority items
                logger.info(f"  • {item}")
        else:
            logger.info("📡 Environment scan - no significant changes detected")
            
    
    async def observe(self) -> None:
        """OBSERVE - Intelligently select the most important observation."""
        logger.info("=== OBSERVE PHASE ===")
        
        # Build full working memory context for the brain to see everything
        selected_memories = self.memory_selector.select_memories(
            symbolic_memory=self.memory_manager.symbolic_memory,
            max_tokens=self.max_context_tokens // 2,  # Give more context for better decisions
            current_task="Deciding what to focus on",
            selection_strategy="balanced"
        )
        memory_context = self.context_builder.build_context(selected_memories)
        
        # Let the AI brain see everything and decide what to focus on
        observation = await self._select_focus_from_memory(memory_context)
        
        # Update cycle state with selected observation
        self._update_cycle_state(current_observation=observation)
        
        if observation:
            if observation.get("type") == "COMMAND":
                logger.info(f"👁️ Selected MESSAGE from {observation.get('from', 'unknown')}: {observation.get('command', 'no command')}")
            elif observation.get("type") == "QUERY":
                logger.info(f"👁️ Selected QUERY from {observation.get('from', 'unknown')}: {observation.get('query', 'no query')[:100]}")
            else:
                logger.info(f"👁️ Selected {observation.get('observation_type', 'observation')}: {str(observation.get('content', observation))[:100]}")
        else:
            logger.info("👁️ Brain decided no immediate focus needed")
    
    async def orient(self) -> None:
        """ORIENT - Understand the situation and build context."""
        logger.info("=== ORIENT PHASE ===")
        
        # Get current observation from cycle state
        cycle_state = self._get_cycle_state()
        observation = cycle_state.current_observation if cycle_state else None
        
        if not observation:
            logger.warning("No observation found in cycle state, returning to perceive")
            return
        
        
        # Use brain to understand the situation
        logger.info("🧠 Analyzing situation and understanding context...")
        orientation = await self._analyze_situation(observation)
        
        # Log what we understood
        task_type = orientation.get("task_type", "unknown")
        understanding = orientation.get("understanding", "")
        logger.info(f"🧠 Understanding: {task_type}")
        if understanding:
            logger.info(f"  💭 {understanding[:200]}")
        
        # Update cycle state with orientation
        self._update_cycle_state(current_orientation=orientation)
    
    async def decide(self) -> None:
        """DECIDE - Choose actions based on orientation."""
        logger.info("=== DECIDE PHASE ===")
        
        # Get current orientation from cycle state
        cycle_state = self._get_cycle_state()
        orientation = cycle_state.current_orientation if cycle_state else None
        
        if not orientation:
            logger.warning("No orientation found in cycle state, returning to perceive")
            return
        
        # Build decision context
        decision_context = await self._build_decision_context(orientation)
        
        # Use brain to decide on actions
        logger.info("🤔 Making decision based on situation...")
        actions = await self._make_decision(orientation, decision_context)
        
        # Log the decision
        if actions:
            logger.info(f"🤔 Decided on {len(actions)} actions:")
            for i, action in enumerate(actions[:5]):  # Show first 5 actions
                params_str = ""
                if action.params:
                    # Show key parameters
                    key_params = []
                    for k, v in list(action.params.items())[:3]:
                        if isinstance(v, str) and len(v) > 50:
                            key_params.append(f"{k}='{v[:50]}...'")
                        else:
                            key_params.append(f"{k}={v}")
                    if key_params:
                        params_str = f" ({', '.join(key_params)})"
                logger.info(f"  {i+1}. {action.name}{params_str}")
        else:
            logger.info("🤔 No actions decided")
        
        # Save actions as serializable data and update cycle state
        action_data = [{"name": a.name, "params": a.params} for a in actions]
        self._update_cycle_state(current_actions=action_data)
    
    async def instruct(self) -> None:
        """INSTRUCT - Prepare and validate actions for execution."""
        logger.info("=== INSTRUCT PHASE ===")
        
        # Get current actions from cycle state
        cycle_state = self._get_cycle_state()
        action_data = cycle_state.current_actions if cycle_state else []
        
        if not action_data:
            logger.info("📋 No actions to validate")
            return
        
        logger.info(f"📋 Validating and preparing {len(action_data)} actions...")
        corrected_actions = []
        validation_errors = 0
        
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
                    logger.info(f"  ✅ {action.name} - ready for execution")
            else:
                validation_errors += 1
                logger.warning(f"  ❌ {action_name} - {error}")
                
        if validation_errors > 0:
            logger.info(f"📋 Validated {len(corrected_actions)}/{len(action_data)} actions ({validation_errors} failed)")
        else:
            logger.info(f"📋 All {len(corrected_actions)} actions validated successfully")
        
        # Update cycle state with corrected actions
        self._update_cycle_state(current_actions=corrected_actions)
    
    async def act(self) -> None:
        """ACT - Execute the decided actions."""
        logger.info("=== ACT PHASE ===")
        
        # Get current state from cycle state
        cycle_state = self._get_cycle_state()
        if not cycle_state:
            logger.warning("No cycle state found, returning to perceive")
            return
            
        observation = cycle_state.current_observation
        orientation = cycle_state.current_orientation
        action_data = cycle_state.current_actions or []
        
        if not all([observation, orientation, action_data]):
            logger.warning("Missing data for action execution, returning to perceive")
            return
        
        # Build execution context
        context = self._build_execution_context(observation, orientation)
        
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
        
        # Execute each action
        results = []
        successful_actions = 0
        for i, action in enumerate(actions):
            logger.info(f"⚡ Executing action {i+1}/{len(actions)}: {action.name}")
            
            result = await self.action_coordinator.execute_action(action, context)
            results.append(result)
            
            # Log result
            if result["success"]:
                successful_actions += 1
                if result.get("result"):
                    # Show a summary of the result
                    result_str = str(result["result"])
                    if len(result_str) > 150:
                        result_str = result_str[:150] + "..."
                    logger.info(f"  ✅ {action.name} completed: {result_str}")
                else:
                    logger.info(f"  ✅ {action.name} completed successfully")
                    
                # Update context with result for subsequent actions
                context[f"action_{i}_result"] = result["result"]
                context["last_action_result"] = result["result"]
            else:
                error_msg = result.get("error", "Unknown error")
                status = result.get("status", "unknown")
                logger.warning(f"  ❌ {action.name} failed: {error_msg}")
                if status != "unknown":
                    logger.warning(f"    Status: {status}")
                if result.get("result"):
                    logger.warning(f"    Details: {str(result['result'])[:200]}")
                
                # Stop on critical failure
                if action.priority == Priority.HIGH:
                    logger.warning("Critical action failed, stopping sequence")
                    break
                
        # Process results into observations
        self.action_coordinator.process_action_results(results, self.memory_manager)
        
        logger.info(f"⚡ Action phase complete: {successful_actions}/{len(results)} successful")
    
    # === CYCLE STATE HELPERS ===
    
    def _get_cycle_state(self) -> Optional[CycleStateMemoryBlock]:
        """Get the current cycle state from memory."""
        cycle_states = self.memory_manager.get_memories_by_type(MemoryType.CYCLE_STATE)
        if cycle_states and isinstance(cycle_states[0], CycleStateMemoryBlock):
            return cycle_states[0]
        return None
    
    def _update_cycle_state(self, **kwargs):
        """Update the cycle state in memory."""
        cycle_state = self._get_cycle_state()
        if not cycle_state:
            # Create new cycle state if missing
            cycle_state = CycleStateMemoryBlock(
                cycle_state=kwargs.get('cycle_state', 'perceive'),
                cycle_count=kwargs.get('cycle_count', 0)
            )
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(cycle_state, key):
                setattr(cycle_state, key, value)
        
        # Update timestamp
        cycle_state.timestamp = datetime.now()
        
        # Add/update in memory
        self.memory_manager.add_memory(cycle_state)

    # === SUPPORTING METHODS ===
    
    async def maintain(self):
        """Perform maintenance tasks when idle."""
        # Cleanup old memories
        expired = self.memory_manager.cleanup_expired()
        old_observations = self.memory_manager.cleanup_old_observations(max_age_seconds=1800)
        
        if expired or old_observations:
            logger.info(f"🧹 Cleaned up {expired} expired, {old_observations} old memories")
            
        # Save state periodically
        if self.cycle_count % 100 == 0:
            logger.info(f"💾 Saving checkpoint at cycle {self.cycle_count}")
            await self._save_checkpoint()
            self.execution_tracker.save_execution_state()
        elif self.cycle_count % 10 == 0:
            logger.debug(f"Idle maintenance at cycle {self.cycle_count}")
    
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
        # Parse the thinking request to get task info
        try:
            request_data = json.loads(prompt)
            task = request_data.get("signature", {}).get("task", "thinking")
            logger.info(f"🧠 Brain thinking: {task}")
        except:
            logger.info("🧠 Brain thinking...")
        
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
                    
                # Log brain response summary
                try:
                    response_data = json.loads(response)
                    if "output_values" in response_data:
                        # Show key output from brain
                        outputs = response_data["output_values"]
                        if "reasoning" in outputs:
                            reasoning = outputs["reasoning"][:100]
                            logger.info(f"🧠 Brain reasoning: {reasoning}")
                        elif "understanding" in outputs:
                            understanding = outputs["understanding"][:100]  
                            logger.info(f"🧠 Brain understanding: {understanding}")
                except:
                    logger.info("🧠 Brain response received")
                    
                # Reset brain
                self.brain_file.write_text("Ready for thinking.")
                
                return response
                
            wait_count += 1
            if wait_count % 100 == 0:
                logger.debug(f"⏳ Waiting for brain response ({wait_count/100:.1f}s)")
                
            await asyncio.sleep(0.01)
    
    async def _select_focus_from_memory(self, memory_context: str) -> Optional[Dict[str, Any]]:
        """Use brain to select what to focus on from full memory context."""
        
        thinking_request = {
            "signature": {
                "instruction": "Review your working memory and decide what deserves immediate attention. Look at timestamps, priorities, and your current situation. You can focus on any memory item by returning its ID, or return 'none' if no immediate focus is needed.",
                "inputs": {
                    "working_memory": "Your current symbolic memory with all observations, messages, tasks, and context"
                },
                "outputs": {
                    "memory_id": "The exact memory ID to focus on (e.g. 'message:inbox:from-alice/urgent-request:abc123') or 'none'",
                    "reasoning": "Why this memory deserves attention right now based on timestamps, priority, and context"
                },
                "display_field": "reasoning"
            },
            "input_values": {
                "working_memory": memory_context
            }
        }
        
        response = await self._use_brain(json.dumps(thinking_request, cls=DateTimeEncoder))
        
        # Parse response and retrieve the selected memory
        return self._parse_memory_selection(response)
    
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
    
    
    def _parse_memory_selection(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse brain response to get selected memory ID and retrieve it."""
        try:
            result = json.loads(response)
            memory_id = result.get("output_values", {}).get("memory_id", "")
            reasoning = result.get("output_values", {}).get("reasoning", "")
            
            if memory_id == "none" or not memory_id:
                logger.info(f"🧠 Brain reasoning: {reasoning}")
                return None
            
            # Find the memory by ID
            memory_block = None
            for memory in self.memory_manager.symbolic_memory:
                if memory.id == memory_id:
                    memory_block = memory
                    break
            
            if not memory_block:
                logger.warning(f"Memory ID not found: {memory_id}")
                return None
            
            logger.info(f"🧠 Brain reasoning: {reasoning}")
            
            # Handle different memory types
            if isinstance(memory_block, MessageMemoryBlock):
                return self._process_message(memory_block, reasoning)
            elif isinstance(memory_block, ObservationMemoryBlock):
                return self._convert_observation(memory_block, reasoning)
            else:
                # For other memory types, convert to observation format
                return {
                    "from": "memory",
                    "type": "MEMORY_FOCUS",
                    "memory_type": memory_block.type.name,
                    "content": str(memory_block),
                    "id": memory_id,
                    "timestamp": memory_block.timestamp.isoformat() if memory_block.timestamp else datetime.now().isoformat(),
                    "observe_reasoning": reasoning
                }
                
        except Exception as e:
            logger.error(f"Failed to parse memory selection: {e}")
            
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
            "content": obs.path,
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
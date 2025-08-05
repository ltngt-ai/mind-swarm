"""Streamlined Cognitive Loop - Pure OODA cycle implementation.

This refactored version focuses purely on the cognitive orchestration,
delegating all supporting functionality to specialized modules.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Import supporting modules
from .memory import (
    MemorySystem,
    ObservationMemoryBlock, MessageMemoryBlock, CycleStateMemoryBlock,
    KnowledgeMemoryBlock, FileMemoryBlock,
    Priority, MemoryType
)
from .perception import EnvironmentScanner
from .knowledge import KnowledgeManager
from .state import AgentStateManager, ExecutionStateTracker
from .actions import ActionCoordinator
from .utils import DateTimeEncoder, CognitiveUtils, FileManager
from .brain import BrainInterface, MessageProcessor

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
        # Unified memory system
        self.memory_system = MemorySystem(
            filesystem_root=self.home.parent,
            max_tokens=self.max_context_tokens
        )
        
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
        
        # Brain interface
        self.brain_interface = BrainInterface(self.brain_file, self.agent_id)
        self.message_processor = MessageProcessor(self.inbox_dir, self.file_manager)
    
    def _initialize_systems(self):
        """Initialize all systems and load initial data."""
        # Initialize managers
        self.state_manager.initialize()
        self.knowledge_manager.initialize()
        
        # Try to restore memory from snapshot first
        if not self.memory_system.load_from_snapshot_file(self.memory_dir, self.knowledge_manager):
            # No snapshot - load ROM and init fresh
            self.knowledge_manager.load_rom_into_memory(self.memory_system)
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
        self.memory_system.add_memory(cycle_state)
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
            self.memory_system.add_memory(obs)
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
        memory_context = self.memory_system.build_context(
            max_tokens=self.max_context_tokens // 2,  # Give more context for better decisions
            current_task="Deciding what to focus on",
            selection_strategy="balanced"
        )
        
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
        orientation = await self.brain_interface.analyze_situation(observation)
        
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
        action_specs = await self.brain_interface.make_decision(orientation, decision_context)
        
        # Convert action specs to Action objects
        actions = []
        for spec in action_specs:
            action = self.action_coordinator.prepare_action(
                spec["name"], spec.get("params", {}), self.knowledge_manager
            )
            if action:
                actions.append(action)
        
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
        self.action_coordinator.process_action_results(results, self.memory_system)
        
        logger.info(f"⚡ Action phase complete: {successful_actions}/{len(results)} successful")
    
    # === CYCLE STATE HELPERS ===
    
    def _get_cycle_state(self) -> Optional[CycleStateMemoryBlock]:
        """Get the current cycle state from memory."""
        cycle_states = self.memory_system.get_memories_by_type(MemoryType.CYCLE_STATE)
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
        self.memory_system.add_memory(cycle_state)

    # === SUPPORTING METHODS ===
    
    async def maintain(self):
        """Perform maintenance tasks when idle."""
        # Cleanup old memories
        expired = self.memory_system.cleanup_expired()
        old_observations = self.memory_system.cleanup_old_observations(max_age_seconds=1800)
        
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
            self.memory_system.save_snapshot_to_file(self.memory_dir)
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
    
    
    def _build_execution_context(self, observation: Dict[str, Any],
                               orientation: Dict[str, Any]) -> Dict[str, Any]:
        """Build context for action execution."""
        return {
            "cognitive_loop": self,
            "memory_system": self.memory_system,
            "agent_id": self.agent_id,
            "home_dir": self.home,
            "outbox_dir": self.outbox_dir,
            "memory_dir": self.memory_dir,
            "observation": observation,
            "orientation": orientation,
            "task_id": orientation.get("task_memory_id"),
            "original_text": observation.get("query", observation.get("command", ""))
        }
    
    
    async def _select_focus_from_memory(self, memory_context: str) -> Optional[Dict[str, Any]]:
        """Use brain to select what to focus on from full memory context."""
        selection_result = await self.brain_interface.select_focus_from_memory(memory_context)
        
        if not selection_result:
            return None
            
        memory_id = selection_result["memory_id"]
        reasoning = selection_result["reasoning"]
        
        # Retrieve the selected memory
        observation = self.brain_interface.retrieve_memory_by_id(
            memory_id, self.memory_system, reasoning
        )
        
        # If it's a message that needs processing, handle it
        if observation and "message" in memory_id.lower():
            # Find the message memory block for processing
            for memory in self.memory_system.symbolic_memory:
                if memory.id == memory_id and isinstance(memory, MessageMemoryBlock):
                    processed_msg = self.message_processor.process_selected_message(
                        memory, self.memory_system, self.environment_scanner
                    )
                    if processed_msg:
                        processed_msg["observe_reasoning"] = reasoning
                        return processed_msg
                    break
        
        return observation
    
    
    async def _build_decision_context(self, orientation: Dict[str, Any]) -> str:
        """Build context for decision making."""
        return self.memory_system.build_context(
            max_tokens=self.max_context_tokens // 2,
            current_task="Making a decision",
            selection_strategy="balanced"
        )
    
    
    
    
    
    

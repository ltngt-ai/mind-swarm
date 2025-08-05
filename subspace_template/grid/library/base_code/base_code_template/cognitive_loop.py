"""Enhanced Cognitive Loop with full memory system integration.

This version integrates the new memory architecture for rich
filesystem perception and intelligent context management.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

from .boot_rom import BootROM
from .memory import (
    WorkingMemoryManager, ContentLoader, ContextBuilder, 
    MemorySelector, Priority, MemoryType,
    FileMemoryBlock, MessageMemoryBlock,
    ObservationMemoryBlock, ROMMemoryBlock, KnowledgeMemoryBlock,
    CycleStateMemoryBlock
)
from .perception import EnvironmentScanner
from .actions import Action, ActionStatus, action_registry

logger = logging.getLogger("agent.cognitive")

class CognitiveLoop:
    """Enhanced cognitive loop with full memory system."""
    
    def __init__(self, agent_id: str, home: Path, 
                 max_context_tokens: int = 50000,
                 agent_type: str = 'base'):
        """Initialize the enhanced cognitive loop.
        
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
        
        # Core cognitive components
        self.boot_rom = BootROM()
        
        # Memory system components
        self.memory_manager = WorkingMemoryManager(max_tokens=max_context_tokens)
        self.content_loader = ContentLoader(filesystem_root=home.parent)
        self.context_builder = ContextBuilder(self.content_loader)
        self.memory_selector = MemorySelector(self.context_builder)
        
        # Perception system
        grid_path = home.parent.parent / "grid"
        self.environment_scanner = EnvironmentScanner(
            home_path=home,
            grid_path=grid_path
        )
        
        # File interfaces
        self.brain_file = self.home / "brain"
        self.inbox_dir = self.home / "inbox"
        self.outbox_dir = self.home / "outbox"
        self.memory_dir = self.home / "memory"
        
        # Ensure directories exist
        self.inbox_dir.mkdir(exist_ok=True)
        self.outbox_dir.mkdir(exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)
        
        # State
        self.cycle_count = 0
        self.last_activity = datetime.now()
        self.last_full_scan = datetime.now()
        
        # Initialize with boot ROM as critical memory
        self._load_boot_rom_memory()
        
        # Load or initialize cycle state
        self._load_or_init_cycle_state()
    
    def _load_or_init_cycle_state(self):
        """Load cycle state from saved memory or initialize new."""
        memory_snapshot_file = self.memory_dir / "memory_snapshot.json"
        
        if memory_snapshot_file.exists():
            try:
                # Load existing memory snapshot
                with open(memory_snapshot_file, 'r') as f:
                    snapshot = json.load(f)
                    self._restore_from_snapshot(snapshot)
                    
                # Find cycle state in restored memory
                cycle_state_block = None
                for memory in self.memory_manager.symbolic_memory:
                    if isinstance(memory, CycleStateMemoryBlock):
                        cycle_state_block = memory
                        break
                
                if cycle_state_block:
                    logger.info(f"Resumed at cycle {cycle_state_block.cycle_count}, state: {cycle_state_block.cycle_state}")
                else:
                    # No cycle state found, initialize
                    self._init_cycle_state()
            except Exception as e:
                logger.error(f"Failed to load memory snapshot: {e}")
                self._init_cycle_state()
        else:
            # Initialize new cycle state
            self._init_cycle_state()
    
    def _init_cycle_state(self):
        """Initialize a new cycle state."""
        cycle_state = CycleStateMemoryBlock(
            cycle_state="perceive",
            cycle_count=0
        )
        self.memory_manager.add_memory(cycle_state)
        logger.info("Initialized new cycle state")
    
    
    def _restore_from_snapshot(self, snapshot: Dict[str, Any]):
        """Restore memory from a snapshot."""
        memories = snapshot.get('memories', [])
        logger.info(f"Restoring from snapshot with {len(memories)} memories")
        
        # Restore configuration from snapshot
        if 'max_tokens' in snapshot:
            self.memory_manager.max_tokens = snapshot['max_tokens']
        if 'current_task_id' in snapshot:
            self.memory_manager.current_task_id = snapshot['current_task_id']
        if 'active_topics' in snapshot:
            self.memory_manager.active_topics = set(snapshot['active_topics'])
        
        # Reconstruct memory blocks
        cycle_state_found = False
        for mem_data in memories:
            try:
                memory_type = MemoryType(mem_data['type'])
                
                # Reconstruct based on type
                if memory_type == MemoryType.CYCLE_STATE:
                    # Special handling for cycle state
                    memory = CycleStateMemoryBlock(
                        cycle_state=mem_data['cycle_state'],
                        cycle_count=mem_data['cycle_count'],
                        current_observation=mem_data.get('current_observation'),
                        current_orientation=mem_data.get('current_orientation'),
                        current_actions=mem_data.get('current_actions'),
                        confidence=mem_data.get('confidence', 1.0),
                        priority=Priority[mem_data.get('priority', 'CRITICAL')]
                    )
                    cycle_state_found = True
                    # Update our cycle count
                    self.cycle_count = memory.cycle_count
                    
                elif memory_type == MemoryType.FILE:
                    memory = FileMemoryBlock(
                        location=mem_data['location'],
                        start_line=mem_data.get('start_line'),
                        end_line=mem_data.get('end_line'),
                        digest=mem_data.get('digest'),
                        confidence=mem_data.get('confidence', 1.0),
                        priority=Priority[mem_data.get('priority', 'MEDIUM')]
                    )
                    
                elif memory_type == MemoryType.MESSAGE:
                    memory = MessageMemoryBlock(
                        from_agent=mem_data['from_agent'],
                        to_agent=mem_data['to_agent'],
                        subject=mem_data.get('subject', ''),
                        preview=mem_data.get('preview', ''),
                        full_path=mem_data['full_path'],
                        read=mem_data.get('read', False),
                        confidence=mem_data.get('confidence', 1.0),
                        priority=Priority[mem_data.get('priority', 'HIGH')]
                    )
                    
                elif memory_type == MemoryType.OBSERVATION:
                    memory = ObservationMemoryBlock(
                        observation_type=mem_data['observation_type'],
                        path=mem_data.get('path', ''),
                        description=mem_data['description'],
                        confidence=mem_data.get('confidence', 1.0),
                        priority=Priority[mem_data.get('priority', 'MEDIUM')]
                    )
                    
                else:
                    # Skip other types for now
                    continue
                
                # Restore timestamps
                if 'timestamp' in mem_data:
                    memory.timestamp = datetime.fromisoformat(mem_data['timestamp'])
                if 'expiry' in mem_data and mem_data['expiry']:
                    memory.expiry = datetime.fromisoformat(mem_data['expiry'])
                
                # Add to memory manager
                self.memory_manager.add_memory(memory)
                
            except Exception as e:
                logger.warning(f"Failed to restore memory: {e}")
                continue
        
        # If no cycle state was found, initialize one
        if not cycle_state_found:
            logger.info("No cycle state found in snapshot, initializing new one")
            self._init_cycle_state()
    
    def _get_cycle_state_block(self) -> Optional[CycleStateMemoryBlock]:
        """Get the current cycle state memory block."""
        for memory in self.memory_manager.symbolic_memory:
            if isinstance(memory, CycleStateMemoryBlock):
                return memory
        return None
    
    def _update_cycle_state(self, new_state: str, **kwargs):
        """Update the cycle state memory block."""
        # Get the old cycle state
        old_state = None
        for memory in self.memory_manager.symbolic_memory:
            if isinstance(memory, CycleStateMemoryBlock):
                old_state = memory
                break
        
        # Create new cycle state with updated values
        cycle_state = CycleStateMemoryBlock(
            cycle_state=new_state,
            cycle_count=old_state.cycle_count if old_state else self.cycle_count,
            current_observation=kwargs.get('current_observation', old_state.current_observation if old_state else None),
            current_orientation=kwargs.get('current_orientation', old_state.current_orientation if old_state else None),
            current_actions=kwargs.get('current_actions', old_state.current_actions if old_state else None)
        )
        # add_memory will handle removing the old one since they have the same id
        self.memory_manager.add_memory(cycle_state)
    
    def _load_boot_rom_memory(self):
        """Load boot ROM from library knowledge files."""
        # Load general ROM files
        general_rom_dir = Path("/grid/library/rom/general")
        if general_rom_dir.exists():
            self._load_rom_directory(general_rom_dir)
        else:
            # Fallback to legacy boot ROM
            logger.warning("ROM directory not found, using legacy boot ROM")
            rom_memory = FileMemoryBlock(
                location="<BOOT_ROM>",
                priority=Priority.CRITICAL,
                confidence=1.0,
                metadata={
                    "virtual": True,
                    "content": self.boot_rom.format_core_knowledge()
                }
            )
            self.memory_manager.add_memory(rom_memory)
        
        # Load agent-specific ROM if available
        agent_rom_dir = Path(f"/grid/library/rom/{self.agent_type}")
        if agent_rom_dir.exists():
            self._load_rom_directory(agent_rom_dir)
    
    def _load_rom_directory(self, rom_dir: Path):
        """Load all knowledge files from a ROM directory."""
        rom_count = 0
        # Load YAML files only
        for pattern in ["*.yaml", "*.yml"]:
            for knowledge_file in rom_dir.glob(pattern):
                if self._load_knowledge_file(knowledge_file, is_rom=True):
                    rom_count += 1
        
        logger.info(f"Loaded {rom_count} ROM files from {rom_dir}")
    
    def _load_knowledge_file(self, knowledge_path: Path, is_rom: bool = False) -> bool:
        """Load a knowledge file and add to working memory.
        
        Args:
            knowledge_path: Path to knowledge JSON file
            is_rom: Whether this is a ROM file (always loaded)
            
        Returns:
            True if successfully loaded
        """
        try:
            # Load YAML file
            import yaml
            file_content = knowledge_path.read_text()
            knowledge_data = yaml.safe_load(file_content)
            
            # Validate schema version
            if knowledge_data.get("knowledge_version") != "1.0":
                logger.warning(f"Unknown knowledge version in {knowledge_path}")
                return False
            
            # Extract metadata
            metadata = knowledge_data.get("metadata", {})
            priority_value = metadata.get("priority", 3)
            
            # Create a KnowledgeMemoryBlock
            knowledge_memory = KnowledgeMemoryBlock(
                topic=metadata.get("category", "general"),
                location=str(knowledge_path),
                subtopic=knowledge_data.get("title", ""),
                relevance_score=1.0 if is_rom else metadata.get("confidence", 0.8),
                confidence=metadata.get("confidence", 1.0),
                priority=Priority(priority_value),
                metadata={
                    "knowledge_id": knowledge_data["id"],
                    "content": knowledge_data["content"] if isinstance(knowledge_data["content"], str) else "\n".join(knowledge_data["content"]),
                    "tags": metadata.get("tags", []),
                    "source": metadata.get("source", "library"),
                    "version": metadata.get("version", 1),
                    "is_rom": is_rom
                }
            )
            
            self.memory_manager.add_memory(knowledge_memory)
            return True
            
        except Exception as e:
            logger.error(f"Failed to load knowledge from {knowledge_path}: {e}")
            return False
    
    async def run_cycle(self) -> bool:
        """Run one complete cognitive cycle with memory system.
        
        This is a resumable state machine - each step saves its output
        to working memory before moving to the next state.
        
        Returns:
            True if something was processed, False if idle
        """
        self.cycle_count += 1
        
        # Get current state from cycle state memory block
        cycle_state_block = self._get_cycle_state_block()
        state = cycle_state_block.cycle_state if cycle_state_block else "perceive"
        logger.debug(f"Resuming cycle {self.cycle_count} at state: {state}")
        
        try:
            # State machine - each state processes and advances to next
            if state == "perceive":
                # PERCEIVE - Scan environment and update memories
                await self.perceive()
                self._update_cycle_state("observe")
                await self._save_memory_snapshot()
                
            elif state == "observe":
                # OBSERVE - Check for high-priority inputs
                observation = await self.observe()
                if observation:
                    # Save observation and move to orient
                    self._update_cycle_state("orient", current_observation=observation)
                else:
                    # No observation, do maintenance and restart
                    await self.maintain()
                    self._update_cycle_state("perceive")
                    await self._save_memory_snapshot()
                    return False
                await self._save_memory_snapshot()
                
            elif state == "orient":
                # ORIENT - Understand the situation with full context
                cycle_state_block = self._get_cycle_state_block()
                observation = cycle_state_block.current_observation if cycle_state_block else None
                if not observation:
                    # Lost our observation, restart
                    self._update_cycle_state("perceive")
                    await self._save_memory_snapshot()
                    return True
                    
                orientation = await self.orient(observation)
                logger.info(f"Oriented: {orientation.get('task_type')} - approach={orientation.get('approach')}")
                
                # Save orientation and advance
                self._update_cycle_state("decide", current_orientation=orientation)
                await self._save_memory_snapshot()
                
            elif state == "decide":
                # DECIDE - Choose actions to take (this is where brain calls happen)
                cycle_state_block = self._get_cycle_state_block()
                orientation = cycle_state_block.current_orientation if cycle_state_block else None
                if not orientation:
                    # Lost our orientation, restart
                    self._update_cycle_state("perceive")
                    await self._save_memory_snapshot()
                    return True
                    
                actions = await self.decide(orientation)
                logger.info(f"Decided on {len(actions)} actions: {[a.name for a in actions]}")
                
                # Save actions as serializable data
                action_data = [{"name": a.name, "params": a.params} for a in actions]
                self._update_cycle_state("instruct", current_actions=action_data)
                await self._save_memory_snapshot()
                
            elif state == "instruct":
                # INSTRUCT - Load action knowledge and validate/fix parameters
                logger.info("=== ENTERING INSTRUCT PHASE ===")
                cycle_state_block = self._get_cycle_state_block()
                if not cycle_state_block:
                    # Missing state, restart
                    logger.warning("Missing cycle state block in instruct phase")
                    self._update_cycle_state("perceive")
                    await self._save_memory_snapshot()
                    return True
                
                action_data = cycle_state_block.current_actions or []
                logger.info(f"Instruct phase: found {len(action_data)} actions to instruct")
                if not action_data:
                    # No actions to take - agent is just observing/waiting
                    logger.info("No actions to take, taking a brief rest before observing again")
                    # Brief pause to avoid spinning when idle
                    await asyncio.sleep(1.0)
                    self._update_cycle_state("perceive")
                    await self._save_memory_snapshot()
                    return True
                
                # Load action knowledge and fix parameters
                logger.info(f"Loading action knowledge for: {[a.get('name') for a in action_data]}")
                instructed_actions = await self.instruct(action_data)
                
                # Save instructed actions and advance to act
                logger.info(f"Instruct phase complete, advancing to act with {len(instructed_actions)} actions")
                self._update_cycle_state("act", current_actions=instructed_actions)
                await self._save_memory_snapshot()
                
            elif state == "act":
                # ACT - Execute actions in sequence
                cycle_state_block = self._get_cycle_state_block()
                if not cycle_state_block:
                    # Missing state, restart
                    self._update_cycle_state("perceive")
                    await self._save_memory_snapshot()
                    return True
                    
                observation = cycle_state_block.current_observation
                orientation = cycle_state_block.current_orientation
                action_data = cycle_state_block.current_actions or []
                
                if not all([observation, orientation, action_data]):
                    # Missing data, restart
                    self._update_cycle_state("perceive")
                    await self._save_memory_snapshot()
                    return True
                
                # Recreate action objects from saved data
                actions = []
                agent_type = self.agent_type if hasattr(self, 'agent_type') else 'base'
                for data in action_data:
                    action = action_registry.create_action(agent_type, data["name"])
                    if action:
                        action.with_params(**data.get("params", {}))
                        actions.append(action)
                
                await self.act(observation, orientation, actions)
                
                # Action sequence complete, restart cycle
                self._update_cycle_state("perceive")
                await self._save_memory_snapshot()
                
            else:
                # Unknown state, restart
                logger.warning(f"Unknown cycle state: {state}, restarting")
                self._update_cycle_state("perceive")
                await self._save_memory_snapshot()
            
            self.last_activity = datetime.now()
            return True
            
        except Exception as e:
            logger.error(f"Error in cognitive cycle state {state}: {e}", exc_info=True)
            # On error, try to restart from perceive
            self._update_cycle_state("perceive")
            await self._save_memory_snapshot()
            return False
    
    async def perceive(self):
        """Scan environment and update memory with observations."""
        # Determine if we need a full scan
        time_since_full = (datetime.now() - self.last_full_scan).total_seconds()
        full_scan = time_since_full > 300  # Full scan every 5 minutes
        
        # Scan environment
        observations = self.environment_scanner.scan_environment(full_scan=full_scan)
        
        if full_scan:
            self.last_full_scan = datetime.now()
        
        # Add observations to memory and log significant ones
        significant_count = 0
        for obs in observations:
            self.memory_manager.add_memory(obs)
            
            # Log significant observations (not low-priority status updates)
            if obs.priority != Priority.LOW:
                significant_count += 1
                if isinstance(obs, ObservationMemoryBlock):
                    logger.info(f"Observed: {obs.observation_type} at {obs.path} - {obs.description}")
                elif isinstance(obs, MessageMemoryBlock):
                    logger.info(f"New message: {obs.subject} from {obs.from_agent}")
                elif hasattr(obs, 'description'):
                    logger.info(f"Observed: {obs.id}")
        
        # Only log if there were significant changes
        if significant_count > 0:
            logger.info(f"Perceived {significant_count} significant changes in environment")
    
    async def observe(self) -> Optional[Dict[str, Any]]:
        """Intelligently select the most important observation to focus on.
        
        Uses the brain with working memory context to prioritize observations.
        """
        # Get all recent observations (messages, action results, env changes)
        recent_cutoff = datetime.now().timestamp() - 300  # Last 5 minutes
        recent_observations = [
            obs for obs in self.memory_manager.symbolic_memory
            if isinstance(obs, ObservationMemoryBlock) 
            and obs.timestamp is not None
            and obs.timestamp.timestamp() > recent_cutoff
        ]
        
        # Get unread messages
        unread_messages = self.memory_manager.get_unread_messages()
        
        if not recent_observations and not unread_messages:
            return None
            
        # Build working memory context
        # Select relevant memories for deciding what to focus on
        selected_memories = self.memory_selector.select_memories(
            symbolic_memory=self.memory_manager.symbolic_memory,
            max_tokens=self.max_context_tokens // 4,
            current_task="Deciding what to focus on",
            selection_strategy="balanced"
        )
        memory_context = self.context_builder.build_context(selected_memories)
        
        # Prepare summaries for the brain
        obs_summaries = []
        for i, obs in enumerate(recent_observations[-10:]):  # Last 10
            age = int(datetime.now().timestamp() - obs.timestamp.timestamp()) if obs.timestamp else 0
            obs_summaries.append({
                "index": i,
                "type": obs.observation_type,
                "description": obs.description,
                "age_seconds": age,
                "priority": obs.priority.name,
                "path": obs.path
            })
            
        msg_summaries = []
        for i, msg in enumerate(unread_messages[:5]):  # Up to 5
            age = int(datetime.now().timestamp() - msg.timestamp.timestamp()) if msg.timestamp else 0
            msg_summaries.append({
                "index": i,
                "from": msg.from_agent,
                "subject": msg.subject,
                "age_seconds": age
            })
        
        # Use brain to prioritize
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
                "context": memory_context  # Full working memory context
            },
            "request_id": f"observe_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self._use_brain(json.dumps(thinking_request, cls=DateTimeEncoder))
        
        try:
            result = json.loads(response.replace("<<<THOUGHT_COMPLETE>>>", "").strip())
            output = result.get("output_values", {})
            
            focus = output.get("focus", "message:0")
            reasoning = output.get("reasoning", "")
            
            logger.info(f"Observe selected: {focus} - {reasoning}")
            
            # Parse the focus decision
            if focus.startswith("message:") and unread_messages:
                idx = int(focus.split(":")[1])
                msg = unread_messages[min(idx, len(unread_messages)-1)]
                
                # Process the message
                try:
                    msg_path = Path(msg.full_path)
                    if msg_path.exists():
                        message = json.loads(msg_path.read_text())
                        
                        # Mark as processed
                        self.memory_manager.mark_message_read(msg.id)
                        self.environment_scanner.mark_message_processed(str(msg_path))
                        
                        # Move to processed
                        processed_dir = self.inbox_dir / "processed"
                        processed_dir.mkdir(exist_ok=True)
                        msg_path.rename(processed_dir / msg_path.name)
                        
                        # Add observe reasoning to the message
                        message["observe_reasoning"] = reasoning
                        
                        logger.info(f"Processing message: {msg.subject}")
                        return message
                        
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
            elif focus.startswith("observation:") and recent_observations:
                idx = int(focus.split(":")[1])
                obs = recent_observations[-(min(idx+1, len(recent_observations)))]
                
                # Convert observation to message-like format for orient
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
                
        except Exception as e:
            logger.error(f"Failed to parse observe response: {e}")
            # Fallback to oldest unread message
            if unread_messages:
                return await self._process_oldest_message(unread_messages)
                
        return None
    
    async def _process_oldest_message(self, messages: List[MessageMemoryBlock]) -> Optional[Dict[str, Any]]:
        """Fallback method to process oldest message mechanically."""
        # Filter out messages without timestamps
        valid_messages = [m for m in messages if m.timestamp is not None]
        if not valid_messages:
            return None
            
        oldest_msg = min(valid_messages, key=lambda m: m.timestamp)
        try:
            msg_path = Path(oldest_msg.full_path)
            if msg_path.exists():
                message = json.loads(msg_path.read_text())
                
                self.memory_manager.mark_message_read(oldest_msg.id)
                self.environment_scanner.mark_message_processed(str(msg_path))
                
                processed_dir = self.inbox_dir / "processed"
                processed_dir.mkdir(exist_ok=True)
                msg_path.rename(processed_dir / msg_path.name)
                
                return message
        except Exception as e:
            logger.error(f"Error in fallback message processing: {e}")
        return None
    
    async def orient(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Use the orient DSPy signature to understand the observation."""
        # Create observation memory
        obs_memory = ObservationMemoryBlock(
            observation_type="message_received",
            path="<inbox>",
            description=f"Received message: {json.dumps(observation)}",
            priority=Priority.HIGH
        )
        self.memory_manager.add_memory(obs_memory)
        
        # Build structured thinking request for orient
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
        
        # Use the brain with structured request
        analysis_json = json.dumps(thinking_request)
        response = await self._use_brain(analysis_json)
        
        try:
            # Parse the structured response
            result = json.loads(response.replace("<<<THOUGHT_COMPLETE>>>", "").strip())
            
            # Map the DSPy outputs to our orientation format
            orientation = {
                "task_type": result.get("output_values", {}).get("situation_type", "unknown"),
                "approach": self._determine_approach(result.get("output_values", {})),
                "requires_response": True,  # Most things require response
                "content": observation.get("command", observation.get("query", str(observation))),
                "reasoning": result.get("output_values", {}).get("understanding", ""),
                "relevant_knowledge": result.get("output_values", {}).get("relevant_knowledge", ""),
                "timestamp": datetime.now(),
                "from": observation.get("from", "unknown"),
                "original_message": observation
            }
            
            logger.info(f"Oriented: {orientation['task_type']} - {orientation['reasoning']}")
            
            # No special message types - agents don't know about infrastructure
            # No automatic task creation - let agents manage their own understanding
            
        except Exception as e:
            logger.error(f"Failed to parse orient response: {e}", exc_info=True)
            # Fallback
            orientation = {
                "task_type": "unknown",
                "approach": "thinking",
                "requires_response": True,
                "content": str(observation),
                "timestamp": datetime.now(),
                "from": observation.get("from", "unknown"),
                "reasoning": "Failed to orient properly, treating as general thinking task"
            }
        
        return orientation
    
    def _determine_approach(self, output_values: Dict[str, Any]) -> str:
        """Determine approach based on DSPy orient outputs."""
        situation = output_values.get("situation_type") or ""
        understanding = output_values.get("understanding") or ""
        
        # Convert to lowercase for comparison
        situation = situation.lower() if isinstance(situation, str) else ""
        understanding = understanding.lower() if isinstance(understanding, str) else ""
        
        if "arithmetic" in situation or "math" in situation:
            return "thinking"
        elif "question" in situation:
            return "answering"
        elif "command" in situation:
            return "executing"
        else:
            return "thinking"
    
    def _get_memory_context_summary(self) -> str:
        """Get a summary of current memory state for decision making."""
        stats = self.memory_manager.get_memory_stats()
        summary = f"Total memories: {stats['total_memories']}\n"
        summary += f"By type: {json.dumps(stats['by_type'], indent=2)}\n"
        
        # Get recent memories
        recent = [m for m in self.memory_manager.symbolic_memory 
                  if (datetime.now() - m.timestamp).total_seconds() < 300]
        if recent:
            summary += f"\nRecent activity ({len(recent)} items in last 5 min)"
        
        return summary
    
    async def decide(self, orientation: Dict[str, Any]) -> List[Action]:
        """Decide what actions to take based on the current situation.
        
        Returns:
            List of Actions to execute in order
        """
        # Get available actions for this agent type
        agent_type = self.agent_type if hasattr(self, 'agent_type') else 'base'
        
        # Build working memory context for decision
        # Select relevant memories including ROM action knowledge
        selected_memories = self.memory_selector.select_memories(
            symbolic_memory=self.memory_manager.symbolic_memory,
            max_tokens=self.max_context_tokens // 2,  # Use half budget for context
            current_task="Deciding what actions to take",
            selection_strategy="balanced"
        )
        
        # Log what memories were selected
        logger.info(f"Selected {len(selected_memories)} memories for decide phase")
        
        # Count ROM memories
        rom_count = sum(1 for m in selected_memories if isinstance(m, KnowledgeMemoryBlock) and m.metadata.get('is_rom', False))
        action_count = sum(1 for m in selected_memories if isinstance(m, KnowledgeMemoryBlock) and 'action' in str(m.location).lower())
        logger.info(f"ROM memories: {rom_count}, Action knowledge: {action_count}")
        
        # Build context with emphasis on action knowledge
        memory_context = self.context_builder.build_context(selected_memories)
        
        # Log the full context - we have grep if we need to search
        logger.info(f"Full working memory context: {memory_context}")
        
        # Check if we have action system ROM
        has_action_rom = any(
            'action_system' in str(m.location) 
            for m in selected_memories 
            if isinstance(m, KnowledgeMemoryBlock)
        )
        logger.info(f"Has action_system ROM in context: {has_action_rom}")
               
        constraints = f"Token budget: {self.max_context_tokens}, Must respond via outbox"
        
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
                "working_memory": memory_context,
                "goal": orientation.get("content", "unknown request")
            },
            "request_id": f"decide_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        # Use the brain to decide
        decision_json = json.dumps(thinking_request)
        response = await self._use_brain(decision_json)
        
        # Debug logging
        logger.info(f"Brain response length: {len(response)}")
        logger.info(f"Full brain response: {response}")
        
        actions = []
        
        try:
            # Parse response
            cleaned_response = response.replace("<<<THOUGHT_COMPLETE>>>", "").strip()
            logger.info(f"Cleaned response length: {len(cleaned_response)}")
            logger.info(f"Full cleaned response: {cleaned_response}")
            
            result = json.loads(cleaned_response)
            output = result.get("output_values", {})
            
            action_names = output.get("actions", "[]")
            reasoning = output.get("reasoning", "")
            
            logger.info(f"Action names: {action_names}")
            logger.info(f"Reasoning: {reasoning}")
            
            # Store raw action output for potential instruct phase correction
            raw_action_output = action_names
            
            # Parse the JSON array of action objects
            try:
                # First, try to clean up markdown-wrapped JSON
                cleaned_actions = action_names
                if isinstance(action_names, str) and "```json" in action_names and "```" in action_names:
                    # Extract JSON from markdown code block
                    start = action_names.find("```json") + 7
                    end = action_names.rfind("```")
                    if start < end:
                        cleaned_actions = action_names[start:end].strip()
                        logger.info(f"Extracted JSON from markdown: {cleaned_actions}")
                elif isinstance(action_names, str) and "```" in action_names:
                    # Try generic code block
                    start = action_names.find("```") + 3
                    end = action_names.rfind("```")
                    if start < end:
                        cleaned_actions = action_names[start:end].strip()
                        logger.info(f"Extracted from code block: {cleaned_actions}")
                
                if isinstance(cleaned_actions, str):
                    action_objects = json.loads(cleaned_actions)
                else:
                    action_objects = cleaned_actions
                
                # Create Action objects from the specifications
                for action_spec in action_objects:
                    if isinstance(action_spec, dict):
                        action_name = action_spec.get("action")
                        params = action_spec.get("params", {})
                    else:
                        # Fallback for simple string format
                        action_name = action_spec
                        params = {}
                    
                    if action_name:  # Only create action if we have a valid name
                        action = action_registry.create_action(agent_type, action_name)
                        if action:
                            # Use provided parameters or fall back to defaults
                            if params:
                                action.with_params(**params)
                            actions.append(action)
                        else:
                            logger.warning(f"Unknown action: {action_name}")
                        
            except json.JSONDecodeError:
                logger.error(f"Failed to parse action names as JSON: {action_names}")
                # Pass raw output to instruct phase for correction
                actions = []
                # Create a special raw action to signal instruct phase
                raw_action = type('RawAction', (), {
                    'name': '_raw_action_output',
                    'params': {
                        'raw_output': raw_action_output, 
                        'reasoning': reasoning,
                        'orientation': orientation
                    }
                })()
                actions.append(raw_action)
            
        except Exception as e:
            logger.error(f"Failed to parse decide response: {e}", exc_info=True)
        
        # Record decision as observation
        decision_obs = ObservationMemoryBlock(
            observation_type="decision",
            path="cognitive_loop",
            description=f"Planned {len(actions)} actions: {[a.name for a in actions]}",
            priority=Priority.LOW,
            metadata={"action_count": len(actions), "action_names": [a.name for a in actions]}
        )
        self.memory_manager.add_memory(decision_obs)
        
        return actions
    
    async def instruct(self, action_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Instruct phase - Load action knowledge and validate/fix parameters.
        
        This phase loads knowledge about how to use each action and fixes
        common parameter mistakes before execution.
        
        Args:
            action_data: List of action dictionaries with name and params
            
        Returns:
            List of corrected action dictionaries
        """
        corrected_actions = []
        
        # Check if we have raw action output to fix
        if (len(action_data) == 1 and 
            action_data[0].get("name") == "_raw_action_output"):
            # Special case: need to parse and fix raw output
            logger.info("Instruct phase: Fixing raw action output")
            raw_params = action_data[0].get("params", {})
            raw_output = raw_params.get("raw_output", "")
            reasoning = raw_params.get("reasoning", "")
            orientation = raw_params.get("orientation", {})
            available_actions = raw_params.get("available_actions", [])
            
            # Use brain to fix the formatting
            fix_request = {
                "signature": {
                    "task": "Fix malformed action JSON",
                    "description": "Convert the raw action output into proper JSON format",
                    "inputs": {
                        "raw_output": "The raw action output that failed to parse",
                        "reasoning": "The reasoning behind the actions",
                        "available_actions": "List of valid action names",
                        "context": "Context about the task"
                    },
                    "outputs": {
                        "fixed_json": "Properly formatted JSON array of action objects",
                        "explanation": "What was wrong and how it was fixed"
                    }
                },
                "input_values": {
                    "raw_output": raw_output,
                    "reasoning": reasoning,
                    "available_actions": ", ".join(available_actions),
                    "context": str(orientation)
                },
                "request_id": f"fix_actions_{int(time.time()*1000)}",
                "timestamp": datetime.now().isoformat()
            }
            
            response = await self._use_brain(json.dumps(fix_request))
            
            try:
                result = json.loads(response.replace("<<<THOUGHT_COMPLETE>>>", "").strip())
                fixed_json = result.get("output_values", {}).get("fixed_json", "[]")
                explanation = result.get("output_values", {}).get("explanation", "")
                
                logger.info(f"Fixed JSON: {fixed_json}")
                logger.info(f"Fix explanation: {explanation}")
                
                # Parse the fixed JSON
                action_objects = json.loads(fixed_json)
                
                # Convert to our format
                for action_spec in action_objects:
                    if isinstance(action_spec, dict):
                        corrected_actions.append({
                            "name": action_spec.get("action", ""),
                            "params": action_spec.get("params", {})
                        })
                
                # If we got valid actions, return them
                if corrected_actions:
                    return corrected_actions
                    
            except Exception as e:
                logger.error(f"Failed to fix raw actions: {e}")
            
            # If fixing failed, return empty action list
            # Let the agent try again on the next cycle rather than sending confusing error messages
            return []
        
        # Normal case: process each action
        for action_spec in action_data:
            action_name = action_spec.get("name", "")
            original_params = action_spec.get("params", {})
            
            # Load action knowledge
            action_knowledge = await self._load_action_knowledge(action_name)
            
            if action_knowledge:
                # Add to working memory
                self.memory_manager.add_memory(action_knowledge)
                
                # Extract parameter schema from knowledge
                metadata = action_knowledge.metadata if action_knowledge.metadata else {}
                param_schema = metadata.get("parameter_schema", {})
                corrections = metadata.get("common_corrections", [])
                
                # Apply automatic corrections
                corrected_params = original_params.copy()
                
                # Check for parameter aliases and rename
                for param_name, param_info in param_schema.items():
                    if param_name not in corrected_params:
                        # Check if any alias was used
                        aliases = param_info.get("aliases", [])
                        for alias in aliases:
                            if alias in corrected_params:
                                corrected_params[param_name] = corrected_params.pop(alias)
                                logger.info(f"Corrected parameter: '{alias}' -> '{param_name}' for action {action_name}")
                                break
                
                # Apply specific corrections
                for correction in corrections:
                    if_param = correction.get("if_param")
                    then_rename = correction.get("then_rename")
                    if if_param in corrected_params and then_rename:
                        corrected_params[then_rename] = corrected_params.pop(if_param)
                        logger.info(f"Applied correction: '{if_param}' -> '{then_rename}' for action {action_name}")
                
                # Validate required parameters
                missing_required = []
                for param_name, param_info in param_schema.items():
                    if param_info.get("required", False) and param_name not in corrected_params:
                        missing_required.append(param_name)
                
                if missing_required:
                    # Use brain to figure out missing parameters
                    thinking_request = {
                        "signature": {
                            "task": "Fill in missing action parameters",
                            "description": "Determine values for missing required parameters based on context",
                            "inputs": {
                                "action_name": "The action being prepared",
                                "missing_params": "List of missing required parameters",
                                "param_descriptions": "What each parameter does",
                                "current_params": "Parameters already provided",
                                "context": "Current task context"
                            },
                            "outputs": {
                                "filled_params": "Dictionary of parameter names to values",
                                "reasoning": "Why these values were chosen"
                            },
                            "display_field": "reasoning"
                        },
                        "input_values": {
                            "action_name": action_name,
                            "missing_params": missing_required,
                            "param_descriptions": {p: param_schema[p].get("description", "") for p in missing_required},
                            "current_params": corrected_params,
                            "context": f"Working on: {getattr(self, 'current_task', 'unknown task')}"
                        },
                        "request_id": f"instruct_{int(time.time()*1000)}",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    response = await self._use_brain(json.dumps(thinking_request))
                    try:
                        result = json.loads(response.replace("<<<THOUGHT_COMPLETE>>>", "").strip())
                        filled = result.get("output_values", {}).get("filled_params", {})
                        if isinstance(filled, dict):
                            corrected_params.update(filled)
                            logger.info(f"Brain filled missing params for {action_name}: {filled}")
                    except Exception as e:
                        logger.warning(f"Failed to fill missing params: {e}")
                
                # Apply defaults for optional parameters
                for param_name, param_info in param_schema.items():
                    if param_name not in corrected_params and "default" in param_info:
                        corrected_params[param_name] = param_info["default"]
                
                corrected_actions.append({
                    "name": action_name,
                    "params": corrected_params
                })
            else:
                # No knowledge available, use original
                logger.warning(f"No knowledge found for action: {action_name}")
                corrected_actions.append(action_spec)
        
        # Log the corrections made
        for i, (original, corrected) in enumerate(zip(action_data, corrected_actions)):
            if original != corrected:
                logger.info(f"Action {i} corrected: {original} -> {corrected}")
        
        return corrected_actions
    
    async def _load_action_knowledge(self, action_name: str) -> Optional[KnowledgeMemoryBlock]:
        """Load knowledge about how to use an action.
        
        Args:
            action_name: Name of the action
            
        Returns:
            KnowledgeMemoryBlock if found, None otherwise
        """
        # Look for action knowledge in the library (always at /grid/library)
        knowledge_path = Path(f"/grid/library/actions/{action_name}.yaml")
        
        if knowledge_path.exists():
            if self._load_knowledge_file(knowledge_path):
                # Find the loaded knowledge in memory
                for memory in self.memory_manager.symbolic_memory:
                    if isinstance(memory, KnowledgeMemoryBlock) and action_name in str(memory.location):
                        return memory
                # If not found in memory after loading, something went wrong
                logger.warning(f"Loaded knowledge file but couldn't find in memory: {knowledge_path}")
        else:
            logger.debug(f"No knowledge file found at: {knowledge_path}")
        
        return None
    
    async def act(self, observation: Dict[str, Any], 
                  orientation: Dict[str, Any], 
                  actions: List[Action]):
        """Execute actions in sequence, storing results in memory.
        
        Args:
            observation: Current observation
            orientation: Understanding of the situation  
            actions: List of actions to execute in order
        """
        # Build execution context
        context = {
            "cognitive_loop": self,
            "memory_manager": self.memory_manager,
            "agent_id": getattr(self, 'agent_id', 'unknown'),
            "home_dir": self.home,
            "outbox_dir": self.outbox_dir,
            "memory_dir": self.memory_dir,
            "observation": observation,
            "orientation": orientation,
            "task_id": orientation.get("task_memory_id"),
            "original_text": observation.get("query", observation.get("command", observation.get("content", "")))
        }
        
        # Add agent-specific context
        if hasattr(self, 'io_handler'):
            context["io_handler"] = self.io_handler
        
        # Execute each action in sequence
        for i, action in enumerate(actions):
            logger.info(f"Executing action {i+1}/{len(actions)}: {action.name}")
            
            try:
                # Execute the action
                result = await action.execute(context)
                
                # Store result as observation for subsequent actions
                if result.result:
                    obs = ObservationMemoryBlock(
                        observation_type="action_result",
                        path=f"action_{i}_{action.name}",
                        description=f"Result of {action.name}: {str(result.result)[:100]}",
                        priority=Priority.HIGH,
                        metadata={
                            "action_name": action.name,
                            "action_index": i,
                            "status": result.status.value,
                            "full_result": result.result,
                            "error": result.error if result.status == ActionStatus.FAILED else None
                        }
                    )
                    self.memory_manager.add_memory(obs)
                    
                    # Make the observation ID available to subsequent actions
                    context[f"action_{i}_result_id"] = obs.id
                    context["last_action_result_id"] = obs.id
                    context["last_action_result"] = result.result
                
                # Check if action failed
                if result.status == ActionStatus.FAILED:
                    logger.error(f"Action {action.name} failed: {result.error}")
                    # Decide whether to continue or abort
                    if action.priority == Priority.HIGH:
                        logger.warning("High priority action failed, aborting sequence")
                        break
                
                # Actions execute in sequence until done
                    
            except Exception as e:
                logger.error(f"Error executing action {action.name}: {e}", exc_info=True)
                
                # Record error as observation
                error_obs = ObservationMemoryBlock(
                    observation_type="action_error",
                    path=f"action_{i}_{action.name}",
                    description=f"Failed to execute {action.name}: {str(e)}",
                    priority=Priority.HIGH,
                    metadata={
                        "action_name": action.name,
                        "action_index": i,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                self.memory_manager.add_memory(error_obs)
                
                # Continue with next action unless critical
                if action.priority == Priority.HIGH:
                    break
        
        logger.info(f"Completed {len(actions)} actions")
    
    async def _use_brain(self, prompt: str) -> str:
        """Use the brain file interface to think."""
        logger.info("=== BRAIN REQUEST START ===")
        logger.info(f"Request length: {len(prompt)} characters")
        logger.info("Full request to brain:")
        logger.info(prompt)
        logger.info("=== BRAIN REQUEST END ===")
        
        # Escape any protocol markers in the prompt to prevent false positives
        escaped_prompt = prompt.replace("<<<THOUGHT_COMPLETE>>>", "[THOUGHT_COMPLETE]")
        escaped_prompt = escaped_prompt.replace("<<<END_THOUGHT>>>", "[END_THOUGHT]")
        
        # Write prompt with end marker
        self.brain_file.write_text(f"{escaped_prompt}\n<<<END_THOUGHT>>>")
        logger.debug("Wrote prompt to brain file")
        
        # Wait for response
        wait_count = 0
        while True:
            content = self.brain_file.read_text()
            
            # Debug logging on first read
            if wait_count == 0:
                logger.debug(f"First read after write - content length: {len(content)}")
                logger.debug(f"Content preview: {repr(content[:200])}")
                logger.debug(f"Contains END_THOUGHT: {'<<<END_THOUGHT>>>' in content}")
                logger.debug(f"Contains THOUGHT_COMPLETE: {'<<<THOUGHT_COMPLETE>>>' in content}")
            
            if "<<<THOUGHT_COMPLETE>>>" in content:
                logger.debug("Found THOUGHT_COMPLETE marker")
                # Find where the prompt ends and response begins
                prompt_end = content.find("<<<END_THOUGHT>>>")
                if prompt_end != -1:
                    # Extract response after the prompt
                    response_start = prompt_end + len("<<<END_THOUGHT>>>")
                    response_with_marker = content[response_start:].strip()
                    # Remove the completion marker
                    response = response_with_marker.replace("<<<THOUGHT_COMPLETE>>>", "").strip()
                else:
                    # Fallback: split on completion marker
                    response = content.split("<<<THOUGHT_COMPLETE>>>")[0].strip()
                
                logger.info("=== BRAIN RESPONSE START ===")
                logger.info(f"Response length: {len(response)} characters")
                logger.info("Full response from brain:")
                logger.info(response)
                logger.info("=== BRAIN RESPONSE END ===")
                
                # Reset brain for next use
                self.brain_file.write_text("This is your brain. Write your thoughts here to think.")
                
                return response
            
            # Log periodically to see if we're stuck
            wait_count += 1
            if wait_count % 100 == 0:
                logger.warning(f"Still waiting for brain response after {wait_count/100} seconds")
                logger.debug(f"Current brain content length: {len(content)}")
            
            # Brief pause to avoid spinning
            await asyncio.sleep(0.01)
     
    async def maintain(self):
        """Perform maintenance tasks when idle."""
        # Cleanup old memories
        expired = self.memory_manager.cleanup_expired()
        old_observations = self.memory_manager.cleanup_old_observations(max_age_seconds=1800)
        
        if expired or old_observations:
            logger.debug(f"Cleaned up {expired} expired, {old_observations} old observation memories")
        
        # Save memory snapshot periodically
        if self.cycle_count % 100 == 0:
            await self._save_memory_snapshot()
    
    async def save_memory(self):
        """Public method to save memory - calls internal snapshot method."""
        await self._save_memory_snapshot()
    
    async def _save_memory_snapshot(self):
        """Save current memory state to disk."""
        try:
            snapshot = self.memory_manager.create_snapshot()
            
            # Save to fixed filename for resume (atomic write to prevent corruption)
            memory_file = self.memory_dir / "memory_snapshot.json"
            temp_file = self.memory_dir / "memory_snapshot.tmp"
            
            # Write to temp file first
            with open(temp_file, 'w') as f:
                json.dump(snapshot, f, indent=2, cls=DateTimeEncoder)
            
            # Atomic rename (on POSIX systems, rename is atomic)
            temp_file.replace(memory_file)
            
            # Also save timestamped backup periodically
            if self.cycle_count % 100 == 0:
                backup_file = self.memory_dir / f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(backup_file, 'w') as f:
                    json.dump(snapshot, f, indent=2, cls=DateTimeEncoder)
                logger.debug(f"Saved memory backup to {backup_file.name}")
                
                # Clean old backups (keep last 5)
                backups = sorted(self.memory_dir.glob("snapshot_*.json"))
                if len(backups) > 5:
                    for old_backup in backups[:-5]:
                        old_backup.unlink()
                    
        except Exception as e:
            logger.error(f"Error saving memory snapshot: {e}")
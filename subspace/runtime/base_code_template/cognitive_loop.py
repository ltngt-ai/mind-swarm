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
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

from .boot_rom import BootROM
from .memory import (
    WorkingMemoryManager, ContentLoader, ContextBuilder, 
    MemorySelector, Priority, MemoryType,
    FileMemoryBlock, MessageMemoryBlock, TaskMemoryBlock,
    HistoryMemoryBlock, ObservationMemoryBlock, ROMMemoryBlock,
    CycleStateMemoryBlock
)
from .perception import EnvironmentScanner
from .actions import Action, ActionResult, ActionStatus, action_registry

logger = logging.getLogger("agent.cognitive")

# Define KnowledgeMemoryBlock if not available
try:
    from .memory import KnowledgeMemoryBlock
except ImportError:
    # Fallback definition
    class KnowledgeMemoryBlock(ROMMemoryBlock):
        """Knowledge memory block for library knowledge."""
        def __init__(self, topic: str, location: str, subtopic: str = "",
                     relevance_score: float = 1.0, **kwargs):
            super().__init__(location=location, **kwargs)
            self.topic = topic
            self.subtopic = subtopic
            self.relevance_score = relevance_score


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
        for knowledge_file in rom_dir.glob("*.json"):
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
            knowledge_data = json.loads(knowledge_path.read_text())
            
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
                    "content": knowledge_data["content"],
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
                self._update_cycle_state("act", current_actions=action_data)
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
                
                # Check if task is complete (finish action was executed)
                if any(a.name == 'finish' for a in actions):
                    # Clear any task tracking
                    if 'task_memory_id' in orientation:
                        task_memory = self.memory_manager.access_memory(orientation['task_memory_id'])
                        if task_memory and isinstance(task_memory, TaskMemoryBlock):
                            task_memory.status = "completed"
                    logger.info(f"Task completed for {orientation.get('task_type')} request")
                
                # Clear current task data and restart cycle
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
            self._save_memory_snapshot()
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
                    logger.info(f"Observed: {obs.description}")
        
        # Only log if there were significant changes
        if significant_count > 0:
            logger.info(f"Perceived {significant_count} significant changes in environment")
    
    async def observe(self) -> Optional[Dict[str, Any]]:
        """Check for high-priority inputs using memory system."""
        # Check for unread messages in memory
        unread_messages = self.memory_manager.get_unread_messages()
        
        if unread_messages:
            # Process oldest unread message
            oldest_msg = min(unread_messages, key=lambda m: m.timestamp)
            
            try:
                # Load full message content
                msg_content = self.content_loader.load_message_content(oldest_msg)
                
                # Parse message data
                msg_path = Path(oldest_msg.full_path)
                if msg_path.exists():
                    message = json.loads(msg_path.read_text())
                    
                    # Process the message
                    # Mark as read in memory
                    self.memory_manager.mark_message_read(oldest_msg.id)
                    
                    # Mark as processed in scanner
                    self.environment_scanner.mark_message_processed(str(msg_path))
                    
                    # Move to processed
                    processed_dir = self.inbox_dir / "processed"
                    processed_dir.mkdir(exist_ok=True)
                    msg_path.rename(processed_dir / msg_path.name)
                    
                    logger.info(f"Processing message: {oldest_msg.subject} (type: {message.get('type', 'unknown')})")
                    return message
                    
            except Exception as e:
                logger.error(f"Error processing message {oldest_msg.id}: {e}")
        
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
        
        # Get current task if any
        current_task = "None"
        task_memories = [m for m in self.memory_manager.symbolic_memory 
                        if isinstance(m, TaskMemoryBlock) and m.status == "in_progress"]
        if task_memories:
            current_task = task_memories[0].description
        
        # Get recent history
        recent_history = []
        history_memories = [m for m in self.memory_manager.symbolic_memory 
                          if isinstance(m, HistoryMemoryBlock)]
        recent_history = [f"{h.action_type}: {h.action_detail}" 
                         for h in sorted(history_memories, key=lambda x: x.timestamp)[-3:]]
        
        # Build structured thinking request for orient
        thinking_request = {
            "signature": {
                "task": "What does this mean and how should I handle it?",
                "description": "Understand the context and meaning of observations",
                "inputs": {
                    "observations": "What was observed",
                    "current_task": "Any task currently being worked on",
                    "recent_history": "Recent actions and outcomes"
                },
                "outputs": {
                    "situation_type": "What kind of situation this is",
                    "understanding": "What I understand about the situation",
                    "relevant_knowledge": "What knowledge or skills apply"
                },
                "display_field": "understanding"
            },
            "input_values": {
                "observations": f"New message received: {json.dumps(observation)}",
                "current_task": current_task,
                "recent_history": "\n".join(recent_history) if recent_history else "Just started"
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
            
            # Create task memory if we're going to process it
            if orientation.get("approach") not in ["terminating", "ignoring"]:
                task_memory = TaskMemoryBlock(
                    task_id=f"task_{self.cycle_count}",
                    description=orientation.get("content", str(observation)),
                    status="in_progress",
                    priority=Priority.HIGH
                )
                self.memory_manager.add_memory(task_memory)
                orientation["task_memory_id"] = task_memory.id
            
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
        situation = output_values.get("situation_type", "").lower()
        understanding = output_values.get("understanding", "").lower()
        
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
    
    def _classify_task(self, content: str) -> str:
        """Classify the type of task based on content."""
        content_lower = content.lower()
        
        # Check for arithmetic
        if any(op in content_lower for op in ['+', '-', '*', '/', 'plus', 'minus', 'times', 'divided']):
            return "arithmetic"
        
        # Check for question words
        if any(q in content_lower for q in ['what', 'why', 'how', 'when', 'where', 'who', '?']):
            return "question"
        
        # Check for analysis keywords
        if any(word in content_lower for word in ['analyze', 'explain', 'describe', 'compare']):
            return "analytical"
        
        # Check for memory/knowledge operations
        if any(word in content_lower for word in ['remember', 'recall', 'knowledge', 'learned']):
            return "memory_query"
        
        return "general"
    
    async def decide(self, orientation: Dict[str, Any]) -> List[Action]:
        """Decide what actions to take based on the current situation.
        
        Returns:
            List of Actions to execute in order
        """
        # Get available actions for this agent type
        agent_type = self.agent_type if hasattr(self, 'agent_type') else 'base'
        available_actions = action_registry.get_available_actions(agent_type)
        
        # No special cases - agents process all tasks the same way
        
        # Build decision thinking request with parameter details
        action_descriptions = []
        for name, cls in available_actions.items():
            action_inst = cls()
            desc = f"- {name}: {action_inst.description}"
            
            # Add parameter hints for common actions
            if name == "send_message":
                desc += " (params: to, type, content)"
            elif name == "update_memory":
                desc += " (params: memory_type, content)"
            elif name == "wait":
                desc += " (params: duration, condition)"
            elif name == "make_network_request":
                desc += " (params: url, method, headers, body)"
            
            action_descriptions.append(desc)
        
        goals = "Respond helpfully and accurately to the user's request"
        constraints = f"Token budget: {self.max_context_tokens}, Must respond via outbox"
        
        thinking_request = {
            "signature": {
                "task": "What actions should I take to complete this task?",
                "description": "Return a literal JSON array of action objects with parameters",
                "inputs": {
                    "understanding": "Understanding of the situation",
                    "available_actions": "Available actions and their descriptions",
                    "goals": "Current goals or objectives",
                    "constraints": "Any constraints or limitations",
                    "original_request": "The original user request text"
                },
                "outputs": {
                    "actions": "JSON array of action objects like [{\"action\": \"send_message\", \"params\": {\"to\": \"user\", \"content\": \"...\"}}] or [{\"action\": \"finish\", \"params\": {}}]",
                    "reasoning": "Why this sequence of actions is best"
                },
                "display_field": "reasoning",
                "examples": [
                    {
                        "input": "User asks to fetch google.com",
                        "output": "[{\"action\": \"make_network_request\", \"params\": {\"url\": \"https://google.com\"}}, {\"action\": \"wait\", \"params\": {\"duration\": 1.0}}, {\"action\": \"send_message\", \"params\": {\"to\": \"user\", \"content\": \"<will be filled after fetch>\"}}]"
                    },
                    {
                        "input": "User asks 'What is 2 + 2?'",
                        "output": "[{\"action\": \"send_message\", \"params\": {\"to\": \"user\", \"content\": \"2 + 2 equals 4\"}}, {\"action\": \"finish\", \"params\": {}}]"
                    }
                ]
            },
            "input_values": {
                "understanding": orientation.get("reasoning", "Need to process this request"),
                "available_actions": "\n".join(action_descriptions),
                "goals": goals,
                "constraints": constraints,
                "original_request": orientation.get("content", str(orientation.get("original_message", {})))
            },
            "request_id": f"decide_{int(time.time()*1000)}",
            "timestamp": datetime.now().isoformat()
        }
        
        # Use the brain to decide
        decision_json = json.dumps(thinking_request)
        response = await self._use_brain(decision_json)
        
        actions = []
        
        try:
            # Parse response
            result = json.loads(response.replace("<<<THOUGHT_COMPLETE>>>", "").strip())
            output = result.get("output_values", {})
            
            action_names = output.get("actions", "[]")
            reasoning = output.get("reasoning", "")
            
            logger.info(f"Action names: {action_names}")
            logger.info(f"Reasoning: {reasoning}")
            
            # Parse the JSON array of action objects
            try:
                if isinstance(action_names, str):
                    action_objects = json.loads(action_names)
                else:
                    action_objects = action_names
                
                # Create Action objects from the specifications
                for action_spec in action_objects:
                    if isinstance(action_spec, dict):
                        action_name = action_spec.get("action")
                        params = action_spec.get("params", {})
                    else:
                        # Fallback for simple string format
                        action_name = action_spec
                        params = {}
                    
                    action = action_registry.create_action(agent_type, action_name)
                    if action:
                        # Use provided parameters or fall back to defaults
                        if params:
                            action.with_params(**params)
                        else:
                            # Set default parameters based on context
                            self._configure_action(action, orientation)
                        actions.append(action)
                    else:
                        logger.warning(f"Unknown action: {action_name}")
                        
            except json.JSONDecodeError:
                logger.error(f"Failed to parse action names as JSON: {action_names}")
                actions = self._get_fallback_actions(orientation, available_actions)
            
        except Exception as e:
            logger.error(f"Failed to parse decide response: {e}", exc_info=True)
            # Fallback: simple action sequence
            actions = self._get_fallback_actions(orientation, available_actions)
        
        # Record decision
        history = HistoryMemoryBlock(
            action_type="decision",
            action_detail=f"Planned {len(actions)} actions",
            result=f"Actions: {[a.name for a in actions]}",
            priority=Priority.LOW
        )
        self.memory_manager.add_memory(history)
        
        return actions
    
    def _configure_action(self, action: Action, orientation: Dict[str, Any]):
        """Configure action parameters based on context."""
        if action.name == "send_message":
            # Determine recipient
            from_agent = orientation.get("from", "")
            action.with_params(
                to=from_agent if from_agent else "user",
                type="RESPONSE",
                content=""  # Will be filled based on previous action results
            )
        elif action.name == "update_memory":
            action.with_params(
                memory_type="task_result",
                content=""  # Will be filled based on task results
            )
        elif action.name == "wait":
            action.with_params(
                duration=1.0,
                condition=None
            )
        # finish action needs no parameters
    
    def _get_fallback_actions(self, orientation: Dict[str, Any], 
                             available_actions: Dict[str, type[Action]]) -> List[Action]:
        """Get fallback actions when parsing fails."""
        agent_type = self.agent_type if hasattr(self, 'agent_type') else 'base'
        actions = []
        
        # Default: send a response if it's a message, otherwise just finish
        if orientation.get('type') == 'message' or orientation.get('from'):
            send_action = action_registry.create_action(agent_type, 'send_message')
            if send_action:
                from_agent = orientation.get("from", "")
                send_action.with_params(
                    to=from_agent if from_agent else "user",
                    type="RESPONSE",
                    content="I understand your request but I'm not sure how to proceed. Let me continue thinking..."
                )
                actions.append(send_action)
        
        # Finish the task
        finish_action = action_registry.create_action(agent_type, 'finish')
        if finish_action:
            actions.append(finish_action)
        
        return actions
    
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
                
                # Store result in memory
                history = HistoryMemoryBlock(
                    action_type=f"action_{action.name}",
                    action_detail=action.description,
                    result=f"Status: {result.status.value}, Result: {result.result}",
                    priority=Priority.MEDIUM
                )
                self.memory_manager.add_memory(history)
                
                # Update context with results for next action
                context[f"action_{i}_result"] = result
                
                # Check if action failed
                if result.status == ActionStatus.FAILED:
                    logger.error(f"Action {action.name} failed: {result.error}")
                    # Decide whether to continue or abort
                    if action.priority == Priority.HIGH:
                        logger.warning("High priority action failed, aborting sequence")
                        break
                
                # Check if task is marked complete
                if context.get("task_complete", False):
                    logger.info("Task marked complete, ending action sequence")
                    break
                    
            except Exception as e:
                logger.error(f"Error executing action {action.name}: {e}", exc_info=True)
                
                # Record error
                history = HistoryMemoryBlock(
                    action_type=f"action_{action.name}_error",
                    action_detail=f"Failed to execute {action.name}",
                    result=str(e),
                    priority=Priority.HIGH
                )
                self.memory_manager.add_memory(history)
                
                # Continue with next action unless critical
                if action.priority == Priority.HIGH:
                    break
        
        logger.info(f"Completed {len(actions)} actions")
    
    async def _think_with_memory(self, task: str, decision: Dict[str, Any], 
                                strategy: str = "balanced") -> str:
        """Think about a task using appropriate DSPy signature."""
        task_type = decision.get("task_type", "general")
        
        # Select relevant memories
        all_memories = self.memory_manager.symbolic_memory
        selected_memories = self.memory_selector.select_memories(
            all_memories,
            max_tokens=self.max_context_tokens - 2000,
            current_task=task,
            selection_strategy=strategy
        )
        
        # Update access patterns
        self.memory_selector.update_access_patterns(selected_memories)
        
        # Build memory context
        memory_context = self.context_builder.build_context(
            selected_memories,
            format_type="structured"
        )
        
        # Choose appropriate signature based on task type
        if "arithmetic" in task_type.lower() or "math" in task.lower():
            # Use arithmetic signature
            thinking_request = {
                "signature": {
                    "task": "Solve this arithmetic problem step by step",
                    "description": "Perform mathematical calculations with clear steps",
                    "inputs": {
                        "problem": "The math problem to solve",
                        "context": "Any context"
                    },
                    "outputs": {
                        "steps": "Step by step solution",
                        "answer": "The final answer",
                        "verification": "How to verify"
                    },
                    "display_field": "answer"
                },
                "input_values": {
                    "problem": task,
                    "context": f"User requested this calculation. Memory context:\n{memory_context}"
                },
                "request_id": f"arithmetic_{int(time.time()*1000)}",
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Use question signature for general tasks
            thinking_request = {
                "signature": {
                    "task": "Answer this question based on available knowledge",
                    "description": "Use available context and knowledge to provide a thoughtful answer",
                    "inputs": {
                        "question": "The question to answer",
                        "context": "Context about the question",
                        "relevant_knowledge": "Any relevant facts"
                    },
                    "outputs": {
                        "answer": "The answer to the question",
                        "confidence": "Confidence level (high/medium/low)",
                        "reasoning": "The reasoning process"
                    },
                    "display_field": "answer"
                },
                "input_values": {
                    "question": task,
                    "context": f"Task type: {task_type}, Approach: {decision.get('approach', 'thinking')}",
                    "relevant_knowledge": memory_context
                },
                "request_id": f"question_{int(time.time()*1000)}",
                "timestamp": datetime.now().isoformat()
            }
        
        # Log what we're doing
        stats = self.memory_manager.get_memory_stats()
        logger.info(
            f"Thinking about {task_type} task with {len(selected_memories)} memories "
            f"(total: {stats['total_memories']}, strategy: {strategy})"
        )
        
        # Use brain
        request_json = json.dumps(thinking_request)
        response = await self._use_brain(request_json)
        
        try:
            # Parse structured response
            result = json.loads(response.replace("<<<THOUGHT_COMPLETE>>>", "").strip())
            output = result.get("output_values", {})
            
            if "answer" in output:
                # For question/arithmetic signatures
                answer = output.get("answer", "I couldn't determine an answer")
                if "steps" in output:
                    # Arithmetic problem - include steps
                    return f"{output.get('steps', '')}\n\nAnswer: {answer}"
                else:
                    # General question
                    reasoning = output.get("reasoning", "")
                    confidence = output.get("confidence", "medium")
                    return f"{answer}\n\n(Confidence: {confidence}. {reasoning})"
            else:
                # Unexpected format, return what we got
                return str(output)
                
        except Exception as e:
            logger.error(f"Failed to parse thinking response: {e}")
            return response  # Return raw response as fallback
    
    async def _use_brain(self, prompt: str) -> str:
        """Use the brain file interface to think."""
        # Write prompt with end marker
        self.brain_file.write_text(f"{prompt}\n<<<END_THOUGHT>>>")
        
        # Wait for response with timeout
        start_time = asyncio.get_event_loop().time()
        timeout = 300  # 5 minute timeout for brain operations
        
        while True:
            # Check for shutdown file
            shutdown_file = self.home / "shutdown"
            if shutdown_file.exists():
                logger.info("Shutdown detected while waiting for brain response")
                # Reset brain for next use
                self.brain_file.write_text("This is your brain. Write your thoughts here to think.")
                return '{"error": "Shutdown requested"}'
            
            content = self.brain_file.read_text()
            if "<<<THOUGHT_COMPLETE>>>" in content:
                # Extract response
                response = content.split("<<<THOUGHT_COMPLETE>>>")[0].strip()
                
                # Reset brain for next use
                self.brain_file.write_text("This is your brain. Write your thoughts here to think.")
                
                return response
            
            # Check for timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.error(f"Brain operation timed out after {timeout}s")
                # Reset brain for next use
                self.brain_file.write_text("This is your brain. Write your thoughts here to think.")
                return '{"error": "Brain operation timed out"}'
            
            # Brief pause to avoid spinning
            await asyncio.sleep(0.01)
    
    async def _send_response(self, original_msg: Dict[str, Any], response: str):
        """Send a response message."""
        response_msg = {
            "from": self.agent_id,
            "to": original_msg.get("from", "subspace"),
            "in_reply_to": original_msg.get("id"),
            "type": "RESPONSE",
            "content": response,
            "timestamp": datetime.now().isoformat()
        }
        
        # Generate unique message ID
        msg_id = f"{self.agent_id}_{int(datetime.now().timestamp() * 1000)}"
        msg_file = self.outbox_dir / f"{msg_id}.msg"
        
        # Write message
        msg_file.write_text(json.dumps(response_msg, indent=2))
        
        # Log response details
        logger.info(f"Sent response to {response_msg['to']}: {response}")
    
    async def maintain(self):
        """Perform maintenance tasks when idle."""
        # Cleanup old memories
        expired = self.memory_manager.cleanup_expired()
        old_history = self.memory_manager.cleanup_old_history(max_age_seconds=1800)
        
        if expired or old_history:
            logger.debug(f"Cleaned up {expired} expired, {old_history} old history memories")
        
        # Save memory snapshot periodically
        if self.cycle_count % 100 == 0:
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
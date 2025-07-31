"""Working Memory (RAM) - The agent's active thinking space.

This is like RAM in a computer - it holds:
- Current task/question being worked on
- Recent thoughts and observations
- Intermediate results and calculations
- Active context from recent interactions
- Reasoning chains in progress
"""

from typing import Dict, List, Any, Optional
from collections import deque
from datetime import datetime
import json


class WorkingMemory:
    """The agent's working memory - temporary storage for active thinking."""
    
    def __init__(self, capacity: int = 7):
        """Initialize working memory with limited capacity.
        
        Based on cognitive science: 7±2 items in working memory.
        
        Args:
            capacity: Maximum number of items to keep active
        """
        self.capacity = capacity
        
        # Current focus
        self.current_task: Optional[str] = None
        self.task_source: Optional[str] = None  # Who gave us this task
        self.task_type: Optional[str] = None    # Type of task (arithmetic, question, etc.)
        
        # Recent thoughts (like a circular buffer)
        self.thoughts = deque(maxlen=capacity)
        
        # Current reasoning chain
        self.reasoning_chain: List[Dict[str, str]] = []
        
        # Scratch pad for calculations and intermediate results
        self.scratch_pad: Dict[str, Any] = {}
        
        # Context stack - remember recent contexts
        self.context_stack = deque(maxlen=3)
        
        # Active facts loaded from long-term memory
        self.active_facts: List[str] = []
        
        # Observations from the current cycle
        self.observations: List[str] = []
    
    def set_task(self, task: str, source: str = "unknown", task_type: str = "general"):
        """Set the current task we're working on."""
        self.current_task = task
        self.task_source = source
        self.task_type = task_type
        self.reasoning_chain = []
        self.scratch_pad.clear()
        self.observations = []
        
        # Add to thoughts
        self.add_thought(f"New task: {task[:50]}...")
    
    def add_thought(self, thought: str):
        """Add a thought to working memory."""
        self.thoughts.append({
            "content": thought,
            "timestamp": datetime.now().isoformat(),
            "task": self.current_task
        })
    
    def add_reasoning_step(self, step: str, result: Optional[str] = None):
        """Add a step to the reasoning chain."""
        entry = {
            "step": step,
            "timestamp": datetime.now().isoformat()
        }
        if result:
            entry["result"] = result
            
        self.reasoning_chain.append(entry)
        self.add_thought(f"Reasoning: {step}")
    
    def store_intermediate(self, key: str, value: Any):
        """Store an intermediate result."""
        self.scratch_pad[key] = value
        self.add_thought(f"Stored {key}: {value}")
    
    def get_intermediate(self, key: str, default: Any = None) -> Any:
        """Retrieve an intermediate result."""
        return self.scratch_pad.get(key, default)
    
    def add_observation(self, observation: str):
        """Add an observation from the current cycle."""
        self.observations.append(observation)
        if len(self.observations) > self.capacity:
            self.observations.pop(0)
    
    def push_context(self, context: Dict[str, Any]):
        """Save a context for future reference."""
        self.context_stack.append({
            "context": context,
            "timestamp": datetime.now().isoformat()
        })
    
    def load_facts(self, facts: List[str]):
        """Load facts from long-term memory into working memory."""
        # Only keep what fits in our capacity
        self.active_facts = facts[:self.capacity]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of working memory contents."""
        return {
            "current_task": self.current_task,
            "task_type": self.task_type,
            "thought_count": len(self.thoughts),
            "reasoning_steps": len(self.reasoning_chain),
            "scratch_items": len(self.scratch_pad),
            "observations": len(self.observations)
        }
    
    def format_for_thinking(self) -> str:
        """Format working memory for inclusion in thinking prompt."""
        sections = []
        
        # Current task
        if self.current_task:
            sections.append("=== CURRENT TASK ===")
            sections.append(f"Task: {self.current_task}")
            sections.append(f"Type: {self.task_type}")
            sections.append(f"From: {self.task_source}")
            sections.append("")
        
        # Recent observations
        if self.observations:
            sections.append("=== OBSERVATIONS ===")
            for obs in self.observations[-3:]:  # Last 3
                sections.append(f"- {obs}")
            sections.append("")
        
        # Reasoning chain
        if self.reasoning_chain:
            sections.append("=== REASONING CHAIN ===")
            for i, step in enumerate(self.reasoning_chain, 1):
                sections.append(f"{i}. {step['step']}")
                if "result" in step:
                    sections.append(f"   → {step['result']}")
            sections.append("")
        
        # Scratch pad
        if self.scratch_pad:
            sections.append("=== WORKING DATA ===")
            for key, value in self.scratch_pad.items():
                sections.append(f"- {key}: {value}")
            sections.append("")
        
        # Recent thoughts
        if self.thoughts:
            sections.append("=== RECENT THOUGHTS ===")
            for thought in list(self.thoughts)[-3:]:  # Last 3
                sections.append(f"- {thought['content']}")
            sections.append("")
        
        return "\n".join(sections)
    
    def save_state(self) -> str:
        """Save working memory state to JSON."""
        state = {
            "current_task": self.current_task,
            "task_source": self.task_source,
            "task_type": self.task_type,
            "thoughts": list(self.thoughts),
            "reasoning_chain": self.reasoning_chain,
            "scratch_pad": self.scratch_pad,
            "observations": self.observations,
            "active_facts": self.active_facts
        }
        return json.dumps(state, indent=2)
    
    def load_state(self, state_json: str):
        """Load working memory state from JSON."""
        state = json.loads(state_json)
        
        self.current_task = state.get("current_task")
        self.task_source = state.get("task_source", "unknown")
        self.task_type = state.get("task_type", "general")
        self.thoughts = deque(state.get("thoughts", []), maxlen=self.capacity)
        self.reasoning_chain = state.get("reasoning_chain", [])
        self.scratch_pad = state.get("scratch_pad", {})
        self.observations = state.get("observations", [])
        self.active_facts = state.get("active_facts", [])
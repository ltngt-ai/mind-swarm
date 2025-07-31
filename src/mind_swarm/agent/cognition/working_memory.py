"""Working Memory - The agent's RAM for current thoughts and context.

This holds:
- Current task/question
- Recent thoughts and reasoning steps
- Temporary results
- Active context
"""

from typing import Dict, List, Any, Optional
from collections import deque
from datetime import datetime
import json


class WorkingMemory:
    """The agent's working memory (RAM)."""
    
    def __init__(self, capacity: int = 7):
        """Initialize working memory with limited capacity.
        
        Args:
            capacity: Number of items to keep in working memory (default 7±2 rule)
        """
        self.capacity = capacity
        
        # Current focus
        self.current_task: Optional[str] = None
        self.current_question: Optional[str] = None
        
        # Recent thoughts (limited capacity)
        self.thoughts = deque(maxlen=capacity)
        
        # Temporary storage for problem solving
        self.scratch_pad: Dict[str, Any] = {}
        
        # Context from recent interactions
        self.context_stack = deque(maxlen=3)  # Keep last 3 contexts
        
        # Working facts extracted from larger memory
        self.active_facts: List[str] = []
        
        # Current reasoning chain
        self.reasoning_steps: List[str] = []
        
    def set_current_task(self, task: str):
        """Set the current task/question being worked on."""
        self.current_task = task
        self.current_question = task  # For now, treat them the same
        self.reasoning_steps = []  # Clear previous reasoning
        
    def add_thought(self, thought: str):
        """Add a thought to working memory."""
        self.thoughts.append({
            "thought": thought,
            "timestamp": datetime.now().isoformat()
        })
        
    def add_reasoning_step(self, step: str):
        """Add a step to the current reasoning chain."""
        self.reasoning_steps.append(step)
        self.add_thought(f"Reasoning: {step}")
        
    def store_intermediate(self, key: str, value: Any):
        """Store an intermediate result in scratch pad."""
        self.scratch_pad[key] = value
        
    def get_intermediate(self, key: str) -> Any:
        """Retrieve an intermediate result."""
        return self.scratch_pad.get(key)
        
    def push_context(self, context: Dict[str, Any]):
        """Push a new context onto the context stack."""
        self.context_stack.append(context)
        
    def load_facts(self, facts: List[str]):
        """Load relevant facts into working memory."""
        # Only keep most relevant facts that fit in capacity
        self.active_facts = facts[:self.capacity]
        
    def clear_scratch(self):
        """Clear the scratch pad."""
        self.scratch_pad.clear()
        
    def format_for_thinking(self) -> str:
        """Format working memory contents for thinking."""
        parts = []
        
        # Current task
        if self.current_task:
            parts.append(f"# Current Task\n{self.current_task}\n")
        
        # Recent thoughts
        if self.thoughts:
            parts.append("# Recent Thoughts")
            for thought_data in list(self.thoughts)[-3:]:  # Last 3 thoughts
                parts.append(f"- {thought_data['thought']}")
            parts.append("")
        
        # Reasoning steps
        if self.reasoning_steps:
            parts.append("# Reasoning Steps")
            for i, step in enumerate(self.reasoning_steps, 1):
                parts.append(f"{i}. {step}")
            parts.append("")
        
        # Active facts
        if self.active_facts:
            parts.append("# Relevant Facts")
            for fact in self.active_facts:
                parts.append(f"- {fact}")
            parts.append("")
        
        # Scratch pad
        if self.scratch_pad:
            parts.append("# Working Data")
            for key, value in self.scratch_pad.items():
                parts.append(f"- {key}: {value}")
            parts.append("")
        
        return "\n".join(parts)
    
    def to_json(self) -> str:
        """Serialize working memory to JSON for persistence."""
        return json.dumps({
            "current_task": self.current_task,
            "thoughts": list(self.thoughts),
            "scratch_pad": self.scratch_pad,
            "context_stack": list(self.context_stack),
            "active_facts": self.active_facts,
            "reasoning_steps": self.reasoning_steps
        }, indent=2)
    
    def from_json(self, json_str: str):
        """Load working memory from JSON."""
        data = json.loads(json_str)
        self.current_task = data.get("current_task")
        self.thoughts = deque(data.get("thoughts", []), maxlen=self.capacity)
        self.scratch_pad = data.get("scratch_pad", {})
        self.context_stack = deque(data.get("context_stack", []), maxlen=3)
        self.active_facts = data.get("active_facts", [])
        self.reasoning_steps = data.get("reasoning_steps", [])
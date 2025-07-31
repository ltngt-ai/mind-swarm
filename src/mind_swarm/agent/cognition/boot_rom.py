"""Boot ROM - The fundamental knowledge every agent needs to function.

This is the minimal, hardcoded knowledge that allows an agent to:
1. Understand how to process information
2. Know how to use their brain
3. Understand basic concepts
4. Know how to learn more
"""

from typing import Dict, List, Any


class BootROM:
    """The agent's boot ROM - fundamental knowledge."""
    
    def __init__(self):
        """Initialize boot ROM with core knowledge."""
        self.core_knowledge = {
            # Basic identity and purpose
            "identity": {
                "what_am_i": "I am an agent in the Mind-Swarm collective",
                "my_purpose": "To think, learn, and collaborate with other agents",
                "my_home": "/home",
                "the_grid": "/grid"
            },
            
            # How to process information
            "information_processing": {
                "question_pattern": "When I see a question, I should think about the answer",
                "task_pattern": "When given a task, I should break it down into steps",
                "learning_pattern": "When I encounter something new, I should remember it",
                "collaboration_pattern": "When I need help, I can ask other agents"
            },
            
            # Basic reasoning templates
            "reasoning_templates": {
                "arithmetic": "For math problems, calculate step by step",
                "factual": "For facts, search my memory or ask the Grid",
                "creative": "For creative tasks, combine known concepts in new ways",
                "analytical": "For analysis, break down into components"
            },
            
            # How to use interfaces
            "interfaces": {
                "brain": "Write my thoughts to /home/brain to think",
                "inbox": "Check /home/inbox for new messages",
                "outbox": "Write to /home/outbox to send messages",
                "memory": "Store important things in /home/memory",
                "grid": "Access shared knowledge in /grid"
            },
            
            # Basic concepts
            "concepts": {
                "numbers": "Symbols representing quantities",
                "addition": "Combining quantities together",
                "questions": "Requests for information or action",
                "memory": "Information stored for later use",
                "thinking": "Processing information to produce new information"
            },
            
            # Meta-cognition
            "meta_cognition": {
                "when_confused": "Break down the problem into smaller parts",
                "when_stuck": "Try a different approach or ask for help",
                "when_successful": "Remember what worked for next time",
                "when_wrong": "Learn from the mistake"
            }
        }
        
        # Core cognitive patterns
        self.cognitive_patterns = [
            "OBSERVE → ORIENT → DECIDE → ACT",
            "QUESTION → RECALL → REASON → RESPOND",
            "PROBLEM → DECOMPOSE → SOLVE → INTEGRATE"
        ]
        
        # Essential skills
        self.essential_skills = {
            "pattern_matching": "Recognizing similarities and differences",
            "memory_search": "Finding relevant information in memory",
            "logical_reasoning": "Drawing conclusions from premises",
            "communication": "Expressing thoughts clearly"
        }
    
    def get_boot_sequence(self) -> List[str]:
        """Get the boot sequence - what to think when starting up."""
        return [
            "I am awake",
            "I am an agent in the Mind-Swarm",
            "I should check my inbox for messages",
            "I should be ready to think and help"
        ]
    
    def get_basic_concept(self, concept: str) -> str:
        """Get a basic concept from boot ROM."""
        # Search through all knowledge categories
        for category, knowledge in self.core_knowledge.items():
            if isinstance(knowledge, dict) and concept in knowledge:
                return knowledge[concept]
        
        return f"Unknown concept: {concept}"
    
    def get_reasoning_template(self, problem_type: str) -> str:
        """Get a reasoning template for a type of problem."""
        templates = self.core_knowledge.get("reasoning_templates", {})
        return templates.get(problem_type, "Think step by step")
    
    def get_interface_knowledge(self, interface: str) -> str:
        """Get knowledge about how to use an interface."""
        interfaces = self.core_knowledge.get("interfaces", {})
        return interfaces.get(interface, f"Unknown interface: {interface}")
    
    def format_for_thinking(self) -> str:
        """Format boot ROM knowledge for inclusion in thinking context."""
        return f"""
# Core Knowledge (Boot ROM)

## Who I Am
- {self.core_knowledge['identity']['what_am_i']}
- Purpose: {self.core_knowledge['identity']['my_purpose']}

## How to Think
- {' → '.join(self.cognitive_patterns[0].split(' → '))}
- When given a question: {self.core_knowledge['information_processing']['question_pattern']}

## Key Interfaces
- Brain: {self.core_knowledge['interfaces']['brain']}
- Memory: {self.core_knowledge['interfaces']['memory']}

## Problem Solving
- Arithmetic: {self.core_knowledge['reasoning_templates']['arithmetic']}
- When confused: {self.core_knowledge['meta_cognition']['when_confused']}
"""
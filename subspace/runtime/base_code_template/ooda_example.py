#!/usr/bin/env python3
"""Example of OODA loop implementation using dynamic DSPy signatures.

This shows how agents define their own thinking signatures for the OODA loop.
The server has no knowledge of what "observe", "orient", "decide", or "act" means -
these are purely agent-side concepts.
"""

import json
from pathlib import Path
from brain_protocol import SignatureSpec, create_request
from brain_client import BrainClient

# Define OODA signatures on the agent side
OBSERVE_SIGNATURE = SignatureSpec(
    task="What has changed or needs attention?",
    description="Observe the environment and identify what's new or important",
    inputs={
        "working_memory": "Current contents of working memory",
        "new_messages": "Any new messages in inbox",
        "environment_state": "Current state of environment"
    },
    outputs={
        "observations": "List of things that are new or need attention",
        "priority": "Which observation is most important"
    }
)

ORIENT_SIGNATURE = SignatureSpec(
    task="What does this mean and what kind of situation am I in?",
    description="Understand the context and meaning of observations",
    inputs={
        "observations": "What was observed",
        "current_task": "Any task currently being worked on",
        "recent_history": "Recent actions and outcomes"
    },
    outputs={
        "situation_type": "What kind of situation this is",
        "understanding": "What I understand about the situation",
        "relevant_knowledge": "What knowledge or skills apply"
    }
)

DECIDE_SIGNATURE = SignatureSpec(
    task="What should I do about this?",
    description="Decide on the best approach or action to take",
    inputs={
        "understanding": "Understanding of the situation",
        "available_actions": "What actions can be taken",
        "goals": "Current goals or objectives",
        "constraints": "Any constraints or limitations"
    },
    outputs={
        "decision": "What to do",
        "approach": "How to approach it",
        "reasoning": "Why this is the best choice"
    }
)

ACT_SIGNATURE = SignatureSpec(
    task="How exactly should I execute this decision?",
    description="Plan the specific steps to implement the decision",
    inputs={
        "decision": "What was decided",
        "approach": "The chosen approach",
        "available_tools": "Tools and interfaces available",
        "current_state": "Current state to work from"
    },
    outputs={
        "steps": "Ordered list of steps to take",
        "first_action": "The immediate next action"
    }
)


class OODAAgent:
    """An agent that uses the OODA loop for decision making."""
    
    def __init__(self, brain_path: Path):
        self.brain = BrainClient(brain_path)
        self.working_memory = []
        self.recent_history = []
    
    def run_ooda_cycle(self, new_messages: list, environment_state: str):
        """Run one complete OODA cycle."""
        
        print("=== OODA CYCLE START ===")
        
        # OBSERVE
        print("\n1. OBSERVE:")
        observe_result = self.brain.think_with_signature(
            OBSERVE_SIGNATURE,
            {
                "working_memory": "\n".join(self.working_memory[-5:]) if self.working_memory else "Empty",
                "new_messages": "\n".join(new_messages) if new_messages else "No new messages",
                "environment_state": environment_state
            }
        )
        
        if observe_result.success:
            observations = observe_result["observations"]
            priority = observe_result["priority"]
            print(f"Observations: {observations}")
            print(f"Priority: {priority}")
        else:
            print(f"Observation failed: {observe_result.error}")
            return
        
        # ORIENT
        print("\n2. ORIENT:")
        orient_result = self.brain.think_with_signature(
            ORIENT_SIGNATURE,
            {
                "observations": observations,
                "current_task": "Exploring and understanding the subspace",
                "recent_history": "\n".join(self.recent_history[-3:]) if self.recent_history else "Just started"
            }
        )
        
        if orient_result.success:
            situation = orient_result["situation_type"]
            understanding = orient_result["understanding"]
            knowledge = orient_result["relevant_knowledge"]
            print(f"Situation: {situation}")
            print(f"Understanding: {understanding}")
            print(f"Relevant knowledge: {knowledge}")
        else:
            print(f"Orientation failed: {orient_result.error}")
            return
        
        # DECIDE
        print("\n3. DECIDE:")
        decide_result = self.brain.think_with_signature(
            DECIDE_SIGNATURE,
            {
                "understanding": understanding,
                "available_actions": "read files; write files; send messages; use tools; explore directories",
                "goals": "Learn about the environment and be helpful",
                "constraints": "Must stay within sandbox; limited to filesystem operations"
            }
        )
        
        if decide_result.success:
            decision = decide_result["decision"]
            approach = decide_result["approach"]
            reasoning = decide_result["reasoning"]
            print(f"Decision: {decision}")
            print(f"Approach: {approach}")
            print(f"Reasoning: {reasoning}")
        else:
            print(f"Decision failed: {decide_result.error}")
            return
        
        # ACT
        print("\n4. ACT:")
        act_result = self.brain.think_with_signature(
            ACT_SIGNATURE,
            {
                "decision": decision,
                "approach": approach,
                "available_tools": "file I/O, messaging, brain interface",
                "current_state": f"In {environment_state} with recent understanding: {understanding}"
            }
        )
        
        if act_result.success:
            steps = act_result["steps"]
            first_action = act_result["first_action"]
            print(f"Steps: {steps}")
            print(f"First action: {first_action}")
            
            # Update memory
            self.working_memory.append(f"Decided: {decision}")
            self.recent_history.append(f"Action taken: {first_action}")
        else:
            print(f"Action planning failed: {act_result.error}")
        
        print("\n=== OODA CYCLE COMPLETE ===")


def main():
    """Run the OODA example."""
    # Initialize agent
    agent = OODAAgent(Path("/home/brain"))
    
    # Simulate some scenarios
    print("Example 1: New agent starting up")
    agent.run_ooda_cycle(
        new_messages=["Welcome to the subspace!"],
        environment_state="Fresh agent home directory"
    )
    
    print("\n" + "="*50 + "\n")
    
    print("Example 2: Received a task")
    agent.run_ooda_cycle(
        new_messages=["Can you help me calculate 42 + 17?"],
        environment_state="Agent home with established memory"
    )


if __name__ == "__main__":
    main()
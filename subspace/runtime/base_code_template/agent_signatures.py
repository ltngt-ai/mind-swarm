"""Agent-side thinking signatures.

This file contains predefined thinking signatures that agents can use.
These are purely agent-side - the server has no knowledge of these specific patterns.
Agents can use these, modify them, or create entirely new ones.
"""

from typing import Dict, Optional
from brain_protocol import SignatureSpec


# OODA Loop signatures
def observe_signature() -> SignatureSpec:
    """Create an observation signature for the OODA loop."""
    return SignatureSpec(
        task="What has changed or needs attention?",
        description="Observe the environment and identify what's new or important",
        inputs={
            "working_memory": "Current contents of working memory",
            "new_messages": "Any new messages or information",
            "environment_state": "Current state of the environment"
        },
        outputs={
            "observations": "List of things that are new or need attention",
            "priority": "Which observation is most important",
            "urgency": "How urgent is the most important observation"
        }
    )


def orient_signature() -> SignatureSpec:
    """Create an orientation signature for the OODA loop."""
    return SignatureSpec(
        task="What does this mean and what kind of situation am I in?",
        description="Understand the context and meaning of observations",
        inputs={
            "observations": "What was observed",
            "current_task": "Any task currently being worked on",
            "recent_history": "Recent actions and their outcomes"
        },
        outputs={
            "situation_type": "What kind of situation this is",
            "understanding": "What I understand about the situation",
            "relevant_knowledge": "What knowledge or skills apply here"
        }
    )


def decide_signature() -> SignatureSpec:
    """Create a decision signature for the OODA loop."""
    return SignatureSpec(
        task="What should I do about this?",
        description="Decide on the best approach or action to take",
        inputs={
            "understanding": "Understanding of the current situation",
            "available_actions": "What actions can be taken",
            "goals": "Current goals or objectives",
            "constraints": "Any constraints or limitations"
        },
        outputs={
            "decision": "What should be done",
            "approach": "How to approach it",
            "reasoning": "Why this is the best choice"
        }
    )


def act_signature() -> SignatureSpec:
    """Create an action planning signature for the OODA loop."""
    return SignatureSpec(
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
            "first_action": "The immediate next action",
            "success_criteria": "How to know if it worked"
        }
    )


# Problem-solving signatures
def arithmetic_signature() -> SignatureSpec:
    """Create a signature for solving arithmetic problems."""
    return SignatureSpec(
        task="Solve this arithmetic problem step by step",
        description="Perform mathematical calculations with clear steps",
        inputs={
            "problem": "The math problem to solve",
            "context": "Any context about the problem"
        },
        outputs={
            "steps": "Step by step solution",
            "answer": "The final answer",
            "verification": "How to verify the answer is correct"
        }
    )


def question_answer_signature() -> SignatureSpec:
    """Create a signature for answering questions."""
    return SignatureSpec(
        task="Answer this question based on available knowledge",
        description="Provide a thoughtful answer to a question",
        inputs={
            "question": "The question to answer",
            "context": "Context about the question",
            "relevant_knowledge": "Any relevant facts or information"
        },
        outputs={
            "answer": "The answer to the question",
            "confidence": "How confident in the answer",
            "reasoning": "The reasoning behind the answer"
        }
    )


# Reflection signature
def reflection_signature() -> SignatureSpec:
    """Create a signature for reflecting on actions and outcomes."""
    return SignatureSpec(
        task="What happened and what did I learn?",
        description="Reflect on actions taken and results achieved",
        inputs={
            "action_taken": "What action was performed",
            "expected_outcome": "What was expected to happen",
            "actual_outcome": "What actually happened",
            "surprises": "Anything unexpected"
        },
        outputs={
            "assessment": "How well did it go",
            "lessons": "What was learned",
            "next_time": "What to do differently next time"
        }
    )


# Agent-specific signatures
def message_analysis_signature() -> SignatureSpec:
    """Create a signature for analyzing incoming messages."""
    return SignatureSpec(
        task="Analyze this message and determine appropriate response",
        description="Understand message intent and plan response",
        inputs={
            "message": "The message content",
            "sender": "Who sent it",
            "context": "Any relevant context",
            "my_state": "My current state/activity"
        },
        outputs={
            "message_type": "Type of message (question, command, info, etc)",
            "intent": "What the sender wants",
            "response_needed": "Whether I should respond",
            "suggested_response": "What to say if responding",
            "action_needed": "Any actions I should take"
        }
    )


def exploration_strategy_signature() -> SignatureSpec:
    """Create a signature for planning exploration strategies."""
    return SignatureSpec(
        task="Plan how to explore and understand this new environment",
        description="Develop a strategy for exploring unknown territory",
        inputs={
            "visible_areas": "What I can currently see or access",
            "known_capabilities": "What I know I can do",
            "exploration_goal": "What I'm trying to discover or achieve",
            "time_constraints": "Any time limits or urgency"
        },
        outputs={
            "strategy": "Overall exploration strategy",
            "priorities": "What to explore first and why",
            "risks": "Potential risks to watch for",
            "success_indicators": "How to know exploration is successful"
        }
    )


def collaboration_planning_signature() -> SignatureSpec:
    """Create a signature for planning collaboration with other agents."""
    return SignatureSpec(
        task="Plan how to collaborate effectively with other agents",
        description="Develop strategies for working with others",
        inputs={
            "other_agents": "Known agents and their capabilities",
            "shared_goal": "What we're trying to achieve together",
            "my_strengths": "What I can contribute",
            "coordination_method": "How we can communicate/coordinate"
        },
        outputs={
            "collaboration_approach": "How to work together",
            "my_role": "What I should focus on",
            "communication_plan": "How and when to communicate",
            "conflict_resolution": "How to handle disagreements"
        }
    )
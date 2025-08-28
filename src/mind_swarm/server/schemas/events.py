"""Typed WebSocket event schemas for the Mind-Swarm server.

These Pydantic models define the shapes of messages sent over the `/ws`
WebSocket endpoint. They use a uniform envelope with:

- type: literal event name
- data: typed payload
- timestamp: ISO timestamp string
"""

from __future__ import annotations

from typing import Dict, Any, Optional, Literal
from datetime import datetime

from pydantic import BaseModel, Field


class EventBase(BaseModel):
    """Base event envelope."""

    type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# Individual event types -----------------------------------------------------


class AgentStateChanged(EventBase):
    type: Literal["agent_state_changed"] = "agent_state_changed"
    data: Dict[str, Any]


class AgentThinking(EventBase):
    type: Literal["agent_thinking"] = "agent_thinking"
    data: Dict[str, Any]


class MessageSent(EventBase):
    type: Literal["message_sent"] = "message_sent"
    data: Dict[str, Any]


class FileActivity(EventBase):
    type: Literal["file_activity"] = "file_activity"
    data: Dict[str, Any]


class SystemMetrics(EventBase):
    type: Literal["system_metrics"] = "system_metrics"
    data: Dict[str, Any]


class CycleStarted(EventBase):
    type: Literal["cycle_started"] = "cycle_started"
    data: Dict[str, Any]


class CycleCompleted(EventBase):
    type: Literal["cycle_completed"] = "cycle_completed"
    data: Dict[str, Any]


class StageStarted(EventBase):
    type: Literal["stage_started"] = "stage_started"
    data: Dict[str, Any]


class StageCompleted(EventBase):
    type: Literal["stage_completed"] = "stage_completed"
    data: Dict[str, Any]


class MemoryChanged(EventBase):
    type: Literal["memory_changed"] = "memory_changed"
    data: Dict[str, Any]


class MessageActivity(EventBase):
    type: Literal["message_activity"] = "message_activity"
    data: Dict[str, Any]


class BrainThinking(EventBase):
    type: Literal["brain_thinking"] = "brain_thinking"
    data: Dict[str, Any]


class FileOperation(EventBase):
    type: Literal["file_operation"] = "file_operation"
    data: Dict[str, Any]


class TokenUsage(EventBase):
    type: Literal["token_usage"] = "token_usage"
    data: Dict[str, Any]


# Utility factory helpers ----------------------------------------------------


def make_event(event_type: str, data: Dict[str, Any]) -> EventBase:
    """Factory that returns a typed event model when known, else generic envelope.

    Keeps backward compatibility while encouraging typed events.
    """
    mapping = {
        "agent_state_changed": AgentStateChanged,
        "agent_thinking": AgentThinking,
        "message_sent": MessageSent,
        "file_activity": FileActivity,
        "system_metrics": SystemMetrics,
        "cycle_started": CycleStarted,
        "cycle_completed": CycleCompleted,
        "stage_started": StageStarted,
        "stage_completed": StageCompleted,
        "memory_changed": MemoryChanged,
        "message_activity": MessageActivity,
        "brain_thinking": BrainThinking,
        "file_operation": FileOperation,
        "token_usage": TokenUsage,
    }
    model = mapping.get(event_type)
    if model:
        return model(data=data)
    return EventBase(type=event_type, data=data)


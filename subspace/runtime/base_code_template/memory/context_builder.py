"""Context builder that transforms symbolic memory into LLM-ready format.

Converts selected memory blocks into a structured JSON context that can be
included in LLM prompts.
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .memory_types import MemoryType, Priority
from .memory_blocks import (
    MemoryBlock,
    FileMemoryBlock, TaskMemoryBlock,
    KnowledgeMemoryBlock, ObservationMemoryBlock
)
from .content_loader import ContentLoader

logger = logging.getLogger("Cyber.memory.context")


class ContextBuilder:
    """Builds LLM context from symbolic memory blocks."""
    
    def __init__(self, content_loader: ContentLoader, 
                 include_metadata: bool = True):
        """Initialize context builder.
        
        Args:
            content_loader: Loader for fetching actual content
            include_metadata: Whether to include metadata in context
        """
        self.content_loader = content_loader
        self.include_metadata = include_metadata
    
    def build_context(self, selected_memories: List[MemoryBlock], 
                     format_type: str = "json") -> str:
        """Convert symbolic memories to formatted context.
        
        Args:
            selected_memories: Memory blocks selected for inclusion
            format_type: Output format - always use "json" for efficiency
            
        Returns:
            Formatted context string for LLM
        """
        # Always use JSON format for clarity and efficiency
        return self._build_json_context(selected_memories)
    
    def _build_json_context(self, memories: List[MemoryBlock]) -> str:
        """Build JSON-formatted context."""
        context_entries = []
        
        for memory in memories:
            try:
                content = self.content_loader.load_content(memory)
                
                # Don't truncate - we need full context
                # User explicitly requested no truncation anywhere in the system
                
                # Compact format - only include non-default values
                entry = {
                    "id": memory.id,
                    "content": content
                }
                
                # Only add type if not obvious from id
                if not memory.id.startswith(memory.type.value):
                    entry["type"] = memory.type.value
                
                # Only add confidence if not 1.0
                if memory.confidence < 1.0:
                    entry["confidence"] = round(memory.confidence, 2)
                
                # Only add priority if not MEDIUM
                if memory.priority != Priority.MEDIUM:
                    entry["priority"] = memory.priority.value
                
                # Add minimal metadata if needed
                if self.include_metadata and memory.metadata:
                    # Only include essential metadata
                    essential_meta = {}
                    if isinstance(memory, FileMemoryBlock) and memory.location != "<BOOT_ROM>":
                        essential_meta["loc"] = memory.location
                        # Check if it's a message file
                        if memory.metadata.get('file_type') == 'message':
                            essential_meta["from"] = memory.metadata.get('from_agent', 'unknown')
                            if not memory.metadata.get('read', False):
                                essential_meta["unread"] = True
                    elif isinstance(memory, TaskMemoryBlock):
                        essential_meta["status"] = memory.status
                    
                    if essential_meta:
                        entry["meta"] = essential_meta
                
                context_entries.append(entry)
                
            except Exception as e:
                logger.error(f"Error building context for {memory.id}: {e}")
                # Include error entry
                context_entries.append({
                    "id": memory.id,
                    "type": memory.type.value,
                    "content": f"[Error loading content: {str(e)}]",
                    "error": True
                })
        
        return json.dumps(context_entries, indent=2)
    
    def _build_structured_context(self, memories: List[MemoryBlock]) -> str:
        """Build human-readable structured context."""
        sections = []
        
        # Group memories by type
        memories_by_type: Dict[MemoryType, List[MemoryBlock]] = {}
        for memory in memories:
            if memory.type not in memories_by_type:
                memories_by_type[memory.type] = []
            memories_by_type[memory.type].append(memory)
        
        # Build sections for each type
        type_order = [
            MemoryType.KNOWLEDGE,  # Knowledge (including pinned ROM)
            MemoryType.TASK,       # Current task
            MemoryType.MESSAGE,    # Messages
            MemoryType.OBSERVATION,  # Recent observations
            MemoryType.FILE,     # File content
            MemoryType.KNOWLEDGE,  # Knowledge base
            MemoryType.CONTEXT,  # Derived context
        ]
        
        for mem_type in type_order:
            if mem_type in memories_by_type:
                section = self._build_type_section(mem_type, memories_by_type[mem_type])
                if section:
                    sections.append(section)
        
        # Add any remaining types not in order
        for mem_type, mems in memories_by_type.items():
            if mem_type not in type_order:
                section = self._build_type_section(mem_type, mems)
                if section:
                    sections.append(section)
        
        return "\n\n".join(sections)
    
    def _build_type_section(self, mem_type: MemoryType, memories: List[MemoryBlock]) -> str:
        """Build a section for a specific memory type."""
        if not memories:
            return ""
        
        # Section headers
        headers = {
            MemoryType.KNOWLEDGE: "=== KNOWLEDGE ===",
            MemoryType.TASK: "=== CURRENT TASKS ===",
            MemoryType.MESSAGE: "=== MESSAGES ===",
            MemoryType.FILE: "=== FILE CONTENT ===",
            MemoryType.KNOWLEDGE: "=== KNOWLEDGE BASE ===",
            MemoryType.OBSERVATION: "=== OBSERVATIONS ===",
            MemoryType.CONTEXT: "=== CONTEXT ===",
            MemoryType.STATUS: "=== STATUS ===",
        }
        
        lines = [headers.get(mem_type, f"=== {mem_type.value.upper()} ===")]
        
        # Add each memory
        for memory in memories:
            try:
                content = self.content_loader.load_content(memory)
                
                # Add memory-specific formatting
                if isinstance(memory, FileMemoryBlock):
                    lines.append(f"\n--- File: {memory.location} ---")
                    if memory.start_line:
                        lines.append(f"Lines {memory.start_line}-{memory.end_line or 'end'}")
                elif isinstance(memory, FileMemoryBlock) and memory.metadata.get('file_type') == 'message':
                    status = "UNREAD" if not memory.metadata.get('read', False) else "READ"
                    from_agent = memory.metadata.get('from_agent', 'unknown')
                    subject = memory.metadata.get('subject', 'No subject')
                    lines.append(f"\n--- Message [{status}] from {from_agent}: {subject} ---")
                elif isinstance(memory, TaskMemoryBlock):
                    lines.append(f"\n--- Task: {memory.task_id} [{memory.status}] ---")
                elif isinstance(memory, ObservationMemoryBlock):
                    lines.append(f"\n--- {memory.observation_type} ---")
                else:
                    lines.append(f"\n--- {memory.id} ---")
                
                # Add confidence/priority if not maximum
                if memory.confidence < 1.0 or memory.priority != Priority.CRITICAL:
                    meta_parts = []
                    if memory.confidence < 1.0:
                        meta_parts.append(f"confidence: {memory.confidence:.2f}")
                    if memory.priority != Priority.CRITICAL:
                        meta_parts.append(f"priority: {memory.priority.name}")
                    lines.append(f"[{', '.join(meta_parts)}]")
                
                # Add content - no truncation
                lines.append(content)
                
            except Exception as e:
                logger.error(f"Error loading {memory.id}: {e}")
                lines.append(f"[Error loading content: {str(e)}]")
        
        return "\n".join(lines)
    
    def _build_narrative_context(self, memories: List[MemoryBlock]) -> str:
        """Build a narrative-style context."""
        lines = ["Let me review what I know and what's happening:\n"]
        
        # Pinned knowledge first (acting as ROM)
        pinned_knowledge = [m for m in memories if m.type == MemoryType.KNOWLEDGE and m.pinned]
        if pinned_knowledge:
            lines.append("My core knowledge tells me:")
            for memory in pinned_knowledge:
                content = self.content_loader.load_content(memory)
                lines.append(f"- {content}")
            lines.append("")
        
        # Current situation
        task_memories = [m for m in memories if m.type == MemoryType.TASK]
        if task_memories:
            lines.append("I'm currently working on:")
            for memory in task_memories:
                if isinstance(memory, TaskMemoryBlock):
                    lines.append(f"- {memory.description} (status: {memory.status})")
            lines.append("")
        
        # Recent observations
        obs_memories = [m for m in memories if m.type == MemoryType.OBSERVATION]
        if obs_memories:
            lines.append("I've recently observed:")
            for memory in obs_memories:
                if isinstance(memory, ObservationMemoryBlock):
                    lines.append(f"- {memory.observation_type}: {memory.path}")
            lines.append("")
        
        # Messages (now FileMemoryBlock with message metadata)
        msg_memories = [m for m in memories if isinstance(m, FileMemoryBlock) and m.metadata.get('file_type') == 'message']
        unread = [m for m in msg_memories if not m.metadata.get('read', False)]
        if unread:
            lines.append(f"I have {len(unread)} unread messages:")
            for memory in unread[:3]:  # First 3
                from_agent = memory.metadata.get('from_agent', 'unknown')
                subject = memory.metadata.get('subject', 'No subject')
                lines.append(f"- From {from_agent}: {subject}")
            if len(unread) > 3:
                lines.append(f"- ...and {len(unread) - 3} more")
            lines.append("")
        
        # Other content
        other_memories = [m for m in memories if m.type not in 
                         [MemoryType.KNOWLEDGE, MemoryType.TASK, MemoryType.OBSERVATION, MemoryType.MESSAGE]]
        
        if other_memories:
            lines.append("Additional relevant information:")
            for memory in other_memories[:5]:  # Limit to avoid too long
                try:
                    content = self.content_loader.load_content(memory)
                    lines.append(f"- {memory.type.value}: {content}")
                except Exception:
                    pass
        
        return "\n".join(lines)
    
    def _build_metadata(self, memory: MemoryBlock) -> Dict[str, Any]:
        """Build metadata for context entry."""
        metadata = {
            "timestamp": memory.timestamp.isoformat(),
            **memory.metadata
        }
        
        # Add type-specific metadata
        if isinstance(memory, FileMemoryBlock):
            metadata["source"] = memory.location
            if memory.start_line is not None:
                metadata["lines"] = f"{memory.start_line}-{memory.end_line or 'end'}"
                
        elif isinstance(memory, TaskMemoryBlock):
            metadata["task_id"] = memory.task_id
            metadata["status"] = memory.status
            if memory.project:
                metadata["project"] = memory.project
                
        # Check if FileMemoryBlock is a message
        elif isinstance(memory, FileMemoryBlock) and memory.metadata.get('file_type') == 'message':
            metadata["from"] = memory.metadata.get('from_agent', 'unknown')
            metadata["to"] = memory.metadata.get('to_agent', 'me')
            metadata["read"] = memory.metadata.get('read', False)
            
        elif isinstance(memory, KnowledgeMemoryBlock):
            metadata["topic"] = memory.topic
            if memory.subtopic:
                metadata["subtopic"] = memory.subtopic
            metadata["relevance"] = memory.relevance_score
            
        elif isinstance(memory, ObservationMemoryBlock):
            metadata["observation_type"] = memory.observation_type
            metadata["path"] = memory.path
        
        return metadata
    
    def estimate_tokens(self, memory: MemoryBlock) -> int:
        """Estimate token count for a memory block.
        
        Simple estimation: ~4 characters per token
        """
        try:
            content = self.content_loader.load_content(memory)
            # Include metadata overhead if enabled
            overhead = 50 if self.include_metadata else 20
            return (len(content) // 4) + overhead
        except Exception:
            # Default estimate for errors
            return 50
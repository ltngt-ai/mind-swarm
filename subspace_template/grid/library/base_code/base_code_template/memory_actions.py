"""Memory-focused actions for agent file operations.

These actions treat files as memories, providing a natural interface
for agents to work with persistent storage through their memory system.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from .actions.base_actions import Action, ActionResult, ActionStatus, Priority
from .memory import (
    FileMemoryBlock, ObservationMemoryBlock, KnowledgeMemoryBlock,
    WorkingMemoryManager, ContentLoader, MemoryType
)

logger = logging.getLogger("agent.memory_actions")


class FocusMemoryAction(Action):
    """Focus attention on a specific memory (file or otherwise).
    
    This loads content into working memory for processing, making it
    available for the agent's cognitive processes.
    """
    
    def __init__(self):
        super().__init__(
            "focus_memory",
            "Focus attention on a memory to load its content",
            Priority.HIGH
        )
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Load memory content into working memory."""
        memory_id = self.params.get("memory_id", "")
        focus_type = self.params.get("focus_type", "read")
        line_range = self.params.get("line_range")  # Optional tuple (start, end)
        
        if not memory_id:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error="No memory_id specified to focus on"
            )
        
        try:
            memory_manager: WorkingMemoryManager = context.get("memory_manager")
            if not memory_manager:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="No memory manager available"
                )
            
            # Check if memory_id is already a loaded memory
            existing_memory = memory_manager.access_memory(memory_id)
            
            if existing_memory:
                # Memory already loaded, just access it
                home_dir = context.get("home_dir", Path.home())
                content_loader = ContentLoader(home_dir.parent)
                content = content_loader.load_content(existing_memory)
                
                # Create observation about focusing
                obs = ObservationMemoryBlock(
                    observation_type="memory_focused",
                    path=memory_id,
                    priority=Priority.MEDIUM,
                    metadata={
                        "focus_type": focus_type,
                        "memory_type": existing_memory.type.value
                    }
                )
                memory_manager.add_memory(obs)
                
                return ActionResult(
                    self.name,
                    ActionStatus.COMPLETED,
                    result={
                        "memory_id": memory_id,
                        "memory_type": existing_memory.type.value,
                        "content": content,
                        "content_length": len(content),
                        "focus_type": focus_type
                    }
                )
            
            # Not in memory, treat as file path
            file_path = Path(memory_id)
            
            # Get home_dir from context (needed for ContentLoader later)
            home_dir = context.get("home_dir", Path.home())
            
            # Resolve path relative to agent's context
            if not file_path.is_absolute():
                # Try different base paths
                possible_paths = [
                    home_dir / file_path,  # Personal memory
                    home_dir.parent / "grid" / file_path,  # Shared memory
                    home_dir / "memory" / file_path,  # Memory directory
                    home_dir.parent / file_path  # Relative to subspace
                ]
                
                for path in possible_paths:
                    if path.exists():
                        file_path = path
                        break
                else:
                    # Couldn't find file
                    return ActionResult(
                        self.name,
                        ActionStatus.FAILED,
                        error=f"Memory not found: {memory_id}",
                        result={"searched_paths": [str(p) for p in possible_paths]}
                    )
            
            # Create FileMemoryBlock for the file
            file_memory = FileMemoryBlock(
                location=str(file_path),
                start_line=line_range[0] if line_range else None,
                end_line=line_range[1] if line_range else None,
                priority=Priority.HIGH if focus_type == "edit" else Priority.MEDIUM,
                metadata={
                    "focus_type": focus_type,
                    "focused_at": datetime.now().isoformat()
                }
            )
            
            # Add to working memory
            memory_manager.add_memory(file_memory)
            
            # Load content
            content_loader = ContentLoader(home_dir.parent)
            content = content_loader.load_content(file_memory)
            
            # Determine file type and create appropriate observation
            file_type = self._determine_file_type(file_path)
            
            obs = ObservationMemoryBlock(
                observation_type="file_focused",
                path=str(file_path),
                priority=Priority.MEDIUM,
                metadata={
                    "focus_type": focus_type,
                    "file_type": file_type,
                    "file_size": file_path.stat().st_size
                }
            )
            memory_manager.add_memory(obs)
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "memory_id": file_memory.id,
                    "file_path": str(file_path),
                    "file_type": file_type,
                    "content": content,
                    "content_length": len(content),
                    "focus_type": focus_type,
                    "line_range": line_range
                }
            )
            
        except Exception as e:
            logger.error(f"Error focusing on memory {memory_id}: {e}", exc_info=True)
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )
    
    def _determine_file_type(self, file_path: Path) -> str:
        """Determine the type of file for better context."""
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()
        
        # Check by extension
        if suffix in ['.py']:
            return "python"
        elif suffix in ['.md', '.markdown']:
            return "markdown"
        elif suffix in ['.json']:
            return "json"
        elif suffix in ['.yaml', '.yml']:
            return "yaml"
        elif suffix in ['.txt', '.log']:
            return "text"
        elif suffix in ['.sh', '.bash']:
            return "shell"
        
        # Check by name patterns
        if 'readme' in name:
            return "documentation"
        elif 'config' in name or 'settings' in name:
            return "configuration"
        elif 'memory' in str(file_path) or 'knowledge' in str(file_path):
            return "memory"
        
        return "generic"


class CreateMemoryAction(Action):
    """Create a new persistent memory (file).
    
    This allows agents to store information permanently as files,
    but thinking of them as memories rather than files.
    """
    
    def __init__(self):
        super().__init__(
            "create_memory",
            "Create a new persistent memory",
            Priority.HIGH
        )
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Create a new file as a memory."""
        content = self.params.get("content", "")
        location = self.params.get("location", "")
        memory_type = self.params.get("memory_type", "note")
        metadata = self.params.get("metadata", {})
        
        if not location:
            # Auto-generate location based on type and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            location = f"memory/{memory_type}_{timestamp}.txt"
        
        try:
            home_dir = context.get("home_dir", Path.home())
            
            # Determine base path based on location prefix
            if location.startswith("shared/"):
                base_path = home_dir.parent / "grid"
                location = location[7:]  # Remove 'shared/' prefix
            elif location.startswith("personal/"):
                base_path = home_dir
                location = location[9:]  # Remove 'personal/' prefix
            else:
                # Default to personal memory
                base_path = home_dir
            
            # Create full path
            file_path = base_path / location
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Add metadata header if it's a structured memory type
            if memory_type in ["knowledge", "observation", "reflection"]:
                header = {
                    "memory_type": memory_type,
                    "created_by": context.get("agent_id", "unknown"),
                    "created_at": datetime.now().isoformat(),
                    "metadata": metadata
                }
                
                # Format content with header
                if file_path.suffix == ".json":
                    # JSON file - merge header with content
                    try:
                        content_data = json.loads(content)
                        content_data["_metadata"] = header
                        formatted_content = json.dumps(content_data, indent=2)
                    except:
                        # Not valid JSON, write as text with header comment
                        formatted_content = f"/* Memory Metadata:\n{json.dumps(header, indent=2)}\n*/\n\n{content}"
                else:
                    # Text file - add header as comment
                    formatted_content = f"# Memory Metadata:\n# {json.dumps(header, indent=2)}\n\n{content}"
            else:
                formatted_content = content
            
            # Write the file
            file_path.write_text(formatted_content, encoding='utf-8')
            
            # Create FileMemoryBlock for the new memory
            file_memory = FileMemoryBlock(
                location=str(file_path),
                priority=Priority.HIGH,
                confidence=1.0,
                metadata={
                    "memory_type": memory_type,
                    "created": True,
                    **metadata
                }
            )
            
            # Add to working memory
            memory_manager = context.get("memory_manager")
            if memory_manager:
                memory_manager.add_memory(file_memory)
                
                # Create observation about creation
                obs = ObservationMemoryBlock(
                    observation_type="memory_created",
                    path=str(file_path),
                    priority=Priority.MEDIUM,
                    metadata={"memory_type": memory_type}
                )
                memory_manager.add_memory(obs)
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "memory_id": file_memory.id,
                    "file_path": str(file_path),
                    "memory_type": memory_type,
                    "size": len(formatted_content),
                    "location_type": "shared" if "grid" in str(file_path) else "personal"
                }
            )
            
        except Exception as e:
            logger.error(f"Error creating memory at {location}: {e}", exc_info=True)
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


class SearchMemoryAction(Action):
    """Search through memories for specific content.
    
    This searches both loaded memories and files on disk,
    creating memory blocks for search results.
    """
    
    def __init__(self):
        super().__init__(
            "search_memory",
            "Search memories for specific content",
            Priority.MEDIUM
        )
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Search for content in memories and files."""
        query = self.params.get("query", "")
        scope = self.params.get("scope", "all")  # "personal", "shared", "all"
        memory_types = self.params.get("memory_types", ["file", "knowledge"])
        max_results = self.params.get("max_results", 10)
        
        if not query:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error="No search query provided"
            )
        
        try:
            home_dir = context.get("home_dir", Path.home())
            memory_manager = context.get("memory_manager")
            results = []
            
            # Determine search paths based on scope
            search_paths = []
            if scope in ["personal", "all"]:
                search_paths.append(home_dir)
            if scope in ["shared", "all"]:
                search_paths.append(home_dir.parent / "grid")
            
            # Search in loaded memories first
            if memory_manager:
                for memory in memory_manager.symbolic_memory:
                    if memory.type.value not in memory_types:
                        continue
                    
                    # Check memory metadata and available content
                    if (query.lower() in str(memory.metadata).lower() or
                        query.lower() in memory.id.lower()):
                        results.append({
                            "memory_id": memory.id,
                            "memory_type": memory.type.value,
                            "match_type": "metadata",
                            "preview": str(memory)[:100]
                        })
            
            # Search in files
            for base_path in search_paths:
                if not base_path.exists():
                    continue
                
                # Simple recursive search (could be optimized with grep)
                for file_path in base_path.rglob("*"):
                    if len(results) >= max_results:
                        break
                    
                    if file_path.is_file() and file_path.stat().st_size < 1_000_000:  # Skip large files
                        try:
                            content = file_path.read_text(encoding='utf-8', errors='ignore')
                            if query.lower() in content.lower():
                                # Find line with match for preview
                                lines = content.split('\n')
                                match_line = next((i for i, line in enumerate(lines) 
                                                 if query.lower() in line.lower()), 0)
                                
                                # Create FileMemoryBlock for result
                                result_memory = FileMemoryBlock(
                                    location=str(file_path),
                                    start_line=max(1, match_line - 2),
                                    end_line=min(len(lines), match_line + 3),
                                    priority=Priority.MEDIUM,
                                    metadata={
                                        "search_query": query,
                                        "match_line": match_line + 1
                                    }
                                )
                                
                                if memory_manager:
                                    memory_manager.add_memory(result_memory)
                                
                                results.append({
                                    "memory_id": result_memory.id,
                                    "file_path": str(file_path),
                                    "match_line": match_line + 1,
                                    "preview": lines[match_line].strip() if match_line < len(lines) else ""
                                })
                        except:
                            # Skip files that can't be read as text
                            pass
            
            # Create observation about search
            if memory_manager:
                obs = ObservationMemoryBlock(
                    observation_type="memory_search",
                    path="search_results",
                    priority=Priority.LOW,
                    metadata={
                        "query": query,
                        "scope": scope,
                        "result_count": len(results)
                    }
                )
                memory_manager.add_memory(obs)
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "query": query,
                    "scope": scope,
                    "result_count": len(results),
                    "results": results[:max_results]
                }
            )
            
        except Exception as e:
            logger.error(f"Error searching memories: {e}", exc_info=True)
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=str(e)
            )


# Register memory actions
def register_memory_actions(registry):
    """Register all memory-focused actions."""
    registry.register_action("base", "focus_memory", FocusMemoryAction)
    registry.register_action("base", "create_memory", CreateMemoryAction)
    registry.register_action("base", "search_memory", SearchMemoryAction)
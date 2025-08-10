"""Memory-focused actions for Cyber file operations.

These actions treat files as memories, providing a natural interface
for Cybers to work with persistent storage through their memory system.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from .actions.base_actions import Action, ActionResult, ActionStatus, Priority as ActionPriority
from .memory import (
    FileMemoryBlock, ObservationMemoryBlock, KnowledgeMemoryBlock,
    MemorySystem, ContentLoader, MemoryType, Priority
)

logger = logging.getLogger("Cyber.memory_actions")


class FocusMemoryAction(Action):
    """Focus attention on a specific memory (file or otherwise).
    
    This loads content into working memory for processing, making it
    available for the Cyber's cognitive processes.
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
            memory_system = context.get("memory_system") or context.get("memory_system")
            if not memory_system:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="No memory system available"
                )
            
            # Check if memory_id is already a loaded memory
            existing_memory = memory_system.get_memory(memory_id)
            
            if existing_memory:
                # Memory already loaded, just access it
                personal_dir = context.get("personal_dir", Path.home())
                content_loader = ContentLoader(personal_dir.parent)
                content = content_loader.load_content(existing_memory)
                
                # Create observation about focusing
                cognitive_loop = context.get("cognitive_loop")
                cycle_count = cognitive_loop.cycle_count if cognitive_loop else 0
                obs = ObservationMemoryBlock(
                    observation_type="memory_focused",
                    path="personal/memory/focused",  # Simple path
                    message=f"Focused on {existing_memory.type.value} memory: {memory_id}",
                    cycle_count=cycle_count,
                    priority=Priority.MEDIUM
                )
                memory_system.add_memory(obs)
                
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
            
            # Get personal_dir from context (needed for ContentLoader later)
            personal_dir = context.get("personal_dir", Path.home())
            
            # Resolve path relative to Cyber's context
            if not file_path.is_absolute():
                # Try different base paths
                possible_paths = [
                    personal_dir / file_path,  # Personal memory
                    personal_dir.parent / "grid" / file_path,  # Shared memory
                    personal_dir / "memory" / file_path,  # Memory directory
                    personal_dir.parent / file_path  # Relative to subspace
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
            
            # Check if it's a directory
            if file_path.is_dir():
                # Handle directory by listing contents
                logger.info(f"Focusing on directory: {file_path}")
                
                # Get cycle count from context
                cognitive_loop = context.get("cognitive_loop")
                cycle_count = cognitive_loop.cycle_count if cognitive_loop else 0
                
                # List directory contents
                dir_contents = []
                try:
                    for item in sorted(file_path.iterdir()):
                        item_type = "directory" if item.is_dir() else "file"
                        # Get file size if it's a file
                        size = item.stat().st_size if item.is_file() else None
                        dir_contents.append({
                            "name": item.name,
                            "type": item_type,
                            "path": str(item),
                            "size": size
                        })
                except Exception as e:
                    logger.warning(f"Error listing directory contents: {e}")
                
                # Create a directory listing as content
                content = f"Directory: {file_path}\n"
                content += f"Contains {len(dir_contents)} items:\n\n"
                
                for item in dir_contents:
                    if item["type"] == "directory":
                        content += f"📁 {item['name']}/\n"
                    else:
                        size_str = f" ({item['size']} bytes)" if item['size'] is not None else ""
                        content += f"📄 {item['name']}{size_str}\n"
                
                # Create observation for directory focus
                obs = ObservationMemoryBlock(
                    observation_type="directory_focused",
                    path=str(file_path),
                    message=f"Focused on directory: {file_path.name} ({len(dir_contents)} items)",
                    cycle_count=cycle_count,
                    content=content if len(content) < 1024 else None,  # Include listing if small
                    priority=Priority.MEDIUM
                )
                memory_system.add_memory(obs)
                
                # Also add FileMemoryBlocks for each file in the directory
                for item in dir_contents:
                    if item["type"] == "file":
                        item_path = Path(item["path"])
                        # Create FileMemoryBlock for each file
                        file_mem = FileMemoryBlock(
                            location=str(item_path),
                            priority=Priority.LOW,  # Low priority since just listing
                            confidence=0.8
                        )
                        memory_system.add_memory(file_mem)
                        logger.debug(f"Added file to memory: {item_path.name}")
                
                return ActionResult(
                    self.name,
                    ActionStatus.COMPLETED,
                    result={
                        "memory_id": f"directory:{file_path}",
                        "directory_path": str(file_path),
                        "item_count": len(dir_contents),
                        "contents": dir_contents,
                        "listing": content,
                        "focus_type": "directory"
                    }
                )
            
            # Regular file handling
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
            memory_system.add_memory(file_memory)
            
            # Load content
            content_loader = ContentLoader(personal_dir.parent)
            content = content_loader.load_content(file_memory)
            
            # Determine file type and create appropriate observation
            file_type = self._determine_file_type(file_path)
            
            # Get cycle count from context
            cognitive_loop = context.get("cognitive_loop")
            cycle_count = cognitive_loop.cycle_count if cognitive_loop else 0
            
            obs = ObservationMemoryBlock(
                observation_type="file_focused",
                path=str(file_path),
                message=f"Focused on {file_type} file: {file_path.name}",
                cycle_count=cycle_count,
                priority=Priority.MEDIUM
            )
            memory_system.add_memory(obs)
            
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
    
    This allows Cybers to store information permanently as files,
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
            personal_dir = context.get("personal_dir", Path.home())
            
            # Determine base path based on location prefix
            if location.startswith("shared/"):
                base_path = personal_dir.parent / "grid"
                location = location[7:]  # Remove 'shared/' prefix
            elif location.startswith("personal/"):
                base_path = personal_dir
                location = location[9:]  # Remove 'personal/' prefix
            else:
                # Default to personal memory
                base_path = personal_dir
            
            # Create full path
            file_path = base_path / location
            
            # Validate the path
            if file_path.is_dir():
                # User provided a directory path, not a file path
                suggested_path = file_path / f"{memory_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Location '{location}' is a directory, not a file. Did you mean '{suggested_path.name}'?",
                    result={
                        "provided_path": str(file_path),
                        "suggested_filename": suggested_path.name,
                        "suggested_full_path": str(suggested_path)
                    }
                )
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Add metadata header if it's a structured memory type
            if memory_type in ["knowledge", "observation", "reflection"]:
                header = {
                    "memory_type": memory_type,
                    "created_by": context.get("cyber_id", "unknown"),
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
            memory_system = context.get("memory_system")
            if memory_system:
                memory_system.add_memory(file_memory)
                
                # Create observation about creation
                cognitive_loop = context.get("cognitive_loop")
                cycle_count = cognitive_loop.cycle_count if cognitive_loop else 0
                obs = ObservationMemoryBlock(
                    observation_type="memory_created",
                    path=str(file_path),
                    message=f"Created {memory_type} memory at {file_path}",
                    cycle_count=cycle_count,
                    priority=Priority.MEDIUM
                )
                memory_system.add_memory(obs)
            
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
            
        except IsADirectoryError as e:
            # This shouldn't happen anymore due to validation above, but just in case
            suggested_name = f"{memory_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=f"Cannot write to directory '{location}'. Please specify a filename, e.g., '{location}/{suggested_name}'",
                result={"suggested_path": f"{location}/{suggested_name}"}
            )
        except PermissionError as e:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=f"Permission denied writing to '{location}'. Try a different location or check permissions.",
                result={"attempted_path": str(file_path)}
            )
        except Exception as e:
            logger.error(f"Error creating memory at {location}: {e}", exc_info=True)
            
            # Provide helpful error messages based on common issues
            error_msg = str(e)
            if "No such file or directory" in error_msg:
                error_msg = f"Path '{location}' contains invalid directories. Check the path and try again."
            elif "File name too long" in error_msg:
                error_msg = f"Filename is too long. Try a shorter name."
            else:
                error_msg = f"Failed to create memory: {error_msg}"
            
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=error_msg,
                result={"attempted_path": str(file_path), "original_error": str(e)}
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
            personal_dir = context.get("personal_dir", Path.home())
            memory_system = context.get("memory_system")
            results = []
            
            # Determine search paths based on scope
            search_paths = []
            if scope in ["personal", "all"]:
                search_paths.append(personal_dir)
            if scope in ["shared", "all"]:
                search_paths.append(personal_dir.parent / "grid")
            
            # Search in loaded memories first
            if memory_system:
                for memory in memory_system.symbolic_memory:
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
                                
                                if memory_system:
                                    memory_system.add_memory(result_memory)
                                
                                results.append({
                                    "memory_id": result_memory.id,
                                    "file_path": str(file_path),
                                    "match_line": match_line + 1,
                                    "preview": lines[match_line].strip() if match_line < len(lines) else ""
                                })
                        except:
                            # Skip files that can't be read as text
                            pass
            
            # Create observation about search - write results to file
            if memory_system:
                from datetime import datetime
                import json
                
                # Write search results to file (this IS memory)
                results_dir = Path("/personal/memory/action_results")
                results_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
                filename = f"search_{timestamp}.json"
                filepath = results_dir / filename
                
                search_data = {
                    "observation_type": "memory_search",
                    "timestamp": datetime.now().isoformat(),
                    "query": query,
                    "scope": scope,
                    "result_count": len(results),
                    "results": results[:max_results]
                }
                
                with open(filepath, 'w') as f:
                    json.dump(search_data, f, indent=2, default=str)
                
                # Get cycle count
                cognitive_loop = context.get("cognitive_loop") if context else None
                cycle_count = cognitive_loop.cycle_count if cognitive_loop else 0
                
                obs = ObservationMemoryBlock(
                    observation_type="memory_search",
                    path=str(filepath),  # Path to actual memory file
                    message=f"Search for '{query}' found {len(results)} results",
                    cycle_count=cycle_count,
                    priority=Priority.LOW
                )
                memory_system.add_memory(obs)
            
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


class ManageMemoryAction(Action):
    """Manage memory block properties including priority, pinning, and removal.
    
    This action allows Cybers to control how their memories are managed,
    including setting priorities, pinning important memories, and forgetting
    obsolete ones.
    """
    
    def __init__(self):
        super().__init__(
            "manage_memory",
            "Manage memory properties like priority and pinning",
            Priority.MEDIUM
        )
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Execute memory management operation."""
        memory_id = self.params.get("memory_id", "")
        operation = self.params.get("operation", "")
        
        if not memory_id:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error="No memory_id specified"
            )
        
        if not operation:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error="No operation specified"
            )
        
        try:
            memory_system = context.get("memory_system") or context.get("memory_system")
            if not memory_system:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="No memory system available"
                )
            
            # Get the memory block
            memory = memory_system.get_memory(memory_id)
            if not memory:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Memory {memory_id} not found"
                )
            
            result = {}
            
            if operation == "set_priority":
                # Change memory priority
                priority_value = self.params.get("priority", "")
                # Handle both string and numeric priority values
                if isinstance(priority_value, int):
                    # Map numeric values to priority names
                    priority_map = {1: "CRITICAL", 2: "HIGH", 3: "MEDIUM", 4: "LOW"}
                    new_priority = priority_map.get(priority_value, "")
                else:
                    new_priority = str(priority_value).upper()
                    
                if not new_priority:
                    return ActionResult(
                        self.name,
                        ActionStatus.FAILED,
                        error="Priority not specified for set_priority operation"
                    )
                
                try:
                    memory.priority = Priority[new_priority]
                    result = {
                        "memory_id": memory_id,
                        "operation": "set_priority",
                        "old_priority": result.get("old_priority", "UNKNOWN"),
                        "new_priority": new_priority,
                        "success": True
                    }
                except KeyError:
                    return ActionResult(
                        self.name,
                        ActionStatus.FAILED,
                        error=f"Invalid priority: {new_priority}. Must be one of: CRITICAL, HIGH, MEDIUM, LOW"
                    )
                    
            elif operation == "pin":
                # Pin memory so it's never removed
                memory.pinned = True
                result = {
                    "memory_id": memory_id,
                    "operation": "pin",
                    "pinned": True,
                    "success": True
                }
                
            elif operation == "unpin":
                # Unpin memory to allow normal management
                memory.pinned = False
                result = {
                    "memory_id": memory_id,
                    "operation": "unpin",
                    "pinned": False,
                    "success": True
                }
                
            elif operation == "forget":
                # Remove memory from the system
                memory_system.remove_memory(memory_id)
                result = {
                    "memory_id": memory_id,
                    "operation": "forget",
                    "removed": True,
                    "success": True
                }
                
            else:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Unknown operation: {operation}. Must be one of: set_priority, pin, unpin, forget"
                )
            
            # Create observation about the management action - write to file
            from datetime import datetime
            import json
            
            results_dir = Path("/personal/memory/action_results")
            results_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
            filename = f"manage_{timestamp}_{operation}.json"
            filepath = results_dir / filename
            
            manage_data = {
                "observation_type": "memory_managed",
                "timestamp": datetime.now().isoformat(),
                "memory_id": memory_id,
                "operation": operation,
                "result": result
            }
            
            with open(filepath, 'w') as f:
                json.dump(manage_data, f, indent=2, default=str)
            
            # Get cycle count
            cognitive_loop = context.get("cognitive_loop") if context else None
            cycle_count = cognitive_loop.cycle_count if cognitive_loop else 0
            
            obs = ObservationMemoryBlock(
                observation_type="memory_managed",
                path=str(filepath),  # Path to actual memory file
                message=f"Memory management: {operation} on {memory_id}",
                cycle_count=cycle_count,
                priority=Priority.LOW
            )
            memory_system.add_memory(obs)
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result=result
            )
            
        except Exception as e:
            logger.error(f"Error managing memory: {e}", exc_info=True)
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
    registry.register_action("base", "manage_memory", ManageMemoryAction)
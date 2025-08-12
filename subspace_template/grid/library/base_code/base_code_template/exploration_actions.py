"""Exploration actions for navigating and discovering the Mind-Swarm.

These actions allow Cybers to explore their environment, discover new areas,
and peek at locations without moving.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from .actions.base_actions import Action, ActionResult, ActionStatus
from .memory.memory_blocks import FileMemoryBlock, ObservationMemoryBlock
from .memory.memory_types import Priority, MemoryType

logger = logging.getLogger("Cyber.actions.exploration")


class FocusMemoryAction(Action):
    """Focus on a memory group (directory) to see its contents without moving.
    
    This is like looking through a telescope at another location - you can see
    what's there without physically going there.
    """
    
    def __init__(self):
        super().__init__("focus_memory", "Look at contents of another location without moving")
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Focus on a location and create a memory of its contents."""
        path = self.params.get("path", "")
        
        if not path:
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error="No path specified to focus on"
            )
        
        try:
            # Get cognitive loop for memory system access
            cognitive_loop = context.get("cognitive_loop")
            if not cognitive_loop:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="No cognitive loop available"
                )
            
            # Normalize the path
            from pathlib import PurePosixPath
            
            if not path.startswith('/'):
                # Relative path - resolve from current location
                dynamic_context = cognitive_loop.get_dynamic_context()
                current_location = dynamic_context.get("current_location", "/personal")
                
                current = PurePosixPath(current_location)
                focus_path = (current / path).resolve()
            else:
                # Absolute path
                focus_path = PurePosixPath(path)
            
            focus_path_str = str(focus_path)
            if not focus_path_str.startswith('/'):
                focus_path_str = '/' + focus_path_str
            
            # Validate the path is within allowed areas
            allowed_roots = ['/personal', '/grid']
            if not any(focus_path_str.startswith(root) or focus_path_str == root for root in allowed_roots):
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Cannot focus on {focus_path_str} - must be within /personal or /grid"
                )
            
            # Map virtual path to actual filesystem path
            if focus_path_str.startswith('/personal'):
                rel_path = focus_path_str[len('/personal'):]
                actual_path = cognitive_loop.personal / rel_path.lstrip('/') if rel_path else cognitive_loop.personal
            elif focus_path_str.startswith('/grid'):
                rel_path = focus_path_str[len('/grid'):]
                grid_path = cognitive_loop.personal.parent.parent / "grid"
                actual_path = grid_path / rel_path.lstrip('/') if rel_path else grid_path
            else:
                actual_path = None
            
            # Check if trying to focus on .internal
            if '.internal' in focus_path_str or focus_path_str.startswith('/personal/.internal'):
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="Cannot access /personal/.internal/* - these are private system memories"
                )
            
            # Check if path exists and is a directory
            if not actual_path or not actual_path.exists():
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Path does not exist: {focus_path_str}"
                )
            
            if not actual_path.is_dir():
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Path is not a memory group (directory): {focus_path_str}"
                )
            
            # Scan the directory contents
            contents = {
                "focused_location": focus_path_str,
                "directories": [],
                "files": [],
                "total_items": 0
            }
            
            for item in sorted(actual_path.iterdir()):
                # Skip ALL hidden files/dirs and system directories completely
                if item.name.startswith('.') or item.name in ['__pycache__', '.git']:
                    continue
                
                if item.is_dir():
                    # Check if it's a memory group with content
                    has_content = any(not sub.name.startswith('.') for sub in item.iterdir()) if any(item.iterdir()) else False
                    contents["directories"].append({
                        "name": f"📁 {item.name}",
                        "path": f"{focus_path_str}/{item.name}",
                        "has_content": has_content
                    })
                else:
                    # Get file info
                    size = item.stat().st_size if item.exists() else 0
                    contents["files"].append({
                        "name": f"📄 {item.name}",
                        "path": f"{focus_path_str}/{item.name}",
                        "size": size,
                        "type": item.suffix[1:] if item.suffix else "unknown"
                    })
            
            contents["total_items"] = len(contents["directories"]) + len(contents["files"])
            
            # Create a temporary focus file
            focus_file = cognitive_loop.memory_dir / f"focus_{Path(focus_path_str).name}.json"
            with open(focus_file, 'w') as f:
                json.dump(contents, f, indent=2)
            
            # Create a memory block for the focused location
            focus_memory = FileMemoryBlock(
                location=str(focus_file.relative_to(cognitive_loop.personal.parent)),
                priority=Priority.HIGH,  # User-requested focus
                confidence=1.0,
                metadata={
                    "file_type": "focused_location",
                    "description": f"Focused view of: {focus_path_str}",
                    "location": focus_path_str,
                    "item_count": contents["total_items"]
                },
                cycle_count=cognitive_loop.cycle_count
            )
            cognitive_loop.memory_system.add_memory(focus_memory)
            
            # Create an observation about what was discovered
            if contents["total_items"] > 0:
                obs_message = f"Focused on {focus_path_str}: Found {len(contents['directories'])} directories and {len(contents['files'])} files"
            else:
                obs_message = f"Focused on {focus_path_str}: Location is empty"
            
            obs_memory = ObservationMemoryBlock(
                observation_type="location_focused",
                path=focus_path_str,
                message=obs_message,
                cycle_count=cognitive_loop.cycle_count,
                priority=Priority.MEDIUM
            )
            cognitive_loop.memory_system.add_memory(obs_memory)
            
            logger.info(f"Focused on location: {focus_path_str} ({contents['total_items']} items)")
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "focused_location": focus_path_str,
                    "directories_found": len(contents["directories"]),
                    "files_found": len(contents["files"]),
                    "total_items": contents["total_items"]
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to focus on location: {e}", exc_info=True)
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=f"Failed to focus on location: {str(e)}"
            )


class ExploreTreeAction(Action):
    """Recursively explore a directory tree to discover its structure.
    
    Creates a tree-view memory of the directory structure, useful for
    understanding the organization of a memory group.
    """
    
    def __init__(self):
        super().__init__("explore_tree", "Recursively explore directory structure")
    
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        """Explore directory tree and create a structural memory."""
        path = self.params.get("path", ".")
        max_depth = self.params.get("max_depth", 3)  # Limit recursion depth
        
        try:
            cognitive_loop = context.get("cognitive_loop")
            if not cognitive_loop:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error="No cognitive loop available"
                )
            
            # Resolve path similar to focus_memory
            from pathlib import PurePosixPath
            
            if path == ".":
                # Current location
                dynamic_context = cognitive_loop.get_dynamic_context()
                explore_path_str = dynamic_context.get("current_location", "/personal")
            elif not path.startswith('/'):
                # Relative path
                dynamic_context = cognitive_loop.get_dynamic_context()
                current_location = dynamic_context.get("current_location", "/personal")
                
                current = PurePosixPath(current_location)
                explore_path = (current / path).resolve()
                explore_path_str = str(explore_path)
            else:
                explore_path_str = path
            
            # Map to actual path
            if explore_path_str.startswith('/personal'):
                rel_path = explore_path_str[len('/personal'):]
                actual_path = cognitive_loop.personal / rel_path.lstrip('/') if rel_path else cognitive_loop.personal
            elif explore_path_str.startswith('/grid'):
                rel_path = explore_path_str[len('/grid'):]
                grid_path = cognitive_loop.personal.parent.parent / "grid"
                actual_path = grid_path / rel_path.lstrip('/') if rel_path else grid_path
            else:
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Invalid path: {explore_path_str}"
                )
            
            if not actual_path.exists() or not actual_path.is_dir():
                return ActionResult(
                    self.name,
                    ActionStatus.FAILED,
                    error=f"Path does not exist or is not a directory: {explore_path_str}"
                )
            
            # Build tree structure
            def build_tree(dir_path: Path, virtual_path: str, depth: int = 0) -> Dict[str, Any]:
                if depth >= max_depth:
                    return {"name": dir_path.name, "path": virtual_path, "truncated": True}
                
                tree = {
                    "name": dir_path.name,
                    "path": virtual_path,
                    "children": []
                }
                
                try:
                    for item in sorted(dir_path.iterdir()):
                        # Skip ALL hidden files/dirs and system directories completely
                        if item.name.startswith('.') or item.name in ['__pycache__', '.git']:
                            continue
                        
                        child_virtual = f"{virtual_path}/{item.name}"
                        
                        if item.is_dir():
                            subtree = build_tree(item, child_virtual, depth + 1)
                            subtree["name"] = f"📁 {subtree['name']}"
                            tree["children"].append(subtree)
                        else:
                            tree["children"].append({
                                "name": f"📄 {item.name}",
                                "path": child_virtual,
                                "type": "file",
                                "size": item.stat().st_size
                            })
                except PermissionError:
                    tree["permission_denied"] = True
                
                return tree
            
            tree_structure = build_tree(actual_path, explore_path_str)
            
            # Save tree structure
            tree_file = cognitive_loop.memory_dir / f"tree_{Path(explore_path_str).name}.json"
            with open(tree_file, 'w') as f:
                json.dump(tree_structure, f, indent=2)
            
            # Create memory block
            tree_memory = FileMemoryBlock(
                location=str(tree_file.relative_to(cognitive_loop.personal.parent)),
                priority=Priority.MEDIUM,
                confidence=1.0,
                metadata={
                    "file_type": "directory_tree",
                    "description": f"Tree structure of: {explore_path_str}",
                    "root_location": explore_path_str,
                    "max_depth": max_depth
                },
                cycle_count=cognitive_loop.cycle_count
            )
            cognitive_loop.memory_system.add_memory(tree_memory)
            
            # Count items in tree
            def count_items(tree: Dict) -> tuple[int, int]:
                dirs = 0
                files = 0
                if tree.get("type") == "file":
                    return 0, 1
                dirs = 1  # Count this directory
                for child in tree.get("children", []):
                    child_dirs, child_files = count_items(child)
                    dirs += child_dirs
                    files += child_files
                return dirs, files
            
            dir_count, file_count = count_items(tree_structure)
            
            logger.info(f"Explored tree at {explore_path_str}: {dir_count} dirs, {file_count} files")
            
            return ActionResult(
                self.name,
                ActionStatus.COMPLETED,
                result={
                    "root_location": explore_path_str,
                    "directories_found": dir_count,
                    "files_found": file_count,
                    "max_depth": max_depth
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to explore tree: {e}", exc_info=True)
            return ActionResult(
                self.name,
                ActionStatus.FAILED,
                error=f"Failed to explore tree: {str(e)}"
            )


# Register exploration actions
def register_exploration_actions(registry):
    """Register all exploration actions."""
    registry.register_action("base", "focus_memory", FocusMemoryAction)
    registry.register_action("base", "explore_tree", ExploreTreeAction)
"""
# Location API for cybers to navigate their environment.

## Location
The Location class provides methods to get and set a Cyber's current
location, you will automatically observe your current location in the OBSERVE stage.

Examples:
    ```python        
    # Get current location
    current = location.current
    
    # Change location
    location.current = "/grid/library/knowledge"
    
    # Check if location exists
    if location.exists("/personal/workspace"):
        location.change("/personal/workspace")
    ```
"""

import json
from pathlib import Path
from typing import Dict, Any


class LocationError(Exception):
    """Base exception for location operations."""
    pass

class Location:
    """Location interface for navigating the Mind-Swarm."""
    
    def __init__(self, context: Dict[str, Any]):
        """Initialize the location system.
        
        Args:
            context: Execution context with cyber_id, paths, state_manager, etc.
        """
        self._context = context
        self._personal_root = Path(context.get('personal_dir', '/personal'))
        self._grid_root = Path('/grid')
        
        # State manager is REQUIRED
        self._state_manager = context.get('state_manager')
        if not self._state_manager:
            raise LocationError("State manager is required in context for Location API")
    
    def _read_dynamic_context(self) -> Dict[str, Any]:
        """Read the current dynamic context from unified state.
        
        Returns:
            Dict containing the dynamic context
            
        Raises:
            LocationError: If unable to read context
        """
        try:
            from ..state.unified_state_manager import StateSection
            return {
                "cycle_count": self._state_manager.get_value(StateSection.COGNITIVE, "cycle_count", 0),
                "current_stage": self._state_manager.get_value(StateSection.COGNITIVE, "current_stage", "INIT"),
                "current_phase": self._state_manager.get_value(StateSection.COGNITIVE, "current_phase", "STARTING"),
                "current_location": self._state_manager.get_value(StateSection.LOCATION, "current_location", "/personal"),
                "previous_location": self._state_manager.get_value(StateSection.LOCATION, "previous_location", None)
            }
            
        except Exception as e:
            raise LocationError(f"Failed to read dynamic context: {e}")
    
    def _write_dynamic_context(self, context: Dict[str, Any]):
        """Write location updates to unified state.
        
        Args:
            context: The context dictionary with location updates
            
        Raises:
            LocationError: If unable to write context
        """
        try:
            # Use state manager's update_location method
            new_location = context.get("current_location")
            if new_location:
                self._state_manager.update_location(new_location)
                
        except Exception as e:
            raise LocationError(f"Failed to write location to unified state: {e}")
    
    @property
    def current(self) -> str:
        """
Get the cyber's current location.        
Returns: Current location path (e.g., "/grid/library/knowledge")
"""
        try:
            dynamic_context = self._read_dynamic_context()
            return dynamic_context.get("current_location", "/grid/library/knowledge")
        except Exception as e:
            raise LocationError(f"Failed to get current location: {e}")
    
    @current.setter
    def current(self, new_location: str):
        """
Set the cyber's current location.
Args: new_location - Path to navigate to (must start with /personal or /grid)
Raises: LocationError - If the location is invalid
"""
        self.change(new_location)
    
    def change(self, new_location: str) -> str:
        """
Change the cyber's current location.        
Args: new_location-  Path to navigate to (must start with /personal or /grid)
Returns: The new location after successful change            
Raises: LocationError -  If the location is invalid or change fails
"""
        # Validate the new location
        if not new_location.startswith(('/personal', '/grid')):
            raise LocationError(
                f"Invalid location: {new_location}. "
                "Location must start with /personal or /grid"
            )
        
        # Normalize the path (remove trailing slashes, etc.)
        new_location = new_location.rstrip('/')
        if not new_location:
            new_location = '/personal'
        
        # Check if the location actually exists before allowing change
        if not self.exists(new_location):
            raise LocationError(
                f"Cannot move to {new_location}: location does not exist"
            )
        
        try:
            # Read current dynamic context
            dynamic_context = self._read_dynamic_context()
            old_location = dynamic_context.get("current_location", "unknown")
            
            # Update location and track previous
            dynamic_context["previous_location"] = old_location
            dynamic_context["current_location"] = new_location
            
            # Write back
            self._write_dynamic_context(dynamic_context)
            
            # Update current_location.txt immediately with basic scan
            location_file = self._personal_root / ".internal" / "memory" / "current_location.txt"
            # Always create/update the file, don't check if exists
            try:
                # Do a quick scan of the new location to populate the file
                actual_path = self._grid_root if new_location.startswith("/grid") else self._personal_root
                if new_location != "/grid" and new_location != "/personal":
                    # Build the actual filesystem path
                    relative_path = new_location[6:] if new_location.startswith("/grid/") else new_location[10:]
                    if relative_path:
                        actual_path = actual_path / relative_path
                
                lines = [f"| {new_location} (📁=directory, 📄=file)", "|"]
                
                if actual_path.exists() and actual_path.is_dir():
                    # Quick scan - just list items without full details
                    items = sorted(actual_path.iterdir())
                    visible_items = [item for item in items if not item.name.startswith('.') and item.name not in ['__pycache__', '.git']]
                    
                    if visible_items:
                        for item in visible_items:
                            icon = "📁" if item.is_dir() else "📄"
                            lines.append(f"|---- {icon} {item.name}")
                    else:
                        lines.append("|---- (empty or only hidden files)")
                else:
                    lines.append("|---- (location not found or not a directory)")
                
                location_file.write_text("\n".join(lines))
                
            except Exception as e:
                # On error, write minimal placeholder
                location_file.write_text(f"| {new_location} (📁=memory group, 📄=memory)\n|\n|---- (error scanning location: {e})\n")
            
            # Log the change (visible in debug logs)
            print(f"📍 Location changed from {old_location} to {new_location}")
            
            return new_location
            
        except Exception as e:
            raise LocationError(f"Failed to change location: {e}")
    
    def exists(self, location: str) -> bool:
        """
Check if a location path is valid and exists.
Args: location - Path to validate
Returns: True if location is valid and exists, False otherwise
"""
        if not location.startswith(('/personal', '/grid')):
            return False
        
        # Map to actual filesystem path using same logic as change()
        try:
            actual_path = self._grid_root if location.startswith("/grid") else self._personal_root
            if location != "/grid" and location != "/personal":
                # Build the actual filesystem path
                relative_path = location[6:] if location.startswith("/grid/") else location[10:]
                if relative_path:
                    actual_path = actual_path / relative_path
            
            return actual_path.exists() and actual_path.is_dir()
        except Exception:
            return False
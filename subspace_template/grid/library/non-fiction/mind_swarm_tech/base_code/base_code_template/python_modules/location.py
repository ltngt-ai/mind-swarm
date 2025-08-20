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
            context: Execution context with cyber_id, paths, etc.
        """
        self._context = context
        self._personal_root = Path(context.get('personal_dir', '/personal'))
        self._grid_root = Path('/grid')
        
        # Path to dynamic context file
        self._dynamic_context_file = self._personal_root / ".internal" / "memory" / "dynamic_context.json"
    
    def _read_dynamic_context(self) -> Dict[str, Any]:
        """Read the current dynamic context.
        
        Returns:
            Dict containing the dynamic context
            
        Raises:
            LocationError: If unable to read context
        """
        try:
            if not self._dynamic_context_file.exists():
                raise LocationError("Dynamic context file not found")
            
            # Read as standard JSON file
            with open(self._dynamic_context_file, 'r') as f:
                return json.load(f)
            
        except Exception as e:
            raise LocationError(f"Failed to read dynamic context: {e}")
    
    def _write_dynamic_context(self, context: Dict[str, Any]):
        """Write the dynamic context back to file.
        
        Args:
            context: The context dictionary to write
            
        Raises:
            LocationError: If unable to write context
        """
        try:
            # Write as standard JSON file
            with open(self._dynamic_context_file, 'w') as f:
                json.dump(context, f, indent=2)
                
        except Exception as e:
            raise LocationError(f"Failed to write dynamic context: {e}")
    
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
        
        try:
            # Read current dynamic context
            dynamic_context = self._read_dynamic_context()
            old_location = dynamic_context.get("current_location", "unknown")
            
            # Update location and track previous
            dynamic_context["previous_location"] = old_location
            dynamic_context["current_location"] = new_location
            
            # Write back
            self._write_dynamic_context(dynamic_context)
            
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
        
        # Map to actual filesystem path
        if location.startswith('/personal'):
            rel_path = location[len('/personal'):]
            actual_path = self._personal_root / rel_path.lstrip('/') if rel_path else self._personal_root
        elif location.startswith('/grid'):
            actual_path = Path(location)
        else:
            return False
        
        return actual_path.exists() and actual_path.is_dir()
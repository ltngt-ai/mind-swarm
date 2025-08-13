"""Location API for cybers to navigate their environment.

This module provides the Location class for managing the cyber's current location
in the filesystem hierarchy, which affects what the environment scanner
sees when looking around.

## Usage Examples

### Getting Current Location
```python
# The location object is pre-initialized for you
current = location.current
print(f"Currently at: {current}")
```

### Changing Location
```python
# Navigate to a specific location
location.current = "/grid/library/knowledge"

# Or use the change method
location.change("/personal/projects")

# Navigate to community area
location.current = "/grid/community"
```

### Validating Locations
```python
# Check if a location exists before navigating
if location.exists("/grid/workshop"):
    location.current = "/grid/workshop"
    print("Moved to workshop")
else:
    print("Workshop doesn't exist")
```

### Complete Example
```python
# Remember where we started
start_location = location.current
print(f"Starting at: {start_location}")

# Explore the knowledge library
location.current = "/grid/library/knowledge"
print("Now exploring the knowledge library...")
# The environment scanner will now show contents of knowledge library

# Check personal notes
if location.exists("/personal/notes"):
    location.current = "/personal/notes"
    print("Checking personal notes...")

# Return to starting location
location.current = start_location
print(f"Returned to: {start_location}")
```

## Important Notes

1. **Location paths must start with `/personal` or `/grid`**
2. **Changing location affects what you see when "looking around"**
3. **The environment scanner uses your current location to show relevant items**
4. **Invalid locations will raise a `LocationError`**
"""

import json
from pathlib import Path
from typing import Dict, Any


class LocationError(Exception):
    """Base exception for location operations."""
    pass


class Location:
    """Main location interface for navigating the cyber's environment.
    
    The Location class provides methods to get and set the cyber's current
    location, which determines what the environment scanner sees.
    
    Examples:
        ```python
        # The location object is pre-initialized for you
        
        # Get current location
        current = location.current
        
        # Change location
        location.current = "/grid/library/knowledge"
        
        # Check if location exists
        if location.exists("/personal/workspace"):
            location.change("/personal/workspace")
        ```
    """
    
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
            
            # Read the memory-mapped file properly
            with open(self._dynamic_context_file, 'rb') as f:
                content = f.read(4096)  # Read up to 4KB
            
            # Find the null terminator
            null_pos = content.find(b'\0')
            if null_pos != -1:
                json_bytes = content[:null_pos]
            else:
                json_bytes = content.rstrip(b'\0')
            
            # Parse JSON
            return json.loads(json_bytes.decode('utf-8'))
            
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
            # Write back with proper padding
            json_str = json.dumps(context, indent=2)
            json_bytes = json_str.encode('utf-8') + b'\0'
            padded_content = json_bytes.ljust(4096, b'\0')
            
            with open(self._dynamic_context_file, 'wb') as f:
                f.write(padded_content)
                
        except Exception as e:
            raise LocationError(f"Failed to write dynamic context: {e}")
    
    @property
    def current(self) -> str:
        """Get the cyber's current location.
        
        Returns:
            str: Current location path (e.g., "/grid/library/knowledge")
            
        Example:
            ```python
            where_am_i = location.current
            print(f"Currently at: {where_am_i}")
            ```
        """
        try:
            dynamic_context = self._read_dynamic_context()
            return dynamic_context.get("current_location", "/grid/library/knowledge")
        except Exception as e:
            raise LocationError(f"Failed to get current location: {e}")
    
    @current.setter
    def current(self, new_location: str):
        """Set the cyber's current location.
        
        Args:
            new_location: Path to navigate to (must start with /personal or /grid)
            
        Raises:
            LocationError: If the location is invalid
            
        Example:
            ```python
            # Navigate to knowledge section
            location.current = "/grid/library/knowledge/sections/communication"
            
            # Go to personal workspace
            location.current = "/personal/workspace"
            ```
        """
        self.change(new_location)
    
    def change(self, new_location: str) -> str:
        """Change the cyber's current location.
        
        This updates the dynamic context so the environment scanner will
        look at the new location on the next scan.
        
        Args:
            new_location: Path to navigate to (must start with /personal or /grid)
            
        Returns:
            str: The new location after successful change
            
        Raises:
            LocationError: If the location is invalid or change fails
            
        Example:
            ```python
            # Navigate to a knowledge section
            location.change("/grid/library/knowledge/sections/communication")
            
            # Go to personal workspace
            location.change("/personal/workspace")
            ```
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
            
            # Update location
            dynamic_context["current_location"] = new_location
            
            # Write back
            self._write_dynamic_context(dynamic_context)
            
            # Log the change (visible in debug logs)
            print(f"📍 Location changed from {old_location} to {new_location}")
            
            return new_location
            
        except Exception as e:
            raise LocationError(f"Failed to change location: {e}")
    
    def exists(self, location: str) -> bool:
        """Check if a location path is valid and exists.
        
        Args:
            location: Path to validate
            
        Returns:
            bool: True if location is valid and exists, False otherwise
            
        Example:
            ```python
            if location.exists("/grid/workshop"):
                location.current = "/grid/workshop"
            else:
                print("Workshop doesn't exist!")
            ```
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
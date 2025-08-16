"""
# Awareness API for cybers to query environmental awareness information.

## Awareness
The Awareness class provides methods to query information about the environment,
including nearby Cybers, locations of other Cybers, and general environment info.

Examples:
    ```python        
    # Query nearby Cybers at current location
    nearby = awareness.get_nearby_cybers()
    for cyber in nearby:
        print(f"- {cyber['name']} is here")
    
    # Check who's at a specific location
    cybers_at_library = awareness.get_cybers_at_location("/grid/library")
    
    # Get all Cyber locations
    locations = awareness.get_all_cyber_locations()
    
    # Get environment statistics
    env_info = awareness.get_environment_info()
    ```
"""

import json
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class AwarenessError(Exception):
    """Base exception for awareness operations."""
    pass


class Awareness:
    """Awareness interface for querying environmental information."""
    
    def __init__(self, context: Dict[str, Any]):
        """Initialize the awareness system.
        
        Args:
            context: Execution context with cyber_id, paths, etc.
        """
        self._context = context
        self._personal_root = Path(context.get('personal_dir', '/personal'))
        self._awareness_file = self._personal_root / ".internal" / "awareness"
        self._shutdown_file = self._personal_root / ".internal" / "shutdown"
        
    def _make_request(self, query_type: str, **kwargs) -> Dict[str, Any]:
        """Make a request to the awareness body file.
        
        Args:
            query_type: Type of query to make
            **kwargs: Additional parameters for the query
            
        Returns:
            Response dictionary from the awareness handler
            
        Raises:
            AwarenessError: If request fails
        """
        request_id = str(uuid.uuid4())
        
        request = {
            "request_id": request_id,
            "query_type": query_type,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        try:
            # Write request with end marker
            request_text = json.dumps(request, indent=2)
            with open(self._awareness_file, 'w') as f:
                f.write(f"{request_text}\n<<<END_AWARENESS_REQUEST>>>")
            
            # Wait for response (body file appears to respond instantly)
            max_wait = 5.0
            start_time = time.time()
            check_interval = 0.1
            
            while time.time() - start_time < max_wait:
                # Check for shutdown
                if self._shutdown_file.exists():
                    raise AwarenessError("Shutdown detected, cancelling request")
                
                with open(self._awareness_file, 'r') as f:
                    content = f.read()
                
                if "<<<AWARENESS_COMPLETE>>>" in content:
                    # Extract response
                    response_text = content.split("<<<AWARENESS_COMPLETE>>>")[0].strip()
                    
                    # Handle the case where response starts after the request
                    if "<<<END_AWARENESS_REQUEST>>>" in response_text:
                        response_text = response_text.split("<<<END_AWARENESS_REQUEST>>>")[1].strip()
                    
                    response = json.loads(response_text)
                    
                    # Clear the file for next request
                    with open(self._awareness_file, 'w') as f:
                        f.write("")
                    
                    if response.get("status") == "error":
                        raise AwarenessError(f"Request failed: {response.get('error', 'Unknown error')}")
                    
                    return response
                
                time.sleep(check_interval)
            
            raise AwarenessError("Request timeout - no response received")
            
        except json.JSONDecodeError as e:
            raise AwarenessError(f"Invalid response format: {e}")
        except AwarenessError:
            raise
        except Exception as e:
            raise AwarenessError(f"Request failed: {e}")
    
    def get_nearby_cybers(self, location: Optional[str] = None) -> List[Dict[str, Any]]:
        """
Get list of Cybers at the current or specified location.
Args: location - Optional location to check (defaults to current location)
Returns: List of nearby Cyber information dicts
"""
        response = self._make_request("nearby_cybers", location=location)
        return response.get("nearby_cybers", [])
    
    def get_cybers_at_location(self, location: str) -> List[Dict[str, Any]]:
        """
Get list of Cybers at a specific location.
Args: location - Location path to check
Returns: List of Cyber information dicts at that location
"""
        response = self._make_request("nearby_cybers", location=location)
        return response.get("nearby_cybers", [])
    
    def get_all_cyber_locations(self) -> List[Dict[str, str]]:
        """
Get locations of all Cybers in the system.
Returns: List of dicts with 'name' and 'location' keys
"""
        response = self._make_request("all_cyber_locations")
        return response.get("cyber_locations", [])
    
    def get_environment_info(self) -> Dict[str, Any]:
        """
Get general environment information and statistics.
Returns: Dictionary with environment statistics
"""
        response = self._make_request("environment_info")
        return response.get("environment", {})
    
    def check_cyber_presence(self, location: str) -> bool:
        """
Check if any other Cybers are at a specific location.
Args: location - Location to check
Returns: True if other Cybers are present, False otherwise
"""
        cybers = self.get_cybers_at_location(location)
        return len(cybers) > 0
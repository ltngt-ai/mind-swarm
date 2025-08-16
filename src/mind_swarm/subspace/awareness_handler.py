"""Awareness handler for Cybers to query environmental awareness.

This handler allows Cybers to query their environment for awareness information
such as nearby Cybers, shared resources, and other environmental data.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from mind_swarm.utils.logging import logger


class AwarenessHandler:
    """Handles awareness queries from Cybers through the awareness body file."""
    
    def __init__(self, subspace_root: Path):
        """Initialize the awareness handler.
        
        Args:
            subspace_root: Root path of the subspace
        """
        self.subspace_root = subspace_root
        self.cybers_dir = subspace_root / "cybers"
        
        # Cache for Cyber locations (updated periodically)
        self._location_cache: Dict[str, str] = {}
        self._cache_update_time: Optional[datetime] = None
        self._cache_lock = asyncio.Lock()
        
        logger.info("Initialized awareness handler")
    
    async def _update_location_cache(self):
        """Update the cache of Cyber locations."""
        async with self._cache_lock:
            new_cache = {}
            
            try:
                # Scan all Cyber directories
                cyber_names = await asyncio.to_thread(
                    lambda: [d.name for d in self.cybers_dir.iterdir() if d.is_dir()]
                )
                
                for cyber_name in cyber_names:
                    # Read dynamic context to get location
                    dynamic_context_file = self.cybers_dir / cyber_name / ".internal" / "memory" / "dynamic_context.json"
                    
                    if dynamic_context_file.exists():
                        try:
                            with open(dynamic_context_file, 'r') as f:
                                context = json.load(f)
                                location = context.get("current_location", "/grid/library/knowledge")
                                new_cache[cyber_name] = location
                        except Exception as e:
                            logger.debug(f"Could not read location for {cyber_name}: {e}")
                
                self._location_cache = new_cache
                self._cache_update_time = datetime.now()
                logger.debug(f"Updated location cache: {len(new_cache)} Cybers tracked")
                
            except Exception as e:
                logger.error(f"Failed to update location cache: {e}")
    
    async def _get_cybers_at_location(self, location: str, exclude_cyber: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of Cybers at a specific location.
        
        Args:
            location: The location to check
            exclude_cyber: Name of Cyber to exclude from results (usually the requester)
            
        Returns:
            List of dicts with Cyber information
        """
        # Update cache if stale (older than 5 seconds)
        if (self._cache_update_time is None or 
            (datetime.now() - self._cache_update_time).seconds > 5):
            await self._update_location_cache()
        
        nearby_cybers = []
        for cyber_name, cyber_location in self._location_cache.items():
            if cyber_name != exclude_cyber and cyber_location == location:
                # Get additional Cyber info if available
                registry_file = self.subspace_root / "shared" / "directory" / "cybers.json"
                cyber_info = {"name": cyber_name, "location": location}
                
                # Try to get more info from registry
                if registry_file.exists():
                    try:
                        with open(registry_file, 'r') as f:
                            registry = json.load(f)
                            if cyber_name in registry.get("cybers", {}):
                                reg_info = registry["cybers"][cyber_name]
                                cyber_info.update({
                                    "type": reg_info.get("type", "GENERAL"),
                                    "status": reg_info.get("status", "unknown"),
                                    "capabilities": reg_info.get("capabilities", [])
                                })
                    except Exception:
                        pass
                
                nearby_cybers.append(cyber_info)
        
        return nearby_cybers
    
    async def handle_request(self, cyber_name: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an awareness request from a Cyber.
        
        Args:
            cyber_name: Name of the requesting Cyber
            request: The awareness request
            
        Returns:
            Response dictionary
        """
        request_id = request.get("request_id", "unknown")
        query_type = request.get("query_type", "")
        
        logger.info(f"Awareness request from {cyber_name}: {query_type}")
        
        try:
            if query_type == "nearby_cybers":
                # Get Cybers at the same location
                location = request.get("location")
                if not location:
                    # Get requester's current location
                    dynamic_context_file = self.cybers_dir / cyber_name / ".internal" / "memory" / "dynamic_context.json"
                    if dynamic_context_file.exists():
                        with open(dynamic_context_file, 'r') as f:
                            context = json.load(f)
                            location = context.get("current_location", "/grid/library/knowledge")
                    else:
                        location = "/grid/library/knowledge"
                
                nearby = await self._get_cybers_at_location(location, exclude_cyber=cyber_name)
                
                return {
                    "request_id": request_id,
                    "status": "success",
                    "query_type": query_type,
                    "location": location,
                    "nearby_cybers": nearby,
                    "count": len(nearby)
                }
            
            elif query_type == "all_cyber_locations":
                # Return all Cyber locations (for special queries)
                await self._update_location_cache()
                
                locations = []
                for name, location in self._location_cache.items():
                    if name != cyber_name:  # Exclude requester
                        locations.append({
                            "name": name,
                            "location": location
                        })
                
                return {
                    "request_id": request_id,
                    "status": "success",
                    "query_type": query_type,
                    "cyber_locations": locations,
                    "count": len(locations)
                }
            
            elif query_type == "environment_info":
                # Return general environment information
                grid_path = self.subspace_root / "grid"
                
                # Count resources in various grid locations
                library_items = len(list((grid_path / "library").rglob("*"))) if (grid_path / "library").exists() else 0
                workshop_items = len(list((grid_path / "workshop").rglob("*"))) if (grid_path / "workshop").exists() else 0
                community_items = len(list((grid_path / "community").rglob("*"))) if (grid_path / "community").exists() else 0
                
                return {
                    "request_id": request_id,
                    "status": "success",
                    "query_type": query_type,
                    "environment": {
                        "total_cybers": len(self._location_cache),
                        "library_items": library_items,
                        "workshop_items": workshop_items,
                        "community_items": community_items
                    }
                }
            
            else:
                return {
                    "request_id": request_id,
                    "status": "error",
                    "error": f"Unknown query type: {query_type}",
                    "supported_queries": ["nearby_cybers", "all_cyber_locations", "environment_info"]
                }
                
        except Exception as e:
            logger.error(f"Error handling awareness request from {cyber_name}: {e}")
            return {
                "request_id": request_id,
                "status": "error",
                "error": str(e)
            }
"""
# Location Knowledge API for Cybers

## Core Concept: Semantic Location Memory
The Location Knowledge API provides semantic storage and retrieval for location-based memories,
replacing file-based location tracking with a knowledge database approach.

Location memories are stored with spatial and temporal metadata, enabling rich
location-based memory retrieval and shared experiences between cybers.

## Examples

### Intention: "Remember what I did at this location"
```python
location_knowledge.store_location_memory(
    location="/grid/library/fiction",
    activity="Reading stories and taking notes",
    observations=["Found interesting sci-fi collection", "Met Alice here"],
    tasks_completed=["Read 3 stories", "Organized notes"]
)
```

### Intention: "What do I remember about the library?"
```python
memories = location_knowledge.get_location_memories("/grid/library")
for mem in memories:
    print(f"{mem['timestamp']}: {mem['activity']}")
```

### Intention: "Find locations where I worked on memory tasks"
```python
locations = location_knowledge.search_locations(
    query="memory optimization tasks",
    days_back=7
)
for loc in locations:
    print(f"{loc['location']}: {loc['visit_count']} visits")
```

### Intention: "Share my experience at this location"
```python
location_knowledge.share_location_experience(
    location="/grid/community/school",
    experience="Great place for learning, helpful cybers here",
    rating=5,
    tags=["educational", "collaborative"]
)
```

## Best Practices
1. Store memories immediately after significant activities
2. Use descriptive activity summaries
3. Include observations for richer context
4. Share positive experiences to help other cybers
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("Cyber.location_knowledge")


class LocationKnowledgeError(Exception):
    """Base exception for location knowledge errors."""
    pass


class LocationKnowledge:
    """Manages location-based memory storage and retrieval using the knowledge database."""
    
    def __init__(self, context_or_knowledge):
        """Initialize the Location Knowledge API.
        
        Args:
            context_or_knowledge: Either execution context dict or Knowledge API instance
        """
        if isinstance(context_or_knowledge, dict):
            # Initialize from context
            self.context = context_or_knowledge
            self.cyber_id = context_or_knowledge.get('cyber_id', 'unknown')
            
            # Get Knowledge API from context
            from .knowledge import Knowledge
            memory_api = context_or_knowledge.get('memory_api')
            if not memory_api:
                raise LocationKnowledgeError("Memory API required in context")
            self.knowledge = Knowledge(memory_api)
        else:
            # Direct Knowledge API instance
            self.knowledge = context_or_knowledge
            self.cyber_id = 'unknown'
    
    def store_location_memory(self,
                             location: str,
                             activity: str,
                             observations: List[str] = None,
                             tasks_completed: List[str] = None,
                             cybers_met: List[str] = None,
                             metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store a memory about activities at a location.
        
        Args:
            location: The location path (e.g., "/grid/library")
            activity: Brief description of what was done
            observations: List of things observed
            tasks_completed: List of tasks completed
            cybers_met: List of cybers encountered
            metadata: Additional metadata
            
        Returns:
            Knowledge ID of stored memory
            
        Example:
            mem_id = location_knowledge.store_location_memory(
                location="/grid/workshop",
                activity="Building memory optimization tool",
                observations=["Found useful scripts", "Workshop is well organized"],
                tasks_completed=["Created prototype", "Tested performance"]
            )
        """
        # Generate unique memory ID
        timestamp = datetime.now()
        memory_id = f"location_memory_{self.cyber_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Create semantic content
        semantic_content = f"""
Location Memory: {location}
Cyber: {self.cyber_id}
Time: {timestamp.isoformat()}
Activity: {activity}
"""
        
        if observations:
            semantic_content += "\nObservations:\n"
            for obs in observations:
                semantic_content += f"- {obs}\n"
        
        if tasks_completed:
            semantic_content += "\nTasks Completed:\n"
            for task in tasks_completed:
                semantic_content += f"- {task}\n"
        
        if cybers_met:
            semantic_content += f"\nCybers Met: {', '.join(cybers_met)}\n"
        
        # Prepare metadata
        mem_metadata = {
            "memory_type": "location",
            "location": location,
            "cyber_id": self.cyber_id,
            "activity": activity,
            "timestamp": timestamp.isoformat(),
            "observations": observations or [],
            "tasks_completed": tasks_completed or [],
            "cybers_met": cybers_met or []
        }
        
        if metadata:
            mem_metadata.update(metadata)
        
        # Extract location components for better search
        location_parts = location.strip('/').split('/')
        location_tags = ["location_memory", f"cyber_{self.cyber_id}"]
        location_tags.extend([f"loc_{part}" for part in location_parts])
        
        # Store in knowledge with hierarchical ID
        knowledge_id = f"locations/{self.cyber_id}/{memory_id}"
        
        stored_id = self.knowledge.store(
            content=semantic_content,
            knowledge_id=knowledge_id,
            tags=location_tags,
            personal=True,  # Location memories are personal by default
            metadata=mem_metadata
        )
        
        logger.info(f"Stored location memory {memory_id} for {location}")
        return stored_id
    
    def get_location_memories(self,
                             location: str,
                             days_back: int = 30,
                             limit: int = 10) -> List[Dict[str, Any]]:
        """Get memories for a specific location.
        
        Args:
            location: The location path
            days_back: How many days of history to retrieve
            limit: Maximum number of memories
            
        Returns:
            List of location memories, most recent first
            
        Example:
            library_memories = location_knowledge.get_location_memories(
                "/grid/library",
                days_back=7
            )
        """
        # Build search query
        location_parts = location.strip('/').split('/')
        search_tags = ["location_memory", f"cyber_{self.cyber_id}"]
        search_tags.extend([f"loc_{part}" for part in location_parts])
        
        # Search for memories
        results = self.knowledge.search(
            query=location,
            tags=search_tags,
            limit=limit * 2  # Get extra to filter by time
        )
        
        # Filter by time window
        cutoff_time = datetime.now() - timedelta(days=days_back)
        memories = []
        
        for result in results:
            metadata = result.get('metadata', {})
            if metadata.get('location') == location:
                try:
                    mem_time = datetime.fromisoformat(metadata.get('timestamp', ''))
                    if mem_time >= cutoff_time:
                        memories.append({
                            'timestamp': metadata.get('timestamp'),
                            'activity': metadata.get('activity'),
                            'observations': metadata.get('observations', []),
                            'tasks_completed': metadata.get('tasks_completed', []),
                            'cybers_met': metadata.get('cybers_met', []),
                            'score': result.get('score', 0)
                        })
                except:
                    pass
        
        # Sort by timestamp (most recent first)
        memories.sort(key=lambda x: x['timestamp'], reverse=True)
        return memories[:limit]
    
    def search_locations(self,
                        query: str,
                        days_back: int = 30,
                        limit: int = 10) -> List[Dict[str, Any]]:
        """Search for locations based on activities or observations.
        
        Args:
            query: Search query for activities/observations
            days_back: How many days back to search
            limit: Maximum number of locations
            
        Returns:
            List of locations with visit information
            
        Example:
            memory_locations = location_knowledge.search_locations(
                query="memory optimization",
                days_back=14
            )
        """
        # Search for matching memories
        results = self.knowledge.search(
            query=query,
            tags=["location_memory", f"cyber_{self.cyber_id}"],
            limit=limit * 5  # Get extra to aggregate
        )
        
        # Aggregate by location
        location_data = {}
        cutoff_time = datetime.now() - timedelta(days=days_back)
        
        for result in results:
            metadata = result.get('metadata', {})
            location = metadata.get('location')
            
            if not location:
                continue
            
            try:
                mem_time = datetime.fromisoformat(metadata.get('timestamp', ''))
                if mem_time < cutoff_time:
                    continue
            except:
                continue
            
            if location not in location_data:
                location_data[location] = {
                    'location': location,
                    'visit_count': 0,
                    'activities': [],
                    'last_visit': None,
                    'total_score': 0
                }
            
            location_data[location]['visit_count'] += 1
            location_data[location]['activities'].append(metadata.get('activity', ''))
            location_data[location]['total_score'] += result.get('score', 0)
            
            # Update last visit
            timestamp = metadata.get('timestamp')
            if timestamp:
                if not location_data[location]['last_visit'] or timestamp > location_data[location]['last_visit']:
                    location_data[location]['last_visit'] = timestamp
        
        # Convert to list and sort by relevance
        locations = list(location_data.values())
        locations.sort(key=lambda x: x['total_score'], reverse=True)
        
        return locations[:limit]
    
    def get_location_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get the cyber's location visit history.
        
        Args:
            limit: Maximum number of locations
            
        Returns:
            List of visited locations with timestamps
            
        Example:
            history = location_knowledge.get_location_history()
            for visit in history:
                print(f"{visit['timestamp']}: {visit['location']}")
        """
        # Search for all location memories
        results = self.knowledge.search(
            query="",
            tags=["location_memory", f"cyber_{self.cyber_id}"],
            limit=limit
        )
        
        # Extract location visits
        history = []
        for result in results:
            metadata = result.get('metadata', {})
            history.append({
                'location': metadata.get('location'),
                'timestamp': metadata.get('timestamp'),
                'activity': metadata.get('activity'),
                'duration': metadata.get('duration')  # If tracked
            })
        
        # Sort by timestamp (most recent first)
        history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return history
    
    def share_location_experience(self,
                                 location: str,
                                 experience: str,
                                 rating: int = None,
                                 tags: List[str] = None) -> str:
        """Share an experience about a location with other cybers.
        
        Args:
            location: The location path
            experience: Description of the experience
            rating: Optional rating (1-5)
            tags: Optional tags for categorization
            
        Returns:
            Knowledge ID of shared experience
            
        Example:
            location_knowledge.share_location_experience(
                location="/grid/community/school",
                experience="Excellent place for learning, very helpful community",
                rating=5,
                tags=["educational", "welcoming"]
            )
        """
        # Generate experience ID
        timestamp = datetime.now()
        experience_id = f"location_exp_{self.cyber_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Create semantic content
        semantic_content = f"""
Location Experience: {location}
Shared by: {self.cyber_id}
Date: {timestamp.isoformat()}
"""
        
        if rating:
            semantic_content += f"Rating: {'⭐' * rating} ({rating}/5)\n"
        
        semantic_content += f"\nExperience:\n{experience}\n"
        
        if tags:
            semantic_content += f"\nTags: {', '.join(tags)}\n"
        
        # Prepare metadata
        exp_metadata = {
            "experience_type": "location",
            "location": location,
            "cyber_id": self.cyber_id,
            "experience": experience,
            "rating": rating,
            "timestamp": timestamp.isoformat(),
            "tags": tags or []
        }
        
        # Build tags for search
        exp_tags = ["location_experience", f"cyber_{self.cyber_id}"]
        location_parts = location.strip('/').split('/')
        exp_tags.extend([f"loc_{part}" for part in location_parts])
        if tags:
            exp_tags.extend(tags)
        
        # Store as shared knowledge
        knowledge_id = f"experiences/locations/{experience_id}"
        
        stored_id = self.knowledge.store(
            content=semantic_content,
            knowledge_id=knowledge_id,
            tags=exp_tags,
            personal=False,  # Shared with other cybers
            metadata=exp_metadata
        )
        
        logger.info(f"Shared location experience {experience_id} for {location}")
        return stored_id
    
    def get_location_experiences(self,
                                location: str,
                                limit: int = 10) -> List[Dict[str, Any]]:
        """Get shared experiences about a location from all cybers.
        
        Args:
            location: The location path
            limit: Maximum number of experiences
            
        Returns:
            List of shared experiences
            
        Example:
            experiences = location_knowledge.get_location_experiences("/grid/library")
            for exp in experiences:
                print(f"{exp['cyber_id']}: {exp['experience']} (Rating: {exp['rating']})")
        """
        # Build search tags
        location_parts = location.strip('/').split('/')
        search_tags = ["location_experience"]
        search_tags.extend([f"loc_{part}" for part in location_parts])
        
        # Search for experiences
        results = self.knowledge.search(
            query=location,
            tags=search_tags,
            scope=["shared"],  # Only shared experiences
            limit=limit
        )
        
        # Extract experience data
        experiences = []
        for result in results:
            metadata = result.get('metadata', {})
            if metadata.get('location') == location:
                experiences.append({
                    'cyber_id': metadata.get('cyber_id'),
                    'experience': metadata.get('experience'),
                    'rating': metadata.get('rating'),
                    'timestamp': metadata.get('timestamp'),
                    'tags': metadata.get('tags', []),
                    'score': result.get('score', 0)
                })
        
        # Sort by score (relevance)
        experiences.sort(key=lambda x: x['score'], reverse=True)
        
        return experiences
    
    def get_popular_locations(self, days_back: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """Get popular locations based on cyber activity.
        
        Args:
            days_back: Time window to consider
            limit: Maximum number of locations
            
        Returns:
            List of popular locations with visit counts
            
        Example:
            popular = location_knowledge.get_popular_locations(days_back=3)
            for loc in popular:
                print(f"{loc['location']}: {loc['unique_visitors']} cybers visited")
        """
        # Search for recent location memories and experiences
        cutoff_time = datetime.now() - timedelta(days=days_back)
        
        results = self.knowledge.search(
            query="",
            tags=["location_memory", "location_experience"],
            scope=["shared", "personal"],
            limit=100  # Get many to aggregate
        )
        
        # Aggregate by location
        location_stats = {}
        
        for result in results:
            metadata = result.get('metadata', {})
            location = metadata.get('location')
            cyber_id = metadata.get('cyber_id')
            
            if not location:
                continue
            
            try:
                timestamp = datetime.fromisoformat(metadata.get('timestamp', ''))
                if timestamp < cutoff_time:
                    continue
            except:
                continue
            
            if location not in location_stats:
                location_stats[location] = {
                    'location': location,
                    'visit_count': 0,
                    'unique_visitors': set(),
                    'activities': [],
                    'avg_rating': []
                }
            
            location_stats[location]['visit_count'] += 1
            location_stats[location]['unique_visitors'].add(cyber_id)
            
            if metadata.get('activity'):
                location_stats[location]['activities'].append(metadata['activity'])
            
            if metadata.get('rating'):
                location_stats[location]['avg_rating'].append(metadata['rating'])
        
        # Convert sets to counts and calculate averages
        popular = []
        for location, stats in location_stats.items():
            avg_rating = sum(stats['avg_rating']) / len(stats['avg_rating']) if stats['avg_rating'] else None
            
            popular.append({
                'location': location,
                'visit_count': stats['visit_count'],
                'unique_visitors': len(stats['unique_visitors']),
                'sample_activities': stats['activities'][:3],
                'avg_rating': avg_rating
            })
        
        # Sort by unique visitors
        popular.sort(key=lambda x: x['unique_visitors'], reverse=True)
        
        return popular[:limit]
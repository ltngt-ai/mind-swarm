"""
# Reflection Knowledge API for Cybers

## Core Concept: Semantic Reflection Storage
The Reflection Knowledge API provides semantic storage and retrieval for cognitive reflections
using a knowledge database approach.

Reflections are stored with insights, patterns, and learnings, enabling
cybers to build on past experiences and share wisdom with the hive mind.

## Examples

### Intention: "Store a reflection from the current cycle"
```python
reflection_knowledge.store_reflection(
    insights=["Memory compression works better with chunking", "Need to clean old observations"],
    successes=["Completed memory optimization task", "Helped Alice with her code"],
    challenges=["Struggled with token limits", "Coordination with Bob was difficult"],
    next_priorities=["Implement chunking algorithm", "Review Bob's feedback"]
)
```

### Intention: "Get my recent reflections"
```python
recent = reflection_knowledge.get_recent_reflections(days_back=3)
for reflection in recent:
    print(f"Cycle {reflection['cycle']}: {reflection['insights']}")
```

### Intention: "Search for reflections about a topic"
```python
memory_insights = reflection_knowledge.search_reflections(
    query="memory optimization techniques",
    include_shared=True
)
for ref in memory_insights:
    print(f"{ref['cyber_id']}: {ref['insights']}")
```

### Intention: "Share a valuable insight with the hive"
```python
reflection_knowledge.share_insight(
    insight="Chunking memory by 4KB blocks reduces token usage by 30%",
    category="optimization",
    tags=["memory", "performance", "tokens"]
)
```

## Best Practices
1. Reflect at the end of each cognitive cycle
2. Be specific about successes and challenges
3. Share generalizable insights with the hive
4. Use reflections to track progress over time
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("Cyber.reflection_knowledge")


class ReflectionKnowledgeError(Exception):
    """Base exception for reflection knowledge errors."""
    pass


class ReflectionKnowledge:
    """Manages reflection storage and retrieval using the knowledge database."""
    
    def __init__(self, context_or_knowledge):
        """Initialize the Reflection Knowledge API.
        
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
                raise ReflectionKnowledgeError("Memory API required in context")
            self.knowledge = Knowledge(memory_api)
            
            # Try to get cycle count from context
            self.current_cycle = context_or_knowledge.get('cycle_count', 0)
        else:
            # Direct Knowledge API instance
            self.knowledge = context_or_knowledge
            self.cyber_id = 'unknown'
            self.current_cycle = 0
    
    def store_reflection(self,
                        insights: List[str] = None,
                        successes: List[str] = None,
                        challenges: List[str] = None,
                        next_priorities: List[str] = None,
                        patterns_noticed: List[str] = None,
                        cycle_number: Optional[int] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store a reflection from a cognitive cycle.
        
        Args:
            insights: Key insights or learnings
            successes: Things that went well
            challenges: Difficulties encountered
            next_priorities: Priorities for next cycles
            patterns_noticed: Patterns observed
            cycle_number: Specific cycle number (defaults to current)
            metadata: Additional metadata
            
        Returns:
            Knowledge ID of stored reflection
            
        Example:
            ref_id = reflection_knowledge.store_reflection(
                insights=["Token limits require better chunking"],
                successes=["Optimized memory by 40%"],
                challenges=["Coordination was slow"],
                next_priorities=["Implement new chunking algorithm"]
            )
        """
        if cycle_number is None:
            cycle_number = self.current_cycle
        
        # Generate reflection ID
        timestamp = datetime.now()
        reflection_id = f"reflection_{self.cyber_id}_cycle{cycle_number}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Create semantic content
        semantic_content = f"""
Reflection - Cycle {cycle_number}
Cyber: {self.cyber_id}
Time: {timestamp.isoformat()}
"""
        
        if insights:
            semantic_content += "\nInsights:\n"
            for insight in insights:
                semantic_content += f"- {insight}\n"
        
        if successes:
            semantic_content += "\nSuccesses:\n"
            for success in successes:
                semantic_content += f"- {success}\n"
        
        if challenges:
            semantic_content += "\nChallenges:\n"
            for challenge in challenges:
                semantic_content += f"- {challenge}\n"
        
        if next_priorities:
            semantic_content += "\nNext Priorities:\n"
            for priority in next_priorities:
                semantic_content += f"- {priority}\n"
        
        if patterns_noticed:
            semantic_content += "\nPatterns Noticed:\n"
            for pattern in patterns_noticed:
                semantic_content += f"- {pattern}\n"
        
        # Prepare metadata
        ref_metadata = {
            "reflection_type": "cycle",
            "cyber_id": self.cyber_id,
            "cycle_number": cycle_number,
            "timestamp": timestamp.isoformat(),
            "insights": insights or [],
            "successes": successes or [],
            "challenges": challenges or [],
            "next_priorities": next_priorities or [],
            "patterns_noticed": patterns_noticed or []
        }
        
        if metadata:
            ref_metadata.update(metadata)
        
        # Build tags for search
        ref_tags = ["reflection", f"cyber_{self.cyber_id}", f"cycle_{cycle_number}"]
        
        # Add topic tags from content
        all_content = " ".join([
            " ".join(insights or []),
            " ".join(successes or []),
            " ".join(challenges or [])
        ])
        
        # Extract key topics (simple keyword extraction)
        if "memory" in all_content.lower():
            ref_tags.append("topic_memory")
        if "task" in all_content.lower():
            ref_tags.append("topic_tasks")
        if "communication" in all_content.lower() or "message" in all_content.lower():
            ref_tags.append("topic_communication")
        
        # Store in knowledge with hierarchical ID
        knowledge_id = f"reflections/{self.cyber_id}/{reflection_id}"
        
        stored_id = self.knowledge.store(
            content=semantic_content,
            knowledge_id=knowledge_id,
            tags=ref_tags,
            personal=True,  # Reflections are personal by default
            metadata=ref_metadata
        )
        
        logger.info(f"Stored reflection {reflection_id} for cycle {cycle_number}")
        return stored_id
    
    def get_recent_reflections(self,
                              days_back: int = 7,
                              limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent reflections for this cyber.
        
        Args:
            days_back: How many days of history
            limit: Maximum number of reflections
            
        Returns:
            List of reflections, most recent first
            
        Example:
            recent = reflection_knowledge.get_recent_reflections(days_back=3)
            for ref in recent:
                print(f"Cycle {ref['cycle_number']}: {', '.join(ref['insights'])}")
        """
        # Search for cyber's reflections
        results = self.knowledge.search(
            query="",
            tags=["reflection", f"cyber_{self.cyber_id}"],
            limit=limit * 2  # Get extra to filter by time
        )
        
        # Filter by time window
        cutoff_time = datetime.now() - timedelta(days=days_back)
        reflections = []
        
        for result in results:
            metadata = result.get('metadata', {})
            
            try:
                ref_time = datetime.fromisoformat(metadata.get('timestamp', ''))
                if ref_time >= cutoff_time:
                    reflections.append({
                        'cycle_number': metadata.get('cycle_number'),
                        'timestamp': metadata.get('timestamp'),
                        'insights': metadata.get('insights', []),
                        'successes': metadata.get('successes', []),
                        'challenges': metadata.get('challenges', []),
                        'next_priorities': metadata.get('next_priorities', []),
                        'patterns_noticed': metadata.get('patterns_noticed', [])
                    })
            except:
                pass
        
        # Sort by cycle number (most recent first)
        reflections.sort(key=lambda x: x.get('cycle_number', 0), reverse=True)
        return reflections[:limit]
    
    def get_last_reflection(self) -> Optional[Dict[str, Any]]:
        """Get the most recent reflection.
        
        Returns:
            Last reflection or None if no reflections
            
        Example:
            last = reflection_knowledge.get_last_reflection()
            if last:
                print(f"Last reflected in cycle {last['cycle_number']}")
        """
        recent = self.get_recent_reflections(days_back=30, limit=1)
        return recent[0] if recent else None
    
    def search_reflections(self,
                          query: str,
                          include_shared: bool = False,
                          days_back: int = 30,
                          limit: int = 20) -> List[Dict[str, Any]]:
        """Search reflections using semantic search.
        
        Args:
            query: Search query for insights/patterns
            include_shared: Include shared insights from other cybers
            days_back: How many days back to search
            limit: Maximum number of results
            
        Returns:
            List of matching reflections
            
        Example:
            memory_reflections = reflection_knowledge.search_reflections(
                query="memory optimization token limits",
                include_shared=True
            )
        """
        # Build search scope
        scope = ["personal"]
        if include_shared:
            scope.append("shared")
        
        # Search for matching reflections
        results = self.knowledge.search(
            query=query,
            tags=["reflection"],
            scope=scope,
            limit=limit * 2  # Get extra to filter
        )
        
        # Filter by time window
        cutoff_time = datetime.now() - timedelta(days=days_back)
        reflections = []
        
        for result in results:
            metadata = result.get('metadata', {})
            
            try:
                ref_time = datetime.fromisoformat(metadata.get('timestamp', ''))
                if ref_time >= cutoff_time:
                    reflections.append({
                        'cyber_id': metadata.get('cyber_id'),
                        'cycle_number': metadata.get('cycle_number'),
                        'timestamp': metadata.get('timestamp'),
                        'insights': metadata.get('insights', []),
                        'patterns_noticed': metadata.get('patterns_noticed', []),
                        'score': result.get('score', 0)
                    })
            except:
                pass
        
        # Sort by relevance
        reflections.sort(key=lambda x: x['score'], reverse=True)
        return reflections[:limit]
    
    def share_insight(self,
                     insight: str,
                     category: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     supporting_evidence: Optional[List[str]] = None) -> str:
        """Share a valuable insight with the hive mind.
        
        Args:
            insight: The insight to share
            category: Category (optimization, debugging, coordination, etc.)
            tags: Tags for discovery
            supporting_evidence: Evidence or examples
            
        Returns:
            Knowledge ID of shared insight
            
        Example:
            insight_id = reflection_knowledge.share_insight(
                insight="Parallel task execution improves throughput by 3x",
                category="optimization",
                tags=["performance", "parallelism"],
                supporting_evidence=["Tested with 10 tasks", "CPU usage stayed under 50%"]
            )
        """
        # Generate insight ID
        timestamp = datetime.now()
        insight_id = f"insight_{self.cyber_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Create semantic content
        semantic_content = f"""
Shared Insight
From: {self.cyber_id}
Date: {timestamp.isoformat()}
"""
        
        if category:
            semantic_content += f"Category: {category}\n"
        
        semantic_content += f"\nInsight:\n{insight}\n"
        
        if supporting_evidence:
            semantic_content += "\nSupporting Evidence:\n"
            for evidence in supporting_evidence:
                semantic_content += f"- {evidence}\n"
        
        if tags:
            semantic_content += f"\nTags: {', '.join(tags)}\n"
        
        # Prepare metadata
        insight_metadata = {
            "insight_type": "shared",
            "cyber_id": self.cyber_id,
            "insight": insight,
            "category": category,
            "timestamp": timestamp.isoformat(),
            "supporting_evidence": supporting_evidence or [],
            "tags": tags or []
        }
        
        # Build tags for search
        insight_tags = ["reflection", "insight", "shared", f"cyber_{self.cyber_id}"]
        if category:
            insight_tags.append(f"category_{category}")
        if tags:
            insight_tags.extend(tags)
        
        # Store as shared knowledge
        knowledge_id = f"insights/shared/{insight_id}"
        
        stored_id = self.knowledge.store(
            content=semantic_content,
            knowledge_id=knowledge_id,
            tags=insight_tags,
            personal=False,  # Shared with hive mind
            metadata=insight_metadata
        )
        
        logger.info(f"Shared insight {insight_id}")
        return stored_id
    
    def get_shared_insights(self,
                           category: Optional[str] = None,
                           days_back: int = 30,
                           limit: int = 20) -> List[Dict[str, Any]]:
        """Get shared insights from the hive mind.
        
        Args:
            category: Filter by category
            days_back: How many days back to look
            limit: Maximum number of insights
            
        Returns:
            List of shared insights
            
        Example:
            optimization_insights = reflection_knowledge.get_shared_insights(
                category="optimization",
                days_back=7
            )
        """
        # Build search tags
        tags = ["reflection", "insight", "shared"]
        if category:
            tags.append(f"category_{category}")
        
        # Search for shared insights
        results = self.knowledge.search(
            query="",
            tags=tags,
            scope=["shared"],
            limit=limit * 2  # Get extra to filter
        )
        
        # Filter by time window
        cutoff_time = datetime.now() - timedelta(days=days_back)
        insights = []
        
        for result in results:
            metadata = result.get('metadata', {})
            
            try:
                insight_time = datetime.fromisoformat(metadata.get('timestamp', ''))
                if insight_time >= cutoff_time:
                    insights.append({
                        'cyber_id': metadata.get('cyber_id'),
                        'insight': metadata.get('insight'),
                        'category': metadata.get('category'),
                        'supporting_evidence': metadata.get('supporting_evidence', []),
                        'timestamp': metadata.get('timestamp'),
                        'tags': metadata.get('tags', [])
                    })
            except:
                pass
        
        # Sort by timestamp (most recent first)
        insights.sort(key=lambda x: x['timestamp'], reverse=True)
        return insights[:limit]
    
    def get_patterns_over_time(self,
                              topic: str,
                              days_back: int = 30) -> Dict[str, Any]:
        """Analyze patterns in reflections over time.
        
        Args:
            topic: Topic to analyze (e.g., "memory", "tasks")
            days_back: Time period to analyze
            
        Returns:
            Pattern analysis with trends
            
        Example:
            memory_patterns = reflection_knowledge.get_patterns_over_time(
                topic="memory",
                days_back=14
            )
        """
        # Search for reflections mentioning the topic
        reflections = self.search_reflections(
            query=topic,
            include_shared=False,
            days_back=days_back,
            limit=100
        )
        
        # Analyze patterns
        patterns = {
            'topic': topic,
            'period_days': days_back,
            'total_reflections': len(reflections),
            'common_insights': {},
            'common_challenges': {},
            'trend': []
        }
        
        # Count common themes
        for ref in reflections:
            # Count insights
            for insight in ref.get('insights', []):
                key = insight[:50]  # Truncate for grouping
                patterns['common_insights'][key] = patterns['common_insights'].get(key, 0) + 1
            
            # Track over time (simple daily buckets)
            try:
                ref_date = datetime.fromisoformat(ref['timestamp']).date()
                date_str = ref_date.isoformat()
                
                # Find or create bucket
                bucket = None
                for b in patterns['trend']:
                    if b['date'] == date_str:
                        bucket = b
                        break
                
                if not bucket:
                    bucket = {'date': date_str, 'count': 0, 'sentiment': 0}
                    patterns['trend'].append(bucket)
                
                bucket['count'] += 1
                
                # Simple sentiment based on successes vs challenges
                sentiment = len(ref.get('successes', [])) - len(ref.get('challenges', []))
                bucket['sentiment'] += sentiment
                
            except:
                pass
        
        # Sort trends by date
        patterns['trend'].sort(key=lambda x: x['date'])
        
        # Get top insights
        if patterns['common_insights']:
            sorted_insights = sorted(patterns['common_insights'].items(), 
                                    key=lambda x: x[1], reverse=True)
            patterns['top_insights'] = [k for k, v in sorted_insights[:5]]
        
        return patterns
    
    def get_improvement_suggestions(self) -> List[str]:
        """Get suggestions based on recent reflections.
        
        Returns:
            List of improvement suggestions
            
        Example:
            suggestions = reflection_knowledge.get_improvement_suggestions()
            for suggestion in suggestions:
                print(f"Consider: {suggestion}")
        """
        suggestions = []
        
        # Get recent reflections
        recent = self.get_recent_reflections(days_back=7, limit=10)
        
        if not recent:
            return ["Start reflecting on your cycles to track progress"]
        
        # Analyze patterns
        all_challenges = []
        all_priorities = []
        
        for ref in recent:
            all_challenges.extend(ref.get('challenges', []))
            all_priorities.extend(ref.get('next_priorities', []))
        
        # Look for recurring challenges
        challenge_counts = {}
        for challenge in all_challenges:
            key = challenge[:30]  # Group similar challenges
            challenge_counts[key] = challenge_counts.get(key, 0) + 1
        
        # Suggest addressing recurring challenges
        for challenge, count in challenge_counts.items():
            if count >= 3:
                suggestions.append(f"Recurring challenge detected: '{challenge}...' - Consider dedicated focus")
        
        # Check if priorities are being completed
        if len(all_priorities) > len(recent) * 2:
            suggestions.append("Many incomplete priorities - consider smaller, more achievable goals")
        
        # Check reflection frequency
        if len(recent) < 5:
            suggestions.append("Reflect more frequently to better track progress")
        
        return suggestions[:5]  # Return top 5 suggestions
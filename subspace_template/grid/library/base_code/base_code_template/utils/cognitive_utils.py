"""Cognitive-specific utility functions.

This module provides helper functions specific to cognitive
processing, data formatting, and validation.
"""

import hashlib
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger("agent.utils.cognitive")


class CognitiveUtils:
    """Utilities for cognitive processing and data management."""
    
    @staticmethod
    def generate_unique_id(prefix: str = "", content: str = "") -> str:
        """Generate a unique ID for cognitive elements.
        
        Args:
            prefix: Optional prefix for the ID
            content: Optional content to include in hash
            
        Returns:
            Unique identifier string
        """
        timestamp = datetime.now().isoformat()
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8] if content else ""
        
        if prefix:
            return f"{prefix}_{timestamp}_{content_hash}" if content_hash else f"{prefix}_{timestamp}"
        else:
            return f"{timestamp}_{content_hash}" if content_hash else timestamp
    
    @staticmethod
    def format_cognitive_output(output: Dict[str, Any], 
                              display_fields: Optional[List[str]] = None) -> str:
        """Format cognitive output for display.
        
        Args:
            output: Output dictionary to format
            display_fields: Specific fields to display (None for all)
            
        Returns:
            Formatted string representation
        """
        if not output:
            return "No output"
            
        lines = []
        fields_to_show = display_fields or list(output.keys())
        
        for field in fields_to_show:
            if field in output:
                value = output[field]
                if isinstance(value, (list, dict)):
                    lines.append(f"{field}: {len(value)} items")
                else:
                    lines.append(f"{field}: {value}")
                    
        return "\n".join(lines)
    
    @staticmethod
    def validate_cognitive_structure(data: Dict[str, Any], 
                                   required_fields: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate cognitive data structure.
        
        Args:
            data: Data to validate
            required_fields: List of required field names
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(data, dict):
            return False, "Data must be a dictionary"
            
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
                
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
            
        return True, None
    
    @staticmethod
    def merge_cognitive_results(results: List[Dict[str, Any]], 
                              strategy: str = "latest") -> Dict[str, Any]:
        """Merge multiple cognitive results.
        
        Args:
            results: List of result dictionaries
            strategy: Merge strategy ('latest', 'combine', 'priority')
            
        Returns:
            Merged result dictionary
        """
        if not results:
            return {}
            
        if strategy == "latest":
            # Return the most recent result
            return results[-1] if results else {}
            
        elif strategy == "combine":
            # Combine all results
            merged = {}
            for result in results:
                for key, value in result.items():
                    if key not in merged:
                        merged[key] = value
                    elif isinstance(value, list) and isinstance(merged[key], list):
                        merged[key].extend(value)
                    elif isinstance(value, dict) and isinstance(merged[key], dict):
                        merged[key].update(value)
            return merged
            
        elif strategy == "priority":
            # Use priority field to determine which to keep
            sorted_results = sorted(
                results, 
                key=lambda x: x.get("priority", 0), 
                reverse=True
            )
            return sorted_results[0] if sorted_results else {}
            
        else:
            return results[0] if results else {}
    
    @staticmethod
    def calculate_time_delta(start_time: datetime, 
                           end_time: Optional[datetime] = None) -> Dict[str, float]:
        """Calculate time delta with useful metrics.
        
        Args:
            start_time: Start time
            end_time: End time (None for current time)
            
        Returns:
            Dict with time metrics
        """
        if end_time is None:
            end_time = datetime.now()
            
        delta = end_time - start_time
        total_seconds = delta.total_seconds()
        
        return {
            "total_seconds": total_seconds,
            "minutes": total_seconds / 60,
            "hours": total_seconds / 3600,
            "human_readable": CognitiveUtils._format_duration(total_seconds)
        }
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration in human-readable form.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Human-readable duration string
        """
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"
    
    @staticmethod
    def extract_key_concepts(text: str, max_concepts: int = 5) -> List[str]:
        """Extract key concepts from text.
        
        Simple implementation - can be enhanced with NLP.
        
        Args:
            text: Text to analyze
            max_concepts: Maximum number of concepts to extract
            
        Returns:
            List of key concepts
        """
        # Simple word frequency approach
        # Remove common words and extract most frequent
        common_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "can", "this", "that",
            "these", "those", "i", "you", "he", "she", "it", "we", "they"
        }
        
        # Tokenize and count
        words = text.lower().split()
        word_count = {}
        
        for word in words:
            # Clean punctuation
            word = word.strip(".,!?;:\"'")
            if word and word not in common_words and len(word) > 2:
                word_count[word] = word_count.get(word, 0) + 1
        
        # Sort by frequency
        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
        
        # Return top concepts
        return [word for word, count in sorted_words[:max_concepts]]
    
    @staticmethod
    def calculate_confidence_score(factors: Dict[str, float]) -> float:
        """Calculate overall confidence score from multiple factors.
        
        Args:
            factors: Dict of factor_name -> score (0.0 to 1.0)
            
        Returns:
            Combined confidence score (0.0 to 1.0)
        """
        if not factors:
            return 0.5  # Default neutral confidence
            
        # Weighted average - can be customized
        total_weight = 0
        weighted_sum = 0
        
        # Default weights (can be customized)
        default_weights = {
            "relevance": 2.0,
            "recency": 1.5,
            "reliability": 2.0,
            "completeness": 1.0
        }
        
        for factor, score in factors.items():
            weight = default_weights.get(factor, 1.0)
            weighted_sum += score * weight
            total_weight += weight
            
        return weighted_sum / total_weight if total_weight > 0 else 0.5
    
    @staticmethod
    def format_thinking_request(task: str, context: Dict[str, Any], 
                              request_type: str = "general") -> Dict[str, Any]:
        """Format a standardized thinking request.
        
        Args:
            task: Task description
            context: Context information
            request_type: Type of request
            
        Returns:
            Formatted thinking request
        """
        return {
            "signature": {
                "task": task,
                "type": request_type,
                "timestamp": datetime.now().isoformat()
            },
            "context": context,
            "request_id": CognitiveUtils.generate_unique_id("think"),
            "metadata": {
                "formatted_by": "CognitiveUtils",
                "version": "1.0"
            }
        }
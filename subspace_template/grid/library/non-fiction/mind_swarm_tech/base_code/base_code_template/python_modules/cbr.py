"""
# Case-Based Reasoning (CBR) API for Cybers

## Core Concept: Learning from Past Solutions
The CBR API enables cybers to store, retrieve, and learn from successful problem-solving 
experiences. It provides semantic similarity-based retrieval of past cases to guide 
current decision-making and stores new cases with success scores for future reference.

## Examples

### Intention: "I want to find similar past solutions to my current problem."
```python
# During decision stage - retrieve relevant cases
current_context = "Need to analyze data files and generate a report"
similar_cases = cbr.retrieve_similar_cases(current_context, limit=3)
for case in similar_cases:
    print(f"Score: {case['metadata']['success_score']:.2f}")
    print(f"Problem: {case['problem_context']}")
    print(f"Solution: {case['solution']}")
```

### Intention: "I want to store this successful solution for future use."
```python
# During reflection stage - store successful case
case_id = cbr.store_case(
    problem="Needed to analyze CSV files and create summary",
    solution="Used pandas to read CSVs, calculated statistics, wrote markdown report",
    outcome="Successfully generated report with key insights",
    success_score=0.85,
    tags=["data_analysis", "reporting"]
)
print(f"Stored case: {case_id}")
```

### Intention: "I want to update the score of a case I just reused."
```python
# After successfully reusing a case
cbr.update_case_score("case_123", new_score=0.9, reused=True)
```

### Intention: "I want to see statistics about CBR usage."
```python
stats = cbr.get_case_statistics()
print(f"Total cases: {stats['total_cases']}")
print(f"Average success score: {stats['avg_success_score']:.2f}")
print(f"Cases reused: {stats['reuse_count']}")
```

### Intention: "I want to share a particularly good solution with other cybers."
```python
# Share successful case with the hive mind
cbr.share_case("case_123")
```

## Metadata Fields
Cases include:
- **case_id**: Unique identifier
- **success_score**: Float 0.0-1.0 indicating solution success
- **usage_count**: How many times the case has been retrieved
- **cyber_id**: Which cyber created the case
- **timestamp**: When the case was created
- **tags**: Categories for the case
- **shared**: Whether the case is shared with other cybers
"""

import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class CBRError(Exception):
    """Base exception for CBR API errors."""
    pass


class CBR:
    """
    Case-Based Reasoning API for cybers to learn from past problem-solving experiences.
    """
    
    def __init__(self, memory_context):
        """
        Initialize the CBR API.
        
        Args:
            memory_context: The Memory instance to access context
        """
        self.memory = memory_context
        self.cbr_file = Path("/personal/.internal/cbr_api")
        self.request_counter = 0
        self._last_request_time = 0
        self._min_request_interval = 0.1  # Rate limiting
        
    def retrieve_similar_cases(self, context: str, limit: int = 3, 
                              min_score: float = 0.5, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Retrieve similar past cases based on current context.
        
        Args:
            context: Current problem context to match against
            limit: Maximum number of cases to retrieve (max 5)
            min_score: Minimum similarity score to include (0-1)
            timeout: How long to wait for response
            
        Returns:
            List of similar cases sorted by relevance, each containing:
            {
                'case_id': str,           # Unique case identifier
                'problem_context': str,   # Original problem description
                'solution': str,          # Solution that was applied
                'outcome': str,           # What happened
                'metadata': {
                    'success_score': float,  # How successful (0-1)
                    'cyber_id': str,         # Who solved it
                    'timestamp': str,        # When it was solved
                    'usage_count': int,      # Times reused
                    'tags': list,           # Categories
                    'shared': bool          # If shared with hive
                },
                'similarity': float,      # How similar to current context (0-1)
                'weighted_score': float   # Combined similarity and success score
            }
        """
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Prepare request
        request_id = self._generate_request_id()
        
        request = {
            "request_id": request_id,
            "operation": "retrieve",
            "context": context,
            "options": {
                "limit": min(limit, 5),  # Cap at 5
                "min_score": min_score
            }
        }
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            return response.get("cases", [])
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"CBR retrieval failed: {error}")
            return []
    
    def store_case(self, problem: str, solution: str, outcome: str,
                  success_score: float = 0.7, tags: Optional[List[str]] = None,
                  metadata: Optional[Dict[str, Any]] = None,
                  timeout: float = 5.0) -> Optional[str]:
        """
        Store a new case for future reference.
        
        Args:
            problem: Description of the problem that was solved
            solution: Description of the solution approach
            outcome: What happened when the solution was applied
            success_score: How successful the solution was (0-1)
            tags: Optional categorization tags
            metadata: Additional metadata to store
            timeout: How long to wait for response
            
        Returns:
            Case ID if successfully stored, None otherwise
        """
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Validate success score
        if not 0.0 <= success_score <= 1.0:
            raise CBRError(f"Success score must be between 0 and 1, got {success_score}")
        
        # Prepare request
        request_id = self._generate_request_id()
        
        # Build case structure
        case = {
            "problem_context": problem,
            "solution": solution,
            "outcome": outcome,
            "metadata": {
                "success_score": success_score,
                "tags": tags or [],
                "shared": False,  # Default to personal
                "usage_count": 0,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Add any additional metadata
        if metadata:
            case["metadata"].update(metadata)
        
        request = {
            "request_id": request_id,
            "operation": "store",
            "case": case
        }
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            case_id = response.get("case_id")
            logger.info(f"Stored CBR case: {case_id}")
            return case_id
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"CBR store failed: {error}")
            return None
    
    def update_case_score(self, case_id: str, new_score: Optional[float] = None,
                         reused: bool = False, timeout: float = 5.0) -> bool:
        """
        Update the success score of an existing case.
        
        Args:
            case_id: ID of the case to update
            new_score: New success score (0-1), if provided
            reused: Whether the case was just successfully reused
            timeout: How long to wait for response
            
        Returns:
            True if successfully updated, False otherwise
        """
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Validate score if provided
        if new_score is not None and not 0.0 <= new_score <= 1.0:
            raise CBRError(f"Success score must be between 0 and 1, got {new_score}")
        
        # Prepare request
        request_id = self._generate_request_id()
        
        request = {
            "request_id": request_id,
            "operation": "update_score",
            "case_id": case_id,
            "updates": {}
        }
        
        if new_score is not None:
            request["updates"]["success_score"] = new_score
        if reused:
            request["updates"]["increment_usage"] = True
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            logger.info(f"Updated CBR case score: {case_id}")
            return True
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"CBR update failed: {error}")
            return False
    
    def get_case(self, case_id: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """
        Get a specific case by ID.
        
        Args:
            case_id: ID of the case to retrieve
            timeout: How long to wait for response
            
        Returns:
            Case dictionary if found, None otherwise
        """
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Prepare request
        request_id = self._generate_request_id()
        
        request = {
            "request_id": request_id,
            "operation": "get",
            "case_id": case_id
        }
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            return response.get("case")
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"CBR get failed: {error}")
            return None
    
    def share_case(self, case_id: str, timeout: float = 5.0) -> bool:
        """
        Share a case with other cybers in the hive mind.
        
        Args:
            case_id: ID of the case to share
            timeout: How long to wait for response
            
        Returns:
            True if successfully shared, False otherwise
        """
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Prepare request
        request_id = self._generate_request_id()
        
        request = {
            "request_id": request_id,
            "operation": "share",
            "case_id": case_id
        }
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            logger.info(f"Shared CBR case: {case_id}")
            return True
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"CBR share failed: {error}")
            return False
    
    def forget_case(self, case_id: str, timeout: float = 5.0) -> bool:
        """
        Remove a case from CBR storage.
        
        Args:
            case_id: ID of the case to remove
            timeout: How long to wait for response
            
        Returns:
            True if successfully removed, False otherwise
        """
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Prepare request
        request_id = self._generate_request_id()
        
        request = {
            "request_id": request_id,
            "operation": "forget",
            "case_id": case_id
        }
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            logger.info(f"Forgot CBR case: {case_id}")
            return True
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"CBR forget failed: {error}")
            return False
    
    def get_case_statistics(self, timeout: float = 5.0) -> Dict[str, Any]:
        """
        Get statistics about CBR usage.
        
        Args:
            timeout: How long to wait for response
            
        Returns:
            Dictionary with statistics:
            {
                'total_cases': int,          # Total stored cases
                'personal_cases': int,       # Personal cases
                'shared_cases': int,         # Shared cases
                'avg_success_score': float,  # Average success score
                'reuse_count': int,          # Total reuses
                'top_tags': list,           # Most common tags
                'oldest_case': str,         # Timestamp of oldest
                'newest_case': str          # Timestamp of newest
            }
        """
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Prepare request
        request_id = self._generate_request_id()
        
        request = {
            "request_id": request_id,
            "operation": "statistics"
        }
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            return response.get("statistics", {})
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"CBR statistics failed: {error}")
            return {}
    
    def search_by_tags(self, tags: List[str], limit: int = 5,
                      timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Search for cases by tags.
        
        Args:
            tags: Tags to search for
            limit: Maximum results
            timeout: How long to wait
            
        Returns:
            List of matching cases
        """
        # Build a query from tags
        query = f"cases with tags: {', '.join(tags)}"
        return self.retrieve_similar_cases(query, limit=limit, timeout=timeout)
    
    def get_recent_cases(self, days: int = 7, limit: int = 10,
                        timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Get recently stored cases.
        
        Args:
            days: How many days back to look
            limit: Maximum results
            timeout: How long to wait
            
        Returns:
            List of recent cases
        """
        # Rate limiting
        self._wait_for_rate_limit()
        
        # Prepare request
        request_id = self._generate_request_id()
        
        request = {
            "request_id": request_id,
            "operation": "recent",
            "options": {
                "days": days,
                "limit": limit
            }
        }
        
        # Send request and get response
        response = self._send_request(request, timeout)
        
        if response and response.get("status") == "success":
            return response.get("cases", [])
        else:
            error = response.get("error", "Unknown error") if response else "Timeout"
            logger.warning(f"CBR recent cases failed: {error}")
            return []
    
    # Private helper methods
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        cyber_id = self.memory._context.get('cyber_id', 'unknown')
        self.request_counter += 1
        timestamp = int(time.time() * 1000)
        return f"cbr_{cyber_id}_{timestamp}_{self.request_counter}"
    
    def _wait_for_rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            time.sleep(self._min_request_interval - time_since_last)
        self._last_request_time = time.time()
    
    def _send_request(self, request: Dict[str, Any], timeout: float) -> Optional[Dict[str, Any]]:
        """
        Send a request to the CBR body file and wait for response.
        
        Args:
            request: Request dictionary
            timeout: How long to wait for response
            
        Returns:
            Response dictionary or None if timeout
        """
        try:
            # Write request with end marker
            request_text = json.dumps(request, indent=2)
            full_request = f"{request_text}\n<<<END_CBR_REQUEST>>>"
            self.cbr_file.write_text(full_request)
            
            # Wait for response with completion marker
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    content = self.cbr_file.read_text()
                    
                    # Check for completion marker
                    if "<<<CBR_COMPLETE>>>" in content:
                        # Extract response (everything before the marker)
                        response_text = content.split("<<<CBR_COMPLETE>>>")[0].strip()
                        
                        # Parse the response
                        response = json.loads(response_text)
                        
                        # Verify this is our response
                        if response.get("request_id") == request["request_id"]:
                            # Clear the file for next request
                            self.cbr_file.write_text("")
                            return response
                        
                except json.JSONDecodeError:
                    # Response might still be writing
                    pass
                except Exception as e:
                    logger.error(f"Error reading CBR response: {e}")
                    
                # Small delay before checking again
                time.sleep(0.05)
            
            # Timeout reached - clear file
            self.cbr_file.write_text("")
            logger.warning(f"CBR request timed out after {timeout}s")
            return None
            
        except Exception as e:
            logger.error(f"Error sending CBR request: {e}")
            return None
    
    def __repr__(self) -> str:
        """String representation."""
        cyber_id = self.memory._context.get('cyber_id', 'unknown')
        return f"CBR(cyber_id='{cyber_id}')"
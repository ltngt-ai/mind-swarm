"""Execution state tracking for the cognitive loop.

This module tracks execution context, history, and provides
insights into cognitive loop performance.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

from ..utils.json_utils import DateTimeEncoder, safe_json_encode, safe_json_decode
from ..utils.file_utils import FileManager
from ..utils.cognitive_utils import CognitiveUtils

logger = logging.getLogger("Cyber.state.execution")


class ExecutionStateTracker:
    """Tracks execution state and provides performance insights."""
    
    def __init__(self, cyber_id: str, memory_dir: Path):
        """Initialize execution state tracker.
        
        Args:
            cyber_id: Cyber identifier
            memory_dir: Directory for state persistence
        """
        self.cyber_id = cyber_id
        self.memory_dir = memory_dir
        self.file_manager = FileManager()
        self.cognitive_utils = CognitiveUtils()
        
        # Execution tracking
        self.current_execution = None
        self.execution_history = []
        self.max_history = 1000
        
        # Performance metrics
        self.metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_duration": 0.0,
            "by_state": defaultdict(lambda: {"count": 0, "total_duration": 0.0})
        }
        
        # File paths
        self.execution_file = memory_dir / "execution_state.json"
        self.metrics_file = memory_dir / "execution_metrics.json"
        
    def start_execution(self, execution_type: str, context: Dict[str, Any]) -> str:
        """Start tracking a new execution.
        
        Args:
            execution_type: Type of execution (cycle, action, etc.)
            context: Execution context
            
        Returns:
            Execution ID
        """
        execution_id = self.cognitive_utils.generate_unique_id("exec", execution_type)
        
        self.current_execution = {
            "id": execution_id,
            "type": execution_type,
            "start_time": datetime.now(),
            "context": context,
            "states": [],
            "status": "running"
        }
        
        logger.debug(f"Started execution: {execution_id} ({execution_type})")
        return execution_id
        
    def track_state_transition(self, from_state: str, to_state: str, 
                             metadata: Optional[Dict[str, Any]] = None):
        """Track a state transition within current execution.
        
        Args:
            from_state: Previous state
            to_state: New state
            metadata: Optional transition metadata
        """
        if not self.current_execution:
            logger.warning("No active execution to track state transition")
            return
            
        transition = {
            "timestamp": datetime.now(),
            "from": from_state,
            "to": to_state,
            "duration": 0.0,  # Will be calculated
            "metadata": metadata or {}
        }
        
        # Calculate duration from previous state
        if self.current_execution["states"]:
            last_state = self.current_execution["states"][-1]
            duration = (transition["timestamp"] - last_state["timestamp"]).total_seconds()
            last_state["duration"] = duration
            
        self.current_execution["states"].append(transition)
        
    def end_execution(self, status: str = "completed", 
                     result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """End the current execution tracking.
        
        Args:
            status: Final status (completed, failed, aborted)
            result: Execution result
            
        Returns:
            Execution summary
        """
        if not self.current_execution:
            logger.warning("No active execution to end")
            return {}
            
        # Finalize execution
        self.current_execution["end_time"] = datetime.now()
        self.current_execution["status"] = status
        self.current_execution["result"] = result or {}
        
        # Calculate total duration
        duration = (self.current_execution["end_time"] - 
                   self.current_execution["start_time"]).total_seconds()
        self.current_execution["duration"] = duration
        
        # Update last state duration if any
        if self.current_execution["states"]:
            last_state = self.current_execution["states"][-1]
            last_state["duration"] = (self.current_execution["end_time"] - 
                                     last_state["timestamp"]).total_seconds()
            
        # Create summary
        summary = self._create_execution_summary(self.current_execution)
        
        # Update metrics
        self._update_metrics(self.current_execution)
        
        # Add to history
        self._add_to_history(self.current_execution)
        
        # Clear current execution
        execution_data = self.current_execution
        self.current_execution = None
        
        logger.debug(f"Ended execution: {execution_data['id']} ({status})")
        
        return summary
        
    def _create_execution_summary(self, execution: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of an execution.
        
        Args:
            execution: Execution data
            
        Returns:
            Execution summary
        """
        state_durations = {}
        for state in execution.get("states", []):
            state_name = state["to"]
            if state_name not in state_durations:
                state_durations[state_name] = 0.0
            state_durations[state_name] += state.get("duration", 0.0)
            
        return {
            "id": execution["id"],
            "type": execution["type"],
            "status": execution["status"],
            "duration": execution.get("duration", 0.0),
            "state_count": len(execution.get("states", [])),
            "state_durations": state_durations,
            "start_time": execution["start_time"],
            "end_time": execution.get("end_time")
        }
        
    def _update_metrics(self, execution: Dict[str, Any]):
        """Update performance metrics based on execution.
        
        Args:
            execution: Completed execution data
        """
        self.metrics["total_executions"] += 1
        
        if execution["status"] == "completed":
            self.metrics["successful_executions"] += 1
        else:
            self.metrics["failed_executions"] += 1
            
        # Update average duration
        duration = execution.get("duration", 0.0)
        current_avg = self.metrics["average_duration"]
        total_execs = self.metrics["total_executions"]
        self.metrics["average_duration"] = ((current_avg * (total_execs - 1)) + duration) / total_execs
        
        # Update state metrics
        for state in execution.get("states", []):
            state_name = state["to"]
            state_duration = state.get("duration", 0.0)
            
            self.metrics["by_state"][state_name]["count"] += 1
            self.metrics["by_state"][state_name]["total_duration"] += state_duration
            
    def _add_to_history(self, execution: Dict[str, Any]):
        """Add execution to history.
        
        Args:
            execution: Execution data to add
        """
        # Create compact history entry
        history_entry = {
            "id": execution["id"],
            "type": execution["type"],
            "status": execution["status"],
            "start_time": execution["start_time"],
            "end_time": execution.get("end_time"),
            "duration": execution.get("duration", 0.0),
            "state_count": len(execution.get("states", []))
        }
        
        self.execution_history.append(history_entry)
        
        # Trim history if needed
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]
            
        # Save periodically
        if len(self.execution_history) % 10 == 0:
            self.save_execution_state()
            
    def save_execution_state(self) -> bool:
        """Save execution state and metrics to disk.
        
        Returns:
            True if saved successfully
        """
        try:
            # Save current execution if any
            execution_data = {
                "current_execution": self.current_execution,
                "recent_history": self.execution_history[-100:],  # Last 100
                "last_saved": datetime.now()
            }
            
            execution_json = safe_json_encode(execution_data, indent=2)
            success1 = self.file_manager.save_file(self.execution_file, execution_json)
            
            # Save metrics
            metrics_json = safe_json_encode(self.metrics, indent=2)
            success2 = self.file_manager.save_file(self.metrics_file, metrics_json)
            
            return success1 and success2
            
        except Exception as e:
            logger.error(f"Failed to save execution state: {e}")
            return False
            
    def load_execution_state(self) -> bool:
        """Load execution state and metrics from disk.
        
        Returns:
            True if loaded successfully
        """
        try:
            # Load execution state
            execution_json = self.file_manager.load_file(self.execution_file)
            if execution_json:
                execution_data = safe_json_decode(execution_json)
                if execution_data:
                    self.current_execution = execution_data.get("current_execution")
                    self.execution_history = execution_data.get("recent_history", [])
                    
            # Load metrics
            metrics_json = self.file_manager.load_file(self.metrics_file)
            if metrics_json:
                metrics_data = safe_json_decode(metrics_json)
                if metrics_data:
                    self.metrics.update(metrics_data)
                    # Convert defaultdict
                    self.metrics["by_state"] = defaultdict(
                        lambda: {"count": 0, "total_duration": 0.0},
                        self.metrics.get("by_state", {})
                    )
                    
            logger.info(f"Loaded execution state: {self.metrics['total_executions']} total executions")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load execution state: {e}")
            return False
            
    def get_execution_history(self, limit: int = 10, 
                            execution_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent execution history.
        
        Args:
            limit: Maximum entries to return
            execution_type: Filter by execution type
            
        Returns:
            List of execution entries
        """
        history = self.execution_history
        
        if execution_type:
            history = [h for h in history if h.get("type") == execution_type]
            
        return history[-limit:] if history else []
        
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics.
        
        Returns:
            Performance metrics dictionary
        """
        # Calculate state averages
        state_averages = {}
        for state, data in self.metrics["by_state"].items():
            if data["count"] > 0:
                state_averages[state] = {
                    "count": data["count"],
                    "average_duration": data["total_duration"] / data["count"]
                }
                
        return {
            "total_executions": self.metrics["total_executions"],
            "successful_executions": self.metrics["successful_executions"],
            "failed_executions": self.metrics["failed_executions"],
            "success_rate": (self.metrics["successful_executions"] / 
                           self.metrics["total_executions"] * 100 
                           if self.metrics["total_executions"] > 0 else 0),
            "average_duration": self.metrics["average_duration"],
            "state_performance": state_averages
        }
        
    def get_execution_insights(self, time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """Get insights about execution patterns.
        
        Args:
            time_window: Time window to analyze (None for all)
            
        Returns:
            Insights dictionary
        """
        insights = {
            "patterns": [],
            "bottlenecks": [],
            "trends": {}
        }
        
        # Filter history by time window if specified
        history = self.execution_history
        if time_window:
            cutoff = datetime.now() - time_window
            history = [h for h in history 
                      if h.get("start_time") and h["start_time"] > cutoff]
            
        if not history:
            return insights
            
        # Find patterns
        # 1. Most common execution types
        type_counts = defaultdict(int)
        for h in history:
            type_counts[h.get("type", "unknown")] += 1
            
        most_common = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        insights["patterns"].append({
            "type": "execution_frequency",
            "data": most_common[:5]
        })
        
        # 2. Find bottlenecks (slowest states)
        state_perf = self.get_performance_metrics()["state_performance"]
        slowest_states = sorted(
            state_perf.items(), 
            key=lambda x: x[1]["average_duration"], 
            reverse=True
        )[:3]
        
        for state, data in slowest_states:
            insights["bottlenecks"].append({
                "state": state,
                "average_duration": data["average_duration"],
                "impact": "high" if data["average_duration"] > 1.0 else "medium"
            })
            
        # 3. Trends
        if len(history) > 10:
            # Success rate trend
            recent = history[-10:]
            older = history[-20:-10] if len(history) > 20 else history[:10]
            
            recent_success = sum(1 for h in recent if h.get("status") == "completed") / len(recent)
            older_success = sum(1 for h in older if h.get("status") == "completed") / len(older)
            
            insights["trends"]["success_rate"] = {
                "current": recent_success * 100,
                "previous": older_success * 100,
                "improving": recent_success > older_success
            }
            
        return insights
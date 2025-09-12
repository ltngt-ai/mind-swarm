"""
# Pipeline Knowledge API for Cybers

## Core Concept: Inter-Stage Communication via Knowledge DB
The Pipeline Knowledge API provides semantic storage for inter-stage communication,
replacing file-based pipeline buffer JSON files with knowledge database entries.

Pipeline buffers are stored with stage, cycle, and temporal metadata,
enabling stages to pass structured data through the cognitive cycle.

## Examples

### Intention: "Store observation stage output"
```python
pipeline_knowledge.store_stage_output(
    stage="observation",
    cycle_number=42,
    output={
        "situation": "Located at /grid/library",
        "observations": ["New message received"],
        "recommended_focus": "Process incoming message"
    }
)
```

### Intention: "Get decision stage input"
```python
observation_data = pipeline_knowledge.get_stage_input("decision", cycle_number=42)
if observation_data:
    situation = observation_data.get("situation")
    process_decision(situation)
```

### Intention: "Get latest stage output"
```python
latest_execution = pipeline_knowledge.get_latest_stage_output("execution")
if latest_execution:
    results = latest_execution.get("results")
```

## Best Practices
1. Store stage output immediately after processing
2. Include cycle number for temporal tracking
3. Use structured data for easy processing
4. Clean up old pipeline data periodically
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger("Cyber.pipeline_knowledge")


class PipelineKnowledgeError(Exception):
    """Base exception for pipeline knowledge errors."""
    pass


class PipelineKnowledge:
    """Manages pipeline buffer storage and retrieval using the knowledge database."""
    
    VALID_STAGES = ["observation", "decision", "execution", "reflection"]
    
    def __init__(self, context_or_knowledge):
        """Initialize the Pipeline Knowledge API.
        
        Args:
            context_or_knowledge: Either execution context dict or Knowledge API instance
        """
        if isinstance(context_or_knowledge, dict):
            # Initialize from context
            self.context = context_or_knowledge
            self.cyber_id = context_or_knowledge.get('cyber_id', 'unknown')
            
            # Create Memory API if not present, then Knowledge API
            from .memory import Memory
            from .knowledge import Knowledge
            
            memory_api = context_or_knowledge.get('memory_api')
            if not memory_api:
                # Create Memory API from context
                memory_api = Memory(context_or_knowledge)
            
            self.knowledge = Knowledge(memory_api)
        else:
            # Direct Knowledge API instance - try to get cyber_id
            self.knowledge = context_or_knowledge
            # Try to get cyber_id from the memory API if possible
            if hasattr(context_or_knowledge, 'memory') and hasattr(context_or_knowledge.memory, 'context'):
                self.cyber_id = context_or_knowledge.memory.context.get('cyber_id', 'unknown')
            else:
                self.cyber_id = getattr(context_or_knowledge, 'cyber_id', 'unknown')
    
    def store_stage_output(self,
                          stage: str,
                          cycle_number: int,
                          output: Dict[str, Any],
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store output from a cognitive stage in the knowledge database.
        
        Args:
            stage: The stage name (observation, decision, execution, reflection)
            cycle_number: The cognitive cycle number
            output: The stage output data
            metadata: Additional metadata
            
        Returns:
            Knowledge ID of stored pipeline buffer
            
        Example:
            buffer_id = pipeline_knowledge.store_stage_output(
                stage="observation",
                cycle_number=10,
                output={
                    "situation": "At /grid/library",
                    "observations": ["5 new messages"],
                    "recommended_focus": "Process messages"
                }
            )
        """
        if stage not in self.VALID_STAGES:
            raise PipelineKnowledgeError(f"Invalid stage: {stage}. Must be one of {self.VALID_STAGES}")
        
        timestamp = datetime.now()
        
        # Use stable ID based on cyber, stage, and cycle number - NO TIMESTAMP!
        # This allows direct lookup like ROM and stage instructions
        knowledge_id = f"pipeline/{self.cyber_id}/{stage}/cycle_{cycle_number}"
        
        # Create semantic content
        semantic_content = f"""
Pipeline Buffer: {stage.title()} Stage Output
Cyber: {self.cyber_id}
Cycle: {cycle_number}
Time: {timestamp.isoformat()}

Output Data:
{json.dumps(output, indent=2)}
"""
        
        # Prepare metadata
        buffer_metadata = {
            "buffer_type": "pipeline",
            "stage": stage,
            "cycle_number": cycle_number,
            "cyber_id": self.cyber_id,
            "timestamp": timestamp.isoformat(),
            "output": output
        }
        
        if metadata:
            buffer_metadata.update(metadata)
        
        # Build tags for search
        buffer_tags = [
            "pipeline",
            f"stage_{stage}",
            f"cycle_{cycle_number}",
            f"cyber_{self.cyber_id}"
        ]
        
        # Pipeline buffers are personal (specific to this cyber)
        stored_id = self.knowledge.store(
            content=semantic_content,
            knowledge_id=knowledge_id,
            tags=buffer_tags,
            personal=True,
            metadata=buffer_metadata
        )
        
        # Validate storage succeeded
        if not stored_id:
            logger.error(f"Failed to store {stage} stage output for cycle {cycle_number} - no ID returned")
            raise PipelineKnowledgeError(f"Storage failed for {stage} cycle {cycle_number}")
        
        # Check if it was idempotent (same content already exists)
        if isinstance(stored_id, dict):
            if stored_id.get('idempotent'):
                logger.warning(f"Idempotent store for {stage} cycle {cycle_number} - content unchanged")
            else:
                logger.info(f"Successfully stored {stage} stage output for cycle {cycle_number}: {stored_id}")
        else:
            logger.info(f"Stored {stage} stage output for cycle {cycle_number}: {stored_id}")
        
        # Validate we can retrieve what we just stored
        try:
            # Try to get by the ID we specified (not the returned one which might be different)
            retrieved = self.knowledge.get(knowledge_id)
            if retrieved:
                # The get method returns the full result under 'result' key
                result = retrieved if 'metadata' in retrieved else retrieved.get('result', {})
                if result:
                    retrieved_metadata = result.get('metadata', {})
                    # Verify critical fields
                    if retrieved_metadata.get('cycle_number') != cycle_number:
                        logger.error(f"Validation failed: stored cycle {cycle_number} but retrieved {retrieved_metadata.get('cycle_number')}")
                    if retrieved_metadata.get('stage') != stage:
                        logger.error(f"Validation failed: stored stage {stage} but retrieved {retrieved_metadata.get('stage')}")
                    logger.info(f"✓ Validation successful: {stage} cycle {cycle_number} stored with correct metadata")
                else:
                    logger.error(f"Validation failed: no result in response for {stage} cycle {cycle_number}")
            else:
                logger.error(f"Validation failed: could not retrieve {stage} cycle {cycle_number} after storage")
        except Exception as e:
            logger.error(f"Validation error for {stage} cycle {cycle_number}: {e}")
        
        return stored_id
    
    def get_stage_input(self,
                       stage: str,
                       cycle_number: int) -> Optional[Dict[str, Any]]:
        """Get input for a stage (output from previous stage in same cycle).
        
        Args:
            stage: The stage that needs input
            cycle_number: The cognitive cycle number
            
        Returns:
            Previous stage output or None
            
        Example:
            # Decision stage gets observation output
            obs_data = pipeline_knowledge.get_stage_input("decision", cycle_number=10)
        """
        # Map stage to its input source
        input_mapping = {
            "decision": "observation",
            "execution": "decision",
            "reflection": "execution",
            "observation": "reflection"  # Next cycle gets reflection
        }
        
        source_stage = input_mapping.get(stage)
        if not source_stage:
            return None
        
        # For observation, we want reflection from previous cycle
        if stage == "observation":
            cycle_number = cycle_number - 1
            if cycle_number < 0:
                return None
        
        return self.get_stage_output(source_stage, cycle_number)
    
    def get_stage_output(self,
                        stage: str,
                        cycle_number: int) -> Optional[Dict[str, Any]]:
        """Get output from a specific stage and cycle.
        
        Args:
            stage: The stage name
            cycle_number: The cognitive cycle number
            
        Returns:
            Stage output data or None
            
        Example:
            execution_output = pipeline_knowledge.get_stage_output("execution", cycle_number=10)
        """
        if stage not in self.VALID_STAGES:
            return None
        
        # Use direct ID lookup like ROM and stage instructions
        # Format: pipeline/{cyber_id}/{stage}/cycle_{cycle_number}
        knowledge_id = f"pipeline/{self.cyber_id}/{stage}/cycle_{cycle_number}"
        
        # Direct get by ID - no searching!
        result = self.knowledge.get(knowledge_id)
        
        if result:
            # The result should have metadata with the output
            if isinstance(result, dict):
                metadata = result.get('metadata', {})
                output = metadata.get('output')
                
                # Validate it's the right cycle and stage
                if metadata.get('cycle_number') == cycle_number and metadata.get('stage') == stage:
                    # Parse JSON string if needed
                    if isinstance(output, str):
                        try:
                            import json
                            output = json.loads(output)
                        except (json.JSONDecodeError, ValueError):
                            logger.warning(f"Output is string but not valid JSON for {stage} cycle {cycle_number}")
                            # Return as dict with the string to avoid breaking downstream code
                            output = {"raw_output": output}
                    return output
                else:
                    logger.warning(f"ID mismatch: expected {stage} cycle {cycle_number}, got {metadata.get('stage')} cycle {metadata.get('cycle_number')}")
            
        return None
    
    def get_latest_stage_output(self, stage: str) -> Optional[Dict[str, Any]]:
        """Get the most recent output from a specific stage.
        
        Args:
            stage: The stage name
            
        Returns:
            Latest stage output or None
            
        Example:
            latest_decision = pipeline_knowledge.get_latest_stage_output("decision")
        """
        if stage not in self.VALID_STAGES:
            return None
        
        # Search for stage outputs using semantic query
        search_query = f"Pipeline Buffer {stage} Stage Output"
        
        results = self.knowledge.search(
            query=search_query,
            limit=10,  # Get recent ones to find latest
            scope=["personal"]  # Only search personal knowledge
        )
        
        if not results:
            return None
        
        # Find the most recent by timestamp
        latest = None
        latest_time = None
        
        for result in results:
            metadata = result.get('metadata', {})
            timestamp_str = metadata.get('timestamp')
            
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if not latest_time or timestamp > latest_time:
                        latest_time = timestamp
                        latest = metadata.get('output')
                except:
                    pass
        
        return latest
    
    def get_current_cycle_buffers(self, cycle_number: int) -> Dict[str, Any]:
        """Get all pipeline buffers for the current cycle.
        
        Args:
            cycle_number: The cognitive cycle number
            
        Returns:
            Dictionary with stage names as keys and outputs as values
            
        Example:
            all_buffers = pipeline_knowledge.get_current_cycle_buffers(10)
            obs_data = all_buffers.get("observation")
            dec_data = all_buffers.get("decision")
        """
        buffers = {}
        
        for stage in self.VALID_STAGES:
            output = self.get_stage_output(stage, cycle_number)
            if output:
                buffers[stage] = output
        
        return buffers
    
    def cleanup_old_buffers(self, cycles_old: int = 10) -> int:
        """Delete pipeline buffers older than specified cycles.
        
        Args:
            cycles_old: Delete buffers older than this many cycles
            
        Returns:
            Number of buffers deleted
            
        Example:
            deleted = pipeline_knowledge.cleanup_old_buffers(cycles_old=5)
            print(f"Cleaned up {deleted} old pipeline buffers")
        """
        # Get current cycle from latest buffer
        latest = self.get_latest_stage_output("observation")
        if not latest:
            latest = self.get_latest_stage_output("decision")
        if not latest:
            return 0
        
        # Search for pipeline buffers
        search_query = "Pipeline Buffer Stage Output"
        results = self.knowledge.search(
            query=search_query,
            limit=100,
            scope=["personal"]  # Only search personal knowledge
        )
        
        deleted_count = 0
        current_cycle = 0
        
        # Find current cycle number
        for result in results:
            metadata = result.get('metadata', {})
            cycle = metadata.get('cycle_number', 0)
            if cycle > current_cycle:
                current_cycle = cycle
        
        # Delete old buffers
        cutoff_cycle = current_cycle - cycles_old
        
        for result in results:
            metadata = result.get('metadata', {})
            cycle = metadata.get('cycle_number', 0)
            
            if cycle < cutoff_cycle:
                knowledge_id = result.get('id')
                if knowledge_id and self.knowledge.forget(knowledge_id):
                    deleted_count += 1
        
        return deleted_count
    
    def get_stage_history(self,
                         stage: str,
                         limit: int = 10) -> List[Dict[str, Any]]:
        """Get history of outputs from a specific stage.
        
        Args:
            stage: The stage name
            limit: Maximum number of results
            
        Returns:
            List of stage outputs, most recent first
            
        Example:
            decision_history = pipeline_knowledge.get_stage_history("decision", limit=5)
            for decision in decision_history:
                print(f"Cycle {decision['cycle_number']}: {decision['output']}")
        """
        if stage not in self.VALID_STAGES:
            return []
        
        # Search for stage outputs using semantic query
        search_query = f"Pipeline Buffer {stage} Stage Output"
        
        results = self.knowledge.search(
            query=search_query,
            limit=limit * 2,  # Get extra to sort
            scope=["personal"]  # Only search personal knowledge
        )
        
        outputs = []
        for result in results:
            metadata = result.get('metadata', {})
            if metadata.get('output'):
                outputs.append({
                    'cycle_number': metadata.get('cycle_number', 0),
                    'timestamp': metadata.get('timestamp'),
                    'output': metadata.get('output')
                })
        
        # Sort by cycle number (most recent first)
        outputs.sort(key=lambda x: x['cycle_number'], reverse=True)
        
        return outputs[:limit]
# CBR Error Resolution System

## Overview

The execution stage now integrates Case-Based Reasoning (CBR) to learn from past script execution errors and their successful fixes. This creates a growing knowledge base of error patterns and solutions that improves over time.

## How It Works

### 1. Error Detection
When a Python script fails during execution:
- The error type, message, traceback, and context are captured
- The system has up to 3 attempts to fix and retry

### 2. Semantic Search for Similar Errors
Before attempting a fix, the system:
- Searches the CBR database for similar past errors using semantic vector search
- Retrieves up to 5 most similar cases with their solutions
- Prioritizes cases with high success scores (0.7+)

### 3. AI-Assisted Error Resolution
The AI brain receives:
- The original script that failed
- Full error details and traceback
- Similar past errors and their successful solutions
- Working memory context including API documentation

The AI then generates a fixed script, potentially adapting solutions from similar past cases.

### 4. Case Storage
When a fix is attempted:
- A new CBR case is created with status "pending"
- The case includes:
  - Problem description (error context)
  - Solution description (the fix applied)
  - Metadata (scripts, error details, cycle count)
  - Initial neutral success score (0.5)

### 5. Score Updates
After all retry attempts complete:
- If execution succeeds: case scores updated to 0.85
- If execution fails: case scores updated to 0.15
- Cases are marked as "reused" to track usage

## Benefits

1. **Learning from Experience**: Each error and fix becomes part of the knowledge base
2. **Faster Resolution**: Similar errors can be fixed using proven solutions
3. **Improved Success Rate**: High-scoring solutions guide future fixes
4. **Shared Knowledge**: Cases can be shared across cybers in the hive mind

## Error Case Structure

```json
{
  "case_id": "case_abc123",
  "problem_context": "Script execution failed with MemoryError: ...",
  "solution": "Fixed script by modifying the code - Changed from 10 to 12 lines",
  "outcome": "Status: success",
  "metadata": {
    "success_score": 0.85,
    "usage_count": 3,
    "tags": ["error_memoryerror", "execution_fix", "attempt_2"],
    "original_script": "...",
    "fixed_script": "...",
    "error_details": {
      "type": "MemoryError",
      "message": "Memory location not found",
      "line": 5
    },
    "cycle_count": 42
  }
}
```

## Implementation Details

### Key Components

1. **_search_similar_error_cases()**: Searches CBR for similar past errors
2. **_store_error_case()**: Stores new error/solution pairs
3. **_update_error_case_scores()**: Updates scores based on success/failure
4. **_fix_script_error()**: Enhanced to use similar solutions

### Integration Points

- Execution retry loop checks CBR before each fix attempt
- Error cases tracked per cycle with `self.error_case_ids`
- CBR API provides semantic search via vector embeddings
- Success scores guide solution selection

### Configuration

- **Similarity threshold**: 0.3 (captures more potential matches)
- **Max similar cases**: 5 retrieved, top 3 shown to AI
- **Success score range**: 0.15 (failed) to 0.85 (successful)
- **Timeout**: 3 seconds for CBR operations (to not delay execution)

## Usage Example

When a cyber encounters a MemoryError:

1. System searches: "Error type: MemoryError, Error message: Memory location '/personal/data.json' not found"
2. Finds similar case: "Fixed by checking memory.exists() before access"
3. AI adapts solution: Adds existence check to current script
4. Retry succeeds: Case score updated to 0.85
5. Future cybers benefit from this learned solution

## Future Improvements

1. **Pattern Detection**: Identify common error patterns across multiple cases
2. **Proactive Prevention**: Warn during script generation about potential errors
3. **Cross-Cyber Learning**: Share high-value cases automatically
4. **Error Clustering**: Group similar errors for batch resolution strategies
5. **Confidence Scoring**: Weight solutions by cyber expertise and context similarity
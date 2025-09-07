# Design: Periodic Memory-to-Knowledge Summarization (Personal)

## Executive Summary

This document outlines the design for a lightweight pipeline that periodically summarizes key cyber memory buffers (reflections, activity logs, status) into durable personal knowledge documents. The system will operate on a daily rollup schedule, producing structured summaries stored in the personal knowledge space with proper IDs and retention policies.

## Design Goals

1. **Preserve Learning**: Convert ephemeral memory into durable knowledge
2. **Reduce Noise**: Summarize and extract insights rather than storing raw buffers
3. **Personal Focus**: Each cyber maintains its own knowledge base
4. **Lightweight**: Minimal resource usage with configurable execution
5. **Configurable**: Feature flags and retention policies for flexibility

## Architecture Overview

### Components

```
┌─────────────────────────────────────────────────────────┐
│                   Cyber Memory Space                     │
│  ┌──────────────────────────────────────────────────┐  │
│  │ .internal/memory/                                │  │
│  │  ├── reflection_on_last_cycle.md                 │  │
│  │  ├── observation_pipe_stage.json                 │  │
│  │  ├── decision_pipe_stage.json                    │  │
│  │  └── execution_pipe_stage.json                   │  │
│  └──────────────────────────────────────────────────┘  │
│                           ↓                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │     Memory Summarization Pipeline (Daily)        │  │
│  │  1. Collect period memories (24h window)         │  │
│  │  2. Extract patterns & insights                  │  │
│  │  3. Generate structured summaries                │  │
│  │  4. Store to personal knowledge                  │  │
│  └──────────────────────────────────────────────────┘  │
│                           ↓                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │ personal/<cyber>/summaries/                      │  │
│  │  ├── reflections/<YYYYMMDD>.md                   │  │
│  │  ├── activity/<YYYYMMDD>.md                      │  │
│  │  └── status/<YYYYMMDD>.md                        │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Collection Phase**: Gather memory buffers from the past period
2. **Analysis Phase**: Extract patterns, insights, and key events
3. **Summarization Phase**: Generate structured knowledge documents
4. **Storage Phase**: Write to personal knowledge with proper metadata
5. **Cleanup Phase**: Mark processed memories for archival (not deletion)

## Detailed Design

### Memory Source Categories

#### 1. Reflections
- **Source**: `reflection_on_last_cycle.md` files over time
- **Content**: Learning points, strategy adjustments, capability improvements
- **Summary Focus**: Pattern recognition, skill development, strategic insights
- **Output ID**: `personal/<cyber>/summaries/reflections/<YYYYMMDD>.md`

#### 2. Activity Logs
- **Source**: Pipeline stage results (observation, decision, execution)
- **Content**: Actions taken, results achieved, errors encountered
- **Summary Focus**: Success patterns, failure analysis, efficiency metrics
- **Output ID**: `personal/<cyber>/summaries/activity/<YYYYMMDD>.md`

#### 3. Status Reports
- **Source**: Cyber status updates, goal progress, task completions
- **Content**: Current state, active goals, resource usage
- **Summary Focus**: Progress tracking, milestone achievements, bottlenecks
- **Output ID**: `personal/<cyber>/summaries/status/<YYYYMMDD>.md`

### Summary Document Format

```yaml
---
title: "Daily Summary - <Type> - <Date>"
category: "personal_summary"
summary_type: "reflections|activity|status"
date: "YYYY-MM-DD"
cyber_id: "<cyber-name>"
period_start: "ISO-8601"
period_end: "ISO-8601"
source_count: <number>
tags: [daily-summary, <type>, auto-generated]
retention_days: 30
---

# Summary Content

## Key Insights
- Bullet points of main discoveries/patterns

## Detailed Analysis
Narrative summary of the period

## Metrics (if applicable)
- Actions taken: X
- Success rate: Y%
- Key achievements: [list]

## Forward Recommendations
Suggested focus areas based on analysis
```

### Implementation Components

#### 1. MemorySummarizer Class
```python
class MemorySummarizer:
    def __init__(self, cyber_id: str, config: SummaryConfig):
        self.cyber_id = cyber_id
        self.config = config
        self.memory_manager = WorkingMemoryManager()
        self.knowledge_api = KnowledgeAPI()
    
    def run_daily_summary(self) -> SummaryResults:
        """Execute daily summarization pipeline"""
        # 1. Check feature flag
        if not self.config.enabled:
            return SummaryResults.skipped()
        
        # 2. Collect period memories
        memories = self.collect_period_memories()
        
        # 3. Generate summaries by type
        summaries = {
            'reflections': self.summarize_reflections(memories),
            'activity': self.summarize_activity(memories),
            'status': self.summarize_status(memories)
        }
        
        # 4. Store to knowledge
        for summary_type, content in summaries.items():
            self.store_summary(summary_type, content)
        
        # 5. Mark memories as processed
        self.mark_processed(memories)
        
        return SummaryResults(summaries)
```

#### 2. Summary Configuration
```yaml
# config/memory_summary.yaml
memory_summarization:
  enabled: true  # Feature flag
  schedule: "daily"  # daily|hourly|cycle-based
  trigger_hour: 3  # 3 AM UTC for daily
  
  retention_policy:
    reflections: 30  # days
    activity: 7
    status: 7
    
  summary_limits:
    max_tokens: 2000  # Per summary document
    max_source_memories: 1000  # Per run
    
  types:
    reflections:
      enabled: true
      min_confidence: 0.3
      include_patterns: ["learning", "insight", "strategy"]
      
    activity:
      enabled: true
      aggregate_metrics: true
      include_errors: true
      
    status:
      enabled: true
      track_goals: true
      include_resources: false
```

#### 3. Summarization Strategies

**Reflections Summarization**:
1. Group reflections by theme/topic
2. Extract learning points and insights
3. Identify recurring patterns
4. Synthesize strategic adjustments
5. Generate forward-looking recommendations

**Activity Summarization**:
1. Aggregate action counts and types
2. Calculate success/failure rates
3. Identify peak activity periods
4. Extract error patterns
5. Highlight notable achievements

**Status Summarization**:
1. Track goal progression
2. Monitor state transitions
3. Measure resource utilization
4. Identify bottlenecks
5. Project completion estimates

### Integration Points

#### 1. Cognitive Loop Integration
- Add summary trigger check at cycle boundaries
- Use existing reflection stage outputs
- Leverage memory manager for collection

#### 2. Knowledge System Integration
- Use standard knowledge document format
- Integrate with knowledge sync for validation
- Support both personal and shared summaries (future)

#### 3. Scheduler Integration
- Implement as periodic task in SubspaceCoordinator
- Support manual triggers via CLI command
- Respect cyber sleep/active states

## Implementation Plan

### Phase 1: Core Pipeline (Week 1)
- [ ] Implement MemorySummarizer base class
- [ ] Create memory collection logic
- [ ] Add configuration system with feature flags
- [ ] Implement basic summarization (concatenation + truncation)

### Phase 2: Smart Summarization (Week 2)
- [ ] Add LLM-based summarization for reflections
- [ ] Implement activity metrics aggregation
- [ ] Create status progression tracking
- [ ] Add pattern recognition logic

### Phase 3: Storage & Integration (Week 3)
- [ ] Integrate with personal knowledge storage
- [ ] Add retention policy enforcement
- [ ] Implement scheduler integration
- [ ] Create CLI commands for manual triggers

### Phase 4: Testing & Refinement (Week 4)
- [ ] Add unit tests for summarizer
- [ ] Test with multiple cyber profiles
- [ ] Optimize summarization prompts
- [ ] Add monitoring and metrics

## Configuration Examples

### Minimal Configuration
```yaml
memory_summarization:
  enabled: true
  schedule: "daily"
  types:
    reflections:
      enabled: true
```

### Aggressive Summarization
```yaml
memory_summarization:
  enabled: true
  schedule: "hourly"
  retention_policy:
    reflections: 90
    activity: 30
    status: 30
  types:
    reflections:
      enabled: true
      min_confidence: 0.1
    activity:
      enabled: true
      aggregate_metrics: true
    status:
      enabled: true
      track_goals: true
```

## Security Considerations

1. **No Raw Buffer Storage**: Never store raw memory buffers in knowledge
2. **Sanitization**: Remove any sensitive data before summarization
3. **Access Control**: Summaries remain in personal space by default
4. **Validation**: Use existing knowledge validation pipeline
5. **Rate Limiting**: Prevent excessive summarization cycles

## Performance Considerations

1. **Incremental Processing**: Only process new memories since last run
2. **Batch Operations**: Summarize multiple types in single LLM call
3. **Caching**: Cache intermediate results for retry logic
4. **Resource Limits**: Respect cyber memory and CPU limits
5. **Async Execution**: Run summarization in background

## Monitoring & Observability

### Metrics
- Summaries generated per day
- Average summary size
- Processing time per cyber
- Memory reduction ratio
- LLM token usage

### Logging
- Summary generation events
- Error conditions
- Skipped summaries (feature disabled)
- Retention policy actions

## Future Enhancements

1. **Cross-Cyber Insights**: Aggregate summaries across cybers
2. **Trend Analysis**: Multi-day pattern recognition
3. **Adaptive Scheduling**: Adjust frequency based on activity
4. **Summary Quality Scoring**: Evaluate and improve summaries
5. **Knowledge Graph Integration**: Link summaries to related knowledge

## Conclusion

This lightweight memory-to-knowledge summarization pipeline provides a practical approach to preserving cyber learning while managing storage efficiently. The feature-flagged, configurable design allows for gradual rollout and tuning based on system needs.
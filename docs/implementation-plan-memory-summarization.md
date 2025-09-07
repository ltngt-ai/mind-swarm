# Implementation Plan: Memory-to-Knowledge Summarization Pipeline

## Overview
Implement a lightweight pipeline to periodically summarize cyber memory buffers into personal knowledge documents with configurable retention and feature flags.

## Development Phases

### Phase 1: Core Infrastructure (3-4 days)

#### 1.1 Configuration System
**File**: `src/mind_swarm/config/memory_summary_config.py`
```python
@dataclass
class MemorySummaryConfig:
    enabled: bool = False  # Feature flag - disabled by default
    schedule: str = "daily"
    trigger_hour: int = 3
    retention_days: Dict[str, int]
    summary_types: Dict[str, TypeConfig]
```

**File**: `config/memory_summary.yaml`
- Default configuration with feature flag
- Type-specific settings
- Retention policies

#### 1.2 Base Summarizer Class
**File**: `src/mind_swarm/subspace/memory_summarizer.py`
- Core MemorySummarizer class
- Memory collection methods
- Summary ID generation
- Basic concatenation summarizer

#### 1.3 Memory Collection
**Updates**: `src/mind_swarm/subspace_template/grid/library/base_code/base_code_template/memory/memory_persistence.py`
- Add timestamp tracking for memories
- Implement period-based queries
- Add "processed" marking system

### Phase 2: Summarization Logic (4-5 days)

#### 2.1 Reflection Summarizer
**File**: `src/mind_swarm/subspace/summarizers/reflection_summarizer.py`
- Pattern extraction from reflections
- Learning point aggregation
- Theme clustering
- LLM-based insight synthesis

#### 2.2 Activity Summarizer
**File**: `src/mind_swarm/subspace/summarizers/activity_summarizer.py`
- Action metrics aggregation
- Success/failure rate calculation
- Error pattern detection
- Timeline reconstruction

#### 2.3 Status Summarizer
**File**: `src/mind_swarm/subspace/summarizers/status_summarizer.py`
- Goal progression tracking
- State transition analysis
- Resource utilization metrics
- Milestone detection

### Phase 3: Knowledge Integration (3-4 days)

#### 3.1 Knowledge Storage Adapter
**File**: `src/mind_swarm/subspace/knowledge_storage_adapter.py`
- Format summaries as knowledge documents
- Generate proper metadata
- Handle personal/<cyber>/summaries/ paths
- Integrate with existing knowledge validation

#### 3.2 Retention Manager
**File**: `src/mind_swarm/subspace/retention_manager.py`
- Track summary ages
- Enforce retention policies
- Archive expired summaries
- Cleanup scheduling

#### 3.3 Knowledge Sync Integration
**Updates**: `config/knowledge_sync.yaml`
- Add personal summaries to sync paths
- Configure exclude patterns for raw memories
- Set appropriate priorities

### Phase 4: Scheduler & Triggers (2-3 days)

#### 4.1 Periodic Scheduler
**Updates**: `src/mind_swarm/subspace/subspace_coordinator.py`
- Add daily summary task
- Check feature flags
- Respect cyber states (active/sleeping)
- Handle multiple cybers efficiently

#### 4.2 Manual Triggers
**Updates**: `src/mind_swarm/cli/commands.py`
- Add `summarize` command
- Support cyber-specific or all-cyber runs
- Progress reporting
- Dry-run mode

#### 4.3 Event-Based Triggers
**Updates**: `src/mind_swarm/subspace/cyber_registry.py`
- Trigger on cyber shutdown
- Trigger on memory threshold
- Configurable trigger conditions

### Phase 5: Testing & Optimization (3-4 days)

#### 5.1 Unit Tests
**Files**: `tests/subspace/test_memory_summarizer.py`
- Test memory collection
- Test summarization logic
- Test retention policies
- Test configuration loading

#### 5.2 Integration Tests
**Files**: `tests/integration/test_summary_pipeline.py`
- End-to-end pipeline tests
- Multi-cyber scenarios
- Edge cases (empty memories, failures)
- Performance benchmarks

#### 5.3 Prompt Optimization
**File**: `src/mind_swarm/ai/prompts/summarization_prompts.py`
- Reflection summarization prompts
- Activity analysis prompts
- Status interpretation prompts
- Iterative refinement based on results

## File Structure

```
src/mind_swarm/
├── config/
│   └── memory_summary_config.py      # Configuration classes
├── subspace/
│   ├── memory_summarizer.py          # Core summarizer
│   ├── knowledge_storage_adapter.py  # Knowledge integration
│   ├── retention_manager.py          # Retention policies
│   └── summarizers/
│       ├── __init__.py
│       ├── base_summarizer.py        # Abstract base
│       ├── reflection_summarizer.py  # Reflection logic
│       ├── activity_summarizer.py    # Activity logic
│       └── status_summarizer.py      # Status logic
├── ai/
│   └── prompts/
│       └── summarization_prompts.py  # LLM prompts
└── cli/
    └── commands.py                    # CLI integration

config/
└── memory_summary.yaml               # Default config

tests/
├── subspace/
│   ├── test_memory_summarizer.py
│   └── test_retention_manager.py
└── integration/
    └── test_summary_pipeline.py
```

## Implementation Steps

### Week 1: Foundation
1. Create configuration system with feature flags
2. Implement base MemorySummarizer class
3. Add memory collection with period queries
4. Create basic concatenation summarizer
5. Write initial unit tests

### Week 2: Smart Summarization
1. Implement reflection summarizer with LLM
2. Create activity metrics aggregator
3. Build status progression tracker
4. Optimize summarization prompts
5. Add pattern recognition

### Week 3: Integration
1. Integrate with knowledge storage
2. Implement retention policies
3. Add scheduler integration
4. Create CLI commands
5. Handle multi-cyber scenarios

### Week 4: Polish & Deploy
1. Complete test coverage
2. Performance optimization
3. Documentation updates
4. Configuration examples
5. Monitoring setup

## Key Implementation Details

### Memory Collection Query
```python
def collect_period_memories(self, start_time: datetime, end_time: datetime):
    memories = []
    
    # Collect reflections
    reflection_files = self.scan_memory_files(
        pattern="reflection_*.md",
        start_time=start_time,
        end_time=end_time
    )
    
    # Collect pipeline stages
    for stage in ['observation', 'decision', 'execution']:
        stage_files = self.scan_memory_files(
            pattern=f"{stage}_pipe_stage.json",
            start_time=start_time,
            end_time=end_time
        )
        memories.extend(stage_files)
    
    return memories
```

### Summary Generation
```python
def generate_summary(self, memories: List[MemoryBlock], summary_type: str):
    # Group memories by relevance
    grouped = self.group_by_theme(memories)
    
    # Extract key insights
    insights = self.extract_insights(grouped)
    
    # Generate summary with LLM
    prompt = self.build_summary_prompt(insights, summary_type)
    summary = self.llm_client.generate(prompt)
    
    # Format as knowledge document
    return self.format_knowledge_document(
        summary=summary,
        summary_type=summary_type,
        source_count=len(memories)
    )
```

### Feature Flag Check
```python
def should_run_summary(self, cyber_id: str) -> bool:
    config = self.load_config()
    
    if not config.enabled:
        return False
    
    if not self.is_due_for_summary(cyber_id, config.schedule):
        return False
    
    if self.cyber_registry.get_state(cyber_id) != "active":
        return False
    
    return True
```

## Testing Strategy

### Unit Test Coverage
- Configuration loading and validation
- Memory collection with time windows
- Each summarizer type independently
- Retention policy enforcement
- Knowledge document formatting

### Integration Test Scenarios
1. **Happy Path**: Daily summary generation for active cyber
2. **Edge Cases**: 
   - Empty memory periods
   - Very large memory sets
   - Cyber state changes during summarization
3. **Error Handling**:
   - LLM failures
   - Storage failures
   - Configuration errors
4. **Performance**: 
   - Multiple cybers simultaneously
   - Large memory volumes
   - Token usage optimization

## Monitoring & Metrics

### Key Metrics
- `memory_summary.generated` - Count of summaries created
- `memory_summary.processing_time` - Time per summary
- `memory_summary.memory_processed` - MB of memory processed
- `memory_summary.tokens_used` - LLM token consumption
- `memory_summary.errors` - Error count by type

### Logging Points
```python
logger.info(f"Starting daily summary for cyber {cyber_id}")
logger.debug(f"Collected {len(memories)} memories for period")
logger.info(f"Generated {summary_type} summary: {doc_id}")
logger.warning(f"Summary skipped: feature disabled")
logger.error(f"Summary failed for {cyber_id}: {error}")
```

## Rollout Plan

### Stage 1: Dark Launch (Week 1)
- Deploy with feature flag disabled
- Test with single test cyber
- Monitor resource usage

### Stage 2: Limited Beta (Week 2)
- Enable for 1-2 production cybers
- Daily monitoring of outputs
- Collect quality metrics

### Stage 3: Gradual Rollout (Week 3)
- Enable for 50% of cybers
- Monitor system load
- Tune configuration

### Stage 4: Full Deployment (Week 4)
- Enable for all cybers
- Set up alerts
- Document learnings

## Success Criteria

1. **Functional**: Summaries generated daily for all active cybers
2. **Performance**: < 30s processing time per cyber
3. **Efficiency**: 10:1 memory reduction ratio
4. **Quality**: Summaries capture key insights (manual review)
5. **Reliability**: < 1% failure rate
6. **Resource**: < 5% additional system load

## Risk Mitigation

### Risk 1: High LLM Costs
- **Mitigation**: Token limits, local model fallback, batching

### Risk 2: Storage Growth
- **Mitigation**: Aggressive retention policies, compression

### Risk 3: Performance Impact
- **Mitigation**: Off-peak scheduling, async processing, caching

### Risk 4: Poor Summary Quality
- **Mitigation**: Prompt iteration, quality scoring, manual review

## Dependencies

- Existing memory system (WorkingMemoryManager)
- Knowledge storage system (KnowledgeAPI)
- LLM integration (BrainHandlerDynamic)
- Scheduler system (SubspaceCoordinator)
- Configuration system (YAML loading)

## Deliverables

1. **Code**: Complete implementation with tests
2. **Configuration**: Default config with examples
3. **Documentation**: User guide and API docs
4. **Monitoring**: Metrics and alerting setup
5. **Rollout**: Staged deployment plan executed
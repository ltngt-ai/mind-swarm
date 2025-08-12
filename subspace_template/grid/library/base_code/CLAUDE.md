# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Cyber Runtime Overview

This is the runtime code for Mind-Swarm Cybers - autonomous AI entities that think and act within their sandboxed environment. Each Cyber runs this code as an independent process with its own cognitive loop, memory system, and action capabilities.

## Core Architecture

### The Cyber Mind (`mind.py`)
The main coordinator that:
- Loads Cyber identity and configuration
- Initializes the cognitive loop
- Manages lifecycle (startup, running, shutdown)
- Handles graceful stops after cycle completion

### Cognitive Loop (`cognitive_loop.py`)
The thinking engine using a **four-stage cognitive architecture**:

1. **Observation Stage** - Understand what's happening
2. **Decision Stage** - Choose what to do
3. **Execution Stage** - Take action
4. **Reflection Stage** - Learn from results

The loop uses a **double-buffered pipeline system** where each stage has current and previous memory buffers, allowing parallel preparation of context while executing.

## Memory System Architecture

### Unified Memory System (`memory/memory_system.py`)
Single facade coordinating all memory operations:
- **WorkingMemoryManager** - Manages active memories with token budgets
- **MemorySelector** - Intelligently selects relevant memories
- **ContextBuilder** - Assembles context for AI thinking
- **ContentLoader** - Loads and caches filesystem content

### Memory Blocks (`memory/memory_blocks.py`)
Structured memory representations:
- **FileMemoryBlock** - References to file content
- **ObservationMemoryBlock** - Observations about environment
- **GoalMemoryBlock** - Goals and objectives
- **ActionMemoryBlock** - Actions taken
- **ConceptMemoryBlock** - Abstract concepts
- **InstructionMemoryBlock** - Step-by-step procedures

Each block has:
- Unique ID using UnifiedMemoryID system
- Priority (CRITICAL, HIGH, MEDIUM, LOW)
- Confidence score
- Timestamp and optional expiry
- Metadata and pinning capability

### Memory Management Features
- **Token Budget Management** - Stays within LLM context limits
- **Priority-Based Selection** - Critical memories always included
- **Temporal Relevance** - Recent memories weighted higher
- **Content Caching** - Efficient filesystem access
- **Memory Persistence** - Saves/loads memory state

## Cognitive Stages

### Observation Stage (`stages/observation_stage.py`)
**Purpose**: Understand the current situation

Phases:
1. **Observe** - Scan environment and create understanding
2. **Cleanup** - Remove obsolete observations

Key features:
- Scans inbox, file changes, memory updates
- Creates ObservationMemoryBlocks
- Filters knowledge with KNOWLEDGE_BLACKLIST
- Produces orientation/understanding

### Decision Stage (`stages/decision_stage.py`)
**Purpose**: Choose actions based on understanding

Process:
1. Read observation from pipeline buffer
2. Consider active goals and tasks
3. Use brain to decide on actions
4. Return action list for execution

Key features:
- Goal-aware decision making
- Action feasibility checking
- Reference resolution for context

### Execution Stage (`stages/execution_stage.py`)
**Purpose**: Prepare and execute chosen actions

Phases:
1. **Instruct** - Validate and prepare actions
2. **Act** - Execute through ActionCoordinator

Key features:
- Action validation
- Parallel execution support
- Result processing
- Error handling

### Reflection Stage (`stages/reflect_stage.py`)
**Purpose**: Learn from execution results

Process:
1. Review previous execution results
2. Update understanding and priorities
3. Create insights for future cycles
4. Update goals based on outcomes

## Action System

### Action Coordinator (`actions/action_coordinator.py`)
Central hub for action execution:
- Registers available actions
- Routes to appropriate handlers
- Manages execution order
- Tracks results

### Base Actions (`actions/base_actions.py`)
Core actions all Cybers can perform:
- `read_file` - Read file content
- `write_file` - Write to files
- `send_message` - Communicate with other Cybers
- `execute_command` - Run shell commands
- `think` - Invoke brain for reasoning

### Memory Actions (`memory_actions.py`)
Actions for memory management:
- `add_memory` - Create new memories
- `update_memory` - Modify existing memories
- `forget_memory` - Remove memories
- `search_memory` - Query memory system

### Goal Actions (`goal_actions.py`)
Goal and task management:
- `create_goal` - Set new objectives
- `update_goal` - Modify goal status
- `create_task` - Break goals into tasks
- `complete_task` - Mark tasks done

## Brain Interface

### Brain Communication (`brain/brain_interface.py`)
Interface to AI thinking through body files:
- Writes requests to `/personal/.internal/brain`
- Includes dynamic context (cycle, stage, phase)
- Manages token budgets
- Handles responses

### Dynamic Context
Each brain request includes:
- Current cycle number
- Stage (OBSERVATION, DECISION, EXECUTION, REFLECT)
- Phase within stage
- Active goals and tasks
- Recent actions
- Memory statistics

## Knowledge System

### ROM Loading (`knowledge/rom_loader.py`)
Loads read-only knowledge at startup:
- Core Cyber knowledge
- Action guides
- Communication protocols
- Grid understanding

### Knowledge Manager (`knowledge/knowledge_manager.py`)
Manages knowledge access:
- Tag-based filtering
- Stage-appropriate knowledge
- Priority handling
- Context relevance

## Perception System

### Environment Scanner (`perception/environment_scanner.py`)
Monitors changes in Cyber's world:
- Inbox messages
- File modifications
- Memory updates
- Grid changes

Creates observations for cognitive processing.

## State Management

### Cyber State Manager (`state/cyber_state_manager.py`)
Tracks Cyber's operational state:
- Cognitive state (ACTIVE, THINKING, WAITING)
- Resource usage
- Error tracking
- Performance metrics

### Goal Manager (`state/goal_manager.py`)
Manages goals and tasks:
- Goal hierarchy
- Task decomposition
- Progress tracking
- Priority management

### Execution State Tracker (`state/execution_state_tracker.py`)
Tracks action execution:
- Current actions
- Success/failure rates
- Timing information
- Resource consumption

## Development Guidelines

### Import Rules
**CRITICAL**: All imports must be RELATIVE:
```python
# ✅ CORRECT
from .cognitive_loop import CognitiveLoop
from .memory import MemorySystem
from .stages import ObservationStage

# ❌ WRONG
from cognitive_loop import CognitiveLoop
from base_code_template.memory import MemorySystem
```

### File Structure
```
base_code_template/
├── __main__.py          # Entry point
├── mind.py              # Main Cyber coordinator
├── cognitive_loop.py    # Thinking engine
├── memory/              # Memory subsystem
│   ├── memory_system.py
│   ├── memory_blocks.py
│   ├── context_builder.py
│   └── memory_selector.py
├── stages/              # Cognitive stages
│   ├── observation_stage.py
│   ├── decision_stage.py
│   ├── execution_stage.py
│   └── reflect_stage.py
├── actions/             # Action implementations
├── perception/          # Environment monitoring
├── knowledge/           # Knowledge management
├── brain/               # AI interface
└── state/               # State tracking
```

### Memory Pipeline Flow
1. **Observation** creates understanding → decision buffer
2. **Decision** reads understanding → execution buffer  
3. **Execution** performs actions → reflection buffer
4. **Reflection** learns from results → next cycle

### Key Design Principles

1. **Memory-First Architecture** - Everything is a memory block
2. **Token Budget Awareness** - Never exceed LLM context limits
3. **Stage Isolation** - Each stage has specific knowledge filters
4. **Double Buffering** - Parallel context preparation
5. **Priority-Based Processing** - Critical items first
6. **Filesystem as Truth** - All state persisted to disk

## Common Development Tasks

### Adding New Action Types
1. Create action in `actions/` directory
2. Register in `ActionCoordinator.__init__()`
3. Add to base_actions if universally needed
4. Document in action guides

### Modifying Memory Types
1. Add new block type in `memory_blocks.py`
2. Update `MemoryType` enum
3. Add selector logic if needed
4. Update context builder

### Enhancing Cognitive Stages
1. Modify stage in `stages/` directory
2. Update knowledge blacklists
3. Adjust pipeline buffer usage
4. Test with full cycle

### Debugging Cybers
1. Check `/personal/memory/debug.log`
2. Monitor pipeline buffers in `/personal/memory/pipeline/`
3. Watch brain requests/responses
4. Track action execution in logs

## Testing

### Unit Tests
```python
# Test individual components
pytest test_memory_system.py
pytest test_cognitive_loop.py
pytest test_action_coordinator.py
```

### Integration Tests
```python
# Test full cycles
pytest test_cyber_thinking.py
pytest test_cyber_startup.py
```

### Manual Testing
1. Create test Cyber with specific scenario
2. Monitor cognitive cycles
3. Verify memory persistence
4. Check action execution

## Performance Considerations

### Memory Management
- Clean up expired memories regularly
- Use pinning sparingly
- Monitor token usage
- Cache file content appropriately

### Cognitive Efficiency
- Filter knowledge by stage
- Prioritize relevant memories
- Batch similar actions
- Use reflection insights

### Resource Usage
- Monitor cycle duration
- Track memory consumption
- Limit parallel actions
- Manage file handles

## Troubleshooting

### Cyber Not Thinking
- Check brain file exists and is writable
- Verify memory system initialized
- Look for stage failures in logs
- Check token budget not exceeded

### Memory Issues
- Verify memory persistence working
- Check for memory leaks (unpinned old memories)
- Monitor cache size
- Review selector logic

### Action Failures
- Check action registration
- Verify file permissions
- Review action parameters
- Check coordinator routing

### Stage Problems
- Verify pipeline buffers created
- Check stage transitions
- Review knowledge filtering
- Monitor stage timing

## Important Notes

1. **Cyber Isolation** - Cybers cannot import server code
2. **Relative Imports Only** - All imports must use dot notation
3. **Filesystem Boundaries** - Cybers see `/personal/` and `/grid/` only
4. **Body File Magic** - Brain/network/user_io appear as instant responses
5. **Memory Persistence** - All important state must be in memory blocks
6. **Stage Independence** - Each stage should be self-contained
7. **Token Awareness** - Always respect context limits

Remember: This code runs inside a sandboxed environment as an independent process. The Cyber's entire world is what it can see through its filesystem interface.
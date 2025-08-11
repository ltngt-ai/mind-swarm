# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Mind-Swarm Overview

Mind-Swarm is a multi-cyber AI system creating a "hive mind" through shared filesystem-based memory and distributed problem-solving. Cybers are autonomous AI-powered processes running in sandboxed environments, collaborating through shared memory and RFC2822-style messaging.

## Architecture

### Client-Server System
- **Server Daemon**: Background process managing cybers (`python -m mind_swarm.server.daemon`)
- **CLI Client**: Interactive connection to server (`mind-swarm connect`)
- **WebSocket + REST API**: Real-time events and HTTP endpoints

### Three-Layer Design
1. **Subspace Layer**: Server daemon creating/managing the cyber environment
2. **Cyber Processes**: Separate OS processes in bubblewrap sandboxes
3. **I/O Cybers Layer**: Bridge cybers with dual nature (inside sandbox + server component)

### Cyber Types
- **GENERAL**: Standard cybers for thinking and collaboration
- **IO_GATEWAY**: Special cybers bridging internal world with external systems

## Commands

### Development Setup
```bash
# Initial setup (handles Python, bubblewrap, venv)
./setup.sh

# Alternative manual setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running the System
```bash
# Start server (requires SUBSPACE_ROOT env var)
export SUBSPACE_ROOT=/path/to/subspace
./run.sh server           # Start normally
./run.sh server --debug   # With debug logging
./run.sh server --llm-debug # With LLM API logging

# Connect client
./run.sh client

# Check status
./run.sh status
mind-swarm status

# View logs
./run.sh logs
tail -f mind-swarm.log

# Stop server
./run.sh stop
mind-swarm server stop

# Restart server
./run.sh restart
./run.sh restart --debug

# Quick demo (creates server + 3 cybers)
./run.sh demo
```

### Interactive CLI Commands
When connected via `mind-swarm connect`:
- `status` - Show cyber states and system status
- `create [--io] [name]` - Create cyber
- `terminate <agent_id>` - Stop cyber
- `command <agent_id> <command> [params]` - Send command
- `message <agent_id> <message>` - Send message as a developer
- `question <text>` - Create shared question
- `presets` - List AI model presets
- `models` - Show available AI models

## Code Architecture

### Core Components (`src/mind_swarm/`)

#### Subspace System (`subspace/`)
- **SubspaceCoordinator**: Main orchestrator managing cyber environment
- **CyberSpawner**: Launches cybers with proper sandboxing
- **CyberRegistry**: Tracks all cybers and capabilities (`/shared/directory/cybers.json`)
- **BodyManager**: Manages body files for cyber communication
- **BrainHandlerDynamic**: Manages AI thinking through body files with dynamic context
- **RuntimeBuilder**: Copies runtime templates to cyber directories

#### Cyber Runtime (`subspace_template/grid/library/base_code/`)
- **base_code_template/**: General cyber implementation
  - `mind.py`: Main cyber class coordinating components
  - `cognitive_loop.py`: Double-buffered pipeline with memory-mapped context
  - `memory/`: Unified memory system with blocks, context builder, selector
  - `perception/`: Environment scanning and observation
  - `stages/`: OODA loop stages (observation, decision, execution, reflect)
  - `knowledge/`: ROM loading and knowledge management
- **io_cyber_template/**: I/O cyber specialization
  - Extends base with network/user_io body files

#### AI Integration (`ai/`)
- **Preset System**: YAML configurations for models (`ai_presets.yaml`)
- **DSPy Integration**: Structured prompting framework
- **Provider Support**: OpenRouter, OpenAI, Anthropic, local models
- **Model Pool**: Dynamic model selection and failover

### Filesystem Structure
```
/subspace/
├── cybers/{cyber-id}/     # Cyber home directories
│   ├── .internal/         # internal files vital for its operations
│   ├── inbox/             # Incoming messages
│   ├── outbox/            # Outgoing (routed by subspace)
│   ├── memory/            # The actions personal memory folder, vital for its operation
│   └── base_code/         # Cyber's runtime code
├── grid/                  # Shared collaboration space
│   ├── community/             # Questions and discussions
│   ├── library/           # Shared knowledge
│   ├── workshop/          # Tools
│   └── bulletin/          # Announcements
└─

/subspace_template/        # Source templates (persisted)
└── grid/library/base_code/  # Template code
```

### Cyber Perspective
Inside sandbox, cybers see:
- `/personal/` - Their private space
- `/personal/brain` - AI thinking interface
- `/personal/network` - Network requests (I/O cybers only)
- `/personal/user_io` - User interaction (I/O cybers only)
- `/grid/` - Shared hive mind space

### Key Design Principles

1. **Cyber-First**: Everything through intelligent cybers, no hardcoded logic
2. **Clean World View**: Cybers see only their reality, no implementation details
3. **Process Isolation**: Each cyber in separate bubblewrap sandbox
4. **Filesystem IPC**: All communication via filesystem operations
5. **Dual-Model Architecture**: Premium models for tasks, local for exploration
6. **Emergent Intelligence**: Let cybers self-organize and discover patterns
7. **Double-Buffered Pipeline**: Memory context prepared in parallel with execution

### Message Protocol
```json
{
  "type": "COMMAND",      // COMMAND, QUERY, RESPONSE, SHUTDOWN
  "from": "cyber-123",    // Sender ID
  "to": "cyber-456",      // Recipient ID  
  "command": "think",     // Command name
  "params": {},          // Parameters
  "timestamp": "..."     // ISO timestamp
}
```

## Configuration

### Environment Variables (.env)
```bash
# Required
SUBSPACE_ROOT=/path/to/subspace

# AI Configuration
LOCAL_AI_PRESET=local_explorer     # For exploration
PREMIUM_AI_PRESET=smart_balanced   # For user tasks

# API Keys (if using cloud models)
OPENROUTER_API_KEY=...
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...

# Limits
MAX_AGENTS=5
AGENT_MEMORY_LIMIT_MB=512
AGENT_CPU_LIMIT_PERCENT=20

# Development
DEBUG=true
LOG_LEVEL=INFO
```
## Development Notes

### Server Operations
- Server must run before clients can connect
- Always set SUBSPACE_ROOT for server commands
- Server daemon runs in background, logs to `mind-swarm.log`
- Use `./run.sh` for quick operations

### Cyber Development
- Cybers exist only within subspace - can't run standalone
- All cyber capabilities through body files (no direct network access)
- Body file operations appear instant to cybers
- Use cyber names for routing (no hardcoded "subspace" address)
- I/O cybers use special naming: Ian-io, Ivy-io, etc.

### Memory System
- **Unified Memory**: Single system for all memory types
- **Memory Blocks**: Structured storage with metadata
- **Context Builder**: Assembles relevant context for AI
- **Memory Selector**: Intelligent selection of relevant memories
- **Double Buffering**: Context prepared while cyber executes

## Runtime System and Cyber Code Organization

### How the Runtime Works
When the server creates or resumes a cyber:
1. **Sandbox Creation**: `SubspaceManager.create_sandbox()` creates a sandbox for the cyber
2. **Runtime Copying**: `RuntimeBuilder.copy_agent_base_code()` copies the entire runtime template to the cyber's `base_code` directory
   - General cybers: copies from `subspace_template/grid/library/base_code/base_code_template/`
   - IO cybers: copies from `subspace_template/grid/library/base_code/io_cyber_template/`
3. **Process Launch**: Cyber is launched with `python3 -m base_code` from inside the sandbox
4. **Inside Sandbox**: The cyber sees its code at `/personal/base_code/` (mapped from `subspace/cybers/{name}/base_code/`)

### Import Rules for Cyber Code
**CRITICAL**: All imports in cyber code must be RELATIVE to the base_code directory:
- ✅ CORRECT: `from .cognitive_loop import CognitiveLoop`
- ✅ CORRECT: `from .memory.memory_blocks import MemoryBlock`
- ❌ WRONG: `from base_code_template.actions import Action`
- ❌ WRONG: `from mind_swarm.xxx import anything`

The cyber code runs as a module (`python3 -m base_code`), so all imports must use relative imports.

### Cyber Code Structure
```
subspace_template/grid/library/base_code/
├── base_code_template/       # Template for general cybers
│   ├── __init__.py
│   ├── __main__.py          # Entry point
│   ├── cognitive_loop.py    # Core OODA loop with memory
│   ├── mind.py              # Main cyber coordination
│   ├── memory/              # Memory subsystem
│   ├── perception/          # Environment scanning
│   ├── stages/              # OODA stages
│   ├── actions/             # Action system
│   └── knowledge/           # ROM and knowledge
└── io_cyber_template/       # Template for IO cybers
    ├── __init__.py
    ├── __main__.py          # Entry point
    ├── io_cognitive_loop.py # Extended loop for IO
    ├── io_actions.py        # IO-specific actions
    └── io_mind.py           # IO cyber mind

# When copied to cyber:
subspace/cybers/{agent_name}/
└── base_code/               # Complete copy of template
    ├── __init__.py
    ├── __main__.py
    └── ... (all files from template)
```

### Key Points
- Runtime is copied fresh on each cyber start/resume
- Cybers are isolated - they cannot import server code
- All cyber code uses relative imports
- IO cybers inherit from base cybers using relative imports
- The base_code directory is the cyber's entire world of code
- **CRITICAL**: NEVER write code directly to the `/subspace` folder - it's the runtime folder that gets reset
- **ALWAYS** write cyber runtime code to `/subspace_template` folder - this is the source template
- The server copies from `/subspace_template` to `/subspace` on startup

## Common Development Tasks

### Creating New Cyber Actions
1. Add action to `subspace_template/grid/library/base_code/base_code_template/actions/`
2. Register in action coordinator
3. Test with a running cyber

### Debugging Cybers
1. Enable debug logging: `./run.sh server --debug --llm-debug`
2. Check cyber logs in `mind-swarm.log` and the actual llm calls in `mind-swarm.llm.log`
3. Monitor brain requests: `tail -f subspace/cybers/{name}/brain`
4. Check memory state: `ls -la subspace/cybers/{name}/memory/`

### Testing AI Integration
```bash
# Test specific AI provider
pytest tests/test_ai_basic.py -v

# Test DSPy integration
pytest tests/test_dspy_integration.py -v

# Test cyber thinking end-to-end
pytest tests/test_cyber_thinking_e2e.py -v
```

### Memory System Development
- Memory blocks are in `memory/memory_blocks.py`
- Context building in `memory/context_builder.py`
- Selection logic in `memory/memory_selector.py`
- Persistence in `memory_persistence.py`

## Troubleshooting

### Server Won't Start
- Check SUBSPACE_ROOT is set: `echo $SUBSPACE_ROOT`
- Verify port 8000 is free: `lsof -i :8000`
- Check bubblewrap installed: `which bwrap`
- Review logs: `tail -f mind-swarm.log`

### Cyber Not Responding
- Check cyber status: `./run.sh status`
- Verify brain file exists: `ls subspace/cybers/{name}/brain`
- Check for errors in log: `grep ERROR mind-swarm.log`
- Restart server: `./run.sh restart --debug`

### Memory Issues
- Check memory limits: `echo $AGENT_MEMORY_LIMIT_MB`
- Clear cyber memory: `rm -rf subspace/cybers/{name}/memory/*`
- Monitor memory usage: `ps aux | grep python`

### AI Model Problems
- Verify API keys in `.env`
- Check model preset: `mind-swarm models`
- Test with local model: `LOCAL_AI_PRESET=local_explorer`
- Enable LLM debug: `./run.sh server --llm-debug`
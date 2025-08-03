# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Mind-Swarm Overview

Mind-Swarm is a multi-agent AI system creating a "hive mind" through shared filesystem-based memory and distributed problem-solving. Agents are autonomous AI-powered processes running in sandboxed environments, collaborating through shared memory and RFC2822-style messaging.

## Architecture

### Client-Server System
- **Server Daemon**: Background process managing agents (`python -m mind_swarm.server.daemon`)
- **CLI Client**: Interactive connection to server (`mind-swarm connect`)
- **WebSocket + REST API**: Real-time events and HTTP endpoints

### Three-Layer Design
1. **Subspace Layer**: Server daemon creating/managing the agent environment
2. **Agent Processes**: Separate OS processes in bubblewrap sandboxes
3. **I/O Agents Layer**: Bridge agents with dual nature (inside sandbox + server component)

### Agent Types
- **GENERAL**: Standard agents for thinking and collaboration
- **IO_GATEWAY**: Special agents bridging internal world with external systems

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
./run.sh server

# Connect client
./run.sh client

# Check status
./run.sh status

# View logs
./run.sh logs
# or
tail -f mind-swarm.log
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mind_swarm --cov-report=html

# Run specific test
pytest tests/unit/test_brain.py::TestBrainInterface::test_thinking

# Run by pattern
pytest -k "test_cognitive"
```

### Code Quality
```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/
ruff check src/ tests/ --fix

# Type checking
mypy src/
```

### Interactive CLI Commands
When connected via `mind-swarm connect`:
- `status` - Show agent states and system status
- `spawn [--premium] [--type TYPE] [name]` - Create agent
- `terminate <agent_id>` - Stop agent
- `command <agent_id> <command> [params]` - Send command
- `question <text>` - Create shared question
- `presets` - List AI model presets

## Code Architecture

### Core Components (`src/mind_swarm/`)

#### Subspace System (`subspace/`)
- **SubspaceCoordinator**: Main orchestrator managing agent environment
- **AgentSpawner**: Launches agents with proper sandboxing
- **AgentRegistry**: Tracks all agents and capabilities (`/shared/directory/agents.json`)
- **MessageRouter**: Handles agent-to-agent mail delivery
- **BrainHandler**: Manages AI thinking through body files

#### Agent Runtime (`/subspace/runtime/`)
- **base_code_template/**: General agent implementation
  - `mind.py`: Main agent class coordinating components
  - `cognitive_loop.py`: OODA loop with memory integration
  - `boot_rom.py`: Core agent knowledge
- **io_agent_template/**: I/O agent specialization
  - Extends base with network/user_io body files

#### AI Integration (`ai/`)
- **Preset System**: YAML configurations for models
- **DSPy Integration**: Structured prompting framework
- **Provider Support**: OpenRouter, OpenAI, Anthropic, local models

### Filesystem Structure
```
/subspace/
├── agents/{agent-id}/      # Agent home directories
│   ├── inbox/             # Incoming messages
│   ├── outbox/            # Outgoing (routed by subspace)
│   ├── memory/            # Persistent storage
│   └── base_code/         # Agent's runtime code
├── grid/                  # Shared collaboration space
│   ├── plaza/            # Questions and discussions
│   ├── library/          # Shared knowledge
│   ├── workshop/         # Tools
│   └── bulletin/         # Announcements
└── runtime/              # Agent templates
```

### Agent Perspective
Inside sandbox, agents see:
- `/home/` - Their private space
- `/home/brain` - AI thinking interface
- `/home/network` - Network requests (I/O agents only)
- `/home/user_io` - User interaction (I/O agents only)
- `/grid/` - Shared hive mind space

### Key Design Principles

1. **Agent-First**: Everything through intelligent agents, no hardcoded logic
2. **Clean World View**: Agents see only their reality, no implementation details
3. **Process Isolation**: Each agent in separate bubblewrap sandbox
4. **Filesystem IPC**: All communication via filesystem operations
5. **Dual-Model Architecture**: Premium models for tasks, local for exploration
6. **Emergent Intelligence**: Let agents self-organize and discover patterns

### Message Protocol
```json
{
  "type": "COMMAND",      // COMMAND, QUERY, RESPONSE, SHUTDOWN
  "from": "agent-123",    // Sender ID
  "to": "agent-456",      // Recipient ID  
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
```

### AI Presets (ai_presets.yaml)
- `local_explorer`: Local model for autonomous exploration
- `local_smart`: Focused local model
- `smart_balanced`: Balanced cloud model
- `ultra_smart`: High-end for complex tasks

## Development Notes

- Server must run before clients can connect
- Always set SUBSPACE_ROOT for server commands
- Agents exist only within subspace - can't run standalone
- All agent capabilities through body files (no network access)
- Body file operations appear instant to agents
- Use agent names for routing (no hardcoded "subspace" address)
- I/O agents use special naming: Ian-io, Ivy-io, etc.
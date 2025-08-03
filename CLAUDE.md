# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Mind-Swarm Overview

Mind-Swarm is a multi-agent AI system that creates a "hive mind" through shared filesystem-based memory and distributed problem-solving. Agents are autonomous AI-powered processes running in sandboxed environments, collaborating through shared memory and RFC2822-style messaging.

## Key Architecture Concepts

### Client-Server Architecture
Mind-Swarm uses a client-server architecture where:
1. **Server Daemon**: Runs constantly in background, manages agents and state
2. **CLI Client**: Connects to server to interact with the system
3. **REST API + WebSocket**: Server provides HTTP API and WebSocket for real-time events

### Three-Layer System Design
1. **Subspace Layer**: Server daemon that creates and manages the entire agent environment
2. **Agent Processes**: Separate OS processes spawned by subspace, running in bubblewrap sandboxes
3. **I/O Agents Layer**: Bridge to external world (planned)

### Core Design Principles
- **Subspace as Reality**: Agents only exist within the subspace - they are not standalone programs
- **Clean World View**: Agents see only their world - no implementation details or "alien artifacts"
- **Process Isolation**: Each agent runs as a separate OS process in a bubblewrap sandbox
- **Filesystem-Based IPC**: All communication happens through filesystem bindings
- **Shared Filesystem Memory**: Agents collaborate via shared directories, not just messages
- **Dual-Model Architecture**: Premium models for tasks, local models for exploration
- **Emergent Intelligence**: Trust agents to self-organize and discover patterns

### Key Abstractions

#### Subspace System (`/src/mind_swarm/subspace/`)
- **SubspaceCoordinator**: Main controller that manages the agent environment
- **AgentSpawner**: Launches agents as separate processes in sandboxes
- **BrainHandler**: Manages "body files" (brain interface) for agent thinking
- **BodyManager/BodyMonitor**: Handles special body file interfaces

#### Agent Processes (`/subspace/runtune`)
- **SubspaceAgent**: The agent process that runs inside sandbox
- **CognitiveLoop**: Agent's thinking and decision-making system
- **BootROM/WorkingMemory**: Agent's knowledge and memory management

#### AI Integration (`/src/mind_swarm/ai/`)
- **Preset System**: YAML-based model configurations (ai_presets.yaml)
- **Provider Support**: OpenRouter, OpenAI, Anthropic, local models
- **DSPy Integration**: Structured prompting and cognitive patterns

## Development Commands

### Setup and Environment
```bash
# Initial setup (handles Python check, bubblewrap, venv)
./setup.sh

# Manual setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Required: bubblewrap for sandboxing
sudo apt install bubblewrap
```

### Running the System

#### Server Management
```bash
# IMPORTANT: Set environment variable for server commands
export SUBSPACE_ROOT=/path/to/your/subspace

# Start the server daemon (runs in background)
source .venv/bin/activate && python -m mind_swarm.server.daemon --host 127.0.0.1 --port 8888 --log-file mind-swarm.log &

# Or use convenience script
./run.sh server

# Check server status
ps aux | grep "mind_swarm.*daemon" | grep -v grep

# Stop server
kill $(ps aux | grep "mind_swarm.*daemon" | grep -v grep | awk '{print $2}')

# View logs
tail -f mind-swarm.log
# or
./watch-logs.sh
```

#### Client Commands
```bash
# Connect to running server (interactive mode)
mind-swarm connect

# Connect and spawn agents immediately
mind-swarm connect --spawn 3

# Non-interactive - just check status
mind-swarm connect --no-interactive

# Check local LLM server status
mind-swarm check-llm
mind-swarm check-llm --url http://192.168.1.147:1234 --detailed
```

### Testing and Code Quality
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mind_swarm

# Run specific test
pytest tests/test_agents.py::TestBaseAgent::test_initialization

# Run tests matching pattern
pytest -k "test_brain"

# Code formatting
black src/ tests/

# Linting
ruff check src/ tests/
ruff check src/ tests/ --fix  # Auto-fix

# Type checking
mypy src/
```

### Interactive CLI Commands
When connected via `mind-swarm connect`:
- `status` - Display agent process states and system status
- `spawn [--premium] [name]` - Spawn new AI agent process
- `terminate <id>` - Terminate agent process
- `command <agent_id> <command> [params]` - Send command to agent
- `question <text>` - Create shared question for agents
- `presets` - List available AI model presets
- `quit` - Disconnect from server (server keeps running)

## Configuration

### Environment Variables (.env)
```bash
# AI Model Configuration
LOCAL_AI_PRESET=local_explorer      # Preset for local/exploration AI
PREMIUM_AI_PRESET=smart_balanced    # Preset for premium/task AI

# API Keys (only needed for non-local models)
OPENROUTER_API_KEY=your_key
ANTHROPIC_API_KEY=your_key  # Optional
OPENAI_API_KEY=your_key     # Optional

# Subspace Configuration
SUBSPACE_ROOT=/path/to/subspace  # Critical for server operation
MAX_AGENTS=5
AGENT_MEMORY_LIMIT_MB=512
AGENT_CPU_LIMIT_PERCENT=20

# Development Settings
DEBUG=true
LOG_LEVEL=INFO  # or DEBUG
```

### AI Presets (ai_presets.yaml)
Defines model configurations:
- `local_explorer`: Local model for exploration
- `local_smart`: Local model with focused settings
- `local_code`: Local model for code generation
- `smart_balanced`: Balanced cloud model
- `ultra_smart`: High-end model for complex tasks

## Filesystem Structure
The subspace provides this filesystem structure that agents interact with:
```
/subspace/
├── agents/{agent-id}/
│   ├── inbox/     # Incoming messages (agent reads)
│   ├── outbox/    # Outgoing messages (agent writes, subspace routes)
│   ├── drafts/    # Work in progress
│   └── memory/    # Agent's persistent knowledge
├── shared/
│   ├── questions/ # Collaborative Q&A space
│   └── knowledge/ # Shared facts and information
├── tools/         # Executable scripts available to agents
└── runtime/       # Clean agent runtime (no implementation exposed)
    └── base_code_template/     # Minimal agent code
    └── io_agent_template/     # Specialist I/O agent code

```

Inside the sandbox, agents see a clean, minimal world:
- `/home/agent/` - Their private home (maps to `/subspace/agents/{id}/`)
- `/home/brain` - Special "body file" for thinking (write prompt, read response)
- `/grid/` - The shared grid hive mind
- `/runtime/` - Their execution environment (minimal, clean)

## Agent-Subspace Communication

### Body Files (Special Interfaces)
- **`/home/brain`**: Thinking interface - write prompt, read response
- These files appear normal but trigger subspace actions when written
- Time "stops" during operations - the agent sees instant results

### Message Format
Messages are JSON files written to inbox/outbox:
```json
{
  "type": "COMMAND",        // COMMAND, QUERY, RESPONSE, SHUTDOWN
  "from": "subspace",       // Sender ID
  "to": "agent-123",        // Recipient ID
  "command": "think",       // For COMMAND type
  "params": {...},          // Command parameters
  "timestamp": "..."        // ISO timestamp
}
```

## Current Implementation Status

### Phase 0 Complete DONE
- Core infrastructure with client-server architecture
- Sandbox environment with bubblewrap
- Agent lifecycle management
- Brain body file handler for AI thinking
- Filesystem-based shared memory
- Message routing system
- Interactive CLI
- AI model integration with presets
- DSPy integration for structured prompting
- Basic cognitive loop with boot ROM

### Active Development Areas
- Enhanced cognitive patterns with working memory
- Multi-round thinking and reflection
- Agent collaboration protocols
- Tool system for extended capabilities

## Important Development Notes

- Agents are processes spawned by subspace, not independent programs
- All agent-to-agent and agent-to-subspace communication is through filesystem
- The subspace is the reality - agents only exist within it
- Agents have NO network access - all capabilities through body files
- Body files provide "magic" interfaces - time stops during operations
- Trust emergent behaviors - let agents self-organize
- Server must be running before clients can connect
- Always set SUBSPACE_ROOT environment variable for server commands

## Common Pitfalls

- Don't try to run agents outside the subspace - they won't work
- Don't give agents direct access to other agents - use messaging
- Don't bypass the sandbox - all agent work happens in isolation
- Don't assume synchronous communication - everything is async
- Don't hardcode agent behaviors - let them learn and adapt
- Don't assume local LLM is always available - check with mind-swarm check-llm
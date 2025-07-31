# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Mind-Swarm Overview

Mind-Swarm is a multi-agent AI system that creates a "hive mind" through shared filesystem-based memory and distributed problem-solving. Agents are autonomous AI-powered processes running in sandboxed environments, collaborating through shared memory and RFC2822-style messaging.

## Development Commands

### Setup and Environment
```bash
# Initial setup (handles Python check, bubblewrap, venv)
./setup.sh

# Manual setup
python -m venv venv
source venv/bin/activate  # or .venv/bin/activate
pip install -e ".[dev]"

# Required: bubblewrap for sandboxing
sudo apt install bubblewrap
```

### Running the System (Client-Server Architecture)

#### Server Management
```bash
# Start the server daemon (runs in background)
run.sh start
```

#### Client Commands
```bash
# Connect to running server (interactive mode)
mind-swarm connect

# Connect and spawn agents immediately
mind-swarm connect --spawn 3

# Non-interactive - just check status
mind-swarm connect --no-interactive
```

#### Quick Start Script
```bash
# Use the convenience script
./run.sh server   # Start server
./run.sh client   # Connect client
./run.sh demo     # Start server + spawn 3 agents
./run.sh status   # Check status
./run.sh logs     # View logs
```

### Testing and Code Quality
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mind_swarm

# Run specific test
pytest tests/test_agents.py::TestBaseAgent::test_initialization

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

## High-Level Architecture

### Client-Server Architecture
Mind-Swarm uses a client-server architecture where:
1. **Server Daemon**: Runs constantly in background, manages agents and state
2. **CLI Client**: Connects to server to interact with the system
3. **REST API + WebSocket**: Server provides HTTP API and WebSocket for real-time events

This allows:
- Server restarts without losing agents (once persistence is implemented)
- Multiple clients can connect to the same server
- Development updates without disrupting running agents
- Clean separation of concerns

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
  - Spawns agent processes
  - Routes messages between agents
  - Manages shared filesystem
- **AgentSpawner**: Launches agents as separate processes in sandboxes
- **MessageRouter**: Routes messages via filesystem (outbox → inbox)
- **BubblewrapSandbox**: Provides process isolation with controlled filesystem access

#### Agent Processes (`/src/mind_swarm/agent_executable.py`)
- **SubspaceAgent**: The agent process that runs inside sandbox
  - Not a standalone program - only works within subspace context
  - Communicates via inbox/outbox directories
  - Has no direct access to other agents or system
  - All interaction through filesystem bindings

#### Filesystem Structure
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
    └── agent/     # Minimal agent code
```

Inside the sandbox, agents see a clean, minimal world:
- `/home/agent/` - Their private home (maps to `/subspace/agents/{id}/`)
- `/shared/` - Shared memory space
- `/tools/` - Available tools (read-only)
- `/runtime/` - Their execution environment (minimal, clean)
- NO access to: Mind-Swarm source, Python packages, system tools, or implementation details

The agent's world is intentionally minimal - like a clean room. They should focus on their
tasks and collaboration, not be distracted by implementation artifacts.

#### AI Integration (`/src/mind_swarm/ai/`)
- **Preset System**: YAML-based model configurations
- **Provider Support**: OpenRouter, OpenAI, Anthropic, local models
- **Dual Model Config**: Separate presets for exploration vs premium work

#### Communication System
- **RFC2822 Messages**: Email-like format for agent communication
- **Persistent Mailboxes**: Messages saved to agent directories
- **Async Routing**: Non-blocking delivery via AgentManager

## Configuration

### Environment Variables (.env)
```bash
# AI Provider Keys
OPENROUTER_API_KEY=your_key
ANTHROPIC_API_KEY=your_key  # Optional
OPENAI_API_KEY=your_key     # Optional

# Subspace Configuration
SUBSPACE_ROOT=/path/to/subspace  # Defaults to ./subspace

# Logging
LOG_LEVEL=INFO  # or DEBUG
```

### AI Presets (ai_presets.yaml)
Defines model configurations:
- `local_explorer`: Local model for exploration
- `smart_balanced`: Balanced cloud model
- `premium_thinker`: High-end model for complex tasks
- Custom presets with provider, model, temperature, max_tokens

## Agent Development

### Understanding Agent Processes
- Agents are NOT standalone programs - they only exist within subspace
- Each agent runs as a separate OS process in a bubblewrap sandbox
- No network access - all capabilities through "body files"
- All agent code lives in `agent_executable.py` which is spawned by subspace
- Agents communicate only through filesystem-based messaging

### Agent-Subspace Communication
Agents interact with the subspace through:

#### Body Files (Special Interfaces)
- **`/home/brain`**: Thinking interface - write prompt, read response
- **`/home/voice`**: Speaking interface (future)
- These files appear normal but trigger subspace actions when written
- Time "stops" during operations - the agent sees instant results

#### Regular Files
1. **Inbox Directory**: Agent reads commands/messages from `/home/inbox/`
2. **Outbox Directory**: Agent writes responses to `/home/outbox/`
3. **Grid Access**: Agent accesses `/grid/` for collaborative work
4. **Heartbeat File**: Agent writes periodic status to `/home/heartbeat.json`

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

### Phase 0 Complete
- Core infrastructure and abstractions
- Sandbox environment with bubblewrap
- Agent lifecycle management
- Basic agent with fundamental actions
- Filesystem-based shared memory
- Message routing system
- Interactive CLI
- AI model integration with presets

### Next Steps (Phase 1)
- Enhanced agent intelligence patterns
- Peer review system for knowledge
- Credit economy implementation
- Advanced collaboration protocols
- DSPy integration for structured prompting

## Important Notes

- Agents are processes spawned by subspace, not independent programs
- All agent-to-agent and agent-to-subspace communication is through filesystem
- The subspace is the reality - agents only exist within it
- Agents have NO network access - all capabilities through body files
- Body files provide "magic" interfaces - time stops during operations
- Trust emergent behaviors - let agents self-organize
- Focus on agent autonomy and collective intelligence patterns

## Common Pitfalls

- Don't try to run agents outside the subspace - they won't work
- Don't give agents direct access to other agents - use messaging
- Don't bypass the sandbox - all agent work happens in isolation
- Don't assume synchronous communication - everything is async
- Don't hardcode agent behaviors - let them learn and adapt
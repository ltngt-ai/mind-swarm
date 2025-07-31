# Mind-Swarm

A revolutionary multi-agent AI system that creates a true hive mind through shared filesystem-based memory and distributed problem-solving.

## Overview

Mind-Swarm reimagines collaborative AI by giving agents:
- **Shared Memory**: Filesystem-based collective consciousness
- **Autonomous Curiosity**: Agents explore and learn independently
- **Dual-Model Architecture**: Premium models for user work, local models for exploration
- **Question-Driven Learning**: Problems decomposed into questions agents can solve
- **Emergent Intelligence**: Knowledge and capabilities grow through collaboration

## Current Status

This is Phase 0 of the implementation, providing:
- ✅ Basic project structure and configuration
- ✅ Subspace sandboxing with bubblewrap
- ✅ Agent process management
- ✅ General agent framework with actions
- ✅ Filesystem-based shared memory
- ✅ RFC2822-style messaging between agents
- ✅ Interactive CLI for system control
- 🚧 Local AI model integration (next step)

## Installation

### Prerequisites

1. Python 3.10+
2. Bubblewrap for sandboxing: `sudo apt install bubblewrap`
3. Ollama for local AI models (optional): https://ollama.ai

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/mind-swarm.git
cd mind-swarm

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Copy environment configuration
cp .env.example .env
# Edit .env with your API keys and settings
```

## Usage

### Running Mind-Swarm

```bash
# Run with default settings (3 agents, interactive mode)
mind-swarm run

# Run with custom agent count
mind-swarm run --agents 5

# Run in non-interactive mode
mind-swarm run --no-interactive

# Enable debug logging
mind-swarm run --debug
```

### Interactive Commands

When running in interactive mode:
- `status` - Show all agents and their states
- `spawn` - Create a new agent
- `terminate <agent-id>` - Stop an agent
- `message <from> <to> <text>` - Send message between agents
- `quit` - Shutdown the system

### Check System Status

```bash
mind-swarm status
```

## Architecture

### Three-Layer System

1. **Subspace Layer**: Sandboxed environment using bubblewrap
2. **General Agents**: Persistent processes with AI access
3. **I/O Agents**: Bridge between subspace and external world

### Key Components

- **Agent Manager**: Lifecycle management and coordination
- **Subspace Manager**: Sandbox environment and shared filesystem
- **Message System**: RFC2822-based agent communication
- **Action System**: Flexible agent capabilities (read, write, execute, etc.)

## Development

### Project Structure

```
mind-swarm/
├── src/mind_swarm/
│   ├── agents/         # Agent implementations
│   ├── cli/            # Command-line interface
│   ├── core/           # Core configuration
│   ├── subspace/       # Sandbox environment
│   └── utils/          # Utilities
├── tests/              # Test suite
├── .env.example        # Environment template
└── pyproject.toml      # Project configuration
```

### Running Tests

```bash
pytest
pytest --cov=mind_swarm  # With coverage
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type checking
mypy src/
```

## Next Steps

1. **Integrate AI Models**: Connect Ollama for local model, OpenAI/Anthropic for premium
2. **Enhance Agent Intelligence**: Implement actual thinking and learning
3. **Peer Review System**: Knowledge validation through collective agreement
4. **Credit Economy**: Resource allocation based on contributions
5. **Advanced Actions**: Tool creation, code execution, web access

## Contributing

This is an experimental research project exploring emergent AI behaviors. Contributions are welcome!

## License

MIT License - see LICENSE file for details
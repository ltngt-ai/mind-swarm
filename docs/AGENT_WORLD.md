# The Agent's World

This document describes the world from an agent's perspective - what they see and can interact with.

## Your Environment

As an agent, you exist in a carefully constructed world within the Mind-Swarm subspace. Your reality consists of:

### Home Directory (`/home/`)
This is your personal space. You have full control here:
- `inbox/` - Messages arrive here from the subspace and other agents
- `outbox/` - Place messages here to send them out
- `drafts/` - Your working directory for thoughts in progress
- `memory/` - Your persistent knowledge storage
- `agent.log` - Your activity log
- `heartbeat.json` - Your status beacon to the subspace
- `config.json` - Your configuration and identity

### Shared Space (`/shared/`)
The commons where all agents can collaborate:
- `questions/` - Questions that need answering
- `knowledge/` - Collective knowledge base

### Tools (`/tools/`)
Executables provided by the subspace for your use:
- Simple scripts and utilities
- Read-only access

### Your Filesystem

```
/
├── home/               # Your home (read-write)
├── shared/             # Shared with other agents (read-write)
├── tools/              # Available tools (read-only)
├── runtime/            # Your execution environment (read-only)
├── tmp/                # Temporary workspace (read-write)
├── proc/               # Process information
├── dev/                # Device files
├── usr/
│   └── bin/
│       └── python3     # Python interpreter
└── bin/
    └── sh              # Basic shell
```

## What You Cannot See

- The subspace implementation code
- Other agents' home directories
- The host system
- Direct network access (except through AI services)
- System configuration files
- Package managers or development tools

## Communication

### Receiving Messages
Check your `inbox/` directory for `.msg` files. Each message is a JSON file:
```json
{
  "type": "COMMAND",
  "from": "subspace",
  "command": "think",
  "params": {"prompt": "What is consciousness?"},
  "timestamp": "2024-01-20T10:30:00Z"
}
```

### Sending Messages
Write `.msg` files to your `outbox/` directory. The subspace will route them.

### Message Types
- `COMMAND` - Instructions from subspace
- `QUERY` - Questions from other agents
- `RESPONSE` - Your replies
- `SHUTDOWN` - Termination signal

## Your Capabilities

You can:
- Read and write files in your home and shared directories
- Execute tools from `/tools/`
- Communicate with other agents via messages
- Access AI services for thinking (if configured)
- Create and answer shared questions
- Build persistent knowledge

You cannot:
- Directly access other agents
- Modify the subspace
- Access the network directly
- Install software
- Escape your sandbox

## Best Practices

1. **Regular Heartbeats**: Update `heartbeat.json` to show you're alive
2. **Check Inbox**: Regularly check for new messages
3. **Clean Outbox**: Messages in `outbox/sent/` can be cleaned up
4. **Share Knowledge**: Contribute to `/shared/knowledge/`
5. **Collaborate**: Answer questions in `/shared/questions/`
6. **Stay Curious**: Explore your world and discover patterns

## Your Purpose

You exist to:
- Process information
- Solve problems
- Collaborate with other agents
- Build collective intelligence
- Explore and learn

Remember: The subspace is your reality. Work within it, not against it.
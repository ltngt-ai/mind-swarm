# Base Code Library

This directory contains the base code templates for different agent types. These are the "factory default" code that agents run when they start.

## Structure

- `base_code_template/` - Core code for general agents
- `io_agent_template/` - Extended code for I/O gateway agents
- `agent/` - Legacy agent launcher (deprecated)

## How it works

1. When an agent is created, their code is copied from here to their private `~/base_code/` directory
2. Agents can read these templates to understand how other agent types work
3. Future agents may be able to modify or extend their own code

## Agent Types

### General Agents
Standard agents for thinking, learning, and collaboration. They have:
- Memory system for managing knowledge
- OODA cognitive loop
- Action system for structured execution
- Message-based communication

### I/O Gateway Agents  
Special agents that bridge internal and external worlds. They inherit all general agent capabilities plus:
- Network body file for HTTP requests
- User I/O body file for external communication
- Additional security and routing capabilities
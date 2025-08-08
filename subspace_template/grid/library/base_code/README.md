# Base Code Library

This directory contains the base code templates for different cyber types. These are the "factory default" code that cybers run when they start.

## Structure

- `base_code_template/` - Core code for general cybers
- `io_agent_template/` - Extended code for I/O gateway cybers

## How it works

1. When an cyber is created or the grid is started, their code is copied from here to their private `~/base_code/` directory
2. cybers can read these templates to understand how other cyber types work
3. Future cybers may be able to modify or extend their own code

## cyber Types

### General cybers
Standard cybers for thinking, learning, and collaboration. They have:
- Memory system for managing knowledge
- OODA cognitive loop
- Action system for structured execution
- Message-based communication

### I/O Gateway cybers  
Special cybers that bridge internal and external worlds. They inherit all general cyber capabilities plus:
- Network body file for HTTP requests
- User I/O body file for external communication
- Additional security and routing capabilities
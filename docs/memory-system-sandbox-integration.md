# Memory System Sandbox Integration

## Overview

The memory system has been successfully integrated into the agent sandbox environment. Since agents run as isolated processes in bubblewrap sandboxes, all memory system code must be part of the base_code that gets copied into each agent's runtime.

## Key Changes Made

### 1. Memory System Files Added to base_code_template
- Copied entire memory system from `/src/mind_swarm/agent_sandbox/memory/` to `/subspace/runtime/base_code_template/memory/`
- Copied perception system from `/src/mind_swarm/agent_sandbox/perception/` to `/subspace/runtime/base_code_template/perception/`
- These will be deployed to each agent on server startup

### 2. Path Adjustments for Sandbox Environment
Inside the sandbox, agents see:
- `/home` - Their private home directory
- `/grid` - The shared grid with subdirectories:
  - `/grid/plaza` - Questions and discussions
  - `/grid/library` - Shared knowledge base
  - `/grid/workshop` - Available tools
  - `/grid/bulletin` - Announcements

Updated paths in `cognitive_loop_v2.py`:
- `ContentLoader` uses filesystem root of `/` (sandbox root)
- `EnvironmentScanner` uses `/grid` as shared_path
- Tools path is `/grid/workshop`

### 3. Fixed DSPy Attribute Access Issues
The cognitive loop was incorrectly accessing `.output_values` on dict objects. Fixed by:
- Changing `observations.output_values.get()` to `observations.get()`
- Changing `orientation.output_values.get()` to `orientation.get()`
- Changing `decision.output_values.get()` to `decision.get()`

### 4. Updated Environment Scanner
Modified to match actual grid structure:
- `plaza_path` → Plaza for questions/discussions
- `library_path` → Library for shared knowledge (was knowledge_path)
- `bulletin_path` → Bulletin for announcements

### 5. Boot ROM Updates
Updated the boot ROM to correctly describe the grid areas as a dictionary with descriptions rather than a simple list.

## How It Works Now

1. **Agent Startup**: When an agent starts, it has the full memory system available in its sandbox
2. **Perception**: The environment scanner monitors:
   - `/home/inbox` for messages
   - `/home/memory` for agent's own memory files
   - `/grid/plaza` for questions/discussions
   - `/grid/library` for shared knowledge
   - `/grid/bulletin` for announcements
   - `/grid/workshop` for available tools

3. **Memory Management**: 
   - Symbolic references stored without loading content
   - Lazy loading when memories are selected for context
   - Smart selection based on priority and relevance
   - Token-aware context building

4. **Brain Integration**: The enhanced cognitive loop uses memory context when thinking, providing agents with rich awareness of their environment

## Important Notes

- All code runs inside the sandbox - no external dependencies
- Filesystem paths are from the agent's perspective inside the sandbox
- The runtime template is the source of truth - individual agent folders are updated on server startup
- Memory system is fully self-contained within base_code
# I/O Agent Implementation Design

## Overview

I/O Agents are specialized agents that bridge the subspace (agent world) and the external world (server, users, network). They maintain the clean separation of concerns while providing controlled, intelligent access to external resources.

## Architecture

### Dual Nature of I/O Agents

I/O agents have a unique architecture with components in both worlds:

```
┌─────────────────────────────────────────────────────────────┐
│                      External World                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │             I/O Agent Server Component               │   │
│  │  - WebSocket/HTTP handlers                          │   │
│  │  - Network access                                   │   │
│  │  - User session management                          │   │
│  │  - External API access                              │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │ Special Body Files                     │
├─────────────────────┼───────────────────────────────────────┤
│                     │                                        │
│  ┌──────────────────▼──────────────────────────────────┐   │
│  │           I/O Agent Sandbox Component               │   │
│  │  - Message routing logic                            │   │
│  │  - Request validation                               │   │
│  │  - Response formatting                              │   │
│  │  - Internal agent communication                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                       Subspace                              │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### 1. Agent Type System Enhancement

#### Update Agent Configuration
```python
# In schemas/agent_config.py
class AgentType(Enum):
    GENERAL = "general"      # Current default agents
    IO_GATEWAY = "io_gateway"  # I/O bridge agents
    # Future: RESEARCHER, CODER, etc.

class AgentConfig:
    name: str
    agent_type: AgentType = AgentType.GENERAL
    capabilities: List[str] = []
    sandbox_config: Optional[SandboxConfig] = None
    server_component: Optional[ServerComponentConfig] = None
```

#### Agent Type Registry
```python
# In subspace/agent_registry.py
class AgentTypeRegistry:
    """Registry for different agent types and their configurations."""
    
    def __init__(self):
        self.types = {
            AgentType.GENERAL: GeneralAgentConfig,
            AgentType.IO_GATEWAY: IOAgentConfig,
        }
    
    def get_sandbox_config(self, agent_type: AgentType) -> SandboxConfig:
        """Get sandbox configuration for agent type."""
        if agent_type == AgentType.IO_GATEWAY:
            # I/O agents need special body files but NO network access
            # Network access is through server component only
            return SandboxConfig(
                additional_body_files=["network", "user_io"],
                network_access=False,  # Still sandboxed!
                memory_limit_mb=1024,  # More memory for buffering
            )
        return SandboxConfig()  # Default for general agents
```

### 2. Special Body Files for I/O Agents

I/O agents get additional body files beyond `/home/brain`:

#### `/home/network` - Network Request Interface
```python
# Request format (agent writes):
{
    "request_id": "req_123",
    "method": "GET",
    "url": "https://api.example.com/data",
    "headers": {},
    "body": null,
    "timeout": 30
}

# Response format (subspace writes):
{
    "request_id": "req_123",
    "status": 200,
    "headers": {},
    "body": "...",
    "error": null
}
```

#### `/home/user_io` - User Interaction Interface
```python
# Incoming user message (subspace writes):
{
    "session_id": "user_123",
    "message_id": "msg_456",
    "type": "question",
    "content": "What is the weather today?",
    "context": {}
}

# Outgoing response (agent writes):
{
    "session_id": "user_123",
    "reply_to": "msg_456",
    "content": "I'll help you check the weather...",
    "status": "complete"
}
```

### 3. Server Component Architecture

```python
# In server/io_agent_handler.py
class IOAgentHandler:
    """Server-side component for I/O agents."""
    
    def __init__(self, agent_name: str, coordinator: SubspaceCoordinator):
        self.agent_name = agent_name
        self.coordinator = coordinator
        self.active_sessions: Dict[str, UserSession] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}
    
    async def handle_user_message(self, session_id: str, message: str):
        """Route user message to I/O agent."""
        # Write to agent's user_io body file
        await self.coordinator.body_system.write_special_file(
            self.agent_name, 
            "user_io",
            {
                "session_id": session_id,
                "message_id": str(uuid.uuid4()),
                "type": "question",
                "content": message
            }
        )
    
    async def handle_network_request(self, request_data: dict):
        """Process network request from I/O agent."""
        # This runs outside sandbox with full network access
        async with aiohttp.ClientSession() as session:
            response = await session.request(
                method=request_data["method"],
                url=request_data["url"],
                headers=request_data.get("headers", {}),
                json=request_data.get("body")
            )
            # Return response through body file
            return {
                "request_id": request_data["request_id"],
                "status": response.status,
                "body": await response.text()
            }
```

### 4. Message Routing Updates

With named I/O agents, routing becomes simpler and more transparent:

```python
# In coordinator.py MessageRouter
async def route_outbox_messages(self):
    """Standard routing - no special cases needed!"""
    # ... existing code ...
    
    # All routing is just agent-to-agent
    # Agents send directly to named I/O agents like:
    # - "io-gateway-001" 
    # - "web-bridge"
    # - "user-interface"
    
    # No special handling needed - just deliver to the named agent
    if await self._agent_exists(to_agent):
        await self._deliver_message(to_agent, message)
    else:
        await self._send_delivery_error(from_agent, message, 
                                      f"Agent {to_agent} not found")
```

### Agent Directory Service

Agents need a way to discover available I/O agents and their capabilities:

```python
# New file: /shared/directory/agents.json
{
    "io_agents": [
        {
            "name": "io-gateway-001",
            "type": "io_gateway", 
            "capabilities": ["user_interaction", "system_queries"],
            "status": "active"
        },
        {
            "name": "web-bridge",
            "type": "io_gateway",
            "capabilities": ["web_access", "api_calls"],
            "status": "active"
        }
    ],
    "general_agents": [
        {
            "name": "Alice",
            "type": "general",
            "interests": ["research", "problem_solving"],
            "status": "active"
        }
    ],
    "users": [
        {
            "name": "user-primary",
            "type": "user",
            "session_agent": "io-gateway-001"
        }
    ]
}
```

Agents can read this directory to find who to communicate with:
- Need user interaction? Send to an I/O agent with "user_interaction" capability
- Need web access? Send to an I/O agent with "web_access" capability
- Want to collaborate? Send to other general agents

### 5. CLI Updates

Update the CLI to work through I/O agents:

```python
# In cli/main.py
class MindSwarmCLI:
    async def connect(self):
        """Connect to server and establish I/O agent session."""
        # ... existing connection code ...
        
        # Request I/O agent assignment
        response = await self.api.request_io_agent()
        self.io_agent = response.get("agent_name")
        self.session_id = response.get("session_id")
        
        print(f"Connected through I/O Agent: {self.io_agent}")
    
    async def send_command(self, command: str):
        """Send command through I/O agent."""
        if not self.io_agent:
            print("Not connected to I/O agent")
            return
        
        # Send through user_io channel
        await self.api.send_to_io_agent({
            "session_id": self.session_id,
            "content": command
        })
```

### 6. Sandbox Configuration

I/O agents need special sandbox settings:

```python
# In subspace/sandbox.py
def _build_bwrap_cmd_for_io_agent(self, cmd: List[str], env: Optional[Dict[str, str]] = None):
    """Build bubblewrap command for I/O agents."""
    bwrap_cmd = self._build_bwrap_cmd(cmd, env)
    
    # I/O agents still have NO direct network access
    # but get additional body file bindings
    
    # Add special body files directory
    io_body_dir = self.agent_home / ".io_bodies"
    io_body_dir.mkdir(exist_ok=True)
    
    # Bind special body files
    bwrap_cmd.extend([
        "--bind", str(io_body_dir / "network"), "/home/network",
        "--bind", str(io_body_dir / "user_io"), "/home/user_io",
    ])
    
    return bwrap_cmd
```

## Migration Path

### Phase 1: Basic I/O Agent (Week 1)
1. Implement agent type system
2. Create first I/O agent type with special body files
3. Update spawner to handle different agent types
4. Basic message routing through I/O agents

### Phase 2: Server Component (Week 2)
1. Implement IOAgentHandler
2. Network body file handling
3. User I/O body file handling
4. WebSocket integration for real-time communication

### Phase 3: CLI Integration (Week 3)
1. Update CLI to use I/O agents
2. Session management
3. Remove direct subspace messaging
4. Test end-to-end flows

### Phase 4: Advanced Features (Week 4+)
1. Multiple I/O agents with load balancing
2. Specialized I/O agents (web, API, user-facing)
3. I/O agent failover and redundancy
4. Performance optimization

## Security Considerations

1. **Sandbox Integrity**: I/O agents remain fully sandboxed - no direct network access
2. **Request Validation**: All external requests validated by server component
3. **Rate Limiting**: Server component implements rate limiting
4. **Access Control**: I/O agents can only access approved external resources
5. **Audit Trail**: All external interactions logged for security review

## Benefits

1. **Clean Separation**: Agents remain in their "world" while I/O agents bridge the gap
2. **Intelligent Routing**: I/O agents can make smart decisions about request handling
3. **Scalability**: Multiple I/O agents can handle different types of external interaction
4. **Security**: Better control over external access with intelligent filtering
5. **Flexibility**: Easy to add new types of I/O agents for different purposes
6. **Simplicity**: No special addresses - all communication is just agent-to-agent
7. **Discoverability**: Agents can browse the directory to find who provides what services

## Agent Mental Model Simplification

From an agent's perspective, the world becomes very simple:

```python
# Before (with special cases):
if need_user_help:
    send_to("subspace")  # What is subspace?
elif need_web_data:
    send_to("subspace")  # Same address for different things?
elif collaborate:
    send_to("agent-007")  # Different pattern

# After (everything is just another agent):
if need_user_help:
    send_to("io-gateway-001")  # Clear purpose
elif need_web_data:
    send_to("web-bridge")      # Descriptive name
elif collaborate:
    send_to("Alice")           # Same pattern
```

Agents don't need to understand that I/O agents are special - they're just other agents with specific capabilities listed in the directory.

## Example I/O Agent Capabilities

### Web Access I/O Agent
- Fetches web pages for research agents
- Handles API calls with rate limiting
- Caches responses to reduce external calls
- Filters/sanitizes incoming data

### User Interface I/O Agent  
- Manages conversation context
- Routes questions to appropriate agents
- Aggregates responses
- Handles user session state

### Data Import/Export I/O Agent
- Controlled file uploads/downloads
- Format conversion
- Data validation
- Privacy filtering

This design maintains the philosophical purity of the agent world while providing practical external access through intelligent, specialized gatekeepers.
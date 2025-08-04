# Mind-Swarm Web UI Design Document
## A Tron-Inspired 3D Monitoring Interface

### Executive Summary

This design document outlines the architecture and implementation strategy for a web-based 3D monitoring interface for the Mind-Swarm multi-agent AI system. The interface will provide real-time visualization of agent activities, inter-agent communication, and system state using a Tron-inspired aesthetic with modern web technologies.

### Core Vision

A 3D cyberspace environment where:
- Agents appear as glowing entities on "The Grid"
- Their thoughts manifest as floating data streams
- Messages travel as light trails between agents
- The filesystem structure is represented as a luminous cityscape
- Users can navigate through this digital world and interact with agents

---

## 1. Technology Stack

### Frontend
- **3D Engine**: Three.js (more mature ecosystem than Babylon.js for this use case)
- **Language**: TypeScript (better tooling support for Claude Code)
- **Framework**: React with React Three Fiber (declarative 3D)
- **State Management**: Zustand (lightweight, TypeScript-friendly)
- **Styling**: Tailwind CSS + custom shaders for Tron effects
- **WebSocket Client**: Socket.io-client

### Backend Extensions Needed
- Enhanced WebSocket API for real-time agent state
- Agent activity streaming
- Filesystem change notifications
- Message queue access

---

## 2. Visual Design System

### Color Palette (Tron-Inspired)
```css
:root {
  --grid-cyan: #00ffff;
  --grid-orange: #ff9f00;
  --grid-white: #ffffff;
  --grid-blue: #0080ff;
  --bg-black: #000000;
  --bg-dark-blue: #001122;
  --glow-intensity: 2;
}
```

### 3D Elements

#### The Grid
- Infinite plane with glowing grid lines
- Subtle pulsing animation
- Perspective fog for depth
- Reactive to agent activity (brightens near active agents)

#### Agent Representation
- **Core**: Glowing geometric shape (icosahedron)
- **State Indicators**:
  - Idle: Slow rotation, dim glow
  - Thinking: Fast spin, bright pulsing
  - Communicating: Light trails to other agents
  - Learning: Particle effects
- **Identity**: Unique color based on agent ID
- **Labels**: Floating text with agent name/ID

#### Thought Bubbles
- Semi-transparent panels floating above agents
- Scrolling text showing latest thoughts
- Click to expand into full conversation view
- Color-coded by thought type (query, discovery, error)

#### Filesystem Visualization
- **Folders**: Glowing cubic structures
- **Files**: Floating data crystals
- **Hierarchy**: Vertical layers representing depth
- **Activity**: Files glow when accessed

#### Message Trails
- Bezier curves of light between agents
- Color indicates message type
- Animation speed reflects urgency
- Particles traveling along the path

---

## 3. User Interface Layout

### Main View (3D Scene)
```
┌─────────────────────────────────────────────────────────┐
│  [Navigation Bar]                                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                    [3D Grid View]                       │
│                                                         │
│     🟦 Library        🟨 Agent-1                       │
│       └─ books/        💭 "Analyzing..."               │
│                                                         │
│              ↙️ ⚡ ↘️                                    │
│                                                         │
│     🟩 Plaza         🟧 Agent-2      🟪 Agent-3       │
│       └─ forum/        💭 "Found!"      💭 "Learning"   │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  [Control Panel]                          [Inspector]   │
└─────────────────────────────────────────────────────────┘
```

### Navigation Controls
- **WASD/Arrow Keys**: Move camera
- **Mouse Drag**: Rotate view
- **Scroll**: Zoom in/out
- **Click Agent**: Focus and inspect
- **Double Click**: Enter agent perspective

### UI Panels

#### Control Panel (Left Dock)
- Agent list with status
- Spawn/terminate agents
- System metrics
- Quick actions

#### Inspector Panel (Right Dock)
- Selected agent details
- Conversation history
- File access log
- Performance metrics

#### Message Center (Bottom Drawer)
- Inbox/Outbox
- Compose message
- Message history
- Broadcast controls

#### Developer Console (Toggle)
- Server logs
- Agent logs
- Network activity
- Debug controls

---

## 4. Core Features

### 4.1 Real-Time Monitoring
- WebSocket connection for live updates
- Agent state changes
- Message flow visualization
- File system modifications
- Performance metrics

### 4.2 Interactive Elements
- Click agents to inspect
- Drag to rearrange grid layout
- Send messages to agents
- View agent conversations
- Browse filesystem

### 4.3 Mailbox System
```typescript
interface MailboxFeatures {
  inbox: Message[];
  outbox: Message[];
  compose: (to: AgentId, content: string) => void;
  broadcast: (content: string) => void;
  filters: MessageFilter[];
}
```

### 4.4 Development Tools
- Log viewer with filtering
- Performance profiler
- Agent debugger
- Network inspector
- State snapshot/restore

---

## 5. Technical Architecture

### 5.1 Component Structure
```
src/
├── components/
│   ├── three/
│   │   ├── Grid.tsx          # The Grid plane
│   │   ├── Agent.tsx         # Agent representation
│   │   ├── ThoughtBubble.tsx # Thought visualization
│   │   ├── MessageTrail.tsx  # Message animations
│   │   └── FileSystem.tsx    # Filesystem viz
│   ├── ui/
│   │   ├── ControlPanel.tsx
│   │   ├── Inspector.tsx
│   │   ├── MessageCenter.tsx
│   │   └── DevConsole.tsx
│   └── App.tsx
├── hooks/
│   ├── useWebSocket.ts
│   ├── useAgentState.ts
│   └── useThreeControls.ts
├── stores/
│   ├── agentStore.ts
│   ├── messageStore.ts
│   └── systemStore.ts
└── utils/
    ├── three-helpers.ts
    └── websocket-client.ts
```

### 5.2 WebSocket Protocol
```typescript
// Client -> Server
interface ClientMessage {
  type: 'subscribe' | 'unsubscribe' | 'command' | 'message';
  payload: any;
}

// Server -> Client
interface ServerMessage {
  type: 'agent_update' | 'message' | 'file_change' | 'system_event';
  payload: any;
  timestamp: number;
}
```

### 5.3 State Management
```typescript
interface AppState {
  agents: Map<string, Agent>;
  messages: Message[];
  filesystem: FileNode;
  camera: CameraState;
  selection: Selection | null;
}
```

---

## 6. Tron-Specific Visual Effects

### 6.1 Shaders
```glsl
// Glow effect vertex shader
varying vec3 vNormal;
void main() {
  vNormal = normalize(normalMatrix * normal);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}

// Glow effect fragment shader
uniform vec3 glowColor;
uniform float intensity;
varying vec3 vNormal;
void main() {
  float glow = pow(0.5 - dot(vNormal, vec3(0, 0, 1.0)), 2.0);
  gl_FragColor = vec4(glowColor, 1.0) * glow * intensity;
}
```

### 6.2 Post-Processing
- Bloom for glow effects
- Scan lines for retro feel
- Chromatic aberration
- Film grain
- Motion blur on camera movement

### 6.3 Audio Design
- Ambient grid hum
- Message transmission sounds
- Agent activity bleeps
- UI interaction feedback
- Alert sounds

---

## 7. Implementation Phases

### Phase 1: Core 3D Environment (Week 1-2)
- Basic Three.js setup
- Grid generation
- Camera controls
- Simple agent representation
- WebSocket connection

### Phase 2: Agent Visualization (Week 3-4)
- Agent models and animations
- Thought bubble system
- State visualization
- Basic interaction

### Phase 3: Communication System (Week 5-6)
- Message trails
- Mailbox UI
- Real-time updates
- Message history

### Phase 4: Filesystem & Developer Tools (Week 7-8)
- Filesystem visualization
- Log viewers
- Debug panels
- Performance monitoring

### Phase 5: Polish & Effects (Week 9-10)
- Tron visual effects
- Sound design
- UI animations
- Performance optimization

---

## 8. Server-Side Requirements

### 8.1 New WebSocket Endpoints
```python
# Agent state streaming
@websocket.route('/agent_states')
async def agent_states_stream():
    # Stream agent state changes
    
# Message queue access
@websocket.route('/messages')
async def message_stream():
    # Stream inter-agent messages
    
# Filesystem events
@websocket.route('/filesystem')
async def filesystem_events():
    # Stream file system changes
    
# System metrics
@websocket.route('/metrics')
async def metrics_stream():
    # Stream performance data
```

### 8.2 REST API Extensions
```python
# Get agent history
GET /api/agents/{id}/history

# Send message to agent
POST /api/agents/{id}/message

# Get filesystem snapshot
GET /api/filesystem

# System controls
POST /api/system/spawn
DELETE /api/system/agents/{id}
```

---

## 9. Performance Considerations

### 9.1 Optimization Strategies
- Level-of-detail (LOD) for distant agents
- Frustum culling
- Object pooling for particles
- Texture atlasing
- Instanced rendering for repeated elements

### 9.2 Scalability
- Support 50+ agents smoothly
- Efficient message rendering
- Progressive filesystem loading
- Pagination for logs

---

## 10. Future Enhancements

### 10.1 Advanced Visualizations
- Agent relationship graphs
- Knowledge network visualization
- Time-based playback
- Multi-dimensional data views

### 10.2 VR/AR Support
- WebXR integration
- Spatial audio
- Hand tracking controls
- Immersive navigation

### 10.3 Collaboration Features
- Multi-user sessions
- Shared annotations
- Collaborative debugging
- Team dashboards

---

## Appendix A: Quick Start for Claude Code

```bash
# Project setup
npx create-react-app mind-swarm-ui --template typescript
cd mind-swarm-ui

# Install dependencies
npm install three @react-three/fiber @react-three/drei
npm install socket.io-client zustand
npm install tailwindcss @types/three

# Generate initial structure
mkdir -p src/components/{three,ui}
mkdir -p src/{hooks,stores,utils}

# Start with basic grid component
# src/components/three/Grid.tsx
```

## Appendix B: Visual References

Key visual elements to implement:
1. **Grid**: Infinite blue grid with glow lines
2. **Agents**: Geometric shapes with particle auras
3. **Data Streams**: Flowing text and light trails
4. **UI Panels**: Semi-transparent with neon borders
5. **Transitions**: Smooth, tech-inspired animations

Remember: The goal is to create a sense of being inside a living digital organism where AI agents exist and interact in a visually stunning cyberspace.
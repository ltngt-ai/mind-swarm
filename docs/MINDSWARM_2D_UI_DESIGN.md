# Mind-Swarm 2D Monitoring Interface Design

## Overview
A 2D Tron-inspired monitoring interface for Mind-Swarm that provides real-time visualization of agent activities, leveraging existing WebSocket infrastructure.

## Technology Stack
- **Frontend**: React + TypeScript 
- **Styling**: Tailwind CSS v4 with custom Tron theme
- **State**: Zustand (lightweight and simple)
- **WebSocket**: Reuse existing patterns from mind-swarm-web-ui
- **Charts**: Recharts for performance metrics
- **Animations**: Framer Motion for smooth transitions

## Visual Design

### Color Palette
```css
:root {
  --grid-cyan: #00ffff;
  --grid-orange: #ff9f00; 
  --grid-white: #ffffff;
  --grid-blue: #0080ff;
  --grid-green: #00ff00;
  --bg-black: #000000;
  --bg-dark-blue: #001122;
  --border-glow: 0 0 10px var(--grid-cyan);
}
```

### Layout Structure
```
┌─────────────────────────────────────────────────────────────┐
│  Mind-Swarm Monitor            [Status: Connected] [Settings]│
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌────────────────────────────────┐  │
│  │ AGENTS (5 active)│  │         AGENT GRID              │  │
│  ├──────────────────┤  │  ┌────┐  ┌────┐  ┌────┐       │  │
│  │ ● Alice          │  │  │Alice│  │ Bob │  │Carol│      │  │
│  │   Thinking...    │  │  │ 🤔 │  │ 💬 │  │ 😴 │      │  │
│  │ ● Bob            │  │  └─╱──┘  └──╲─┘  └────┘       │  │
│  │   Chatting       │  │    ╱        ╲                  │  │
│  │ ○ Carol          │  │  ┌────┐  ┌────┐                │  │
│  │   Sleeping       │  │  │Dave│  │ Eve │                │  │
│  │ ● Dave           │  │  │ 📝 │  │ 🔍 │                │  │
│  │   Writing        │  │  └────┘  └────┘                │  │
│  │ ● Eve            │  │                                 │  │
│  │   Searching      │  └────────────────────────────────┘  │
│  └──────────────────┘                                       │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ ACTIVITY FEED                              [Auto-scroll]│ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ 14:32:15 ➤ Alice started thinking about "AI ethics"     │ │
│  │ 14:32:10 ➤ Bob → Carol: "Have you seen the new data?"  │ │
│  │ 14:32:05 ➤ New question in Plaza: "How to optimize..." │ │
│  │ 14:31:58 ➤ Dave created file: analysis_results.md      │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ MESSAGES (12)    │  │ FILES (48)      │  │ METRICS     │ │
│  │ ░░░░░░░░░░░░░░  │  │ ▓▓▓▓▓▓░░░░░░░░ │  │ CPU: 45%    │ │
│  │ Inbox: 8        │  │ Active: 23      │  │ MEM: 2.1GB  │ │
│  │ Sent: 4         │  │ Total: 48       │  │ Agents: 5   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Agent Grid View
- **Visual**: Agents as glowing nodes with status indicators
- **Interactions**: 
  - Click to view agent details
  - Drag to rearrange layout
  - Lines show active communications
- **States**: 
  - 🤔 Thinking (pulsing glow)
  - 💬 Communicating (message trails)
  - 😴 Sleeping (dimmed)
  - 📝 Writing (file icon)
  - 🔍 Searching (scanning animation)

### 2. Agent List Panel
- Scrollable list with status indicators
- Real-time state updates
- Quick actions (terminate, wake, message)
- Search/filter functionality

### 3. Activity Feed
- Real-time event stream
- Color-coded by event type
- Clickable items for details
- Auto-scroll with pause option

### 4. Status Cards
- Message flow metrics
- File system activity
- System resource usage
- Agent count and states

## WebSocket Integration

### Leveraging Existing Infrastructure

We'll extend the current WebSocket events:

```typescript
interface MonitoringEvents {
  // Existing events we can use
  agent_created: { name: string; use_premium: boolean; timestamp: string };
  agent_terminated: { name: string; timestamp: string };
  question_created: { question_id: string; text: string; created_by: string };
  
  // New events to add
  agent_state_changed: { name: string; old_state: string; new_state: string };
  agent_thinking: { name: string; thought: string; token_count?: number };
  message_sent: { from: string; to: string; subject: string };
  file_activity: { agent: string; action: string; path: string };
  system_metrics: { cpu: number; memory: number; agent_count: number };
}
```

### Server-Side Additions

Minimal additions to current server:

```python
# In SubspaceCoordinator or BrainHandler
async def _emit_agent_event(self, event_type: str, data: dict):
    """Emit monitoring events via websocket."""
    await self.server._broadcast_event({
        "type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat()
    })
```

## Implementation Plan

### Phase 1: Core Structure (Days 1-3)
1. Set up React + TypeScript project
2. Implement WebSocket connection using existing patterns
3. Create basic layout with Tron styling
4. Connect to existing `/ws` endpoint

### Phase 2: Agent Visualization (Days 4-6)
1. Agent Grid component with D3.js or pure SVG
2. Agent List with real-time updates
3. Status indicators and animations
4. Message trail visualization

### Phase 3: Activity & Metrics (Days 7-9)
1. Activity Feed with event filtering
2. Status cards with live metrics
3. File system activity tracker
4. Performance charts

### Phase 4: Polish & Optimization (Days 10-12)
1. Smooth animations with Framer Motion
2. Responsive design
3. Dark theme refinements
4. Performance optimization

## Key Features

### 1. Real-Time Updates
- WebSocket-driven state changes
- Smooth transitions between states
- Live activity feed
- Instant message visualization

### 2. Interactive Elements
- Click agents for detailed view
- Filter activity by type/agent
- Pause/resume activity feed
- Export activity logs

### 3. Visual Effects
- Glowing borders (CSS box-shadow)
- Pulsing animations for active agents
- Message trails as animated SVG paths
- Scanline effect overlay (optional)

## Component Structure

```
src/
├── components/
│   ├── AgentGrid/
│   │   ├── AgentGrid.tsx
│   │   ├── AgentNode.tsx
│   │   └── MessageTrail.tsx
│   ├── AgentList/
│   │   ├── AgentList.tsx
│   │   └── AgentListItem.tsx
│   ├── ActivityFeed/
│   │   ├── ActivityFeed.tsx
│   │   └── ActivityItem.tsx
│   ├── StatusCards/
│   │   ├── MessageCard.tsx
│   │   ├── FileCard.tsx
│   │   └── MetricsCard.tsx
│   └── Layout/
│       ├── Header.tsx
│       └── Container.tsx
├── hooks/
│   ├── useWebSocket.ts
│   ├── useAgentState.ts
│   └── useActivityFeed.ts
├── stores/
│   └── monitorStore.ts
├── styles/
│   └── tron-theme.css
└── App.tsx
```

## Advantages of 2D First Approach

1. **Faster Development**: 2-3 weeks vs 10+ weeks for 3D
2. **Better Performance**: Handles 50+ agents smoothly
3. **Clearer Information**: Better text readability, easier navigation
4. **Mobile Compatible**: Works on tablets and large phones
5. **Easier Maintenance**: Standard React patterns
6. **Progressive Enhancement**: Can add 3D view later as alternate mode

## Next Steps

1. Create the React project structure
2. Implement WebSocket connection
3. Build the Agent Grid component
4. Add minimal server-side event emissions
5. Style with Tron theme

The 2D approach gives us a production-ready monitoring interface quickly while maintaining the Tron aesthetic and providing all the visualization benefits.
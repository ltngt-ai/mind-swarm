**WebSocket Events**

- Envelope: `{ type: string, data: object, timestamp: string }`
- Purpose: Consistent, typed events for the 3D monitor client.

- Core Types:
  - `agent_created`: `{ name }`
  - `agent_terminated`: `{ name }`
  - `agent_state_changed`: `{ name, old_state, new_state }`
  - `agent_thinking`: `{ name, thought, token_count? }`
  - `question_created`: `{ question_id, text, created_by }`
  - `task_created`: `{ task_id, summary, created_by }`
  - `announcement_updated`: `{ title, message, priority }`
  - `announcements_cleared`: `{}`
  - `developer_registered`: `{ name, cyber_name }`
  - `token_boost_applied`: `{ cyber_id, multiplier, duration_hours }`
  - `token_boost_cleared`: `{ cyber_id }`
  - `cyber_restarted`: `{ name }`
  - `cyber_paused`: `{ name }`
  - `system_metrics`: object
  - `cycle_started`: `{ cyber, cycle_number }`
  - `cycle_completed`: `{ cyber, cycle_number, duration_ms }`
  - `stage_started`: `{ cyber, cycle_number, stage }`
  - `stage_completed`: `{ cyber, cycle_number, stage, stage_data? }`
  - `memory_changed`: `{ cyber, cycle_number, operation, memory_info }`
  - `message_sent`: `{ from, to, subject }`
  - `message_activity`: `{ from, to, from_cycle, message_type, content }`
  - `brain_thinking`: `{ cyber, cycle_number, stage, request, response? }`
  - `file_activity`: `{ cyber, action, path }`
  - `file_operation`: `{ cyber, cycle_number, operation, path, details? }`
  - `token_usage`: `{ cyber, cycle_number, stage, tokens }`
  - Heartbeat: `ping` events are periodically emitted by server; client may send `{ type: "ping" }` and receive `pong` in response.

- Source Files:
  - Server models: `src/mind_swarm/server/schemas/events.py`
  - Server emitter: `src/mind_swarm/server/monitoring_events.py`
  - Client types: `mind-swarm-3d-monitor/src/ws/events.ts`

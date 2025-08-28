**Dual‑Repo Dev (Server + Client)**

- Repos:
  - Server: this repo (FastAPI on `MIND_SWARM_PORT`, default `8888`).
  - Client: `mind-swarm-3d-monitor` (TypeScript/3D monitor UI).

- Run both locally:
  - Copy `.env.example` to `.env` and set `MIND_SWARM_PORT` if needed.
  - Start both with: `bash scripts/dev.sh`
    - Defaults assume sibling repos:
      - Server: `~/projects/mind-swarm-work`
      - Client: `~/projects/mind-swarm-3d-monitor`
    - Exports `API_BASE_URL` (configurable) to the client process.

- Overrides:
  - `CLIENT_DIR=~/projects/mind-swarm-3d-monitor` to point to your client checkout.
  - `CLIENT_CMD="npm run dev"` for your client dev command.
  - `CLIENT_API_ENV_VAR=API_BASE_URL` if the client expects a different env var name.
  - `MIND_SWARM_PORT=8888` to match the server port.

- Example:
  - `CLIENT_DIR=~/projects/mind-swarm-3d-monitor CLIENT_CMD="npm run dev" bash scripts/dev.sh`

- CORS: server allows all origins in dev (`CORSMiddleware`), so no extra setup needed.

- API Contract:
  - FastAPI exposes `/openapi.json` and interactive docs at `/docs` when the server is running.
  - Recommended: generate client types from OpenAPI in the client repo (e.g., `openapi-typescript`).
  - CI tip: add a contract check that diffs the generated types or schema to catch drift.
  - Offline schema: export with `python scripts/export_openapi.py --out docs/openapi.json` and point the client generator at that file.

- WebSocket Events:
  - The server now emits typed envelopes for WS messages under `src/mind_swarm/server/schemas/events.py`.
  - Envelope shape: `{ type: string, data: object, timestamp: string }`.
  - Existing ad-hoc events are still supported for backward compatibility, but new events follow the envelope.
  - Client suggestion: create `src/ws/events.ts` with a union of event types and optional Zod validators to validate `data` per event.
  - Migration path: prefer using `data` payloads in the client; keep a fallback for legacy top-level fields.
  - Subscriptions: client sends `{ type: "subscribe", cybers: ["*"] }` on connect by default; adjust with `WebSocketClient.subscribe(["Alice"])`.

- Notes:
  - `scripts/dev.sh` starts the server via `./run.sh server --debug --llm-debug`, waits for readiness, and then runs the client in the foreground. Exiting the client stops the server.
  - If your client requires a different env var (e.g., `VITE_API_BASE_URL`), set `CLIENT_API_ENV_VAR` accordingly.

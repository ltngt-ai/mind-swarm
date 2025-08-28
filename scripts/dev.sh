#!/usr/bin/env bash
# Orchestrate server + client (mind-swarm-3d-monitor) during development.
#
# Defaults assume sibling repos:
#   - this repo:   ~/projects/mind-swarm-work
#   - client repo: ~/projects/mind-swarm-3d-monitor
#
# Env overrides:
#   CLIENT_DIR             Path to client repo (default: ../mind-swarm-3d-monitor)
#   CLIENT_CMD             Command to start client (default: npm run dev)
#   CLIENT_API_ENV_VAR     Env var name used by client for API URL (default: API_BASE_URL)
#   MIND_SWARM_PORT        Server port (default: 8888)
#   SERVER_ARGS            Extra args for server (e.g., "--debug --llm-debug")

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"

# Config
CLIENT_DIR=${CLIENT_DIR:-"$root/../mind-swarm-3d-monitor"}
CLIENT_CMD=${CLIENT_CMD:-"npm run dev"}
CLIENT_API_ENV_VAR=${CLIENT_API_ENV_VAR:-"API_BASE_URL"}
PORT=${MIND_SWARM_PORT:-8888}
SERVER_ARGS=${SERVER_ARGS:-"--debug --llm-debug"}

log() { echo -e "\033[0;36m[dev]\033[0m $*"; }
err() { echo -e "\033[0;31m[dev]\033[0m $*" 1>&2; }

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Missing dependency: $1"
    exit 1
  fi
}

require bash
require grep

# Start server (daemonized by run.sh) and wait for readiness
start_server() {
  log "Starting server on port $PORT..."
  pushd "$root" >/dev/null
  MIND_SWARM_PORT="$PORT" ./run.sh server $SERVER_ARGS || true
  popd >/dev/null

  # Wait for /status to become available
  if command -v curl >/dev/null 2>&1; then
    log "Waiting for server readiness at http://localhost:$PORT/status ..."
    for i in {1..60}; do
      if curl -fsS "http://localhost:$PORT/status" >/dev/null 2>&1; then
        log "Server is ready."
        return 0
      fi
      sleep 0.5
    done
    err "Server did not become ready in time. Check ./run.sh logs"
  else
    log "curl not found; skipping readiness check."
  fi
}

stop_server() {
  log "Stopping server..."
  pushd "$root" >/dev/null
  ./run.sh stop || true
  popd >/dev/null
}

start_client() {
  if [ ! -d "$CLIENT_DIR" ]; then
    err "Client directory not found: $CLIENT_DIR"
    err "Set CLIENT_DIR to your client repo path."
    exit 1
  fi

  log "Starting client in $CLIENT_DIR"
  pushd "$CLIENT_DIR" >/dev/null

  # Export API base URL for the client process
  export "$CLIENT_API_ENV_VAR"="http://localhost:$PORT"
  log "Exported $CLIENT_API_ENV_VAR=$API_BASE_URL"

  # Run client in foreground so Ctrl-C stops it
  set +e
  bash -lc "$CLIENT_CMD"
  client_exit=$?
  set -e
  popd >/dev/null
  return $client_exit
}

cleanup() {
  log "Cleaning up..."
  stop_server
}

trap cleanup EXIT INT TERM

start_server
start_client

exit $?


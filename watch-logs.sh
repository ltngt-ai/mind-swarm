#!/bin/bash

# Watch Mind-Swarm logs

LOG_FILE="${1:-mind-swarm.log}"

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found: $LOG_FILE"
    echo "Make sure Mind-Swarm is running first."
    exit 1
fi

echo "Watching logs from: $LOG_FILE"
echo "Press Ctrl+C to stop"
echo ""

tail -f "$LOG_FILE"
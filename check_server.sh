#!/bin/bash
# Check if translation server is running, start if not

readonly PORT=8785
readonly PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly UV="${HOME}/.local/bin/uv"
readonly MAX_WAIT_SECONDS=120  # Increased for first-time model download (12.5GB)
readonly CHECK_INTERVAL=0.5
readonly CONNECTION_TIMEOUT=1

# Check if server is running
if ! curl -s --max-time "$CONNECTION_TIMEOUT" "http://127.0.0.1:${PORT}" > /dev/null 2>&1; then
    # Server not running, start it in background
    cd "$PROJECT_DIR" || exit 1
    nohup "$UV" run python main.py --serve > /tmp/translator-server.log 2>&1 &

    # Wait up to MAX_WAIT_SECONDS for server to start
    max_attempts=$((MAX_WAIT_SECONDS * 2))
    for ((i=1; i<=max_attempts; i++)); do
        if curl -s --max-time "$CONNECTION_TIMEOUT" "http://127.0.0.1:${PORT}" > /dev/null 2>&1; then
            exit 0
        fi
        sleep "$CHECK_INTERVAL"
    done

    # Server failed to start
    osascript -e 'display dialog "Could not start translation server. Check /tmp/translator-server.log" with title "Error" buttons {"OK"} default button "OK"'
    exit 1
fi

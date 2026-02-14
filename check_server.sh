#!/bin/bash
# Check if translation server is running, start if not

PORT=8785
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
UV="${HOME}/.local/bin/uv"

# Check if server is running
if ! curl -s --max-time 1 "http://127.0.0.1:${PORT}" > /dev/null 2>&1; then
    # Server not running, start it in background
    cd "$PROJECT_DIR"
    nohup "$UV" run python main.py --serve > /tmp/translator-server.log 2>&1 &

    # Wait up to 10 seconds for server to start
    for i in {1..20}; do
        if curl -s --max-time 1 "http://127.0.0.1:${PORT}" > /dev/null 2>&1; then
            exit 0
        fi
        sleep 0.5
    done

    # Server failed to start
    osascript -e 'display dialog "No se pudo iniciar el servidor de traducción. Revisa /tmp/translator-server.log" with title "Error" buttons {"OK"} default button "OK"'
    exit 1
fi

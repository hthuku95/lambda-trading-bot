#!/bin/bash
# Stop the trading agent daemon gracefully

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

if [ ! -f "agent_daemon.pid" ]; then
    echo "❌ Agent daemon is not running (no PID file found)"
    exit 1
fi

PID=$(cat agent_daemon.pid)

if ! ps -p $PID > /dev/null 2>&1; then
    echo "❌ Agent daemon is not running (PID $PID not found)"
    rm agent_daemon.pid
    exit 1
fi

echo "🛑 Stopping trading agent daemon (PID: $PID)..."

# Send SIGTERM for graceful shutdown
kill -TERM $PID

# Wait for graceful shutdown (max 30 seconds)
TIMEOUT=30
for i in $(seq 1 $TIMEOUT); do
    if ! ps -p $PID > /dev/null 2>&1; then
        echo "✅ Agent daemon stopped successfully"
        rm -f agent_daemon.pid
        exit 0
    fi
    sleep 1
done

# If still running, force kill
echo "⚠️ Agent daemon did not stop gracefully, forcing..."
kill -KILL $PID 2>/dev/null
rm -f agent_daemon.pid
echo "✅ Agent daemon forcefully stopped"
exit 0

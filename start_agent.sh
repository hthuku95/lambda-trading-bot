#!/bin/bash
# Start the trading agent daemon

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if already running
if [ -f "agent_daemon.pid" ]; then
    PID=$(cat agent_daemon.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "❌ Agent daemon is already running (PID: $PID)"
        exit 1
    else
        echo "⚠️ Stale PID file found, removing..."
        rm agent_daemon.pid
    fi
fi

echo "🚀 Starting trading agent daemon..."

# Activate virtual environment and start daemon
source env/bin/activate
nohup python agent_daemon.py > agent_daemon_console.log 2>&1 &

# Wait a moment for startup
sleep 5

# Check if started successfully
if [ -f "agent_daemon.pid" ]; then
    PID=$(cat agent_daemon.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Agent daemon started successfully (PID: $PID)"
        echo "📝 Logs: agent_daemon.log"
        echo "📊 Status: agent_daemon_status.json"
        exit 0
    else
        echo "❌ Agent daemon failed to start"
        exit 1
    fi
else
    echo "❌ Agent daemon failed to start (no PID file created)"
    exit 1
fi

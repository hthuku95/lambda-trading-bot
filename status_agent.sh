#!/bin/bash
# Check the status of the trading agent daemon

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=" $(printf '=%.0s' {1..70})
echo "📊 TRADING AGENT DAEMON STATUS"
echo "=" $(printf '=%.0s' {1..70})

# Check PID file
if [ -f "agent_daemon.pid" ]; then
    PID=$(cat agent_daemon.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Status: RUNNING"
        echo "🆔 PID: $PID"

        # Get process info
        echo "⏰ Uptime: $(ps -p $PID -o etime= | tr -d ' ')"
        echo "💾 Memory: $(ps -p $PID -o rss= | awk '{printf "%.2f MB", $1/1024}')"
        echo "🔥 CPU: $(ps -p $PID -o %cpu=)%"

        # Check status file
        if [ -f "agent_daemon_status.json" ]; then
            echo ""
            echo "📄 Latest Status:"
            cat agent_daemon_status.json | python3 -m json.tool 2>/dev/null || cat agent_daemon_status.json
        fi

        # Check agent state
        if [ -f "agent_state.json" ]; then
            echo ""
            echo "💰 Agent State:"
            echo "   Balance: $(cat agent_state.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"{data.get('wallet_balance_sol', 0):.6f} SOL\")" 2>/dev/null)"
            echo "   Cycles: $(cat agent_state.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('cycles_completed', 0))" 2>/dev/null)"
            echo "   Positions: $(cat agent_state.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('active_positions', [])))" 2>/dev/null)"
        fi

        echo ""
        echo "📝 Log files:"
        echo "   - agent_daemon.log (daemon logs)"
        echo "   - agent_daemon_console.log (console output)"

    else
        echo "❌ Status: NOT RUNNING (stale PID file)"
        echo "⚠️ PID file exists but process $PID not found"
    fi
else
    echo "❌ Status: NOT RUNNING"
    echo "💡 Start with: ./start_agent.sh"
fi

echo "=" $(printf '=%.0s' {1..70})

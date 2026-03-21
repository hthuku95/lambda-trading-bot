"""
Client for interacting with the standalone agent daemon
Allows UI to monitor and control the daemon process
"""
import os
import json
import signal
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger("daemon_client")

class AgentDaemonClient:
    """Client for managing the standalone agent daemon"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent
        self.pid_file = self.project_root / "agent_daemon.pid"
        self.status_file = self.project_root / "agent_daemon_status.json"
        self.state_file = self.project_root / "agent_state.json"

    def is_running(self) -> bool:
        """Check if daemon is running"""
        if not self.pid_file.exists():
            return False

        try:
            pid = int(self.pid_file.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            return True
        except (OSError, ValueError, ProcessLookupError):
            # PID file exists but process doesn't - clean up
            if self.pid_file.exists():
                self.pid_file.unlink()
            return False

    def get_pid(self) -> Optional[int]:
        """Get daemon PID"""
        if not self.pid_file.exists():
            return None

        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, IOError):
            return None

    def start(self) -> Dict[str, Any]:
        """Start the daemon"""
        if self.is_running():
            return {
                "success": False,
                "error": "Daemon is already running",
                "pid": self.get_pid()
            }

        try:
            # Use the start script
            start_script = self.project_root / "start_agent.sh"
            result = subprocess.run(
                [str(start_script)],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "Daemon started successfully",
                    "pid": self.get_pid()
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr or result.stdout
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout starting daemon"
            }
        except Exception as e:
            logger.error(f"Error starting daemon: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def stop(self) -> Dict[str, Any]:
        """Stop the daemon gracefully"""
        if not self.is_running():
            return {
                "success": False,
                "error": "Daemon is not running"
            }

        try:
            # Use the stop script
            stop_script = self.project_root / "stop_agent.sh"
            result = subprocess.run(
                [str(stop_script)],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=35
            )

            return {
                "success": result.returncode == 0,
                "message": "Daemon stopped successfully" if result.returncode == 0 else result.stderr
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout stopping daemon"
            }
        except Exception as e:
            logger.error(f"Error stopping daemon: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_status(self) -> Dict[str, Any]:
        """Get daemon status"""
        running = self.is_running()
        pid = self.get_pid() if running else None

        status = {
            "running": running,
            "pid": pid,
            "timestamp": datetime.now().isoformat()
        }

        # Read status file if available
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r') as f:
                    daemon_status = json.load(f)
                    status.update(daemon_status)
            except Exception as e:
                logger.error(f"Error reading status file: {e}")

        # Read agent state if available
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    agent_state = json.load(f)
                    status["agent_state"] = {
                        "balance_sol": agent_state.get("wallet_balance_sol", 0),
                        "cycles_completed": agent_state.get("cycles_completed", 0),
                        "active_positions": len(agent_state.get("active_positions", [])),
                        "win_rate": agent_state.get("portfolio_metrics", {}).get("win_rate", 0),
                        "last_updated": agent_state.get("last_update_timestamp"),
                        "model_provider": agent_state.get("agent_parameters", {}).get("model_provider", "unknown")
                    }
            except Exception as e:
                logger.error(f"Error reading agent state: {e}")

        return status

    def get_logs(self, lines: int = 50) -> str:
        """Get recent daemon log lines"""
        log_file = self.project_root / "agent_daemon.log"
        if not log_file.exists():
            return "No log file found"

        try:
            result = subprocess.run(
                ["tail", "-n", str(lines), str(log_file)],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout if result.returncode == 0 else "Error reading logs"
        except Exception as e:
            return f"Error: {e}"

    def restart(self) -> Dict[str, Any]:
        """Restart the daemon"""
        if self.is_running():
            stop_result = self.stop()
            if not stop_result.get("success"):
                return stop_result

        # Wait a moment
        import time
        time.sleep(2)

        return self.start()


# Singleton instance
_daemon_client = None

def get_daemon_client() -> AgentDaemonClient:
    """Get singleton daemon client instance"""
    global _daemon_client
    if _daemon_client is None:
        _daemon_client = AgentDaemonClient()
    return _daemon_client

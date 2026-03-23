#!/usr/bin/env python3
"""
Standalone Trading Agent Daemon
Runs independently of the Streamlit UI
Survives browser logouts and restarts
"""
import os
import sys
import time
import signal
import logging
import json
import queue
import threading
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agent.langgraph_trading_agent import CompleteLangGraphTradingAgent
from src.agent.state import load_agent_state, save_agent_state, create_initial_state, update_portfolio_metrics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("agent_daemon")

# Initialise PostgreSQL (non-fatal if DB unavailable)
try:
    from src.db import init_db
    from src.db.log_handler import attach_to_root_logger
    _db_ready = init_db()
    if _db_ready:
        attach_to_root_logger(level=logging.INFO)
        logger.info("PostgreSQL logging handler attached")
except Exception as _db_err:
    logger.warning(f"PostgreSQL init skipped: {_db_err}")

# Global flag for graceful shutdown
running = True
reload_config = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global running
    logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
    running = False

def sighup_handler(signum, frame):
    """Handle SIGHUP — reload config without restarting"""
    global reload_config
    logger.info("🔄 SIGHUP received — will reload config after current cycle")
    reload_config = True


# ─────────────────────────────────────────────────────────────────────────────
# Pair monitor + backtest worker threads
# ─────────────────────────────────────────────────────────────────────────────

_pair_queue: queue.Queue = queue.Queue(maxsize=500)
_pair_monitor_stop: threading.Event = threading.Event()


def _pair_monitor_loop() -> None:
    """
    Background daemon: poll DexScreener every 60s for boosted/new tokens
    and push their addresses into _pair_queue for the backtest worker.
    """
    logger.info("🔭 Pair monitor thread started")
    while not _pair_monitor_stop.wait(timeout=60):
        try:
            from src.data.dexscreener import get_boosted_tokens_latest
            pairs = get_boosted_tokens_latest(limit=50) or []
            added = 0
            for pair in pairs:
                addr = pair.get("baseToken", {}).get("address") or pair.get("address")
                if addr and not _pair_queue.full():
                    try:
                        _pair_queue.put_nowait(addr)
                        added += 1
                    except queue.Full:
                        break
            if added:
                logger.debug(f"Pair monitor: queued {added} token addresses for backtesting")
        except Exception as e:
            logger.warning(f"Pair monitor error: {e}")
    logger.info("🔭 Pair monitor thread stopped")


def _backtest_worker_loop() -> None:
    """
    Background daemon: consume token addresses from _pair_queue and run
    parallel strategy backtests. Results persist to PostgreSQL and AstraDB.
    """
    logger.info("⚙️ Backtest worker thread started")
    while not _pair_monitor_stop.is_set():
        try:
            token_address = _pair_queue.get(timeout=5)
        except queue.Empty:
            continue
        try:
            from src.backtesting.engine import run_parallel_backtests
            from src.backtesting.strategies import list_strategies
            from src.db.backtest_store import save_backtest_result
            import uuid as _uuid

            strategies = list_strategies()
            results = run_parallel_backtests(
                [token_address], strategies, days_back=7, max_workers=4
            )
            run_id = str(_uuid.uuid4())[:12]
            saved = 0
            for r in results:
                if r.num_trades > 0:
                    save_backtest_result(r, run_id=run_id, model_provider="daemon")
                    saved += 1
            if saved:
                logger.info(
                    f"Backtest worker: saved {saved} results for {token_address[:8]}... (run {run_id})"
                )
        except Exception as e:
            logger.error(f"Backtest worker error for {token_address}: {e}")
        finally:
            _pair_queue.task_done()
    logger.info("⚙️ Backtest worker thread stopped")

def create_pid_file():
    """Create PID file to track daemon process"""
    pid_file = Path("agent_daemon.pid")
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    logger.info(f"📝 PID file created: {pid_file} (PID: {os.getpid()})")
    return pid_file

def remove_pid_file(pid_file):
    """Remove PID file on shutdown"""
    try:
        if pid_file.exists():
            pid_file.unlink()
            logger.info("🗑️ PID file removed")
    except Exception as e:
        logger.error(f"Error removing PID file: {e}")

def create_status_file(status: str, message: str = ""):
    """Create status file for UI to read"""
    status_file = Path("agent_daemon_status.json")
    status_data = {
        "status": status,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "pid": os.getpid()
    }
    with open(status_file, 'w') as f:
        json.dump(status_data, f, indent=2)

def run_agent_daemon():
    """Main daemon loop - runs agent continuously"""
    global running

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGHUP, sighup_handler)

    # Create PID file
    pid_file = create_pid_file()

    try:
        logger.info("=" * 80)
        logger.info("🚀 TRADING AGENT DAEMON STARTING")
        logger.info("=" * 80)

        # Start background pair monitor + backtest worker threads
        _pair_monitor_stop.clear()
        _monitor_thread = threading.Thread(
            target=_pair_monitor_loop, name="pair-monitor", daemon=True
        )
        _worker_thread = threading.Thread(
            target=_backtest_worker_loop, name="backtest-worker", daemon=True
        )
        _monitor_thread.start()
        _worker_thread.start()
        logger.info("🔭 Background backtest threads started (pair monitor + worker)")

        # Load initial state
        state = load_agent_state() or create_initial_state()
        logger.info(f"💾 Loaded agent state - Cycles: {state.get('cycles_completed', 0)}")

        # Get agent parameters
        parameters = state.get("agent_parameters", {})
        model_provider = parameters.get("model_provider", "anthropic")
        cycle_time = parameters.get("cycle_time_seconds", 180)

        logger.info(f"🤖 Model: {model_provider.upper()}")
        logger.info(f"⏱️ Cycle time: {cycle_time}s")
        logger.info(f"💰 Trading mode: {parameters.get('trading_mode', 'dry_run')}")

        # Initialize agent
        logger.info(f"🔧 Initializing {model_provider.upper()} agent...")
        agent = CompleteLangGraphTradingAgent(model_provider=model_provider)

        # Create a DB session for this daemon run
        _session_id = None
        try:
            from src.db.trade_store import create_session, end_session, mark_session_error
            _session_id = create_session(
                model_provider=model_provider,
                trading_mode=parameters.get("trading_mode", "dry_run"),
                parameters=parameters,
                initial_balance_sol=state.get("wallet_balance_sol") or state.get("simulated_balance_sol"),
            )
            if _session_id:
                logger.info(f"DB session created: {_session_id[:8]}...")
        except Exception as _se:
            logger.warning(f"DB session creation skipped: {_se}")

        create_status_file("running", f"Agent daemon started with {model_provider}")
        logger.info("✅ Agent daemon initialized successfully")
        logger.info("=" * 80)

        cycle_count = state.get("cycles_completed", 0)

        # Main trading loop
        while running:
            # Handle SIGHUP config reload
            if reload_config:
                reload_config = False
                load_dotenv(override=True)
                state = load_agent_state() or state
                parameters = state.get("agent_parameters", {})
                new_cycle_time = parameters.get("cycle_time_seconds", 180)
                if new_cycle_time != cycle_time:
                    cycle_time = new_cycle_time
                    logger.info(f"🔄 Config reloaded — new cycle time: {cycle_time}s")
                else:
                    logger.info("🔄 Config reloaded — no changes detected")

            try:
                cycle_count += 1
                logger.info(f"\n{'=' * 80}")
                logger.info(f"🔄 CYCLE {cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'=' * 80}")

                # Run trading cycle
                state = agent.run_trading_cycle(
                    initial_state=state
                )

                # Update cycle count
                state["cycles_completed"] = cycle_count
                state = update_portfolio_metrics(state)

                # Record cycle to DB
                if _session_id:
                    try:
                        from src.db.trade_store import record_cycle as _record_cycle
                        _record_cycle(_session_id, cycle_count, state)
                    except Exception as _ce:
                        logger.debug(f"record_cycle skipped: {_ce}")

                # Save state
                save_agent_state(state)

                # Log cycle summary
                balance = state.get("wallet_balance_sol", 0)
                positions = len(state.get("active_positions", []))
                logger.info(f"✅ Cycle {cycle_count} completed")
                logger.info(f"💰 Balance: {balance:.6f} SOL | Positions: {positions}")

                create_status_file(
                    "running",
                    f"Cycle {cycle_count} completed - {balance:.6f} SOL"
                )

                # Sleep until next cycle (with interrupt check every second)
                logger.info(f"💤 Sleeping for {cycle_time}s until next cycle...")
                for i in range(cycle_time):
                    if not running:
                        logger.info("🛑 Stop requested during sleep, breaking...")
                        break
                    time.sleep(1)

            except Exception as e:
                logger.error(f"❌ Error in trading cycle {cycle_count}: {e}", exc_info=True)
                create_status_file("error", f"Cycle error: {str(e)}")

                # Wait before retry (with interrupt check)
                logger.info("⏳ Waiting 60s before retry...")
                for i in range(60):
                    if not running:
                        break
                    time.sleep(1)

        logger.info("\n" + "=" * 80)
        logger.info("🏁 Agent daemon shutting down gracefully...")
        logger.info("=" * 80)

        # Save final state
        if state:
            state["session_active"] = False
            state["session_end_timestamp"] = datetime.now().isoformat()
            save_agent_state(state)
            logger.info("💾 Final state saved")

        # Close DB session
        if _session_id:
            try:
                from src.db.trade_store import end_session as _end_session
                _end_session(_session_id, {
                    "cycles_completed": cycle_count,
                    "total_profit_sol": state.get("total_profit_sol", 0) if state else 0,
                    "wallet_balance_sol": (state.get("wallet_balance_sol") or state.get("simulated_balance_sol", 0)) if state else 0,
                })
            except Exception as _ee:
                logger.debug(f"end_session skipped: {_ee}")

        create_status_file("stopped", "Agent daemon stopped gracefully")

    except Exception as e:
        logger.error(f"💥 Fatal error in agent daemon: {e}", exc_info=True)
        create_status_file("error", f"Fatal error: {str(e)}")
        raise

    finally:
        # Stop background backtest threads
        _pair_monitor_stop.set()
        remove_pid_file(pid_file)
        logger.info("👋 Agent daemon terminated")

if __name__ == "__main__":
    try:
        run_agent_daemon()
    except KeyboardInterrupt:
        logger.info("⌨️ Keyboard interrupt received")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Unhandled exception: {e}", exc_info=True)
        sys.exit(1)

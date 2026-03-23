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
#
# Queue items are tuples: (token_address: str, days_back: int, timeframes: list[int])
#   - Discovery monitors push fresh tokens: (addr, 7,  [5])          single TF, 7d
#   - Nansen monitor pushes confirmed tokens: (addr, 7,  [5, 15])    2 TFs, 7d
#   - Universe sweep pushes established tokens: (addr, 30, [5,15,60]) all TFs, 30d
# ─────────────────────────────────────────────────────────────────────────────

_pair_queue: queue.Queue = queue.Queue(maxsize=1000)
_pair_monitor_stop: threading.Event = threading.Event()

# ── Timeframe presets ────────────────────────────────────────────────────────
_TF_FRESH = [5]            # new / unverified tokens: 5-min only
_TF_STANDARD = [5, 15]     # smart-money confirmed: 5m + 15m
_TF_DEEP = [5, 15, 60]     # universe sweep: all three timeframes


def _enqueue(addr: str, days_back: int, timeframes: list[int]) -> bool:
    """Put a (addr, days_back, timeframes) job into the queue. Returns True if added."""
    if not addr or _pair_queue.full():
        return False
    try:
        _pair_queue.put_nowait((addr, days_back, timeframes))
        return True
    except queue.Full:
        return False


def _pair_monitor_loop() -> None:
    """
    Background daemon: poll DexScreener every 60s for boosted/new tokens.
    Fresh tokens get 7-day single-timeframe jobs (minimal history available).
    """
    logger.info("🔭 Pair monitor thread started")
    while not _pair_monitor_stop.wait(timeout=60):
        try:
            from src.data.dexscreener import get_boosted_tokens_latest
            pairs = get_boosted_tokens_latest(limit=50) or []
            added = 0
            for pair in pairs:
                addr = pair.get("baseToken", {}).get("address") or pair.get("address")
                if _enqueue(addr, 7, _TF_FRESH):
                    added += 1
            if added:
                logger.debug(f"Pair monitor: queued {added} tokens (7d/5m)")
        except Exception as e:
            logger.warning(f"Pair monitor error: {e}")
    logger.info("🔭 Pair monitor thread stopped")


def _nansen_monitor_loop() -> None:
    """
    Background daemon: poll Nansen token screener every 5 minutes.
    Smart-money confirmed tokens get dual-timeframe (5m + 15m) jobs.
    """
    logger.info("💡 Nansen monitor thread started (smart money screener, 5min interval)")
    while not _pair_monitor_stop.wait(timeout=300):
        try:
            from src.data.nansen_client import screen_smart_money_tokens, _is_available
            if not _is_available():
                logger.debug("Nansen monitor: NANSEN_API_KEY not set — skipping")
                continue
            tokens = screen_smart_money_tokens(timeframe="1h", per_page=50)
            added = 0
            for token in tokens:
                addr = token.get("token_address")
                if _enqueue(addr, 7, _TF_STANDARD):
                    added += 1
            if added:
                logger.info(f"Nansen monitor: queued {added} smart money tokens (7d/5m+15m)")
        except Exception as e:
            logger.warning(f"Nansen monitor error: {e}")
    logger.info("💡 Nansen monitor thread stopped")


def _new_token_monitor_loop() -> None:
    """
    Background daemon: poll RugCheck /stats/new_tokens every 15s.
    Very fresh tokens: 7-day 5-min jobs only.
    """
    logger.info("🆕 New token monitor thread started (RugCheck, 15s interval)")
    while not _pair_monitor_stop.wait(timeout=15):
        try:
            from src.data.rugcheck_client import RugCheckClient
            client = RugCheckClient()
            result = client.get_recent_tokens()
            tokens = result.get("tokens", []) if isinstance(result, dict) else []
            added = 0
            for token in tokens[:30]:
                addr = token.get("mint") or token.get("address") or token.get("token")
                if _enqueue(addr, 7, _TF_FRESH):
                    added += 1
            if added:
                logger.debug(f"New token monitor: queued {added} fresh tokens (7d/5m)")
        except Exception as e:
            logger.warning(f"New token monitor error: {e}")
    logger.info("🆕 New token monitor thread stopped")


def _universe_sweep_loop() -> None:
    """
    Background sweep: every hour, fetch the top 200 Solana tokens by volume/boost
    from DexScreener and queue them for deep multi-timeframe backtesting.

    These are established tokens with enough history for 30-day backtests across
    5m, 15m, and 60m timeframes — generating ~72× more compressed context per token
    than a single-strategy 7-day run.  The sweep rotates continuously, so the agent's
    AstraDB memory converges on the full Solana memecoin universe over time.
    """
    logger.info("🌐 Universe sweep thread started (top-200 tokens, 30d / 5m+15m+60m, 1hr cycle)")
    while not _pair_monitor_stop.wait(timeout=3600):
        try:
            from src.data.dexscreener import get_boosted_tokens_top, get_latest_token_profiles
            universe: set[str] = set()

            # Top boosted tokens (highest promotion = most active)
            try:
                boosted = get_boosted_tokens_top(limit=100) or []
                for p in boosted:
                    addr = p.get("baseToken", {}).get("address") or p.get("address")
                    if addr:
                        universe.add(addr)
            except Exception as e:
                logger.debug(f"Universe sweep: boosted fetch error: {e}")

            # Latest token profiles (recent listings with established pools)
            try:
                profiles = get_latest_token_profiles() or []
                for p in profiles[:100]:
                    addr = p.get("address")
                    if addr:
                        universe.add(addr)
            except Exception as e:
                logger.debug(f"Universe sweep: profiles fetch error: {e}")

            added = 0
            for addr in universe:
                if _enqueue(addr, 30, _TF_DEEP):
                    added += 1

            logger.info(
                f"🌐 Universe sweep: queued {added}/{len(universe)} tokens "
                f"for deep backtest (30d × 5m/15m/60m × 24 strategies)"
            )
        except Exception as e:
            logger.warning(f"Universe sweep error: {e}")
    logger.info("🌐 Universe sweep thread stopped")


def _backtest_worker_loop() -> None:
    """
    Background daemon: consume (token_address, days_back, timeframes) jobs from
    _pair_queue and run multi-timeframe parallel strategy backtests.

    Results persist to PostgreSQL (with market_regime + interval_minutes metadata)
    and AstraDB (with regime-tagged experience documents for retrieval).

    Throughput: 24 strategies × up to 3 timeframes per token = 72 backtests/token.
    """
    logger.info("⚙️ Backtest worker thread started (24 strategies, multi-timeframe)")
    while not _pair_monitor_stop.is_set():
        try:
            item = _pair_queue.get(timeout=5)
        except queue.Empty:
            continue

        # Unpack queue item — support both old str format and new tuple format
        if isinstance(item, tuple):
            token_address, days_back, timeframes = item
        else:
            token_address, days_back, timeframes = item, 7, _TF_FRESH

        try:
            from src.backtesting.engine import run_multi_timeframe_backtests, run_parallel_backtests
            from src.backtesting.strategies import list_strategies
            from src.db.backtest_store import save_backtest_result
            import uuid as _uuid

            strategies = list_strategies()  # all 24 strategies
            run_id = str(_uuid.uuid4())[:12]

            # Use multi-timeframe runner when multiple TFs requested
            if len(timeframes) > 1:
                results = run_multi_timeframe_backtests(
                    [token_address], strategies, timeframes, days_back=days_back, max_workers=4
                )
            else:
                results = run_parallel_backtests(
                    [token_address], strategies, days_back=days_back,
                    max_workers=4, interval_minutes=timeframes[0]
                )

            saved = 0
            vectorized = 0
            for r in results:
                if r.num_trades == 0:
                    continue
                save_backtest_result(r, run_id=run_id, model_provider="daemon")
                saved += 1

                # Vectorize into AstraDB — include market_regime for context-aware retrieval
                try:
                    from src.memory.astra_vector_store import add_trading_experience
                    experience = {
                        "model_provider": "daemon",
                        "trade_type": "backtest",
                        "strategy_name": r.strategy_name,
                        "token_symbol": r.token_symbol,
                        "total_return_pct": r.total_return_pct,
                        "win_rate": r.win_rate,
                        "num_trades": r.num_trades,
                        "sharpe_ratio": r.sharpe_ratio,
                        "max_drawdown_pct": r.max_drawdown_pct,
                        "avg_hold_minutes": r.avg_hold_minutes,
                        "best_trade_pct": r.best_trade_pct,
                        "worst_trade_pct": r.worst_trade_pct,
                        "market_regime": r.market_regime,
                        "interval_minutes": r.interval_minutes,
                        "days_back": days_back,
                        "run_id": run_id,
                        "ai_reasoning": (
                            f"Daemon backtest {r.strategy_name} on {r.token_symbol} "
                            f"[{r.market_regime} regime, {r.interval_minutes}m candles]: "
                            f"{r.total_return_pct:.1f}% return, "
                            f"{r.win_rate:.0%} win rate, "
                            f"{r.num_trades} trades over {days_back}d"
                        ),
                        "timestamp": datetime.now().isoformat(),
                    }
                    add_trading_experience(token_address, experience)
                    vectorized += 1
                except Exception as vec_err:
                    logger.debug(f"AstraDB vectorize skipped for {token_address[:8]}...: {vec_err}")

            if saved:
                tfs_str = "+".join(f"{tf}m" for tf in timeframes)
                logger.info(
                    f"Backtest worker: {saved} results for {token_address[:8]}... "
                    f"[{tfs_str}, {days_back}d, run {run_id}, {vectorized} → AstraDB]"
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
        _new_token_thread = threading.Thread(
            target=_new_token_monitor_loop, name="new-token-monitor", daemon=True
        )
        _nansen_thread = threading.Thread(
            target=_nansen_monitor_loop, name="nansen-monitor", daemon=True
        )
        _universe_thread = threading.Thread(
            target=_universe_sweep_loop, name="universe-sweep", daemon=True
        )
        _worker_thread = threading.Thread(
            target=_backtest_worker_loop, name="backtest-worker", daemon=True
        )
        _monitor_thread.start()
        _new_token_thread.start()
        _nansen_thread.start()
        _universe_thread.start()
        _worker_thread.start()
        logger.info(
            "🔭 Background threads started: "
            "DexScreener boosted (60s) | RugCheck new tokens (15s) | "
            "Nansen smart money (5min) | Universe sweep (1hr, 30d/3TFs) | "
            "Backtest worker (24 strategies × multi-timeframe)"
        )

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
                initial_balance_sol=state.get("wallet_balance_sol"),
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

                # Record cycle to DB first so we have a cycle_id for trade records
                _cycle_id = None
                if _session_id:
                    try:
                        from src.db.trade_store import record_cycle as _record_cycle
                        _cycle_id = _record_cycle(_session_id, cycle_count, state)
                    except Exception as _ce:
                        logger.debug(f"record_cycle (pre-run) skipped: {_ce}")

                # Run trading cycle — passes session_id + cycle_id so trades are
                # automatically persisted to PostgreSQL and vectorized into AstraDB
                state = agent.run_trading_cycle(
                    initial_state=state,
                    session_id=_session_id,
                    cycle_id=_cycle_id,
                )

                # Update cycle count
                state["cycles_completed"] = cycle_count
                state = update_portfolio_metrics(state)

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
                    "wallet_balance_sol": state.get("wallet_balance_sol", 0) if state else 0,
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

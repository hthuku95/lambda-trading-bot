# src/db/trade_store.py
"""
Write-side DB operations for sessions, cycles, trades, positions, snapshots, and token discovery.
All functions are standalone, thread-safe, and silently no-op when the DB is unavailable.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.db.connection import get_conn, is_available

logger = logging.getLogger("trading_agent.db.trade_store")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────
# Sessions
# ─────────────────────────────────────────────────────────────

def create_session(
    model_provider: str,
    trading_mode: str,
    parameters: Dict[str, Any],
    initial_balance_sol: float = None,
) -> Optional[str]:
    """Create a new trading session. Returns the session UUID or None if DB unavailable."""
    if not is_available():
        return None
    session_id = str(uuid.uuid4())
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trading_sessions
                        (id, model_provider, trading_mode, status, initial_balance_sol, parameters)
                    VALUES (%s, %s, %s, 'running', %s, %s)
                    """,
                    (
                        session_id,
                        model_provider,
                        trading_mode,
                        initial_balance_sol,
                        json.dumps(parameters),
                    ),
                )
        logger.info(f"Session created: {session_id[:8]}... ({model_provider}/{trading_mode})")
        return session_id
    except Exception as e:
        logger.error(f"create_session error: {e}")
        return None


def end_session(session_id: str, final_state: Dict[str, Any]) -> None:
    if not is_available() or not session_id:
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE trading_sessions SET
                        status = 'completed',
                        ended_at = NOW(),
                        cycles_completed = %s,
                        total_profit_sol = %s,
                        final_balance_sol = %s
                    WHERE id = %s
                    """,
                    (
                        final_state.get("cycles_completed", 0),
                        final_state.get("total_profit_sol", 0),
                        final_state.get("wallet_balance_sol", 0),
                        session_id,
                    ),
                )
    except Exception as e:
        logger.error(f"end_session error: {e}")


def mark_session_error(session_id: str) -> None:
    if not is_available() or not session_id:
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE trading_sessions SET status = 'error', ended_at = NOW() WHERE id = %s",
                    (session_id,),
                )
    except Exception as e:
        logger.error(f"mark_session_error: {e}")


# ─────────────────────────────────────────────────────────────
# Cycles
# ─────────────────────────────────────────────────────────────

def record_cycle(
    session_id: str,
    cycle_number: int,
    state: Dict[str, Any],
    duration_seconds: float = None,
) -> Optional[int]:
    """Insert a trading cycle record. Returns the new cycle_id or None."""
    if not is_available() or not session_id:
        return None
    try:
        tools_used = state.get("tools_used_this_cycle", [])
        active_positions = state.get("active_positions", [])
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trading_cycles (
                        session_id, cycle_number, model_provider, trading_mode,
                        duration_seconds, wallet_balance_sol, simulated_balance_sol,
                        active_positions_count, market_sentiment, ai_strategy,
                        agent_reasoning, tools_used, state_snapshot
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (
                        session_id,
                        cycle_number,
                        state.get("model_provider", "unknown"),
                        state.get("trading_mode", "dry_run"),
                        duration_seconds,
                        state.get("wallet_balance_sol"),
                        state.get("simulated_balance_sol"),
                        len(active_positions),
                        state.get("market_sentiment"),
                        state.get("ai_strategy"),
                        state.get("agent_reasoning", "")[:2000],  # truncate for DB
                        tools_used if tools_used else None,
                        json.dumps({
                            "cycles_completed": state.get("cycles_completed"),
                            "win_rate": state.get("win_rate"),
                            "total_profit_sol": state.get("total_profit_sol"),
                            "sharpe_ratio": state.get("sharpe_ratio"),
                        }),
                    ),
                )
                cycle_id = cur.fetchone()[0]
        return cycle_id
    except Exception as e:
        logger.error(f"record_cycle error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Trades
# ─────────────────────────────────────────────────────────────

def record_trade(
    session_id: str,
    cycle_id: Optional[int],
    trade_data: Dict[str, Any],
) -> Optional[int]:
    """
    Insert a trade record. trade_data is the dict returned by execute_trade_tool().
    Returns the new trade_id or None.
    """
    if not is_available():
        return None
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trades (
                        session_id, cycle_id, model_provider, trading_mode,
                        trade_type, token_address, token_symbol,
                        amount_sol, dry_run, reasoning,
                        simulated_balance_after, transaction_id,
                        success, error_message, raw_data
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (
                        session_id,
                        cycle_id,
                        trade_data.get("model_provider", "unknown"),
                        trade_data.get("trading_mode", "dry_run"),
                        trade_data.get("trade_type"),
                        trade_data.get("token_address"),
                        trade_data.get("token_symbol"),
                        trade_data.get("amount_sol"),
                        trade_data.get("dry_run", True),
                        trade_data.get("reasoning", ""),
                        trade_data.get("simulated_balance_after"),
                        trade_data.get("simulated_result", {}).get("transaction_id")
                            or trade_data.get("transaction_result", {}).get("transaction_id"),
                        trade_data.get("success", True),
                        trade_data.get("error"),
                        json.dumps(trade_data),
                    ),
                )
                return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"record_trade error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Positions
# ─────────────────────────────────────────────────────────────

def open_position(trade_id: int, position_data: Dict[str, Any]) -> Optional[int]:
    """Record a new open position linked to an entry trade."""
    if not is_available():
        return None
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO positions (
                        position_id, session_id, entry_trade_id, model_provider,
                        token_address, token_symbol, status,
                        entry_time, amount, position_size_sol, entry_price_usd,
                        entry_ai_score, entry_safety_score, entry_reasoning, strategy, risk_level
                    ) VALUES (%s,%s,%s,%s,%s,%s,'open',%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (
                        position_data.get("position_id"),
                        position_data.get("session_id"),
                        trade_id,
                        position_data.get("model_provider", "unknown"),
                        position_data.get("token_address"),
                        position_data.get("token_symbol"),
                        position_data.get("entry_time"),
                        position_data.get("amount"),
                        position_data.get("position_size_sol"),
                        position_data.get("entry_price_usd"),
                        position_data.get("entry_ai_score"),
                        position_data.get("entry_safety_score"),
                        position_data.get("entry_ai_reasoning"),
                        position_data.get("strategy"),
                        position_data.get("risk_level"),
                    ),
                )
                return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"open_position error: {e}")
        return None


def close_position(position_id_str: str, exit_trade_id: int, exit_data: Dict[str, Any]) -> None:
    """Mark a position as closed with exit data."""
    if not is_available():
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE positions SET
                        status = 'closed',
                        exit_trade_id = %s,
                        exit_time = NOW(),
                        hold_time_hours = %s,
                        exit_price_usd = %s,
                        realized_pnl_sol = %s,
                        realized_pnl_usd = %s,
                        profit_percentage = %s,
                        peak_profit_pct = %s,
                        stop_loss_triggered = %s,
                        profit_target_hit = %s,
                        exit_reasoning = %s
                    WHERE position_id = %s
                    """,
                    (
                        exit_trade_id,
                        exit_data.get("hold_time_hours"),
                        exit_data.get("exit_price_usd"),
                        exit_data.get("realized_pnl_sol"),
                        exit_data.get("realized_pnl_usd"),
                        exit_data.get("profit_percentage"),
                        exit_data.get("peak_profit_percentage"),
                        exit_data.get("stop_loss_triggered", False),
                        exit_data.get("profit_target_hit", False),
                        exit_data.get("exit_reasoning"),
                        position_id_str,
                    ),
                )
    except Exception as e:
        logger.error(f"close_position error: {e}")


# ─────────────────────────────────────────────────────────────
# State snapshots
# ─────────────────────────────────────────────────────────────

def save_state_snapshot(model_provider: str, state: Dict[str, Any]) -> None:
    """Persist a lightweight state snapshot to PostgreSQL alongside the JSON file."""
    if not is_available():
        return
    try:
        metrics = state.get("portfolio_metrics", {})
        active_positions = state.get("active_positions", [])
        # Build a lean state_json (exclude large lists to keep row size reasonable)
        lean_state = {k: v for k, v in state.items()
                      if k not in ("discovered_tokens", "analyzed_tokens", "validated_tokens",
                                   "watchlist_tokens", "performance_log", "error_log")}
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_state_snapshots (
                        model_provider, trading_mode, cycles_completed,
                        wallet_balance_sol, simulated_balance_sol,
                        total_profit_sol, total_profit_usd,
                        win_rate, sharpe_ratio, max_drawdown,
                        total_trades, successful_trades, active_positions_count,
                        portfolio_metrics, state_json
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        model_provider,
                        state.get("trading_mode", "dry_run"),
                        state.get("cycles_completed", 0),
                        state.get("wallet_balance_sol"),
                        state.get("simulated_balance_sol"),
                        state.get("total_profit_sol"),
                        state.get("total_profit_usd"),
                        state.get("win_rate"),
                        state.get("sharpe_ratio"),
                        state.get("max_drawdown"),
                        state.get("total_trades"),
                        state.get("successful_trades"),
                        len(active_positions),
                        json.dumps(metrics),
                        json.dumps(lean_state),
                    ),
                )
    except Exception as e:
        logger.error(f"save_state_snapshot error: {e}")


# ─────────────────────────────────────────────────────────────
# Token discovery
# ─────────────────────────────────────────────────────────────

def record_discovered_token(
    session_id: str,
    cycle_id: Optional[int],
    model_provider: str,
    token_data: Dict[str, Any],
    action_taken: str = "skipped",
    skip_reason: str = None,
) -> None:
    if not is_available():
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO discovered_tokens (
                        session_id, cycle_id, model_provider,
                        token_address, token_symbol, token_name, discovery_source,
                        price_usd, liquidity_usd, volume_24h, market_cap, age_hours,
                        ai_score, safety_score, social_score,
                        action_taken, skip_reason, raw_data
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        session_id, cycle_id, model_provider,
                        token_data.get("address"),
                        token_data.get("symbol"),
                        token_data.get("name"),
                        token_data.get("discovery_source"),
                        token_data.get("price_usd"),
                        token_data.get("liquidity_usd"),
                        token_data.get("volume_24h"),
                        token_data.get("market_cap"),
                        token_data.get("age_hours"),
                        token_data.get("ai_score"),
                        token_data.get("ai_safety_score"),
                        token_data.get("ai_social_score"),
                        action_taken,
                        skip_reason,
                        json.dumps(token_data),
                    ),
                )
    except Exception as e:
        logger.error(f"record_discovered_token error: {e}")


# ─────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────

def record_agent_error(
    session_id: str,
    cycle_id: Optional[int],
    model_provider: str,
    error_type: str,
    error_message: str,
    stack_trace: str = None,
    tool_name: str = None,
    recoverable: bool = True,
) -> None:
    if not is_available():
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_errors (
                        session_id, cycle_id, model_provider,
                        error_type, error_message, stack_trace, tool_name, recoverable
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (session_id, cycle_id, model_provider,
                     error_type, error_message, stack_trace, tool_name, recoverable),
                )
    except Exception as e:
        logger.error(f"record_agent_error error: {e}")


# ─────────────────────────────────────────────────────────────
# Chat messages
# ─────────────────────────────────────────────────────────────

def save_chat_message(
    model_provider: str,
    role: str,
    content: str,
    session_id: str = None,
    metadata: Dict[str, Any] = None,
) -> None:
    if not is_available():
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO chat_messages (session_id, model_provider, role, content, metadata) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (session_id, model_provider, role, content,
                     json.dumps(metadata) if metadata else None),
                )
    except Exception as e:
        logger.error(f"save_chat_message error: {e}")

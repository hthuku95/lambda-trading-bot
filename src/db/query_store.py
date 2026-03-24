# src/db/query_store.py
"""
Read-side analytics queries — used by new agent DB tools and the UI.
All functions return plain dicts/lists and silently return empty results if DB is unavailable.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.db.connection import get_conn, is_available

logger = logging.getLogger("trading_agent.db.query_store")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────
# Trade history
# ─────────────────────────────────────────────────────────────

def get_trade_history(
    model_provider: str = None,
    token_address: str = None,
    trade_type: str = None,
    days_back: int = 30,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    if not is_available():
        return []
    try:
        since = _now() - timedelta(days=days_back)
        conditions = ["timestamp >= %s"]
        params: list = [since]

        if model_provider:
            conditions.append("model_provider = %s")
            params.append(model_provider)
        if token_address:
            conditions.append("token_address = %s")
            params.append(token_address)
        if trade_type:
            conditions.append("trade_type = %s")
            params.append(trade_type)

        where = " AND ".join(conditions)
        params += [limit, offset]

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, session_id, model_provider, trading_mode, trade_type,
                           token_address, token_symbol, amount_sol, price_usd,
                           dry_run, reasoning, simulated_balance_after,
                           transaction_id, success, error_message, timestamp
                    FROM trades WHERE {where}
                    ORDER BY timestamp DESC LIMIT %s OFFSET %s
                    """,
                    params,
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_trade_history error: {e}")
        return []


# ─────────────────────────────────────────────────────────────
# Session history
# ─────────────────────────────────────────────────────────────

def get_session_history(limit: int = 10) -> List[Dict[str, Any]]:
    if not is_available():
        return []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, model_provider, trading_mode, status,
                           started_at, ended_at, cycles_completed,
                           total_profit_sol, final_balance_sol, initial_balance_sol
                    FROM trading_sessions ORDER BY started_at DESC LIMIT %s
                    """,
                    (limit,),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_session_history error: {e}")
        return []


# ─────────────────────────────────────────────────────────────
# Performance analytics
# ─────────────────────────────────────────────────────────────

def get_performance_summary(
    model_provider: str = None,
    days_back: int = 7,
) -> Dict[str, Any]:
    if not is_available():
        return {}
    try:
        since = _now() - timedelta(days=days_back)
        provider_filter = "AND model_provider = %s" if model_provider else ""
        params_base = [since] + ([model_provider] if model_provider else [])

        with get_conn() as conn:
            with conn.cursor() as cur:
                # Trade stats
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) AS total_trades,
                        COUNT(*) FILTER (WHERE trade_type IN ('sell','partial_sell')) AS sell_trades,
                        COUNT(*) FILTER (WHERE success = TRUE) AS successful,
                        SUM(amount_sol) FILTER (WHERE trade_type = 'sell') AS total_sol_out,
                        AVG(amount_sol) AS avg_trade_sol
                    FROM trades
                    WHERE timestamp >= %s {provider_filter}
                    """,
                    params_base,
                )
                trade_row = cur.fetchone()

                # Win rate from closed positions
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) AS closed_positions,
                        COUNT(*) FILTER (WHERE profit_percentage > 0) AS profitable,
                        AVG(profit_percentage) AS avg_profit_pct,
                        MAX(profit_percentage) AS best_trade_pct,
                        MIN(profit_percentage) AS worst_trade_pct,
                        AVG(hold_time_hours) AS avg_hold_hours
                    FROM positions
                    WHERE status = 'closed' AND exit_time >= %s
                    {"AND model_provider = %s" if model_provider else ""}
                    """,
                    params_base,
                )
                pos_row = cur.fetchone()

                # Latest snapshot for Sharpe/drawdown
                cur.execute(
                    f"""
                    SELECT sharpe_ratio, max_drawdown, win_rate
                    FROM agent_state_snapshots
                    WHERE timestamp >= %s {provider_filter}
                    ORDER BY timestamp DESC LIMIT 1
                    """,
                    params_base,
                )
                snap_row = cur.fetchone()

        closed = pos_row[0] or 0
        profitable = pos_row[1] or 0

        return {
            "period_days": days_back,
            "model_provider": model_provider or "all",
            "total_trades": trade_row[0] or 0,
            "sell_trades": trade_row[1] or 0,
            "successful_trades": trade_row[2] or 0,
            "total_sol_received": round(float(trade_row[3] or 0), 6),
            "avg_trade_sol": round(float(trade_row[4] or 0), 6),
            "closed_positions": closed,
            "profitable_positions": profitable,
            "win_rate": round(profitable / closed, 4) if closed > 0 else 0.0,
            "avg_profit_pct": round(float(pos_row[2] or 0), 4),
            "best_trade_pct": round(float(pos_row[3] or 0), 4),
            "worst_trade_pct": round(float(pos_row[4] or 0), 4),
            "avg_hold_hours": round(float(pos_row[5] or 0), 2),
            "sharpe_ratio": round(float(snap_row[0] or 0), 4) if snap_row else 0.0,
            "max_drawdown": round(float(snap_row[1] or 0), 4) if snap_row else 0.0,
        }
    except Exception as e:
        logger.error(f"get_performance_summary error: {e}")
        return {}


# ─────────────────────────────────────────────────────────────
# Model comparison
# ─────────────────────────────────────────────────────────────

def compare_model_performance(days_back: int = 30) -> Dict[str, Any]:
    if not is_available():
        return {}
    try:
        since = _now() - timedelta(days=days_back)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        model_provider,
                        COUNT(DISTINCT session_id) AS sessions,
                        COUNT(*) AS total_trades,
                        COUNT(*) FILTER (WHERE trade_type = 'buy') AS buys,
                        COUNT(*) FILTER (WHERE trade_type IN ('sell','partial_sell')) AS sells,
                        SUM(amount_sol) AS total_sol_traded
                    FROM trades
                    WHERE timestamp >= %s
                    GROUP BY model_provider
                    """,
                    (since,),
                )
                trade_rows = {r[0]: r for r in cur.fetchall()}

                cur.execute(
                    """
                    SELECT
                        model_provider,
                        COUNT(*) AS closed,
                        COUNT(*) FILTER (WHERE profit_percentage > 0) AS profitable,
                        AVG(profit_percentage) AS avg_profit_pct,
                        SUM(realized_pnl_sol) AS total_pnl_sol
                    FROM positions
                    WHERE status = 'closed' AND exit_time >= %s
                    GROUP BY model_provider
                    """,
                    (since,),
                )
                pos_rows = {r[0]: r for r in cur.fetchall()}

        result = {}
        for provider in set(list(trade_rows.keys()) + list(pos_rows.keys())):
            t = trade_rows.get(provider, (provider, 0, 0, 0, 0, 0))
            p = pos_rows.get(provider, (provider, 0, 0, 0.0, 0.0))
            closed = p[1] or 0
            profitable = p[2] or 0
            result[provider] = {
                "sessions": t[1],
                "total_trades": t[2],
                "buys": t[3],
                "sells": t[4],
                "total_sol_traded": round(float(t[5] or 0), 6),
                "closed_positions": closed,
                "win_rate": round(profitable / closed, 4) if closed > 0 else 0.0,
                "avg_profit_pct": round(float(p[3] or 0), 4),
                "total_pnl_sol": round(float(p[4] or 0), 6),
            }
        return {"period_days": days_back, "models": result}
    except Exception as e:
        logger.error(f"compare_model_performance error: {e}")
        return {}


# ─────────────────────────────────────────────────────────────
# Token history
# ─────────────────────────────────────────────────────────────

def get_token_discovery_history(token_address: str, limit: int = 20) -> List[Dict[str, Any]]:
    if not is_available():
        return []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT model_provider, discovery_source, action_taken, skip_reason,
                           ai_score, safety_score, price_usd, liquidity_usd, timestamp
                    FROM discovered_tokens WHERE token_address = %s
                    ORDER BY timestamp DESC LIMIT %s
                    """,
                    (token_address, limit),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_token_discovery_history error: {e}")
        return []


def get_top_performing_tokens(
    metric: str = "profit_percentage",  # or 'trade_count', 'total_pnl_sol'
    limit: int = 20,
    days_back: int = 30,
) -> List[Dict[str, Any]]:
    if not is_available():
        return []
    valid_metrics = {"profit_percentage": "AVG(profit_percentage)",
                     "trade_count": "COUNT(*)",
                     "total_pnl_sol": "SUM(realized_pnl_sol)"}
    agg = valid_metrics.get(metric, "AVG(profit_percentage)")
    try:
        since = _now() - timedelta(days=days_back)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT token_address, token_symbol,
                           COUNT(*) AS trade_count,
                           AVG(profit_percentage) AS avg_profit_pct,
                           SUM(realized_pnl_sol) AS total_pnl_sol,
                           COUNT(*) FILTER (WHERE profit_percentage > 0) AS wins
                    FROM positions
                    WHERE status = 'closed' AND exit_time >= %s
                    GROUP BY token_address, token_symbol
                    ORDER BY {agg} DESC NULLS LAST
                    LIMIT %s
                    """,
                    (since, limit),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_top_performing_tokens error: {e}")
        return []


# ─────────────────────────────────────────────────────────────
# Log search
# ─────────────────────────────────────────────────────────────

def search_logs(
    level: str = None,
    keyword: str = None,
    logger_name: str = None,
    hours_back: int = 24,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    if not is_available():
        return []
    try:
        since = _now() - timedelta(hours=hours_back)
        conditions = ["timestamp >= %s"]
        params: list = [since]

        if level:
            conditions.append("level = %s")
            params.append(level.upper())
        if keyword:
            conditions.append("message ILIKE %s")
            params.append(f"%{keyword}%")
        if logger_name:
            conditions.append("logger_name ILIKE %s")
            params.append(f"%{logger_name}%")

        where = " AND ".join(conditions)
        params.append(limit)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT timestamp, level, logger_name, message
                    FROM system_logs WHERE {where}
                    ORDER BY timestamp DESC LIMIT %s
                    """,
                    params,
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"search_logs error: {e}")
        return []


def get_error_summary(hours: int = 24) -> Dict[str, Any]:
    if not is_available():
        return {}
    try:
        since = _now() - timedelta(hours=hours)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT error_type, COUNT(*) AS count FROM agent_errors "
                    "WHERE timestamp >= %s GROUP BY error_type ORDER BY count DESC",
                    (since,),
                )
                by_type = {r[0]: r[1] for r in cur.fetchall()}

                cur.execute(
                    "SELECT COUNT(*) FROM agent_errors WHERE timestamp >= %s", (since,)
                )
                total = cur.fetchone()[0]

        return {"hours": hours, "total_errors": total, "by_type": by_type}
    except Exception as e:
        logger.error(f"get_error_summary error: {e}")
        return {}


# ─────────────────────────────────────────────────────────────
# State restoration (used on startup when agent_state.json is missing)
# ─────────────────────────────────────────────────────────────

def restore_state_from_db(model_provider: str = None) -> Optional[Dict[str, Any]]:
    """
    Restore full agent state from PostgreSQL when agent_state.json is missing
    (e.g. after a Render redeploy wipes the container filesystem).

    Strategy:
      1. Load the most recent agent_state_snapshots row (state_json contains
         active_positions, transaction_history, agent_parameters, etc.)
      2. Overlay live open positions from the positions table (authoritative
         source for what is actually open, even if the snapshot is slightly stale)
      3. Overlay the exact cycles_completed count from trading_cycles
      4. Return a dict compatible with AgentState — caller should immediately
         write it back to agent_state.json so subsequent loads are from disk.

    Returns None if DB is unavailable or has no snapshots yet.
    """
    if not is_available():
        return None
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                # ── 1. Latest snapshot ──────────────────────────────────────
                if model_provider:
                    cur.execute(
                        """
                        SELECT state_json, cycles_completed, wallet_balance_sol,
                               total_profit_sol, win_rate, sharpe_ratio, max_drawdown,
                               total_trades, successful_trades, trading_mode,
                               model_provider, timestamp
                        FROM agent_state_snapshots
                        WHERE model_provider = %s
                        ORDER BY timestamp DESC LIMIT 1
                        """,
                        (model_provider,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT state_json, cycles_completed, wallet_balance_sol,
                               total_profit_sol, win_rate, sharpe_ratio, max_drawdown,
                               total_trades, successful_trades, trading_mode,
                               model_provider, timestamp
                        FROM agent_state_snapshots
                        ORDER BY timestamp DESC LIMIT 1
                        """
                    )
                row = cur.fetchone()
                if not row:
                    logger.info("restore_state_from_db: no snapshots found in DB")
                    return None

                (state_json, cycles_completed, wallet_balance_sol,
                 total_profit_sol, win_rate, sharpe_ratio, max_drawdown,
                 total_trades, successful_trades, trading_mode,
                 provider, snapshot_ts) = row

                if not state_json:
                    return None

                # psycopg2 returns JSONB as dict already; guard against string
                if isinstance(state_json, str):
                    state = json.loads(state_json)
                else:
                    state = dict(state_json)

                # ── 2. Overlay authoritative open positions ──────────────────
                cur.execute(
                    """
                    SELECT position_id, token_address, token_symbol,
                           entry_time, amount, position_size_sol,
                           entry_price_usd, entry_ai_score, entry_safety_score,
                           entry_reasoning, strategy, risk_level
                    FROM positions
                    WHERE status = 'open'
                    AND model_provider = %s
                    ORDER BY entry_time ASC
                    """,
                    (provider,),
                )
                cols = [d[0] for d in cur.description]
                open_rows = [dict(zip(cols, r)) for r in cur.fetchall()]

                if open_rows:
                    rebuilt = []
                    for p in open_rows:
                        entry_t = p["entry_time"]
                        entry_iso = (
                            entry_t.isoformat()
                            if hasattr(entry_t, "isoformat")
                            else str(entry_t)
                        )
                        rebuilt.append({
                            "position_id": p["position_id"],
                            "token_address": p["token_address"],
                            "token_symbol": p["token_symbol"] or "",
                            "entry_time": entry_iso,
                            "amount": p["amount"] or 0,
                            "position_size_sol": p["position_size_sol"] or 0,
                            "entry_price_usd": p["entry_price_usd"] or 0,
                            "current_price_usd": p["entry_price_usd"] or 0,  # stale; refreshed next cycle
                            "current_value_sol": p["position_size_sol"] or 0,
                            "current_value_usd": 0,
                            "unrealized_profit_sol": 0,
                            "current_profit_percentage": 0,
                            "entry_ai_score": p["entry_ai_score"] or 0,
                            "entry_safety_score": p["entry_safety_score"] or 0,
                            "entry_reasoning": p["entry_reasoning"] or "",
                            "strategy": p["strategy"] or "",
                            "risk_level": p["risk_level"] or "unknown",
                        })
                    state["active_positions"] = rebuilt
                else:
                    # No open positions in DB → clear the list (positions were closed
                    # between the snapshot and now, or there never were any)
                    state["active_positions"] = []

                # ── 3. Authoritative cycle count ────────────────────────────
                cur.execute(
                    """
                    SELECT COUNT(*) FROM trading_cycles
                    WHERE session_id IN (
                        SELECT id FROM trading_sessions WHERE model_provider = %s
                    )
                    """,
                    (provider,),
                )
                db_cycles = cur.fetchone()[0] or 0
                state["cycles_completed"] = max(db_cycles, cycles_completed or 0)

                # ── 4. Overlay scalar metrics from snapshot row ─────────────
                if wallet_balance_sol is not None:
                    state["wallet_balance_sol"] = wallet_balance_sol
                pm = state.setdefault("portfolio_metrics", {})
                if win_rate is not None:
                    pm["win_rate"] = win_rate
                if sharpe_ratio is not None:
                    pm["sharpe_ratio"] = sharpe_ratio
                if max_drawdown is not None:
                    pm["max_drawdown"] = max_drawdown
                if total_profit_sol is not None:
                    pm["total_profit_sol"] = total_profit_sol
                if total_trades is not None:
                    pm["total_closed_trades"] = total_trades
                if successful_trades is not None:
                    pm["successful_trades"] = successful_trades

                # Preserve trading_mode from snapshot so dry/live persists
                if trading_mode:
                    state["trading_mode"] = trading_mode
                    ap = state.setdefault("agent_parameters", {})
                    ap.setdefault("trading_mode", trading_mode)

                logger.info(
                    f"State restored from PostgreSQL snapshot "
                    f"(provider={provider}, ts={snapshot_ts}, "
                    f"cycles={state['cycles_completed']}, "
                    f"open_positions={len(state['active_positions'])})"
                )
                return state

    except Exception as e:
        logger.error(f"restore_state_from_db error: {e}")
        return None

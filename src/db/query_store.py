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

# src/db/backtest_store.py
"""
PostgreSQL read/write operations for the backtesting tables.

Tables:
    backtest_ohlcv_cache   — cached OHLCV candles
    backtest_results       — per-strategy run results

All public functions guard with `if not is_available(): return default`.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("trading_agent.db")


def _avail() -> bool:
    from src.db.connection import is_available
    return is_available()


def _conn():
    from src.db.connection import get_conn
    return get_conn()


# ─────────────────────────────────────────────────────────────────────────────
# OHLCV cache
# ─────────────────────────────────────────────────────────────────────────────

def cache_ohlcv(token_address: str, interval_minutes: int, candles: list[dict]) -> int:
    """
    Bulk-insert OHLCV candles. Skips duplicates (ON CONFLICT DO NOTHING).
    Returns number of rows inserted.
    """
    if not _avail() or not candles:
        return 0
    try:
        sql = """
            INSERT INTO backtest_ohlcv_cache
                (token_address, interval_minutes, timestamp,
                 open_price, high_price, low_price, close_price, volume_usd)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (token_address, interval_minutes, timestamp) DO NOTHING
        """
        rows = [
            (
                token_address,
                interval_minutes,
                c["timestamp"],
                c.get("open"),
                c.get("high"),
                c.get("low"),
                c.get("close"),
                c.get("volume_usd"),
            )
            for c in candles
        ]
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
        return len(rows)
    except Exception as e:
        logger.error(f"cache_ohlcv error: {e}")
        return 0


def get_cached_ohlcv(
    token_address: str,
    interval_minutes: int,
    start_ts: int,
    end_ts: int,
) -> list[dict]:
    """
    Load cached OHLCV candles from PostgreSQL.
    Returns [] if DB unavailable or no rows found.
    """
    if not _avail():
        return []
    try:
        sql = """
            SELECT timestamp, open_price, high_price, low_price, close_price, volume_usd
            FROM backtest_ohlcv_cache
            WHERE token_address = %s
              AND interval_minutes = %s
              AND timestamp BETWEEN %s AND %s
            ORDER BY timestamp ASC
        """
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (token_address, interval_minutes, start_ts, end_ts))
                rows = cur.fetchall()

        return [
            {
                "timestamp": row[0],
                "open": float(row[1] or 0),
                "high": float(row[2] or 0),
                "low": float(row[3] or 0),
                "close": float(row[4] or 0),
                "volume_usd": float(row[5] or 0),
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"get_cached_ohlcv error: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Backtest results
# ─────────────────────────────────────────────────────────────────────────────

def save_backtest_result(result: Any, run_id: str, model_provider: str = "") -> int:
    """
    Insert a BacktestResult into backtest_results.
    Returns inserted row id, or 0 on failure.
    """
    if not _avail():
        return 0
    try:
        sql = """
            INSERT INTO backtest_results (
                run_id, token_address, token_symbol, strategy_name, model_provider,
                timeframe_start, timeframe_end, num_trades, win_rate,
                total_return_pct, max_drawdown_pct, sharpe_ratio,
                avg_hold_minutes, best_trade_pct, worst_trade_pct, parameters
            ) VALUES (
                %s, %s, %s, %s, %s,
                to_timestamp(%s), to_timestamp(%s), %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s
            )
            RETURNING id
        """
        params = (
            run_id,
            result.token_address,
            result.token_symbol,
            result.strategy_name,
            model_provider,
            result.timeframe_start or None,
            result.timeframe_end or None,
            result.num_trades,
            result.win_rate,
            result.total_return_pct,
            result.max_drawdown_pct,
            result.sharpe_ratio,
            result.avg_hold_minutes,
            result.best_trade_pct,
            result.worst_trade_pct,
            json.dumps({}),
        )
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"save_backtest_result error: {e}")
        return 0


def get_best_strategy_for_token(token_address: str, model_provider: str = "") -> list[dict]:
    """
    Return strategies ranked by avg total_return_pct for a given token.
    Returns [] if DB unavailable.
    """
    if not _avail():
        return []
    try:
        sql = """
            SELECT strategy_name,
                   COUNT(*) AS runs,
                   AVG(total_return_pct) AS avg_return,
                   AVG(win_rate) AS avg_win_rate,
                   AVG(sharpe_ratio) AS avg_sharpe,
                   AVG(max_drawdown_pct) AS avg_drawdown
            FROM backtest_results
            WHERE token_address = %s
              AND (%s = '' OR model_provider = %s)
            GROUP BY strategy_name
            ORDER BY avg_return DESC
        """
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (token_address, model_provider, model_provider))
                rows = cur.fetchall()
        return [
            {
                "strategy_name": r[0],
                "runs": r[1],
                "avg_return_pct": round(float(r[2] or 0), 3),
                "avg_win_rate": round(float(r[3] or 0), 4),
                "avg_sharpe": round(float(r[4] or 0), 4),
                "avg_drawdown_pct": round(float(r[5] or 0), 3),
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"get_best_strategy_for_token error: {e}")
        return []


def get_backtest_leaderboard(limit: int = 20) -> list[dict]:
    """
    Top backtest results ranked by total_return_pct.
    Returns [] if DB unavailable.
    """
    if not _avail():
        return []
    try:
        sql = """
            SELECT token_symbol, token_address, strategy_name, model_provider,
                   total_return_pct, win_rate, sharpe_ratio, max_drawdown_pct,
                   num_trades, created_at
            FROM backtest_results
            WHERE num_trades > 0
            ORDER BY total_return_pct DESC
            LIMIT %s
        """
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (limit,))
                rows = cur.fetchall()
        return [
            {
                "token_symbol": r[0] or "UNKNOWN",
                "token_address": r[1],
                "strategy_name": r[2],
                "model_provider": r[3],
                "total_return_pct": round(float(r[4] or 0), 3),
                "win_rate": round(float(r[5] or 0), 4),
                "sharpe_ratio": round(float(r[6] or 0), 4),
                "max_drawdown_pct": round(float(r[7] or 0), 3),
                "num_trades": r[8],
                "created_at": r[9].isoformat() if r[9] else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"get_backtest_leaderboard error: {e}")
        return []


def get_backtest_run_summary(run_id: str) -> dict:
    """
    Aggregate stats for a full parallel run.
    Returns {} if DB unavailable or run not found.
    """
    if not _avail():
        return {}
    try:
        sql = """
            SELECT COUNT(*) AS combos,
                   SUM(num_trades) AS total_trades,
                   AVG(total_return_pct) AS avg_return,
                   MAX(total_return_pct) AS best_return,
                   MIN(total_return_pct) AS worst_return,
                   AVG(win_rate) AS avg_win_rate,
                   AVG(sharpe_ratio) AS avg_sharpe
            FROM backtest_results
            WHERE run_id = %s
        """
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (run_id,))
                row = cur.fetchone()
        if not row or row[0] == 0:
            return {}
        return {
            "run_id": run_id,
            "strategy_token_combos": row[0],
            "total_simulated_trades": row[1],
            "avg_return_pct": round(float(row[2] or 0), 3),
            "best_return_pct": round(float(row[3] or 0), 3),
            "worst_return_pct": round(float(row[4] or 0), 3),
            "avg_win_rate": round(float(row[5] or 0), 4),
            "avg_sharpe_ratio": round(float(row[6] or 0), 4),
        }
    except Exception as e:
        logger.error(f"get_backtest_run_summary error: {e}")
        return {}

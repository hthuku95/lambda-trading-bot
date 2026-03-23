# src/backtesting/engine.py
"""
Pure Python backtesting simulation engine.

No pandas, no numpy — only stdlib + our own strategy functions.
"""
import logging
import math
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

logger = logging.getLogger("trading_agent.backtesting")

# Annualisation factor for 5-minute candles
# 252 trading days × 24 hours × 12 five-min periods
_PERIODS_PER_YEAR_5M = 252 * 24 * 12

FEE_BPS_DEFAULT = 30  # 0.30% per trade (Jupiter swap fee estimate)


@dataclass
class BacktestResult:
    strategy_name: str
    token_address: str
    token_symbol: str
    num_trades: int
    win_rate: float            # fraction 0-1
    total_return_pct: float    # e.g. 0.25 = +25%
    max_drawdown_pct: float    # e.g. 0.10 = 10% drawdown (positive number)
    sharpe_ratio: float
    avg_hold_minutes: float
    best_trade_pct: float
    worst_trade_pct: float
    trade_log: list[dict] = field(default_factory=list)
    timeframe_start: int = 0   # unix timestamp
    timeframe_end: int = 0
    error: str = ""


def _compute_sharpe(returns: list[float], periods_per_year: int = _PERIODS_PER_YEAR_5M) -> float:
    """Annualised Sharpe ratio from per-trade return list (pure Python)."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean_r = sum(returns) / n
    variance = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
    std_r = math.sqrt(variance)
    if std_r == 0:
        return 0.0
    return (mean_r / std_r) * math.sqrt(periods_per_year)


def _compute_max_drawdown(equity_curve: list[float]) -> float:
    """Peak-to-trough drawdown as a positive fraction."""
    if len(equity_curve) < 2:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def run_backtest(
    token_address: str,
    strategy_fn: Callable,
    candles: list[dict],
    token_symbol: str = "",
    initial_sol: float = 1.0,
    fee_bps: int = FEE_BPS_DEFAULT,
) -> BacktestResult:
    """
    Simulate a single strategy against a candle series.

    Walk-forward only — no lookahead. Each step the strategy sees
    only candles[0..i] (inclusive).
    """
    strategy_name = getattr(strategy_fn, "__name__", "unknown").replace("strategy_", "")

    if len(candles) < 5:
        return BacktestResult(
            strategy_name=strategy_name,
            token_address=token_address,
            token_symbol=token_symbol,
            num_trades=0,
            win_rate=0.0,
            total_return_pct=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
            avg_hold_minutes=0.0,
            best_trade_pct=0.0,
            worst_trade_pct=0.0,
            error="insufficient candles",
        )

    fee_fraction = fee_bps / 10_000.0
    balance = initial_sol
    position: dict | None = None
    trade_log: list[dict] = []
    returns: list[float] = []
    equity_curve: list[float] = [initial_sol]
    timeframe_start = candles[0]["timestamp"]
    timeframe_end = candles[-1]["timestamp"]

    for i in range(len(candles)):
        candles_so_far = candles[: i + 1]
        current_candle = candles[i]
        price = current_candle["close"]
        ts = current_candle["timestamp"]

        signal = strategy_fn(candles_so_far, position)

        if signal == "BUY" and position is None and balance > 0:
            # Enter full position
            fee_cost = balance * fee_fraction
            invested = balance - fee_cost
            position = {
                "entry_price": price,
                "entry_ts": ts,
                "entry_sol": invested,
                "trade_id": str(uuid.uuid4())[:8],
            }
            balance = 0.0

        elif signal == "SELL" and position is not None:
            # Exit position
            entry_price = position["entry_price"]
            entry_sol = position["entry_sol"]
            if entry_price > 0:
                price_return = (price - entry_price) / entry_price
            else:
                price_return = 0.0

            gross_sol = entry_sol * (1.0 + price_return)
            fee_cost = gross_sol * fee_fraction
            exit_sol = gross_sol - fee_cost

            trade_pnl_pct = (exit_sol - initial_sol * (entry_sol / initial_sol) * 1.0) / (entry_sol + 1e-12) - fee_fraction
            # Simpler: just track net return relative to position size
            net_return = (exit_sol - entry_sol) / entry_sol if entry_sol > 0 else 0.0

            hold_minutes = (ts - position["entry_ts"]) / 60.0

            trade_log.append({
                "trade_id": position["trade_id"],
                "token_address": token_address,
                "token_symbol": token_symbol,
                "strategy": strategy_name,
                "trade_type": "ROUND_TRIP",
                "entry_price": entry_price,
                "exit_price": price,
                "entry_ts": position["entry_ts"],
                "exit_ts": ts,
                "hold_minutes": round(hold_minutes, 1),
                "profit_percentage": round(net_return * 100, 3),
                "success": net_return > 0,
            })

            returns.append(net_return)
            balance = exit_sol
            equity_curve.append(balance)
            position = None

    # Close any open position at last candle price
    if position is not None:
        price = candles[-1]["close"]
        entry_price = position["entry_price"]
        entry_sol = position["entry_sol"]
        if entry_price > 0:
            price_return = (price - entry_price) / entry_price
        else:
            price_return = 0.0
        gross_sol = entry_sol * (1.0 + price_return)
        fee_cost = gross_sol * fee_fraction
        exit_sol = gross_sol - fee_cost
        net_return = (exit_sol - entry_sol) / entry_sol if entry_sol > 0 else 0.0

        hold_minutes = (candles[-1]["timestamp"] - position["entry_ts"]) / 60.0
        trade_log.append({
            "trade_id": position["trade_id"],
            "token_address": token_address,
            "token_symbol": token_symbol,
            "strategy": strategy_name,
            "trade_type": "ROUND_TRIP",
            "entry_price": entry_price,
            "exit_price": price,
            "entry_ts": position["entry_ts"],
            "exit_ts": candles[-1]["timestamp"],
            "hold_minutes": round(hold_minutes, 1),
            "profit_percentage": round(net_return * 100, 3),
            "success": net_return > 0,
        })
        returns.append(net_return)
        balance = exit_sol
        equity_curve.append(balance)

    num_trades = len(trade_log)
    win_rate = sum(1 for r in returns if r > 0) / num_trades if num_trades > 0 else 0.0
    total_return_pct = (balance - initial_sol) / initial_sol
    max_dd = _compute_max_drawdown(equity_curve)
    sharpe = _compute_sharpe(returns)

    avg_hold = (
        sum(t["hold_minutes"] for t in trade_log) / num_trades if num_trades > 0 else 0.0
    )
    best_trade = max((t["profit_percentage"] for t in trade_log), default=0.0)
    worst_trade = min((t["profit_percentage"] for t in trade_log), default=0.0)

    return BacktestResult(
        strategy_name=strategy_name,
        token_address=token_address,
        token_symbol=token_symbol,
        num_trades=num_trades,
        win_rate=round(win_rate, 4),
        total_return_pct=round(total_return_pct * 100, 3),
        max_drawdown_pct=round(max_dd * 100, 3),
        sharpe_ratio=round(sharpe, 4),
        avg_hold_minutes=round(avg_hold, 1),
        best_trade_pct=round(best_trade, 3),
        worst_trade_pct=round(worst_trade, 3),
        trade_log=trade_log,
        timeframe_start=timeframe_start,
        timeframe_end=timeframe_end,
    )


def run_parallel_backtests(
    token_addresses: list[str],
    strategy_names: list[str],
    days_back: int = 30,
    max_workers: int = 8,
) -> list[BacktestResult]:
    """
    Run all token × strategy combos in parallel via ThreadPoolExecutor.

    Returns a flat list of BacktestResult objects (one per combo).
    Targets 50+ simulated trades/hour.
    """
    from src.data.historical_data import fetch_ohlcv
    from src.backtesting.strategies import get_strategy

    results: list[BacktestResult] = []

    # Pre-fetch all OHLCV data (I/O bound — do in parallel)
    ohlcv_map: dict[str, list[dict]] = {}

    def _fetch(addr: str) -> tuple[str, list[dict]]:
        return addr, fetch_ohlcv(addr, days_back=days_back, interval_minutes=5)

    with ThreadPoolExecutor(max_workers=min(max_workers, len(token_addresses) or 1)) as ex:
        futs = {ex.submit(_fetch, addr): addr for addr in token_addresses}
        for fut in as_completed(futs):
            try:
                addr, candles = fut.result()
                ohlcv_map[addr] = candles
            except Exception as e:
                logger.warning(f"OHLCV fetch failed: {e}")

    # Run backtests (CPU-bound but fast — still thread-parallel)
    combos = [
        (addr, name)
        for addr in token_addresses
        for name in strategy_names
        if addr in ohlcv_map and ohlcv_map[addr]
    ]

    def _run_one(addr: str, name: str) -> BacktestResult:
        candles = ohlcv_map[addr]
        strategy_fn = get_strategy(name)
        return run_backtest(addr, strategy_fn, candles)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_run_one, addr, name): (addr, name) for addr, name in combos}
        for fut in as_completed(futs):
            addr, name = futs[fut]
            try:
                result = fut.result()
                results.append(result)
            except Exception as e:
                logger.warning(f"Backtest failed for {addr}/{name}: {e}")
                results.append(BacktestResult(
                    strategy_name=name,
                    token_address=addr,
                    token_symbol="",
                    num_trades=0,
                    win_rate=0.0,
                    total_return_pct=0.0,
                    max_drawdown_pct=0.0,
                    sharpe_ratio=0.0,
                    avg_hold_minutes=0.0,
                    best_trade_pct=0.0,
                    worst_trade_pct=0.0,
                    error=str(e),
                ))

    return results

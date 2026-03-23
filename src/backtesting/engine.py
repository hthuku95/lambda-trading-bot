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
    market_regime: str = "unknown"   # bull | bear | sideways | volatile | unknown
    interval_minutes: int = 5        # candle resolution this result was run on


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


def detect_market_regime(candles: list[dict]) -> str:
    """
    Classify a candle series into a market regime.

    Returns one of: "bull" | "bear" | "sideways" | "volatile" | "unknown"

    Uses the last 50 candles (or all candles if fewer):
    - volatile : mean absolute per-candle return > 1.5%
    - bull     : net price change > +15% over the window
    - bear     : net price change < -15% over the window
    - sideways : everything else
    """
    if len(candles) < 20:
        return "unknown"

    lookback = min(50, len(candles))
    recent = candles[-lookback:]
    closes = [c["close"] for c in recent]

    # Mean absolute per-candle return (volatility proxy)
    abs_returns: list[float] = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            abs_returns.append(abs(closes[i] - closes[i - 1]) / closes[i - 1])
    avg_abs = sum(abs_returns) / len(abs_returns) if abs_returns else 0.0

    # Net trend across the window
    first_c = closes[0]
    last_c = closes[-1]
    trend = (last_c - first_c) / first_c if first_c > 0 else 0.0

    if avg_abs > 0.015:       # >1.5% avg absolute move per candle
        return "volatile"
    if trend > 0.15:
        return "bull"
    if trend < -0.15:
        return "bear"
    return "sideways"


def _annualisation_factor(interval_minutes: int) -> int:
    """Periods per year for a given candle interval (trading 24/7 for crypto)."""
    minutes_per_year = 365 * 24 * 60
    return max(1, minutes_per_year // interval_minutes)


def run_backtest(
    token_address: str,
    strategy_fn: Callable,
    candles: list[dict],
    token_symbol: str = "",
    initial_sol: float = 1.0,
    fee_bps: int = FEE_BPS_DEFAULT,
    interval_minutes: int = 5,
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
            interval_minutes=interval_minutes,
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
        price_return = (price - entry_price) / entry_price if entry_price > 0 else 0.0
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
    ann_factor = _annualisation_factor(interval_minutes)
    sharpe = _compute_sharpe(returns, periods_per_year=ann_factor)

    avg_hold = (
        sum(t["hold_minutes"] for t in trade_log) / num_trades if num_trades > 0 else 0.0
    )
    best_trade = max((t["profit_percentage"] for t in trade_log), default=0.0)
    worst_trade = min((t["profit_percentage"] for t in trade_log), default=0.0)

    regime = detect_market_regime(candles)

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
        market_regime=regime,
        interval_minutes=interval_minutes,
    )


def run_parallel_backtests(
    token_addresses: list[str],
    strategy_names: list[str],
    days_back: int = 30,
    max_workers: int = 8,
    interval_minutes: int = 5,
) -> list[BacktestResult]:
    """
    Run all token × strategy combos in parallel via ThreadPoolExecutor.

    Returns a flat list of BacktestResult objects (one per combo).
    """
    from src.data.historical_data import fetch_ohlcv
    from src.backtesting.strategies import get_strategy

    results: list[BacktestResult] = []

    # Pre-fetch all OHLCV data (I/O bound — do in parallel)
    ohlcv_map: dict[str, list[dict]] = {}

    def _fetch(addr: str) -> tuple[str, list[dict]]:
        return addr, fetch_ohlcv(addr, days_back=days_back, interval_minutes=interval_minutes)

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
        return run_backtest(addr, strategy_fn, candles, interval_minutes=interval_minutes)

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
                    interval_minutes=interval_minutes,
                ))

    return results


def run_multi_timeframe_backtests(
    token_addresses: list[str],
    strategy_names: list[str],
    timeframes_minutes: list[int] | None = None,
    days_back: int = 30,
    max_workers: int = 8,
) -> list[BacktestResult]:
    """
    Run all token × strategy × timeframe combos in parallel.

    Each returned BacktestResult has interval_minutes and market_regime populated.
    Using 3 timeframes × 24 strategies = 72x the context of a single-strategy run.

    Args:
        token_addresses:   Solana mint addresses to test
        strategy_names:    Strategy names from the registry
        timeframes_minutes: Candle intervals to test [default: 5, 15, 60]
        days_back:         Historical window (same calendar window, different granularity)
        max_workers:       Thread pool size
    """
    if timeframes_minutes is None:
        timeframes_minutes = [5, 15, 60]

    from src.data.historical_data import fetch_ohlcv
    from src.backtesting.strategies import get_strategy

    results: list[BacktestResult] = []

    # Pre-fetch all (token, timeframe) combos in parallel (I/O bound)
    ohlcv_map: dict[tuple[str, int], list[dict]] = {}
    fetch_keys = [(addr, tf) for addr in token_addresses for tf in timeframes_minutes]

    def _fetch(addr: str, tf: int) -> tuple[tuple[str, int], list[dict]]:
        return (addr, tf), fetch_ohlcv(addr, days_back=days_back, interval_minutes=tf)

    with ThreadPoolExecutor(max_workers=min(max_workers, len(fetch_keys) or 1)) as ex:
        futs = {ex.submit(_fetch, addr, tf): (addr, tf) for addr, tf in fetch_keys}
        for fut in as_completed(futs):
            try:
                key, candles = fut.result()
                if candles:
                    ohlcv_map[key] = candles
            except Exception as e:
                logger.warning(f"Multi-TF OHLCV fetch error: {e}")

    # Build and run all (token, strategy, timeframe) combos
    combos = [
        (addr, name, tf)
        for addr in token_addresses
        for name in strategy_names
        for tf in timeframes_minutes
        if (addr, tf) in ohlcv_map
    ]

    def _run_one(addr: str, name: str, tf: int) -> BacktestResult:
        candles = ohlcv_map[(addr, tf)]
        strategy_fn = get_strategy(name)
        return run_backtest(addr, strategy_fn, candles, interval_minutes=tf)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_run_one, a, n, tf): (a, n, tf) for a, n, tf in combos}
        for fut in as_completed(futs):
            a, n, tf = futs[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                logger.warning(f"Multi-TF backtest failed {a[:8]}/{n}/{tf}m: {e}")
                results.append(BacktestResult(
                    strategy_name=name,
                    token_address=a,
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
                    interval_minutes=tf,
                ))

    return results

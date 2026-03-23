# src/backtesting/__init__.py
"""
Backtesting package for the Lambda Trading Bot.

Public API:
    run_backtest(token_address, strategy_fn, candles, ...) -> BacktestResult
    run_parallel_backtests(token_addresses, strategy_names, days_back, ...) -> list[BacktestResult]
    run_multi_timeframe_backtests(token_addresses, strategy_names, timeframes_minutes, ...) -> list[BacktestResult]
    detect_market_regime(candles) -> str
    BacktestResult (dataclass)

Strategy registry:
    list_strategies() -> list[str]   # returns all 24 strategies
    get_strategy(name) -> Callable
"""
from src.backtesting.engine import (
    BacktestResult,
    run_backtest,
    run_parallel_backtests,
    run_multi_timeframe_backtests,
    detect_market_regime,
)
from src.backtesting.strategies import get_strategy, list_strategies, register

__all__ = [
    "BacktestResult",
    "run_backtest",
    "run_parallel_backtests",
    "run_multi_timeframe_backtests",
    "detect_market_regime",
    "get_strategy",
    "list_strategies",
    "register",
]

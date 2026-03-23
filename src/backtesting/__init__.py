# src/backtesting/__init__.py
"""
Backtesting package for the Lambda Trading Bot.

Public API:
    run_backtest(token_address, strategy_fn, candles, ...) -> BacktestResult
    run_parallel_backtests(token_addresses, strategy_names, days_back, ...) -> list[BacktestResult]
    BacktestResult (dataclass)

Strategy registry:
    list_strategies() -> list[str]
    get_strategy(name) -> Callable
"""
from src.backtesting.engine import BacktestResult, run_backtest, run_parallel_backtests
from src.backtesting.strategies import get_strategy, list_strategies, register

__all__ = [
    "BacktestResult",
    "run_backtest",
    "run_parallel_backtests",
    "get_strategy",
    "list_strategies",
    "register",
]

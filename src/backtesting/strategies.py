# src/backtesting/strategies.py
"""
Strategy registry + 6 named memecoin trading strategies.

Each strategy function signature:
    strategy_fn(candles: list[dict], position: dict | None) -> str
        candles  — all candles seen so far (no lookahead)
        position — current open position or None
        returns  — "BUY" | "SELL" | "HOLD"

All math uses pure Python (no pandas/numpy).
"""
from typing import Callable

_REGISTRY: dict[str, Callable] = {}


def register(name: str) -> Callable:
    def decorator(fn: Callable) -> Callable:
        _REGISTRY[name] = fn
        return fn
    return decorator


def get_strategy(name: str) -> Callable:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown strategy: {name!r}. Available: {list(_REGISTRY)}")
    return _REGISTRY[name]


def list_strategies() -> list[str]:
    return list(_REGISTRY.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Helpers (pure Python rolling-window math)
# ─────────────────────────────────────────────────────────────────────────────

def _sma(values: list[float], n: int) -> float | None:
    """Simple moving average of last n values."""
    if len(values) < n:
        return None
    window = values[-n:]
    return sum(window) / n


def _slope(values: list[float], n: int) -> float | None:
    """Percentage slope across last n closes: (last - first) / first."""
    if len(values) < n:
        return None
    first = values[-n]
    last = values[-1]
    if first == 0:
        return None
    return (last - first) / first


def _rsi(closes: list[float], period: int = 14) -> float | None:
    """Pure-Python RSI. Returns None if not enough data."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-delta)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _avg_volume(candles: list[dict], n: int) -> float | None:
    if len(candles) < n:
        return None
    return sum(c["volume_usd"] for c in candles[-n:]) / n


def _recent_high(candles: list[dict], n: int) -> float | None:
    if len(candles) < n:
        return None
    return max(c["high"] for c in candles[-n:])


# ─────────────────────────────────────────────────────────────────────────────
# Strategy: momentum
# ─────────────────────────────────────────────────────────────────────────────

@register("momentum")
def strategy_momentum(candles: list[dict], position: dict | None) -> str:
    """
    Buy when 3-candle close slope > 2%.
    Sell when slope < -1% OR open position has +15% gain.
    """
    if len(candles) < 4:
        return "HOLD"

    closes = [c["close"] for c in candles]
    slope = _slope(closes, 3)
    if slope is None:
        return "HOLD"

    if position:
        entry = position.get("entry_price", closes[-1])
        if entry and entry > 0:
            gain_pct = (closes[-1] - entry) / entry
            if gain_pct >= 0.15 or slope < -0.01:
                return "SELL"
        return "HOLD"

    if slope > 0.02:
        return "BUY"
    return "HOLD"


# ─────────────────────────────────────────────────────────────────────────────
# Strategy: safety_first
# ─────────────────────────────────────────────────────────────────────────────

@register("safety_first")
def strategy_safety_first(candles: list[dict], position: dict | None) -> str:
    """
    Buy when: price > 20-candle SMA AND current volume > 1.5x avg volume.
    Sell when: +10% gain OR -5% loss.
    """
    if len(candles) < 21:
        return "HOLD"

    closes = [c["close"] for c in candles]
    current_close = closes[-1]

    sma20 = _sma(closes, 20)
    avg_vol = _avg_volume(candles, 20)
    current_vol = candles[-1]["volume_usd"]

    if position:
        entry = position.get("entry_price", current_close)
        if entry and entry > 0:
            gain_pct = (current_close - entry) / entry
            if gain_pct >= 0.10 or gain_pct <= -0.05:
                return "SELL"
        return "HOLD"

    if sma20 and avg_vol and current_close > sma20 and current_vol > avg_vol * 1.5:
        return "BUY"
    return "HOLD"


# ─────────────────────────────────────────────────────────────────────────────
# Strategy: quick_flip
# ─────────────────────────────────────────────────────────────────────────────

@register("quick_flip")
def strategy_quick_flip(candles: list[dict], position: dict | None) -> str:
    """
    Buy on 2% dip from recent 12-candle high.
    Sell at +5% gain OR -3% loss (tight stops).
    """
    if len(candles) < 13:
        return "HOLD"

    closes = [c["close"] for c in candles]
    current_close = closes[-1]
    high_12 = _recent_high(candles, 12)

    if position:
        entry = position.get("entry_price", current_close)
        if entry and entry > 0:
            gain_pct = (current_close - entry) / entry
            if gain_pct >= 0.05 or gain_pct <= -0.03:
                return "SELL"
        return "HOLD"

    if high_12 and high_12 > 0:
        dip_pct = (current_close - high_12) / high_12
        if dip_pct <= -0.02:
            return "BUY"
    return "HOLD"


# ─────────────────────────────────────────────────────────────────────────────
# Strategy: reversal
# ─────────────────────────────────────────────────────────────────────────────

@register("reversal")
def strategy_reversal(candles: list[dict], position: dict | None) -> str:
    """
    Buy when RSI(14) < 30 (oversold).
    Sell when RSI(14) > 60.
    """
    if len(candles) < 16:
        return "HOLD"

    closes = [c["close"] for c in candles]
    rsi = _rsi(closes, 14)
    if rsi is None:
        return "HOLD"

    if position:
        if rsi > 60:
            return "SELL"
        return "HOLD"

    if rsi < 30:
        return "BUY"
    return "HOLD"


# ─────────────────────────────────────────────────────────────────────────────
# Strategy: breakout
# ─────────────────────────────────────────────────────────────────────────────

@register("breakout")
def strategy_breakout(candles: list[dict], position: dict | None) -> str:
    """
    Buy when price exceeds 24h high (288 five-minute candles) on above-avg volume.
    Sell when -5% from entry.
    """
    lookback = min(288, len(candles) - 1)
    if lookback < 10:
        return "HOLD"

    closes = [c["close"] for c in candles]
    current_close = closes[-1]
    current_vol = candles[-1]["volume_usd"]

    prior_high = max(c["high"] for c in candles[-lookback - 1:-1])
    avg_vol = _avg_volume(candles[:-1], lookback)

    if position:
        entry = position.get("entry_price", current_close)
        if entry and entry > 0:
            gain_pct = (current_close - entry) / entry
            if gain_pct <= -0.05:
                return "SELL"
        return "HOLD"

    if avg_vol and current_close > prior_high and current_vol > avg_vol * 1.2:
        return "BUY"
    return "HOLD"


# ─────────────────────────────────────────────────────────────────────────────
# Strategy: hybrid
# ─────────────────────────────────────────────────────────────────────────────

@register("hybrid")
def strategy_hybrid(candles: list[dict], position: dict | None) -> str:
    """
    Combined momentum + safety_first.
    Requires BOTH to agree before buying.
    Sells if either strategy says SELL.
    """
    momentum_signal = strategy_momentum(candles, position)
    safety_signal = strategy_safety_first(candles, position)

    if position:
        if momentum_signal == "SELL" or safety_signal == "SELL":
            return "SELL"
        return "HOLD"

    if momentum_signal == "BUY" and safety_signal == "BUY":
        return "BUY"
    return "HOLD"

# src/backtesting/strategies.py
"""
Strategy registry + named memecoin trading strategies.

Each strategy function signature:
    strategy_fn(candles: list[dict], position: dict | None) -> str
        candles  — all candles seen so far (no lookahead)
        position — current open position or None
        returns  — "BUY" | "SELL" | "HOLD"

6 base strategies + 18 parameterized variants = 24 total.
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
# Parameter factories — register variants without code duplication
# ─────────────────────────────────────────────────────────────────────────────

def _make_momentum(name: str, slope_period: int, buy_threshold: float,
                   take_profit: float, stop_loss: float) -> Callable:
    """Factory: momentum strategy variant."""
    def _fn(candles: list[dict], position: dict | None) -> str:
        if len(candles) < slope_period + 1:
            return "HOLD"
        closes = [c["close"] for c in candles]
        slope = _slope(closes, slope_period)
        if slope is None:
            return "HOLD"
        if position:
            entry = position.get("entry_price", closes[-1])
            if entry and entry > 0:
                gain = (closes[-1] - entry) / entry
                if gain >= take_profit or gain <= stop_loss:
                    return "SELL"
            return "HOLD"
        if slope > buy_threshold:
            return "BUY"
        return "HOLD"
    _fn.__name__ = name
    _REGISTRY[name] = _fn
    return _fn


def _make_reversal(name: str, rsi_period: int, buy_rsi: float, sell_rsi: float) -> Callable:
    """Factory: RSI reversal strategy variant."""
    def _fn(candles: list[dict], position: dict | None) -> str:
        if len(candles) < rsi_period + 2:
            return "HOLD"
        closes = [c["close"] for c in candles]
        rsi = _rsi(closes, rsi_period)
        if rsi is None:
            return "HOLD"
        if position:
            if rsi > sell_rsi:
                return "SELL"
            return "HOLD"
        if rsi < buy_rsi:
            return "BUY"
        return "HOLD"
    _fn.__name__ = name
    _REGISTRY[name] = _fn
    return _fn


def _make_quick_flip(name: str, lookback: int, dip_pct: float,
                     take_profit: float, stop_loss: float) -> Callable:
    """Factory: dip-buy quick-flip variant."""
    def _fn(candles: list[dict], position: dict | None) -> str:
        if len(candles) < lookback + 1:
            return "HOLD"
        closes = [c["close"] for c in candles]
        current_close = closes[-1]
        high_n = _recent_high(candles, lookback)
        if position:
            entry = position.get("entry_price", current_close)
            if entry and entry > 0:
                gain = (current_close - entry) / entry
                if gain >= take_profit or gain <= stop_loss:
                    return "SELL"
            return "HOLD"
        if high_n and high_n > 0:
            dip = (current_close - high_n) / high_n
            if dip <= dip_pct:
                return "BUY"
        return "HOLD"
    _fn.__name__ = name
    _REGISTRY[name] = _fn
    return _fn


def _make_safety_first(name: str, sma_period: int, vol_mult: float,
                        take_profit: float, stop_loss: float) -> Callable:
    """Factory: SMA + volume safety-first variant."""
    def _fn(candles: list[dict], position: dict | None) -> str:
        if len(candles) < sma_period + 1:
            return "HOLD"
        closes = [c["close"] for c in candles]
        current_close = closes[-1]
        sma = _sma(closes, sma_period)
        avg_vol = _avg_volume(candles, sma_period)
        current_vol = candles[-1]["volume_usd"]
        if position:
            entry = position.get("entry_price", current_close)
            if entry and entry > 0:
                gain = (current_close - entry) / entry
                if gain >= take_profit or gain <= stop_loss:
                    return "SELL"
            return "HOLD"
        if sma and avg_vol and current_close > sma and current_vol > avg_vol * vol_mult:
            return "BUY"
        return "HOLD"
    _fn.__name__ = name
    _REGISTRY[name] = _fn
    return _fn


def _make_breakout(name: str, lookback_candles: int, vol_mult: float,
                   stop_loss: float) -> Callable:
    """Factory: price breakout above recent high with volume confirmation."""
    def _fn(candles: list[dict], position: dict | None) -> str:
        lb = min(lookback_candles, len(candles) - 1)
        if lb < 10:
            return "HOLD"
        closes = [c["close"] for c in candles]
        current_close = closes[-1]
        current_vol = candles[-1]["volume_usd"]
        prior_high = max(c["high"] for c in candles[-lb - 1:-1])
        avg_vol = _avg_volume(candles[:-1], lb)
        if position:
            entry = position.get("entry_price", current_close)
            if entry and entry > 0:
                gain = (current_close - entry) / entry
                if gain <= stop_loss:
                    return "SELL"
            return "HOLD"
        if avg_vol and current_close > prior_high and current_vol > avg_vol * vol_mult:
            return "BUY"
        return "HOLD"
    _fn.__name__ = name
    _REGISTRY[name] = _fn
    return _fn


# ─────────────────────────────────────────────────────────────────────────────
# Base strategies (original 6 — unchanged behaviour)
# ─────────────────────────────────────────────────────────────────────────────

@register("momentum")
def strategy_momentum(candles: list[dict], position: dict | None) -> str:
    """Buy on 3-candle +2% slope. Sell on +15% gain or slope reversal."""
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


@register("safety_first")
def strategy_safety_first(candles: list[dict], position: dict | None) -> str:
    """Price > 20-SMA and volume > 1.5x avg. TP +10%, SL -5%."""
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


@register("quick_flip")
def strategy_quick_flip(candles: list[dict], position: dict | None) -> str:
    """Buy on 2% dip from 12-candle high. TP +5%, SL -3%."""
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


@register("reversal")
def strategy_reversal(candles: list[dict], position: dict | None) -> str:
    """Buy RSI(14) < 30 (oversold). Sell RSI > 60."""
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


@register("breakout")
def strategy_breakout(candles: list[dict], position: dict | None) -> str:
    """24h high breakout on above-avg volume. SL -5%."""
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


@register("hybrid")
def strategy_hybrid(candles: list[dict], position: dict | None) -> str:
    """momentum + safety_first must both agree to buy. Either triggers sell."""
    momentum_signal = strategy_momentum(candles, position)
    safety_signal = strategy_safety_first(candles, position)
    if position:
        if momentum_signal == "SELL" or safety_signal == "SELL":
            return "SELL"
        return "HOLD"
    if momentum_signal == "BUY" and safety_signal == "BUY":
        return "BUY"
    return "HOLD"


# ─────────────────────────────────────────────────────────────────────────────
# Momentum variants (4 new)
# ─────────────────────────────────────────────────────────────────────────────
# Parameters: slope_period, buy_threshold, take_profit, stop_loss

# Very short-term scalp: tight entry/exit, 2-candle slope
_make_momentum("momentum_scalp",        2, 0.010, 0.08, -0.005)
# Swing trade: longer slope confirmation, wide TP
_make_momentum("momentum_swing",        5, 0.030, 0.25, -0.020)
# Aggressive: low buy threshold, high TP, tight SL
_make_momentum("momentum_aggressive",   3, 0.015, 0.20, -0.005)
# Conservative: strong signal required, moderate TP with protection
_make_momentum("momentum_conservative", 4, 0.030, 0.10, -0.020)


# ─────────────────────────────────────────────────────────────────────────────
# Reversal variants (4 new)
# ─────────────────────────────────────────────────────────────────────────────
# Parameters: rsi_period, buy_rsi_threshold, sell_rsi_threshold

# Stricter oversold requirement
_make_reversal("reversal_oversold", 14, 25, 55)
# More permissive entry — catches earlier reversals
_make_reversal("reversal_loose",    14, 35, 65)
# Faster RSI: reacts quicker to price moves
_make_reversal("reversal_fast",      7, 30, 60)
# Slower RSI: more stable, fewer false signals
_make_reversal("reversal_slow",     21, 28, 62)


# ─────────────────────────────────────────────────────────────────────────────
# Quick-flip variants (3 new)
# ─────────────────────────────────────────────────────────────────────────────
# Parameters: lookback_candles, dip_pct, take_profit, stop_loss

# Micro scalp: tiny dip, very short lookback, tight TP/SL
_make_quick_flip("quick_flip_micro",  6, -0.010, 0.03, -0.020)
# Deep dip: larger drawdown required, bigger TP
_make_quick_flip("quick_flip_deep",  24, -0.030, 0.08, -0.050)
# Tight: moderate lookback, slightly lower entry bar
_make_quick_flip("quick_flip_tight", 12, -0.015, 0.04, -0.020)


# ─────────────────────────────────────────────────────────────────────────────
# Safety-first variants (2 new)
# ─────────────────────────────────────────────────────────────────────────────
# Parameters: sma_period, vol_multiplier, take_profit, stop_loss

# Tight: shorter SMA, lower volume bar, quicker exit
_make_safety_first("safety_first_tight",   10, 1.2, 0.07, -0.030)
# Relaxed: longer SMA confirmation, higher vol bar, wider TP
_make_safety_first("safety_first_relaxed", 30, 2.0, 0.15, -0.080)


# ─────────────────────────────────────────────────────────────────────────────
# Breakout variants (2 new)
# ─────────────────────────────────────────────────────────────────────────────
# Parameters: lookback_candles, vol_multiplier, stop_loss

# Short: 6h high breakout (72 × 5-min candles)
_make_breakout("breakout_short", 72,  1.1, -0.040)
# Long: 48h consolidation breakout (576 × 5-min candles)
_make_breakout("breakout_long",  576, 1.5, -0.070)


# ─────────────────────────────────────────────────────────────────────────────
# Hybrid variants (3 new) — composites referencing other strategies
# ─────────────────────────────────────────────────────────────────────────────

@register("hybrid_aggressive")
def strategy_hybrid_aggressive(candles: list[dict], position: dict | None) -> str:
    """momentum_scalp + reversal_fast: fast signals from both directions."""
    s1 = _REGISTRY["momentum_scalp"](candles, position)
    s2 = _REGISTRY["reversal_fast"](candles, position)
    if position:
        return "SELL" if s1 == "SELL" or s2 == "SELL" else "HOLD"
    return "BUY" if s1 == "BUY" and s2 == "BUY" else "HOLD"


@register("hybrid_conservative")
def strategy_hybrid_conservative(candles: list[dict], position: dict | None) -> str:
    """momentum_conservative + safety_first_relaxed: high-conviction entries only."""
    s1 = _REGISTRY["momentum_conservative"](candles, position)
    s2 = _REGISTRY["safety_first_relaxed"](candles, position)
    if position:
        return "SELL" if s1 == "SELL" or s2 == "SELL" else "HOLD"
    return "BUY" if s1 == "BUY" and s2 == "BUY" else "HOLD"


@register("hybrid_breakout")
def strategy_hybrid_breakout(candles: list[dict], position: dict | None) -> str:
    """breakout_short + momentum: breakout must be accompanied by momentum."""
    s1 = _REGISTRY["breakout_short"](candles, position)
    s2 = _REGISTRY["momentum"](candles, position)
    if position:
        return "SELL" if s1 == "SELL" or s2 == "SELL" else "HOLD"
    return "BUY" if s1 == "BUY" and s2 == "BUY" else "HOLD"

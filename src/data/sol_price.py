# src/data/sol_price.py
"""
SOL/USD price feed via CoinGecko free API.
Caches the result for 60 seconds to avoid hammering the endpoint.
"""
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger("trading_agent.sol_price")

_CACHE: dict = {"price": None, "timestamp": 0.0}
_CACHE_TTL = 60  # seconds
_COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"


def get_sol_price_usd() -> Optional[float]:
    """
    Return the current SOL/USD price.

    Uses a 60-second in-process cache. Returns None if the API call fails.
    """
    now = time.time()
    if _CACHE["price"] is not None and (now - _CACHE["timestamp"]) < _CACHE_TTL:
        return _CACHE["price"]

    try:
        resp = requests.get(_COINGECKO_URL, timeout=5)
        resp.raise_for_status()
        price = float(resp.json()["solana"]["usd"])
        _CACHE["price"] = price
        _CACHE["timestamp"] = now
        logger.debug(f"SOL price fetched: ${price:.2f}")
        return price
    except Exception as e:
        logger.warning(f"SOL price fetch failed: {e}")
        # Return stale cache if available
        return _CACHE["price"]


def sol_to_usd(sol_amount: float) -> float:
    """Convert a SOL amount to USD. Returns 0.0 if price unavailable."""
    price = get_sol_price_usd()
    if price is None:
        return 0.0
    return sol_amount * price

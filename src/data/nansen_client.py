# src/data/nansen_client.py
"""
Nansen API Client — Smart Money Intelligence for Solana Memecoin Trading

Replaces TweetScout as the primary social/on-chain intelligence source.
Provides:
  - Smart money token screening (who the best traders are buying)
  - Per-token smart money signal (holders, flows, DEX trades)
  - Token information (social links, market metadata)
  - Nansen risk/reward indicators
  - Flow intelligence (accumulation vs distribution by holder segment)

Auth: apiKey header (not Bearer)
Rate limit: 20 req/s, 300 req/min
Docs: https://docs.nansen.ai/
"""
import os
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from src.memory.cache import get_cached_data, cache_data

logger = logging.getLogger("trading_agent.nansen")

_BASE_URL = "https://api.nansen.ai/api/v1"
_TIMEOUT = 15  # seconds per request


def _api_key() -> str:
    return os.getenv("NANSEN_API_KEY", "")


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "apiKey": _api_key(),
    }


def _is_available() -> bool:
    return bool(_api_key())


def _post(endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    POST to Nansen API; returns parsed JSON or None on failure.

    403 with "Insufficient credits" means the endpoint requires a higher
    subscription tier — logged at DEBUG level so it doesn't pollute logs.
    """
    if not _is_available():
        logger.debug("NANSEN_API_KEY not configured — skipping request")
        return None
    url = f"{_BASE_URL}{endpoint}"
    try:
        resp = requests.post(url, headers=_headers(), json=payload, timeout=_TIMEOUT)
        if resp.status_code == 403:
            body = resp.text[:150]
            if "Insufficient credits" in body or "credits" in body.lower():
                logger.debug(
                    f"Nansen {endpoint}: endpoint requires higher subscription tier"
                )
            else:
                logger.warning(f"Nansen {endpoint}: 403 — {body}")
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Nansen HTTP error {endpoint}: {e.response.status_code} — {e.response.text[:200]}")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"Nansen request error {endpoint}: {e}")
        return None
    except Exception as e:
        logger.error(f"Nansen unexpected error {endpoint}: {e}")
        return None


def _get(endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """GET from Nansen API; returns parsed JSON or None on failure."""
    if not _is_available():
        return None
    url = f"{_BASE_URL}{endpoint}"
    try:
        resp = requests.get(url, headers=_headers(), params=params or {}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Nansen HTTP error {endpoint}: {e.response.status_code}")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"Nansen request error {endpoint}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. TOKEN SCREENER  — discover smart money opportunities on Solana
# ─────────────────────────────────────────────────────────────────────────────

def screen_smart_money_tokens(
    timeframe: str = "1h",
    per_page: int = 50,
    only_smart_money: bool = True,
    min_token_age_days: int = 0,
    max_token_age_days: int = 180,
) -> List[Dict[str, Any]]:
    """
    Discover Solana tokens with significant smart money buying activity.

    Returns a list of token dicts sorted by buy_volume DESC.
    Each dict contains: token_address, token_symbol, chain, market_cap_usd,
    liquidity, price_usd, price_change, buy_volume, sell_volume, netflow,
    nof_traders, inflow_fdv_ratio, outflow_fdv_ratio, token_age_days.

    Cached for 5 minutes (screener data refreshes every few minutes on Nansen).
    """
    cache_key = f"nansen_screener_{timeframe}_{only_smart_money}_{per_page}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    payload = {
        "chains": ["solana"],
        "timeframe": timeframe,
        "filters": {
            "only_smart_money": only_smart_money,
            "token_age_days": {"min": min_token_age_days, "max": max_token_age_days},
        },
        "order_by": [{"field": "buy_volume", "direction": "DESC"}],
        "pagination": {"page": 1, "per_page": per_page},
    }

    result = _post("/token-screener", payload)
    tokens = result.get("data", []) if result else []

    cache_data(cache_key, tokens, ttl_seconds=300)
    logger.info(f"Nansen screener: {len(tokens)} Solana tokens with smart money activity ({timeframe})")
    return tokens


# ─────────────────────────────────────────────────────────────────────────────
# 2. TOKEN INFORMATION  — social links + market metadata
# ─────────────────────────────────────────────────────────────────────────────

def get_token_information(
    token_address: str,
    timeframe: str = "24h",
) -> Dict[str, Any]:
    """
    Fetch token metadata including social links (X/Twitter, Telegram, website),
    deployment date, market cap, volume, holder count, and liquidity.

    Cached for 10 minutes.
    """
    cache_key = f"nansen_token_info_{token_address}_{timeframe}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    payload = {
        "chain": "solana",
        "token_address": token_address,
        "timeframe": timeframe,
    }

    result = _post("/tgm/token-information", payload)  # requires Growth+ plan
    data = result if result else {}

    cache_data(cache_key, data, ttl_seconds=600)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# 3. SMART MONEY HOLDERS  — concentration and quality of holders
# ─────────────────────────────────────────────────────────────────────────────

def get_smart_money_holders(
    token_address: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Return top smart money holders for a token.

    Each entry: address, address_label, token_amount, value_usd,
    ownership_percentage, balance_change_24h, balance_change_7d.

    Cached for 5 minutes.
    """
    cache_key = f"nansen_sm_holders_{token_address}_{limit}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    payload = {
        "chain": "solana",
        "token_address": token_address,
        "label_type": "smart_money",
        "pagination": {"page": 1, "per_page": limit},
        "order_by": {"field": "value_usd", "direction": "DESC"},
    }

    result = _post("/tgm/holders", payload)  # requires Growth+ plan
    holders = result.get("data", []) if result else []

    cache_data(cache_key, holders, ttl_seconds=300)
    return holders


# ─────────────────────────────────────────────────────────────────────────────
# 4. FLOW INTELLIGENCE  — accumulation vs distribution by segment
# ─────────────────────────────────────────────────────────────────────────────

def get_flow_intelligence(
    token_address: str,
    timeframe: str = "1h",
) -> Dict[str, Any]:
    """
    Return net flows broken down by holder segment:
      exchanges, whales, smart_traders, top_pnl, public_figures, fresh_wallets.

    Each segment: net_flow_usd, avg_flow_usd, wallet_count.
    Positive net_flow_usd = accumulation; negative = distribution.

    Cached for 5 minutes.
    """
    cache_key = f"nansen_flow_intel_{token_address}_{timeframe}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    payload = {
        "chain": "solana",
        "token_address": token_address,
        "timeframe": timeframe,
    }

    result = _post("/tgm/flow-intelligence", payload)  # requires Growth+ plan
    data = result if result else {}

    cache_data(cache_key, data, ttl_seconds=300)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# 5. SMART MONEY DEX TRADES  — real-time smart money buy/sell activity
# ─────────────────────────────────────────────────────────────────────────────

def get_smart_money_dex_trades(
    token_address: str,
    hours_back: int = 6,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Return recent DEX trades by smart money wallets for a specific token.

    Each entry: block_timestamp, tx_hash, trader_address, trader_label,
    action (BUY/SELL), token_amount, value_usd.

    Cached for 2 minutes (high-frequency data).
    """
    cache_key = f"nansen_sm_dex_{token_address}_{hours_back}_{limit}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    now = datetime.now(timezone.utc)
    from_dt = (now - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_dt = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "chain": "solana",
        "token_address": token_address,
        "date": {"from": from_dt, "to": to_dt},
        "only_smart_money": True,
        "pagination": {"page": 1, "per_page": limit},
        "order_by": {"field": "block_timestamp", "direction": "DESC"},
    }

    result = _post("/tgm/dex-trades", payload)  # requires Growth+ plan
    trades = result.get("data", []) if result else []

    cache_data(cache_key, trades, ttl_seconds=120)
    return trades


# ─────────────────────────────────────────────────────────────────────────────
# 6. NANSEN INDICATORS  — risk/reward scoring
# ─────────────────────────────────────────────────────────────────────────────

def get_nansen_indicators(token_address: str) -> Dict[str, Any]:
    """
    Fetch Nansen risk + reward indicators for a token.

    Risk indicators: liquidity-risk, concentration-risk, token-supply-inflation
    Reward indicators: price-momentum, trading-range, cex-flows

    Each indicator has: score (categorical), signal (raw), signal_percentile (0-100).

    Cached for 15 minutes (indicators update infrequently).
    """
    cache_key = f"nansen_indicators_{token_address}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    payload = {
        "chain": "solana",
        "token_address": token_address,
    }

    result = _post("/tgm/indicators", payload)  # requires Growth+ plan
    data = result if result else {}

    cache_data(cache_key, data, ttl_seconds=900)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# 7. SMART MONEY HOLDINGS SCREENER  — what smart money is accumulating globally
# ─────────────────────────────────────────────────────────────────────────────

def get_smart_money_accumulation(
    timeframe: str = "24h",
    per_page: int = 50,
) -> List[Dict[str, Any]]:
    """
    Return Solana tokens being actively accumulated by smart money wallets,
    sorted by 24h balance change.

    Each entry: token_address, token_symbol, value_usd, holders_count,
    balance_24h_percent_change, market_cap_usd.

    Cached for 10 minutes.
    """
    cache_key = f"nansen_sm_accumulation_{timeframe}_{per_page}"
    cached = get_cached_data(cache_key)
    if cached is not None:
        return cached

    payload = {
        "chains": ["solana"],
        "include_stablecoins": False,
        "include_native_tokens": False,
        "token_age_days": {"max": 365},
        "order_by": {"field": "balance_24h_percent_change", "direction": "DESC"},
        "pagination": {"page": 1, "per_page": per_page},
    }

    result = _post("/smart-money/holdings", payload)  # requires Growth+ plan
    holdings = result.get("data", []) if result else []

    cache_data(cache_key, holdings, ttl_seconds=600)
    logger.info(f"Nansen smart money accumulation: {len(holdings)} tokens being accumulated")
    return holdings


# ─────────────────────────────────────────────────────────────────────────────
# 8. COMPOSITE SIGNAL  — single call for everything the agent needs on a token
# ─────────────────────────────────────────────────────────────────────────────

def get_full_nansen_signal(
    token_address: str,
    token_symbol: str = "",
) -> Dict[str, Any]:
    """
    Aggregate all Nansen signals for a single token into one dict.
    The agent receives this as a rich context block.

    Combines:
      - token_information (social links, market data)
      - smart_money_holders (who holds it, concentration)
      - flow_intelligence (accumulation vs distribution)
      - smart_money_dex_trades (recent activity)
      - nansen_indicators (risk/reward scores)

    Returns empty sub-dicts if a call fails — never raises.
    """
    if not _is_available():
        return {
            "available": False,
            "reason": "NANSEN_API_KEY not configured",
            "token_address": token_address,
        }

    logger.info(f"Fetching full Nansen signal for {token_symbol or token_address[:8]}...")

    token_info = get_token_information(token_address)
    sm_holders = get_smart_money_holders(token_address, limit=10)
    flow_intel = get_flow_intelligence(token_address, timeframe="1h")
    sm_trades = get_smart_money_dex_trades(token_address, hours_back=6, limit=10)
    indicators = get_nansen_indicators(token_address)

    # Summarise smart money holder count + total value
    sm_holder_count = len(sm_holders)
    sm_total_value_usd = sum(float(h.get("value_usd") or 0) for h in sm_holders)

    # Net smart money flow direction
    smart_trader_flow = 0.0
    if isinstance(flow_intel, dict) and "smart_traders" in flow_intel:
        smart_trader_flow = float(flow_intel["smart_traders"].get("net_flow_usd") or 0)
    whale_flow = 0.0
    if isinstance(flow_intel, dict) and "whales" in flow_intel:
        whale_flow = float(flow_intel["whales"].get("net_flow_usd") or 0)

    # Recent smart money buy vs sell count
    sm_buys = sum(1 for t in sm_trades if str(t.get("action", "")).upper() == "BUY")
    sm_sells = sum(1 for t in sm_trades if str(t.get("action", "")).upper() == "SELL")

    return {
        "available": True,
        "token_address": token_address,
        "token_symbol": token_symbol,
        "timestamp": datetime.now(timezone.utc).isoformat(),

        # Social / metadata
        "token_information": token_info,

        # Smart money holders
        "smart_money_holders": sm_holders,
        "smart_money_holder_count": sm_holder_count,
        "smart_money_total_value_usd": sm_total_value_usd,

        # Flow intelligence summary
        "flow_intelligence_raw": flow_intel,
        "smart_trader_net_flow_usd": smart_trader_flow,
        "whale_net_flow_usd": whale_flow,
        "smart_money_accumulating": (smart_trader_flow + whale_flow) > 0,

        # Recent DEX activity summary
        "recent_smart_money_trades": sm_trades,
        "sm_buys_last_6h": sm_buys,
        "sm_sells_last_6h": sm_sells,
        "sm_buy_pressure": (sm_buys / max(sm_buys + sm_sells, 1)),

        # Risk/reward indicators
        "nansen_indicators": indicators,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 9. HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

def check_nansen_health() -> Dict[str, Any]:
    """Verify Nansen API key is set and reachable."""
    if not _is_available():
        return {"healthy": False, "reason": "NANSEN_API_KEY not set"}
    try:
        # Lightweight call — 3-token screener to verify auth
        payload = {
            "chains": ["solana"],
            "timeframe": "24h",
            "filters": {"only_smart_money": True, "token_age_days": {"min": 1, "max": 30}},
            "order_by": [{"field": "buy_volume", "direction": "DESC"}],
            "pagination": {"page": 1, "per_page": 1},
        }
        result = _post("/token-screener", payload)
        if result is not None:
            return {"healthy": True, "endpoint": "token-screener", "timestamp": datetime.now().isoformat()}
        return {"healthy": False, "reason": "No response from Nansen API"}
    except Exception as e:
        return {"healthy": False, "reason": str(e)}

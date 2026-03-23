# src/data/historical_data.py
"""
Historical OHLCV data fetcher for backtesting.

Primary source: DexPaprika (free, no API key required)
Fallback: GeckoTerminal (free tier, 30 req/min)

Results are cached in the PostgreSQL backtest_ohlcv_cache table.
"""
import logging
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger("trading_agent.historical_data")

_DEXPAPRIKA_BASE = "https://api.dexpaprika.com"
_GECKOTERM_BASE = "https://api.geckoterminal.com/api/v2"

_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json", "User-Agent": "lambda-trading-bot/1.0"})

# Simple in-memory TTL cache to avoid repeated DB lookups within the same process run
_mem_cache: dict[str, tuple[list, float]] = {}
_MEM_CACHE_TTL = 3600  # 1 hour


def _mem_cache_key(token_address: str, days_back: int, interval_minutes: int) -> str:
    return f"{token_address}:{days_back}:{interval_minutes}"


def _fetch_dexpaprika(token_address: str, start_ts: int, end_ts: int, interval_minutes: int) -> list[dict]:
    """Fetch OHLCV from DexPaprika. Returns list of candle dicts or []."""
    try:
        # Step 1: get pool id for this token
        pools_url = f"{_DEXPAPRIKA_BASE}/networks/solana/tokens/{token_address}/pools"
        resp = _SESSION.get(pools_url, timeout=15)
        if resp.status_code != 200:
            logger.debug(f"DexPaprika pools lookup failed: {resp.status_code}")
            return []

        pools_data = resp.json()
        # pools_data may be a list or {"pools": [...]}
        if isinstance(pools_data, dict):
            pools = pools_data.get("pools", [])
        else:
            pools = pools_data

        if not pools:
            logger.debug(f"DexPaprika: no pools found for {token_address}")
            return []

        pool_id = pools[0].get("id") or pools[0].get("pool_id")
        if not pool_id:
            return []

        # Step 2: fetch OHLCV with pagination
        interval_str = f"{interval_minutes}m"
        all_candles: list[dict] = []
        current_start = start_ts

        while current_start < end_ts:
            ohlcv_url = (
                f"{_DEXPAPRIKA_BASE}/networks/solana/pools/{pool_id}/ohlcv"
                f"?start={current_start}&end={end_ts}&interval={interval_str}&limit=366"
            )
            resp = _SESSION.get(ohlcv_url, timeout=15)
            if resp.status_code != 200:
                logger.debug(f"DexPaprika OHLCV failed: {resp.status_code}")
                break

            data = resp.json()
            # data may be list or {"ohlcv": [...]}
            if isinstance(data, dict):
                candle_list = data.get("ohlcv", data.get("data", []))
            else:
                candle_list = data

            if not candle_list:
                break

            for c in candle_list:
                ts = c.get("time_open") or c.get("timestamp") or c.get("time")
                if ts is None:
                    continue
                all_candles.append({
                    "timestamp": int(ts),
                    "open": float(c.get("open", 0)),
                    "high": float(c.get("high", 0)),
                    "low": float(c.get("low", 0)),
                    "close": float(c.get("close", 0)),
                    "volume_usd": float(c.get("volume", c.get("volume_usd", 0))),
                })

            # Advance start to avoid re-fetching
            last_ts = all_candles[-1]["timestamp"] if all_candles else end_ts
            if last_ts <= current_start:
                break
            current_start = last_ts + interval_minutes * 60
            time.sleep(0.1)  # be polite

        return all_candles

    except Exception as e:
        logger.warning(f"DexPaprika fetch error for {token_address}: {e}")
        return []


def _fetch_geckoterm(token_address: str, start_ts: int, end_ts: int, interval_minutes: int) -> list[dict]:
    """Fetch OHLCV from GeckoTerminal. Returns list of candle dicts or []."""
    try:
        # Step 1: find pool address
        pools_url = f"{_GECKOTERM_BASE}/networks/solana/tokens/{token_address}/pools"
        resp = _SESSION.get(pools_url, timeout=15)
        if resp.status_code != 200:
            logger.debug(f"GeckoTerminal pools lookup failed: {resp.status_code}")
            return []

        pools_json = resp.json()
        pool_items = pools_json.get("data", [])
        if not pool_items:
            logger.debug(f"GeckoTerminal: no pools for {token_address}")
            return []

        pool_address = pool_items[0].get("attributes", {}).get("address") or pool_items[0].get("id", "").split("_")[-1]
        if not pool_address:
            return []

        # Step 2: paginate backwards from end_ts
        # GeckoTerminal supports: /ohlcv/{timeframe} where timeframe = "minute"
        # with aggregate=5, limit=1000, before_timestamp=<unix>
        all_candles: list[dict] = []
        before_ts = end_ts

        while before_ts > start_ts:
            ohlcv_url = (
                f"{_GECKOTERM_BASE}/networks/solana/pools/{pool_address}/ohlcv/minute"
                f"?aggregate={interval_minutes}&limit=1000&before_timestamp={before_ts}&currency=usd"
            )
            resp = _SESSION.get(ohlcv_url, timeout=15)
            if resp.status_code == 429:
                logger.debug("GeckoTerminal rate limited, sleeping 2s")
                time.sleep(2)
                continue
            if resp.status_code != 200:
                logger.debug(f"GeckoTerminal OHLCV failed: {resp.status_code}")
                break

            attrs = resp.json().get("data", {}).get("attributes", {})
            raw_list = attrs.get("ohlcv_list", [])
            if not raw_list:
                break

            batch: list[dict] = []
            for row in raw_list:
                # row = [ts, open, high, low, close, volume]
                if len(row) < 6:
                    continue
                ts_val = int(row[0])
                if ts_val < start_ts:
                    continue
                batch.append({
                    "timestamp": ts_val,
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume_usd": float(row[5]),
                })

            if not batch:
                break

            all_candles.extend(batch)
            earliest = min(c["timestamp"] for c in batch)
            if earliest <= start_ts:
                break
            before_ts = earliest - 1
            time.sleep(0.1)

        # Sort ascending
        all_candles.sort(key=lambda c: c["timestamp"])
        return all_candles

    except Exception as e:
        logger.warning(f"GeckoTerminal fetch error for {token_address}: {e}")
        return []


def _load_from_db_cache(token_address: str, interval_minutes: int, start_ts: int, end_ts: int) -> list[dict]:
    """Load cached OHLCV from PostgreSQL. Returns [] if DB unavailable or no data."""
    try:
        from src.db.backtest_store import get_cached_ohlcv
        return get_cached_ohlcv(token_address, interval_minutes, start_ts, end_ts)
    except Exception as e:
        logger.debug(f"DB cache load failed: {e}")
        return []


def _save_to_db_cache(token_address: str, interval_minutes: int, candles: list[dict]) -> None:
    """Persist fetched OHLCV to PostgreSQL cache (best-effort)."""
    try:
        from src.db.backtest_store import cache_ohlcv
        cache_ohlcv(token_address, interval_minutes, candles)
    except Exception as e:
        logger.debug(f"DB cache save failed: {e}")


def fetch_ohlcv(
    token_address: str,
    days_back: int = 30,
    interval_minutes: int = 5,
) -> list[dict]:
    """
    Fetch historical OHLCV candles for a Solana token.

    Returns list of dicts:
        {"timestamp": int, "open": float, "high": float,
         "low": float, "close": float, "volume_usd": float}

    Lookup order:
        1. In-memory TTL cache (1 hour)
        2. PostgreSQL backtest_ohlcv_cache
        3. DexPaprika API
        4. GeckoTerminal API (fallback)
    """
    cache_key = _mem_cache_key(token_address, days_back, interval_minutes)
    now = time.time()

    # 1. In-memory cache
    if cache_key in _mem_cache:
        data, cached_at = _mem_cache[cache_key]
        if now - cached_at < _MEM_CACHE_TTL:
            return data

    end_ts = int(now)
    start_ts = end_ts - days_back * 86400

    # 2. DB cache
    db_candles = _load_from_db_cache(token_address, interval_minutes, start_ts, end_ts)
    if len(db_candles) > 10:
        _mem_cache[cache_key] = (db_candles, now)
        return db_candles

    # 3. DexPaprika
    logger.info(f"Fetching OHLCV from DexPaprika for {token_address} ({days_back}d)")
    candles = _fetch_dexpaprika(token_address, start_ts, end_ts, interval_minutes)

    # 4. Fallback to GeckoTerminal
    if len(candles) < 10:
        logger.info(f"DexPaprika returned {len(candles)} candles, trying GeckoTerminal")
        candles = _fetch_geckoterm(token_address, start_ts, end_ts, interval_minutes)

    if candles:
        _save_to_db_cache(token_address, interval_minutes, candles)
        _mem_cache[cache_key] = (candles, now)
        logger.info(f"Fetched {len(candles)} candles for {token_address}")
    else:
        logger.warning(f"No OHLCV data found for {token_address}")

    return candles


def get_ohlcv_summary(candles: list[dict]) -> dict:
    """Return a brief summary dict for agent tool output."""
    if not candles:
        return {"candle_count": 0, "error": "no data"}

    timestamps = [c["timestamp"] for c in candles]
    closes = [c["close"] for c in candles]
    volumes = [c["volume_usd"] for c in candles]

    return {
        "candle_count": len(candles),
        "date_start": datetime.fromtimestamp(min(timestamps), tz=timezone.utc).isoformat(),
        "date_end": datetime.fromtimestamp(max(timestamps), tz=timezone.utc).isoformat(),
        "price_min": round(min(closes), 8),
        "price_max": round(max(closes), 8),
        "price_latest": round(closes[-1], 8),
        "total_volume_usd": round(sum(volumes), 2),
        "avg_volume_per_candle_usd": round(sum(volumes) / len(volumes), 2),
    }

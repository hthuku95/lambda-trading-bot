# tests/test_dexscreener.py
"""
Tests for src/data/dexscreener.py

process_pair_data() is a pure transformation function — it is tested with real
data fetched from DexScreener (BONK token).

make_api_call() retry logic is tested with mocked HTTP errors (these test code
behavior, not market data — you cannot reliably trigger 429/500 from a real API).
"""
import pytest
import requests
from unittest.mock import patch, MagicMock
from src.data.dexscreener import process_pair_data, make_api_call

BONK_ADDRESS = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"


# ─────────────────────────────────────────────────────────────────────────────
# Real DexScreener pair data (session-scoped — one API call per run)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def real_pair_raw():
    """Fetches the raw DexScreener API response for BONK and returns the first pair dict."""
    import requests as req
    resp = req.get(
        f"https://api.dexscreener.com/latest/dex/tokens/{BONK_ADDRESS}",
        timeout=15,
    )
    assert resp.status_code == 200, "DexScreener API must respond with 200"
    data = resp.json()
    raw_pairs = data.get("pairs") or []
    assert raw_pairs, "DexScreener must return raw pair data for BONK"
    return raw_pairs[0]


@pytest.fixture(scope="session")
def processed_bonk(real_pair_raw):
    """Pre-processed BONK pair for structure and type assertions."""
    return process_pair_data(real_pair_raw)


# ─────────────────────────────────────────────────────────────────────────────
# process_pair_data() — real data structural tests
# ─────────────────────────────────────────────────────────────────────────────

def test_process_pair_data_core_fields(processed_bonk):
    """Core identification fields must be non-empty strings."""
    assert isinstance(processed_bonk["address"], str) and processed_bonk["address"]
    assert isinstance(processed_bonk["symbol"], str) and processed_bonk["symbol"]
    assert isinstance(processed_bonk["pair_address"], str) and processed_bonk["pair_address"]
    assert isinstance(processed_bonk["chain_id"], str) and processed_bonk["chain_id"]


def test_process_pair_data_numeric_fields(processed_bonk):
    """Numeric fields must be floats and non-negative."""
    for field in ("price_usd", "liquidity_usd", "volume_24h"):
        assert isinstance(processed_bonk[field], float), f"{field} must be float"
        assert processed_bonk[field] >= 0.0, f"{field} must be >= 0"


def test_process_pair_data_price_positive(processed_bonk):
    """BONK must have a real price > 0."""
    assert processed_bonk["price_usd"] > 0.0


def test_process_pair_data_age_calculation(processed_bonk):
    """Token age must be a non-negative float (BONK is over a year old)."""
    assert isinstance(processed_bonk["age_hours"], float)
    assert processed_bonk["age_hours"] >= 0.0


def test_process_pair_data_transaction_aggregation(processed_bonk):
    """buy_count, sell_count, and buy_ratio must be sensible."""
    assert isinstance(processed_bonk["buy_count"], int)
    assert isinstance(processed_bonk["sell_count"], int)
    assert processed_bonk["buy_count"] >= 0
    assert processed_bonk["sell_count"] >= 0
    assert 0.0 <= processed_bonk["buy_ratio"] <= 1.0


def test_process_pair_data_placeholders(processed_bonk):
    """AI analysis placeholders must be present and empty (filled in by agent layer)."""
    assert "safety_raw_data" in processed_bonk
    assert "social_raw_data" in processed_bonk
    assert processed_bonk["ai_overall_score"] == 0
    assert processed_bonk["ai_recommendation"] == ""


def test_process_pair_data_liquidity_components(processed_bonk):
    """Liquidity base and quote must be present as floats >= 0."""
    assert isinstance(processed_bonk["liquidity_base"], float)
    assert isinstance(processed_bonk["liquidity_quote"], float)
    assert processed_bonk["liquidity_base"] >= 0.0
    assert processed_bonk["liquidity_quote"] >= 0.0


def test_process_pair_data_price_change_fields(processed_bonk):
    """Price change fields must be floats (negative changes are valid)."""
    for field in ("price_change_5m", "price_change_1h", "price_change_24h"):
        assert isinstance(processed_bonk[field], float), f"{field} must be float"


# ─────────────────────────────────────────────────────────────────────────────
# process_pair_data() — edge cases with minimal input
# ─────────────────────────────────────────────────────────────────────────────

def test_process_pair_data_with_missing_fields():
    """The function must handle incomplete data gracefully."""
    incomplete_data = {
        "chainId": "solana",
        "pairAddress": "h1z2y3x4",
        "baseToken": {
            "address": "So11111111111111111111111111111111111111112",
            "symbol": "SOL",
        },
    }
    try:
        processed = process_pair_data(incomplete_data)
        assert processed["price_usd"] == 0.0
        assert processed["liquidity_usd"] == 0.0
        assert processed["volume_24h"] == 0.0
        assert processed["buy_count"] == 0
        assert processed["age_hours"] == 0
    except Exception as e:
        pytest.fail(f"process_pair_data raised an exception with incomplete data: {e}")


def test_process_pair_data_buy_ratio_default_with_no_transactions():
    """No transactions → buy_ratio defaults to 0.5 (neutral)."""
    data = {
        "chainId": "solana",
        "pairAddress": "abc",
        "baseToken": {"address": "abc", "symbol": "TKN"},
        "txns": {},
    }
    processed = process_pair_data(data)
    assert processed["buy_ratio"] == pytest.approx(0.5)


def test_process_pair_data_all_buy_sell_timeframes_aggregated():
    """buy_count and sell_count must sum over all timeframes."""
    data = {
        "chainId": "solana",
        "pairAddress": "abc",
        "baseToken": {"address": "abc", "symbol": "TKN"},
        "txns": {
            "m5":  {"buys": 10, "sells": 5},
            "h1":  {"buys": 20, "sells": 10},
            "h6":  {"buys": 30, "sells": 15},
            "h24": {"buys": 40, "sells": 20},
        },
    }
    processed = process_pair_data(data)
    assert processed["buy_count"] == 100
    assert processed["sell_count"] == 50


def test_process_pair_data_age_hours_zero_when_pairCreatedAt_missing():
    data = {
        "chainId": "solana",
        "pairAddress": "abc",
        "baseToken": {"address": "abc", "symbol": "TKN"},
    }
    processed = process_pair_data(data)
    assert processed["age_hours"] == 0


def test_process_pair_data_priceUsd_string_cast_to_float():
    data = {
        "chainId": "solana",
        "pairAddress": "abc",
        "baseToken": {"address": "abc", "symbol": "TKN"},
        "priceUsd": "99.99",
    }
    processed = process_pair_data(data)
    assert isinstance(processed["price_usd"], float)
    assert processed["price_usd"] == pytest.approx(99.99)


# ─────────────────────────────────────────────────────────────────────────────
# make_api_call() — retry logic and error handling (mocked HTTP)
# ─────────────────────────────────────────────────────────────────────────────

class TestMakeApiCall:
    def _mock_response(self, status_code=200, json_data=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {"data": "ok"}
        if status_code >= 400:
            resp.raise_for_status.side_effect = requests.HTTPError(
                f"HTTP {status_code}", response=resp
            )
        else:
            resp.raise_for_status.return_value = None
        return resp

    def test_returns_json_on_success(self):
        good = self._mock_response(200, {"pairs": []})
        with patch("requests.get", return_value=good), patch("time.sleep"):
            result = make_api_call("https://api.test.com/endpoint")
        assert result == {"pairs": []}

    def test_returns_none_when_all_retries_fail(self):
        bad = self._mock_response(500)
        with patch("requests.get", return_value=bad), patch("time.sleep"):
            result = make_api_call("https://api.test.com/fail", max_retries=3)
        assert result is None

    def test_retries_on_429_rate_limit(self):
        rate_limited = self._mock_response(429)
        success = self._mock_response(200, {"ok": True})
        responses = [rate_limited, rate_limited, success]
        with patch("requests.get", side_effect=responses), \
             patch("time.sleep") as mock_sleep:
            result = make_api_call("https://api.test.com/limited", max_retries=3)
        assert result == {"ok": True}
        assert mock_sleep.call_count >= 1

    def test_returns_none_on_connection_error(self):
        with patch("requests.get", side_effect=requests.ConnectionError("no network")), \
             patch("time.sleep"):
            result = make_api_call("https://api.test.com/gone", max_retries=2)
        assert result is None

    def test_sleeps_between_retries_on_error(self):
        bad = self._mock_response(500)
        with patch("requests.get", return_value=bad), \
             patch("time.sleep") as mock_sleep:
            make_api_call("https://api.test.com/retry", max_retries=3)
        assert mock_sleep.call_count >= 1

    def test_respects_max_retries_parameter(self):
        """With max_retries=1 it must call requests.get exactly once."""
        bad = self._mock_response(500)
        with patch("requests.get", return_value=bad) as mock_get, patch("time.sleep"):
            make_api_call("https://api.test.com/once", max_retries=1)
        assert mock_get.call_count == 1

    def test_returns_none_on_timeout(self):
        with patch("requests.get", side_effect=requests.Timeout("timed out")), \
             patch("time.sleep"):
            result = make_api_call("https://api.test.com/slow", max_retries=2)
        assert result is None

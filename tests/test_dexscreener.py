
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
import requests
from src.data.dexscreener import process_pair_data, make_api_call

@pytest.fixture
def sample_pair_data():
    """Provides a sample raw pair data from DexScreener API."""
    return {
        "chainId": "solana",
        "dexId": "raydium",
        "url": "https://dexscreener.com/solana/h1z2y3x4",
        "pairAddress": "h1z2y3x4",
        "baseToken": {
            "address": "So11111111111111111111111111111111111111112",
            "name": "Wrapped SOL",
            "symbol": "SOL"
        },
        "quoteToken": {
            "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "name": "USD Coin",
            "symbol": "USDC"
        },
        "priceUsd": "140.5",
        "txns": {
            "m5": {"buys": 10, "sells": 5},
            "h1": {"buys": 100, "sells": 80},
            "h24": {"buys": 1200, "sells": 1100}
        },
        "volume": {
            "h24": 50000000,
            "h1": 2000000,
            "m5": 50000
        },
        "priceChange": {
            "m5": 0.1,
            "h1": -1.5,
            "h24": 5.2
        },
        "liquidity": {"usd": 25000000, "base": 177935, "quote": 25000000},
        "pairCreatedAt": (datetime.now() - timedelta(days=365)).timestamp() * 1000,
        "marketCap": 65000000000,
        "fdv": 75000000000,
        "labels": ["Raydium", "Stablecoin Pair"],
        "boosts": {"active": 2}
    }

def test_process_pair_data_core_fields(sample_pair_data):
    """Tests that core identification fields are processed correctly."""
    processed = process_pair_data(sample_pair_data)
    assert processed["address"] == "So11111111111111111111111111111111111111112"
    assert processed["symbol"] == "SOL"
    assert processed["name"] == "Wrapped SOL"
    assert processed["pair_address"] == "h1z2y3x4"
    assert processed["dex_id"] == "raydium"
    assert processed["chain_id"] == "solana"

def test_process_pair_data_numeric_fields(sample_pair_data):
    """Tests that numeric fields like price, volume, and liquidity are correctly cast to float."""
    processed = process_pair_data(sample_pair_data)
    assert isinstance(processed["price_usd"], float)
    assert processed["price_usd"] == 140.5
    assert isinstance(processed["liquidity_usd"], float)
    assert processed["liquidity_usd"] == 25000000
    assert isinstance(processed["volume_24h"], float)
    assert processed["volume_24h"] == 50000000
    assert isinstance(processed["market_cap"], float)
    assert processed["market_cap"] == 65000000000

def test_process_pair_data_age_calculation(sample_pair_data):
    """Tests that the token age is calculated correctly in hours."""
    processed = process_pair_data(sample_pair_data)
    assert "age_hours" in processed
    assert isinstance(processed["age_hours"], float)
    # Approximately 1 year in hours
    assert 364 * 24 < processed["age_hours"] < 366 * 24

def test_process_pair_data_transaction_aggregation(sample_pair_data):
    """Tests that buy/sell counts and ratios are aggregated correctly."""
    processed = process_pair_data(sample_pair_data)
    assert processed["buy_count"] == 10 + 100 + 1200
    assert processed["sell_count"] == 5 + 80 + 1100
    total_txns = 1310 + 1185
    assert processed["total_transactions"] == total_txns
    assert processed["buy_ratio"] == pytest.approx(1310 / total_txns)

def test_process_pair_data_placeholders(sample_pair_data):
    """Tests that placeholders for AI analysis and other data sources are present and empty."""
    processed = process_pair_data(sample_pair_data)
    assert "safety_raw_data" in processed and processed["safety_raw_data"] == {}
    assert "social_raw_data" in processed and processed["social_raw_data"] == {}
    assert "ai_overall_score" in processed and processed["ai_overall_score"] == 0
    assert "ai_recommendation" in processed and processed["ai_recommendation"] == ""

def test_process_pair_data_with_missing_fields():
    """Tests that the function handles incomplete data gracefully without errors."""
    incomplete_data = {
        "chainId": "solana",
        "pairAddress": "h1z2y3x4",
        "baseToken": {
            "address": "So11111111111111111111111111111111111111112",
            "symbol": "SOL"
        }
        # Many fields are missing
    }
    try:
        processed = process_pair_data(incomplete_data)
        # Check that essential fields have default values
        assert processed["price_usd"] == 0.0
        assert processed["liquidity_usd"] == 0.0
        assert processed["volume_24h"] == 0.0
        assert processed["buy_count"] == 0
        assert processed["age_hours"] == 0
    except Exception as e:
        pytest.fail(f"process_pair_data raised an exception with incomplete data: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# make_api_call() — retry logic and error handling
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
        with patch("requests.get", return_value=good), \
             patch("time.sleep"):
            result = make_api_call("https://api.test.com/endpoint")
        assert result == {"pairs": []}

    def test_returns_none_when_all_retries_fail(self):
        bad = self._mock_response(500)
        with patch("requests.get", return_value=bad), \
             patch("time.sleep"):
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
        # Must have slept at least once during the rate-limit retries
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
        # Should sleep between non-last retries (max_retries-1 times)
        assert mock_sleep.call_count >= 1

    def test_respects_max_retries_parameter(self):
        """With max_retries=1 it must call requests.get exactly once."""
        bad = self._mock_response(500)
        with patch("requests.get", return_value=bad) as mock_get, \
             patch("time.sleep"):
            make_api_call("https://api.test.com/once", max_retries=1)
        assert mock_get.call_count == 1

    def test_returns_none_on_timeout(self):
        with patch("requests.get", side_effect=requests.Timeout("timed out")), \
             patch("time.sleep"):
            result = make_api_call("https://api.test.com/slow", max_retries=2)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# process_pair_data() — additional edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestProcessPairDataAdditional:
    def test_liquidity_base_and_quote_extracted(self, sample_pair_data):
        processed = process_pair_data(sample_pair_data)
        assert processed["liquidity_base"] == pytest.approx(177935.0)
        assert processed["liquidity_quote"] == pytest.approx(25000000.0)

    def test_boosts_active_extracted(self, sample_pair_data):
        processed = process_pair_data(sample_pair_data)
        assert processed["boosts_active"] == 2

    def test_labels_preserved(self, sample_pair_data):
        processed = process_pair_data(sample_pair_data)
        assert isinstance(processed["labels"], list)
        assert len(processed["labels"]) == 2

    def test_price_change_fields_present(self, sample_pair_data):
        processed = process_pair_data(sample_pair_data)
        assert processed["price_change_5m"] == pytest.approx(0.1)
        assert processed["price_change_1h"] == pytest.approx(-1.5)
        assert processed["price_change_24h"] == pytest.approx(5.2)

    def test_buy_ratio_is_zero_point_five_when_no_transactions(self):
        """No transactions → buy_ratio defaults to 0.5 (neutral)."""
        data = {
            "chainId": "solana",
            "pairAddress": "abc",
            "baseToken": {"address": "abc", "symbol": "TKN"},
            "txns": {},
        }
        processed = process_pair_data(data)
        assert processed["buy_ratio"] == pytest.approx(0.5)

    def test_all_buy_sell_timeframes_aggregated(self):
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

    def test_buyers_5m_and_sellers_5m_extracted(self, sample_pair_data):
        """buyers_5m / sellers_5m come from the m5 timeframe."""
        sample_pair_data["txns"]["m5"]["buyers"] = 7
        sample_pair_data["txns"]["m5"]["sellers"] = 3
        processed = process_pair_data(sample_pair_data)
        assert processed["buyers_5m"] == 7
        assert processed["sellers_5m"] == 3

    def test_age_hours_zero_when_pairCreatedAt_missing(self):
        data = {
            "chainId": "solana",
            "pairAddress": "abc",
            "baseToken": {"address": "abc", "symbol": "TKN"},
        }
        processed = process_pair_data(data)
        assert processed["age_hours"] == 0

    def test_priceUsd_string_cast_to_float(self, sample_pair_data):
        sample_pair_data["priceUsd"] = "99.99"
        processed = process_pair_data(sample_pair_data)
        assert isinstance(processed["price_usd"], float)
        assert processed["price_usd"] == pytest.approx(99.99)

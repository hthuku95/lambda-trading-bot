# tests/test_sol_price.py
"""
Tests for src/data/sol_price.py

All HTTP calls to CoinGecko are mocked.
Caching logic is tested by manipulating the module-level _CACHE dict.
"""
import time
import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _reset_cache():
    import src.data.sol_price as sp
    sp._CACHE["price"] = None
    sp._CACHE["timestamp"] = 0.0


def _set_cache(price: float, age_seconds: float = 0.0):
    import src.data.sol_price as sp
    sp._CACHE["price"] = price
    sp._CACHE["timestamp"] = time.time() - age_seconds


# ─────────────────────────────────────────────────────────────────────────────
# get_sol_price_usd()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetSolPriceUsd:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _reset_cache()
        yield
        _reset_cache()

    def _mock_coingecko(self, price=150.0):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"solana": {"usd": price}}
        return mock_resp

    def test_returns_float_price_on_success(self):
        with patch("requests.get", return_value=self._mock_coingecko(150.0)):
            from src.data.sol_price import get_sol_price_usd
            price = get_sol_price_usd()
        assert isinstance(price, float)
        assert price == 150.0

    def test_updates_cache_after_successful_fetch(self):
        with patch("requests.get", return_value=self._mock_coingecko(180.0)):
            from src.data.sol_price import get_sol_price_usd
            get_sol_price_usd()
        import src.data.sol_price as sp
        assert sp._CACHE["price"] == 180.0
        assert sp._CACHE["timestamp"] > 0

    def test_uses_cache_when_fresh(self):
        """Second call within 60s must NOT hit the network."""
        _set_cache(price=120.0, age_seconds=5)  # 5s old — still fresh
        with patch("requests.get") as mock_get:
            from src.data.sol_price import get_sol_price_usd
            price = get_sol_price_usd()
        mock_get.assert_not_called()
        assert price == 120.0

    def test_refetches_when_cache_stale(self):
        """Cache older than 60s must trigger a new HTTP call."""
        _set_cache(price=100.0, age_seconds=65)  # stale
        with patch("requests.get", return_value=self._mock_coingecko(200.0)) as mock_get:
            from src.data.sol_price import get_sol_price_usd
            price = get_sol_price_usd()
        mock_get.assert_called_once()
        assert price == 200.0

    def test_returns_stale_cache_when_api_fails(self):
        """If the API call fails, return the last known price (may be None)."""
        _set_cache(price=130.0, age_seconds=65)  # stale cache
        with patch("requests.get", side_effect=Exception("timeout")):
            from src.data.sol_price import get_sol_price_usd
            price = get_sol_price_usd()
        assert price == 130.0  # returns stale value

    def test_returns_none_when_no_cache_and_api_fails(self):
        _reset_cache()
        with patch("requests.get", side_effect=Exception("no internet")):
            from src.data.sol_price import get_sol_price_usd
            price = get_sol_price_usd()
        assert price is None

    def test_handles_http_error_response(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("429 Too Many Requests")
        with patch("requests.get", return_value=mock_resp):
            from src.data.sol_price import get_sol_price_usd
            price = get_sol_price_usd()
        assert price is None  # no stale cache, no price

    def test_handles_malformed_json(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {}  # missing "solana" key
        with patch("requests.get", return_value=mock_resp):
            from src.data.sol_price import get_sol_price_usd
            price = get_sol_price_usd()
        assert price is None  # KeyError caught → returns stale cache (None)

    def test_price_is_float_not_string(self):
        """CoinGecko returns numbers; function must return float."""
        with patch("requests.get", return_value=self._mock_coingecko(155.55)):
            from src.data.sol_price import get_sol_price_usd
            price = get_sol_price_usd()
        assert type(price) is float


# ─────────────────────────────────────────────────────────────────────────────
# sol_to_usd()
# ─────────────────────────────────────────────────────────────────────────────

class TestSolToUsd:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _reset_cache()
        yield
        _reset_cache()

    def test_converts_correctly(self):
        _set_cache(price=150.0, age_seconds=0)
        from src.data.sol_price import sol_to_usd
        result = sol_to_usd(2.0)
        assert result == 300.0

    def test_returns_zero_for_zero_sol(self):
        _set_cache(price=150.0, age_seconds=0)
        from src.data.sol_price import sol_to_usd
        assert sol_to_usd(0.0) == 0.0

    def test_returns_zero_when_price_unavailable(self):
        _reset_cache()
        with patch("requests.get", side_effect=Exception("no internet")):
            from src.data.sol_price import sol_to_usd
            result = sol_to_usd(5.0)
        assert result == 0.0

    def test_fractional_sol_amount(self):
        _set_cache(price=200.0, age_seconds=0)
        from src.data.sol_price import sol_to_usd
        result = sol_to_usd(0.05)
        assert abs(result - 10.0) < 0.0001

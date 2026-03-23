# tests/test_rugcheck_client.py
"""
Tests for src/data/rugcheck_client.py

Success-path tests call the real RugCheck API for USDC (always has data).
Error-handling tests mock HTTP responses (you cannot reliably trigger 429/500 from real APIs).
"""
import pytest
from unittest.mock import MagicMock, patch
from src.data.rugcheck_client import RugCheckClient

USDC_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


@pytest.fixture(scope="session")
def rugcheck_client():
    return RugCheckClient()


@pytest.fixture(scope="session")
def real_usdc_safety_data(rugcheck_client):
    """Real RugCheck safety data for USDC (session-scoped — one API call per run)."""
    data = rugcheck_client.get_token_safety_data_raw(USDC_ADDRESS)
    assert data is not None, "RugCheck must return data for USDC"
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Real API structural tests
# ─────────────────────────────────────────────────────────────────────────────

def test_real_data_available(real_usdc_safety_data):
    """RugCheck must report data_available=True for USDC."""
    assert real_usdc_safety_data["data_available"] is True


def test_real_data_token_address_matches(real_usdc_safety_data):
    assert real_usdc_safety_data["token_address"] == USDC_ADDRESS


def test_real_data_has_score_metrics(real_usdc_safety_data):
    """Score must be a number (int or float)."""
    assert "score_metrics" in real_usdc_safety_data
    raw_score = real_usdc_safety_data["score_metrics"]["raw_score"]
    assert isinstance(raw_score, (int, float))


def test_real_data_has_rugcheck_raw_response(real_usdc_safety_data):
    assert "rugcheck_raw_response" in real_usdc_safety_data


def test_real_data_holder_metrics_present(real_usdc_safety_data):
    """Holder metrics must be present; USDC always has holder data."""
    assert "holder_metrics" in real_usdc_safety_data
    metrics = real_usdc_safety_data["holder_metrics"]
    assert "top_1_holder_pct" in metrics


def test_real_data_security_fields_present(real_usdc_safety_data):
    assert "security_data" in real_usdc_safety_data
    sec = real_usdc_safety_data["security_data"]
    assert "mint_authority_present" in sec
    assert "freeze_authority_present" in sec


# ─────────────────────────────────────────────────────────────────────────────
# Error handling — mocked HTTP responses
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return RugCheckClient()


def _mock_get(status_code):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    return mock_response


def test_not_found_returns_data_unavailable(client):
    with patch('requests.Session.get', return_value=_mock_get(404)):
        data = client.get_token_safety_data_raw("NotFoundToken")
    assert data["data_available"] is False
    assert data["error"] == "Token not found in RugCheck database"


def test_rate_limit_returns_data_unavailable(client):
    with patch('requests.Session.get', return_value=_mock_get(429)):
        data = client.get_token_safety_data_raw("RateLimitedToken")
    assert data["data_available"] is False
    assert data["error"] == "Rate limit exceeded"


def test_server_error_returns_data_unavailable(client):
    with patch('requests.Session.get', return_value=_mock_get(500)):
        data = client.get_token_safety_data_raw("ApiErrorToken")
    assert data["data_available"] is False
    assert data["error"] == "API error: 500"


# ─────────────────────────────────────────────────────────────────────────────
# Helper method unit tests (pure logic, no network)
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_holder_metrics_no_holders(client):
    metrics = client._extract_holder_metrics([])
    assert metrics["data_available"] is False
    assert metrics["top_1_holder_pct"] == 0
    assert metrics["top_10_holders_pct"] == 0


def test_create_legacy_holder_analysis(client):
    holders = [
        {"address": "holder1", "pct": 25.0},
        {"address": "holder2", "pct": 10.0},
    ]
    legacy = client._create_legacy_holder_analysis(holders)
    assert legacy["analysis"] == "calculated"
    assert legacy["top_1_holder_pct"] == 25.0


def test_create_legacy_market_analysis(client):
    markets = [{"marketType": "AMM", "lp": {"lpLockedUSD": 10000}}]
    legacy = client._create_legacy_market_analysis(markets)
    assert legacy["analysis"] == "calculated"
    assert legacy["total_liquidity_usd"] == 10000


def test_create_legacy_security_analysis(client):
    response = {"mintAuthority": "some_address", "freezeAuthority": None}
    legacy = client._create_legacy_security_analysis(response)
    assert legacy["mint_authority_present"] is True
    assert legacy["freeze_authority_present"] is False


def test_create_legacy_lp_analysis(client):
    lockers = {"locker1": {"usdcLocked": 5000}}
    legacy = client._create_legacy_lp_analysis(lockers)
    assert legacy["analysis"] == "calculated"
    assert legacy["total_locked_usd"] == 5000
    assert legacy["locked"] is True

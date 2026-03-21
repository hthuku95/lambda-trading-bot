
import pytest
from unittest.mock import MagicMock, patch
from src.data.rugcheck_client import RugCheckClient

@pytest.fixture
def mock_requests_get():
    """Fixture to mock requests.get."""
    with patch('requests.Session.get') as mock_get:
        yield mock_get

@pytest.fixture
def rugcheck_client():
    """Returns an instance of the RugCheckClient."""
    return RugCheckClient()

@pytest.fixture
def sample_rugcheck_api_response():
    """Provides a sample raw API response from RugCheck."""
    return {
        "tokenMeta": {
            "name": "Test Token",
            "symbol": "TEST",
            "address": "TestTokenAddress"
        },
        "risks": [
            {"name": "High Risk", "value": "Yes", "score": 90}
        ],
        "score": 500,
        "markets": [
            {"marketType": "AMM", "lp": {"lpLockedUSD": 10000}}
        ],
        "topHolders": [
            {"address": "holder1", "pct": 25.0},
            {"address": "holder2", "pct": 10.0}
        ],
        "mintAuthority": "some_address",
        "freezeAuthority": None,
        "lockers": {
            "locker1": {"usdcLocked": 5000}
        }
    }

def test_get_token_safety_data_raw_success(rugcheck_client, mock_requests_get, sample_rugcheck_api_response):
    """Tests successful retrieval and processing of raw safety data."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_rugcheck_api_response
    mock_requests_get.return_value = mock_response

    token_address = "TestTokenAddress"
    data = rugcheck_client.get_token_safety_data_raw(token_address)

    assert data["data_available"] is True
    assert data["token_address"] == token_address
    assert "rugcheck_raw_response" in data
    assert data["score_metrics"]["raw_score"] == 500
    assert data["holder_metrics"]["top_1_holder_pct"] == 25.0
    assert data["market_metrics"]["total_liquidity_usd"] == 10000
    assert data["security_data"]["mint_authority_present"] is True
    assert data["lp_lock_data"]["total_locked_usd"] == 5000

def test_get_token_safety_data_raw_not_found(rugcheck_client, mock_requests_get):
    """Tests handling of a 404 Not Found error from the API."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_requests_get.return_value = mock_response

    token_address = "NotFoundToken"
    data = rugcheck_client.get_token_safety_data_raw(token_address)

    assert data["data_available"] is False
    assert data["error"] == "Token not found in RugCheck database"
    assert data["token_address"] == token_address

def test_get_token_safety_data_raw_rate_limit(rugcheck_client, mock_requests_get):
    """Tests handling of a 429 Rate Limit Exceeded error."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_requests_get.return_value = mock_response

    token_address = "RateLimitedToken"
    data = rugcheck_client.get_token_safety_data_raw(token_address)

    assert data["data_available"] is False
    assert data["error"] == "Rate limit exceeded"

def test_get_token_safety_data_raw_api_error(rugcheck_client, mock_requests_get):
    """Tests handling of a generic API error (e.g., 500)."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_requests_get.return_value = mock_response

    token_address = "ApiErrorToken"
    data = rugcheck_client.get_token_safety_data_raw(token_address)

    assert data["data_available"] is False
    assert data["error"] == "API error: 500"

def test_extract_holder_metrics_no_holders(rugcheck_client):
    """Tests that holder metrics are handled correctly when no holder data is present."""
    metrics = rugcheck_client._extract_holder_metrics([])
    assert metrics["data_available"] is False
    assert metrics["top_1_holder_pct"] == 0
    assert metrics["top_10_holders_pct"] == 0

def test_create_legacy_structures(rugcheck_client, sample_rugcheck_api_response):
    """Tests that legacy data structures are created for backward compatibility."""
    # Test legacy holder analysis
    legacy_holders = rugcheck_client._create_legacy_holder_analysis(sample_rugcheck_api_response["topHolders"])
    assert legacy_holders["analysis"] == "calculated"
    assert legacy_holders["top_1_holder_pct"] == 25.0

    # Test legacy market analysis
    legacy_markets = rugcheck_client._create_legacy_market_analysis(sample_rugcheck_api_response["markets"])
    assert legacy_markets["analysis"] == "calculated"
    assert legacy_markets["total_liquidity_usd"] == 10000

    # Test legacy security analysis
    legacy_security = rugcheck_client._create_legacy_security_analysis(sample_rugcheck_api_response)
    assert legacy_security["mint_authority_present"] is True
    assert legacy_security["freeze_authority_present"] is False

    # Test legacy LP analysis
    legacy_lp = rugcheck_client._create_legacy_lp_analysis(sample_rugcheck_api_response["lockers"])
    assert legacy_lp["analysis"] == "calculated"
    assert legacy_lp["total_locked_usd"] == 5000
    assert legacy_lp["locked"] is True

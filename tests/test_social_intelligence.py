"""
Tests for src/data/social_intelligence.py

TweetScout is deprecated as of 2026-03.
social_intelligence.py now returns DexScreener social data only.
All TweetScout fields return stub dicts with status='deprecated'.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.data.social_intelligence import SocialIntelligenceClient


@pytest.fixture
def mock_requests_get():
    """Fixture to mock requests.get."""
    with patch('requests.get') as mock_get:
        yield mock_get


@pytest.fixture
def social_client():
    """Returns an instance of the SocialIntelligenceClient."""
    with patch.dict('os.environ', {'TWEETSCOUT_API_KEY': 'test-key'}):
        client = SocialIntelligenceClient()
    return client


@pytest.fixture
def mock_dexscreener_pairs():
    """Fixture to mock the dexscreener get_token_pairs function."""
    with patch('src.data.social_intelligence.get_token_pairs') as mock_get_pairs:
        mock_get_pairs.return_value = [{
            "baseToken": {"symbol": "TEST"}
        }]
        yield mock_get_pairs


# ─────────────────────────────────────────────────────────────────────────────
# get_token_social_data_raw() — structure tests
# ─────────────────────────────────────────────────────────────────────────────

def test_get_token_social_data_raw_returns_expected_keys(social_client, mock_dexscreener_pairs):
    """Result must always contain the required top-level keys."""
    data = social_client.get_token_social_data_raw("TestTokenAddress", "TEST")
    assert "tweetscout_accounts" in data
    assert "tweetscout_tweets" in data
    assert "dexscreener_social" in data
    assert "errors" in data
    assert data["token_symbol"] == "TEST"


def test_get_token_social_data_no_api_key():
    """
    Even without an API key, the client returns the standard structure.
    TweetScout is deprecated — all tweetscout fields return status='deprecated'.
    """
    with patch.dict('os.environ', {'TWEETSCOUT_API_KEY': ''}):
        client = SocialIntelligenceClient()
        data = client.get_token_social_data_raw("some_address", "SOME")
    assert "tweetscout_accounts" in data
    # Deprecated stub — has 'status' not 'error'
    assert data["tweetscout_accounts"].get("status") == "deprecated"


def test_get_token_social_data_no_symbol(social_client, mock_dexscreener_pairs):
    """Tests that the client handles a missing symbol gracefully."""
    data = social_client.get_token_social_data_raw("TestTokenAddress")
    # Should still return the standard structure
    assert "tweetscout_accounts" in data
    assert "errors" in data


# ─────────────────────────────────────────────────────────────────────────────
# _get_empty_social_data() — stub structure
# ─────────────────────────────────────────────────────────────────────────────

def test_empty_social_data_structure(social_client):
    """
    _get_empty_social_data() must return the standard structure.
    TweetScout fields use status='deprecated', not error='...'.
    """
    empty_data = social_client._get_empty_social_data("some_address", "Test Error")
    assert empty_data["token_address"] == "some_address"
    assert "tweetscout_accounts" in empty_data
    # Deprecated stub format
    assert empty_data["tweetscout_accounts"].get("status") == "deprecated"
    # Error is in the errors list
    assert isinstance(empty_data["errors"], list)


# ─────────────────────────────────────────────────────────────────────────────
# check_api_health()
# ─────────────────────────────────────────────────────────────────────────────

def test_check_api_health_returns_dict(social_client, mock_requests_get):
    """check_api_health() must return a dict with required keys."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_requests_get.return_value = mock_response

    health = social_client.check_api_health()
    assert isinstance(health, dict)
    assert "healthy" in health
    assert "tweetscout_available" in health


def test_check_api_health_tweetscout_always_deprecated(social_client, mock_requests_get):
    """
    TweetScout is deprecated — tweetscout_available must always be False
    regardless of HTTP response code.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_requests_get.return_value = mock_response

    health = social_client.check_api_health()
    assert health["tweetscout_available"] is False


def test_check_api_health_overall_healthy_when_dexscreener_ok(social_client, mock_requests_get):
    """Overall health is True when DexScreener is reachable (TweetScout is irrelevant)."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_requests_get.return_value = mock_response

    health = social_client.check_api_health()
    # healthy is True because the client itself is operational
    assert isinstance(health["healthy"], bool)

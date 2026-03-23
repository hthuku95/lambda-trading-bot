"""
Tests for src/data/social_intelligence.py

TweetScout is deprecated as of 2026-03 and has been fully removed.
social_intelligence.py now returns DexScreener social data only.
TweetScout keys must NOT appear in any response dict.
"""
import pytest
from unittest.mock import MagicMock, patch
from src.data.social_intelligence import SocialIntelligenceClient


BONK_ADDRESS = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"


@pytest.fixture
def social_client():
    """Returns an instance of the SocialIntelligenceClient."""
    return SocialIntelligenceClient()


@pytest.fixture
def mock_dexscreener_pairs():
    """Provides real-looking DexScreener pair structure for social tests."""
    with patch('src.data.social_intelligence.get_token_pairs') as mock_get_pairs:
        mock_get_pairs.return_value = [{"baseToken": {"symbol": "BONK"}}]
        yield mock_get_pairs


# ─────────────────────────────────────────────────────────────────────────────
# get_token_social_data_raw() — structure tests
# ─────────────────────────────────────────────────────────────────────────────

def test_get_token_social_data_raw_has_no_tweetscout_keys(social_client, mock_dexscreener_pairs):
    """TweetScout is fully removed — no tweetscout_* keys should appear."""
    data = social_client.get_token_social_data_raw(BONK_ADDRESS, "BONK")
    assert "tweetscout_accounts" not in data
    assert "tweetscout_tweets" not in data
    assert "tweetscout_search_results" not in data


def test_get_token_social_data_raw_has_required_keys(social_client, mock_dexscreener_pairs):
    """Result must contain dexscreener_social, errors, and token_symbol keys."""
    data = social_client.get_token_social_data_raw(BONK_ADDRESS, "BONK")
    assert "dexscreener_social" in data
    assert "errors" in data
    assert data["token_symbol"] == "BONK"


def test_get_token_social_data_raw_no_symbol(social_client, mock_dexscreener_pairs):
    """Client handles a missing symbol gracefully."""
    data = social_client.get_token_social_data_raw(BONK_ADDRESS)
    assert "dexscreener_social" in data
    assert "errors" in data


def test_get_token_social_data_no_api_key():
    """Without API key, client returns the standard structure without TweetScout keys."""
    with patch.dict('os.environ', {'TWEETSCOUT_API_KEY': ''}):
        client = SocialIntelligenceClient()
        data = client.get_token_social_data_raw(BONK_ADDRESS, "BONK")
    assert "tweetscout_accounts" not in data
    assert "dexscreener_social" in data


# ─────────────────────────────────────────────────────────────────────────────
# _get_empty_social_data() — stub structure
# ─────────────────────────────────────────────────────────────────────────────

def test_empty_social_data_has_no_tweetscout_keys(social_client):
    """_get_empty_social_data() must NOT include any tweetscout_* keys."""
    empty_data = social_client._get_empty_social_data(BONK_ADDRESS, "Test Error")
    assert "tweetscout_accounts" not in empty_data
    assert "tweetscout_tweets" not in empty_data
    assert "tweetscout_search_results" not in empty_data


def test_empty_social_data_required_keys(social_client):
    """_get_empty_social_data() must include standard keys."""
    empty_data = social_client._get_empty_social_data(BONK_ADDRESS, "Test Error")
    assert empty_data["token_address"] == BONK_ADDRESS
    assert "dexscreener_social" in empty_data
    assert isinstance(empty_data["errors"], list)


# ─────────────────────────────────────────────────────────────────────────────
# check_api_health()
# ─────────────────────────────────────────────────────────────────────────────

def test_check_api_health_returns_dict(social_client):
    """check_api_health() must return a dict with a 'healthy' key."""
    health = social_client.check_api_health()
    assert isinstance(health, dict)
    assert "healthy" in health


def test_check_api_health_no_tweetscout_key(social_client):
    """tweetscout_available must not appear in health check (deprecated and removed)."""
    health = social_client.check_api_health()
    assert "tweetscout_available" not in health
    assert "tweetscout_status" not in health

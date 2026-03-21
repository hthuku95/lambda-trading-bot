

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
    # Ensure the client is initialized with a dummy API key for testing
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

def test_get_token_social_data_raw_success(social_client, mock_requests_get, mock_dexscreener_pairs):
    """Tests the successful aggregation of raw social data from all sources."""
    # Mock responses for all internal API calls
    mock_account_search = MagicMock()
    mock_account_search.status_code = 200
    mock_account_search.json.return_value = [{"username": "testuser"}]

    mock_account_info = MagicMock()
    mock_account_info.status_code = 200
    mock_account_info.json.return_value = {"name": "Test User"}

    mock_tweet_search = MagicMock()
    mock_tweet_search.status_code = 200
    mock_tweet_search.json.return_value = {"tweets": [{"text": "Hello $TEST"}]}
    
    mock_requests_get.side_effect = [
        mock_account_search,  # For account search
        mock_account_info,    # For account info
        MagicMock(status_code=200, json=lambda: {}), # For score
        MagicMock(status_code=200, json=lambda: {}), # For followers
        mock_tweet_search     # For tweet search
    ]

    token_address = "TestTokenAddress"
    token_symbol = "TEST"
    data = social_client.get_token_social_data_raw(token_address, token_symbol)

    assert "errors" in data and not data["errors"]
    assert "tweetscout_accounts" in data
    assert "tweetscout_tweets" in data
    assert "dexscreener_social" in data
    assert data["token_symbol"] == token_symbol

def test_get_token_social_data_no_api_key():
    """Tests that the client handles a missing API key gracefully."""
    with patch.dict('os.environ', {'TWEETSCOUT_API_KEY': ''}):
        client = SocialIntelligenceClient()
        data = client.get_token_social_data_raw("some_address", "SOME")
        assert "tweetscout_accounts" in data and data["tweetscout_accounts"]["error"] == "No API key"

def test_get_token_social_data_no_symbol(social_client, mock_dexscreener_pairs):
    """Tests that the client can fetch a symbol if it's not provided."""
    # This test relies on the mock_dexscreener_pairs fixture to provide the symbol
    with patch.object(social_client, '_get_tweetscout_accounts_raw', return_value={}) as mock_accounts, \
         patch.object(social_client, '_get_tweetscout_tweets_raw', return_value={}) as mock_tweets:
        
        social_client.get_token_social_data_raw("TestTokenAddress")
    
        # Verify that the symbol was fetched and used in subsequent calls
        mock_dexscreener_pairs.assert_called_once_with("solana", "TestTokenAddress")
        mock_accounts.assert_called_once_with("TEST")
        mock_tweets.assert_called_once_with("TEST")
        mock_accounts.assert_called_once_with("TEST")
        mock_tweets.assert_called_once_with("TEST")
        mock_accounts.assert_called_once_with("TEST")
        mock_tweets.assert_called_once_with("TEST")
        mock_accounts.assert_called_once_with("TEST")
        mock_tweets.assert_called_once_with("TEST")
        mock_accounts.assert_called_once_with("TEST")
        mock_tweets.assert_called_once_with("TEST")

def test_empty_social_data_structure(social_client):
    """Ensures the empty data structure has the correct format."""
    empty_data = social_client._get_empty_social_data("some_address", "Test Error")
    assert empty_data["token_address"] == "some_address"
    assert "Test Error" in empty_data["errors"]
    assert "tweetscout_accounts" in empty_data
    assert empty_data["tweetscout_accounts"]["error"] == "Test Error"

def test_check_api_health_success(social_client, mock_requests_get):
    """Tests a successful API health check."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_requests_get.return_value = mock_response

    health = social_client.check_api_health()
    assert health["healthy"] is True
    assert health["tweetscout_available"] is True
    assert health["tweetscout_available"] is True
    assert health["tweetscout_available"] is True
    assert health["tweetscout_available"] is True
    assert health["tweetscout_available"] is True

def test_check_api_health_failure(social_client, mock_requests_get):
    """Tests a failed API health check."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_requests_get.return_value = mock_response

    health = social_client.check_api_health()
    assert health["healthy"] is False
    assert health["tweetscout_available"] is False


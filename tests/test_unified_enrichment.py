import pytest
from unittest.mock import MagicMock, patch
from src.data.unified_enrichment import UnifiedTokenEnrichment

@pytest.fixture
def mock_data_sources():
    """Fixture to mock all underlying data source functions."""
    with patch('src.data.unified_enrichment.get_token_safety_data_raw') as mock_rugcheck, \
         patch('src.data.unified_enrichment.get_social_data_raw') as mock_social, \
         patch('src.data.unified_enrichment.get_token_pairs') as mock_dexscreener:
        
        # Configure default successful mock returns
        mock_rugcheck.return_value = {"data_available": True, "score_raw": 500}
        mock_social.return_value = {"tweetscout_accounts": {"total_accounts": 5}}
        mock_dexscreener.return_value = [{"baseToken": {"symbol": "TEST"}}]
        
        yield {
            "rugcheck": mock_rugcheck,
            "social": mock_social,
            "dexscreener": mock_dexscreener
        }

@pytest.fixture
def enrichment_client():
    """Returns an instance of the UnifiedTokenEnrichment client."""
    return UnifiedTokenEnrichment()

def test_get_comprehensive_raw_data_all_sources_succeed(enrichment_client, mock_data_sources):
    """
    Tests the successful aggregation of raw data when all sources are available.
    """
    token_address = "TestTokenAddress"
    data = enrichment_client.get_comprehensive_raw_data(token_address)

    # Verify that all mock functions were called
    mock_data_sources["rugcheck"].assert_called()
    mock_data_sources["social"].assert_called()
    mock_data_sources["dexscreener"].assert_called()

    # Verify that the final structure contains data from all sources
    assert "dexscreener_raw" in data and "error" not in data["dexscreener_raw"]
    assert "rugcheck_raw" in data and data["rugcheck_raw"]["data_available"]
    assert "tweetscout_raw" in data and "error" not in data["tweetscout_raw"]
    assert data["data_sources_status"]["rugcheck_success"] is True
    assert data["data_sources_status"]["tweetscout_success"] is True

def test_get_comprehensive_raw_data_partial_failure(enrichment_client, mock_data_sources):
    """
    Tests aggregation when some data sources fail.
    """
    # Simulate a failure in the RugCheck client
    mock_data_sources["rugcheck"].return_value = {"error": "API timeout", "data_available": False}

    token_address = "PartialFailureToken"
    data = enrichment_client.get_comprehensive_raw_data(token_address)

    # Verify that the final structure correctly reflects the partial failure
    assert "rugcheck_raw" in data and "error" in data["rugcheck_raw"]
    assert "tweetscout_raw" in data and "error" not in data["tweetscout_raw"] # Should still be successful
    assert data["data_sources_status"]["rugcheck_success"] is False
    assert data["data_sources_status"]["tweetscout_success"] is True
    assert "RugCheck data unavailable - safety analysis limited" in data["data_quality_notes"]

def test_get_comprehensive_raw_data_no_symbol(enrichment_client, mock_data_sources):
    """
    Tests that the symbol is fetched if not provided.
    """
    token_address = "NoSymbolToken"
    enrichment_client.get_comprehensive_raw_data(token_address)

    # The mock is configured to return "TEST" as the symbol
    mock_data_sources["social"].assert_called_with(token_address, "TEST")

def test_assess_data_quality(enrichment_client):
    """
    Tests the internal data quality assessment logic.
    """
    # Case 1: All data is present
    full_data = {
        "dexscreener_raw": {"pairs_raw": [{}]},
        "rugcheck_raw": {"data_available": True},
        "tweetscout_raw": {}
    }
    assessed_full = enrichment_client._assess_data_quality(full_data)
    assert assessed_full["data_quality_assessment"]["data_completeness"]["total_sources_available"] == 3
    assert not assessed_full["data_quality_notes"]

    # Case 2: RugCheck data is missing
    partial_data = {
        "dexscreener_raw": {"pairs_raw": [{}]},
        "rugcheck_raw": {"error": "Failed"},
        "tweetscout_raw": {}
    }
    assessed_partial = enrichment_client._assess_data_quality(partial_data)
    assert assessed_partial["data_quality_assessment"]["data_completeness"]["total_sources_available"] == 2
    assert "RugCheck data unavailable - safety analysis limited" in assessed_partial["data_quality_notes"]
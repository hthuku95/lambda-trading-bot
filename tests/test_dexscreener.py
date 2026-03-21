
import pytest
from datetime import datetime, timedelta
from src.data.dexscreener import process_pair_data

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


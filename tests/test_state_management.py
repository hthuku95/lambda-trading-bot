
import pytest
from datetime import datetime
from unittest.mock import patch
from src.agent.state import (
    create_initial_state,
    update_portfolio_metrics,
    validate_state_structure,
    migrate_legacy_state
)

def test_create_initial_state():
    """Tests that the initial state is created with all necessary default fields."""
    with patch('src.blockchain.solana_client.get_wallet_balance', return_value=100.0):
        state = create_initial_state()

    assert state["wallet_balance_sol"] == 100.0
    assert state["cycles_completed"] == 0
    assert state["active_positions"] == []
    assert "portfolio_metrics" in state
    assert "agent_parameters" in state
    assert validate_state_structure(state) is True

def test_update_portfolio_metrics():
    """Tests that portfolio metrics are correctly calculated and updated."""
    state = create_initial_state()
    state["wallet_balance_sol"] = 50.0
    state["active_positions"] = [
        {"current_value_sol": 25.0, "unrealized_pnl_sol": 5.0},
        {"current_value_sol": 30.0, "unrealized_pnl_sol": -2.0}
    ]
    state["transaction_history"] = [
        {"type": "sell", "profit_percentage": 10},
        {"type": "sell", "profit_percentage": -5},
        {"type": "sell", "profit_percentage": 20}
    ]

    updated_state = update_portfolio_metrics(state)

    assert updated_state["total_portfolio_value_sol"] == 50.0 + 25.0 + 30.0
    assert updated_state["portfolio_metrics"]["unrealized_profit_sol"] == pytest.approx(3.0)
    assert updated_state["win_rate"] == pytest.approx(2 / 3)

def test_validate_state_structure():
    """Tests the validation of the agent state structure."""
    valid_state = create_initial_state()
    assert validate_state_structure(valid_state) is True

    invalid_state = {"wallet_balance_sol": 100} # Missing required fields
    assert validate_state_structure(invalid_state) is False

def test_migrate_legacy_state():
    """Tests the migration of a legacy state structure to the modern format."""
    legacy_state = {
        "wallet_balance": 120.0,
        "active_positions": [
            {
                "token_address": "LegacyToken1",
                "token_symbol": "LEGACY",
                "entry_price_usd": 1.0,
                "amount": 100,
                "bitquery_enriched": True, # Legacy field
                "entry_bitquery_score": 75 # Legacy field
            }
        ],
        "agent_parameters": {"old_param": "value"}
    }

    with patch('src.blockchain.solana_client.get_wallet_balance', return_value=100.0):
        migrated_state = migrate_legacy_state(legacy_state)

    assert validate_state_structure(migrated_state) is True
    assert migrated_state["wallet_balance_sol"] == 120.0
    assert len(migrated_state["active_positions"]) == 1
    
    migrated_pos = migrated_state["active_positions"][0]
    assert migrated_pos["token_symbol"] == "LEGACY"
    assert migrated_pos["entry_ai_score"] == 75 # Should be mapped
    assert "old_param" in migrated_state["agent_parameters"]

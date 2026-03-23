"""
Tests for src/agent/state.py

create_initial_state() calls real Solana RPC and CoinGecko.
Tests assert structural properties, not specific values.
"""
import os
import json
import math
import pytest
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock
from src.agent.state import (
    create_initial_state,
    update_portfolio_metrics,
    validate_state_structure,
    migrate_legacy_state,
    save_agent_state,
    load_agent_state,
    get_state_summary,
)


def test_create_initial_state():
    """Tests that create_initial_state() returns a structurally valid state dict."""
    state = create_initial_state()

    assert isinstance(state["wallet_balance_sol"], float)
    assert state["wallet_balance_sol"] >= 0.0
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
        {"current_value_sol": 30.0, "unrealized_pnl_sol": -2.0},
    ]
    state["transaction_history"] = [
        {"type": "sell", "profit_percentage": 10},
        {"type": "sell", "profit_percentage": -5},
        {"type": "sell", "profit_percentage": 20},
    ]

    updated_state = update_portfolio_metrics(state)

    assert updated_state["total_portfolio_value_sol"] == 50.0 + 25.0 + 30.0
    assert updated_state["portfolio_metrics"]["unrealized_profit_sol"] == pytest.approx(3.0)
    assert updated_state["win_rate"] == pytest.approx(2 / 3)


def test_validate_state_structure():
    """Tests the validation of the agent state structure."""
    valid_state = create_initial_state()
    assert validate_state_structure(valid_state) is True

    invalid_state = {"wallet_balance_sol": 100}  # Missing required fields
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
                "bitquery_enriched": True,
                "entry_bitquery_score": 75,
            }
        ],
        "agent_parameters": {"old_param": "value"},
    }

    migrated_state = migrate_legacy_state(legacy_state)

    assert validate_state_structure(migrated_state) is True
    assert migrated_state["wallet_balance_sol"] == 120.0
    assert len(migrated_state["active_positions"]) == 1

    migrated_pos = migrated_state["active_positions"][0]
    assert migrated_pos["token_symbol"] == "LEGACY"
    assert migrated_pos["entry_ai_score"] == 75
    assert "old_param" in migrated_state["agent_parameters"]


# ─────────────────────────────────────────────────────────────────────────────
# save_agent_state() — atomic write and DB snapshot
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveAgentState:
    @pytest.fixture
    def tmp_state_path(self, tmp_path):
        return str(tmp_path / "agent_state_test.json")

    @pytest.fixture
    def state(self):
        return create_initial_state()

    def test_save_returns_true_on_success(self, tmp_state_path, state):
        result = save_agent_state(state, tmp_state_path)
        assert result is True

    def test_save_writes_json_file(self, tmp_state_path, state):
        state["cycles_completed"] = 42
        save_agent_state(state, tmp_state_path)
        with open(tmp_state_path) as f:
            data = json.load(f)
        assert data["cycles_completed"] == 42

    def test_save_does_not_leave_tmp_file(self, tmp_state_path, state):
        save_agent_state(state, tmp_state_path)
        tmp_file = tmp_state_path + ".tmp"
        assert not os.path.exists(tmp_file), ".tmp file must be removed after atomic replace"

    def test_save_calls_db_snapshot(self, tmp_state_path, state):
        with patch("src.db.trade_store.save_state_snapshot") as mock_snap:
            save_agent_state(state, tmp_state_path)
        mock_snap.assert_called_once()

    def test_save_continues_when_db_snapshot_fails(self, tmp_state_path, state):
        """DB snapshot failure must NOT cause save to fail."""
        with patch("src.db.trade_store.save_state_snapshot",
                   side_effect=Exception("DB down")):
            result = save_agent_state(state, tmp_state_path)
        assert result is True
        assert os.path.exists(tmp_state_path)

    def test_save_returns_false_on_io_error(self, state):
        """Non-writable path must return False without raising."""
        bad_path = "/nonexistent/deep/path/state.json"
        result = save_agent_state(state, bad_path)
        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# load_agent_state() — file not found, corrupt JSON
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadAgentState:
    def test_returns_none_when_file_missing(self, tmp_path):
        missing = str(tmp_path / "no_such_file.json")
        result = load_agent_state(missing)
        assert result is None

    def test_returns_dict_when_file_present(self, tmp_path):
        state_file = tmp_path / "state.json"
        payload = {"cycles_completed": 7, "wallet_balance_sol": 3.14}
        state_file.write_text(json.dumps(payload))
        result = load_agent_state(str(state_file))
        assert isinstance(result, dict)
        assert result["cycles_completed"] == 7

    def test_returns_none_on_corrupt_json(self, tmp_path):
        state_file = tmp_path / "corrupt.json"
        state_file.write_text("{this is not valid json{{{{")
        result = load_agent_state(str(state_file))
        assert result is None

    def test_returns_none_on_empty_file(self, tmp_path):
        state_file = tmp_path / "empty.json"
        state_file.write_text("")
        result = load_agent_state(str(state_file))
        assert result is None

    def test_round_trip_save_then_load(self, tmp_path):
        """save then load must reproduce the same data."""
        state_file = str(tmp_path / "roundtrip.json")
        state = create_initial_state()
        state["cycles_completed"] = 99
        save_agent_state(state, state_file)
        loaded = load_agent_state(state_file)
        assert loaded is not None
        assert loaded["cycles_completed"] == 99


# ─────────────────────────────────────────────────────────────────────────────
# get_state_summary()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetStateSummary:
    EXPECTED_KEYS = {
        "wallet_balance_sol",
        "active_positions_count",
        "total_portfolio_value",
        "ai_strategy",
        "cycles_completed",
        "win_rate",
        "total_trades",
        "successful_trades",
        "last_updated",
        "current_stage",
        "performance_score",
    }

    def test_returns_dict_with_all_expected_keys(self):
        state = create_initial_state()
        summary = get_state_summary(state)
        assert self.EXPECTED_KEYS.issubset(summary.keys())

    def test_total_portfolio_value_includes_positions(self):
        state = create_initial_state()
        state["wallet_balance_sol"] = 5.0
        state["active_positions"] = [
            {"current_value_sol": 2.0},
            {"current_value_sol": 1.5},
        ]
        summary = get_state_summary(state)
        assert summary["total_portfolio_value"] == pytest.approx(8.5)

    def test_active_positions_count_correct(self):
        state = create_initial_state()
        state["active_positions"] = [{"current_value_sol": 1.0}] * 3
        summary = get_state_summary(state)
        assert summary["active_positions_count"] == 3

    def test_successful_trades_only_counts_profitable_sells(self):
        state = create_initial_state()
        state["transaction_history"] = [
            {"type": "sell", "profit_percentage": 10},
            {"type": "sell", "profit_percentage": -5},
            {"type": "buy",  "profit_percentage": 15},
            {"type": "sell", "profit_percentage": 20},
        ]
        summary = get_state_summary(state)
        assert summary["successful_trades"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# update_portfolio_metrics() — Sharpe ratio and max drawdown
# ─────────────────────────────────────────────────────────────────────────────

class TestPortfolioMetricsExtended:
    def _state_with_trades(self, profit_percentages):
        state = create_initial_state()
        state["transaction_history"] = [
            {"type": "sell", "profit_percentage": p}
            for p in profit_percentages
        ]
        return state

    def test_sharpe_ratio_nonzero_with_variance(self):
        state = self._state_with_trades([10, -5, 20, 3, -8])
        updated = update_portfolio_metrics(state)
        assert updated.get("sharpe_ratio", 0) != 0

    def test_sharpe_ratio_zero_with_identical_returns(self):
        state = self._state_with_trades([5, 5, 5, 5, 5])
        updated = update_portfolio_metrics(state)
        assert updated.get("sharpe_ratio", 0) == 0.0

    def test_sharpe_not_calculated_with_fewer_than_two_trades(self):
        state = self._state_with_trades([10])
        updated = update_portfolio_metrics(state)
        sharpe = updated.get("sharpe_ratio", 0)
        assert isinstance(sharpe, (int, float))

    def test_max_drawdown_calculated_from_balance_history(self):
        """Peak 100 → trough 80 → drawdown = 20%."""
        state = create_initial_state()
        state["transaction_history"] = [
            {"type": "sell", "profit_percentage": 10},
            {"type": "sell", "profit_percentage": -5},
        ]
        state["portfolio_metrics"]["balance_history"] = [100, 95, 90, 80, 85]
        updated = update_portfolio_metrics(state)
        dd = updated.get("max_drawdown", 0)
        assert dd == pytest.approx(0.20, abs=1e-5)

    def test_max_drawdown_zero_with_monotonic_increase(self):
        state = create_initial_state()
        state["portfolio_metrics"]["balance_history"] = [10, 11, 12, 13, 14]
        updated = update_portfolio_metrics(state)
        assert updated.get("max_drawdown", 0) == pytest.approx(0.0, abs=1e-9)

    def test_balance_history_appended(self):
        state = create_initial_state()
        state["wallet_balance_sol"] = 7.0
        updated = update_portfolio_metrics(state)
        history = updated["portfolio_metrics"].get("balance_history", [])
        assert len(history) >= 1
        assert history[-1] == pytest.approx(7.0, rel=1e-3)

    def test_balance_history_capped_at_500(self):
        state = create_initial_state()
        state["portfolio_metrics"]["balance_history"] = [1.0] * 500
        state["wallet_balance_sol"] = 2.0
        updated = update_portfolio_metrics(state)
        assert len(updated["portfolio_metrics"]["balance_history"]) <= 500

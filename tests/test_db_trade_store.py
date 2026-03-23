# tests/test_db_trade_store.py
"""
Tests for src/db/trade_store.py

Unit tests mock the DB connection; integration tests use real PostgreSQL.
"""
import json
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Guards when DB unavailable
# ─────────────────────────────────────────────────────────────────────────────

class TestGuardsWhenDbUnavailable:
    @pytest.fixture(autouse=True)
    def db_off(self):
        with patch("src.db.trade_store.is_available", return_value=False):
            yield

    def test_create_session_returns_none(self):
        from src.db.trade_store import create_session
        assert create_session("google", "dry_run", {}) is None

    def test_end_session_is_noop(self):
        from src.db.trade_store import end_session
        end_session("session_id", {})  # must not raise

    def test_record_cycle_returns_none(self):
        from src.db.trade_store import record_cycle
        assert record_cycle("session_id", 1, {}) is None

    def test_record_trade_returns_none(self):
        from src.db.trade_store import record_trade
        assert record_trade("session_id", None, {}) is None

    def test_open_position_returns_none(self):
        from src.db.trade_store import open_position
        assert open_position(1, {}) is None

    def test_close_position_is_noop(self):
        from src.db.trade_store import close_position
        close_position("pos_id", 1, {})  # must not raise

    def test_save_state_snapshot_is_noop(self):
        from src.db.trade_store import save_state_snapshot
        save_state_snapshot("google", {})  # must not raise

    def test_record_discovered_token_is_noop(self):
        from src.db.trade_store import record_discovered_token
        record_discovered_token("s", None, "google", {})  # must not raise

    def test_record_agent_error_is_noop(self):
        from src.db.trade_store import record_agent_error
        record_agent_error("s", None, "google", "TestError", "msg")  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
# create_session()
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateSession:
    def test_returns_valid_uuid_string(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import create_session
            session_id = create_session("google", "dry_run", {"key": "val"}, 10.0)
        assert session_id is not None
        uuid.UUID(session_id)  # must be valid UUID

    def test_executes_insert_with_correct_fields(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import create_session
            create_session("anthropic", "live", {"mode": "live"}, 5.0)
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        # params: (session_id, model_provider, trading_mode, initial_balance_sol, json_params)
        # 'running' is hardcoded in the SQL string, not a parameter
        assert "INSERT INTO trading_sessions" in sql
        assert "'running'" in sql or "running" in sql
        assert params[1] == "anthropic"
        assert params[2] == "live"
        assert params[3] == 5.0  # initial_balance_sol
        assert json.loads(params[4]) == {"mode": "live"}

    def test_returns_none_on_db_exception(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.execute.side_effect = Exception("DB error")
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import create_session
            result = create_session("google", "dry_run", {})
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# end_session()
# ─────────────────────────────────────────────────────────────────────────────

class TestEndSession:
    def test_executes_update_with_session_id(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        final_state = {"cycles_completed": 10, "total_profit_sol": 0.5, "wallet_balance_sol": 10.5}
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import end_session
            end_session("sess-123", final_state)
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert "UPDATE trading_sessions" in sql
        assert "completed" in sql
        assert params[0] == 10
        assert params[-1] == "sess-123"

    def test_skips_when_no_session_id(self):
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import end_session
            end_session(None, {})  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
# record_cycle()
# ─────────────────────────────────────────────────────────────────────────────

class TestRecordCycle:
    def test_returns_cycle_id_from_db(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchone.return_value = (42,)
        state = {
            "model_provider": "google",
            "trading_mode": "dry_run",
            "wallet_balance_sol": 10.0,
            "simulated_balance_sol": 9.5,
            "active_positions": [],
            "tools_used_this_cycle": ["get_wallet_balance_tool"],
            "market_sentiment": "bullish",
        }
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import record_cycle
            cycle_id = record_cycle("sess-123", 5, state, duration_seconds=12.3)
        assert cycle_id == 42

    def test_inserts_tools_used_array(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchone.return_value = (1,)
        state = {"tools_used_this_cycle": ["tool_a", "tool_b"], "active_positions": []}
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import record_cycle
            record_cycle("sess-123", 1, state)
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO trading_cycles" in sql

    def test_returns_none_on_exception(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.execute.side_effect = Exception("timeout")
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import record_cycle
            assert record_cycle("s", 1, {}) is None


# ─────────────────────────────────────────────────────────────────────────────
# record_trade()
# ─────────────────────────────────────────────────────────────────────────────

class TestRecordTrade:
    def test_returns_trade_id(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchone.return_value = (99,)
        trade_data = {
            "model_provider": "google",
            "trading_mode": "dry_run",
            "trade_type": "buy",
            "token_address": "TokenXXX",
            "token_symbol": "BONK",
            "amount_sol": 0.05,
            "dry_run": True,
            "reasoning": "Strong signal",
            "success": True,
        }
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import record_trade
            trade_id = record_trade("sess-123", 42, trade_data)
        assert trade_id == 99

    def test_stores_raw_data_as_json(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchone.return_value = (1,)
        trade_data = {"token_symbol": "TEST", "trade_type": "buy"}
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import record_trade
            record_trade("s", None, trade_data)
        params = mock_cursor.execute.call_args[0][1]
        # Last param is raw_data JSON
        raw = json.loads(params[-1])
        assert raw["token_symbol"] == "TEST"


# ─────────────────────────────────────────────────────────────────────────────
# open_position() / close_position()
# ─────────────────────────────────────────────────────────────────────────────

class TestPositions:
    def test_open_position_inserts_and_returns_id(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchone.return_value = (55,)
        pos_data = {
            "position_id": "pos_001",
            "token_address": "TokenXXX",
            "token_symbol": "BONK",
            "model_provider": "google",
            "position_size_sol": 0.05,
            "entry_price_usd": 0.000025,
        }
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import open_position
            pos_id = open_position(99, pos_data)
        assert pos_id == 55
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO positions" in sql

    def test_close_position_executes_update(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        exit_data = {
            "hold_time_hours": 6.5,
            "exit_price_usd": 0.000030,
            "realized_pnl_sol": 0.01,
            "realized_pnl_usd": 1.5,
            "profit_percentage": 20.0,
        }
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import close_position
            close_position("pos_001", 100, exit_data)
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert "UPDATE positions" in sql
        assert "closed" in sql
        assert params[-1] == "pos_001"  # WHERE position_id = %s


# ─────────────────────────────────────────────────────────────────────────────
# save_state_snapshot()
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveStateSnapshot:
    def test_inserts_snapshot_row(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        state = {
            "trading_mode": "dry_run",
            "cycles_completed": 5,
            "wallet_balance_sol": 10.0,
            "simulated_balance_sol": 9.5,
            "total_profit_sol": 0.3,
            "win_rate": 0.6,
            "active_positions": [],
            "portfolio_metrics": {"total_value_sol": 9.5},
        }
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import save_state_snapshot
            save_state_snapshot("google", state)
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO agent_state_snapshots" in sql

    def test_excludes_large_lists_from_json(self, mock_db_conn):
        """Lean state JSON must not include discovered_tokens etc."""
        mock_conn, mock_cursor = mock_db_conn
        state = {
            "wallet_balance_sol": 5.0,
            "active_positions": [],
            "discovered_tokens": [{"address": "x"} for _ in range(100)],
            "analyzed_tokens": [{"address": "y"} for _ in range(100)],
            "portfolio_metrics": {},
        }
        with patch("src.db.trade_store.is_available", return_value=True):
            from src.db.trade_store import save_state_snapshot
            save_state_snapshot("google", state)
        params = mock_cursor.execute.call_args[0][1]
        lean_state = json.loads(params[-1])
        assert "discovered_tokens" not in lean_state
        assert "analyzed_tokens" not in lean_state


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests — real PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

class TestTradeStoreIntegration:
    def test_create_and_end_session_roundtrip(self, db_available):
        from src.db.trade_store import create_session, end_session
        from src.db.connection import get_conn

        session_id = create_session("google", "dry_run", {"test": True}, 10.0)
        assert session_id is not None
        uuid.UUID(session_id)

        final_state = {"cycles_completed": 3, "total_profit_sol": 0.1, "wallet_balance_sol": 10.1}
        end_session(session_id, final_state)

        # Verify in DB
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status, cycles_completed FROM trading_sessions WHERE id = %s", (session_id,))
                row = cur.fetchone()
        assert row is not None
        assert row[0] == "completed"
        assert row[1] == 3

        # Cleanup
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM trading_sessions WHERE id = %s", (session_id,))

    def test_record_cycle_returns_real_id(self, db_available):
        from src.db.trade_store import create_session, record_cycle
        from src.db.connection import get_conn

        session_id = create_session("google", "dry_run", {}, 10.0)
        state = {
            "model_provider": "google", "trading_mode": "dry_run",
            "wallet_balance_sol": 10.0, "simulated_balance_sol": 9.8,
            "active_positions": [], "tools_used_this_cycle": ["test_tool"],
            "cycles_completed": 1,
        }
        cycle_id = record_cycle(session_id, 1, state, duration_seconds=5.0)
        assert isinstance(cycle_id, int)
        assert cycle_id > 0

        # Cleanup
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM trading_cycles WHERE session_id = %s", (session_id,))
                cur.execute("DELETE FROM trading_sessions WHERE id = %s", (session_id,))

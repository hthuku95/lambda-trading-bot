# tests/test_db_query_store.py
"""
Tests for src/db/query_store.py

Unit tests mock the DB. Integration tests hit real PostgreSQL.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Guards when DB unavailable
# ─────────────────────────────────────────────────────────────────────────────

class TestGuardsWhenDbUnavailable:
    @pytest.fixture(autouse=True)
    def db_off(self):
        with patch("src.db.query_store.is_available", return_value=False):
            yield

    def test_get_trade_history_returns_empty_list(self):
        from src.db.query_store import get_trade_history
        assert get_trade_history() == []

    def test_get_session_history_returns_empty_list(self):
        from src.db.query_store import get_session_history
        assert get_session_history() == []

    def test_get_performance_summary_returns_empty_dict(self):
        from src.db.query_store import get_performance_summary
        assert get_performance_summary() == {}

    def test_compare_model_performance_returns_empty_dict(self):
        from src.db.query_store import compare_model_performance
        assert compare_model_performance() == {}

    def test_get_token_discovery_history_returns_empty_list(self):
        from src.db.query_store import get_token_discovery_history
        assert get_token_discovery_history("TokenXXX") == []

    def test_get_top_performing_tokens_returns_empty_list(self):
        from src.db.query_store import get_top_performing_tokens
        assert get_top_performing_tokens() == []

    def test_search_logs_returns_empty_list(self):
        from src.db.query_store import search_logs
        assert search_logs() == []

    def test_get_error_summary_returns_empty_dict(self):
        from src.db.query_store import get_error_summary
        assert get_error_summary() == {}


# ─────────────────────────────────────────────────────────────────────────────
# get_trade_history()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetTradeHistory:
    def _make_cursor_with_rows(self, rows, columns):
        cur = MagicMock()
        cur.description = [(col,) for col in columns]
        cur.fetchall.return_value = rows
        return cur

    def test_returns_list_of_dicts(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        cols = ["id", "session_id", "model_provider", "trading_mode", "trade_type",
                "token_address", "token_symbol", "amount_sol", "price_usd",
                "dry_run", "reasoning", "simulated_balance_after",
                "transaction_id", "success", "error_message", "timestamp"]
        mock_cursor.description = [(c,) for c in cols]
        mock_cursor.fetchall.return_value = [
            (1, "sess-1", "google", "dry_run", "buy", "TokenXXX", "BONK",
             0.05, None, True, "strong signal", 9.95, None, True, None,
             datetime.now(timezone.utc))
        ]
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import get_trade_history
            result = get_trade_history()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["trade_type"] == "buy"
        assert result[0]["token_symbol"] == "BONK"

    def test_filters_by_model_provider(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = []
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import get_trade_history
            get_trade_history(model_provider="anthropic")
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert "model_provider" in sql
        assert "anthropic" in params

    def test_filters_by_token_address(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = []
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import get_trade_history
            get_trade_history(token_address="TokenABC")
        sql = mock_cursor.execute.call_args[0][0]
        assert "token_address" in sql

    def test_filters_by_trade_type(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = []
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import get_trade_history
            get_trade_history(trade_type="buy")
        sql = mock_cursor.execute.call_args[0][0]
        assert "trade_type" in sql

    def test_returns_empty_list_on_exception(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.execute.side_effect = Exception("timeout")
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import get_trade_history
            result = get_trade_history()
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# get_performance_summary()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetPerformanceSummary:
    EXPECTED_KEYS = {
        "period_days", "model_provider", "total_trades", "sell_trades",
        "successful_trades", "total_sol_received", "avg_trade_sol",
        "closed_positions", "profitable_positions", "win_rate",
        "avg_profit_pct", "best_trade_pct", "worst_trade_pct",
        "avg_hold_hours", "sharpe_ratio", "max_drawdown",
    }

    def test_returns_dict_with_all_expected_keys(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        # fetchone called 3 times: trade_row, pos_row, snap_row
        mock_cursor.fetchone.side_effect = [
            (100, 40, 95, 5.0, 0.05),    # trade_row
            (40, 30, 12.5, 25.0, -5.0, 6.5),  # pos_row
            (1.2, 0.08, 0.75),           # snap_row
        ]
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import get_performance_summary
            result = get_performance_summary("google", 7)
        assert isinstance(result, dict)
        assert self.EXPECTED_KEYS.issubset(result.keys())

    def test_win_rate_calculated_correctly(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchone.side_effect = [
            (50, 20, 48, 2.5, 0.05),
            (20, 15, 10.0, 30.0, -3.0, 5.0),
            None,
        ]
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import get_performance_summary
            result = get_performance_summary()
        assert result["win_rate"] == round(15 / 20, 4)

    def test_win_rate_zero_when_no_closed_positions(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchone.side_effect = [
            (0, 0, 0, None, None),
            (0, 0, None, None, None, None),
            None,
        ]
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import get_performance_summary
            result = get_performance_summary()
        assert result["win_rate"] == 0.0

    def test_returns_empty_dict_on_exception(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.execute.side_effect = Exception("timeout")
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import get_performance_summary
            result = get_performance_summary()
        assert result == {}


# ─────────────────────────────────────────────────────────────────────────────
# compare_model_performance()
# ─────────────────────────────────────────────────────────────────────────────

class TestCompareModelPerformance:
    def test_returns_dict_with_models_key(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchall.side_effect = [
            [("google", 5, 100, 60, 40, 8.0)],   # trade_rows
            [("google", 40, 30, 12.5, 0.5)],     # pos_rows
        ]
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import compare_model_performance
            result = compare_model_performance(30)
        assert "models" in result
        assert "period_days" in result
        assert result["period_days"] == 30

    def test_includes_both_providers_when_both_active(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchall.side_effect = [
            [
                ("google", 3, 60, 35, 25, 4.5),
                ("anthropic", 2, 40, 22, 18, 3.0),
            ],
            [
                ("google", 25, 18, 8.5, 0.3),
                ("anthropic", 18, 14, 9.1, 0.25),
            ],
        ]
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import compare_model_performance
            result = compare_model_performance()
        assert "google" in result["models"]
        assert "anthropic" in result["models"]


# ─────────────────────────────────────────────────────────────────────────────
# search_logs()
# ─────────────────────────────────────────────────────────────────────────────

class TestSearchLogs:
    def test_adds_level_filter_when_given(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.description = [("timestamp",), ("level",), ("logger_name",), ("message",)]
        mock_cursor.fetchall.return_value = []
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import search_logs
            search_logs(level="ERROR")
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert "level" in sql
        assert "ERROR" in params

    def test_adds_ilike_keyword_filter_when_given(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.description = [("timestamp",), ("level",), ("logger_name",), ("message",)]
        mock_cursor.fetchall.return_value = []
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import search_logs
            search_logs(keyword="RugCheck")
        sql = mock_cursor.execute.call_args[0][0]
        assert "ILIKE" in sql

    def test_no_filters_returns_recent_logs(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.description = [("timestamp",), ("level",), ("logger_name",), ("message",)]
        mock_cursor.fetchall.return_value = [
            (datetime.now(timezone.utc), "INFO", "trading_agent", "Started cycle")
        ]
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import search_logs
            result = search_logs()
        assert len(result) == 1
        assert result[0]["message"] == "Started cycle"


# ─────────────────────────────────────────────────────────────────────────────
# get_top_performing_tokens()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetTopPerformingTokens:
    COLS = ["token_address", "token_symbol", "trade_count",
            "avg_profit_pct", "total_pnl_sol", "wins"]

    def test_returns_list_ordered_by_profit_pct_default(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.description = [(c,) for c in self.COLS]
        mock_cursor.fetchall.return_value = [
            ("TokenA", "BONK", 10, 25.5, 0.5, 8),
            ("TokenB", "WIF", 5, 12.0, 0.2, 3),
        ]
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import get_top_performing_tokens
            result = get_top_performing_tokens(metric="profit_percentage")
        sql = mock_cursor.execute.call_args[0][0]
        assert "AVG(profit_percentage)" in sql
        assert len(result) == 2

    def test_uses_count_metric_when_specified(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.description = [(c,) for c in self.COLS]
        mock_cursor.fetchall.return_value = []
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import get_top_performing_tokens
            get_top_performing_tokens(metric="trade_count")
        sql = mock_cursor.execute.call_args[0][0]
        assert "COUNT(*)" in sql

    def test_invalid_metric_falls_back_to_profit_pct(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.description = [(c,) for c in self.COLS]
        mock_cursor.fetchall.return_value = []
        with patch("src.db.query_store.is_available", return_value=True):
            from src.db.query_store import get_top_performing_tokens
            get_top_performing_tokens(metric="invalid_metric")
        sql = mock_cursor.execute.call_args[0][0]
        assert "AVG(profit_percentage)" in sql


# ─────────────────────────────────────────────────────────────────────────────
# Integration — real PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

class TestQueryStoreIntegration:
    def test_get_trade_history_returns_list(self, db_available):
        from src.db.query_store import get_trade_history
        result = get_trade_history(days_back=30, limit=5)
        assert isinstance(result, list)

    def test_get_session_history_returns_list(self, db_available):
        from src.db.query_store import get_session_history
        result = get_session_history(limit=5)
        assert isinstance(result, list)

    def test_get_performance_summary_returns_dict(self, db_available):
        from src.db.query_store import get_performance_summary
        result = get_performance_summary(days_back=7)
        assert isinstance(result, dict)

    def test_compare_model_performance_returns_dict(self, db_available):
        from src.db.query_store import compare_model_performance
        result = compare_model_performance(days_back=30)
        assert isinstance(result, dict)

    def test_search_logs_returns_list(self, db_available):
        from src.db.query_store import search_logs
        result = search_logs(hours_back=1, limit=10)
        assert isinstance(result, list)

    def test_get_error_summary_returns_dict(self, db_available):
        from src.db.query_store import get_error_summary
        result = get_error_summary(hours=24)
        assert isinstance(result, dict)
        assert "total_errors" in result

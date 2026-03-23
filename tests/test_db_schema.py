# tests/test_db_schema.py
"""
Tests for src/db/schema.py

ensure_schema() makes ONE execute() call with the entire DDL string.
Unit tests mock get_conn() directly (schema.py has no is_available guard).
Integration tests run ensure_schema() against the real DB.
"""
import pytest
from unittest.mock import patch, MagicMock, call


EXPECTED_TABLES = [
    "auth_login_attempts",
    "auth_lockouts",
    "auth_events",
    "system_logs",
    "trading_sessions",
    "trading_cycles",
    "trades",
    "positions",
    "agent_state_snapshots",
    "discovered_tokens",
    "agent_errors",
    "chat_messages",
]


def _make_mock_conn():
    """Return (mock_conn, mock_cursor) wired as a context manager pair."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    # Wire conn.cursor() as a context manager
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    # Wire get_conn() itself as a context manager
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestEnsureSchemaWhenDbUnavailable:
    def test_returns_false_when_get_conn_raises(self):
        """ensure_schema() has no is_available guard; it returns False when get_conn() raises."""
        from src.db.schema import ensure_schema
        with patch("src.db.schema.get_conn", side_effect=RuntimeError("DB unavailable")):
            result = ensure_schema()
        assert result is False


class TestEnsureSchemaWithMockedDb:
    @pytest.fixture
    def captured_sql(self):
        """Collect all SQL strings executed during ensure_schema()."""
        mock_conn, mock_cursor = _make_mock_conn()
        executed = []

        def capture_execute(sql, *args, **kwargs):
            executed.append(sql)

        mock_cursor.execute.side_effect = capture_execute

        from src.db.schema import ensure_schema
        with patch("src.db.schema.get_conn", return_value=mock_conn):
            ensure_schema()
        return executed

    def test_creates_all_12_tables(self, captured_sql):
        """Every table name must appear in at least one execute call."""
        all_sql = " ".join(captured_sql)
        for table in EXPECTED_TABLES:
            assert table in all_sql, \
                f"Table '{table}' not found in any executed SQL statement"

    def test_uses_create_table_if_not_exists(self, captured_sql):
        """All CREATE TABLE must be idempotent."""
        all_sql = " ".join(captured_sql)
        assert "CREATE TABLE IF NOT EXISTS" in all_sql.upper()

    def test_creates_indexes_for_system_logs(self, captured_sql):
        """system_logs needs indexes for query performance."""
        all_sql = " ".join(captured_sql)
        assert "system_logs" in all_sql
        assert "CREATE INDEX" in all_sql.upper()

    def test_idempotent_two_consecutive_calls(self):
        """ensure_schema() called twice must not raise any error."""
        mock_conn, mock_cursor = _make_mock_conn()
        from src.db.schema import ensure_schema
        with patch("src.db.schema.get_conn", return_value=mock_conn):
            ensure_schema()
            ensure_schema()  # second call — must not raise

    def test_returns_true_on_success(self):
        mock_conn, _ = _make_mock_conn()
        from src.db.schema import ensure_schema
        with patch("src.db.schema.get_conn", return_value=mock_conn):
            result = ensure_schema()
        assert result is True

    def test_returns_false_on_db_exception(self):
        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.execute.side_effect = Exception("syntax error")
        from src.db.schema import ensure_schema
        with patch("src.db.schema.get_conn", return_value=mock_conn):
            result = ensure_schema()
        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# Integration — real PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemaIntegration:
    def test_ensure_schema_creates_all_tables(self, db_available):
        """Run against real DB — all tables must exist after ensure_schema()."""
        from src.db.schema import ensure_schema
        from src.db.connection import get_conn

        ensure_schema()

        with get_conn() as conn:
            with conn.cursor() as cur:
                for table in EXPECTED_TABLES:
                    cur.execute(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = %s)",
                        (table,)
                    )
                    exists = cur.fetchone()[0]
                    assert exists, f"Table '{table}' does not exist in real DB"

    def test_ensure_schema_is_idempotent_on_real_db(self, db_available):
        """Running twice against real DB must not raise."""
        from src.db.schema import ensure_schema
        ensure_schema()
        ensure_schema()  # second call — must succeed

# tests/test_db_auth_store.py
"""
Tests for src/db/auth_store.py

Unit tests use a mock DB connection (no real DB needed).
Integration tests marked with db_available fixture use the real PostgreSQL instance.
"""
import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, call


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — all DB calls mocked
# ─────────────────────────────────────────────────────────────────────────────

class TestGuardsWhenDbUnavailable:
    """Every public function must silently no-op when the DB is unavailable."""

    @pytest.fixture(autouse=True)
    def db_off(self):
        with patch("src.db.auth_store.is_available", return_value=False):
            yield

    def test_record_failed_attempt_is_noop(self):
        from src.db.auth_store import record_failed_attempt
        record_failed_attempt("key", "user")  # must not raise

    def test_get_recent_attempt_count_returns_zero(self):
        from src.db.auth_store import get_recent_attempt_count
        assert get_recent_attempt_count("key") == 0

    def test_get_remaining_attempts_returns_max(self):
        from src.db.auth_store import get_remaining_attempts
        result = get_remaining_attempts("key")
        max_attempts = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
        assert result == max_attempts

    def test_is_locked_out_returns_false(self):
        from src.db.auth_store import is_locked_out
        assert is_locked_out("key") is False

    def test_record_lockout_is_noop(self):
        from src.db.auth_store import record_lockout
        record_lockout("key")  # must not raise

    def test_clear_lockout_is_noop(self):
        from src.db.auth_store import clear_lockout
        clear_lockout("key")  # must not raise

    def test_log_auth_event_is_noop(self):
        from src.db.auth_store import log_auth_event
        log_auth_event("login", "user", success=True)  # must not raise

    def test_clear_old_attempts_is_noop(self):
        from src.db.auth_store import clear_old_attempts
        clear_old_attempts("key")  # must not raise


class TestRecordFailedAttempt:
    def test_inserts_row_with_correct_values(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import record_failed_attempt
            record_failed_attempt("client_123", "testuser", "192.168.1.1")

        executed_sql = mock_cursor.execute.call_args[0][0]
        executed_params = mock_cursor.execute.call_args[0][1]
        assert "INSERT INTO auth_login_attempts" in executed_sql
        assert executed_params[0] == "client_123"
        assert executed_params[1] == "testuser"
        assert executed_params[2] == "192.168.1.1"

    def test_handles_db_exception_gracefully(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.execute.side_effect = Exception("DB error")
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import record_failed_attempt
            record_failed_attempt("key", "user")  # must not raise


class TestGetRecentAttemptCount:
    def test_returns_count_from_db(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchone.return_value = (3,)
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import get_recent_attempt_count
            count = get_recent_attempt_count("client_123")
        assert count == 3

    def test_returns_zero_on_db_exception(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.execute.side_effect = Exception("timeout")
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import get_recent_attempt_count
            count = get_recent_attempt_count("client_123")
        assert count == 0


class TestGetRemainingAttempts:
    def test_full_remaining_when_no_attempts(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchone.return_value = (0,)
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import get_remaining_attempts
            remaining = get_remaining_attempts("key")
        max_attempts = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
        assert remaining == max_attempts

    def test_decrements_correctly(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchone.return_value = (3,)
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import get_remaining_attempts
            remaining = get_remaining_attempts("key")
        max_attempts = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
        assert remaining == max_attempts - 3

    def test_never_returns_negative(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchone.return_value = (999,)  # way over limit
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import get_remaining_attempts
            remaining = get_remaining_attempts("key")
        assert remaining == 0


class TestIsLockedOut:
    def test_returns_false_when_no_lockout_row(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.fetchone.return_value = None
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import is_locked_out
            assert is_locked_out("key") is False

    def test_returns_true_when_lockout_not_expired(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        future_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        mock_cursor.fetchone.return_value = (future_expiry,)
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import is_locked_out
            assert is_locked_out("key") is True

    def test_returns_false_and_deletes_when_lockout_expired(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        past_expiry = datetime.now(timezone.utc) - timedelta(minutes=5)
        mock_cursor.fetchone.return_value = (past_expiry,)
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import is_locked_out
            result = is_locked_out("key")
        assert result is False
        # Verify DELETE was called to clean up expired lockout
        all_sqls = [c[0][0] for c in mock_cursor.execute.call_args_list]
        assert any("DELETE" in sql for sql in all_sqls)

    def test_returns_false_on_db_exception(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        mock_cursor.execute.side_effect = Exception("timeout")
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import is_locked_out
            assert is_locked_out("key") is False


class TestRecordLockout:
    def test_executes_upsert_with_future_expiry(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import record_lockout
            record_lockout("client_key")
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert "INSERT INTO auth_lockouts" in sql
        assert "ON CONFLICT" in sql
        assert params[0] == "client_key"
        # Expiry must be in the future
        expiry = params[1]
        assert expiry > datetime.now(timezone.utc)


class TestClearLockout:
    def test_executes_delete(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import clear_lockout
            clear_lockout("client_key")
        sql = mock_cursor.execute.call_args[0][0]
        assert "DELETE FROM auth_lockouts" in sql
        assert "client_key" in mock_cursor.execute.call_args[0][1]


class TestLogAuthEvent:
    def test_inserts_event_with_all_fields(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import log_auth_event
            log_auth_event("login", "testuser", success=True,
                          ip_address="10.0.0.1", details={"reason": "ok"})
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert "INSERT INTO auth_events" in sql
        assert params[0] == "login"
        assert params[1] == "testuser"
        assert params[2] == "10.0.0.1"
        # details serialised as JSON string
        import json
        assert json.loads(params[3]) == {"reason": "ok"}

    def test_handles_none_details(self, mock_db_conn):
        mock_conn, mock_cursor = mock_db_conn
        with patch("src.db.auth_store.is_available", return_value=True):
            from src.db.auth_store import log_auth_event
            log_auth_event("logout", "user", success=True)
        params = mock_cursor.execute.call_args[0][1]
        assert params[3] is None  # no details → None


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests — real PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthStoreIntegration:
    """These tests hit the real DB. Each test is isolated via a rolled-back transaction."""

    TEST_KEY = "test_client_pytest_isolation"

    def test_record_and_count_failed_attempts(self, db_available):
        from src.db.auth_store import record_failed_attempt, get_recent_attempt_count
        # Clear any pre-existing data for this key
        from src.db.connection import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM auth_login_attempts WHERE client_key = %s", (self.TEST_KEY,))

        record_failed_attempt(self.TEST_KEY, "integration_user")
        record_failed_attempt(self.TEST_KEY, "integration_user")
        count = get_recent_attempt_count(self.TEST_KEY)
        assert count >= 2

        # Cleanup
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM auth_login_attempts WHERE client_key = %s", (self.TEST_KEY,))

    def test_lockout_roundtrip(self, db_available):
        from src.db.auth_store import record_lockout, is_locked_out, clear_lockout
        from src.db.connection import get_conn
        # Ensure no existing lockout
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM auth_lockouts WHERE client_key = %s", (self.TEST_KEY,))

        record_lockout(self.TEST_KEY)
        assert is_locked_out(self.TEST_KEY) is True
        clear_lockout(self.TEST_KEY)
        assert is_locked_out(self.TEST_KEY) is False

    def test_log_auth_event_inserts_row(self, db_available):
        from src.db.auth_store import log_auth_event
        from src.db.connection import get_conn
        log_auth_event("test_event", "pytest_user", success=True,
                      details={"test": True})
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM auth_events WHERE event_type = 'test_event' AND username = 'pytest_user'")
                count = cur.fetchone()[0]
        assert count >= 1
        # Cleanup
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM auth_events WHERE event_type = 'test_event' AND username = 'pytest_user'")

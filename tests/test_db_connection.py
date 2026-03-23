# tests/test_db_connection.py
"""
Tests for src/db/connection.py

Unit tests mock the psycopg2 pool; integration tests use the real PostgreSQL DB.
"""
import os
import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _reset_pool():
    """Reset the module-level _pool singleton between tests."""
    import src.db.connection as conn_module
    conn_module._pool = None


# ─────────────────────────────────────────────────────────────────────────────
# init_pool()
# ─────────────────────────────────────────────────────────────────────────────

class TestInitPool:
    @pytest.fixture(autouse=True)
    def reset(self):
        _reset_pool()
        yield
        _reset_pool()

    def test_returns_false_when_no_database_url(self):
        from src.db.connection import init_pool
        with patch.dict(os.environ, {}, clear=True):
            # Remove both URL vars
            env = {k: v for k, v in os.environ.items()
                   if k not in ("DATABASE_URL", "DATABASE_URL_INTERNAL")}
            with patch.dict(os.environ, env, clear=True):
                result = init_pool()
        assert result is False

    def test_returns_false_and_pool_stays_none_on_no_url(self):
        import src.db.connection as conn_module
        env = {k: v for k, v in os.environ.items()
               if k not in ("DATABASE_URL", "DATABASE_URL_INTERNAL")}
        with patch.dict(os.environ, env, clear=True):
            conn_module.init_pool()
        assert conn_module._pool is None

    def test_is_available_false_when_pool_not_initialised(self):
        from src.db.connection import is_available
        assert is_available() is False

    def test_returns_true_on_second_call_when_already_initialised(self):
        """init_pool() is idempotent — returns True immediately if pool exists."""
        import src.db.connection as conn_module
        conn_module._pool = MagicMock()  # Simulate already-init'd pool
        from src.db.connection import init_pool
        result = init_pool()
        assert result is True

    def test_prefers_internal_url_over_external(self):
        """When DATABASE_URL_INTERNAL is set it must be used, not DATABASE_URL."""
        mock_pool_class = MagicMock()
        env = {
            "DATABASE_URL": "postgresql://external/db",
            "DATABASE_URL_INTERNAL": "postgresql://internal/db",
        }
        with patch.dict(os.environ, env), \
             patch("psycopg2.pool.ThreadedConnectionPool", mock_pool_class):
            from src.db.connection import init_pool
            init_pool(min_conn=1, max_conn=2)
        # The DSN passed to ThreadedConnectionPool must be the internal URL
        call_kwargs = mock_pool_class.call_args
        used_dsn = call_kwargs[1].get("dsn") or call_kwargs[0][2]
        assert used_dsn == "postgresql://internal/db"

    def test_returns_false_on_pool_exception(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://bad/db"}), \
             patch("psycopg2.pool.ThreadedConnectionPool", side_effect=Exception("conn refused")):
            from src.db.connection import init_pool
            result = init_pool()
        assert result is False

    def test_is_available_true_after_successful_init(self):
        mock_pool = MagicMock()
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://ok/db"}), \
             patch("psycopg2.pool.ThreadedConnectionPool", return_value=mock_pool):
            from src.db.connection import init_pool, is_available
            init_pool()
        assert is_available() is True


# ─────────────────────────────────────────────────────────────────────────────
# get_conn() context manager
# ─────────────────────────────────────────────────────────────────────────────

class TestGetConn:
    @pytest.fixture(autouse=True)
    def reset(self):
        _reset_pool()
        yield
        _reset_pool()

    def test_raises_runtime_error_when_pool_not_initialised(self):
        from src.db.connection import get_conn
        with pytest.raises(RuntimeError, match="not initialised"):
            with get_conn():
                pass

    def test_commits_on_clean_exit(self):
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        import src.db.connection as conn_module
        conn_module._pool = mock_pool

        from src.db.connection import get_conn
        with get_conn() as conn:
            pass  # no exception

        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()

    def test_rolls_back_on_exception(self):
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        import src.db.connection as conn_module
        conn_module._pool = mock_pool

        from src.db.connection import get_conn
        with pytest.raises(ValueError):
            with get_conn():
                raise ValueError("boom")

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

    def test_always_returns_conn_to_pool(self):
        """putconn must be called even when an exception is raised."""
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        import src.db.connection as conn_module
        conn_module._pool = mock_pool

        from src.db.connection import get_conn
        try:
            with get_conn():
                raise RuntimeError("crash")
        except RuntimeError:
            pass

        mock_pool.putconn.assert_called_once_with(mock_conn)


# ─────────────────────────────────────────────────────────────────────────────
# close_pool()
# ─────────────────────────────────────────────────────────────────────────────

class TestClosePool:
    @pytest.fixture(autouse=True)
    def reset(self):
        _reset_pool()
        yield
        _reset_pool()

    def test_calls_closeall_when_pool_exists(self):
        mock_pool = MagicMock()
        import src.db.connection as conn_module
        conn_module._pool = mock_pool

        from src.db.connection import close_pool
        close_pool()
        mock_pool.closeall.assert_called_once()

    def test_sets_pool_to_none_after_close(self):
        import src.db.connection as conn_module
        conn_module._pool = MagicMock()
        from src.db.connection import close_pool
        close_pool()
        assert conn_module._pool is None

    def test_is_safe_to_call_when_pool_not_initialised(self):
        from src.db.connection import close_pool
        close_pool()  # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# Integration test — real PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

class TestRealDBConnection:
    def test_real_connection_roundtrip(self, db_available):
        """Execute a trivial query against the real DB."""
        from src.db.connection import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS val")
                row = cur.fetchone()
        assert row[0] == 1

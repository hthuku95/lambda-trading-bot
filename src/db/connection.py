# src/db/connection.py
"""
PostgreSQL connection pool — singleton ThreadedConnectionPool.
Call init_pool() once at application startup (agent_daemon.py or __init__.py).
Use get_conn() as a context manager for all DB operations.
"""
import os
import logging
from contextlib import contextmanager
from psycopg2 import pool as pg_pool

logger = logging.getLogger("trading_agent.db")

_pool: pg_pool.ThreadedConnectionPool = None


def init_pool(min_conn: int = 2, max_conn: int = 15) -> bool:
    """Initialise the connection pool. Safe to call multiple times — no-op if already initialised."""
    global _pool
    if _pool is not None:
        return True
    # Prefer internal URL (set by Render's Blueprint fromDatabase) — no SSL routing issues.
    # Fall back to external DATABASE_URL for local development.
    dsn = os.environ.get("DATABASE_URL_INTERNAL") or os.environ.get("DATABASE_URL")
    if not dsn:
        logger.warning("DATABASE_URL not set — PostgreSQL features disabled")
        return False
    try:
        _pool = pg_pool.ThreadedConnectionPool(min_conn, max_conn, dsn=dsn)
        logger.info(f"PostgreSQL pool initialised (min={min_conn}, max={max_conn})")
        return True
    except Exception as e:
        logger.error(f"Failed to initialise PostgreSQL pool: {e}")
        return False


def is_available() -> bool:
    """Return True if the pool has been successfully initialised."""
    return _pool is not None


@contextmanager
def get_conn():
    """
    Context manager that yields a psycopg2 connection from the pool.
    Commits on success, rolls back on exception, always returns connection to pool.
    """
    if _pool is None:
        raise RuntimeError("PostgreSQL pool not initialised — call init_pool() first")
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def close_pool():
    """Close all connections. Call on graceful shutdown."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("PostgreSQL pool closed")

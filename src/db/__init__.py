# src/db/__init__.py
"""
PostgreSQL integration package.
Call init_db() once at application startup.
"""
import logging

logger = logging.getLogger("trading_agent.db")


def init_db(min_conn: int = 2, max_conn: int = 15) -> bool:
    """
    Initialise the connection pool and ensure the schema exists.
    Safe to call multiple times — idempotent.
    Returns True if DB is available, False if DATABASE_URL is not set or connection fails.
    """
    from src.db.connection import init_pool, is_available
    from src.db.schema import ensure_schema

    if not init_pool(min_conn=min_conn, max_conn=max_conn):
        logger.warning("PostgreSQL pool not initialised — DB features disabled")
        return False

    if not ensure_schema():
        logger.error("Schema creation failed — DB features may be incomplete")
        return False

    logger.info("PostgreSQL ready")
    return True

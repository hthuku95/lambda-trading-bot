# src/db/auth_store.py
"""
PostgreSQL-backed auth store — replaces SQLite in enterprise_auth.py.
All functions are standalone and thread-safe via the connection pool.
"""
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from src.db.connection import get_conn, is_available

logger = logging.getLogger("trading_agent.db.auth")

# Mirror the env-var defaults from enterprise_auth.py
_MAX_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
_LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_DURATION_MINUTES", "15"))
_WINDOW_MINUTES = _LOCKOUT_MINUTES  # sliding window matches lockout duration


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────
# Login attempts
# ─────────────────────────────────────────────────────────────

def record_failed_attempt(client_key: str, username: str, ip_address: str = None) -> None:
    if not is_available():
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO auth_login_attempts (client_key, username, ip_address, success) "
                    "VALUES (%s, %s, %s, FALSE)",
                    (client_key, username, ip_address)
                )
    except Exception as e:
        logger.error(f"record_failed_attempt error: {e}")


def get_recent_attempt_count(client_key: str) -> int:
    """Count failed attempts within the sliding window."""
    if not is_available():
        return 0
    try:
        window_start = _now() - timedelta(minutes=_WINDOW_MINUTES)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM auth_login_attempts "
                    "WHERE client_key = %s AND attempt_time >= %s AND success = FALSE",
                    (client_key, window_start)
                )
                return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"get_recent_attempt_count error: {e}")
        return 0


def get_remaining_attempts(client_key: str) -> int:
    count = get_recent_attempt_count(client_key)
    return max(0, _MAX_ATTEMPTS - count)


def clear_old_attempts(client_key: str) -> None:
    """Prune attempts older than the window (called on successful login)."""
    if not is_available():
        return
    try:
        window_start = _now() - timedelta(minutes=_WINDOW_MINUTES)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM auth_login_attempts WHERE client_key = %s AND attempt_time < %s",
                    (client_key, window_start)
                )
    except Exception as e:
        logger.error(f"clear_old_attempts error: {e}")


# ─────────────────────────────────────────────────────────────
# Lockouts
# ─────────────────────────────────────────────────────────────

def is_locked_out(client_key: str) -> bool:
    if not is_available():
        return False
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT expires_at FROM auth_lockouts WHERE client_key = %s",
                    (client_key,)
                )
                row = cur.fetchone()
                if row is None:
                    return False
                expires_at = row[0]
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if _now() >= expires_at:
                    # Lockout expired — clean up
                    cur.execute("DELETE FROM auth_lockouts WHERE client_key = %s", (client_key,))
                    return False
                return True
    except Exception as e:
        logger.error(f"is_locked_out error: {e}")
        return False


def record_lockout(client_key: str) -> None:
    if not is_available():
        return
    try:
        expires_at = _now() + timedelta(minutes=_LOCKOUT_MINUTES)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO auth_lockouts (client_key, expires_at) VALUES (%s, %s) "
                    "ON CONFLICT (client_key) DO UPDATE SET lockout_time = NOW(), expires_at = EXCLUDED.expires_at",
                    (client_key, expires_at)
                )
    except Exception as e:
        logger.error(f"record_lockout error: {e}")


def clear_lockout(client_key: str) -> None:
    if not is_available():
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM auth_lockouts WHERE client_key = %s", (client_key,))
    except Exception as e:
        logger.error(f"clear_lockout error: {e}")


# ─────────────────────────────────────────────────────────────
# Auth event log
# ─────────────────────────────────────────────────────────────

def log_auth_event(
    event_type: str,
    username: str,
    success: bool = True,
    ip_address: str = None,
    details: dict = None
) -> None:
    if not is_available():
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO auth_events (event_type, username, ip_address, details) "
                    "VALUES (%s, %s, %s, %s)",
                    (event_type, username, ip_address, json.dumps(details) if details else None)
                )
    except Exception as e:
        logger.error(f"log_auth_event error: {e}")

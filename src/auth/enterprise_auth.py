# src/auth/enterprise_auth.py
"""
Enterprise Authentication System for Trading Dashboard
Secure authentication with session management and rate limiting.
"""
import os
import time
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, Tuple
import streamlit as st
from dotenv import load_dotenv

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

# Load environment variables from .env file
load_dotenv()

# Create logs directory and configure audit logging
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - SECURITY - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/security_audit.log'),
        logging.StreamHandler()
    ]
)
audit_logger = logging.getLogger('security_audit')


class EnterpriseAuth:
    def __init__(self):
        # Load credentials from environment
        self.admin_username = os.getenv("DASHBOARD_USERNAME")
        self.admin_password = os.getenv("DASHBOARD_PASSWORD")

        # Security settings
        self.session_timeout = int(os.getenv("SESSION_TIMEOUT_HOURS", "8")) * 3600
        self.max_login_attempts = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
        self.lockout_duration = int(os.getenv("LOCKOUT_DURATION_MINUTES", "15")) * 60

        # SQLite-backed rate limiting (survives process restarts)
        self._db_path = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "rate_limit.db")
        self._init_db()

        audit_logger.info("Enterprise Auth initialized")

    def _init_db(self):
        """Initialise SQLite tables for rate limiting persistence."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS login_attempts (
                    client_key TEXT NOT NULL,
                    attempt_time REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lockouts (
                    client_key TEXT PRIMARY KEY,
                    lockout_time REAL NOT NULL
                )
            """)

    def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security events for audit trail."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'details': details
        }
        audit_logger.info(f"SECURITY_EVENT: {event_type} - {details}")

    def _get_client_key(self) -> str:
        """Get unique client identifier for rate limiting."""
        # In Streamlit, use session ID as a proxy for client
        return st.runtime.scriptrunner.get_script_run_ctx().session_id if hasattr(st, 'runtime') else "default"

    def _is_locked_out(self, client_key: str) -> bool:
        """Check if client is currently locked out (DB-backed)."""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT lockout_time FROM lockouts WHERE client_key = ?", (client_key,)
            ).fetchone()
        if row:
            if time.time() - row[0] < self.lockout_duration:
                return True
            else:
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute("DELETE FROM lockouts WHERE client_key = ?", (client_key,))
        return False

    def _record_failed_attempt(self, client_key: str, username: str):
        """Record failed login attempt and apply lockout if needed."""
        current_time = time.time()
        cutoff = current_time - 3600  # 1-hour window

        with sqlite3.connect(self._db_path) as conn:
            # Clean old attempts
            conn.execute("DELETE FROM login_attempts WHERE client_key = ? AND attempt_time < ?", (client_key, cutoff))
            # Record new attempt
            conn.execute("INSERT INTO login_attempts (client_key, attempt_time) VALUES (?, ?)", (client_key, current_time))
            # Check total
            count = conn.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE client_key = ?", (client_key,)
            ).fetchone()[0]

            if count >= self.max_login_attempts:
                conn.execute(
                    "INSERT OR REPLACE INTO lockouts (client_key, lockout_time) VALUES (?, ?)",
                    (client_key, current_time)
                )
                self._log_security_event('ACCOUNT_LOCKOUT', {
                    'username': username,
                    'attempts_count': count,
                    'lockout_duration_minutes': self.lockout_duration / 60
                })

    def _clear_failed_attempts(self, client_key: str):
        """Clear failed attempts after successful login."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM login_attempts WHERE client_key = ?", (client_key,))

    def _get_remaining_attempts(self, client_key: str) -> int:
        """Return how many attempts remain before lockout."""
        cutoff = time.time() - 3600
        with sqlite3.connect(self._db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE client_key = ? AND attempt_time >= ?",
                (client_key, cutoff)
            ).fetchone()[0]
        return max(0, self.max_login_attempts - count)

    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify login credentials securely (no debug output)."""
        if not username or not password:
            return False
        if not self.admin_username or not self.admin_password:
            audit_logger.error("No credentials configured in environment")
            return False

        username_match = username.strip() == self.admin_username.strip()
        if not username_match:
            return False

        stored_password = self.admin_password.strip()

        # bcrypt check: stored password starts with $2b$ or $2a$
        if BCRYPT_AVAILABLE and stored_password.startswith(('$2b$', '$2a$')):
            try:
                return bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8'))
            except Exception:
                return False

        # Plaintext fallback (warn on first use)
        audit_logger.warning(
            "SECURITY: Password is stored as plaintext. "
            "Hash it with bcrypt and update DASHBOARD_PASSWORD in .env"
        )
        return password.strip() == stored_password

    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated with session validation."""
        if not st.session_state.get("authenticated", False):
            return False

        login_time = st.session_state.get("login_time", 0)
        if time.time() - login_time > self.session_timeout:
            self._log_security_event('SESSION_TIMEOUT', {
                'username': st.session_state.get('username', 'unknown'),
                'session_duration_hours': (time.time() - login_time) / 3600
            })
            self.logout()
            return False

        return True

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """Login with rate limiting and audit logging."""
        client_key = self._get_client_key()

        if self._is_locked_out(client_key):
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute("SELECT lockout_time FROM lockouts WHERE client_key = ?", (client_key,)).fetchone()
            remaining_time = self.lockout_duration - (time.time() - row[0])
            self._log_security_event('LOGIN_ATTEMPT_DURING_LOCKOUT', {'username': username})
            return False, f"Account locked. Try again in {int(remaining_time/60)} minutes."

        if self.verify_credentials(username, password):
            current_time = time.time()
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.login_time = current_time
            self._clear_failed_attempts(client_key)
            self._log_security_event('SUCCESSFUL_LOGIN', {
                'username': username,
                'login_time': datetime.fromtimestamp(current_time).isoformat()
            })
            return True, "Login successful"
        else:
            self._record_failed_attempt(client_key, username)
            remaining = self._get_remaining_attempts(client_key)
            self._log_security_event('FAILED_LOGIN_ATTEMPT', {
                'username': username,
                'remaining_attempts': remaining
            })
            if remaining > 0:
                return False, f"Invalid credentials. {remaining} attempts remaining."
            else:
                return False, "Invalid credentials. Account is now locked."

    def logout(self):
        """Logout with audit logging."""
        username = st.session_state.get('username', 'unknown')
        login_time = st.session_state.get('login_time', time.time())
        session_duration = time.time() - login_time

        self._log_security_event('LOGOUT', {
            'username': username,
            'session_duration_hours': session_duration / 3600
        })

        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.login_time = None

    def require_auth(self):
        """Require authentication before showing any content."""
        if not self.is_authenticated():
            self.show_login_page()
            st.stop()

    def show_login_page(self):
        """Login page."""
        st.set_page_config(
            page_title="Secure Access Required",
            page_icon="🔐",
            layout="centered"
        )

        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            st.markdown("# 🔐 Secure Access")
            st.markdown("### Private Trading Dashboard")
            st.markdown("---")

            client_key = self._get_client_key()
            if self._is_locked_out(client_key):
                with sqlite3.connect(self._db_path) as conn:
                    row = conn.execute("SELECT lockout_time FROM lockouts WHERE client_key = ?", (client_key,)).fetchone()
                remaining_time = self.lockout_duration - (time.time() - row[0])
                st.error("🚫 **Account Locked**")
                st.warning(f"Too many failed attempts. Try again in {int(remaining_time/60)} minutes.")
                return

            remaining_attempts = self._get_remaining_attempts(client_key)
            if remaining_attempts < self.max_login_attempts:
                st.warning(f"⚠️ {remaining_attempts} attempts remaining before lockout")

            with st.form("login_form"):
                st.markdown("#### Enter Your Credentials")
                username = st.text_input("Username", placeholder="Enter username")
                password = st.text_input("Password", type="password", placeholder="Enter password")

                col_a, col_b = st.columns(2)
                with col_a:
                    login_button = st.form_submit_button("🚀 Access Dashboard", use_container_width=True)
                with col_b:
                    if st.form_submit_button("❌ Cancel", use_container_width=True):
                        st.stop()

            if login_button:
                if username and password:
                    success, message = self.login(username, password)
                    if success:
                        st.success("✅ Access Granted! Redirecting...")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                else:
                    st.warning("⚠️ Please enter both username and password")

            st.markdown("---")
            st.markdown("🛡️ **Security Status:**")
            st.markdown(f"• **Session Timeout**: {self.session_timeout/3600:.1f} hours")
            st.markdown(f"• **Rate Limiting**: {self.max_login_attempts} attempts max")
            st.markdown(f"• **Audit Logging**: Enabled")

            st.markdown("---")
            st.markdown(f"🕒 **Server Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            with st.expander("🔧 Troubleshooting"):
                st.markdown("**Common Issues:**")
                st.markdown("• Check username/password in `.env` file")
                st.markdown("• Ensure no extra spaces in credentials")
                st.markdown("• Verify `.env` file is in project root")
                st.markdown("• Check for case sensitivity")


# Create global auth instance
enterprise_auth_manager = EnterpriseAuth()

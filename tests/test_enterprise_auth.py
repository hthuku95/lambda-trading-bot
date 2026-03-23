# tests/test_enterprise_auth.py
"""
Tests for src/auth/enterprise_auth.py

EnterpriseAuth is tightly coupled to Streamlit (st.session_state).
All Streamlit calls are mocked via SessionStateProxy + targeted patches.
DB auth_store calls are mocked so no live DB is needed.
"""
import time
import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_session(**kwargs):
    """Return a SessionStateProxy pre-populated with kwargs."""
    from tests.conftest import SessionStateProxy
    return SessionStateProxy(kwargs)


def _make_auth(username="testuser", password_hash=None, plaintext_pw=None, session=None):
    """
    Build an EnterpriseAuth instance with patched env vars.
    Pass either a bcrypt hash or a plaintext password.
    """
    if password_hash is None and plaintext_pw is not None:
        password_hash = plaintext_pw  # plaintext — triggers fallback path
    env = {
        "DASHBOARD_USERNAME": username,
        "DASHBOARD_PASSWORD": password_hash,
        "SESSION_TIMEOUT_HOURS": "8",
        "MAX_LOGIN_ATTEMPTS": "5",
        "LOCKOUT_DURATION_MINUTES": "15",
    }
    if session is None:
        session = _make_session()
    with patch.dict("os.environ", env), \
         patch("streamlit.session_state", session), \
         patch("logging.FileHandler"), \
         patch("os.makedirs"):
        from importlib import reload
        import src.auth.enterprise_auth as ea_module
        reload(ea_module)
        return ea_module.EnterpriseAuth()


def _bcrypt_hash(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# ─────────────────────────────────────────────────────────────────────────────
# verify_credentials()
# ─────────────────────────────────────────────────────────────────────────────

class TestVerifyCredentials:
    def test_correct_bcrypt_password_returns_true(self):
        pw = "secret123"
        hashed = _bcrypt_hash(pw)
        auth = _make_auth(password_hash=hashed)
        assert auth.verify_credentials("testuser", pw) is True

    def test_wrong_bcrypt_password_returns_false(self):
        hashed = _bcrypt_hash("correct_password")
        auth = _make_auth(password_hash=hashed)
        assert auth.verify_credentials("testuser", "wrong_password") is False

    def test_wrong_username_returns_false(self):
        hashed = _bcrypt_hash("password")
        auth = _make_auth(password_hash=hashed)
        assert auth.verify_credentials("wrong_user", "password") is False

    def test_plaintext_password_fallback_returns_true(self):
        auth = _make_auth(plaintext_pw="myplainpassword")
        assert auth.verify_credentials("testuser", "myplainpassword") is True

    def test_plaintext_wrong_password_returns_false(self):
        auth = _make_auth(plaintext_pw="correct")
        assert auth.verify_credentials("testuser", "wrong") is False

    def test_empty_username_returns_false(self):
        auth = _make_auth(plaintext_pw="pw")
        assert auth.verify_credentials("", "pw") is False

    def test_empty_password_returns_false(self):
        auth = _make_auth(plaintext_pw="pw")
        assert auth.verify_credentials("testuser", "") is False

    def test_no_credentials_configured_returns_false(self):
        env = {"DASHBOARD_USERNAME": "", "DASHBOARD_PASSWORD": ""}
        with patch.dict("os.environ", env), \
             patch("streamlit.session_state", _make_session()), \
             patch("logging.FileHandler"), \
             patch("os.makedirs"):
            from importlib import reload
            import src.auth.enterprise_auth as ea
            reload(ea)
            auth = ea.EnterpriseAuth()
        assert auth.verify_credentials("testuser", "password") is False


# ─────────────────────────────────────────────────────────────────────────────
# is_authenticated()
# ─────────────────────────────────────────────────────────────────────────────

class TestIsAuthenticated:
    def test_returns_false_when_no_authenticated_key(self):
        session = _make_session()
        with patch("streamlit.session_state", session), \
             patch("logging.FileHandler"), patch("os.makedirs"):
            from importlib import reload
            import src.auth.enterprise_auth as ea
            reload(ea)
            auth = ea.EnterpriseAuth()
            result = auth.is_authenticated()
        assert result is False

    def test_returns_false_when_authenticated_is_false(self):
        session = _make_session(authenticated=False)
        with patch("streamlit.session_state", session), \
             patch("logging.FileHandler"), patch("os.makedirs"):
            from importlib import reload
            import src.auth.enterprise_auth as ea
            reload(ea)
            auth = ea.EnterpriseAuth()
            result = auth.is_authenticated()
        assert result is False

    def test_returns_true_when_session_valid(self):
        session = _make_session(authenticated=True, login_time=time.time())
        with patch("streamlit.session_state", session), \
             patch("logging.FileHandler"), patch("os.makedirs"):
            from importlib import reload
            import src.auth.enterprise_auth as ea
            reload(ea)
            auth = ea.EnterpriseAuth()
            result = auth.is_authenticated()
        assert result is True

    def test_returns_false_when_session_expired(self):
        old_time = time.time() - (9 * 3600)  # 9 hours ago, timeout is 8h
        session = _make_session(authenticated=True, login_time=old_time, username="user")
        with patch("streamlit.session_state", session), \
             patch("logging.FileHandler"), patch("os.makedirs"):
            from importlib import reload
            import src.auth.enterprise_auth as ea
            reload(ea)
            auth = ea.EnterpriseAuth()
            result = auth.is_authenticated()
        assert result is False
        # Session must be cleared
        assert session.get("authenticated") is False


# ─────────────────────────────────────────────────────────────────────────────
# login()
# ─────────────────────────────────────────────────────────────────────────────

class TestLogin:
    def _make_auth_with_session(self, session_dict, plaintext_pw="testpass"):
        env = {
            "DASHBOARD_USERNAME": "testuser",
            "DASHBOARD_PASSWORD": plaintext_pw,
            "SESSION_TIMEOUT_HOURS": "8",
            "MAX_LOGIN_ATTEMPTS": "5",
            "LOCKOUT_DURATION_MINUTES": "15",
        }
        with patch.dict("os.environ", env), \
             patch("streamlit.session_state", session_dict), \
             patch("logging.FileHandler"), \
             patch("os.makedirs"):
            from importlib import reload
            import src.auth.enterprise_auth as ea
            reload(ea)
            return ea.EnterpriseAuth()

    def test_successful_login_sets_session(self):
        session = _make_session()
        auth = self._make_auth_with_session(session)
        with patch("streamlit.session_state", session), \
             patch.object(auth, "_get_client_key", return_value="default"), \
             patch.object(auth, "_is_locked_out", return_value=False), \
             patch.object(auth, "_clear_failed_attempts"), \
             patch("src.db.auth_store.log_auth_event"):
            success, msg = auth.login("testuser", "testpass")
        assert success is True
        assert session.get("authenticated") is True
        assert session.get("username") == "testuser"
        assert "login_time" in session

    def test_failed_login_calls_record_failed_attempt(self):
        session = _make_session()
        auth = self._make_auth_with_session(session)
        with patch("streamlit.session_state", session), \
             patch.object(auth, "_get_client_key", return_value="default"), \
             patch.object(auth, "_is_locked_out", return_value=False), \
             patch.object(auth, "_record_failed_attempt") as mock_record, \
             patch.object(auth, "_get_remaining_attempts", return_value=3), \
             patch("src.db.auth_store.log_auth_event"):
            success, msg = auth.login("testuser", "wrongpassword")
        assert success is False
        mock_record.assert_called_once_with("default", "testuser")

    def test_locked_out_returns_false_without_checking_password(self):
        session = _make_session()
        auth = self._make_auth_with_session(session)
        with patch("streamlit.session_state", session), \
             patch.object(auth, "_get_client_key", return_value="default"), \
             patch.object(auth, "_is_locked_out", return_value=True), \
             patch.object(auth, "verify_credentials") as mock_verify:
            success, msg = auth.login("testuser", "anypass")
        assert success is False
        mock_verify.assert_not_called()

    def test_failed_login_shows_remaining_attempts(self):
        session = _make_session()
        auth = self._make_auth_with_session(session)
        with patch("streamlit.session_state", session), \
             patch.object(auth, "_get_client_key", return_value="default"), \
             patch.object(auth, "_is_locked_out", return_value=False), \
             patch.object(auth, "_record_failed_attempt"), \
             patch.object(auth, "_get_remaining_attempts", return_value=2), \
             patch("src.db.auth_store.log_auth_event"):
            success, msg = auth.login("testuser", "wrong")
        assert "2 attempts" in msg


# ─────────────────────────────────────────────────────────────────────────────
# logout()
# ─────────────────────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_clears_session_state(self):
        session = _make_session(
            authenticated=True,
            username="testuser",
            login_time=time.time(),
        )
        env = {"DASHBOARD_USERNAME": "testuser", "DASHBOARD_PASSWORD": "pw"}
        with patch.dict("os.environ", env), \
             patch("streamlit.session_state", session), \
             patch("logging.FileHandler"), \
             patch("os.makedirs"):
            from importlib import reload
            import src.auth.enterprise_auth as ea
            reload(ea)
            auth = ea.EnterpriseAuth()
        with patch("streamlit.session_state", session):
            auth.logout()
        assert session["authenticated"] is False
        assert session["username"] is None
        assert session["login_time"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Rate limiting helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestRateLimitingHelpers:
    def _make_auth_bare(self):
        env = {
            "DASHBOARD_USERNAME": "u",
            "DASHBOARD_PASSWORD": "p",
            "SESSION_TIMEOUT_HOURS": "8",
            "MAX_LOGIN_ATTEMPTS": "5",
            "LOCKOUT_DURATION_MINUTES": "15",
        }
        with patch.dict("os.environ", env), \
             patch("streamlit.session_state", _make_session()), \
             patch("logging.FileHandler"), \
             patch("os.makedirs"):
            from importlib import reload
            import src.auth.enterprise_auth as ea
            reload(ea)
            return ea.EnterpriseAuth()

    def test_is_locked_out_delegates_to_auth_store(self):
        auth = self._make_auth_bare()
        with patch("src.db.auth_store.is_locked_out", return_value=True) as mock_lo:
            result = auth._is_locked_out("key")
        assert result is True
        mock_lo.assert_called_once_with("key")

    def test_is_locked_out_returns_false_on_exception(self):
        auth = self._make_auth_bare()
        with patch("src.db.auth_store.is_locked_out", side_effect=Exception("err")):
            result = auth._is_locked_out("key")
        assert result is False

    def test_get_remaining_attempts_delegates_to_auth_store(self):
        auth = self._make_auth_bare()
        with patch("src.db.auth_store.get_remaining_attempts", return_value=3):
            result = auth._get_remaining_attempts("key")
        assert result == 3

    def test_get_remaining_attempts_returns_max_on_exception(self):
        auth = self._make_auth_bare()
        with patch("src.db.auth_store.get_remaining_attempts", side_effect=Exception):
            result = auth._get_remaining_attempts("key")
        assert result == auth.max_login_attempts

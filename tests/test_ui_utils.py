# tests/test_ui_utils.py
"""
Tests for ui/utils.py

load_dashboard_data() and initialize_session_state() are tested
with mocked Streamlit and agent state functions.
"""
import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# load_dashboard_data()
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadDashboardData:
    EXPECTED_KEYS = {"agent_state", "wallet_balance", "cache_stats", "memory_stats"}

    @pytest.fixture(autouse=True)
    def reloaded_ui_utils(self):
        """
        Reload ui.utils with cache_data patched as identity so the
        @st.cache_data decorator is stripped.  Must happen BEFORE individual
        ui.utils.* patches so the reload does not overwrite them.
        """
        with patch("streamlit.cache_data", lambda **kw: lambda f: f):
            from importlib import reload
            import ui.utils
            reload(ui.utils)
            yield ui.utils

    def test_returns_dict_with_all_expected_keys(self, initial_state, reloaded_ui_utils):
        with patch("ui.utils.load_agent_state", return_value=initial_state), \
             patch("ui.utils.create_initial_state", return_value=initial_state), \
             patch("ui.utils.get_wallet_balance", return_value=5.0), \
             patch("ui.utils.get_cache_stats", return_value={}), \
             patch("ui.utils.get_memory_stats", return_value={}):
            result = reloaded_ui_utils.load_dashboard_data()
        assert self.EXPECTED_KEYS.issubset(result.keys())

    def test_agent_state_is_never_none_when_no_json_file(self, initial_state, reloaded_ui_utils):
        """
        The critical fix: load_agent_state() returns None on fresh deployment.
        load_dashboard_data() must fall back to create_initial_state() so
        agent_state is NEVER None.
        """
        with patch("ui.utils.load_agent_state", return_value=None), \
             patch("ui.utils.create_initial_state", return_value=initial_state), \
             patch("ui.utils.get_wallet_balance", return_value=0.0), \
             patch("ui.utils.get_cache_stats", return_value={}), \
             patch("ui.utils.get_memory_stats", return_value={}):
            result = reloaded_ui_utils.load_dashboard_data()
        assert result["agent_state"] is not None
        assert isinstance(result["agent_state"], dict)

    def test_agent_state_uses_existing_state_when_available(self, initial_state, reloaded_ui_utils):
        initial_state["cycles_completed"] = 42
        with patch("ui.utils.load_agent_state", return_value=initial_state), \
             patch("ui.utils.create_initial_state") as mock_create, \
             patch("ui.utils.get_wallet_balance", return_value=5.0), \
             patch("ui.utils.get_cache_stats", return_value={}), \
             patch("ui.utils.get_memory_stats", return_value={}):
            result = reloaded_ui_utils.load_dashboard_data()
        mock_create.assert_not_called()
        assert result["agent_state"]["cycles_completed"] == 42

    def test_wallet_balance_included_in_result(self, initial_state, reloaded_ui_utils):
        with patch("ui.utils.load_agent_state", return_value=initial_state), \
             patch("ui.utils.create_initial_state", return_value=initial_state), \
             patch("ui.utils.get_wallet_balance", return_value=7.5), \
             patch("ui.utils.get_cache_stats", return_value={}), \
             patch("ui.utils.get_memory_stats", return_value={}):
            result = reloaded_ui_utils.load_dashboard_data()
        assert result["wallet_balance"] == 7.5

    def test_error_fallback_returns_valid_dict_with_initial_state(self, initial_state, reloaded_ui_utils):
        """If any sub-call raises, the error branch must still return a valid dict."""
        with patch("ui.utils.load_agent_state", side_effect=Exception("state load error")), \
             patch("ui.utils.create_initial_state", return_value=initial_state), \
             patch("ui.utils.get_wallet_balance", return_value=0), \
             patch("ui.utils.get_cache_stats", return_value={}), \
             patch("ui.utils.get_memory_stats", return_value={}), \
             patch("streamlit.error"):
            result = reloaded_ui_utils.load_dashboard_data()
        assert isinstance(result, dict)
        assert result["agent_state"] is not None
        assert result["wallet_balance"] == 0

    def test_cache_stats_and_memory_stats_included(self, initial_state, reloaded_ui_utils):
        with patch("ui.utils.load_agent_state", return_value=initial_state), \
             patch("ui.utils.create_initial_state", return_value=initial_state), \
             patch("ui.utils.get_wallet_balance", return_value=0.0), \
             patch("ui.utils.get_cache_stats", return_value={"hits": 10}), \
             patch("ui.utils.get_memory_stats", return_value={"size": 500}):
            result = reloaded_ui_utils.load_dashboard_data()
        assert result["cache_stats"] == {"hits": 10}
        assert result["memory_stats"] == {"size": 500}


# ─────────────────────────────────────────────────────────────────────────────
# initialize_session_state()
# ─────────────────────────────────────────────────────────────────────────────

class TestInitializeSessionState:
    EXPECTED_SESSION_KEYS = {"agent_running", "agent_thread", "agent_parameters", "trading_mode"}
    EXPECTED_PARAMETER_KEYS = {
        "dry_run", "max_positions", "max_position_size_sol",
        "min_position_size_sol", "cycle_time_seconds", "risk_tolerance"
    }

    @pytest.fixture
    def fresh_session(self):
        """
        SessionStateProxy supports both dict-style and attribute-style access
        so that `st.session_state.key = value` works in tests.
        """
        from tests.conftest import SessionStateProxy
        return SessionStateProxy()

    def test_sets_all_expected_keys_on_fresh_session(self, fresh_session):
        with patch("streamlit.session_state", fresh_session), \
             patch("streamlit.cache_data", lambda **kw: lambda f: f):
            from importlib import reload
            import ui.utils
            reload(ui.utils)
            ui.utils.initialize_session_state()
        assert self.EXPECTED_SESSION_KEYS.issubset(fresh_session.keys())

    def test_agent_running_defaults_to_false(self, fresh_session):
        with patch("streamlit.session_state", fresh_session), \
             patch("streamlit.cache_data", lambda **kw: lambda f: f):
            from importlib import reload
            import ui.utils
            reload(ui.utils)
            ui.utils.initialize_session_state()
        assert fresh_session["agent_running"] is False

    def test_agent_thread_defaults_to_none(self, fresh_session):
        with patch("streamlit.session_state", fresh_session), \
             patch("streamlit.cache_data", lambda **kw: lambda f: f):
            from importlib import reload
            import ui.utils
            reload(ui.utils)
            ui.utils.initialize_session_state()
        assert fresh_session["agent_thread"] is None

    def test_agent_parameters_has_all_expected_keys(self, fresh_session):
        with patch("streamlit.session_state", fresh_session), \
             patch("streamlit.cache_data", lambda **kw: lambda f: f):
            from importlib import reload
            import ui.utils
            reload(ui.utils)
            ui.utils.initialize_session_state()
        assert self.EXPECTED_PARAMETER_KEYS.issubset(fresh_session["agent_parameters"].keys())

    def test_dry_run_defaults_to_true(self, fresh_session):
        with patch("streamlit.session_state", fresh_session), \
             patch("streamlit.cache_data", lambda **kw: lambda f: f):
            from importlib import reload
            import ui.utils
            reload(ui.utils)
            ui.utils.initialize_session_state()
        assert fresh_session["agent_parameters"]["dry_run"] is True

    def test_idempotent_does_not_overwrite_existing_values(self, fresh_session):
        """Calling twice must not overwrite user-set values."""
        fresh_session["agent_running"] = True  # user set this
        with patch("streamlit.session_state", fresh_session), \
             patch("streamlit.cache_data", lambda **kw: lambda f: f):
            from importlib import reload
            import ui.utils
            reload(ui.utils)
            ui.utils.initialize_session_state()
            ui.utils.initialize_session_state()  # second call
        assert fresh_session["agent_running"] is True  # preserved

    def test_trading_mode_defaults_to_custom(self, fresh_session):
        with patch("streamlit.session_state", fresh_session), \
             patch("streamlit.cache_data", lambda **kw: lambda f: f):
            from importlib import reload
            import ui.utils
            reload(ui.utils)
            ui.utils.initialize_session_state()
        assert fresh_session["trading_mode"] == "custom"

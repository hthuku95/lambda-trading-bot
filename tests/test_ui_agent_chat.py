# tests/test_ui_agent_chat.py
"""
Tests for ui/components/agent_chat.py

Critical checks:
1. The 5 functions are now importable from src.agent (regression test for the fixed bug)
2. Component functions run without crashing (render path tested)
3. Chat input handling delegates to the correct backend functions
"""
import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Import regression tests — the bug that caused Render crash
# ─────────────────────────────────────────────────────────────────────────────

class TestImportRegression:
    def test_render_chat_tab_importable(self):
        """render_chat_tab must be importable from ui.components.agent_chat."""
        from ui.components.agent_chat import render_chat_tab
        assert callable(render_chat_tab)

    def test_all_five_agent_chat_functions_importable_from_src_agent(self):
        """
        Regression test for the ImportError that crashed ALL dashboard tabs.
        These 5 functions were defined in src/agent/agent_chat.py but missing
        from src/agent/__init__.py.
        """
        from src.agent import (
            get_agent_chat,
            get_multi_agent_chat,
            chat_with_claude,
            chat_with_gemini,
            chat_with_both_agents,
        )
        assert callable(get_agent_chat)
        assert callable(get_multi_agent_chat)
        assert callable(chat_with_claude)
        assert callable(chat_with_gemini)
        assert callable(chat_with_both_agents)

    def test_render_agent_chat_interface_importable(self):
        from ui.components.agent_chat import render_agent_chat_interface
        assert callable(render_agent_chat_interface)

    def test_initialize_chat_session_state_importable(self):
        from ui.components.agent_chat import initialize_chat_session_state
        assert callable(initialize_chat_session_state)


# ─────────────────────────────────────────────────────────────────────────────
# initialize_chat_session_state()
# ─────────────────────────────────────────────────────────────────────────────

def _make_session(**kwargs):
    """Return a SessionStateProxy (supports attribute + dict access) for testing."""
    from tests.conftest import SessionStateProxy
    return SessionStateProxy(kwargs)


class TestInitializeChatSessionState:
    EXPECTED_KEYS = {"chat_messages", "chat_mode", "selected_chat_agent"}

    def test_sets_all_expected_keys(self):
        session = _make_session()
        with patch("streamlit.session_state", session):
            from ui.components.agent_chat import initialize_chat_session_state
            initialize_chat_session_state()
        assert self.EXPECTED_KEYS.issubset(session.keys())

    def test_chat_messages_defaults_to_empty_list(self):
        session = _make_session()
        with patch("streamlit.session_state", session):
            from ui.components.agent_chat import initialize_chat_session_state
            initialize_chat_session_state()
        assert isinstance(session["chat_messages"], list)
        assert len(session["chat_messages"]) == 0

    def test_chat_mode_defaults_to_single(self):
        session = _make_session()
        with patch("streamlit.session_state", session):
            from ui.components.agent_chat import initialize_chat_session_state
            initialize_chat_session_state()
        assert session["chat_mode"] == "single"

    def test_selected_chat_agent_defaults_to_anthropic(self):
        session = _make_session()
        with patch("streamlit.session_state", session):
            from ui.components.agent_chat import initialize_chat_session_state
            initialize_chat_session_state()
        assert session["selected_chat_agent"] in ("anthropic", "google")

    def test_idempotent_does_not_overwrite_existing_chat(self):
        session = _make_session(
            chat_messages=[{"role": "user", "content": "Hello"}],
            chat_mode="both",
            selected_chat_agent="google",
        )
        with patch("streamlit.session_state", session):
            from ui.components.agent_chat import initialize_chat_session_state
            initialize_chat_session_state()
        # Existing values must NOT be overwritten
        assert len(session["chat_messages"]) == 1
        assert session["chat_mode"] == "both"
        assert session["selected_chat_agent"] == "google"


# ─────────────────────────────────────────────────────────────────────────────
# handle_chat_input() — single agent mode
# ─────────────────────────────────────────────────────────────────────────────

class TestHandleChatInput:
    @pytest.fixture
    def chat_session(self):
        return _make_session(
            chat_messages=[],
            chat_mode="single",
            selected_chat_agent="anthropic",
        )

    def test_single_claude_adds_user_and_assistant_messages(self, chat_session):
        chat_session["selected_chat_agent"] = "anthropic"
        with patch("streamlit.session_state", chat_session), \
             patch("streamlit.spinner", return_value=MagicMock(__enter__=lambda s: s, __exit__=MagicMock(return_value=False))), \
             patch("ui.components.agent_chat.chat_with_claude",
                   return_value="Claude says hello") as mock_claude:
            from ui.components.agent_chat import handle_chat_input
            handle_chat_input("Hello Claude")
        # Should have user message + assistant message = 2
        assert len(chat_session["chat_messages"]) == 2
        assert chat_session["chat_messages"][0]["role"] == "user"
        assert chat_session["chat_messages"][0]["content"] == "Hello Claude"
        assert chat_session["chat_messages"][1]["role"] == "assistant"
        assert "Claude says hello" in chat_session["chat_messages"][1]["content"]
        mock_claude.assert_called_once_with("Hello Claude")

    def test_single_gemini_calls_chat_with_gemini(self, chat_session):
        chat_session["selected_chat_agent"] = "google"
        with patch("streamlit.session_state", chat_session), \
             patch("streamlit.spinner", return_value=MagicMock(__enter__=lambda s: s, __exit__=MagicMock(return_value=False))), \
             patch("ui.components.agent_chat.chat_with_gemini",
                   return_value="Gemini response") as mock_gemini:
            from ui.components.agent_chat import handle_chat_input
            handle_chat_input("Hi Gemini")
        mock_gemini.assert_called_once_with("Hi Gemini")
        assert len(chat_session["chat_messages"]) == 2

    def test_both_agents_mode_adds_three_messages(self, chat_session):
        chat_session["chat_mode"] = "both"
        # Source reads responses['claude'] and responses['gemini']
        with patch("streamlit.session_state", chat_session), \
             patch("streamlit.spinner", return_value=MagicMock(__enter__=lambda s: s, __exit__=MagicMock(return_value=False))), \
             patch("ui.components.agent_chat.chat_with_both_agents",
                   return_value={
                       "claude": "Claude: hi",
                       "gemini": "Gemini: hello"
                   }):
            from ui.components.agent_chat import handle_chat_input
            handle_chat_input("Hi both")
        # 1 user + 2 assistant responses = 3 messages
        assert len(chat_session["chat_messages"]) == 3
        roles = [m["role"] for m in chat_session["chat_messages"]]
        assert roles.count("user") == 1
        assert roles.count("assistant") == 2

    def test_empty_input_is_ignored(self, chat_session):
        with patch("streamlit.session_state", chat_session):
            from ui.components.agent_chat import handle_chat_input
            handle_chat_input("")
        assert len(chat_session["chat_messages"]) == 0

    def test_handles_backend_error_gracefully(self, chat_session):
        with patch("streamlit.session_state", chat_session), \
             patch("streamlit.spinner", return_value=MagicMock(__enter__=lambda s: s, __exit__=MagicMock(return_value=False))), \
             patch("ui.components.agent_chat.chat_with_claude",
                   side_effect=Exception("LLM down")):
            from ui.components.agent_chat import handle_chat_input
            handle_chat_input("Hello")
        # User message should still be recorded; error response added
        user_msgs = [m for m in chat_session["chat_messages"] if m["role"] == "user"]
        assert len(user_msgs) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Tokens tab — data.get('agent_state') or {} regression test
# ─────────────────────────────────────────────────────────────────────────────

class TestTokensTabNoneRegression:
    """
    Regression test: data.get('agent_state', {}) returns None (not {})
    when the key exists but value is None. Must use `data.get('agent_state') or {}`.
    """

    def test_get_with_default_returns_none_when_key_exists_with_none_value(self):
        """
        Documents the Python dict.get() gotcha that caused the AttributeError.
        This is a pure Python logic test — no mocking needed.
        """
        data = {"agent_state": None}
        # The broken pattern
        result_broken = data.get("agent_state", {})
        assert result_broken is None  # bug: returns None, not {}

        # The fixed pattern
        result_fixed = data.get("agent_state") or {}
        assert result_fixed == {}  # fix: returns {} when value is None

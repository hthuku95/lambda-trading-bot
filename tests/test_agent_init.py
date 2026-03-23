# tests/test_agent_init.py
"""
Tests for src/agent/__init__.py

Verifies:
- Every name in __all__ is importable from src.agent
- The 5 agent_chat functions are now exported (the bug that was fixed)
- Background agent thread management (start / stop / status)
"""
import importlib
import threading
import time
import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Import surface
# ─────────────────────────────────────────────────────────────────────────────

class TestExports:
    """All names in __all__ must be importable without error."""

    def test_module_importable(self):
        import src.agent  # must not raise

    def test_all_exports_importable(self):
        import src.agent as agent_module
        for name in agent_module.__all__:
            assert hasattr(agent_module, name), f"'{name}' declared in __all__ but not importable"

    def test_agent_chat_functions_exported(self):
        """The 5 functions that were missing and caused the Render ImportError."""
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

    def test_state_functions_exported(self):
        from src.agent import (
            load_agent_state,
            save_agent_state,
            create_initial_state,
            update_portfolio_metrics,
            get_state_summary,
        )
        assert callable(load_agent_state)
        assert callable(create_initial_state)

    def test_background_management_exported(self):
        from src.agent import (
            start_agent_background,
            stop_agent_background,
            get_agent_status,
            run_trading_agent,
        )
        assert callable(start_agent_background)
        assert callable(stop_agent_background)
        assert callable(get_agent_status)
        assert callable(run_trading_agent)

    def test_multi_agent_functions_exported(self):
        from src.agent import (
            start_demo_parallel_mode,
            start_live_hybrid_mode,
            stop_multi_agent_system,
            get_multi_agent_status,
            is_multi_agent_running,
        )
        assert callable(start_demo_parallel_mode)
        assert callable(is_multi_agent_running)

    def test_type_exports(self):
        from src.agent import AgentState, TokenData, Position
        # These are TypedDicts — just confirm they exist
        assert AgentState is not None
        assert TokenData is not None
        assert Position is not None


# ─────────────────────────────────────────────────────────────────────────────
# get_agent_status()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetAgentStatus:
    """get_agent_status() must always return a valid dict with all expected keys."""

    EXPECTED_KEYS = {
        "running", "thread_alive", "cycles_completed",
        "last_update", "wallet_balance_sol", "active_positions",
        "tools_used_last_cycle", "agent_type",
    }

    def test_status_returns_dict_when_no_state_file(self):
        with patch("src.agent.load_agent_state", return_value=None):
            from src.agent import get_agent_status
            status = get_agent_status()
        assert isinstance(status, dict)
        assert self.EXPECTED_KEYS.issubset(status.keys())

    def test_status_running_false_initially(self):
        import src.agent as agent_module
        agent_module._agent_running = False
        with patch("src.agent.load_agent_state", return_value=None):
            status = agent_module.get_agent_status()
        assert status["running"] is False

    def test_status_reads_cycles_from_state(self):
        mock_state = {"cycles_completed": 42, "last_update_timestamp": "2026-01-01",
                      "wallet_balance_sol": 5.0, "active_positions": [], "tools_used_this_cycle": []}
        with patch("src.agent.load_agent_state", return_value=mock_state):
            from src.agent import get_agent_status
            status = get_agent_status()
        assert status["cycles_completed"] == 42
        assert status["wallet_balance_sol"] == 5.0

    def test_status_thread_alive_false_when_no_thread(self):
        import src.agent as agent_module
        agent_module._agent_thread = None
        with patch("src.agent.load_agent_state", return_value=None):
            status = agent_module.get_agent_status()
        assert status["thread_alive"] is False

    def test_agent_type_is_langgraph(self):
        with patch("src.agent.load_agent_state", return_value=None):
            from src.agent import get_agent_status
            status = get_agent_status()
        assert status["agent_type"] == "LangGraph_Enhanced"


# ─────────────────────────────────────────────────────────────────────────────
# start_agent_background() / stop_agent_background()
# ─────────────────────────────────────────────────────────────────────────────

class TestBackgroundAgent:
    """Tests for the background thread lifecycle."""

    @pytest.fixture(autouse=True)
    def reset_globals(self):
        """Ensure clean state before and after each test."""
        import src.agent as agent_module
        agent_module._agent_running = False
        agent_module._agent_stop_flag = False
        agent_module._agent_thread = None
        agent_module._agent_instance = None
        yield
        agent_module._agent_stop_flag = True
        agent_module._agent_running = False
        agent_module._agent_thread = None
        agent_module._agent_instance = None

    def test_start_returns_true_when_not_running(self):
        """start_agent_background() spawns a daemon thread and returns True."""
        with patch("src.agent.run_trading_agent", side_effect=Exception("stop")), \
             patch("src.agent.CompleteLangGraphTradingAgent"):
            from src.agent import start_agent_background
            result = start_agent_background({"cycle_time_seconds": 1})
        assert result is True

    def test_start_returns_false_when_already_running(self):
        import src.agent as agent_module
        agent_module._agent_running = True
        from src.agent import start_agent_background
        result = start_agent_background()
        assert result is False

    def test_stop_returns_true_when_not_running(self):
        import src.agent as agent_module
        agent_module._agent_running = False
        from src.agent import stop_agent_background
        result = stop_agent_background()
        assert result is True

    def test_stop_sets_stop_flag(self):
        import src.agent as agent_module
        agent_module._agent_running = True  # Pretend it's running

        # Immediately flip _agent_running so stop() doesn't wait forever
        def flip(*args, **kwargs):
            agent_module._agent_running = False

        with patch("src.agent.time.sleep", side_effect=flip):
            from src.agent import stop_agent_background
            stop_agent_background()

        assert agent_module._agent_stop_flag is True

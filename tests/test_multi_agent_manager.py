# tests/test_multi_agent_manager.py
"""
Tests for src/agent/multi_agent_manager.py

MultiAgentCoordinator and the public API functions are tested with mocked
trading cycles. Threading behaviour is tested with real threads (short-lived)
so we verify start/stop semantics without mocking away all concurrency.
"""
import time
import threading
import pytest
from unittest.mock import patch, MagicMock, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_coordinator():
    """Return a fresh MultiAgentCoordinator (not the global singleton)."""
    from src.agent.multi_agent_manager import MultiAgentCoordinator
    return MultiAgentCoordinator()


BASE_PARAMS = {
    "dry_run": True,
    "trading_mode": "dry_run",
    "cycle_time_seconds": 1,
    "max_positions": 3,
    "max_position_size_sol": 0.5,
}


# ---------------------------------------------------------------------------
# MultiAgentCoordinator.get_status() — no threads running
# ---------------------------------------------------------------------------

class TestGetStatusNotRunning:
    def test_returns_dict_with_expected_top_level_keys(self):
        coord = _make_coordinator()
        status = coord.get_status()
        for key in ("coordinator_mode", "live_model", "agents", "any_running", "all_running", "timestamp"):
            assert key in status

    def test_any_running_false_when_idle(self):
        coord = _make_coordinator()
        assert coord.get_status()["any_running"] is False

    def test_all_running_false_when_idle(self):
        coord = _make_coordinator()
        assert coord.get_status()["all_running"] is False

    def test_coordinator_mode_none_when_idle(self):
        coord = _make_coordinator()
        assert coord.get_status()["coordinator_mode"] is None

    def test_agents_dict_has_both_providers(self):
        coord = _make_coordinator()
        agents = coord.get_status()["agents"]
        assert "anthropic" in agents
        assert "google" in agents

    def test_agents_running_false_when_idle(self):
        coord = _make_coordinator()
        agents = coord.get_status()["agents"]
        assert agents["anthropic"]["running"] is False
        assert agents["google"]["running"] is False

    def test_get_status_does_not_raise_on_empty_coordinator(self):
        coord = _make_coordinator()
        # Should never raise even when called on a completely fresh instance
        status = coord.get_status()
        assert isinstance(status, dict)


# ---------------------------------------------------------------------------
# MultiAgentCoordinator.start_demo_parallel() — mocked cycle
# ---------------------------------------------------------------------------

class TestStartDemoParallel:
    @pytest.fixture
    def mock_cycle(self):
        """Mock run_langgraph_trading_cycle so no real trading happens."""
        with patch("src.agent.multi_agent_manager.run_langgraph_trading_cycle",
                   return_value=_fresh_state(cycles_completed=1)) as mock_run, \
             patch("src.agent.multi_agent_manager.save_agent_state"), \
             patch("src.agent.multi_agent_manager.load_agent_state", return_value=None), \
             patch("src.agent.multi_agent_manager.create_initial_state",
                   side_effect=_fresh_state):
            yield mock_run

    def test_start_demo_parallel_sets_mode(self, mock_cycle):
        coord = _make_coordinator()
        # Immediately set stop flags after start so threads terminate quickly
        coord.start_demo_parallel(BASE_PARAMS)
        assert coord.mode == "demo_parallel"
        coord.stop_all()

    def test_start_demo_parallel_live_model_is_none(self, mock_cycle):
        coord = _make_coordinator()
        coord.start_demo_parallel(BASE_PARAMS)
        assert coord.live_model is None
        coord.stop_all()

    def test_start_demo_parallel_creates_two_threads(self, mock_cycle):
        coord = _make_coordinator()
        coord.start_demo_parallel(BASE_PARAMS)
        assert len(coord.threads) == 2
        coord.stop_all()

    def test_start_demo_parallel_both_providers_in_threads(self, mock_cycle):
        coord = _make_coordinator()
        coord.start_demo_parallel(BASE_PARAMS)
        assert "anthropic" in coord.threads
        assert "google" in coord.threads
        coord.stop_all()

    def test_start_demo_parallel_returns_true_on_success(self, mock_cycle):
        coord = _make_coordinator()
        result = coord.start_demo_parallel(BASE_PARAMS)
        assert result is True
        coord.stop_all()

    def test_start_demo_parallel_agent_params_have_dry_run(self, mock_cycle):
        """Both agents must be set to dry_run regardless of what was in parameters."""
        params = BASE_PARAMS.copy()
        params["trading_mode"] = "live"  # Should be overridden to dry_run
        coord = _make_coordinator()
        coord.start_demo_parallel(params)
        # Check states — trading_mode should be dry_run
        for provider in ["anthropic", "google"]:
            state = coord.states.get(provider, {})
            agent_params = state.get("agent_parameters", {})
            assert agent_params.get("trading_mode") == "dry_run", \
                f"{provider} must use dry_run in demo parallel mode"
        coord.stop_all()


# ---------------------------------------------------------------------------
# MultiAgentCoordinator.start_live_hybrid() — mocked cycle
# ---------------------------------------------------------------------------

def _fresh_state(**overrides):
    """Return a fresh dict (never the same object twice) for create_initial_state mocks."""
    base = dict(
        cycles_completed=0,
        wallet_balance_sol=10.0,
        active_positions=[],
        error=None,
        tools_used_this_cycle=[],
        agent_parameters=BASE_PARAMS.copy(),
    )
    base.update(overrides)
    return base


class TestStartLiveHybrid:
    @pytest.fixture
    def mock_cycle(self):
        # Preserve agent_parameters from the input state so thread updates don't overwrite them
        def _cycle_preserve_params(state):
            return {**_fresh_state(cycles_completed=1),
                    "agent_parameters": state.get("agent_parameters", BASE_PARAMS.copy())}

        with patch("src.agent.multi_agent_manager.run_langgraph_trading_cycle",
                   side_effect=_cycle_preserve_params), \
             patch("src.agent.multi_agent_manager.save_agent_state"), \
             patch("src.agent.multi_agent_manager.load_agent_state", return_value=None), \
             patch("src.agent.multi_agent_manager.create_initial_state",
                   side_effect=_fresh_state):
            yield

    def test_start_live_hybrid_sets_mode(self, mock_cycle):
        coord = _make_coordinator()
        coord.start_live_hybrid("anthropic", BASE_PARAMS)
        assert coord.mode == "live_hybrid"
        coord.stop_all()

    def test_start_live_hybrid_sets_live_model(self, mock_cycle):
        coord = _make_coordinator()
        coord.start_live_hybrid("anthropic", BASE_PARAMS)
        assert coord.live_model == "anthropic"
        coord.stop_all()

    def test_live_model_gets_live_trading_mode(self, mock_cycle):
        coord = _make_coordinator()
        coord.start_live_hybrid("anthropic", BASE_PARAMS)
        anthropic_params = coord.states.get("anthropic", {}).get("agent_parameters", {})
        assert anthropic_params.get("trading_mode") == "live"
        coord.stop_all()

    def test_demo_model_gets_dry_run_trading_mode(self, mock_cycle):
        coord = _make_coordinator()
        coord.start_live_hybrid("anthropic", BASE_PARAMS)
        google_params = coord.states.get("google", {}).get("agent_parameters", {})
        assert google_params.get("trading_mode") == "dry_run"
        coord.stop_all()

    def test_start_live_hybrid_returns_true(self, mock_cycle):
        coord = _make_coordinator()
        result = coord.start_live_hybrid("google", BASE_PARAMS)
        assert result is True
        coord.stop_all()

    def test_start_live_hybrid_google_live_makes_anthropic_demo(self, mock_cycle):
        coord = _make_coordinator()
        coord.start_live_hybrid("google", BASE_PARAMS)
        google_params = coord.states.get("google", {}).get("agent_parameters", {})
        anthropic_params = coord.states.get("anthropic", {}).get("agent_parameters", {})
        assert google_params.get("trading_mode") == "live"
        assert anthropic_params.get("trading_mode") == "dry_run"
        coord.stop_all()


# ---------------------------------------------------------------------------
# MultiAgentCoordinator.stop_all()
# ---------------------------------------------------------------------------

class TestStopAll:
    @pytest.fixture
    def running_coordinator(self):
        """Start a coordinator in demo mode then yield it for stop tests."""
        with patch("src.agent.multi_agent_manager.run_langgraph_trading_cycle",
                   return_value=_fresh_state(cycles_completed=1)), \
             patch("src.agent.multi_agent_manager.save_agent_state"), \
             patch("src.agent.multi_agent_manager.load_agent_state", return_value=None), \
             patch("src.agent.multi_agent_manager.create_initial_state",
                   side_effect=_fresh_state):
            coord = _make_coordinator()
            coord.start_demo_parallel(BASE_PARAMS)
            yield coord

    def test_stop_all_returns_bool(self, running_coordinator):
        result = running_coordinator.stop_all()
        assert isinstance(result, bool)

    def test_stop_all_sets_mode_to_none(self, running_coordinator):
        running_coordinator.stop_all()
        assert running_coordinator.mode is None

    def test_stop_all_clears_threads(self, running_coordinator):
        running_coordinator.stop_all()
        assert len(running_coordinator.threads) == 0

    def test_stop_all_clears_running(self, running_coordinator):
        running_coordinator.stop_all()
        assert len(running_coordinator.running) == 0

    def test_stop_all_idempotent(self, running_coordinator):
        running_coordinator.stop_all()
        # Second call on already-stopped coordinator must not raise
        result = running_coordinator.stop_all()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# MultiAgentCoordinator._agent_loop() error recovery
# ---------------------------------------------------------------------------

class TestAgentLoopErrorRecovery:
    def test_loop_continues_after_single_error(self):
        """Loop must not exit after the first exception — it retries."""
        call_count = {"n": 0}
        coord = _make_coordinator()  # created here so fake_cycle can reference it

        def fake_cycle(state):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("transient error")
            # On second successful call, signal stop so the loop terminates
            coord.stop_flags["anthropic"] = True
            return {
                "cycles_completed": call_count["n"],
                "wallet_balance_sol": 10.0,
                "active_positions": [],
                "error": None,
                "tools_used_this_cycle": [],
                "agent_parameters": {**BASE_PARAMS, "cycle_time_seconds": 0},
            }

        coord.states["anthropic"] = {
            "cycles_completed": 0,
            "wallet_balance_sol": 10.0,
            "active_positions": [],
            "error": None,
            "tools_used_this_cycle": [],
            "agent_parameters": {**BASE_PARAMS, "cycle_time_seconds": 0},
        }
        coord.stop_flags["anthropic"] = False
        coord.running["anthropic"] = False

        with patch("src.agent.multi_agent_manager.run_langgraph_trading_cycle",
                   side_effect=fake_cycle), \
             patch("src.agent.multi_agent_manager.save_agent_state"), \
             patch("time.sleep"):  # no real sleeping
            coord._agent_loop("anthropic", {**BASE_PARAMS, "cycle_time_seconds": 0})

        # The loop ran at least 2 times (once raising, once succeeding)
        assert call_count["n"] >= 2

    def test_loop_stops_after_max_consecutive_errors(self):
        """Three consecutive errors must cause the loop to exit."""
        with patch("src.agent.multi_agent_manager.run_langgraph_trading_cycle",
                   side_effect=RuntimeError("always fails")), \
             patch("src.agent.multi_agent_manager.save_agent_state"), \
             patch("time.sleep"):
            coord = _make_coordinator()
            coord.states["anthropic"] = {
                "cycles_completed": 0,
                "wallet_balance_sol": 10.0,
                "active_positions": [],
                "error": None,
                "tools_used_this_cycle": [],
                "agent_parameters": {**BASE_PARAMS, "cycle_time_seconds": 0},
            }
            coord.stop_flags["anthropic"] = False
            coord.running["anthropic"] = False
            coord._agent_loop("anthropic", {**BASE_PARAMS, "cycle_time_seconds": 0})

        # After loop exits, running flag must be reset to False
        assert coord.running["anthropic"] is False


# ---------------------------------------------------------------------------
# Public API functions (module-level delegates to global coordinator)
# ---------------------------------------------------------------------------

class TestPublicApiFunctions:
    @pytest.fixture(autouse=True)
    def reset_global_coordinator(self):
        """Reset the global singleton between tests."""
        import src.agent.multi_agent_manager as m
        m._global_coordinator = None
        yield
        # Clean up any threads started during the test
        if m._global_coordinator is not None:
            m._global_coordinator.stop_all()
        m._global_coordinator = None

    def test_get_multi_agent_coordinator_returns_coordinator(self):
        from src.agent.multi_agent_manager import get_multi_agent_coordinator, MultiAgentCoordinator
        coord = get_multi_agent_coordinator()
        assert isinstance(coord, MultiAgentCoordinator)

    def test_get_multi_agent_coordinator_is_singleton(self):
        from src.agent.multi_agent_manager import get_multi_agent_coordinator
        first = get_multi_agent_coordinator()
        second = get_multi_agent_coordinator()
        assert first is second

    def test_is_multi_agent_running_false_when_idle(self):
        from src.agent.multi_agent_manager import is_multi_agent_running
        assert is_multi_agent_running() is False

    def test_get_multi_agent_status_returns_dict(self):
        from src.agent.multi_agent_manager import get_multi_agent_status
        status = get_multi_agent_status()
        assert isinstance(status, dict)
        assert "any_running" in status

    def test_stop_multi_agent_system_safe_when_not_running(self):
        from src.agent.multi_agent_manager import stop_multi_agent_system
        result = stop_multi_agent_system()
        assert isinstance(result, bool)

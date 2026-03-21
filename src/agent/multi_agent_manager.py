# src/agent/multi_agent_manager.py
"""
Multi-Agent Manager for Parallel Model Execution
Coordinates Claude and Gemini agents running simultaneously in different modes

Architecture:
- Demo Mode: Both agents train in parallel (dry_run)
- Live Mode: Selected agent trades live, other trains in background (dry_run)

Based on best practices:
- Threading for I/O-bound tasks (LLM API calls)
- Independent state files per model (agent_state_anthropic.json, agent_state_google.json)
- Graceful shutdown with stop flags
- Comprehensive error handling and logging
"""
import threading
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .langgraph_trading_agent import run_langgraph_trading_cycle
from .state import AgentState, create_initial_state, save_agent_state, load_agent_state

logger = logging.getLogger("trading_agent.multi_agent_manager")


class MultiAgentCoordinator:
    """
    Coordinates multiple AI agents (Claude + Gemini) running in parallel

    Modes:
    1. Demo Parallel: Both agents run in demo mode simultaneously
    2. Live Hybrid: One agent in live mode, other in demo mode
    """

    def __init__(self):
        self.threads = {}       # {model_provider: thread}
        self.states = {}        # {model_provider: AgentState}
        self.running = {}       # {model_provider: bool}
        self.stop_flags = {}    # {model_provider: bool}
        self.mode = None        # 'demo_parallel' or 'live_hybrid'
        self.live_model = None  # Which model is in live mode (if any)

    def start_demo_parallel(self, parameters: Dict[str, Any]) -> bool:
        """
        Start both Claude and Gemini in parallel demo mode

        Args:
            parameters: Base agent parameters

        Returns:
            bool: True if started successfully
        """
        try:
            logger.info("🚀 Starting Demo Parallel Mode - Both models training simultaneously")

            self.mode = 'demo_parallel'
            self.live_model = None

            # Ensure both agents run in dry_run mode
            demo_params = parameters.copy()
            demo_params['trading_mode'] = 'dry_run'

            # Start Claude agent
            claude_params = demo_params.copy()
            claude_params['model_provider'] = 'anthropic'
            claude_success = self._start_agent('anthropic', claude_params)

            # Start Gemini agent
            gemini_params = demo_params.copy()
            gemini_params['model_provider'] = 'google'
            gemini_success = self._start_agent('google', gemini_params)

            if claude_success and gemini_success:
                logger.info("✅ Demo Parallel Mode: Both agents started successfully")
                return True
            else:
                logger.error("❌ Failed to start one or both agents")
                self.stop_all()
                return False

        except Exception as e:
            logger.error(f"❌ Error starting demo parallel mode: {e}")
            return False

    def start_live_hybrid(self, live_model: str, parameters: Dict[str, Any]) -> bool:
        """
        Start live trading with one model, demo training with the other

        Args:
            live_model: Model to use for live trading ('anthropic' or 'google')
            parameters: Base agent parameters

        Returns:
            bool: True if started successfully
        """
        try:
            logger.info(f"🚀 Starting Live Hybrid Mode - {live_model.upper()} live, other in demo")

            self.mode = 'live_hybrid'
            self.live_model = live_model

            # Determine which model is which
            demo_model = 'google' if live_model == 'anthropic' else 'anthropic'

            # Start LIVE agent
            live_params = parameters.copy()
            live_params['trading_mode'] = 'live'
            live_params['model_provider'] = live_model
            live_success = self._start_agent(live_model, live_params)

            # Start DEMO agent (background training)
            demo_params = parameters.copy()
            demo_params['trading_mode'] = 'dry_run'
            demo_params['model_provider'] = demo_model
            demo_success = self._start_agent(demo_model, demo_params)

            if live_success and demo_success:
                logger.info(f"✅ Live Hybrid Mode: {live_model.upper()} live, {demo_model.upper()} demo")
                return True
            else:
                logger.error("❌ Failed to start live hybrid mode")
                self.stop_all()
                return False

        except Exception as e:
            logger.error(f"❌ Error starting live hybrid mode: {e}")
            return False

    def _start_agent(self, model_provider: str, parameters: Dict[str, Any]) -> bool:
        """
        Start a single agent in its own thread

        Args:
            model_provider: 'anthropic' or 'google'
            parameters: Agent parameters

        Returns:
            bool: True if started successfully
        """
        try:
            if self.running.get(model_provider, False):
                logger.warning(f"{model_provider} agent already running")
                return False

            # Load or create initial state for this model
            state_file = f"agent_state_{model_provider}.json"
            try:
                state = load_agent_state(state_file)
                if state is None:
                    state = create_initial_state()
            except:
                state = create_initial_state()

            # Update state with parameters
            state['agent_parameters'] = parameters
            state['model_provider'] = model_provider

            # Save initial state
            self.states[model_provider] = state

            # Create and start thread
            thread = threading.Thread(
                target=self._agent_loop,
                args=(model_provider, parameters),
                daemon=True,
                name=f"{model_provider}_agent_thread"
            )

            self.threads[model_provider] = thread
            self.running[model_provider] = False  # Will be set to True in thread
            self.stop_flags[model_provider] = False

            thread.start()

            # Wait a moment to ensure thread started
            time.sleep(0.5)

            if self.running.get(model_provider, False):
                logger.info(f"✅ {model_provider.upper()} agent started successfully")
                return True
            else:
                logger.error(f"❌ {model_provider.upper()} agent thread failed to start")
                return False

        except Exception as e:
            logger.error(f"❌ Error starting {model_provider} agent: {e}")
            return False

    def _agent_loop(self, model_provider: str, parameters: Dict[str, Any]):
        """
        Main loop for a single agent

        Args:
            model_provider: 'anthropic' or 'google'
            parameters: Agent parameters
        """
        try:
            self.running[model_provider] = True
            consecutive_errors = 0
            max_consecutive_errors = 3

            trading_mode = parameters.get('trading_mode', 'dry_run')
            mode_emoji = "💰" if trading_mode == 'live' else "🎓"

            logger.info(f"{mode_emoji} {model_provider.upper()} agent loop started ({trading_mode} mode)")

            while not self.stop_flags.get(model_provider, False):
                try:
                    # Get current state
                    current_state = self.states.get(model_provider)

                    # Run trading cycle
                    cycle_num = current_state.get('cycles_completed', 0) + 1
                    logger.info(f"{mode_emoji} {model_provider.upper()}: Starting cycle {cycle_num}")

                    new_state = run_langgraph_trading_cycle(current_state)

                    # Update state
                    self.states[model_provider] = new_state

                    # Save state to model-specific file
                    state_file = f"agent_state_{model_provider}.json"
                    save_agent_state(new_state, state_file)

                    # Reset error counter on success
                    consecutive_errors = 0

                    # Log cycle completion
                    cycles = new_state.get('cycles_completed', 0)
                    balance = new_state.get('wallet_balance_sol', 0)
                    positions = len(new_state.get('active_positions', []))
                    tools_used = new_state.get('tools_used_this_cycle', [])

                    logger.info(
                        f"{mode_emoji} {model_provider.upper()} Cycle {cycles} complete: "
                        f"{balance:.4f} SOL, {positions} positions, {len(tools_used)} tools used"
                    )

                    # Check for stop flag
                    if self.stop_flags.get(model_provider, False):
                        logger.info(f"🛑 Stop flag detected for {model_provider}")
                        break

                    # Sleep between cycles
                    cycle_time = parameters.get('cycle_time_seconds', 300)

                    # Adjust cycle time based on state
                    if new_state.get('error'):
                        cycle_time = max(cycle_time, 600)

                    # Sleep in small intervals to check stop flag
                    for i in range(cycle_time):
                        if self.stop_flags.get(model_provider, False):
                            break
                        time.sleep(1)

                except Exception as cycle_error:
                    consecutive_errors += 1
                    logger.error(
                        f"🚨 {model_provider.upper()} cycle error "
                        f"({consecutive_errors}/{max_consecutive_errors}): {cycle_error}"
                    )

                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"🛑 Too many errors for {model_provider}, stopping")
                        break

                    # Wait before retry
                    time.sleep(60)

        except Exception as e:
            logger.error(f"🚨 Critical error in {model_provider} agent loop: {e}")
        finally:
            self.running[model_provider] = False
            logger.info(f"🏁 {model_provider.upper()} agent stopped")

    def stop_all(self) -> bool:
        """
        Stop all running agents

        Returns:
            bool: True if all agents stopped successfully
        """
        try:
            logger.info("🛑 Stopping all agents...")

            # Set stop flags
            for model_provider in list(self.running.keys()):
                self.stop_flags[model_provider] = True

            # Wait for threads to stop (up to 15 seconds each)
            all_stopped = True
            for model_provider, thread in list(self.threads.items()):
                if thread and thread.is_alive():
                    thread.join(timeout=15)
                    if thread.is_alive():
                        logger.warning(f"⚠️ {model_provider} thread did not stop gracefully")
                        all_stopped = False
                    else:
                        logger.info(f"✅ {model_provider} agent stopped")

            # Clean up
            self.threads.clear()
            self.running.clear()
            self.stop_flags.clear()
            self.mode = None
            self.live_model = None

            logger.info("✅ All agents stopped" if all_stopped else "⚠️ Some agents did not stop cleanly")
            return all_stopped

        except Exception as e:
            logger.error(f"❌ Error stopping agents: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all agents

        Returns:
            Dict with comprehensive status information
        """
        try:
            agents_status = {}

            for model_provider in ['anthropic', 'google']:
                state = self.states.get(model_provider)

                if state:
                    agents_status[model_provider] = {
                        'running': self.running.get(model_provider, False),
                        'cycles_completed': state.get('cycles_completed', 0),
                        'wallet_balance_sol': state.get('wallet_balance_sol', 0),
                        'active_positions': len(state.get('active_positions', [])),
                        'trading_mode': state.get('agent_parameters', {}).get('trading_mode', 'unknown'),
                        'last_update': state.get('last_update_timestamp'),
                        'error': state.get('error'),
                        'tools_used': state.get('tools_used_this_cycle', [])
                    }
                else:
                    agents_status[model_provider] = {
                        'running': False,
                        'cycles_completed': 0,
                        'wallet_balance_sol': 0,
                        'active_positions': 0,
                        'trading_mode': 'unknown',
                        'last_update': None,
                        'error': None,
                        'tools_used': []
                    }

            return {
                'coordinator_mode': self.mode,
                'live_model': self.live_model,
                'agents': agents_status,
                'any_running': any(self.running.values()),
                'all_running': all(self.running.get(m, False) for m in ['anthropic', 'google']) if self.mode else False,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting multi-agent status: {e}")
            return {
                'coordinator_mode': None,
                'live_model': None,
                'agents': {},
                'any_running': False,
                'all_running': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Global coordinator instance
_global_coordinator = None


def get_multi_agent_coordinator() -> MultiAgentCoordinator:
    """Get or create the global multi-agent coordinator"""
    global _global_coordinator
    if _global_coordinator is None:
        _global_coordinator = MultiAgentCoordinator()
    return _global_coordinator


# ============================================================================
# PUBLIC API FUNCTIONS
# ============================================================================

def start_demo_parallel_mode(parameters: Dict[str, Any]) -> bool:
    """
    Start both Claude and Gemini in parallel demo mode

    Args:
        parameters: Base agent parameters

    Returns:
        bool: True if started successfully
    """
    coordinator = get_multi_agent_coordinator()
    return coordinator.start_demo_parallel(parameters)


def start_live_hybrid_mode(live_model: str, parameters: Dict[str, Any]) -> bool:
    """
    Start one model in live mode, other in demo mode

    Args:
        live_model: Model for live trading ('anthropic' or 'google')
        parameters: Base agent parameters

    Returns:
        bool: True if started successfully
    """
    coordinator = get_multi_agent_coordinator()
    return coordinator.start_live_hybrid(live_model, parameters)


def stop_multi_agent_system() -> bool:
    """
    Stop all running agents

    Returns:
        bool: True if stopped successfully
    """
    coordinator = get_multi_agent_coordinator()
    return coordinator.stop_all()


def get_multi_agent_status() -> Dict[str, Any]:
    """
    Get status of multi-agent system

    Returns:
        Dict with status information
    """
    coordinator = get_multi_agent_coordinator()
    return coordinator.get_status()


def is_multi_agent_running() -> bool:
    """Check if any agent is running"""
    coordinator = get_multi_agent_coordinator()
    return coordinator.mode is not None and any(coordinator.running.values())

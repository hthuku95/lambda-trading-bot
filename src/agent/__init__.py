# src/agent/__init__.py
"""
Complete Agent Module - Updated for LangGraph with Full UI Integration
Provides all functions expected by the Streamlit UI
"""
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Import LangGraph implementation (THE KEY CHANGE)
from .langgraph_trading_agent import run_langgraph_trading_cycle, CompleteLangGraphTradingAgent

# Import multi-agent coordinator functions (required by Streamlit sidebar)
from .multi_agent_manager import (
    start_demo_parallel_mode, start_live_hybrid_mode,
    stop_multi_agent_system, get_multi_agent_status, is_multi_agent_running,
)

# Import state management (unchanged)
from .state import (
    AgentState, TokenData, Position, 
    create_initial_state, save_agent_state, load_agent_state,
    update_portfolio_metrics, migrate_legacy_state, validate_state_structure,
    get_state_summary
)

# Configure logger
logger = logging.getLogger("trading_agent")

# Global variables for background agent management (REQUIRED BY UI)
_agent_thread = None
_agent_running = False
_agent_stop_flag = False
_agent_instance = None # To hold the persistent agent instance

def run_trading_agent(parameters: dict = None) -> AgentState:
    """
    Main trading agent function - now uses LangGraph
    Compatible with existing UI calls
    """
    global _agent_instance
    try:
        # Load or create initial state
        state = load_agent_state()
        if state is None:
            state = create_initial_state()
            logger.info("Created new agent state")
        else:
            logger.info("Loaded existing agent state")
            
            # Validate and migrate if needed
            if not validate_state_structure(state):
                logger.warning("State structure outdated, migrating...")
                state = migrate_legacy_state(state)
        
        # Extract model_provider from parameters, default to 'gemini'
        model_provider = "gemini"
        if parameters:
            model_provider = parameters.get("model_provider", "gemini")
            current_params = state.get("agent_parameters", {})
            current_params.update(parameters)
            state["agent_parameters"] = current_params

        # Initialize the agent instance if it doesn't exist
        if _agent_instance is None:
            logger.info(f"🔧 Creating persistent agent instance with {model_provider.upper()}...")
            _agent_instance = CompleteLangGraphTradingAgent(model_provider=model_provider)
        
        # USE LANGGRAPH instead of pure_ai_agent (THE KEY CHANGE)
        logger.info(f"🚀 Running LangGraph trading cycle with {model_provider.upper()}...")
        result_state = _agent_instance.run_trading_cycle(state)
        
        # Save state
        save_agent_state(result_state)
        
        # Log success indicators
        tools_used = result_state.get("tools_used_this_cycle", [])
        cycles = result_state.get("cycles_completed", 0)
        
        if tools_used:
            logger.info(f"✅ LangGraph cycle {cycles} completed with tools: {tools_used}")
        else:
            logger.warning(f"⚠️ LangGraph cycle {cycles} completed but no tools were used")
        
        return result_state
        
    except Exception as e:
        logger.error(f"❌ Trading agent error: {e}")
        # Return error state
        error_state = state if 'state' in locals() else create_initial_state()
        error_state["error"] = str(e)
        error_state["error_timestamp"] = datetime.now().isoformat()
        save_agent_state(error_state)
        return error_state

def start_agent_background(parameters: dict = None) -> bool:
    """Start the trading agent in background mode (REQUIRED BY UI)"""
    global _agent_thread, _agent_running, _agent_stop_flag, _agent_instance
    
    if _agent_running:
        logger.warning("Agent already running in background")
        return False
    
    def background_loop():
        global _agent_running, _agent_stop_flag, _agent_instance
        _agent_stop_flag = False
        
        # Initialize the agent instance at the start of the thread
        model_provider = parameters.get("model_provider", "gemini") if parameters else "gemini"
        logger.info(f"🔧 Initializing persistent agent for background thread with {model_provider.upper()}...")
        _agent_instance = CompleteLangGraphTradingAgent(model_provider=model_provider)
        
        logger.info("🚀 Starting LangGraph agent in background mode...")
        
        while not _agent_stop_flag:
            try:
                # Run one trading cycle using the persistent instance
                run_trading_agent(parameters)
                
                # Check for stop condition
                if _agent_stop_flag:
                    break
                
                # Sleep between cycles
                cycle_time = parameters.get("cycle_time_seconds", 300) if parameters else 300
                for _ in range(cycle_time):
                    if _agent_stop_flag:
                        break
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"Background agent error: {e}")
                time.sleep(60)  # Wait before retrying
        
        _agent_running = False
        _agent_instance = None # Clear the instance on exit
        logger.info("Background agent stopped")
    
    try:
        _agent_running = True  # Set before thread starts to avoid race condition
        _agent_thread = threading.Thread(target=background_loop, daemon=True)
        _agent_thread.start()
        logger.info("Background agent thread started")
        return True
    except Exception as e:
        logger.error(f"Failed to start background agent: {e}")
        _agent_running = False
        return False

def stop_agent_background() -> bool:
    """Stop the background trading agent (REQUIRED BY UI)"""
    global _agent_stop_flag, _agent_running
    
    if not _agent_running:
        logger.info("No background agent to stop")
        return True
    
    logger.info("Stopping background agent...")
    _agent_stop_flag = True
    
    # Wait up to 10 seconds for graceful shutdown
    for _ in range(100):
        if not _agent_running:
            logger.info("Background agent stopped successfully")
            return True
        time.sleep(0.1)
    
    logger.warning("Background agent did not stop gracefully")
    return False

def get_agent_status() -> Dict[str, Any]:
    """Get current agent status (REQUIRED BY UI)"""
    global _agent_running, _agent_thread
    
    # Load current state
    state = load_agent_state()
    
    return {
        "running": _agent_running,
        "thread_alive": _agent_thread.is_alive() if _agent_thread else False,
        "cycles_completed": state.get("cycles_completed", 0) if state else 0,
        "last_update": state.get("last_update_timestamp") if state else None,
        "wallet_balance_sol": state.get("wallet_balance_sol", 0) if state else 0,
        "active_positions": len(state.get("active_positions", [])) if state else 0,
        "tools_used_last_cycle": state.get("tools_used_this_cycle", []) if state else [],
        "agent_type": "LangGraph_Enhanced"
    }

# ============================================================================
# EXPORTS (All functions the UI expects)
# ============================================================================

__all__ = [
    # Main agent functions
    "run_trading_agent",

    # Background management
    "start_agent_background",
    "stop_agent_background",
    "get_agent_status",

    # Multi-agent coordinator
    "start_demo_parallel_mode",
    "start_live_hybrid_mode",
    "stop_multi_agent_system",
    "get_multi_agent_status",
    "is_multi_agent_running",

    # State management
    "load_agent_state",
    "save_agent_state",
    "create_initial_state",
    "update_portfolio_metrics",
    "get_state_summary",

    # State types
    "AgentState",
    "TokenData",
    "Position",
]

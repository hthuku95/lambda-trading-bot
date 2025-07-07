# src/agent/__init__.py
"""
Complete Agent Module - Updated for LangGraph with Proper State Management
Implements correct LangGraph patterns: stateful workflows, thread continuity, error handling
"""
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Import LangGraph implementation
from .langgraph_trading_agent import run_langgraph_trading_cycle

# Import pure_ai_graph for compatibility
from .pure_ai_graph import build_pure_ai_trading_graph

# Import state management
from .state import (
    AgentState, TokenData, Position, 
    create_initial_state, save_agent_state, load_agent_state,
    update_portfolio_metrics, migrate_legacy_state, validate_state_structure,
    get_state_summary
)

# Configure logger
logger = logging.getLogger("trading_agent")

# Global variables for background agent management
_agent_thread = None
_agent_running = False
_agent_stop_flag = False
_current_thread_id = None
_current_state = None

# ============================================================================
# MAIN AGENT FUNCTIONS (Corrected for LangGraph State Management)
# ============================================================================

def run_trading_agent(parameters: dict = None, previous_state: AgentState = None, thread_id: str = None) -> AgentState:
    """
    Main trading agent function - now uses LangGraph with proper state management
    
    Args:
        parameters: Agent configuration parameters
        previous_state: State from previous cycle (for continuity)
        thread_id: Thread ID for persistent memory across cycles
        
    Returns:
        AgentState: Updated agent state after trading cycle
    """
    try:
        # Determine state to use - previous state takes priority for continuity
        if previous_state:
            state = previous_state
            logger.info(f"Continuing from previous state (cycle {state.get('cycles_completed', 0)})")
        else:
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
        
        # Set thread ID for session continuity
        if thread_id:
            state["thread_id"] = thread_id
            state["session_active"] = True
        
        # Update parameters if provided
        if parameters:
            current_params = state.get("agent_parameters", {})
            current_params.update(parameters)
            state["agent_parameters"] = current_params
            
            # Update trading mode
            if "dry_run" in parameters:
                state["trading_mode"] = "dry_run" if parameters["dry_run"] else "live"
            
            logger.info(f"Updated agent parameters: {parameters}")
        
        # Clear any previous errors before new cycle
        if "error" in state:
            state["previous_errors"] = state.get("previous_errors", [])
            state["previous_errors"].append({
                "error": state["error"],
                "timestamp": state.get("error_timestamp"),
                "resolved": True
            })
            del state["error"]
            if "error_timestamp" in state:
                del state["error_timestamp"]
        
        # USE LANGGRAPH with proper state management
        logger.info("🚀 Starting LangGraph trading cycle with state continuity...")
        updated_state = run_langgraph_trading_cycle(state)
        
        # Validate returned state
        if not isinstance(updated_state, dict):
            logger.error("LangGraph returned invalid state type")
            updated_state = state  # Fall back to input state
            updated_state["error"] = "Invalid state returned from LangGraph"
            updated_state["error_timestamp"] = datetime.now().isoformat()
        
        # Log cycle completion with state analysis
        cycles = updated_state.get("cycles_completed", 0)
        balance = updated_state.get("wallet_balance_sol", 0)
        positions = len(updated_state.get("active_positions", []))
        tools_used = updated_state.get("tools_used_this_cycle", [])
        
        # Enhanced state-based logging
        if tools_used:
            logger.info(f"✅ LangGraph cycle {cycles} completed with tools: {tools_used}")
        else:
            logger.warning(f"⚠️ LangGraph cycle {cycles} completed but no tools were used")
            
        logger.info(f"📊 Trading cycle {cycles} completed - Balance: {balance:.4f} SOL, Positions: {positions}")
        
        # Check for state errors or warnings
        if updated_state.get("error"):
            logger.error(f"🚨 Cycle completed with error: {updated_state['error']}")
        
        # Update session continuity markers
        updated_state["last_cycle_timestamp"] = datetime.now().isoformat()
        updated_state["state_healthy"] = not bool(updated_state.get("error"))
        
        # Save state for persistence
        save_agent_state(updated_state)
        
        return updated_state
        
    except Exception as e:
        logger.error(f"❌ Critical error in run_trading_agent: {e}")
        
        # Create comprehensive error state
        error_state = previous_state or state if 'state' in locals() else create_initial_state()
        error_state["error"] = str(e)
        error_state["error_timestamp"] = datetime.now().isoformat()
        error_state["error_type"] = "run_trading_agent_failure"
        error_state["cycles_completed"] = error_state.get("cycles_completed", 0) + 1
        error_state["state_healthy"] = False
        
        # Save error state
        save_agent_state(error_state)
        return error_state

def start_agent_background(parameters: dict = None) -> bool:
    """
    Start the trading agent in background mode with proper LangGraph state management
    
    Args:
        parameters: Agent configuration parameters
        
    Returns:
        bool: True if started successfully
    """
    global _agent_thread, _agent_running, _agent_stop_flag, _current_thread_id, _current_state
    
    if _agent_running:
        logger.warning("Agent already running in background")
        return False
    
    def background_trading_loop():
        """Background trading loop with proper LangGraph state management"""
        global _agent_running, _agent_stop_flag, _current_thread_id, _current_state
        
        _agent_running = True
        _agent_stop_flag = False
        
        # Create unique thread ID for this session
        _current_thread_id = f"trading_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"🚀 Starting LangGraph agent in background mode (Thread: {_current_thread_id})")
        
        # Initialize state for continuous operation
        _current_state = None
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        try:
            while not _agent_stop_flag:
                try:
                    # Run trading cycle with state continuity
                    new_state = run_trading_agent(
                        parameters=parameters, 
                        previous_state=_current_state,
                        thread_id=_current_thread_id
                    )
                    
                    # STATE-BASED DECISION MAKING (Critical LangGraph Pattern)
                    
                    # Check for errors in state
                    if new_state.get("error"):
                        consecutive_errors += 1
                        logger.error(f"📊 State contains error ({consecutive_errors}/{max_consecutive_errors}): {new_state['error']}")
                        
                        # Handle too many consecutive errors
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error("🛑 Too many consecutive errors, stopping agent")
                            break
                    else:
                        # Reset error counter on successful cycle
                        consecutive_errors = 0
                    
                    # Check for stop conditions in state
                    if new_state.get("should_stop") or new_state.get("fatal_error"):
                        logger.info("🛑 Agent state indicates should stop")
                        break
                    
                    # Update current state for next cycle (STATE CONTINUITY)
                    _current_state = new_state
                    
                    # Log important state information
                    cycles = new_state.get("cycles_completed", 0)
                    tools_used = new_state.get("tools_used_this_cycle", [])
                    balance = new_state.get("wallet_balance_sol", 0)
                    positions = len(new_state.get("active_positions", []))
                    
                    logger.info(f"🔄 Cycle {cycles} state: {balance:.4f} SOL, {positions} positions, tools: {tools_used}")
                    
                    # Check for stop condition
                    if _agent_stop_flag:
                        logger.info("🛑 Stop flag detected, breaking loop")
                        break
                    
                    # Get cycle time from parameters or state
                    cycle_time = parameters.get("cycle_time_seconds", 300) if parameters else 300
                    
                    # State-aware sleep interval adjustments
                    if new_state.get("error"):
                        # Longer wait on errors
                        cycle_time = max(cycle_time, 600)
                        logger.info(f"💤 Extended wait due to error: {cycle_time}s")
                    elif not tools_used:
                        # Longer wait if no tools were used (possible issue)
                        cycle_time = max(cycle_time, 450)
                        logger.info(f"💤 Extended wait due to no tool usage: {cycle_time}s")
                    
                    # Sleep in small intervals so we can check stop flag
                    for i in range(cycle_time):
                        if _agent_stop_flag:
                            logger.info(f"🛑 Stop flag detected during sleep ({i}/{cycle_time}s)")
                            break
                        time.sleep(1)
                
                except Exception as cycle_error:
                    consecutive_errors += 1
                    logger.error(f"🚨 Background cycle error ({consecutive_errors}/{max_consecutive_errors}): {cycle_error}")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error("🛑 Too many consecutive cycle errors, stopping agent")
                        break
                    
                    # Wait before retrying on error
                    time.sleep(60)
                    
        except Exception as e:
            logger.error(f"🚨 Critical background agent error: {e}")
        finally:
            _agent_running = False
            _current_state = None
            _current_thread_id = None
            logger.info("🏁 Background agent stopped")
    
    try:
        _agent_thread = threading.Thread(target=background_trading_loop, daemon=True)
        _agent_thread.start()
        logger.info("✅ Background agent thread started successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start background agent: {e}")
        _agent_running = False
        return False

def stop_agent_background() -> bool:
    """
    Stop the background trading agent with proper state cleanup
    
    Returns:
        bool: True if stopped successfully
    """
    global _agent_stop_flag, _agent_running, _current_state, _current_thread_id
    
    if not _agent_running:
        logger.info("No background agent to stop")
        return True
    
    logger.info("🛑 Stopping background agent...")
    _agent_stop_flag = True
    
    # Wait up to 15 seconds for graceful shutdown
    for i in range(150):
        if not _agent_running:
            logger.info("✅ Background agent stopped successfully")
            
            # Clean up state
            if _current_state:
                _current_state["session_active"] = False
                _current_state["session_end_timestamp"] = datetime.now().isoformat()
                save_agent_state(_current_state)
                logger.info("💾 Final state saved")
            
            _current_state = None
            _current_thread_id = None
            return True
        time.sleep(0.1)
    
    logger.warning("⚠️ Background agent did not stop gracefully")
    return False

def get_agent_status() -> Dict[str, Any]:
    """
    Get current agent status with enhanced state information
    
    Returns:
        Dict containing comprehensive agent status
    """
    global _agent_running, _agent_thread, _current_thread_id, _current_state
    
    try:
        # Get current state
        state = _current_state or load_agent_state()
        
        if state:
            summary = get_state_summary(state)
            
            # Enhanced status with state-based information
            status = {
                # Basic runtime info
                "running": _agent_running,
                "thread_alive": _agent_thread.is_alive() if _agent_thread else False,
                "current_thread_id": _current_thread_id,
                
                # State-based information
                "cycles_completed": state.get("cycles_completed", 0),
                "last_update": state.get("last_cycle_timestamp") or state.get("last_update_timestamp"),
                "wallet_balance_sol": state.get("wallet_balance_sol", 0),
                "active_positions": len(state.get("active_positions", [])),
                "tools_used_last_cycle": state.get("tools_used_this_cycle", []),
                
                # Enhanced state information
                "agent_type": "LangGraph_Enhanced",
                "session_active": state.get("session_active", False),
                "state_healthy": state.get("state_healthy", True),
                "consecutive_errors": len([e for e in state.get("previous_errors", []) if not e.get("resolved", True)]),
                
                # Status determination based on state
                "status": self._determine_status(state),
                "summary": summary,
                "agent_health": state.get("agent_health", {}),
                "trading_mode": state.get("trading_mode", "dry_run"),
                "ai_strategy": state.get("ai_strategy", "unknown"),
                
                # Error information
                "current_error": state.get("error"),
                "error_timestamp": state.get("error_timestamp")
            }
            
            return status
        else:
            return {
                "running": _agent_running,
                "thread_alive": _agent_thread.is_alive() if _agent_thread else False,
                "current_thread_id": _current_thread_id,
                "cycles_completed": 0,
                "last_update": None,
                "wallet_balance_sol": 0,
                "active_positions": 0,
                "tools_used_last_cycle": [],
                "agent_type": "LangGraph_Enhanced",
                "status": "initialized",
                "state_healthy": True
            }
            
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        return {
            "running": _agent_running,
            "status": "error",
            "error": str(e),
            "state_healthy": False
        }

def _determine_status(state: AgentState) -> str:
    """Determine agent status based on state analysis"""
    if state.get("error"):
        return "error"
    elif state.get("cycles_completed", 0) == 0:
        return "initialized"
    elif not state.get("tools_used_this_cycle", []):
        return "idle"
    elif len(state.get("active_positions", [])) > 0:
        return "trading"
    else:
        return "active"

# ============================================================================
# COMPATIBILITY FUNCTIONS (Updated for proper state management)
# ============================================================================

def run_trading_cycle(state: AgentState) -> AgentState:
    """
    Compatibility function for direct cycle execution
    Updated to use LangGraph with state continuity
    """
    return run_langgraph_trading_cycle(state)

def build_trading_agent():
    """
    Compatibility function - returns pure AI graph
    For any code that uses the graph-based workflow
    """
    return build_pure_ai_trading_graph()

# For backwards compatibility - alias to the LangGraph implementation
def run_pure_ai_trading_agent(state: AgentState = None) -> AgentState:
    """
    Backwards compatibility function
    Now redirects to LangGraph implementation with proper state handling
    """
    return run_langgraph_trading_cycle(state)

# ============================================================================
# EXPORTS (All functions needed by UI and other components)
# ============================================================================

__all__ = [
    # Main functions
    "run_trading_agent",
    "start_agent_background", 
    "stop_agent_background",
    "get_agent_status",
    
    # LangGraph functions (new)
    "run_langgraph_trading_cycle",
    
    # Pure AI functions (compatibility)
    "run_pure_ai_trading_agent",
    "build_pure_ai_trading_graph",
    
    # State management
    "AgentState", 
    "TokenData", 
    "Position",
    "create_initial_state",
    "save_agent_state", 
    "load_agent_state",
    "update_portfolio_metrics",
    "migrate_legacy_state",
    "validate_state_structure",
    "get_state_summary",
    
    # Compatibility
    "run_trading_cycle",
    "build_trading_agent"
]
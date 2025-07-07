# src/agent/__init__.py
"""
Modern Pure AI Trading Agent Module
Exports pure AI functions and updated state management
"""
from .pure_ai_agent import run_pure_ai_trading_agent
from .pure_ai_graph import build_pure_ai_trading_graph
from .state import (
    AgentState, TokenData, Position, 
    create_initial_state, save_agent_state, load_agent_state,
    update_portfolio_metrics, migrate_legacy_state, validate_state_structure,
    get_state_summary
)

# ============================================================================
# MAIN AGENT FUNCTIONS (Updated for Pure AI)
# ============================================================================

def run_trading_agent(parameters: dict = None) -> AgentState:
    """
    Main trading agent function - now uses Pure AI
    Compatible with existing UI calls but runs enhanced AI agent
    
    Args:
        parameters: Agent configuration parameters
        
    Returns:
        AgentState: Updated agent state after trading cycle
    """
    import logging
    logger = logging.getLogger("trading_agent")
    
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
        
        # Update parameters if provided
        if parameters:
            current_params = state.get("agent_parameters", {})
            current_params.update(parameters)
            state["agent_parameters"] = current_params
            
            # Update trading mode
            if "dry_run" in parameters:
                state["trading_mode"] = "dry_run" if parameters["dry_run"] else "live"
            
            logger.info(f"Updated agent parameters: {parameters}")
        
        # Run the pure AI trading cycle
        logger.info("Starting Pure AI trading cycle...")
        updated_state = run_pure_ai_trading_agent(state)
        
        # Log cycle completion
        cycles = updated_state.get("cycles_completed", 0)
        balance = updated_state.get("wallet_balance_sol", 0)
        positions = len(updated_state.get("active_positions", []))
        
        logger.info(f"Trading cycle {cycles} completed - Balance: {balance:.4f} SOL, Positions: {positions}")
        
        return updated_state
        
    except Exception as e:
        logger.error(f"Error in run_trading_agent: {e}")
        # Return current state or create new one on error
        try:
            return load_agent_state() or create_initial_state()
        except:
            return create_initial_state()

def start_agent_background(parameters: dict = None) -> bool:
    """
    Start the trading agent in background mode
    For UI integration - starts continuous trading
    
    Args:
        parameters: Agent configuration parameters
        
    Returns:
        bool: True if started successfully
    """
    import threading
    import time
    import logging
    
    logger = logging.getLogger("trading_agent")
    
    def background_trading_loop():
        """Background trading loop"""
        try:
            while True:
                # Run trading cycle
                state = run_trading_agent(parameters)
                
                # Get cycle time from parameters or default
                cycle_time = 300  # 5 minutes default
                if parameters and "cycle_time_seconds" in parameters:
                    cycle_time = parameters["cycle_time_seconds"]
                elif state and "agent_parameters" in state:
                    cycle_time = state["agent_parameters"].get("cycle_time_seconds", 300)
                
                logger.info(f"Trading cycle completed, waiting {cycle_time}s for next cycle")
                time.sleep(cycle_time)
                
        except Exception as e:
            logger.error(f"Background trading loop error: {e}")
    
    try:
        # Start background thread
        thread = threading.Thread(target=background_trading_loop, daemon=True)
        thread.start()
        logger.info("Background trading agent started")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start background agent: {e}")
        return False

def stop_agent_background() -> bool:
    """
    Stop the background trading agent
    Note: With daemon threads, this is mainly for logging
    
    Returns:
        bool: True if stop signal sent
    """
    import logging
    logger = logging.getLogger("trading_agent")
    
    logger.info("Stop signal sent to background trading agent")
    # With daemon threads, they'll stop when main program stops
    return True

def get_agent_status() -> dict:
    """
    Get current agent status and performance metrics
    
    Returns:
        dict: Agent status information
    """
    try:
        state = load_agent_state()
        if state is None:
            return {
                "status": "not_initialized",
                "message": "Agent not yet initialized"
            }
        
        summary = get_state_summary(state)
        
        return {
            "status": "active" if state.get("cycles_completed", 0) > 0 else "initialized",
            "summary": summary,
            "agent_health": state.get("agent_health", {}),
            "last_update": state.get("last_update_timestamp", ""),
            "trading_mode": state.get("trading_mode", "dry_run"),
            "ai_strategy": state.get("ai_strategy", "unknown")
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# ============================================================================
# COMPATIBILITY FUNCTIONS (for existing UI components)
# ============================================================================

def run_trading_cycle(state: AgentState) -> AgentState:
    """Compatibility function for direct cycle execution"""
    return run_pure_ai_trading_agent(state)

def build_trading_agent():
    """Compatibility function - returns pure AI graph"""
    return build_pure_ai_trading_graph()

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Main functions
    "run_trading_agent",
    "start_agent_background", 
    "stop_agent_background",
    "get_agent_status",
    
    # Pure AI functions
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
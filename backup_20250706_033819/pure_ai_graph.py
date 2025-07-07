# src/agent/pure_ai_graph.py
"""
LangGraph configuration for Pure AI Trading Agent
Updated to use proper LangGraph implementation
"""
from langgraph.graph import StateGraph, END
from typing import Dict, Any
from src.agent.state import AgentState

def pure_ai_trading_cycle(state: AgentState) -> AgentState:
    """Pure AI trading cycle function - now uses LangGraph"""
    try:
        # Import LangGraph implementation instead of old pure_ai_agent
        from src.agent.langgraph_trading_agent import run_langgraph_trading_cycle
        return run_langgraph_trading_cycle(state)
    except Exception as e:
        import logging
        logger = logging.getLogger("trading_agent.graph")
        logger.error(f"Error in LangGraph trading cycle: {e}")
        return state

def build_pure_ai_trading_graph():
    """Build the pure AI trading agent graph with LangGraph"""
    graph = StateGraph(AgentState)
    
    # Single AI node that handles everything
    graph.add_node("ai_trading_cycle", pure_ai_trading_cycle)
    
    # Simple flow - AI handles all decisions
    graph.set_entry_point("ai_trading_cycle")
    graph.add_edge("ai_trading_cycle", END)
    
    return graph.compile()
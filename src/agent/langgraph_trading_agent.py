# src/agent/langgraph_trading_agent.py - COMPLETE IMPLEMENTATION
"""
Complete LangGraph Trading Agent Implementation
Preserves ALL functionality from the original pure_ai_agent.py
No features omitted - this is a 1:1 functional replacement using proper LangGraph patterns
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from src.agent.state import AgentState, save_agent_state, load_agent_state, create_initial_state, update_portfolio_metrics
from src.memory.astra_vector_store import (
    astra_store, search_trading_experiences, add_trading_experience, 
    get_trading_patterns, learn_from_similar_trades
)
from src.data.dexscreener import (
    get_boosted_tokens_latest, get_boosted_tokens_top, get_latest_token_profiles,
    search_tokens_by_query, filter_tokens_by_age, filter_tokens_by_liquidity, 
    filter_tokens_by_volume, filter_tokens_by_market_cap, filter_tokens_by_price_change,
    sort_tokens_by_metric, get_discovery_capabilities
)
from src.data.rugcheck_client import get_token_safety_data_raw, check_rugcheck_api_health
from src.data.social_intelligence import get_social_data_raw, check_social_intelligence_health
from src.data.unified_enrichment import get_comprehensive_raw_token_data, get_unified_enrichment_capabilities
from src.data.jupiter import get_quote, get_swap_transaction
from src.blockchain.solana_client import get_wallet_balance, send_serialized_transaction

load_dotenv()
logger = logging.getLogger("trading_agent.langgraph")

# ============================================================================
# COMPLETE TOOL DEFINITIONS - ALL ORIGINAL FUNCTIONALITY PRESERVED
# ============================================================================

# WALLET AND PORTFOLIO TOOLS
@tool
def get_wallet_balance_tool() -> Dict[str, Any]:
    """Get current SOL wallet balance"""
    try:
        balance = get_wallet_balance()
        return {"success": True, "balance_sol": balance, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Wallet balance error: {e}")
        return {"success": False, "error": str(e)}

@tool
def get_portfolio_summary_tool() -> Dict[str, Any]:
    """Get comprehensive portfolio summary and performance metrics"""
    try:
        # Load current state for portfolio data
        state = load_agent_state() or create_initial_state()
        
        wallet_balance = state.get("wallet_balance_sol", 0)
        active_positions = state.get("active_positions", [])
        portfolio_metrics = state.get("portfolio_metrics", {})
        
        total_position_value = sum(pos.get("current_value_sol", 0) for pos in active_positions)
        total_portfolio_value = wallet_balance + total_position_value
        
        return {
            "success": True,
            "portfolio_summary": {
                "wallet_balance_sol": wallet_balance,
                "active_positions_count": len(active_positions),
                "total_portfolio_value_sol": total_portfolio_value,
                "unrealized_profit_sol": portfolio_metrics.get("unrealized_profit_sol", 0),
                "realized_profit_sol": portfolio_metrics.get("realized_profit_sol", 0),
                "win_rate": portfolio_metrics.get("win_rate", 0),
                "active_positions": active_positions,
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Portfolio summary error: {e}")
        return {"success": False, "error": str(e)}

# TOKEN DISCOVERY TOOLS
@tool
def discover_tokens_tool(
    strategy: str, 
    search_terms: Optional[List[str]] = None, 
    limit: int = 20
) -> Dict[str, Any]:
    """
    Discover tokens using various strategies and data sources
    
    Args:
        strategy: Discovery strategy (boosted_latest, boosted_top, profiles_latest, custom_search)
        search_terms: Custom search terms (for custom_search strategy)
        limit: Maximum tokens to return
    """
    try:
        if strategy == "boosted_latest":
            tokens = get_boosted_tokens_latest("solana")
        elif strategy == "boosted_top":
            tokens = get_boosted_tokens_top("solana")
        elif strategy == "profiles_latest":
            tokens = get_latest_token_profiles("solana")
        elif strategy == "custom_search":
            if not search_terms:
                return {"success": False, "error": "search_terms required for custom_search strategy"}
            tokens = search_tokens_by_query(search_terms)
        else:
            return {"success": False, "error": f"Unknown strategy: {strategy}"}
        
        if tokens:
            limited_tokens = tokens[:limit]
            return {
                "success": True,
                "tokens": limited_tokens,
                "count": len(limited_tokens),
                "strategy_used": strategy,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {"success": False, "error": "No tokens found"}
            
    except Exception as e:
        logger.error(f"Token discovery error: {e}")
        return {"success": False, "error": str(e)}

@tool
def filter_tokens_tool(
    tokens: List[Dict], 
    max_age_hours: Optional[float] = None,
    min_liquidity_usd: Optional[float] = None,
    max_liquidity_usd: Optional[float] = None,
    min_volume_24h: Optional[float] = None,
    min_market_cap: Optional[float] = None,
    max_market_cap: Optional[float] = None,
    min_price_change_24h: Optional[float] = None,
    max_price_change_24h: Optional[float] = None
) -> Dict[str, Any]:
    """
    Filter tokens by various criteria
    
    Args:
        tokens: List of tokens to filter
        max_age_hours: Maximum age in hours
        min_liquidity_usd: Minimum liquidity in USD
        max_liquidity_usd: Maximum liquidity in USD
        min_volume_24h: Minimum 24h volume
        min_market_cap: Minimum market cap
        max_market_cap: Maximum market cap
        min_price_change_24h: Minimum 24h price change percentage
        max_price_change_24h: Maximum 24h price change percentage
    """
    try:
        filtered = tokens.copy()
        
        if max_age_hours is not None:
            filtered = filter_tokens_by_age(filtered, max_age_hours)
        
        if min_liquidity_usd is not None or max_liquidity_usd is not None:
            filtered = filter_tokens_by_liquidity(filtered, min_liquidity_usd, max_liquidity_usd)
        
        if min_volume_24h is not None:
            filtered = filter_tokens_by_volume(filtered, min_volume_24h)
        
        if min_market_cap is not None or max_market_cap is not None:
            filtered = filter_tokens_by_market_cap(filtered, min_market_cap, max_market_cap)
        
        if min_price_change_24h is not None or max_price_change_24h is not None:
            filtered = filter_tokens_by_price_change(filtered, min_price_change_24h, max_price_change_24h)
        
        return {
            "success": True,
            "tokens": filtered,
            "count": len(filtered),
            "original_count": len(tokens),
            "filters_applied": {
                "max_age_hours": max_age_hours,
                "min_liquidity_usd": min_liquidity_usd,
                "max_liquidity_usd": max_liquidity_usd,
                "min_volume_24h": min_volume_24h,
                "min_market_cap": min_market_cap,
                "max_market_cap": max_market_cap,
                "min_price_change_24h": min_price_change_24h,
                "max_price_change_24h": max_price_change_24h
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Token filtering error: {e}")
        return {"success": False, "error": str(e)}

@tool
def sort_tokens_tool(
    tokens: List[Dict], 
    sort_by: str, 
    descending: bool = True
) -> Dict[str, Any]:
    """
    Sort tokens by specified metrics
    
    Args:
        tokens: List of tokens to sort
        sort_by: Metric to sort by
        descending: Sort in descending order
    """
    try:
        sorted_tokens = sort_tokens_by_metric(tokens, sort_by, descending)
        return {
            "success": True,
            "tokens": sorted_tokens,
            "count": len(sorted_tokens),
            "sorted_by": sort_by,
            "descending": descending,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Token sorting error: {e}")
        return {"success": False, "error": str(e)}

# DATA COLLECTION TOOLS
@tool
def get_comprehensive_token_data_tool(
    token_address: str, 
    token_symbol: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get comprehensive raw data for a token from all sources
    
    Args:
        token_address: Token mint address
        token_symbol: Token symbol (optional)
    """
    try:
        raw_data = get_comprehensive_raw_token_data(token_address, token_symbol)
        return {
            "success": True,
            "token_address": token_address,
            "token_symbol": token_symbol,
            "comprehensive_data": raw_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Comprehensive token data error: {e}")
        return {"success": False, "error": str(e), "token_address": token_address}

@tool
def get_safety_data_tool(token_address: str) -> Dict[str, Any]:
    """
    Get raw safety data from RugCheck
    
    Args:
        token_address: Token mint address
    """
    try:
        safety_data = get_token_safety_data_raw(token_address)
        return {
            "success": True,
            "token_address": token_address,
            "safety_data": safety_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Safety data error: {e}")
        return {"success": False, "error": str(e), "token_address": token_address}

@tool
def get_social_data_tool(token_address: str, token_symbol: str) -> Dict[str, Any]:
    """
    Get raw social data from TweetScout
    
    Args:
        token_address: Token mint address
        token_symbol: Token symbol
    """
    try:
        social_data = get_social_data_raw(token_address, token_symbol)
        return {
            "success": True,
            "token_address": token_address,
            "token_symbol": token_symbol,
            "social_data": social_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Social data error: {e}")
        return {"success": False, "error": str(e), "token_address": token_address}

# ANALYSIS AND MEMORY TOOLS
@tool
def search_trading_history_tool(
    query: str, 
    filters: Optional[Dict] = None, 
    limit: int = 10
) -> Dict[str, Any]:
    """
    Search historical trading experiences for pattern learning
    
    Args:
        query: Search query for historical experiences
        filters: Optional filters for search
        limit: Maximum results to return
    """
    try:
        if filters is None:
            filters = {}
        
        results = search_trading_experiences(query, limit, filters)
        return {
            "success": True,
            "query": query,
            "experiences": results,
            "count": len(results),
            "filters": filters,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Trading history search error: {e}")
        return {"success": False, "error": str(e)}

@tool
def find_similar_tokens_tool(
    token_characteristics: Dict, 
    limit: int = 5
) -> Dict[str, Any]:
    """
    Find historically similar tokens based on characteristics
    
    Args:
        token_characteristics: Token characteristics to match
        limit: Maximum similar tokens to find
    """
    try:
        similar_tokens = learn_from_similar_trades(token_characteristics)
        limited_results = similar_tokens[:limit] if similar_tokens else []
        
        return {
            "success": True,
            "characteristics": token_characteristics,
            "similar_tokens": limited_results,
            "count": len(limited_results),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Similar tokens search error: {e}")
        return {"success": False, "error": str(e)}

@tool
def get_trading_patterns_tool(pattern_type: str) -> Dict[str, Any]:
    """
    Get trading patterns for AI learning and strategy development
    
    Args:
        pattern_type: Type of trading patterns to analyze (profitable, losing, high_profit, quick_trades, all)
    """
    try:
        patterns = get_trading_patterns(pattern_type)
        return {
            "success": True,
            "pattern_type": pattern_type,
            "patterns": patterns,
            "count": len(patterns) if patterns else 0,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Trading patterns error: {e}")
        return {"success": False, "error": str(e)}

# TRADING EXECUTION TOOLS
@tool
def get_swap_quote_tool(
    input_mint: str, 
    output_mint: str, 
    amount_sol: float, 
    slippage_bps: int = 100
) -> Dict[str, Any]:
    """
    Get swap quote from Jupiter aggregator
    
    Args:
        input_mint: Input token mint address
        output_mint: Output token mint address
        amount_sol: Amount in SOL to swap
        slippage_bps: Slippage tolerance in basis points
    """
    try:
        # Convert SOL to lamports for Jupiter API
        amount_lamports = int(amount_sol * 1e9)
        quote = get_quote(input_mint, output_mint, amount_lamports)
        
        return {
            "success": True,
            "quote": quote,
            "input_mint": input_mint,
            "output_mint": output_mint,
            "amount_sol": amount_sol,
            "amount_lamports": amount_lamports,
            "slippage_bps": slippage_bps,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Swap quote error: {e}")
        return {"success": False, "error": str(e)}

@tool
def execute_trade_tool(
    trade_type: str,
    token_address: str, 
    amount_sol: float,
    quote_data: Dict,
    dry_run: bool = True,
    reasoning: str = ""
) -> Dict[str, Any]:
    """
    Execute a token trade (buy/sell)
    
    Args:
        trade_type: Type of trade to execute (buy/sell)
        token_address: Token mint address
        amount_sol: Amount in SOL
        quote_data: Quote data from get_swap_quote
        dry_run: Whether to simulate the trade only
        reasoning: AI reasoning for this trade
    """
    try:
        if dry_run:
            # Simulate trade execution
            return {
                "success": True,
                "message": f"Dry run: {trade_type} {amount_sol} SOL of {token_address}",
                "trade_type": trade_type,
                "token_address": token_address,
                "amount_sol": amount_sol,
                "dry_run": True,
                "reasoning": reasoning,
                "simulated_result": {
                    "transaction_id": "dry_run_simulation",
                    "status": "simulated_success"
                },
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Real trade execution
            if not quote_data:
                return {"success": False, "error": "No quote data provided"}
            
            # Get transaction from Jupiter
            transaction = get_swap_transaction(quote_data)
            
            if not transaction:
                return {"success": False, "error": "Failed to get transaction from Jupiter"}
            
            # Send transaction
            result = send_serialized_transaction(transaction)
            
            return {
                "success": True,
                "message": f"Executed {trade_type} of {amount_sol} SOL for {token_address}",
                "trade_type": trade_type,
                "token_address": token_address,
                "amount_sol": amount_sol,
                "dry_run": False,
                "reasoning": reasoning,
                "transaction_result": result,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Trade execution error: {e}")
        return {"success": False, "error": str(e)}

# LEARNING AND MEMORY TOOLS
@tool
def save_trading_experience_tool(
    token_address: str,
    trading_data: Dict,
    ai_reasoning: str
) -> Dict[str, Any]:
    """
    Save trading experience to memory for future learning
    
    Args:
        token_address: Token mint address
        trading_data: Complete trading experience data
        ai_reasoning: AI reasoning and lessons learned
    """
    try:
        # Add AI reasoning to trading data
        enhanced_data = trading_data.copy()
        enhanced_data["ai_reasoning"] = ai_reasoning
        enhanced_data["timestamp"] = datetime.now().isoformat()
        
        doc_id = add_trading_experience(token_address, enhanced_data)
        return {
            "success": True,
            "document_id": doc_id,
            "token_address": token_address,
            "experience_saved": True,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Save trading experience error: {e}")
        return {"success": False, "error": str(e)}

# SYSTEM STATUS TOOLS
@tool
def check_system_status_tool() -> Dict[str, Any]:
    """Check status of all data sources and trading systems"""
    try:
        rugcheck_health = check_rugcheck_api_health()
        social_health = check_social_intelligence_health()
        enrichment_caps = get_unified_enrichment_capabilities()
        
        return {
            "success": True,
            "system_status": {
                "rugcheck": rugcheck_health,
                "social_intelligence": social_health,
                "enrichment_capabilities": enrichment_caps,
                "vector_store": astra_store.get_stats() if hasattr(astra_store, 'get_stats') else {},
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"System status check error: {e}")
        return {"success": False, "error": str(e)}

@tool
def get_market_overview_tool() -> Dict[str, Any]:
    """Get comprehensive market overview and conditions"""
    try:
        discovery_caps = get_discovery_capabilities()
        return {
            "success": True,
            "market_overview": {
                "discovery_capabilities": discovery_caps,
                "timestamp": datetime.now().isoformat(),
                "note": "Comprehensive market analysis available"
            }
        }
    except Exception as e:
        logger.error(f"Market overview error: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# COMPLETE LANGGRAPH TRADING AGENT
# ============================================================================

class CompleteLangGraphTradingAgent:
    """Complete LangGraph Trading Agent - ALL original functionality preserved"""
    
    def __init__(self):
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        
        # Use ChatAnthropic with bind_tools (proper LangGraph pattern)
        self.model = ChatAnthropic(
            model="claude-opus-4-20250514",
            temperature=0.1,
            api_key=self.anthropic_key
        )
        
        # ALL tools from original implementation
        self.tools = [
            # Wallet and Portfolio Tools
            get_wallet_balance_tool,
            get_portfolio_summary_tool,
            
            # Token Discovery Tools
            discover_tokens_tool,
            filter_tokens_tool,
            sort_tokens_tool,
            
            # Data Collection Tools
            get_comprehensive_token_data_tool,
            get_safety_data_tool,
            get_social_data_tool,
            
            # Analysis and Memory Tools
            search_trading_history_tool,
            find_similar_tokens_tool,
            get_trading_patterns_tool,
            
            # Trading Execution Tools
            get_swap_quote_tool,
            execute_trade_tool,
            
            # Learning and Memory Tools
            save_trading_experience_tool,
            
            # System Status Tools
            check_system_status_tool,
            get_market_overview_tool
        ]
        
        # Bind tools to model (proper LangGraph pattern)
        self.model_with_tools = self.model.bind_tools(
            self.tools,
            parallel_tool_calls=False  # Execute tools sequentially for better control
        )
        
        # Create React Agent (proper LangGraph pattern)
        self.agent = create_react_agent(
            model=self.model,
            tools=self.tools,
            prompt=self._create_comprehensive_system_prompt()  # ✅ CORRECT
        )
        
        logger.info("✅ Complete LangGraph Trading Agent initialized with ALL original functionality")
    
    def _create_comprehensive_system_prompt(self) -> str:
        """Create the comprehensive system prompt matching the original"""
        return """You are an elite crypto trading AI with deep expertise in Solana DeFi and memecoin markets. You have access to comprehensive tools for discovery, analysis, and execution. Your goal is to maximize portfolio growth through intelligent trading decisions.

🧠 AI TRADING PHILOSOPHY:
- Target 15-100%+ gains per position  
- Typical hold time: 1-24 hours
- Maximum loss tolerance: -15%
- Position sizing: 1-8% of portfolio per trade
- Focus on momentum, safety, and viral potential
- Learn from historical patterns and similar tokens
- Adapt strategy based on market conditions

🔧 COMPREHENSIVE TOOLSET:
You have access to powerful tools for:
- Token Discovery: Multiple strategies (boosted, profiles, custom search)
- Data Collection: RugCheck safety, TweetScout social, DexScreener market
- Analysis: Comprehensive raw data aggregation from all sources
- Historical Learning: Search past trades, find similar tokens, identify patterns
- Trading Execution: Jupiter quotes and swap execution
- Memory Management: Save experiences for continuous learning

🎮 TRADING CYCLE WORKFLOW:
1. **PORTFOLIO ANALYSIS**: Review current positions for exit opportunities
2. **MARKET INTELLIGENCE**: Assess overall market conditions and sentiment
3. **TOKEN DISCOVERY**: Find promising opportunities using multiple strategies
4. **COMPREHENSIVE ANALYSIS**: Gather and analyze raw data from all sources
5. **HISTORICAL LEARNING**: Search for similar past experiences and patterns
6. **STRATEGIC DECISION**: Make informed buy/sell/hold decisions
7. **EXECUTION PLANNING**: Prepare trades with proper sizing and reasoning
8. **TRADE EXECUTION**: Execute approved trades (respecting dry run mode)
9. **EXPERIENCE LOGGING**: Save analysis and decisions for future learning

⚡ DECISION-MAKING GUIDELINES:
- Use multiple data sources for each analysis
- Cross-reference historical similar trades
- Always prioritize safety analysis before entry
- Consider social momentum and viral potential
- Factor in market conditions and timing
- Be decisive but risk-aware
- Document reasoning for all decisions
- Learn from both successes and failures

🚨 CRITICAL INSTRUCTIONS:
- You MUST use tools to complete this cycle
- Start EVERY cycle by checking wallet balance
- Use discovery tools to find opportunities
- Analyze tokens comprehensively before decisions
- Check safety data for all potential trades
- Save experiences for continuous learning

Begin each cycle by using get_wallet_balance_tool, then proceed through the complete workflow."""

    def run_trading_cycle(self, initial_state: AgentState = None) -> AgentState:
        """Run a complete trading cycle using proper LangGraph implementation"""
        try:
            # Load or create state
            if initial_state is None:
                state = load_agent_state() or create_initial_state()
            else:
                state = initial_state
            
            # Update portfolio metrics
            state = update_portfolio_metrics(state)
            
            # Get current context
            wallet_balance = state.get("wallet_balance_sol", 0)
            cycles_completed = state.get("cycles_completed", 0)
            active_positions = state.get("active_positions", [])
            ai_strategy = state.get("ai_strategy", "discovery_and_analysis")
            trading_mode = state.get("trading_mode", "dry_run")
            
            # Calculate portfolio metrics
            total_position_value = sum(pos.get("current_value_sol", 0) for pos in active_positions)
            total_portfolio_value = wallet_balance + total_position_value
            
            # Create comprehensive trading context (matching original prompt structure)
            context_message = f"""🎯 TRADING CYCLE {cycles_completed + 1}

🎯 CURRENT PORTFOLIO STATUS:
- Wallet Balance: {wallet_balance:.4f} SOL
- Active Positions: {len(active_positions)}
- Total Portfolio Value: {total_portfolio_value:.4f} SOL  
- Cash Allocation: {(wallet_balance/total_portfolio_value*100) if total_portfolio_value > 0 else 100:.1f}%
- Cycles Completed: {cycles_completed}
- Current Strategy: {ai_strategy}
- Trading Mode: {trading_mode.upper()}

📊 ACTIVE POSITIONS OVERVIEW:
{json.dumps([{
    'symbol': pos.get('token_symbol', 'Unknown'),
    'value_sol': pos.get('current_value_sol', 0),
    'profit_pct': pos.get('current_profit_percentage', 0),
    'hold_time_hours': pos.get('hold_time_hours', 0),
    'entry_reasoning': pos.get('reason', 'Unknown')[:100] + "..." if len(pos.get('reason', '')) > 100 else pos.get('reason', 'Unknown')
} for pos in active_positions], indent=2)}

🎯 CURRENT CYCLE OBJECTIVES:
1. Start by checking your wallet balance using get_wallet_balance_tool
2. Assess system status and data source availability using check_system_status_tool
3. Review active positions for management opportunities using get_portfolio_summary_tool
4. Discover new token opportunities using discover_tokens_tool with comprehensive strategies
5. Conduct thorough analysis using get_comprehensive_token_data_tool and get_safety_data_tool
6. Search historical experiences using search_trading_history_tool for learning and validation
7. Make strategic trading decisions with detailed reasoning
8. Execute trades using execute_trade_tool (in {trading_mode.upper()} mode)
9. Save experiences to memory using save_trading_experience_tool for continuous improvement

Execute a complete trading analysis cycle using your comprehensive toolset. Begin now with get_wallet_balance_tool."""
            
            logger.info(f"🚀 Starting complete LangGraph trading cycle {cycles_completed + 1}")
            
            # Use LangGraph agent with proper message format
            response = self.agent.invoke({
                "messages": [HumanMessage(content=context_message)]
            })
            
            # Extract final message and update state
            final_messages = response.get("messages", [])
            if final_messages:
                final_message = final_messages[-1]
                if hasattr(final_message, 'content'):
                    state["agent_reasoning"] = final_message.content
                    logger.info(f"💭 AI Response: {final_message.content[:200]}...")
            
            # Update state
            state["cycles_completed"] = cycles_completed + 1
            state["last_update_timestamp"] = datetime.now().isoformat()
            state["ai_strategy"] = "complete_langgraph_execution"
            
            # Check if tools were actually used
            tool_messages = [msg for msg in final_messages if hasattr(msg, 'name')]
            tools_used = [msg.name for msg in tool_messages if hasattr(msg, 'name')]
            state["tools_used_this_cycle"] = tools_used
            
            if tools_used:
                logger.info(f"✅ Tools used: {', '.join(tools_used)}")
                state["tools_executed_successfully"] = True
            else:
                logger.warning("⚠️ No tools were used in this cycle")
                state["tools_executed_successfully"] = False
            
            # Save state
            save_agent_state(state)
            
            return state
            
        except Exception as e:
            logger.error(f"❌ Complete LangGraph trading cycle error: {e}")
            
            # Return error state but still progress
            error_state = initial_state or create_initial_state()
            error_state["cycles_completed"] = error_state.get("cycles_completed", 0) + 1
            error_state["error_log"] = error_state.get("error_log", []) + [{
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "error_type": "complete_langgraph_execution"
            }]
            error_state["agent_reasoning"] = f"Complete LangGraph execution error: {str(e)}"
            
            save_agent_state(error_state)
            return error_state

# ============================================================================
# USAGE FUNCTIONS
# ============================================================================

# Global instance
complete_langgraph_agent = CompleteLangGraphTradingAgent()

def run_langgraph_trading_cycle(state: AgentState = None) -> AgentState:
    """Main function to run complete LangGraph trading cycle with ALL functionality"""
    return complete_langgraph_agent.run_trading_cycle(state)

def test_langgraph_tools():
    """Test that ALL LangGraph tools work correctly"""
    print("🧪 Testing Complete LangGraph Tools...")
    
    test_results = {}
    
    # Test critical tools
    critical_tools = [
        ("Wallet Balance", get_wallet_balance_tool),
        ("Portfolio Summary", get_portfolio_summary_tool),
        ("Token Discovery", lambda: discover_tokens_tool.invoke({"strategy": "boosted_latest", "limit": 5})),
        ("System Status", check_system_status_tool),
        ("Market Overview", get_market_overview_tool)
    ]
    
    for tool_name, tool_func in critical_tools:
        print(f"Testing {tool_name}...")
        try:
            if callable(tool_func):
                if hasattr(tool_func, 'invoke'):
                    result = tool_func.invoke({})
                else:
                    result = tool_func()
            else:
                result = tool_func
            
            success = result.get('success', False) if isinstance(result, dict) else bool(result)
            test_results[tool_name] = success
            print(f"   {'✅' if success else '❌'} {tool_name}")
            
        except Exception as e:
            print(f"   ❌ {tool_name}: {e}")
            test_results[tool_name] = False
    
    # Test full agent
    print("Testing complete agent...")
    try:
        result = complete_langgraph_agent.run_trading_cycle()
        tools_used = result.get("tools_used_this_cycle", [])
        cycles = result.get("cycles_completed", 0)
        
        print(f"   📊 Cycle completed: {cycles}")
        print(f"   🔧 Tools used: {tools_used}")
        
        if tools_used:
            print("   ✅ SUCCESS: Complete agent is calling tools!")
            test_results["Complete Agent"] = True
        else:
            print("   ❌ FAILURE: Complete agent not calling tools")
            test_results["Complete Agent"] = False
            
    except Exception as e:
        print(f"   ❌ Complete agent test failed: {e}")
        test_results["Complete Agent"] = False
    
    # Summary
    passed = sum(test_results.values())
    total = len(test_results)
    
    print(f"\n🎯 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Complete LangGraph implementation is working correctly")
        return True
    else:
        print("⚠️ Some tests failed. Check the errors above.")
        return False

# For backwards compatibility
def run_pure_ai_trading_agent(initial_state=None):
    """Backwards compatibility function"""
    return run_langgraph_trading_cycle(initial_state)

if __name__ == "__main__":
    success = test_langgraph_tools()
    print(f"\nComplete LangGraph implementation test: {'✅ PASSED' if success else '❌ FAILED'}")
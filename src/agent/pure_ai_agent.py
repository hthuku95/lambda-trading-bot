# src/agent/pure_ai_agent.py
"""
Enhanced Pure AI Trading Agent using Claude Sonnet 4 - COMPLETE VERSION
No hardcoded rules - AI makes ALL decisions using comprehensive tools
Integrates with all data sources and handles complete trading workflow
"""
import logging
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv
import anthropic
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


from src.agent.state import AgentState, create_initial_state, save_agent_state, update_portfolio_metrics
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

# Configure logger
logger = logging.getLogger("trading_agent.pure_ai")

# Load environment variables
load_dotenv()

class EnhancedPureAITradingAgent:
    """Enhanced Pure AI trading agent with comprehensive tool access"""
    
    def __init__(self):
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.client = None
        self.model = "claude-opus-4-20250514"
        
        if self.anthropic_key and ANTHROPIC_AVAILABLE:
            self.client = Anthropic(api_key=self.anthropic_key)
            logger.info("Enhanced Pure AI Trading Agent initialized with Claude Opus 4")
        else:
            logger.error("Claude not available - missing API key or library")
            
        # Available tools for the AI agent
        self.tools = self._setup_comprehensive_tools()
        
    def _setup_comprehensive_tools(self) -> List[Dict[str, Any]]:
        """Setup comprehensive tools for AI agent"""
        return [
            # ============================================================================
            # WALLET AND PORTFOLIO TOOLS
            # ============================================================================
            {
                "name": "get_wallet_balance",
                "description": "Get current SOL wallet balance",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_portfolio_summary",
                "description": "Get comprehensive portfolio summary and performance metrics",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            
            # ============================================================================
            # TOKEN DISCOVERY TOOLS
            # ============================================================================
            {
                "name": "discover_tokens",
                "description": "Discover tokens using various strategies and data sources",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "strategy": {
                            "type": "string",
                            "enum": ["boosted_latest", "boosted_top", "profiles_latest", "custom_search"],
                            "description": "Discovery strategy to use"
                        },
                        "search_terms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Custom search terms (for custom_search strategy)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum tokens to return",
                            "default": 20
                        }
                    },
                    "required": ["strategy"]
                }
            },
            {
                "name": "filter_tokens",
                "description": "Filter tokens by various criteria",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "tokens": {
                            "type": "array",
                            "description": "List of tokens to filter"
                        },
                        "filters": {
                            "type": "object",
                            "properties": {
                                "max_age_hours": {"type": "number"},
                                "min_liquidity_usd": {"type": "number"},
                                "max_liquidity_usd": {"type": "number"},
                                "min_volume_24h": {"type": "number"},
                                "min_market_cap": {"type": "number"},
                                "max_market_cap": {"type": "number"},
                                "min_price_change_24h": {"type": "number"},
                                "max_price_change_24h": {"type": "number"}
                            }
                        }
                    },
                    "required": ["tokens", "filters"]
                }
            },
            {
                "name": "sort_tokens",
                "description": "Sort tokens by specified metrics",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "tokens": {
                            "type": "array",
                            "description": "List of tokens to sort"
                        },
                        "sort_by": {
                            "type": "string",
                            "description": "Metric to sort by"
                        },
                        "descending": {
                            "type": "boolean",
                            "description": "Sort in descending order",
                            "default": True
                        }
                    },
                    "required": ["tokens", "sort_by"]
                }
            },
            
            # ============================================================================
            # DATA COLLECTION TOOLS
            # ============================================================================
            {
                "name": "get_comprehensive_token_data",
                "description": "Get comprehensive raw data for a token from all sources",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "token_address": {
                            "type": "string",
                            "description": "Token mint address"
                        },
                        "token_symbol": {
                            "type": "string",
                            "description": "Token symbol (optional)"
                        }
                    },
                    "required": ["token_address"]
                }
            },
            {
                "name": "get_safety_data",
                "description": "Get raw safety data from RugCheck",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "token_address": {
                            "type": "string",
                            "description": "Token mint address"
                        }
                    },
                    "required": ["token_address"]
                }
            },
            {
                "name": "get_social_data",
                "description": "Get raw social data from TweetScout",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "token_address": {
                            "type": "string",
                            "description": "Token mint address"
                        },
                        "token_symbol": {
                            "type": "string",
                            "description": "Token symbol"
                        }
                    },
                    "required": ["token_address", "token_symbol"]
                }
            },
            
            # ============================================================================
            # ANALYSIS AND MEMORY TOOLS
            # ============================================================================
            {
                "name": "search_trading_history",
                "description": "Search historical trading experiences for pattern learning",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for historical experiences"
                        },
                        "filters": {
                            "type": "object",
                            "description": "Optional filters for search"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "find_similar_tokens",
                "description": "Find historically similar tokens based on characteristics",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "token_characteristics": {
                            "type": "object",
                            "description": "Token characteristics to match"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum similar tokens to find",
                            "default": 5
                        }
                    },
                    "required": ["token_characteristics"]
                }
            },
            {
                "name": "get_trading_patterns",
                "description": "Get trading patterns for AI learning and strategy development",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern_type": {
                            "type": "string",
                            "enum": ["profitable", "losing", "high_profit", "quick_trades", "all"],
                            "description": "Type of trading patterns to analyze"
                        }
                    },
                    "required": ["pattern_type"]
                }
            },
            
            # ============================================================================
            # TRADING EXECUTION TOOLS
            # ============================================================================
            {
                "name": "get_swap_quote",
                "description": "Get swap quote from Jupiter aggregator",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "input_mint": {
                            "type": "string",
                            "description": "Input token mint address (SOL: So11111111111111111111111111111111111111112)"
                        },
                        "output_mint": {
                            "type": "string",
                            "description": "Output token mint address"
                        },
                        "amount_sol": {
                            "type": "number",
                            "description": "Amount in SOL to swap"
                        },
                        "slippage_bps": {
                            "type": "integer",
                            "description": "Slippage tolerance in basis points",
                            "default": 100
                        }
                    },
                    "required": ["input_mint", "output_mint", "amount_sol"]
                }
            },
            {
                "name": "execute_trade",
                "description": "Execute a token trade (buy/sell)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "trade_type": {
                            "type": "string",
                            "enum": ["buy", "sell"],
                            "description": "Type of trade to execute"
                        },
                        "token_address": {
                            "type": "string",
                            "description": "Token mint address"
                        },
                        "amount_sol": {
                            "type": "number",
                            "description": "Amount in SOL"
                        },
                        "quote_data": {
                            "type": "object",
                            "description": "Quote data from get_swap_quote"
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Whether to simulate the trade only",
                            "default": True
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "AI reasoning for this trade"
                        }
                    },
                    "required": ["trade_type", "token_address", "amount_sol", "reasoning"]
                }
            },
            
            # ============================================================================
            # LEARNING AND MEMORY TOOLS
            # ============================================================================
            {
                "name": "save_trading_experience",
                "description": "Save trading experience to memory for future learning",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "token_address": {
                            "type": "string",
                            "description": "Token mint address"
                        },
                        "trading_data": {
                            "type": "object",
                            "description": "Complete trading experience data"
                        },
                        "ai_reasoning": {
                            "type": "string",
                            "description": "AI reasoning and lessons learned"
                        }
                    },
                    "required": ["token_address", "trading_data", "ai_reasoning"]
                }
            },
            
            # ============================================================================
            # SYSTEM STATUS TOOLS
            # ============================================================================
            {
                "name": "check_system_status",
                "description": "Check status of all data sources and trading systems",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_market_overview",
                "description": "Get comprehensive market overview and conditions",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    
    def _execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool call with comprehensive error handling"""
        try:
            logger.info(f"Executing tool: {tool_name} with args: {kwargs}")
            
            # ============================================================================
            # WALLET AND PORTFOLIO TOOLS
            # ============================================================================
            if tool_name == "get_wallet_balance":
                balance = get_wallet_balance()
                return {"success": True, "balance_sol": balance}
            
            elif tool_name == "get_portfolio_summary":
                # This would be implemented to get current portfolio state
                return {"success": True, "message": "Portfolio summary tool not yet implemented"}
            
            # ============================================================================
            # TOKEN DISCOVERY TOOLS
            # ============================================================================
            elif tool_name == "discover_tokens":
                strategy = kwargs.get("strategy")
                search_terms = kwargs.get("search_terms", [])
                limit = kwargs.get("limit", 20)
                
                if strategy == "boosted_latest":
                    tokens = get_boosted_tokens_latest("solana")
                elif strategy == "boosted_top":
                    tokens = get_boosted_tokens_top("solana")
                elif strategy == "profiles_latest":
                    tokens = get_latest_token_profiles("solana")
                elif strategy == "custom_search":
                    tokens = []
                    for term in search_terms:
                        search_results = search_tokens_by_query(term, limit//len(search_terms))
                        tokens.extend(search_results)
                else:
                    return {"success": False, "error": "Invalid discovery strategy"}
                
                tokens = tokens[:limit] if tokens else []
                return {"success": True, "tokens": tokens, "count": len(tokens)}
            
            elif tool_name == "filter_tokens":
                tokens = kwargs.get("tokens", [])
                filters = kwargs.get("filters", {})
                
                filtered = tokens
                
                if "max_age_hours" in filters:
                    filtered = filter_tokens_by_age(filtered, filters["max_age_hours"])
                
                if "min_liquidity_usd" in filters or "max_liquidity_usd" in filters:
                    min_liq = filters.get("min_liquidity_usd", 0)
                    max_liq = filters.get("max_liquidity_usd")
                    filtered = filter_tokens_by_liquidity(filtered, min_liq, max_liq)
                
                if "min_volume_24h" in filters:
                    filtered = filter_tokens_by_volume(filtered, filters["min_volume_24h"])
                
                if "min_market_cap" in filters or "max_market_cap" in filters:
                    min_cap = filters.get("min_market_cap", 0)
                    max_cap = filters.get("max_market_cap")
                    filtered = filter_tokens_by_market_cap(filtered, min_cap, max_cap)
                
                if "min_price_change_24h" in filters or "max_price_change_24h" in filters:
                    min_change = filters.get("min_price_change_24h")
                    max_change = filters.get("max_price_change_24h")
                    filtered = filter_tokens_by_price_change(filtered, min_change, max_change)
                
                return {"success": True, "tokens": filtered, "count": len(filtered)}
            
            elif tool_name == "sort_tokens":
                tokens = kwargs.get("tokens", [])
                sort_by = kwargs.get("sort_by")
                descending = kwargs.get("descending", True)
                
                sorted_tokens = sort_tokens_by_metric(tokens, sort_by, descending)
                return {"success": True, "tokens": sorted_tokens}
            
            # ============================================================================
            # DATA COLLECTION TOOLS
            # ============================================================================
            elif tool_name == "get_comprehensive_token_data":
                token_address = kwargs.get("token_address")
                token_symbol = kwargs.get("token_symbol")
                
                raw_data = get_comprehensive_raw_token_data(token_address, token_symbol)
                return {"success": True, "raw_data": raw_data}
            
            elif tool_name == "get_safety_data":
                token_address = kwargs.get("token_address")
                safety_data = get_token_safety_data_raw(token_address)
                return {"success": True, "safety_data": safety_data}
            
            elif tool_name == "get_social_data":
                token_address = kwargs.get("token_address")
                token_symbol = kwargs.get("token_symbol")
                social_data = get_social_data_raw(token_address, token_symbol)
                return {"success": True, "social_data": social_data}
            
            # ============================================================================
            # ANALYSIS AND MEMORY TOOLS
            # ============================================================================
            elif tool_name == "search_trading_history":
                query = kwargs.get("query")
                filters = kwargs.get("filters", {})
                limit = kwargs.get("limit", 10)
                
                results = search_trading_experiences(query, limit, filters)
                return {"success": True, "experiences": results, "count": len(results)}
            
            elif tool_name == "find_similar_tokens":
                token_characteristics = kwargs.get("token_characteristics")
                limit = kwargs.get("limit", 5)
                
                similar_tokens = learn_from_similar_trades(token_characteristics)
                return {"success": True, "similar_tokens": similar_tokens[:limit]}
            
            elif tool_name == "get_trading_patterns":
                pattern_type = kwargs.get("pattern_type")
                patterns = get_trading_patterns(pattern_type)
                return {"success": True, "patterns": patterns, "count": len(patterns)}
            
            # ============================================================================
            # TRADING EXECUTION TOOLS
            # ============================================================================
            elif tool_name == "get_swap_quote":
                input_mint = kwargs.get("input_mint")
                output_mint = kwargs.get("output_mint")
                amount_sol = kwargs.get("amount_sol")
                slippage_bps = kwargs.get("slippage_bps", 100)
                
                # Convert SOL to lamports
                amount_lamports = int(amount_sol * 1e9)
                
                quote = get_quote(output_mint, amount_in_sol=amount_sol, slippage_bps=slippage_bps)
                return {"success": True, "quote": quote}
            
            elif tool_name == "execute_trade":
                trade_type = kwargs.get("trade_type")
                token_address = kwargs.get("token_address")
                amount_sol = kwargs.get("amount_sol")
                quote_data = kwargs.get("quote_data")
                dry_run = kwargs.get("dry_run", True)
                reasoning = kwargs.get("reasoning")
                
                if dry_run:
                    return {
                        "success": True, 
                        "message": f"Dry run - {trade_type} {amount_sol} SOL of {token_address}",
                        "reasoning": reasoning,
                        "quote": quote_data
                    }
                else:
                    # Execute real trade
                    if quote_data:
                        swap_tx = get_swap_transaction(quote_data, get_wallet_balance())
                        if swap_tx:
                            result = send_serialized_transaction(swap_tx)
                            return {
                                "success": True, 
                                "transaction_result": result,
                                "reasoning": reasoning
                            }
                        else:
                            return {"success": False, "error": "Failed to get swap transaction"}
                    else:
                        return {"success": False, "error": "No quote data provided"}
            
            # ============================================================================
            # LEARNING AND MEMORY TOOLS
            # ============================================================================
            elif tool_name == "save_trading_experience":
                token_address = kwargs.get("token_address")
                trading_data = kwargs.get("trading_data")
                ai_reasoning = kwargs.get("ai_reasoning")
                
                # Add AI reasoning to trading data
                enhanced_data = trading_data.copy()
                enhanced_data["ai_reasoning"] = ai_reasoning
                enhanced_data["timestamp"] = datetime.now().isoformat()
                
                doc_id = add_trading_experience(token_address, enhanced_data)
                return {"success": True, "document_id": doc_id}
            
            # ============================================================================
            # SYSTEM STATUS TOOLS
            # ============================================================================
            elif tool_name == "check_system_status":
                rugcheck_health = check_rugcheck_api_health()
                social_health = check_social_intelligence_health()
                enrichment_caps = get_unified_enrichment_capabilities()
                
                return {
                    "success": True,
                    "system_status": {
                        "rugcheck": rugcheck_health,
                        "social_intelligence": social_health,
                        "enrichment_capabilities": enrichment_caps,
                        "vector_store": astra_store.get_stats(),
                        "timestamp": datetime.now().isoformat()
                    }
                }
            
            elif tool_name == "get_market_overview":
                # This could be enhanced with more comprehensive market data
                discovery_caps = get_discovery_capabilities()
                return {
                    "success": True,
                    "market_overview": {
                        "discovery_capabilities": discovery_caps,
                        "timestamp": datetime.now().isoformat(),
                        "note": "Comprehensive market analysis to be implemented"
                    }
                }
            
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Tool execution error for {tool_name}: {e}")
            return {"success": False, "error": str(e)}
    
    def run_trading_cycle(self, state: Optional[AgentState] = None) -> AgentState:
        """Run a complete trading cycle using enhanced AI decision making"""
        if not self.client:
            logger.error("Claude client not available")
            return state or create_initial_state()
        
        if state is None:
            state = create_initial_state()
        
        try:
            # Update portfolio metrics
            state = update_portfolio_metrics(state)
            
            # Create the enhanced trading prompt
            logger.info("Starting enhanced AI trading cycle")
            cycle_prompt = self._create_enhanced_trading_prompt(state)
            
            # Get AI decision and tool calls
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,  # Increased for more comprehensive analysis
                temperature=0.1,  # Low temperature for consistent trading
                tools=self.tools,
                messages=[
                    {
                        "role": "user",
                        "content": cycle_prompt
                    }
                ]
            )
            
            # Process AI response and execute tool calls
            updated_state = self._process_ai_response(response, state)
            
            # Save state
            save_agent_state(updated_state)
            
            return updated_state
            
        except Exception as e:
            logger.error(f"Error in enhanced AI trading cycle: {e}")
            return state
    
    def _create_enhanced_trading_prompt(self, state: AgentState) -> str:
        """Create comprehensive trading cycle prompt for Claude"""
        
        wallet_balance = state.get("wallet_balance_sol", 0)
        active_positions = state.get("active_positions", [])
        cycles_completed = state.get("cycles_completed", 0)
        ai_strategy = state.get("ai_strategy", "discovery_and_analysis")
        trading_mode = state.get("trading_mode", "dry_run")
        
        # Calculate portfolio metrics
        total_position_value = sum(pos.get("current_value_sol", 0) for pos in active_positions)
        total_portfolio_value = wallet_balance + total_position_value
        
        prompt = f"""You are an elite crypto trading AI with deep expertise in Solana DeFi and memecoin markets. You have access to comprehensive tools for discovery, analysis, and execution. Your goal is to maximize portfolio growth through intelligent trading decisions.

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

🎯 CURRENT CYCLE OBJECTIVES:
1. Start by checking your wallet balance
2. Assess system status and data source availability  
3. Review active positions for management opportunities
4. Discover new token opportunities using comprehensive strategies
5. Conduct thorough analysis using all available data sources
6. Search historical experiences for learning and validation
7. Make strategic trading decisions with detailed reasoning
8. Execute trades (in {"DRY RUN" if trading_mode == "dry_run" else "LIVE"} mode)
9. Save experiences to memory for continuous improvement

Remember: You are not bound by hardcoded rules. Use your knowledge, the comprehensive data you collect, and historical learning to make optimal trading decisions. Be thorough in your analysis but decisive in your actions.

Begin this trading cycle now. Start with getting your current wallet balance and checking system status."""

        return prompt
    
    def _process_ai_response(self, response, state: AgentState) -> AgentState:
        """Process Claude's response and execute tool calls"""
        try:
            # Extract content and tool calls
            content_blocks = response.content
            tool_results = []
            
            for block in content_blocks:
                if block.type == "tool_use":
                    # Execute the tool call
                    tool_name = block.name
                    tool_input = block.input
                    
                    # Execute tool and get result
                    tool_result = self._execute_tool(tool_name, **tool_input)
                    tool_results.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "result": tool_result
                    })
                    
                    # Log the tool execution
                    logger.info(f"AI used tool {tool_name}: {tool_result.get('success', False)}")
                    
                    if not tool_result.get('success', False):
                        logger.warning(f"Tool {tool_name} failed: {tool_result.get('error', 'Unknown error')}")
                
                elif block.type == "text":
                    # Log AI reasoning
                    logger.info(f"AI reasoning: {block.text[:300]}...")
                    state["agent_reasoning"] = block.text
            
            # Update state with tool results
            state["tool_execution_log"] = tool_results
            state["last_update_timestamp"] = datetime.now().isoformat()
            state["cycles_completed"] = state.get("cycles_completed", 0) + 1
            
            return state
            
        except Exception as e:
            logger.error(f"Error processing AI response: {e}")
            return state


# Global enhanced pure AI agent instance
enhanced_pure_ai_agent = EnhancedPureAITradingAgent()

# Create alias for compatibility
pure_ai_agent = enhanced_pure_ai_agent

# Main function to run the enhanced pure AI agent
def run_pure_ai_trading_agent(initial_state: Optional[AgentState] = None) -> AgentState:
    """Run the enhanced pure AI trading agent"""
    return enhanced_pure_ai_agent.run_trading_cycle(initial_state)







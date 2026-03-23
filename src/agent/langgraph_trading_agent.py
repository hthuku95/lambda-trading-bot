# src/agent/langgraph_trading_agent.py - COMPLETE IMPLEMENTATION
"""
Complete LangGraph Trading Agent Implementation
Preserves ALL functionality from the original pure_ai_agent.py
No features omitted - this is a 1:1 functional replacement using proper LangGraph patterns
"""
import os
import json
import logging
import time
import operator
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
try:
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver as _SqliteSaver
    _SQLITE_AVAILABLE = True
except ImportError:
    _SQLITE_AVAILABLE = False
from pydantic.v1 import BaseModel, Field

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
from src.blockchain.solana_client import get_wallet_balance, send_serialized_transaction, wallet

load_dotenv()
logger = logging.getLogger("trading_agent.langgraph")

# Module-level model provider tracker (updated by CompleteLangGraphTradingAgent on init)
_current_model_provider = "gemini"

# Module-level trading mode tracker — set at start of each cycle
_current_trading_mode: str = "dry_run"

# ============================================================================
# Agent State Definition for Custom Graph
# ============================================================================
class TradingAgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    agent_state: AgentState

# ============================================================================
# COMPLETE TOOL DEFINITIONS - ALL ORIGINAL FUNCTIONALITY PRESERVED
# ============================================================================

# WALLET AND PORTFOLIO TOOLS
@tool
def get_wallet_balance_tool() -> Dict[str, Any]:
    """Get current SOL wallet balance from the configured Solana wallet"""
    try:
        balance = get_wallet_balance()
        return {
            "success": True,
            "balance_sol": balance,
            "trading_mode": _current_trading_mode,
            "timestamp": datetime.now().isoformat()
        }
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
    Get raw social data (DexScreener social links + Nansen smart money signals).

    Returns DexScreener social links (Twitter/Telegram/website) AND Nansen
    smart money intelligence (holder count, flow direction, recent trades).

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


@tool
def get_nansen_smart_money_tool(
    token_address: str,
    token_symbol: str = "",
) -> Dict[str, Any]:
    """
    Get Nansen smart money intelligence for a specific token.

    Returns a rich signal combining:
    - smart_money_holder_count: How many tracked smart wallets hold this token
    - smart_money_total_value_usd: Total USD value held by smart money
    - smart_trader_net_flow_usd: Net smart trader flow (positive = accumulating)
    - whale_net_flow_usd: Net whale flow (positive = accumulating)
    - smart_money_accumulating: True if combined flow is positive
    - sm_buys_last_6h / sm_sells_last_6h: Smart money trade counts
    - sm_buy_pressure: Fraction of smart money trades that are buys (0-1)
    - nansen_indicators: Risk/reward indicator scores
    - token_information: Social links, market metadata from Nansen

    Use this before executing trades to confirm smart money conviction.
    High sm_buy_pressure + positive net_flow = strong signal.

    Args:
        token_address: Solana token mint address
        token_symbol: Token symbol (optional, for logging)
    """
    try:
        from src.data.nansen_client import get_full_nansen_signal
        signal = get_full_nansen_signal(token_address, token_symbol)
        out = str(signal)
        return out[:4000] + "\n...[truncated]" if len(out) > 4000 else out
    except Exception as e:
        logger.error(f"get_nansen_smart_money_tool error: {e}")
        return str({"success": False, "error": str(e), "token_address": token_address})


@tool
def screen_nansen_opportunities_tool(
    timeframe: str = "1h",
) -> str:
    """
    Screen Solana tokens with active smart money buying via Nansen.

    Returns up to 50 tokens sorted by smart money buy_volume DESC.
    Each token has: token_address, token_symbol, market_cap_usd, liquidity,
    price_change, buy_volume, sell_volume, netflow, nof_traders, token_age_days.

    Use this early in a trading cycle to find tokens already attracting
    smart money attention before they become mainstream news.

    Args:
        timeframe: One of 5m, 1h, 6h, 24h, 7d (default: 1h)
    """
    try:
        from src.data.nansen_client import screen_smart_money_tokens
        tokens = screen_smart_money_tokens(timeframe=timeframe, per_page=50)
        result = {
            "success": True,
            "timeframe": timeframe,
            "count": len(tokens),
            "tokens": tokens,
            "timestamp": datetime.now().isoformat(),
        }
        out = str(result)
        return out[:4000] + "\n...[truncated]" if len(out) > 4000 else out
    except Exception as e:
        logger.error(f"screen_nansen_opportunities_tool error: {e}")
        return str({"success": False, "error": str(e)})


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
    limit: int = 5,
    agent_state: AgentState = None
) -> Dict[str, Any]:
    """
    Find historically similar tokens based on characteristics

    Args:
        token_characteristics: Token characteristics to match
        limit: Maximum similar tokens to find
        agent_state: The current state of the agent, including model_provider.
    """
    try:
        model_provider = agent_state.get("model_provider", "voyageai") if agent_state else "voyageai"
        similar_tokens = learn_from_similar_trades(token_characteristics, model_provider=model_provider)
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
class GetSwapQuoteInput(BaseModel):
    input_mint: str = Field(description="Input token mint address (e.g., 'So11111111111111111111111111111111111111112' for SOL)")
    output_mint: str = Field(description="Output token mint address")
    amount_sol: float = Field(description="Amount in SOL to swap")
    slippage_bps: int = Field(default=100, description="Slippage tolerance in basis points")

@tool(args_schema=GetSwapQuoteInput)
def get_swap_quote_tool(
    input_mint: str,
    output_mint: str,
    amount_sol: float,
    slippage_bps: int = 100
) -> Dict[str, Any]:
    """
    Get swap quote from Jupiter aggregator.
    """
    try:
        # Cap slippage to 500 bps (5%) max to prevent sandwich attacks
        MAX_SLIPPAGE_BPS = 500
        if slippage_bps > MAX_SLIPPAGE_BPS:
            logger.warning(f"Slippage {slippage_bps} bps exceeds max {MAX_SLIPPAGE_BPS} bps — capping")
            slippage_bps = MAX_SLIPPAGE_BPS
        # The Pydantic model ensures amount_sol is a float.
        # Convert SOL to lamports for Jupiter API
        amount_lamports = int(amount_sol * 1e9)
        quote = get_quote(output_mint, input_mint=input_mint, amount=amount_lamports, slippage_bps=slippage_bps)

        if quote is None:
            return {"success": False, "error": "Failed to retrieve quote from Jupiter."}

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

# ─────────────────────────────────────────────────────────────────────────────
# HUMAN-IN-THE-LOOP APPROVAL SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

_PROJECT_ROOT  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_APPROVAL_FILE = os.path.join(_PROJECT_ROOT, "trade_approvals.json")
_PENDING_FILE  = os.path.join(_PROJECT_ROOT, "trade_pending_approval.json")


def _write_pending_approval(
    trade_id: str,
    trade_type: str,
    token_address: str,
    amount_sol: float,
    reasoning: str,
    threshold_sol: float,
    expires_at: str,
) -> None:
    """Write a pending trade to disk so the dashboard can surface it."""
    import json as _json
    pending = {
        "trade_id": trade_id,
        "trade_type": trade_type,
        "token_address": token_address,
        "amount_sol": amount_sol,
        "reasoning": reasoning,
        "threshold_sol": threshold_sol,
        "requested_at": datetime.now().isoformat(),
        "expires_at": expires_at,
        "status": "pending",
    }
    try:
        with open(_PENDING_FILE, "w") as f:
            _json.dump(pending, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not write pending approval file: {e}")


def _await_human_approval(
    trade_type: str,
    token_address: str,
    amount_sol: float,
    reasoning: str,
    threshold_sol: float,
) -> tuple[bool, float]:
    """
    Wait up to HUMAN_APPROVAL_TIMEOUT_MINUTES for a human to approve a large
    trade by writing to trade_approvals.json.

    Returns (approved: bool, final_amount_sol: float).
    If approved: returns (True, approved_amount).
    If timed out: returns (False, amount_sol) — caller caps the amount.

    The approval file schema expected from the dashboard:
        {
          "trade_id": "<uuid>",
          "approved": true,
          "amount_sol": 4.5,       # operator can reduce the amount
          "approved_at": "..."
        }
    """
    import json as _json
    import uuid as _uuid

    timeout_minutes = int(os.getenv("HUMAN_APPROVAL_TIMEOUT_MINUTES", "60"))
    poll_interval   = 10  # seconds between file checks
    trade_id = str(_uuid.uuid4())[:12]
    expires_at = (
        datetime.now() + timedelta(minutes=timeout_minutes)
    ).isoformat()

    logger.warning(
        f"🔔 LARGE TRADE REQUIRES APPROVAL: {trade_type.upper()} {amount_sol:.2f} SOL "
        f"of {token_address[:8]}... (threshold {threshold_sol:.1f} SOL). "
        f"trade_id={trade_id}  expires={expires_at}"
    )
    _write_pending_approval(
        trade_id, trade_type, token_address, amount_sol, reasoning, threshold_sol, expires_at
    )

    deadline = datetime.now() + timedelta(minutes=timeout_minutes)
    while datetime.now() < deadline:
        time.sleep(poll_interval)
        try:
            if not os.path.exists(_APPROVAL_FILE):
                continue
            with open(_APPROVAL_FILE) as f:
                data = _json.load(f)
            if data.get("trade_id") != trade_id:
                continue
            if data.get("approved"):
                approved_amount = float(data.get("amount_sol", amount_sol))
                logger.info(
                    f"✅ Trade {trade_id} approved by operator "
                    f"({approved_amount:.2f} SOL)"
                )
                # Clean up files
                for path in (_APPROVAL_FILE, _PENDING_FILE):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                return True, approved_amount
            else:
                # Explicit rejection
                logger.info(f"❌ Trade {trade_id} rejected by operator")
                for path in (_APPROVAL_FILE, _PENDING_FILE):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                return False, amount_sol
        except Exception:
            continue

    # Timeout — clean up pending file
    try:
        os.remove(_PENDING_FILE)
    except OSError:
        pass
    logger.info(
        f"⏰ Trade {trade_id} approval timed out after {timeout_minutes}min"
    )
    return False, amount_sol


class ExecuteTradeInput(BaseModel):
    trade_type: str = Field(description="Type of trade to execute (buy/sell)")
    token_address: str = Field(description="Token mint address")
    amount_sol: float = Field(description="Amount in SOL")
    quote_data: Dict = Field(description="Quote data from get_swap_quote")
    dry_run: bool = Field(default=True, description="Whether to simulate the trade only")
    reasoning: str = Field(default="", description="AI reasoning for this trade")

@tool(args_schema=ExecuteTradeInput)
def execute_trade_tool(
    trade_type: str,
    token_address: str,
    amount_sol: float,
    quote_data: Dict,
    dry_run: bool = True,
    reasoning: str = ""
) -> Dict[str, Any]:
    """
    Execute a token trade (buy/sell).
    """
    try:
        user_pubkey = wallet.pubkey()
        logger.info(f"Executing trade for user: {user_pubkey}")

        # Safety: Cap position size to MAX_POSITION_SIZE_SOL (default 0.5 SOL or env override)
        max_position_sol = float(os.getenv("MAX_POSITION_SIZE_SOL", "0.5"))
        if amount_sol > max_position_sol:
            logger.warning(f"Trade amount {amount_sol} SOL exceeds max {max_position_sol} SOL — capping")
            amount_sol = max_position_sol

        # Human-in-the-loop gate for large live trades
        # Trades >= HUMAN_APPROVAL_THRESHOLD_SOL (default 5.0) require explicit
        # approval written to trade_approvals.json by the dashboard or operator.
        # If no approval arrives within HUMAN_APPROVAL_TIMEOUT_MINUTES the trade
        # is capped at (threshold - 0.1) SOL and proceeds automatically so the
        # daemon never stalls during unattended 24/7 operation.
        if not dry_run:
            threshold_sol = float(os.getenv("HUMAN_APPROVAL_THRESHOLD_SOL", "5.0"))
            if amount_sol >= threshold_sol:
                approved, final_amount = _await_human_approval(
                    trade_type=trade_type,
                    token_address=token_address,
                    amount_sol=amount_sol,
                    reasoning=reasoning,
                    threshold_sol=threshold_sol,
                )
                if not approved:
                    # Auto-proceed at just-below threshold after timeout
                    amount_sol = threshold_sol - 0.1
                    logger.info(
                        f"Human approval timeout — proceeding with capped amount "
                        f"{amount_sol:.2f} SOL (threshold {threshold_sol:.1f} SOL)"
                    )
                else:
                    amount_sol = final_amount  # operator may have adjusted amount

        if dry_run:
            # Build real transaction from the real Jupiter quote but do NOT submit to chain
            if not quote_data:
                return {"success": False, "error": "No quote data provided for dry-run transaction build"}
            transaction = get_swap_transaction(quote_data, str(user_pubkey))
            return {
                "success": True,
                "message": f"[DRY RUN] {trade_type.upper()} {amount_sol:.4f} SOL of {token_address} — transaction built, not submitted",
                "trade_type": trade_type,
                "token_address": token_address,
                "amount_sol": amount_sol,
                "dry_run": True,
                "transaction_ready": transaction is not None,
                "reasoning": reasoning,
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Real trade execution
            if not quote_data:
                return {"success": False, "error": "No quote data provided"}

            # Get transaction from Jupiter, now with the required user_pubkey
            transaction = get_swap_transaction(quote_data, user_pubkey)

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

# ============================================================================
# DB QUERY TOOLS — backed by src/db/query_store.py
# ============================================================================

@tool
def query_trade_history_db_tool(
    model_provider: str = None,
    token_address: str = None,
    trade_type: str = None,
    days_back: int = 30,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Query past trades from the PostgreSQL database.
    Use this to check how a specific token was traded before, identify losing patterns,
    or see what trades a model made recently.
    """
    try:
        from src.db.query_store import get_trade_history
        trades = get_trade_history(
            model_provider=model_provider,
            token_address=token_address,
            trade_type=trade_type,
            days_back=days_back,
            limit=limit,
        )
        return {"success": True, "trades": trades, "count": len(trades)}
    except Exception as e:
        logger.error(f"query_trade_history_db_tool error: {e}")
        return {"success": False, "error": str(e), "trades": []}


@tool
def get_performance_analytics_db_tool(
    model_provider: str = None,
    days_back: int = 7,
) -> Dict[str, Any]:
    """
    Get performance analytics from the database: win rate, avg P&L, Sharpe ratio,
    max drawdown, best/worst trades. Use to evaluate recent strategy effectiveness.
    """
    try:
        from src.db.query_store import get_performance_summary
        summary = get_performance_summary(model_provider=model_provider, days_back=days_back)
        return {"success": True, "analytics": summary}
    except Exception as e:
        logger.error(f"get_performance_analytics_db_tool error: {e}")
        return {"success": False, "error": str(e), "analytics": {}}


@tool
def compare_model_performance_db_tool(days_back: int = 30) -> Dict[str, Any]:
    """
    Compare Claude vs Gemini performance side-by-side: sessions, trades, win rate,
    total PnL, average profit. Use to determine which model strategy is outperforming.
    """
    try:
        from src.db.query_store import compare_model_performance
        comparison = compare_model_performance(days_back=days_back)
        return {"success": True, "comparison": comparison}
    except Exception as e:
        logger.error(f"compare_model_performance_db_tool error: {e}")
        return {"success": False, "error": str(e), "comparison": {}}


@tool
def get_session_history_db_tool(limit: int = 10) -> Dict[str, Any]:
    """
    Get past training session records: start/end times, cycle count, final balance,
    total profit. Use to understand how previous training runs performed.
    """
    try:
        from src.db.query_store import get_session_history
        sessions = get_session_history(limit=limit)
        return {"success": True, "sessions": sessions, "count": len(sessions)}
    except Exception as e:
        logger.error(f"get_session_history_db_tool error: {e}")
        return {"success": False, "error": str(e), "sessions": []}


@tool
def search_system_logs_db_tool(
    level: str = None,
    keyword: str = None,
    logger_name: str = None,
    hours_back: int = 24,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Search structured system logs in the database by log level (ERROR/WARNING/INFO),
    keyword, or logger name. Use to diagnose issues or review recent agent activity.
    """
    try:
        from src.db.query_store import search_logs
        logs = search_logs(
            level=level,
            keyword=keyword,
            logger_name=logger_name,
            hours_back=hours_back,
            limit=limit,
        )
        return {"success": True, "logs": logs, "count": len(logs)}
    except Exception as e:
        logger.error(f"search_system_logs_db_tool error: {e}")
        return {"success": False, "error": str(e), "logs": []}


@tool
def get_top_tokens_db_tool(
    metric: str = "profit_percentage",
    limit: int = 10,
    days_back: int = 30,
) -> Dict[str, Any]:
    """
    Get historically best-performing tokens from the database.
    metric options: 'profit_percentage' (avg return), 'trade_count' (most traded),
    'total_pnl_sol' (highest total profit). Use to weight token selection.
    """
    try:
        from src.db.query_store import get_top_performing_tokens
        tokens = get_top_performing_tokens(metric=metric, limit=limit, days_back=days_back)
        return {"success": True, "tokens": tokens, "count": len(tokens), "metric": metric}
    except Exception as e:
        logger.error(f"get_top_tokens_db_tool error: {e}")
        return {"success": False, "error": str(e), "tokens": []}


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
                "vector_store": astra_store.get_stats(model_provider=_current_model_provider) if hasattr(astra_store, 'get_stats') else {},
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
# BACKTESTING TOOLS
# ============================================================================

@tool
def fetch_token_ohlcv_tool(token_address: str, days_back: int = 30) -> str:
    """
    Fetch historical OHLCV price candles for a Solana token (5-minute intervals).
    Results are cached in the database. Use before running backtests.

    Args:
        token_address: Solana token mint address
        days_back: How many days of history to fetch (default 30, max 90)
    """
    try:
        from src.data.historical_data import fetch_ohlcv, get_ohlcv_summary
        days_back = min(max(int(days_back), 1), 90)
        candles = fetch_ohlcv(token_address, days_back=days_back, interval_minutes=5)
        summary = get_ohlcv_summary(candles)
        result = {
            "success": True,
            "token_address": token_address,
            "days_back": days_back,
            **summary,
        }
        out = str(result)
        return out[:4000] + "\n...[truncated]" if len(out) > 4000 else out
    except Exception as e:
        logger.error(f"fetch_token_ohlcv_tool error: {e}")
        return str({"success": False, "error": str(e)})


@tool
def run_strategy_backtest_tool(
    token_address: str,
    strategy_name: str,
    days_back: int = 30,
) -> str:
    """
    Run a single named strategy backtest against historical OHLCV data for a token.
    Saves result to PostgreSQL and stores trade log in AstraDB for future learning.

    Available strategies: momentum, safety_first, quick_flip, reversal, breakout, hybrid

    Args:
        token_address: Solana token mint address
        strategy_name: One of: momentum, safety_first, quick_flip, reversal, breakout, hybrid
        days_back: Days of history to use (default 30)
    """
    try:
        import uuid as _uuid
        from src.data.historical_data import fetch_ohlcv
        from src.backtesting.engine import run_backtest
        from src.backtesting.strategies import get_strategy
        from src.db.backtest_store import save_backtest_result

        candles = fetch_ohlcv(token_address, days_back=days_back, interval_minutes=5)
        if not candles:
            return str({"success": False, "error": "No OHLCV data available for this token"})

        strategy_fn = get_strategy(strategy_name)
        result = run_backtest(token_address, strategy_fn, candles)

        run_id = str(_uuid.uuid4())[:12]
        save_backtest_result(result, run_id=run_id, model_provider=_current_model_provider)

        # Store each trade in AstraDB for learning
        if result.trade_log:
            try:
                for trade in result.trade_log:
                    trade["model_provider"] = _current_model_provider
                    trade["ai_reasoning"] = f"Backtest {strategy_name}: {result.total_return_pct:.1f}% total return"
                    add_trading_experience(token_address, trade)
            except Exception as mem_err:
                logger.debug(f"AstraDB trade log save failed: {mem_err}")

        # Gap 6: Share profitable backtest insights with the other model's collection
        if result.num_trades > 0 and result.total_return_pct > 0 and result.win_rate > 0.5:
            try:
                from src.memory.astra_vector_store import share_insight_across_models
                share_insight_across_models(
                    insight={
                        "strategy": strategy_name,
                        "success_rate": result.win_rate * 100,
                        "pattern_description": (
                            f"{strategy_name} strategy on {token_address[:8]}...: "
                            f"{result.total_return_pct:.1f}% return, "
                            f"{result.win_rate:.0%} win rate over {days_back}d"
                        ),
                        "market_conditions": f"{len(candles)} candles, {days_back}d backtest window",
                        "confidence_score": min(result.sharpe_ratio / 2.0, 1.0),
                        "token_characteristics": {
                            "token_address": token_address,
                            "total_return_pct": result.total_return_pct,
                            "num_trades": result.num_trades,
                            "avg_hold_minutes": result.avg_hold_minutes,
                            "sharpe_ratio": result.sharpe_ratio,
                        },
                        "risk_factors": [f"max_drawdown: {result.max_drawdown_pct:.1f}%"],
                        "success_factors": [
                            f"sharpe: {result.sharpe_ratio:.2f}",
                            f"win_rate: {result.win_rate:.0%}",
                            f"best_trade: {result.best_trade_pct:.1f}%",
                        ],
                        "recommendations": (
                            f"Consider {strategy_name} strategy on tokens with similar profiles"
                        ),
                        "detailed_analysis": (
                            f"Run {run_id}: {result.num_trades} trades, "
                            f"best {result.best_trade_pct:.1f}%, worst {result.worst_trade_pct:.1f}%, "
                            f"avg hold {result.avg_hold_minutes:.0f}min"
                        ),
                        "pattern_type": "backtest_success",
                    },
                    source_model=_current_model_provider,
                )
                logger.debug(
                    f"Backtest insight shared across models: {strategy_name} "
                    f"{result.total_return_pct:.1f}% on {token_address[:8]}..."
                )
            except Exception as share_err:
                logger.debug(f"share_insight_across_models skipped: {share_err}")

        summary = {
            "success": True,
            "strategy": result.strategy_name,
            "token_address": token_address,
            "candles_used": len(candles),
            "num_trades": result.num_trades,
            "win_rate_pct": round(result.win_rate * 100, 1),
            "total_return_pct": result.total_return_pct,
            "max_drawdown_pct": result.max_drawdown_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "avg_hold_minutes": result.avg_hold_minutes,
            "best_trade_pct": result.best_trade_pct,
            "worst_trade_pct": result.worst_trade_pct,
            "run_id": run_id,
        }
        out = str(summary)
        return out[:4000] + "\n...[truncated]" if len(out) > 4000 else out
    except Exception as e:
        logger.error(f"run_strategy_backtest_tool error: {e}")
        return str({"success": False, "error": str(e)})


@tool
def compare_strategies_backtest_tool(
    token_address: str,
    days_back: int = 30,
) -> str:
    """
    Run all 6 strategies in parallel against a token's historical data.
    Returns a ranked table to help decide which strategy performs best.
    Saves all results to PostgreSQL and AstraDB.

    Strategies compared: momentum, safety_first, quick_flip, reversal, breakout, hybrid

    Args:
        token_address: Solana token mint address
        days_back: Days of history to use (default 30)
    """
    try:
        import uuid as _uuid
        from src.backtesting.engine import run_parallel_backtests
        from src.backtesting.strategies import list_strategies
        from src.db.backtest_store import save_backtest_result

        run_id = str(_uuid.uuid4())[:12]
        results = run_parallel_backtests([token_address], list_strategies(), days_back=days_back)

        rankings = []
        for r in sorted(results, key=lambda x: x.total_return_pct, reverse=True):
            save_backtest_result(r, run_id=run_id, model_provider=_current_model_provider)
            rankings.append({
                "strategy": r.strategy_name,
                "total_return_pct": r.total_return_pct,
                "win_rate_pct": round(r.win_rate * 100, 1),
                "num_trades": r.num_trades,
                "sharpe": r.sharpe_ratio,
                "max_dd_pct": r.max_drawdown_pct,
                "avg_hold_min": r.avg_hold_minutes,
                "error": r.error or None,
            })

        summary = {
            "success": True,
            "token_address": token_address,
            "days_back": days_back,
            "run_id": run_id,
            "best_strategy": rankings[0]["strategy"] if rankings else "none",
            "strategy_rankings": rankings,
        }
        out = str(summary)
        return out[:4000] + "\n...[truncated]" if len(out) > 4000 else out
    except Exception as e:
        logger.error(f"compare_strategies_backtest_tool error: {e}")
        return str({"success": False, "error": str(e)})


@tool
def get_best_strategy_tool(token_address: str = "") -> str:
    """
    Query the backtest results database to find the best-performing strategies.
    If token_address given, returns strategy rankings for that specific token.
    Otherwise returns the global leaderboard of top strategy+token combos.

    Args:
        token_address: Optional Solana token mint address (leave blank for global leaderboard)
    """
    try:
        from src.db.backtest_store import get_best_strategy_for_token, get_backtest_leaderboard

        if token_address.strip():
            data = get_best_strategy_for_token(token_address.strip(), _current_model_provider)
            result = {
                "success": True,
                "token_address": token_address,
                "strategy_rankings": data,
                "recommendation": data[0]["strategy_name"] if data else "no data — run compare_strategies_backtest_tool first",
            }
        else:
            leaderboard = get_backtest_leaderboard(limit=15)
            result = {
                "success": True,
                "global_leaderboard": leaderboard,
                "tip": "Use compare_strategies_backtest_tool on a specific token to populate this leaderboard",
            }

        out = str(result)
        return out[:4000] + "\n...[truncated]" if len(out) > 4000 else out
    except Exception as e:
        logger.error(f"get_best_strategy_tool error: {e}")
        return str({"success": False, "error": str(e)})


@tool
def run_deep_backtest_tool(
    token_address: str,
    days_back: int = 30,
) -> str:
    """
    Run all 24 strategy variants across three timeframes (5m, 15m, 60m) against
    a token's full historical data. Returns top performers grouped by timeframe
    and market regime. Use this before entering a position on a new token to get
    maximum compressed context — 72 simulations instead of 6.

    Args:
        token_address: Solana token mint address
        days_back: Historical window in days (default 30; new tokens may have less)
    """
    try:
        import uuid as _uuid
        from src.backtesting.engine import run_multi_timeframe_backtests
        from src.backtesting.strategies import list_strategies
        from src.db.backtest_store import save_backtest_result

        run_id = str(_uuid.uuid4())[:12]
        strategies = list_strategies()
        timeframes = [5, 15, 60]

        results = run_multi_timeframe_backtests(
            [token_address], strategies, timeframes, days_back=days_back, max_workers=6
        )

        # Persist all results and build summary
        by_timeframe: dict[int, list[dict]] = {tf: [] for tf in timeframes}
        by_regime: dict[str, list[dict]] = {}

        for r in results:
            save_backtest_result(r, run_id=run_id, model_provider=_current_model_provider)

            if r.num_trades > 0:
                row = {
                    "strategy": r.strategy_name,
                    "return_pct": r.total_return_pct,
                    "win_rate_pct": round(r.win_rate * 100, 1),
                    "sharpe": r.sharpe_ratio,
                    "trades": r.num_trades,
                    "regime": r.market_regime,
                }
                by_timeframe[r.interval_minutes].append(row)
                by_regime.setdefault(r.market_regime, []).append(row)

                # Vectorize to AstraDB with regime metadata
                try:
                    add_trading_experience(token_address, {
                        "model_provider": _current_model_provider,
                        "trade_type": "deep_backtest",
                        "strategy_name": r.strategy_name,
                        "token_symbol": r.token_symbol,
                        "total_return_pct": r.total_return_pct,
                        "win_rate": r.win_rate,
                        "num_trades": r.num_trades,
                        "sharpe_ratio": r.sharpe_ratio,
                        "max_drawdown_pct": r.max_drawdown_pct,
                        "avg_hold_minutes": r.avg_hold_minutes,
                        "market_regime": r.market_regime,
                        "interval_minutes": r.interval_minutes,
                        "days_back": days_back,
                        "run_id": run_id,
                        "ai_reasoning": (
                            f"Deep backtest {r.strategy_name} [{r.interval_minutes}m, "
                            f"{r.market_regime}]: {r.total_return_pct:.1f}% return, "
                            f"{r.win_rate:.0%} win rate over {days_back}d"
                        ),
                        "timestamp": datetime.now().isoformat(),
                    })
                except Exception:
                    pass

        # Sort each timeframe bucket by return
        for tf in timeframes:
            by_timeframe[tf].sort(key=lambda x: x["return_pct"], reverse=True)
        for reg in by_regime:
            by_regime[reg].sort(key=lambda x: x["return_pct"], reverse=True)

        # Top 3 per timeframe
        top_by_tf = {
            f"{tf}m": by_timeframe[tf][:3] for tf in timeframes
        }

        # Detected regime (use most common across results)
        detected_regime = max(by_regime, key=lambda r: len(by_regime[r])) if by_regime else "unknown"
        best_for_regime = by_regime.get(detected_regime, [])[:3]

        summary = {
            "success": True,
            "token_address": token_address,
            "days_back": days_back,
            "run_id": run_id,
            "total_simulations": len(results),
            "detected_regime": detected_regime,
            "top_strategies_by_timeframe": top_by_tf,
            "top_strategies_for_current_regime": best_for_regime,
            "recommendation": (
                best_for_regime[0]["strategy"] if best_for_regime
                else (by_timeframe[5][:1][0]["strategy"] if by_timeframe[5] else "no data")
            ),
        }
        out = str(summary)
        return out[:4000] + "\n...[truncated]" if len(out) > 4000 else out
    except Exception as e:
        logger.error(f"run_deep_backtest_tool error: {e}")
        return str({"success": False, "error": str(e)})


@tool
def get_strategy_by_regime_tool(regime: str = "") -> str:
    """
    Query historical backtest database for strategy performance grouped by market regime.
    Returns which strategies perform best in bull / bear / sideways / volatile markets.
    Use this to pick the right strategy for the current market conditions.

    Args:
        regime: "bull" | "bear" | "sideways" | "volatile" | "" (all regimes)
    """
    try:
        from src.db.backtest_store import get_strategy_performance_by_regime
        regime_clean = regime.strip().lower()
        data = get_strategy_performance_by_regime(regime=regime_clean, limit=20)
        result = {
            "success": True,
            "regime_filter": regime_clean or "all",
            "strategy_rankings": data,
            "tip": (
                "Use run_deep_backtest_tool to populate this database for a specific token. "
                "The regime column tells you under what market conditions each strategy thrives."
            ),
        }
        out = str(result)
        return out[:4000] + "\n...[truncated]" if len(out) > 4000 else out
    except Exception as e:
        logger.error(f"get_strategy_by_regime_tool error: {e}")
        return str({"success": False, "error": str(e)})


# ============================================================================
# Custom LangGraph Node Functions (Standalone)
# ============================================================================

def _call_model(state: TradingAgentState, model_with_tools):
    """Node function to call the LLM."""
    messages = state['messages']
    # Always keep the SystemMessage (first message) — only truncate non-system history
    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    other_msgs = [m for m in messages if not isinstance(m, SystemMessage)][-12:]
    response = model_with_tools.invoke(system_msgs + other_msgs)
    return {"messages": [response]}

def _call_tool(state: TradingAgentState, tools):
    """Node function to execute tools."""
    last_message = state['messages'][-1]
    tool_calls = last_message.tool_calls
    
    tool_messages = []
    tool_map = {tool.name: tool for tool in tools}
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_to_call = tool_map[tool_name]
        try:
            tool_output = tool_to_call.invoke(tool_call["args"])
            output_str = str(tool_output)
            # Cap tool output to prevent context window overflow
            if len(output_str) > 4000:
                output_str = output_str[:4000] + "\n...[truncated]"
            tool_messages.append(
                ToolMessage(content=output_str, tool_call_id=tool_call["id"])
            )
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            tool_messages.append(
                ToolMessage(content=f"Error: {e}", tool_call_id=tool_call["id"])
            )
    # Also pass along the original agent_state
    return {"messages": tool_messages, "agent_state": state['agent_state']}

def _should_continue(state: TradingAgentState):
    """Conditional edge to decide whether to continue or end."""
    last_message = state['messages'][-1]
    if not last_message.tool_calls:
        return "end"
    return "continue"

# ============================================================================
# Custom LangGraph Implementation
# ============================================================================

class CompleteLangGraphTradingAgent:
    """A custom LangGraph agent for robust, multi-turn trading cycles."""

    def __init__(self, model_provider: str = "gemini"):
        global _current_model_provider
        self.model_provider = model_provider
        _current_model_provider = model_provider
        # Set the global model provider context for the memory store
        from src.memory.astra_vector_store import set_current_model_provider
        set_current_model_provider(model_provider)
        
        self.tools = self._get_all_tools()
        self.model = self._initialize_model(model_provider)
        self.model_with_tools = self.model.bind_tools(self.tools)
        self.graph = self._build_graph()

    def _initialize_model(self, model_provider: str):
        if model_provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found for Claude model")
            return ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0.1, api_key=api_key)
        elif model_provider == "gemini":
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY not found for Gemini model")
            return ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.1, google_api_key=api_key)
        else:
            raise ValueError(f"Unsupported model provider: {model_provider}")

    def _get_all_tools(self):
        return [
            get_wallet_balance_tool, get_portfolio_summary_tool, discover_tokens_tool,
            filter_tokens_tool, sort_tokens_tool, get_comprehensive_token_data_tool,
            get_safety_data_tool, get_social_data_tool,
            get_nansen_smart_money_tool, screen_nansen_opportunities_tool,
            search_trading_history_tool,
            find_similar_tokens_tool, get_trading_patterns_tool, get_swap_quote_tool,
            execute_trade_tool, save_trading_experience_tool, check_system_status_tool,
            get_market_overview_tool,
            # DB analytics tools
            query_trade_history_db_tool, get_performance_analytics_db_tool,
            compare_model_performance_db_tool, get_session_history_db_tool,
            search_system_logs_db_tool, get_top_tokens_db_tool,
            # Backtesting tools
            fetch_token_ohlcv_tool, run_strategy_backtest_tool,
            compare_strategies_backtest_tool, get_best_strategy_tool,
            run_deep_backtest_tool, get_strategy_by_regime_tool,
        ]

    def _build_graph(self):
        workflow = StateGraph(TradingAgentState)
        
        # Use lambdas to pass self-managed dependencies to the standalone node functions
        workflow.add_node("agent", lambda s: _call_model(s, self.model_with_tools))
        workflow.add_node("action", lambda s: _call_tool(s, self.tools))
        
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            _should_continue,
            {"continue": "action", "end": END},
        )
        workflow.add_edge("action", "agent")
        if _SQLITE_AVAILABLE:
            _checkpoint_db = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "langgraph_checkpoints.db"
            )
            conn = sqlite3.connect(_checkpoint_db, check_same_thread=False)
            checkpointer = _SqliteSaver(conn)
            logger.info(f"Using SqliteSaver checkpointer at {_checkpoint_db}")
        else:
            checkpointer = MemorySaver()
            logger.info("SqliteSaver not available — falling back to MemorySaver")
        return workflow.compile(checkpointer=checkpointer)

    def run_trading_cycle(
        self,
        initial_state: AgentState = None,
        session_id: str = None,
        cycle_id: int = None,
    ) -> AgentState:
        if initial_state is None:
            state = load_agent_state() or create_initial_state()
        else:
            state = initial_state

        state = update_portfolio_metrics(state)

        # Set current trading mode for tools
        global _current_trading_mode
        trading_mode = state.get("trading_mode", "dry_run")
        _current_trading_mode = trading_mode

        context_message = self._create_context_message(state)
        cycles = state.get("cycles_completed", 0)
        config = {
            "configurable": {"thread_id": f"trading_{self.model_provider}_{trading_mode}"},
            # LangSmith metadata — auto-captured when LANGCHAIN_TRACING_V2=true
            "metadata": {
                "model_provider": self.model_provider,
                "trading_mode": trading_mode,
                "cycle_number": cycles + 1,
                "wallet_balance_sol": state.get("wallet_balance_sol", 0),
                "active_positions": len(state.get("active_positions", [])),
            },
            "tags": ["trading_cycle", self.model_provider, trading_mode],
        }

        # Pass model_provider in the agent_state so tools can access it
        state["model_provider"] = self.model_provider

        # The initial state for the graph must match the TradingAgentState TypedDict
        # SystemMessage carries the full operating manual (persists across message truncation).
        # HumanMessage carries the per-cycle portfolio snapshot.
        graph_initial_state = {
            "messages": [
                SystemMessage(content=self._build_system_prompt(state)),
                HumanMessage(content=context_message),
            ],
            "agent_state": state,
        }

        # Wrap graph.invoke() with collect_runs to capture the LangSmith run ID
        _langsmith_run_id = None
        if os.getenv("LANGCHAIN_API_KEY"):
            try:
                from langchain_core.tracers.context import collect_runs
                with collect_runs() as cb:
                    final_state_graph = self.graph.invoke(
                        graph_initial_state,
                        config=config
                    )
                if cb.traced_runs:
                    _langsmith_run_id = str(cb.traced_runs[0].id)
                    logger.debug(f"LangSmith run ID captured: {_langsmith_run_id}")
            except Exception as _ls_err:
                logger.debug(f"collect_runs unavailable, falling back: {_ls_err}")
                final_state_graph = self.graph.invoke(
                    graph_initial_state,
                    config=config
                )
        else:
            final_state_graph = self.graph.invoke(
                graph_initial_state,
                config=config
            )

        # Extract and save the final state from the graph's state
        final_agent_state = final_state_graph['agent_state']
        final_ai_message = final_state_graph['messages'][-1]

        final_agent_state["agent_reasoning"] = final_ai_message.content
        final_agent_state["cycles_completed"] = final_agent_state.get("cycles_completed", 0) + 1
        final_agent_state["last_update_timestamp"] = datetime.now().isoformat()

        # Extract tool calls from the entire exchange
        all_messages = final_state_graph['messages']
        tools_used = [
            tool_call['name']
            for msg in all_messages
            if isinstance(msg, AIMessage) and msg.tool_calls
            for tool_call in msg.tool_calls
        ]
        final_agent_state["tools_used_this_cycle"] = tools_used

        # Store the LangSmith run ID for this cycle so _persist_cycle_trades can attach it
        if _langsmith_run_id:
            final_agent_state["last_cycle_langsmith_run_id"] = _langsmith_run_id

        # Persist every execute_trade_tool result to PostgreSQL + AstraDB
        self._persist_cycle_trades(
            all_messages, final_agent_state, session_id, cycle_id
        )

        save_agent_state(final_agent_state)
        return final_agent_state

    def _persist_cycle_trades(
        self,
        all_messages: list,
        final_state: AgentState,
        session_id: str = None,
        cycle_id: int = None,
    ) -> None:
        """
        Scan LangGraph messages for execute_trade_tool calls and their results.
        For each trade found:
          - Append to state["transaction_history"]
          - Record to PostgreSQL (record_trade)
          - Vectorize into AstraDB (add_trading_experience) for agent learning
        """
        import ast

        # Build a map of tool_call_id → result content for fast lookup
        tool_results: dict[str, str] = {}
        for msg in all_messages:
            if isinstance(msg, ToolMessage):
                tool_results[msg.tool_call_id] = msg.content

        # Walk AIMessages to find execute_trade_tool invocations
        for msg in all_messages:
            if not (isinstance(msg, AIMessage) and msg.tool_calls):
                continue
            for tc in msg.tool_calls:
                if tc["name"] != "execute_trade_tool":
                    continue

                raw_result = tool_results.get(tc["id"], "")
                if not raw_result:
                    continue

                # Parse stringified dict (ToolMessage content is str(dict))
                try:
                    trade_result = ast.literal_eval(raw_result)
                except Exception:
                    try:
                        trade_result = json.loads(raw_result)
                    except Exception:
                        logger.warning(f"Could not parse trade result: {raw_result[:200]}")
                        continue

                if not isinstance(trade_result, dict):
                    continue

                # Enrich with context not available inside the tool
                trade_result["model_provider"] = self.model_provider
                trade_result["trading_mode"] = final_state.get("trading_mode", "dry_run")
                trade_result["cycle_number"] = final_state.get("cycles_completed", 0)
                trade_result["wallet_balance_sol"] = final_state.get("wallet_balance_sol", 0)

                # ── 1. transaction_history ──────────────────────────────────
                history = final_state.setdefault("transaction_history", [])
                history.append(trade_result)
                # Keep last 200 entries
                if len(history) > 200:
                    final_state["transaction_history"] = history[-200:]

                # ── 1b. Dry-run balance simulation ──────────────────────────
                # Update wallet_balance_sol so the agent sees the effect of
                # its own dry-run decisions within a single cycle.
                if trade_result.get("dry_run") and trade_result.get("success"):
                    amount = trade_result.get("amount_sol", 0)
                    trade_type = trade_result.get("trade_type", "").lower()
                    current_bal = final_state.get("wallet_balance_sol", 0)
                    if trade_type == "buy":
                        final_state["wallet_balance_sol"] = max(0.0, current_bal - amount)
                    elif trade_type == "sell":
                        final_state["wallet_balance_sol"] = current_bal + amount
                    logger.debug(
                        f"Dry-run balance updated: {current_bal:.4f} → "
                        f"{final_state['wallet_balance_sol']:.4f} SOL "
                        f"({trade_type} {amount:.4f} SOL)"
                    )

                # ── 2. PostgreSQL ────────────────────────────────────────────
                if session_id:
                    try:
                        from src.db.trade_store import record_trade
                        trade_id = record_trade(session_id, cycle_id, trade_result)
                        if trade_id:
                            logger.info(
                                f"Trade recorded to PostgreSQL: id={trade_id} "
                                f"type={trade_result.get('trade_type')} "
                                f"token={str(trade_result.get('token_address',''))[:8]}... "
                                f"dry_run={trade_result.get('dry_run')}"
                            )
                    except Exception as e:
                        logger.warning(f"record_trade skipped: {e}")

                # ── 3. AstraDB vectorization ────────────────────────────────
                token_address = trade_result.get("token_address", "")
                if token_address:
                    try:
                        experience = {
                            "model_provider": self.model_provider,
                            "trade_type": trade_result.get("trade_type", "unknown"),
                            "token_symbol": trade_result.get("token_symbol", "unknown"),
                            "amount_sol": trade_result.get("amount_sol", 0),
                            "dry_run": trade_result.get("dry_run", True),
                            "transaction_ready": trade_result.get("transaction_ready"),
                            "success": trade_result.get("success", False),
                            "ai_reasoning": trade_result.get("reasoning", ""),
                            "market_conditions": final_state.get("market_conditions", {}),
                            "wallet_balance_sol": final_state.get("wallet_balance_sol", 0),
                            "profit_percentage": 0,  # updated when position closes
                            "safety_score": 0,
                            "timestamp": trade_result.get("timestamp", datetime.now().isoformat()),
                            "cycle_number": trade_result.get("cycle_number", 0),
                            "trading_mode": trade_result.get("trading_mode", "dry_run"),
                        }
                        add_trading_experience(token_address, experience)
                        logger.info(
                            f"Trade vectorized to AstraDB: "
                            f"{trade_result.get('trade_type')} {token_address[:8]}... "
                            f"(dry_run={trade_result.get('dry_run')})"
                        )
                    except Exception as e:
                        logger.warning(f"add_trading_experience skipped: {e}")

                # ── 3b. LangSmith: tag active position with this cycle's run ID ──
                # On a successful BUY, store the run ID on the position so we can
                # attach outcome feedback when the position is later sold.
                if (
                    trade_result.get("trade_type", "").lower() == "buy"
                    and trade_result.get("success")
                    and token_address
                    and os.getenv("LANGCHAIN_API_KEY")
                ):
                    try:
                        run_id_for_pos = final_state.get("last_cycle_langsmith_run_id")
                        if run_id_for_pos:
                            active_positions = final_state.get("active_positions", [])
                            for pos in active_positions:
                                if pos.get("token_address") == token_address:
                                    pos["langsmith_run_id"] = run_id_for_pos
                                    logger.debug(
                                        f"Attached LangSmith run ID {run_id_for_pos} "
                                        f"to position {token_address[:8]}..."
                                    )
                                    break
                    except Exception as _ls_buy_err:
                        logger.debug(f"LangSmith BUY tag skipped: {_ls_buy_err}")

                # ── 4. Gaps 2 & 5: Outcome calibration on sell ──────────────
                # When the agent closes a position (sell), record the actual
                # P&L and compare it against any prior backtest prediction for
                # this token. This calibration is stored in AstraDB so agents
                # can learn how accurate their backtest predictions really are.
                if (
                    trade_result.get("trade_type", "").lower() == "sell"
                    and trade_result.get("success")
                    and token_address
                ):
                    try:
                        # Find the matching open position for P&L calculation
                        active_positions = final_state.get("active_positions", [])
                        matching_pos = next(
                            (p for p in active_positions
                             if p.get("token_address") == token_address),
                            None,
                        )
                        entry_price = matching_pos.get("entry_price_usd", 0) if matching_pos else 0
                        current_price = matching_pos.get("current_price_usd", 0) if matching_pos else 0
                        actual_profit_pct = (
                            ((current_price - entry_price) / entry_price * 100)
                            if entry_price else 0
                        )

                        # ── LangSmith outcome feedback ───────────────────────
                        if os.getenv("LANGCHAIN_API_KEY") and matching_pos:
                            try:
                                _ls_run_id = matching_pos.get("langsmith_run_id")
                                if _ls_run_id:
                                    from langsmith import Client as LangSmithClient
                                    ls_client = LangSmithClient()
                                    ls_client.create_feedback(
                                        run_id=_ls_run_id,
                                        key="trade_outcome",
                                        score=actual_profit_pct / 100,
                                        value=f"{'profit' if actual_profit_pct > 0 else 'loss'}: {actual_profit_pct:.1f}%",
                                        comment=(
                                            f"Position held {matching_pos.get('hold_time_hours', 0):.1f}h. "
                                            f"Entry {matching_pos.get('entry_price_usd', 0):.6f} → "
                                            f"Exit {matching_pos.get('current_price_usd', 0):.6f} USD"
                                        ),
                                    )
                                    logger.info(
                                        f"LangSmith feedback submitted: run={_ls_run_id[:8]}... "
                                        f"score={actual_profit_pct / 100:.3f} "
                                        f"({'profit' if actual_profit_pct > 0 else 'loss'})"
                                    )
                            except Exception as _ls_fb_err:
                                logger.debug(f"LangSmith feedback skipped: {_ls_fb_err}")

                        # Look up backtest predictions for this token
                        from src.db.backtest_store import get_best_strategy_for_token
                        backtest_strategies = get_best_strategy_for_token(
                            token_address, self.model_provider
                        )
                        best_bt = backtest_strategies[0] if backtest_strategies else None
                        bt_predicted = best_bt["avg_return_pct"] if best_bt else None
                        prediction_error = (
                            actual_profit_pct - bt_predicted
                            if bt_predicted is not None else None
                        )

                        calibration = {
                            "model_provider": self.model_provider,
                            "trade_type": "outcome_calibration",
                            "token_symbol": (
                                matching_pos.get("token_symbol", "")
                                if matching_pos else ""
                            ),
                            "actual_profit_pct": actual_profit_pct,
                            "hold_time_hours": (
                                matching_pos.get("hold_time_hours", 0)
                                if matching_pos else 0
                            ),
                            "best_backtest_strategy": (
                                best_bt.get("strategy_name") if best_bt else None
                            ),
                            "backtest_predicted_return_pct": bt_predicted,
                            "prediction_error_pct": prediction_error,
                            "was_profitable": actual_profit_pct > 0,
                            "ai_reasoning": (
                                f"Position closed: {actual_profit_pct:.1f}% actual"
                                + (f" vs {bt_predicted:.1f}% backtest predicted"
                                   if bt_predicted is not None else " (no backtest baseline)")
                            ),
                            "market_conditions": final_state.get("market_conditions", {}),
                            "timestamp": trade_result.get("timestamp", datetime.now().isoformat()),
                            "dry_run": trade_result.get("dry_run", True),
                        }
                        add_trading_experience(token_address, calibration)
                        logger.info(
                            f"Outcome calibration vectorized: {actual_profit_pct:.1f}% actual"
                            + (f" vs {bt_predicted:.1f}% predicted (error {prediction_error:+.1f}%)"
                               if prediction_error is not None else "")
                        )
                    except Exception as cal_err:
                        logger.debug(f"Outcome calibration skipped: {cal_err}")

    def _create_context_message(self, state: AgentState) -> str:
        """Creates the per-cycle HumanMessage briefing (portfolio snapshot for this cycle)."""
        wallet_balance = state.get("wallet_balance_sol", 0)
        cycles_completed = state.get("cycles_completed", 0)
        active_positions = state.get("active_positions", [])
        trading_mode = state.get("trading_mode", "dry_run")
        total_position_value = sum(pos.get("current_value_sol", 0) for pos in active_positions)
        total_portfolio_value = wallet_balance + total_position_value

        pos_lines = []
        for pos in active_positions[:5]:
            sym = pos.get("token_symbol", "?")
            val = pos.get("current_value_sol", 0)
            pnl = pos.get("current_profit_percentage", 0)
            held_h = pos.get("hold_time_hours", 0)
            pos_lines.append(f"  • {sym}: {val:.4f} SOL | PnL {pnl:+.1f}% | held {held_h:.1f}h")
        positions_str = "\n".join(pos_lines) if pos_lines else "  (none)"

        return f"""═══ CYCLE {cycles_completed + 1} BRIEFING ═══
Wallet:    {wallet_balance:.4f} SOL  (free cash)
Positions: {len(active_positions)} open  |  position value: {total_position_value:.4f} SOL
Portfolio: {total_portfolio_value:.4f} SOL  total
Mode:      {trading_mode.upper()}

Open positions:
{positions_str}

Execute the full Decision Loop from your system instructions.
Start with: get_portfolio_summary_tool → manage exits → discover → analyze → backtest → trade → save learnings."""

    def _build_system_prompt(self, state: dict) -> str:
        """
        Comprehensive system prompt injected at the start of every trading cycle.
        Contains the agent's full operating manual: decision loop, scoring, all 24 strategies,
        tool reference, risk rules, position sizing, memory guidance, and human-approval gate.
        """
        model_name = "Claude (Haiku)" if self.model_provider == "claude" else "Gemini"
        wallet = state.get("wallet_balance_sol", 0)
        max_pos_env = float(os.getenv("MAX_POSITION_SIZE_SOL", "1.0"))
        max_pos = min(wallet * 0.25, max_pos_env)
        approval_threshold = float(os.getenv("HUMAN_APPROVAL_THRESHOLD_SOL", "5.0"))
        approval_timeout = int(os.getenv("HUMAN_APPROVAL_TIMEOUT_MINUTES", "60"))

        return f"""You are {model_name}, an elite autonomous Solana memecoin trading agent running 24/7/365.

MISSION: Compound SOL continuously through high-conviction memecoin trades.
Discover → Analyse → Backtest → Score → Execute → Learn → Repeat.
You operate without human intervention except for trades ≥ {approval_threshold} SOL.

═══════════════════════════════════════════════════════════
DECISION LOOP  (execute in this order every cycle)
═══════════════════════════════════════════════════════════

1. PORTFOLIO CHECK
   → get_wallet_balance_tool
   → get_portfolio_summary_tool
   → get_market_overview_tool

2. MANAGE OPEN POSITIONS
   For each open position apply exit rules (see RISK MANAGEMENT below).
   Close via execute_trade_tool(trade_type="sell", ...).
   After every sell → save_trading_experience_tool with actual outcome.

3. DISCOVER CANDIDATES
   → discover_tokens_tool(strategy="boosted_latest", limit=20)
   → filter_tokens_tool (min_liquidity_usd=5000, min_volume_24h_usd=10000)
   → sort_tokens_tool by volume or price change
   Also check: screen_nansen_opportunities_tool for smart-money confirmed tokens.

4. DEEP ANALYSE SHORTLIST (top 3-5 candidates)
   For each candidate run ALL of:
   a. get_comprehensive_token_data_tool
   b. get_safety_data_tool          ← reject immediately if risk = HIGH or score < 700
   c. get_social_data_tool          ← DexScreener social signals
   d. get_nansen_smart_money_tool   ← smart money wallet activity
   e. search_trading_history_tool   ← AstraDB: similar past tokens & outcomes
   f. get_strategy_by_regime_tool   ← which strategies work in CURRENT market regime?
   g. run_deep_backtest_tool        ← 72 simulations (24 strats × 3 timeframes)
      OR get_best_strategy_tool     ← if daemon already ran backtests for this token

5. SCORE EACH CANDIDATE (100-point system — see below)

6. EXECUTE high-conviction trades (score ≥ 60)
   → get_swap_quote_tool first, then execute_trade_tool
   → save_trading_experience_tool immediately after entry

7. SAVE LEARNINGS
   → save_trading_experience_tool with reasoning, score, strategy used, regime

═══════════════════════════════════════════════════════════
5-SIGNAL SCORING SYSTEM (100 points total)
═══════════════════════════════════════════════════════════

1. VIRAL NARRATIVE POWER    (30 pts)
   Meme quality, cultural fit, emotional resonance, viral potential.
   Great narrative = token can spread itself. Mediocre story = pass.

2. SOCIAL MOMENTUM          (25 pts)
   DexScreener: website + Twitter + Telegram links present (+5 each)
   Nansen smart money: wallets actively buying (+10), holding (+5)
   Community activity: votes, takeovers, promoted status

3. VOLUME VELOCITY          (25 pts)
   Volume spikes in last 5m/1h vs 24h baseline
   Buy pressure > sell pressure (buyers_5m > sellers_5m)
   Holder count growing, not flat or declining

4. SAFETY FLOOR             (10 pts)
   RugCheck score ≥ 800 (+5), ≥ 900 (+10)
   LP locked or burned (+3), no mint authority (+3), top holder < 20% (+4)
   Reject outright: rug risk HIGH, score < 700

5. MARKETING FIREPOWER      (10 pts)
   DexScreener boosts active, trending rank < 50
   Community votes, promoted status, recent social boost

THRESHOLDS:
  ≥ 90 pts → ULTRA-HIGH conviction  |  25% of wallet
  75-89    → HIGH conviction         |  20% of wallet
  60-74    → MODERATE conviction     |  15% of wallet
  50-59    → LOW conviction          |  10% of wallet (risky, prefer to skip)
  < 50     → REJECT

═══════════════════════════════════════════════════════════
POSITION SIZING  (current wallet: {wallet:.4f} SOL)
═══════════════════════════════════════════════════════════

  ULTRA-HIGH (25%):  {wallet * 0.25:.4f} SOL  (hard cap: {max_pos:.4f} SOL)
  HIGH       (20%):  {wallet * 0.20:.4f} SOL
  MODERATE   (15%):  {wallet * 0.15:.4f} SOL
  LOW        (10%):  {wallet * 0.10:.4f} SOL

  MAX single position: {max_pos:.4f} SOL  (env cap: {max_pos_env} SOL)
  MIN position: 0.01 SOL
  MAX concurrent positions: 5
  Trades ≥ {approval_threshold} SOL: paused for human approval ({approval_timeout}min timeout → auto-proceeds at {approval_threshold - 0.1:.1f} SOL)

═══════════════════════════════════════════════════════════
RISK MANAGEMENT  (non-negotiable rules)
═══════════════════════════════════════════════════════════

EXIT TRIGGERS (check every cycle for each open position):
  Stop loss:    -20% from entry → SELL FULL POSITION immediately
  Time stop:    > 12 hours held → review; exit unless strong momentum
  Profit steps: +5x → sell 25%, +15x → sell 25%, +50x → sell 25%, hold 25% moon bag

DO NOT:
  • Average down on a losing position
  • Hold through -30%+ hoping for recovery
  • Take a position > 25% of wallet on any single token
  • Open position #6 while 5 are already open
  • Trade tokens with RugCheck score < 700

═══════════════════════════════════════════════════════════
STRATEGY LIBRARY  (24 strategies — choose with run_deep_backtest_tool)
═══════════════════════════════════════════════════════════

MOMENTUM FAMILY — buy rising price, ride trend:
  momentum            3-candle slope >2%,  TP +15%, SL -1%    ← baseline
  momentum_scalp      2-candle slope >1%,  TP +8%,  SL -0.5%  ← fast micro-scalp
  momentum_swing      5-candle slope >3%,  TP +25%, SL -2%    ← swing hold
  momentum_aggressive 3-candle slope >1.5%,TP +20%, SL -0.5%  ← aggressive uptrend
  momentum_conservative 4-candle >3%,      TP +10%, SL -2%    ← cautious entry

REVERSAL FAMILY — buy oversold bounces (RSI-based):
  reversal            RSI(14) <30 buy, >60 sell               ← baseline
  reversal_fast       RSI(7)  <30 buy, >60 sell               ← quick reaction
  reversal_slow       RSI(21) <28 buy, >62 sell               ← fewer false signals
  reversal_oversold   RSI(14) <25 buy, >55 sell               ← strict entry
  reversal_loose      RSI(14) <35 buy, >65 sell               ← early bounce

QUICK-FLIP FAMILY — buy dips off recent high, tight exits:
  quick_flip          2% dip from 12-candle high, TP +5%, SL -3%   ← baseline
  quick_flip_micro    1% dip from 6-candle high,  TP +3%, SL -2%   ← ultra-short
  quick_flip_deep     3% dip from 24-candle high, TP +8%, SL -5%   ← larger dips
  quick_flip_tight    1.5% dip, 12-candle high,   TP +4%, SL -2%   ← tight range

SAFETY-FIRST FAMILY — SMA + volume confirmation required:
  safety_first        SMA20 + 1.5× avg vol, TP +10%, SL -5%        ← baseline
  safety_first_tight  SMA10 + 1.2× avg vol, TP +7%,  SL -3%        ← quick confirm
  safety_first_relaxed SMA30 + 2.0× avg vol, TP +15%, SL -8%       ← wide swing

BREAKOUT FAMILY — price breaks above recent high on volume:
  breakout            24h high + 1.2× vol, SL -5%                  ← baseline
  breakout_short      6h high  + 1.1× vol, SL -4%                  ← intraday
  breakout_long       48h high + 1.5× vol, SL -7%                  ← major breakout

HYBRID FAMILY — two strategies must agree before entry:
  hybrid              momentum + safety_first agree                  ← conservative
  hybrid_aggressive   momentum_scalp + reversal_fast agree          ← fast dual-signal
  hybrid_conservative momentum_conservative + safety_first_relaxed  ← high-conviction only
  hybrid_breakout     breakout_short + momentum agree               ← breakout+trend

REGIME GUIDE:
  bull      → momentum, momentum_swing, breakout, breakout_long
  bear      → reversal, safety_first, quick_flip_deep  (or hold cash)
  sideways  → quick_flip, reversal_loose, safety_first_tight
  volatile  → momentum_scalp, quick_flip_micro, hybrid_aggressive  (tight stops critical)

Use get_strategy_by_regime_tool to see which strategies ACTUALLY performed best historically.
Use run_deep_backtest_tool before any new position — it runs 72 simulations in ~30 seconds.

═══════════════════════════════════════════════════════════
MEMORY & LEARNING  (AstraDB vector store)
═══════════════════════════════════════════════════════════

BEFORE trading any token:
  search_trading_history_tool(query="token similar to X in bull/sideways market")
  find_similar_tokens_tool — find tokens with similar profiles we traded before
  get_trading_patterns_tool — what patterns have worked for this model?

AFTER every entry:
  save_trading_experience_tool with: token data, score breakdown, strategy chosen, reasoning

AFTER every exit:
  save_trading_experience_tool with: actual return, what worked, what didn't, lessons learned

The background daemon continuously backtests the top 200 Solana tokens across all 24 strategies
× 3 timeframes × market regimes. This builds your vector memory BEFORE you encounter a token.
Always check get_best_strategy_tool first — the answer may already be in the database.

═══════════════════════════════════════════════════════════
TOOLS REFERENCE
═══════════════════════════════════════════════════════════

PORTFOLIO    get_wallet_balance_tool | get_portfolio_summary_tool | get_market_overview_tool
DISCOVERY    discover_tokens_tool | filter_tokens_tool | sort_tokens_tool
ANALYSIS     get_comprehensive_token_data_tool | get_safety_data_tool | get_social_data_tool
SMART MONEY  get_nansen_smart_money_tool | screen_nansen_opportunities_tool
MEMORY       search_trading_history_tool | find_similar_tokens_tool | get_trading_patterns_tool
BACKTEST ⭐  run_deep_backtest_tool | compare_strategies_backtest_tool | run_strategy_backtest_tool
             get_best_strategy_tool | get_strategy_by_regime_tool | fetch_token_ohlcv_tool
EXECUTION    get_swap_quote_tool | execute_trade_tool | save_trading_experience_tool
DB ANALYTICS query_trade_history_db_tool | get_performance_analytics_db_tool
             compare_model_performance_db_tool | get_top_tokens_db_tool | get_session_history_db_tool
SYSTEM       check_system_status_tool | search_system_logs_db_tool

⭐ run_deep_backtest_tool = 72 simulations (24 strategies × 3 timeframes) + regime tag + AstraDB write
   Use this before any new position. Takes ~30 seconds. Returns best strategy for this token NOW."""


# ============================================================================
# USAGE FUNCTIONS
# ============================================================================

# Global instance - managed by src/agent/__init__.py
complete_langgraph_agent = None

def get_agent_instance(model_provider: str = "gemini") -> "CompleteLangGraphTradingAgent":
    """Return (or create) the global agent instance for the given model provider."""
    global complete_langgraph_agent
    if complete_langgraph_agent is None or complete_langgraph_agent.model_provider != model_provider:
        complete_langgraph_agent = CompleteLangGraphTradingAgent(model_provider=model_provider)
    return complete_langgraph_agent


def run_langgraph_trading_cycle(state: AgentState = None, model_provider: str = "gemini") -> AgentState:
    """
    Main function to run a complete LangGraph trading cycle.
    This function is now a simple pass-through to the agent's method.
    The agent instance is managed by the background thread in __init__.py.
    """
    if complete_langgraph_agent is None:
        # This should not happen in the background thread context
        logger.warning("CompleteLangGraphTradingAgent not initialized. Initializing for a single run.")
        agent = CompleteLangGraphTradingAgent(model_provider=model_provider)
        return agent.run_trading_cycle(state)
    
    return complete_langgraph_agent.run_trading_cycle(state)

def test_langgraph_tools():
    """Test that ALL LangGraph tools work correctly for both Claude and Gemini"""
    print("🧪 Testing Complete LangGraph Tools...")

    for provider in ["claude", "gemini"]:
        print(f"\n--- TESTING WITH {provider.upper()} ---")
        # Set the necessary API key environment variable for the test
        if provider == "claude" and not os.getenv("ANTHROPIC_API_KEY"):
            print("⚠️ ANTHROPIC_API_KEY not set, skipping Claude tests.")
            continue
        if provider == "gemini" and not os.getenv("GOOGLE_API_KEY"):
            print("⚠️ GOOGLE_API_KEY not set, skipping Gemini tests.")
            continue

        test_results = {}
        try:
            # Initialize agent for the provider
            agent = CompleteLangGraphTradingAgent(model_provider=provider)

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
            result = agent.run_trading_cycle()
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
            print(f"   ❌ Agent initialization or cycle failed for {provider}: {e}")
            test_results["Complete Agent"] = False

        # Summary
        passed = sum(1 for v in test_results.values() if v)
        total = len(test_results)

        print(f"\n🎯 Test Results for {provider.upper()}: {passed}/{total} passed")
        if passed != total:
            return False

    print("\n🎉 ALL TESTS PASSED FOR ALL PROVIDERS! Complete LangGraph implementation is working correctly")
    return True

# For backwards compatibility
def run_pure_ai_trading_agent(initial_state=None):
    """Backwards compatibility function"""
    return run_langgraph_trading_cycle(initial_state)

if __name__ == "__main__":
    success = test_langgraph_tools()
    print(f"\nComplete LangGraph implementation test: {'✅ PASSED' if success else '❌ FAILED'}")
# src/agent/agent_chat.py
"""
Agent Chat Interface
Allows users to chat with trading agents to understand their decision-making,
strategies, and ask questions about trades - works regardless of agent state

Based on best practices:
- LangGraph memory management (2024-2025 standard)
- ConversationBufferWindowMemory for recent context
- Database-backed persistence for production
- Context window management (recent messages only)
- System prompt with agent state context
"""
import logging
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.chat_history import InMemoryChatMessageHistory

from .state import load_agent_state
from .langgraph_trading_agent import get_agent_instance

logger = logging.getLogger("trading_agent.chat")

# Chat history storage (in-memory for now, can be moved to DB)
_chat_histories = {}  # {model_provider: InMemoryChatMessageHistory}


class AgentChatInterface:
    """
    Chat interface for interacting with trading agents

    Features:
    - Chat with agents regardless of running state
    - Ask about decisions, strategies, trades
    - Get insights into agent reasoning
    - Works with both Claude and Gemini
    """

    def __init__(self, model_provider: str = 'anthropic', max_history: int = 10):
        """
        Initialize chat interface for a specific agent

        Args:
            model_provider: 'anthropic' or 'google'
            max_history: Maximum number of messages to keep in context (default: 10)
        """
        self.model_provider = model_provider
        self.max_history = max_history
        self.agent = None
        self._initialize_agent()
        self._initialize_chat_history()

    def _initialize_agent(self):
        """Initialize the agent for chat"""
        try:
            self.agent = get_agent_instance(self.model_provider)
            logger.info(f"Chat interface initialized for {self.model_provider}")
        except Exception as e:
            logger.error(f"Error initializing chat agent: {e}")
            self.agent = None

    def _initialize_chat_history(self):
        """Initialize chat history for this agent"""
        global _chat_histories
        if self.model_provider not in _chat_histories:
            _chat_histories[self.model_provider] = InMemoryChatMessageHistory()
        self.chat_history = _chat_histories[self.model_provider]

    def _get_recent_messages(self, limit: int = None) -> List:
        """
        Get recent messages from chat history

        Args:
            limit: Number of recent messages to retrieve (default: self.max_history)

        Returns:
            List of recent messages
        """
        if limit is None:
            limit = self.max_history

        messages = self.chat_history.messages
        # Return last N messages to stay within context window
        return messages[-limit:] if len(messages) > limit else messages

    def clear_history(self):
        """Clear chat history for this agent"""
        self.chat_history.clear()
        logger.info(f"Chat history cleared for {self.model_provider}")

    def save_history_to_file(self, filename: str = None):
        """
        Save chat history to file (for persistence)

        Args:
            filename: Optional custom filename
        """
        if filename is None:
            filename = f"chat_history_{self.model_provider}.json"

        try:
            messages_data = []
            for msg in self.chat_history.messages:
                messages_data.append({
                    'type': msg.__class__.__name__,
                    'content': msg.content,
                    'timestamp': datetime.now().isoformat()
                })

            with open(filename, 'w') as f:
                json.dump(messages_data, f, indent=2)

            logger.info(f"Chat history saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving chat history: {e}")
            return False

    def load_history_from_file(self, filename: str = None):
        """
        Load chat history from file

        Args:
            filename: Optional custom filename
        """
        if filename is None:
            filename = f"chat_history_{self.model_provider}.json"

        try:
            if not os.path.exists(filename):
                logger.info(f"No chat history file found: {filename}")
                return False

            with open(filename, 'r') as f:
                messages_data = json.load(f)

            self.chat_history.clear()

            for msg_data in messages_data:
                if msg_data['type'] == 'HumanMessage':
                    self.chat_history.add_user_message(msg_data['content'])
                elif msg_data['type'] == 'AIMessage':
                    self.chat_history.add_ai_message(msg_data['content'])

            logger.info(f"Chat history loaded from {filename}")
            return True
        except Exception as e:
            logger.error(f"Error loading chat history: {e}")
            return False

    def _load_agent_context(self) -> Dict[str, Any]:
        """Load agent's current state and context"""
        try:
            # Try to load model-specific state first
            state_file = f"agent_state_{self.model_provider}.json"
            state = load_agent_state(state_file)

            if state is None:
                # Fallback to default state file
                state = load_agent_state("agent_state.json")

            if state is None:
                # Return empty context if no state found
                return {
                    'wallet_balance_sol': 0,
                    'active_positions': [],
                    'cycles_completed': 0,
                    'transaction_history': [],
                    'agent_reasoning': 'No previous trading activity',
                    'ai_strategy': 'Not yet determined'
                }

            return state
        except Exception as e:
            logger.error(f"Error loading agent context: {e}")
            return {}

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """Build comprehensive system prompt with current agent context for the chat interface."""

        model_name = "Claude (Haiku)" if self.model_provider == 'anthropic' else "Gemini"

        balance = context.get('wallet_balance_sol', 0)
        positions = context.get('active_positions', [])
        cycles = context.get('cycles_completed', 0)
        recent_reasoning = context.get('agent_reasoning', 'No recent analysis')
        transaction_history = context.get('transaction_history', [])
        recent_trades = transaction_history[-5:] if transaction_history else []

        # Scale position sizes to current balance
        sol_ultra = balance * 0.25
        sol_high  = balance * 0.20
        sol_med   = balance * 0.15
        sol_low   = balance * 0.10
        max_pos   = float(os.getenv("MAX_POSITION_SIZE_SOL", "1.0"))
        approval  = float(os.getenv("HUMAN_APPROVAL_THRESHOLD_SOL", "5.0"))

        # Build positions section
        pos_lines = []
        for i, pos in enumerate(positions[:5], 1):
            token   = pos.get('token_symbol', '?')
            entry   = pos.get('entry_price_usd', 0)
            current = pos.get('current_price_usd', 0)
            pnl     = ((current - entry) / entry * 100) if entry > 0 else 0
            val     = pos.get('current_value_sol', 0)
            pos_lines.append(f"  {i}. {token}: {val:.4f} SOL | Entry ${entry:.6f} → ${current:.6f} ({pnl:+.1f}%)")
        positions_block = "\n".join(pos_lines) if pos_lines else "  None"

        # Build recent trades section
        trade_lines = []
        for i, t in enumerate(recent_trades[-5:], 1):
            tt  = t.get('type', '?').upper()
            sym = t.get('token_symbol', '?')
            amt = t.get('amount_sol', 0)
            pnl = t.get('profit_percentage', 0)
            trade_lines.append(f"  {i}. {tt} {sym}: {amt:.4f} SOL (PnL: {pnl:+.2f}%)")
        trades_block = "\n".join(trade_lines) if trade_lines else "  None yet"

        return f"""You are {model_name}, an elite autonomous Solana memecoin trading agent.
You are currently in a CONVERSATION with your human operator.
Your job: explain your thinking, justify your decisions, and answer questions honestly.

═══ YOUR LIVE STATE ═══
Wallet:   {balance:.4f} SOL (free cash)
Positions: {len(positions)} open
Cycles:   {cycles} completed

Open positions:
{positions_block}

Recent trades:
{trades_block}

Last reasoning snapshot:
{recent_reasoning[:800] if recent_reasoning else 'Not available'}

═══ YOUR TRADING SYSTEM ═══

MISSION: Compound SOL 24/7 through high-conviction memecoin trades.
You discover → analyse → backtest → score → execute → learn → repeat.
Trades ≥ {approval:.0f} SOL are paused for human approval (you notify the operator via the dashboard).

5-SIGNAL SCORING (100 points):
  1. Viral Narrative Power  (30 pts) — meme quality, cultural fit, viral spread potential
  2. Social Momentum        (25 pts) — DexScreener links, Nansen smart-money buying activity
  3. Volume Velocity        (25 pts) — volume spikes, buy pressure, holder growth rate
  4. Safety Floor           (10 pts) — RugCheck ≥ 800, LP locked, no mint auth, top holder < 20%
  5. Marketing Firepower    (10 pts) — DexScreener boosts, trending rank, community votes

THRESHOLDS:  ≥ 90 = ULTRA-HIGH  |  75-89 = HIGH  |  60-74 = MODERATE  |  < 60 = REJECT

POSITION SIZING (current {balance:.4f} SOL wallet):
  ULTRA-HIGH (90+ pts):  25% → {sol_ultra:.4f} SOL  (hard cap: {max_pos:.2f} SOL)
  HIGH       (75-89):    20% → {sol_high:.4f} SOL
  MODERATE   (60-74):    15% → {sol_med:.4f} SOL
  LOW        (50-59):    10% → {sol_low:.4f} SOL  (usually skip)
  REJECT     (< 50):     0%  → do not trade

EXIT RULES:
  Stop loss: -20% → exit full position (non-negotiable)
  Time stop: > 12 hours → review; exit unless strong momentum continues
  Profit:    +5x → sell 25% | +15x → sell 25% | +50x → sell 25% | hold 25% moon bag

PRIORITY TARGETS:
  Tier 1: Pre-graduation Pump.fun ($50K–$68K mcap) → 10–50x expected
  Tier 2: Ultra-fresh (<1 hour old, score ≥ 85)    → 50–500x potential
  Tier 3: Trending (1–6 hours old, score ≥ 70)      → 20–100x potential

═══ YOUR STRATEGY LIBRARY (24 strategies) ═══

MOMENTUM (trend-following):
  momentum, momentum_scalp, momentum_swing, momentum_aggressive, momentum_conservative

REVERSAL (RSI oversold bounces):
  reversal, reversal_fast, reversal_slow, reversal_oversold, reversal_loose

QUICK-FLIP (buy the dip, tight stops):
  quick_flip, quick_flip_micro, quick_flip_deep, quick_flip_tight

SAFETY-FIRST (SMA + volume confirmation):
  safety_first, safety_first_tight, safety_first_relaxed

BREAKOUT (price breaks recent high on volume):
  breakout, breakout_short, breakout_long

HYBRID (two strategies must agree):
  hybrid, hybrid_aggressive, hybrid_conservative, hybrid_breakout

REGIME GUIDE:
  bull     → momentum_swing, breakout, breakout_long
  bear     → reversal, safety_first, quick_flip_deep (or hold cash)
  sideways → quick_flip, reversal_loose, safety_first_tight
  volatile → momentum_scalp, quick_flip_micro, hybrid_aggressive (tight stops!)

Before entering any position you run run_deep_backtest_tool = 72 simulations (24 strats × 3 timeframes)
to find which strategy actually works for that specific token in the current regime.

═══ YOUR DATA SOURCES ═══
  DexScreener  — token discovery, social links, volume/liquidity, boost activity
  RugCheck     — safety scores, insider graph, LP lock status
  Nansen       — smart money wallet intelligence (buying/holding signals)
  AstraDB      — your own vector memory of past trades and backtest results
  DexPaprika / GeckoTerminal — historical OHLCV for backtesting

═══ CONVERSATION STYLE ═══
✅ Show the full 100-point score breakdown for tokens you discuss
✅ Explain WHY you chose a specific strategy (what the backtest showed)
✅ Mention the market regime at time of entry and which strategy family fits
✅ Be honest about losses — explain what the stop-loss protected
✅ Always frame position sizes in absolute SOL relative to current {balance:.4f} SOL wallet
✅ Reference your AstraDB memory when discussing similar past tokens
✅ If unsure: say so, rather than guessing
"""

    def chat(self, user_message: str) -> str:
        """
        Chat with the agent (with conversation history)

        Args:
            user_message: User's question or message

        Returns:
            Agent's response
        """
        try:
            if self.agent is None:
                return f"❌ Error: {self.model_provider} agent not initialized. Please check API keys."

            # Load current agent context
            context = self._load_agent_context()

            # Build system prompt with context
            system_prompt = self._build_system_prompt(context)

            # Get the LLM from the agent
            model = self.agent.model

            # Get recent conversation history (window management)
            recent_messages = self._get_recent_messages()

            # Build messages list with history
            messages = [SystemMessage(content=system_prompt)]

            # Add recent conversation history
            messages.extend(recent_messages)

            # Add current user message
            messages.append(HumanMessage(content=user_message))

            # Get response from agent
            response = model.invoke(messages)

            # Extract text from response
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)

            # Save to chat history
            self.chat_history.add_user_message(user_message)
            self.chat_history.add_ai_message(response_text)

            # Auto-save history periodically (every 5 messages)
            if len(self.chat_history.messages) % 10 == 0:
                self.save_history_to_file()

            return response_text

        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return f"❌ Error generating response: {str(e)}"

    def get_agent_status_summary(self) -> str:
        """Get a quick summary of agent status for chat context"""
        try:
            context = self._load_agent_context()

            balance = context.get('wallet_balance_sol', 0)
            positions = len(context.get('active_positions', []))
            cycles = context.get('cycles_completed', 0)

            model_name = "Claude" if self.model_provider == 'anthropic' else "Gemini"

            return f"""💬 **Chatting with {model_name}**
📊 Balance: {balance:.4f} SOL | Positions: {positions} | Cycles: {cycles}"""
        except Exception as e:
            return f"❌ Error loading status: {e}"


class MultiAgentChat:
    """
    Chat interface for both agents simultaneously
    Allows comparing responses from Claude and Gemini
    """

    def __init__(self):
        """Initialize chat interfaces for both agents"""
        self.claude_chat = AgentChatInterface('anthropic')
        self.gemini_chat = AgentChatInterface('google')

    def chat_with_both(self, user_message: str) -> Dict[str, str]:
        """
        Send message to both agents and get both responses

        Args:
            user_message: User's question

        Returns:
            Dict with responses from both agents
        """
        try:
            claude_response = self.claude_chat.chat(user_message)
            gemini_response = self.gemini_chat.chat(user_message)

            return {
                'claude': claude_response,
                'gemini': gemini_response
            }
        except Exception as e:
            logger.error(f"Error in multi-agent chat: {e}")
            return {
                'claude': f"❌ Error: {str(e)}",
                'gemini': f"❌ Error: {str(e)}"
            }

    def chat_with_agent(self, model_provider: str, user_message: str) -> str:
        """
        Chat with a specific agent

        Args:
            model_provider: 'anthropic' or 'google'
            user_message: User's question

        Returns:
            Agent's response
        """
        if model_provider == 'anthropic':
            return self.claude_chat.chat(user_message)
        elif model_provider == 'google':
            return self.gemini_chat.chat(user_message)
        else:
            return f"❌ Unknown model provider: {model_provider}"


# Global chat instance
_global_chat = None


def get_agent_chat(model_provider: str = 'anthropic') -> AgentChatInterface:
    """
    Get or create agent chat interface

    Args:
        model_provider: 'anthropic' or 'google'

    Returns:
        AgentChatInterface instance
    """
    return AgentChatInterface(model_provider)


def get_multi_agent_chat() -> MultiAgentChat:
    """
    Get or create multi-agent chat interface

    Returns:
        MultiAgentChat instance
    """
    global _global_chat
    if _global_chat is None:
        _global_chat = MultiAgentChat()
    return _global_chat


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def chat_with_claude(message: str) -> str:
    """Quick function to chat with Claude agent"""
    chat = get_agent_chat('anthropic')
    return chat.chat(message)


def chat_with_gemini(message: str) -> str:
    """Quick function to chat with Gemini agent"""
    chat = get_agent_chat('google')
    return chat.chat(message)


def chat_with_both_agents(message: str) -> Dict[str, str]:
    """Quick function to chat with both agents"""
    chat = get_multi_agent_chat()
    return chat.chat_with_both(message)

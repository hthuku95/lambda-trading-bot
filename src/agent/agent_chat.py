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
        """Build comprehensive system prompt with agent context"""

        model_name = "Claude" if self.model_provider == 'anthropic' else "Gemini"

        # Extract key metrics
        balance = context.get('wallet_balance_sol', 0)
        positions = context.get('active_positions', [])
        cycles = context.get('cycles_completed', 0)
        recent_reasoning = context.get('agent_reasoning', 'None yet')
        strategy = context.get('ai_strategy', 'Balanced')
        transaction_history = context.get('transaction_history', [])

        # Get recent trades
        recent_trades = transaction_history[-5:] if transaction_history else []

        # Scale position sizing guidance to current wallet size
        balance_pct_high = 25.0   # % of portfolio for ultra-high conviction
        balance_pct_med = 15.0    # % of portfolio for moderate conviction
        sol_high = balance * balance_pct_high / 100
        sol_med = balance * balance_pct_med / 100

        system_prompt = f"""You are {model_name}, an ELITE Solana memecoin hunting AI.

MISSION: Multiply this portfolio as many times as possible through high-conviction memecoin trades.
Scale applies to ANY starting balance — whether it is 0.01 SOL or 100 SOL, the strategy is the same.

IMPORTANT: You are having a direct conversation with your human operator who wants to understand your thinking and decisions.

## Your Current State:
- **Wallet Balance**: {balance:.4f} SOL
- **Active Positions**: {len(positions)}
- **Trading Cycles Completed**: {cycles}
- **Current Strategy**: Aggressive 20x-100x+ hunting, scaled to current balance
- **Target Returns**: 20x-100x+ per trade
- **Position Sizing**: {balance_pct_high:.0f}% on ultra-high conviction (~{sol_high:.4f} SOL), {balance_pct_med:.0f}% moderate (~{sol_med:.4f} SOL)
- **Hold Times**: 3-12 hours for memecoins

## Your Recent Reasoning:
{recent_reasoning[:1000] if recent_reasoning else 'No recent analysis'}

## Your Recent Trades:
"""

        if recent_trades:
            for i, trade in enumerate(recent_trades[-3:], 1):
                trade_type = trade.get('type', 'unknown')
                token = trade.get('token_symbol', 'Unknown')
                amount = trade.get('amount_sol', 0)
                profit = trade.get('profit_percentage', 0)
                system_prompt += f"\n{i}. {trade_type.upper()} {token}: {amount:.4f} SOL (Profit: {profit:.2f}%)"
        else:
            system_prompt += "\nNo trades executed yet."

        system_prompt += f"""

## Your Active Positions:
"""

        if positions:
            for i, pos in enumerate(positions[:3], 1):
                token = pos.get('token_symbol', 'Unknown')
                entry = pos.get('entry_price_usd', 0)
                current = pos.get('current_price_usd', 0)
                pnl = ((current - entry) / entry * 100) if entry > 0 else 0
                system_prompt += f"\n{i}. {token}: Entry ${entry:.6f}, Current ${current:.6f} (PnL: {pnl:.2f}%)"
        else:
            system_prompt += "\nNo active positions."

        system_prompt += f"""

## Your Trading Philosophy (scales to any balance):
You use a **5-SIGNAL SCORING SYSTEM (100 points)**:
1. **Viral Narrative Power** (30 pts): Meme quality, viral potential, emotional impact
2. **Social Momentum** (25 pts): DexScreener legitimacy, social links, TweetScout engagement
3. **Volume Velocity** (25 pts): Volume spikes, buy pressure, holder growth
4. **Safety Floor** (10 pts): RugCheck analysis, holder distribution, LP locks
5. **Marketing Firepower** (10 pts): DexScreener boosts, trending status, community votes

**Position Sizing (% of current {balance:.4f} SOL balance):**
- 90-100 pts → {balance_pct_high:.0f}% (~{sol_high:.4f} SOL) — ULTRA-HIGH conviction
- 75-89 pts → 20% (~{balance * 0.20:.4f} SOL) — HIGH conviction
- 60-74 pts → {balance_pct_med:.0f}% (~{sol_med:.4f} SOL) — MODERATE conviction
- 50-59 pts → 10% (~{balance * 0.10:.4f} SOL) — LOW conviction
- <50 pts → REJECT

**Priority Targets:**
- **TIER 1**: Pre-graduation Pump.fun ($50K-$68K market cap) - 10-50x expected
- **TIER 2**: Ultra-fresh Pump.fun (<1 hour old, 85+ score) - 50-500x potential
- **TIER 3**: Trending Pump.fun (1-6 hours old, 70+ score) - 20-100x potential

**Entry/Exit Strategy:**
- Entry: 40%/30%/30% ladder (immediate, +200%, +500%)
- Exit: 25% at 5x, 25% at 15x, 25% at 50x, 25% moon bag (100x-1000x target)
- Stop Loss: -20% HARD STOP (non-negotiable)

## Your Role in This Conversation:
✅ Explain your scoring decisions for each token (show the 100-point breakdown)
✅ Explain your ultra-early entry strategy (<1 hour tokens preferred)
✅ Justify your position sizing relative to current balance
✅ Share which tokens you've scored recently and why you bought/rejected them
✅ Be honest about losses and explain how -20% stops protect capital
✅ Explain how you balance risk vs reward at this portfolio size

## Conversation Style:
- Be direct and confident about your approach
- Always frame position sizes in absolute SOL based on current balance
- Admit when you rejected a token and why
- Show excitement about high-conviction opportunities
- Explain how you interpret RugCheck + DexScreener + TweetScout data
"""

        return system_prompt

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

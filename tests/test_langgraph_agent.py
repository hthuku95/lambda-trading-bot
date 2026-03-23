

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from src.agent.langgraph_trading_agent import (
    CompleteLangGraphTradingAgent,
    TradingAgentState,
    get_wallet_balance_tool,
    execute_trade_tool,
    query_trade_history_db_tool,
    get_performance_analytics_db_tool,
    search_system_logs_db_tool,
)
import src.agent.langgraph_trading_agent as _lgt

@pytest.fixture
def mock_llm_and_tools():
    """Mocks the LLM, tools, and state management functions."""
    with patch('src.agent.langgraph_trading_agent.ChatGoogleGenerativeAI') as mock_chat_class, \
         patch('src.agent.langgraph_trading_agent.get_wallet_balance_tool') as mock_wallet_tool, \
         patch('src.agent.langgraph_trading_agent.load_agent_state') as mock_load_state, \
         patch('src.agent.langgraph_trading_agent.save_agent_state') as mock_save_state, \
         patch('src.agent.langgraph_trading_agent.update_portfolio_metrics') as mock_update_metrics:
        
        # Mock the LLM
        mock_llm = MagicMock()
        mock_chat_class.return_value = mock_llm

        # Mock a tool
        mock_wallet_tool.invoke.return_value = {"success": True, "balance_sol": 100.0}
        mock_wallet_tool.name = "get_wallet_balance_tool"

        # Mock state functions
        # Configure load_agent_state to return a default state
        mock_load_state.return_value = {"cycles_completed": 0, "active_positions": []}
        # Make update_portfolio_metrics return the state it's given
        mock_update_metrics.side_effect = lambda state: state

        yield {
            "llm": mock_llm,
            "tools": [mock_wallet_tool],
            "load_state": mock_load_state,
            "save_state": mock_save_state,
            "update_metrics": mock_update_metrics
        }


@pytest.fixture
def trading_agent(mock_llm_and_tools):
    """Returns an instance of the agent with mocked dependencies."""
    # Force MemorySaver so each test gets fresh checkpoint state (not shared SQLite file)
    with patch.dict('os.environ', {'GOOGLE_API_KEY': 'test-key'}), \
         patch('src.agent.langgraph_trading_agent._SQLITE_AVAILABLE', False):
        agent = CompleteLangGraphTradingAgent(model_provider="gemini")
        # Replace the real model and tools with our mocks
        agent.model = mock_llm_and_tools["llm"]
        agent.model_with_tools = mock_llm_and_tools["llm"] # Simplified for testing
        agent.tools = mock_llm_and_tools["tools"]
        # Rebuild the graph with the mocked components
        agent.graph = agent._build_graph()
    return agent

def test_agent_initialization(trading_agent):
    """Tests that the agent and its graph are initialized correctly."""
    assert trading_agent is not None
    assert trading_agent.graph is not None
    assert "agent" in trading_agent.graph.nodes
    assert "action" in trading_agent.graph.nodes

def test_trading_cycle_tool_call_flow(trading_agent, mock_llm_and_tools):
    """
    Tests a full agent cycle, ensuring the LLM calls a tool and the tool's
    output is processed.
    """
    mock_llm = mock_llm_and_tools["llm"]
    
    # --- Define the multi-turn conversation ---
    # 1. Initial user message (created by the agent)
    initial_human_message = HumanMessage(content="...") 

    # 2. LLM responds with a tool call
    tool_call_id = "tool_call_123"
    ai_message_with_tool_call = AIMessage(
        content="",
        tool_calls=[{
            "name": "get_wallet_balance_tool",
            "args": {},
            "id": tool_call_id
        }]
    )

    # 3. Tool execution result
    tool_output_message = ToolMessage(
        content='{"success": True, "balance_sol": 100.0}',
        tool_call_id=tool_call_id
    )

    # 4. LLM responds with final analysis after getting tool output
    final_ai_response = AIMessage(content="The wallet balance is 100.0 SOL.")

    # Configure the mock LLM to simulate this conversation
    mock_llm.invoke.side_effect = [
        ai_message_with_tool_call, # First call returns a tool call
        final_ai_response          # Second call returns the final answer
    ]

    # --- Run the agent cycle ---
    initial_state = {"cycles_completed": 0}
    final_state = trading_agent.run_trading_cycle(initial_state)

    # --- Assertions ---
    # Check that the LLM was called twice
    assert mock_llm.invoke.call_count == 2

    # Check that the wallet tool was called
    wallet_tool = mock_llm_and_tools["tools"][0]
    wallet_tool.invoke.assert_called_once()

    # Check the final state for correctness
    assert final_state["cycles_completed"] == 1
    assert "get_wallet_balance_tool" in final_state["tools_used_this_cycle"]
    assert "The wallet balance is 100.0 SOL." in final_state["agent_reasoning"]

def test_trading_cycle_no_tool_call(trading_agent, mock_llm_and_tools):
    """
    Tests a simplified cycle where the LLM responds directly without needing a tool.
    """
    mock_llm = mock_llm_and_tools["llm"]
    
    # LLM responds immediately with no tool calls
    final_ai_response = AIMessage(content="No action needed at this time.")
    mock_llm.invoke.return_value = final_ai_response

    initial_state = {"cycles_completed": 5}
    final_state = trading_agent.run_trading_cycle(initial_state)

    # LLM should only be called once
    mock_llm.invoke.assert_called_once()

    # No tools should have been used
    wallet_tool = mock_llm_and_tools["tools"][0]
    wallet_tool.invoke.assert_not_called()

    # Check final state
    assert final_state["cycles_completed"] == 6
    assert not final_state["tools_used_this_cycle"]
    assert "No action needed at this time." in final_state["agent_reasoning"]


# ─────────────────────────────────────────────────────────────────────────────
# get_wallet_balance_tool() — dry-run vs live
# ─────────────────────────────────────────────────────────────────────────────

class TestGetWalletBalanceTool:
    def test_dry_run_returns_simulated_balance(self):
        _lgt._current_trading_mode = "dry_run"
        _lgt._current_simulated_balance = 7.5

        result = get_wallet_balance_tool.invoke({})

        assert result["success"] is True
        assert result["balance_sol"] == pytest.approx(7.5)
        assert result["simulated"] is True

    def test_live_mode_calls_get_wallet_balance(self):
        _lgt._current_trading_mode = "live"
        with patch("src.agent.langgraph_trading_agent.get_wallet_balance", return_value=3.14) as mock_bal:
            result = get_wallet_balance_tool.invoke({})
        mock_bal.assert_called_once()
        assert result["success"] is True
        assert result["balance_sol"] == pytest.approx(3.14)
        assert result["simulated"] is False

    def test_live_mode_error_returns_failure(self):
        _lgt._current_trading_mode = "live"
        with patch("src.agent.langgraph_trading_agent.get_wallet_balance",
                   side_effect=Exception("RPC down")):
            result = get_wallet_balance_tool.invoke({})
        assert result["success"] is False
        assert "error" in result


# ─────────────────────────────────────────────────────────────────────────────
# execute_trade_tool() — dry-run mode
# ─────────────────────────────────────────────────────────────────────────────

class TestExecuteTradeToolDryRun:
    @pytest.fixture(autouse=True)
    def setup_dry_run(self):
        """Ensure module-level state is in dry-run with a known balance.

        Sets MAX_POSITION_SIZE_SOL=10.0 so test amounts (≤5 SOL) are never capped
        by the default 0.1–0.5 SOL from the local .env file.
        """
        _lgt._current_trading_mode = "dry_run"
        _lgt._current_simulated_balance = 10.0
        # Raise the cap so test amounts are not silently capped
        with patch("src.agent.langgraph_trading_agent.wallet") as mock_wallet, \
             patch.dict("os.environ", {"MAX_POSITION_SIZE_SOL": "10.0"}):
            mock_wallet.pubkey.return_value = "FakePubkey111111111111111111111111111111111"
            yield

    def test_dry_run_buy_debits_simulated_balance(self):
        before = _lgt._current_simulated_balance
        result = execute_trade_tool.invoke({
            "trade_type": "buy",
            "token_address": "TokenMintABC",
            "amount_sol": 1.0,
            "quote_data": {},
            "dry_run": True,
            "reasoning": "test buy",
        })
        assert result["success"] is True
        assert result["dry_run"] is True
        assert _lgt._current_simulated_balance == pytest.approx(before - 1.0)

    def test_dry_run_sell_credits_simulated_balance(self):
        _lgt._current_simulated_balance = 5.0
        result = execute_trade_tool.invoke({
            "trade_type": "sell",
            "token_address": "TokenMintABC",
            "amount_sol": 2.0,
            "quote_data": {},
            "dry_run": True,
            "reasoning": "test sell",
        })
        assert result["success"] is True
        assert _lgt._current_simulated_balance == pytest.approx(7.0)

    def test_dry_run_balance_never_goes_below_zero(self):
        _lgt._current_simulated_balance = 0.1
        execute_trade_tool.invoke({
            "trade_type": "buy",
            "token_address": "TokenMintABC",
            "amount_sol": 5.0,  # way more than available
            "quote_data": {},
            "dry_run": True,
            "reasoning": "overdraft test",
        })
        assert _lgt._current_simulated_balance >= 0.0

    def test_dry_run_returns_simulated_balance_after(self):
        _lgt._current_simulated_balance = 10.0
        result = execute_trade_tool.invoke({
            "trade_type": "buy",
            "token_address": "TokenMintABC",
            "amount_sol": 2.0,
            "quote_data": {},
            "dry_run": True,
            "reasoning": "check return value",
        })
        assert "simulated_balance_after" in result
        assert result["simulated_balance_after"] == pytest.approx(8.0)

    def test_amount_capped_at_max_position_size(self):
        """Trade amount above MAX_POSITION_SIZE_SOL must be capped."""
        with patch.dict("os.environ", {"MAX_POSITION_SIZE_SOL": "0.5"}):
            _lgt._current_simulated_balance = 100.0
            result = execute_trade_tool.invoke({
                "trade_type": "buy",
                "token_address": "TokenMintABC",
                "amount_sol": 10.0,   # exceeds 0.5 SOL cap
                "quote_data": {},
                "dry_run": True,
                "reasoning": "cap test",
            })
        assert result["success"] is True
        # Balance should only decrease by 0.5, not 10
        assert _lgt._current_simulated_balance >= 99.5   # not pytest.approx — `>=` with float is fine


# ─────────────────────────────────────────────────────────────────────────────
# execute_trade_tool() — live mode
# ─────────────────────────────────────────────────────────────────────────────

class TestExecuteTradeToolLive:
    @pytest.fixture(autouse=True)
    def setup_live(self):
        _lgt._current_trading_mode = "live"
        with patch("src.agent.langgraph_trading_agent.wallet") as mock_wallet:
            mock_wallet.pubkey.return_value = "FakePubkey111111111111111111111111111111111"
            yield

    def test_live_no_quote_data_returns_failure(self):
        result = execute_trade_tool.invoke({
            "trade_type": "buy",
            "token_address": "TokenMintABC",
            "amount_sol": 0.1,
            "quote_data": {},   # empty — must fail gracefully
            "dry_run": False,
            "reasoning": "live test",
        })
        assert result["success"] is False

    def test_live_calls_get_swap_transaction_and_send(self):
        quote = {"inputMint": "So1...", "outputMint": "Tok...", "inAmount": "100000000"}
        with patch("src.agent.langgraph_trading_agent.get_swap_transaction",
                   return_value="base64txdata") as mock_swap, \
             patch("src.agent.langgraph_trading_agent.send_serialized_transaction",
                   return_value={"txid": "abc123"}) as mock_send:
            result = execute_trade_tool.invoke({
                "trade_type": "buy",
                "token_address": "TokenMintABC",
                "amount_sol": 0.1,
                "quote_data": quote,
                "dry_run": False,
                "reasoning": "live integration",
            })
        mock_swap.assert_called_once()
        mock_send.assert_called_once()
        assert result["success"] is True
        assert result["dry_run"] is False


# ─────────────────────────────────────────────────────────────────────────────
# DB query tools — happy path + DB unavailable guard
# ─────────────────────────────────────────────────────────────────────────────

class TestDbQueryTools:
    def test_query_trade_history_returns_success_dict(self):
        fake_trades = [{"trade_id": 1, "token_symbol": "MEME", "profit_sol": 0.1}]
        with patch("src.db.query_store.get_trade_history", return_value=fake_trades):
            result = query_trade_history_db_tool.invoke({})
        assert result["success"] is True
        assert result["count"] == 1
        assert result["trades"] == fake_trades

    def test_query_trade_history_on_db_exception_returns_failure(self):
        with patch("src.db.query_store.get_trade_history",
                   side_effect=Exception("DB unavailable")):
            result = query_trade_history_db_tool.invoke({})
        assert result["success"] is False
        assert result["trades"] == []
        assert "error" in result

    def test_get_performance_analytics_returns_success_dict(self):
        fake_summary = {"win_rate": 0.6, "total_trades": 10}
        with patch("src.db.query_store.get_performance_summary", return_value=fake_summary):
            result = get_performance_analytics_db_tool.invoke({})
        assert result["success"] is True
        assert result["analytics"] == fake_summary

    def test_get_performance_analytics_on_db_exception_returns_failure(self):
        with patch("src.db.query_store.get_performance_summary",
                   side_effect=Exception("timeout")):
            result = get_performance_analytics_db_tool.invoke({})
        assert result["success"] is False
        assert result["analytics"] == {}

    def test_search_system_logs_returns_success_dict(self):
        fake_logs = [{"level": "ERROR", "message": "something failed"}]
        with patch("src.db.query_store.search_logs", return_value=fake_logs):
            result = search_system_logs_db_tool.invoke({"level": "ERROR"})
        assert result["success"] is True
        assert result["count"] == 1
        assert result["logs"] == fake_logs

    def test_search_system_logs_on_db_exception_returns_failure(self):
        with patch("src.db.query_store.search_logs",
                   side_effect=Exception("connection refused")):
            result = search_system_logs_db_tool.invoke({})
        assert result["success"] is False
        assert result["logs"] == []

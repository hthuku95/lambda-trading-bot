"""
Tests for src/agent/langgraph_trading_agent.py

LangGraph agent tests that require LLM API calls are tagged @pytest.mark.integration.
Wallet balance and trade tool tests use real Solana RPC where possible.
"""
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
    """Mocks the LLM and state management functions for graph flow tests."""
    with patch('src.agent.langgraph_trading_agent.ChatGoogleGenerativeAI') as mock_chat_class, \
         patch('src.agent.langgraph_trading_agent.get_wallet_balance_tool') as mock_wallet_tool, \
         patch('src.agent.langgraph_trading_agent.load_agent_state') as mock_load_state, \
         patch('src.agent.langgraph_trading_agent.save_agent_state') as mock_save_state, \
         patch('src.agent.langgraph_trading_agent.update_portfolio_metrics') as mock_update_metrics:

        mock_llm = MagicMock()
        mock_chat_class.return_value = mock_llm

        mock_wallet_tool.invoke.return_value = {"success": True, "balance_sol": 1.0}
        mock_wallet_tool.name = "get_wallet_balance_tool"

        mock_load_state.return_value = {"cycles_completed": 0, "active_positions": []}
        mock_update_metrics.side_effect = lambda state: state

        yield {
            "llm": mock_llm,
            "tools": [mock_wallet_tool],
            "load_state": mock_load_state,
            "save_state": mock_save_state,
            "update_metrics": mock_update_metrics,
        }


@pytest.fixture
def trading_agent(mock_llm_and_tools):
    """Returns an agent instance with mocked LLM dependencies."""
    with patch.dict('os.environ', {'GOOGLE_API_KEY': 'test-key'}), \
         patch('src.agent.langgraph_trading_agent._SQLITE_AVAILABLE', False):
        agent = CompleteLangGraphTradingAgent(model_provider="gemini")
        agent.model = mock_llm_and_tools["llm"]
        agent.model_with_tools = mock_llm_and_tools["llm"]
        agent.tools = mock_llm_and_tools["tools"]
        agent.graph = agent._build_graph()
    return agent


def test_agent_initialization(trading_agent):
    """Tests that the agent and its graph are initialized correctly."""
    assert trading_agent is not None
    assert trading_agent.graph is not None
    assert "agent" in trading_agent.graph.nodes
    assert "action" in trading_agent.graph.nodes


def test_trading_cycle_tool_call_flow(trading_agent, mock_llm_and_tools):
    """Tests a full agent cycle where the LLM calls a tool."""
    mock_llm = mock_llm_and_tools["llm"]

    tool_call_id = "tool_call_123"
    ai_message_with_tool_call = AIMessage(
        content="",
        tool_calls=[{
            "name": "get_wallet_balance_tool",
            "args": {},
            "id": tool_call_id,
        }]
    )
    tool_output_message = ToolMessage(
        content='{"success": true, "balance_sol": 1.0}',
        tool_call_id=tool_call_id,
    )
    final_ai_response = AIMessage(content="The wallet balance is 1.0 SOL.")

    mock_llm.invoke.side_effect = [ai_message_with_tool_call, final_ai_response]

    initial_state = {"cycles_completed": 0}
    final_state = trading_agent.run_trading_cycle(initial_state)

    assert mock_llm.invoke.call_count == 2
    mock_llm_and_tools["tools"][0].invoke.assert_called_once()
    assert final_state["cycles_completed"] == 1
    assert "get_wallet_balance_tool" in final_state["tools_used_this_cycle"]
    assert "The wallet balance is 1.0 SOL." in final_state["agent_reasoning"]


def test_trading_cycle_no_tool_call(trading_agent, mock_llm_and_tools):
    """Tests a cycle where the LLM responds directly without calling a tool."""
    mock_llm = mock_llm_and_tools["llm"]
    final_ai_response = AIMessage(content="No action needed at this time.")
    mock_llm.invoke.return_value = final_ai_response

    initial_state = {"cycles_completed": 5}
    final_state = trading_agent.run_trading_cycle(initial_state)

    mock_llm.invoke.assert_called_once()
    mock_llm_and_tools["tools"][0].invoke.assert_not_called()
    assert final_state["cycles_completed"] == 6
    assert not final_state["tools_used_this_cycle"]
    assert "No action needed at this time." in final_state["agent_reasoning"]


# ─────────────────────────────────────────────────────────────────────────────
# get_wallet_balance_tool() — always calls real Solana RPC
# ─────────────────────────────────────────────────────────────────────────────

class TestGetWalletBalanceTool:
    def test_balance_tool_calls_get_wallet_balance(self):
        """Tool must call real get_wallet_balance() regardless of trading mode."""
        with patch("src.agent.langgraph_trading_agent.get_wallet_balance",
                   return_value=3.14) as mock_bal:
            result = get_wallet_balance_tool.invoke({})
        mock_bal.assert_called_once()
        assert result["success"] is True
        assert result["balance_sol"] == pytest.approx(3.14)

    def test_balance_tool_returns_nonnegative(self):
        """balance_sol must be >= 0 for any real wallet."""
        with patch("src.agent.langgraph_trading_agent.get_wallet_balance", return_value=0.0):
            result = get_wallet_balance_tool.invoke({})
        assert result["success"] is True
        assert result["balance_sol"] >= 0.0

    def test_balance_tool_error_returns_failure(self):
        with patch("src.agent.langgraph_trading_agent.get_wallet_balance",
                   side_effect=Exception("RPC down")):
            result = get_wallet_balance_tool.invoke({})
        assert result["success"] is False
        assert "error" in result


# ─────────────────────────────────────────────────────────────────────────────
# execute_trade_tool() — dry-run mode: build real tx, don't submit
# ─────────────────────────────────────────────────────────────────────────────

class TestExecuteTradeToolDryRun:
    @pytest.fixture(autouse=True)
    def setup_dry_run(self):
        _lgt._current_trading_mode = "dry_run"
        with patch("src.agent.langgraph_trading_agent.wallet") as mock_wallet, \
             patch.dict("os.environ", {"MAX_POSITION_SIZE_SOL": "10.0"}):
            mock_wallet.pubkey.return_value = "FakePubkey111111111111111111111111111111111"
            yield

    def test_dry_run_without_quote_data_fails(self):
        """dry_run with empty quote_data must fail gracefully."""
        result = execute_trade_tool.invoke({
            "trade_type": "buy",
            "token_address": "TokenMintABC",
            "amount_sol": 1.0,
            "quote_data": {},
            "dry_run": True,
            "reasoning": "test buy without quote",
        })
        assert result["success"] is False
        assert "error" in result

    def test_dry_run_with_quote_data_builds_transaction(self):
        """dry_run with a real quote must call get_swap_transaction and return transaction_ready."""
        quote = {
            "inputMint": "So11111111111111111111111111111111111111112",
            "outputMint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            "inAmount": "100000000",
            "outAmount": "5000000000",
            "slippageBps": 100,
            "swapMode": "ExactIn",
        }
        with patch("src.agent.langgraph_trading_agent.get_swap_transaction",
                   return_value="base64txdata") as mock_swap:
            result = execute_trade_tool.invoke({
                "trade_type": "buy",
                "token_address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                "amount_sol": 0.1,
                "quote_data": quote,
                "dry_run": True,
                "reasoning": "test dry run with quote",
            })
        mock_swap.assert_called_once()
        assert result["success"] is True
        assert result["dry_run"] is True
        assert "transaction_ready" in result
        assert result["transaction_ready"] is True

    def test_dry_run_transaction_not_submitted(self):
        """dry_run must NEVER call send_serialized_transaction."""
        quote = {"inputMint": "So1...", "outputMint": "Tok...", "inAmount": "100000000"}
        with patch("src.agent.langgraph_trading_agent.get_swap_transaction",
                   return_value="base64txdata"), \
             patch("src.agent.langgraph_trading_agent.send_serialized_transaction") as mock_send:
            execute_trade_tool.invoke({
                "trade_type": "buy",
                "token_address": "TokenMintABC",
                "amount_sol": 0.1,
                "quote_data": quote,
                "dry_run": True,
                "reasoning": "verify no submission",
            })
        mock_send.assert_not_called()

    def test_dry_run_transaction_ready_false_when_build_fails(self):
        """If get_swap_transaction returns None, transaction_ready must be False."""
        quote = {"inputMint": "So1...", "outputMint": "Tok...", "inAmount": "100000000"}
        with patch("src.agent.langgraph_trading_agent.get_swap_transaction", return_value=None):
            result = execute_trade_tool.invoke({
                "trade_type": "buy",
                "token_address": "TokenMintABC",
                "amount_sol": 0.1,
                "quote_data": quote,
                "dry_run": True,
                "reasoning": "tx build failure",
            })
        assert result["success"] is True
        assert result["transaction_ready"] is False


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
            "quote_data": {},
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
# DB query tools — happy path + exception guard
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

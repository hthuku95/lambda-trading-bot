

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from src.agent.langgraph_trading_agent import CompleteLangGraphTradingAgent, TradingAgentState

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
    with patch.dict('os.environ', {'GOOGLE_API_KEY': 'test-key'}):
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


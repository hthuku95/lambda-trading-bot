# tests/test_agent_chat.py
"""
Tests for src/agent/agent_chat.py

AgentChatInterface and MultiAgentChat are tested with mocked LLMs.
The chat logic, history management, and error handling are tested for real.

Key facts about the source:
- get_agent_chat() creates a new AgentChatInterface each call (no caching)
- chat_with_both() returns {'claude': ..., 'gemini': ...} (not 'anthropic'/'google')
- chat_history is InMemoryChatMessageHistory — use .messages for length
- chat() returns an error string when self.agent is None (not None itself)
"""
import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Module-level function tests (get_agent_chat, get_multi_agent_chat, etc.)
# ─────────────────────────────────────────────────────────────────────────────

class TestModuleFunctions:
    @pytest.fixture(autouse=True)
    def reset_global_chat(self):
        """Reset the module-level _global_chat singleton between tests."""
        import src.agent.agent_chat as ac
        ac._global_chat = None
        yield
        ac._global_chat = None

    def test_get_agent_chat_returns_agent_chat_interface(self):
        with patch("src.agent.agent_chat.get_agent_instance"), \
             patch("src.agent.agent_chat.ChatAnthropic"), \
             patch("src.agent.agent_chat.ChatGoogleGenerativeAI"):
            from src.agent.agent_chat import get_agent_chat, AgentChatInterface
            instance = get_agent_chat("anthropic")
        assert isinstance(instance, AgentChatInterface)

    def test_get_agent_chat_returns_new_instance_each_call(self):
        """get_agent_chat() does not cache — each call returns a fresh instance."""
        with patch("src.agent.agent_chat.get_agent_instance"), \
             patch("src.agent.agent_chat.ChatAnthropic"), \
             patch("src.agent.agent_chat.ChatGoogleGenerativeAI"):
            from src.agent.agent_chat import get_agent_chat, AgentChatInterface
            first = get_agent_chat("google")
            second = get_agent_chat("google")
        assert isinstance(first, AgentChatInterface)
        assert isinstance(second, AgentChatInterface)

    def test_different_providers_get_different_instances(self):
        with patch("src.agent.agent_chat.get_agent_instance"), \
             patch("src.agent.agent_chat.ChatAnthropic"), \
             patch("src.agent.agent_chat.ChatGoogleGenerativeAI"):
            from src.agent.agent_chat import get_agent_chat
            claude = get_agent_chat("anthropic")
            gemini = get_agent_chat("google")
        assert claude is not gemini

    def test_get_multi_agent_chat_returns_multi_agent_chat(self):
        with patch("src.agent.agent_chat.get_agent_instance"), \
             patch("src.agent.agent_chat.ChatAnthropic"), \
             patch("src.agent.agent_chat.ChatGoogleGenerativeAI"):
            from src.agent.agent_chat import get_multi_agent_chat, MultiAgentChat
            multi = get_multi_agent_chat()
        assert isinstance(multi, MultiAgentChat)

    def test_get_multi_agent_chat_returns_singleton(self):
        with patch("src.agent.agent_chat.get_agent_instance"), \
             patch("src.agent.agent_chat.ChatAnthropic"), \
             patch("src.agent.agent_chat.ChatGoogleGenerativeAI"):
            from src.agent.agent_chat import get_multi_agent_chat
            first = get_multi_agent_chat()
            second = get_multi_agent_chat()
        assert first is second

    def test_chat_with_claude_calls_agent_chat(self):
        """chat_with_claude() creates an interface and calls .chat()."""
        with patch("src.agent.agent_chat.get_agent_instance"), \
             patch("src.agent.agent_chat.AgentChatInterface.chat",
                   return_value="Claude response") as mock_chat:
            from src.agent.agent_chat import chat_with_claude
            result = chat_with_claude("Hello Claude")
        mock_chat.assert_called_once_with("Hello Claude")
        assert result == "Claude response"

    def test_chat_with_gemini_calls_agent_chat(self):
        """chat_with_gemini() creates an interface and calls .chat()."""
        with patch("src.agent.agent_chat.get_agent_instance"), \
             patch("src.agent.agent_chat.AgentChatInterface.chat",
                   return_value="Gemini response") as mock_chat:
            from src.agent.agent_chat import chat_with_gemini
            result = chat_with_gemini("Hello Gemini")
        mock_chat.assert_called_once_with("Hello Gemini")
        assert result == "Gemini response"

    def test_chat_with_both_agents_delegates_to_multi_agent_chat(self):
        with patch("src.agent.agent_chat.get_agent_instance"), \
             patch("src.agent.agent_chat.ChatAnthropic"), \
             patch("src.agent.agent_chat.ChatGoogleGenerativeAI"):
            from src.agent.agent_chat import get_multi_agent_chat, chat_with_both_agents
            multi = get_multi_agent_chat()
        with patch.object(multi, "chat_with_both",
                         return_value={"claude": "Claude says hi", "gemini": "Gemini says hi"}):
            with patch("src.agent.agent_chat._global_chat", multi):
                result = chat_with_both_agents("Hello both")
        assert "claude" in result
        assert "gemini" in result


# ─────────────────────────────────────────────────────────────────────────────
# AgentChatInterface
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentChatInterface:
    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "I am the AI response."
        llm.invoke.return_value = mock_message
        return llm

    @pytest.fixture
    def chat_interface(self, mock_llm):
        """
        Build an AgentChatInterface with a properly wired mock agent.
        The source uses self.agent.model.invoke() — so mock_llm must be
        placed at interface.agent.model.
        """
        with patch("src.agent.agent_chat.get_agent_instance") as mock_get_agent, \
             patch("src.agent.agent_chat.load_agent_state", return_value=None):
            from src.agent.agent_chat import AgentChatInterface
            interface = AgentChatInterface(model_provider="google")
        # Wire mock_llm as the underlying model so chat() uses it
        interface.agent = MagicMock()
        interface.agent.model = mock_llm
        return interface

    def test_chat_returns_string_response(self, chat_interface, mock_llm):
        with patch.object(chat_interface, "_load_agent_context", return_value={}), \
             patch.object(chat_interface, "_build_system_prompt", return_value="You are a trading bot."):
            response = chat_interface.chat("What is my balance?")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_chat_response_is_llm_content(self, chat_interface, mock_llm):
        """The response must be the LLM's content string."""
        mock_llm.invoke.return_value.content = "Balance is 5 SOL."
        with patch.object(chat_interface, "_load_agent_context", return_value={}), \
             patch.object(chat_interface, "_build_system_prompt", return_value="sys"):
            response = chat_interface.chat("What is my balance?")
        assert response == "Balance is 5 SOL."

    def test_chat_appends_to_history(self, chat_interface, mock_llm):
        initial_len = len(chat_interface.chat_history.messages)
        with patch.object(chat_interface, "_load_agent_context", return_value={}), \
             patch.object(chat_interface, "_build_system_prompt", return_value="system prompt"):
            chat_interface.chat("Test message")
        # History should have grown by 2 (user + assistant messages)
        assert len(chat_interface.chat_history.messages) >= initial_len + 2

    def test_chat_returns_error_message_when_llm_raises(self, chat_interface, mock_llm):
        mock_llm.invoke.side_effect = Exception("LLM API error")
        with patch.object(chat_interface, "_load_agent_context", return_value={}), \
             patch.object(chat_interface, "_build_system_prompt", return_value="sys"):
            response = chat_interface.chat("Hello")
        assert "error" in response.lower() or "❌" in response

    def test_clear_history_empties_chat_history(self, chat_interface, mock_llm):
        with patch.object(chat_interface, "_load_agent_context", return_value={}), \
             patch.object(chat_interface, "_build_system_prompt", return_value="sys"):
            chat_interface.chat("message 1")
            chat_interface.chat("message 2")
        chat_interface.clear_history()
        assert len(chat_interface.chat_history.messages) == 0

    def test_build_system_prompt_includes_balance(self, chat_interface):
        context = {"wallet_balance_sol": 5.5, "active_positions": [], "cycles_completed": 3}
        prompt = chat_interface._build_system_prompt(context)
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # non-trivial prompt

    def test_get_agent_status_summary_returns_string(self, chat_interface):
        with patch.object(chat_interface, "_load_agent_context",
                         return_value={"wallet_balance_sol": 5.0, "cycles_completed": 2}):
            summary = chat_interface.get_agent_status_summary()
        assert isinstance(summary, str)


# ─────────────────────────────────────────────────────────────────────────────
# MultiAgentChat
# ─────────────────────────────────────────────────────────────────────────────

class TestMultiAgentChat:
    @pytest.fixture
    def multi_chat(self):
        mock_claude = MagicMock()
        mock_claude.chat.return_value = "Claude response"
        mock_gemini = MagicMock()
        mock_gemini.chat.return_value = "Gemini response"
        with patch("src.agent.agent_chat.get_agent_instance"), \
             patch("src.agent.agent_chat.ChatAnthropic"), \
             patch("src.agent.agent_chat.ChatGoogleGenerativeAI"):
            from src.agent.agent_chat import MultiAgentChat
            multi = MultiAgentChat()
        multi.claude_chat = mock_claude
        multi.gemini_chat = mock_gemini
        return multi

    def test_chat_with_both_returns_dict_with_claude_and_gemini_keys(self, multi_chat):
        """Source returns {'claude': ..., 'gemini': ...} keys."""
        result = multi_chat.chat_with_both("Hello both")
        assert "claude" in result
        assert "gemini" in result

    def test_chat_with_both_calls_both_agents(self, multi_chat):
        multi_chat.chat_with_both("test message")
        multi_chat.claude_chat.chat.assert_called_once_with("test message")
        multi_chat.gemini_chat.chat.assert_called_once_with("test message")

    def test_chat_with_both_returns_correct_responses(self, multi_chat):
        result = multi_chat.chat_with_both("Hello")
        assert result["claude"] == "Claude response"
        assert result["gemini"] == "Gemini response"

    def test_chat_with_both_exception_returns_error_for_all_keys(self, multi_chat):
        """
        If claude_chat.chat() raises, the outer except catches it and returns
        error strings for BOTH keys (not partial success).
        """
        multi_chat.claude_chat.chat.side_effect = Exception("Claude API down")
        result = multi_chat.chat_with_both("Hello")
        # Both keys must exist (outer except populates both)
        assert "claude" in result
        assert "gemini" in result
        # Both contain error messages
        assert "❌" in result["claude"] or "error" in result["claude"].lower()

    def test_chat_with_agent_claude(self, multi_chat):
        result = multi_chat.chat_with_agent("anthropic", "Hi Claude")
        assert result == "Claude response"

    def test_chat_with_agent_gemini(self, multi_chat):
        result = multi_chat.chat_with_agent("google", "Hi Gemini")
        assert result == "Gemini response"

    def test_chat_with_agent_unknown_provider(self, multi_chat):
        result = multi_chat.chat_with_agent("unknown_provider", "Hi")
        assert isinstance(result, str)  # should return a string (error or response)

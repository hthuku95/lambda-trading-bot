# ui/components/agent_chat.py
"""
Agent Chat UI Component
Provides chat interface for interacting with trading agents

Based on Streamlit best practices 2024-2025:
- st.chat_message for message display
- st.chat_input for user input
- Session state for message persistence
- Mobile-friendly layout
"""
import streamlit as st
import logging
from typing import Dict, Any, List

from src.agent import (
    get_agent_chat,
    get_multi_agent_chat,
    chat_with_claude,
    chat_with_gemini,
    chat_with_both_agents
)

logger = logging.getLogger("trading_agent.ui.chat")


def initialize_chat_session_state():
    """Initialize session state for chat interface"""
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []

    if 'chat_mode' not in st.session_state:
        st.session_state.chat_mode = 'single'  # 'single' or 'both'

    if 'selected_chat_agent' not in st.session_state:
        st.session_state.selected_chat_agent = 'anthropic'

    if 'chat_history_loaded' not in st.session_state:
        st.session_state.chat_history_loaded = False


def load_chat_history_from_file():
    """Load chat history from file on first load"""
    if not st.session_state.chat_history_loaded:
        try:
            # Load history for selected agent
            selected_agent = st.session_state.get('selected_chat_agent', 'anthropic')
            chat_interface = get_agent_chat(selected_agent)
            chat_interface.load_history_from_file()

            # Convert to session state format
            st.session_state.chat_messages = []
            for msg in chat_interface.chat_history.messages:
                if hasattr(msg, '__class__'):
                    role = 'user' if 'Human' in msg.__class__.__name__ else 'assistant'
                    st.session_state.chat_messages.append({
                        'role': role,
                        'content': msg.content,
                        'agent': selected_agent
                    })

            st.session_state.chat_history_loaded = True
            logger.info(f"Loaded {len(st.session_state.chat_messages)} messages from history")
        except Exception as e:
            logger.error(f"Error loading chat history: {e}")
            st.session_state.chat_history_loaded = True  # Mark as loaded to avoid retry


def render_chat_mode_selector():
    """Render chat mode selector"""
    col1, col2 = st.columns(2)

    with col1:
        chat_mode = st.radio(
            "Chat Mode",
            options=['single', 'both'],
            format_func=lambda x: "Single Agent" if x == 'single' else "Both Agents",
            horizontal=True,
            key='chat_mode'
        )

    with col2:
        if st.session_state.chat_mode == 'single':
            selected_agent = st.selectbox(
                "Select Agent",
                options=['anthropic', 'google'],
                format_func=lambda x: "🔵 Claude" if x == 'anthropic' else "🟢 Gemini",
                key='selected_chat_agent'
            )


def render_chat_controls():
    """Render chat control buttons"""
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_messages = []

            # Clear backend history
            try:
                if st.session_state.chat_mode == 'single':
                    chat = get_agent_chat(st.session_state.selected_chat_agent)
                    chat.clear_history()
                else:
                    multi_chat = get_multi_agent_chat()
                    multi_chat.claude_chat.clear_history()
                    multi_chat.gemini_chat.clear_history()

                st.success("Chat cleared!")
            except Exception as e:
                st.error(f"Error clearing chat: {e}")

            st.rerun()

    with col2:
        if st.button("💾 Save History", use_container_width=True):
            try:
                if st.session_state.chat_mode == 'single':
                    chat = get_agent_chat(st.session_state.selected_chat_agent)
                    chat.save_history_to_file()
                else:
                    multi_chat = get_multi_agent_chat()
                    multi_chat.claude_chat.save_history_to_file()
                    multi_chat.gemini_chat.save_history_to_file()

                st.success("History saved!")
            except Exception as e:
                st.error(f"Error saving: {e}")

    with col3:
        if st.button("📂 Load History", use_container_width=True):
            st.session_state.chat_history_loaded = False
            load_chat_history_from_file()
            st.success("History loaded!")
            st.rerun()


def render_agent_status_header():
    """Render agent status in chat header"""
    try:
        if st.session_state.chat_mode == 'single':
            chat = get_agent_chat(st.session_state.selected_chat_agent)
            status = chat.get_agent_status_summary()
            st.info(status)
        else:
            col1, col2 = st.columns(2)
            with col1:
                claude_chat = get_agent_chat('anthropic')
                st.info(claude_chat.get_agent_status_summary())
            with col2:
                gemini_chat = get_agent_chat('google')
                st.info(gemini_chat.get_agent_status_summary())
    except Exception as e:
        st.warning(f"⚠️ Status unavailable: {e}")


def render_chat_messages():
    """Render chat message history"""
    for message in st.session_state.chat_messages:
        role = message['role']
        content = message['content']
        agent = message.get('agent', 'unknown')

        # Determine avatar
        if role == 'user':
            avatar = "👤"
        else:
            if agent == 'anthropic':
                avatar = "🔵"  # Claude
            elif agent == 'google':
                avatar = "🟢"  # Gemini
            else:
                avatar = "🤖"

        with st.chat_message(role, avatar=avatar):
            st.markdown(content)


def handle_chat_input(user_input: str):
    """Handle user chat input"""
    if not user_input.strip():
        return

    # Add user message to session state
    st.session_state.chat_messages.append({
        'role': 'user',
        'content': user_input,
        'agent': 'user'
    })

    try:
        if st.session_state.chat_mode == 'single':
            # Single agent chat
            selected_agent = st.session_state.selected_chat_agent

            with st.spinner(f"{'🔵 Claude' if selected_agent == 'anthropic' else '🟢 Gemini'} is thinking..."):
                if selected_agent == 'anthropic':
                    response = chat_with_claude(user_input)
                else:
                    response = chat_with_gemini(user_input)

            # Add response to session state
            st.session_state.chat_messages.append({
                'role': 'assistant',
                'content': response,
                'agent': selected_agent
            })

        else:
            # Both agents chat
            with st.spinner("Both agents are thinking..."):
                responses = chat_with_both_agents(user_input)

            # Add both responses
            st.session_state.chat_messages.append({
                'role': 'assistant',
                'content': f"**🔵 Claude:**\n\n{responses['claude']}",
                'agent': 'anthropic'
            })

            st.session_state.chat_messages.append({
                'role': 'assistant',
                'content': f"**🟢 Gemini:**\n\n{responses['gemini']}",
                'agent': 'google'
            })

    except Exception as e:
        logger.error(f"Error in chat: {e}")
        st.session_state.chat_messages.append({
            'role': 'assistant',
            'content': f"❌ Error: {str(e)}",
            'agent': 'error'
        })


def render_agent_chat_interface():
    """Render complete agent chat interface"""
    # Initialize session state
    initialize_chat_session_state()

    # Load history on first load
    if not st.session_state.chat_history_loaded:
        load_chat_history_from_file()

    # Header
    st.header("💬 Chat with AI Trading Agents")
    st.caption("Ask about trading decisions, strategies, and market insights")

    # Mode selector
    render_chat_mode_selector()

    # Agent status
    render_agent_status_header()

    # Control buttons
    render_chat_controls()

    st.markdown("---")

    # Chat container (for messages)
    chat_container = st.container()

    with chat_container:
        # Render message history
        render_chat_messages()

    # Chat input (fixed at bottom)
    user_input = st.chat_input(
        "Ask your agent anything about trading strategies, decisions, or market conditions..."
    )

    # Handle input
    if user_input:
        handle_chat_input(user_input)
        st.rerun()


def render_quick_questions():
    """Render quick question buttons"""
    st.subheader("💡 Quick Questions")

    quick_questions = [
        "Why did you make that last trade?",
        "What's your current trading strategy?",
        "Explain your recent performance",
        "What tokens are you watching?",
        "How do you manage risk?",
        "What market conditions favor your strategy?"
    ]

    cols = st.columns(2)

    for i, question in enumerate(quick_questions):
        with cols[i % 2]:
            if st.button(question, use_container_width=True):
                handle_chat_input(question)
                st.rerun()


def render_chat_tab():
    """Render complete chat tab (for dashboard integration)"""
    render_agent_chat_interface()

    st.markdown("---")

    render_quick_questions()

    # Chat tips
    with st.expander("💡 Chat Tips"):
        st.markdown("""
        **What you can ask:**
        - ✅ "Why did you buy/sell [token]?"
        - ✅ "What's your current strategy?"
        - ✅ "Explain your risk management"
        - ✅ "Compare yourself to the other agent"
        - ✅ "What would you do in [scenario]?"

        **Features:**
        - 💾 Chat history is auto-saved every 10 messages
        - 🔄 History persists across sessions
        - 🤖 Agents have full context of their trading activity
        - 🔍 Both agents mode lets you compare responses
        """)

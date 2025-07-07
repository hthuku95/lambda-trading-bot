# ui/components/insights.py
"""
Agent insights tab component for the Streamlit dashboard
"""
import streamlit as st

def render_agent_reasoning(agent_state):
    """Render the latest agent reasoning"""
    if agent_state and agent_state.get('agent_reasoning'):
        st.subheader("Latest Agent Decision")
        
        # Extract key sections from the reasoning
        reasoning = agent_state['agent_reasoning']
        
        # Try to parse structured sections
        sections = ["MARKET ANALYSIS:", "POSITION MANAGEMENT:", "NEW OPPORTUNITIES:", "EXECUTION PLAN:"]
        parsed_sections = {}
        
        for i, section in enumerate(sections):
            start_idx = reasoning.find(section)
            if start_idx != -1:
                if i < len(sections) - 1:
                    end_idx = reasoning.find(sections[i + 1])
                    if end_idx == -1:
                        end_idx = len(reasoning)
                else:
                    end_idx = len(reasoning)
                
                content = reasoning[start_idx + len(section):end_idx].strip()
                parsed_sections[section[:-1]] = content
        
        # Display each section in tabs
        if parsed_sections:
            reasoning_tabs = st.tabs(list(parsed_sections.keys()))
            for tab, (section, content) in zip(reasoning_tabs, parsed_sections.items()):
                with tab:
                    st.write(content)
        else:
            # Fallback to showing full reasoning
            st.text_area("Agent Reasoning", value=reasoning, height=300)

def render_market_conditions(agent_state):
    """Render market conditions analysis"""
    if agent_state and agent_state.get('market_conditions'):
        st.subheader("📊 Market Analysis")
        market = agent_state['market_conditions']
        
        # Market sentiment indicators
        col1, col2 = st.columns(2)
        
        with col1:
            sentiment = market.get('overall_sentiment', 'Unknown')
            sentiment_emoji = {
                'bullish': '🚀',
                'slightly bullish': '📈',
                'neutral': '➡️',
                'slightly bearish': '📉',
                'bearish': '🐻'
            }.get(sentiment, '❓')
            
            st.metric("Market Sentiment", f"{sentiment_emoji} {sentiment.title()}")
            
            volatility = market.get('market_volatility', 'Unknown')
            volatility_emoji = {
                'high': '🌋',
                'medium': '🌊',
                'low': '🏞️'
            }.get(volatility, '❓')
            
            st.metric("Volatility", f"{volatility_emoji} {volatility.title()}")
            
            sol_change = market.get('sol_price_change_24h', 0)
            sol_price = market.get('sol_price_usd', 0)
            st.metric("SOL Price", f"${sol_price:.2f}", delta=f"{sol_change:+.1f}%")
        
        with col2:
            bull_market = market.get('bull_market', False)
            st.metric("Bull Market", "✅ Yes" if bull_market else "❌ No")
            
            high_vol = market.get('high_volatility', False)
            st.metric("High Volatility", "🔥 Yes" if high_vol else "❄️ No")
            
            trending_tokens = market.get('trending_tokens', [])
            if trending_tokens:
                st.write("**Trending Tokens:**")
                st.write(", ".join(trending_tokens[:5]))
            else:
                st.write("**Trending Tokens:** None detected")

def render_trading_decisions(agent_state):
    """Render latest trading decisions"""
    if agent_state and agent_state.get('trading_decisions'):
        st.subheader("⚡ Latest Trading Decisions")
        decisions = agent_state['trading_decisions']
        
        for decision in decisions:
            action = decision.get('action', 'unknown')
            
            if action == 'exit_position':
                st.error(f"🔴 Exit Position: {decision.get('token_symbol', 'Unknown')}")
            elif action == 'enter_position':
                allocation = decision.get('allocation_percentage', 0)
                st.success(f"🟢 Enter Position: {decision.get('token_symbol', 'Unknown')} ({allocation}%)")
            elif action == 'take_partial_profits':
                percentage = decision.get('percentage', 0)
                st.warning(f"🟡 Take Partial Profits: {decision.get('token_symbol', 'Unknown')} ({percentage}%)")
            elif action == 'hold':
                st.info("🔵 Hold - No action recommended")
            
            st.caption(f"Reason: {decision.get('reason', 'No reason provided')}")

def render_insights_tab(data):
    """Render the complete agent insights tab"""
    st.header("🧠 Agent Insights")
    
    agent_state = data['agent_state']
    
    render_agent_reasoning(agent_state)
    render_market_conditions(agent_state)
    render_trading_decisions(agent_state)
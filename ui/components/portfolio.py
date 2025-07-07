# ui/components/portfolio.py
"""
Portfolio tab component for the Streamlit dashboard
Updated for RugCheck + TweetScout integration (No BitQuery)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from ui.components.metrics import get_performance_color, format_currency
from datetime import datetime

def render_portfolio_allocation(positions):
    """Render portfolio allocation chart"""
    if len(positions) > 1:
        st.subheader("📊 Position Allocation")
        
        # Create pie chart of position values
        labels = [pos['token_symbol'] for pos in positions]
        values = [pos['current_value_usd'] for pos in positions]
        
        # Color code by enrichment status
        colors = []
        for pos in positions:
            if pos.get('enriched', False):
                colors.append('#00CC88')  # Green for enriched
            elif pos.get('safety_score', 0) > 0:
                colors.append('#FFB366')  # Orange for partial
            else:
                colors.append('#FF6B6B')  # Red for basic
        
        fig = px.pie(
            values=values, 
            names=labels, 
            title="Current Position Distribution",
            color_discrete_sequence=colors
        )
        
        # Add legend for enrichment status
        fig.add_annotation(
            text="🟢 Full Analysis | 🟡 Partial | 🔴 Basic",
            showarrow=False,
            x=0, y=-0.15,
            xref="paper", yref="paper",
            xanchor="left", yanchor="bottom",
            font=dict(size=10)
        )
        
        st.plotly_chart(fig, use_container_width=True)

def render_active_positions(positions):
    """Render detailed active positions display with RugCheck + TweetScout enhancements"""
    st.subheader("📋 Active Positions")
    
    if not positions:
        st.info("No active positions")
        return
    
    for i, position in enumerate(positions):
        profit_pct = position.get('current_profit_percentage', 0)
        enriched = position.get('enriched', False)
        safety_score = position.get('safety_score', 0)
        social_activity = position.get('social_activity', 0)
        
        # Get color for profit/loss display
        color = get_performance_color(profit_pct)
        
        # Enhanced title with enrichment indicator
        title_parts = [f"{position['token_symbol']} - {profit_pct:+.1f}% P&L"]
        
        if enriched:
            title_parts.append(f"🔬 Full Analysis (Safety: {safety_score}/100)")
        elif safety_score > 0:
            title_parts.append(f"🛡️ Safety Only ({safety_score}/100)")
        elif social_activity > 0:
            title_parts.append(f"📱 Social Only ({social_activity}/100)")
        else:
            title_parts.append("📊 Basic Analysis")
        
        title = " | ".join(title_parts)
        
        with st.expander(title, expanded=True):
            # Basic position info
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.write("**Position Details:**")
                st.write(f"• Entry Price: ${position.get('entry_price_usd', 0):.6f}")
                st.write(f"• Current Price: ${position.get('current_price_usd', 0):.6f}")
                st.write(f"• Position Size: {format_currency(position.get('position_size_sol', 0))} SOL")
                st.write(f"• Current Value: ${position.get('current_value_usd', 0):.2f}")
            
            with col2:
                st.write("**Performance:**")
                st.write(f"• P&L: {profit_pct:+.2f}%")
                st.write(f"• Unrealized P&L: ${position.get('unrealized_pnl_usd', 0):+.2f}")
                hold_time = position.get('hold_time_hours', 0)
                st.write(f"• Hold Time: {hold_time:.1f}h")
                
                # Risk metrics
                stop_loss = position.get('stop_loss_percentage', 0)
                take_profit = position.get('take_profit_percentage', 0)
                if stop_loss > 0:
                    st.write(f"• Stop Loss: -{stop_loss:.1f}%")
                if take_profit > 0:
                    st.write(f"• Take Profit: +{take_profit:.1f}%")
            
            with col3:
                # RugCheck safety analysis
                st.write("**🛡️ Safety Analysis:**")
                if safety_score > 0:
                    # Color code safety score
                    if safety_score >= 80:
                        safety_color = "🟢"
                    elif safety_score >= 60:
                        safety_color = "🟡"
                    else:
                        safety_color = "🔴"
                    
                    st.write(f"• Safety Score: {safety_color} {safety_score}/100")
                    
                    # Show specific safety indicators
                    if position.get('contract_verified', False):
                        st.write("• ✅ Contract Verified")
                    else:
                        st.write("• ❌ Contract Not Verified")
                    
                    if position.get('liquidity_locked', False):
                        st.write("• ✅ Liquidity Locked")
                    else:
                        st.write("• ⚠️ Liquidity Not Locked")
                    
                    if position.get('rug_pull_risk', False):
                        st.write("• 🔴 Rug Pull Risk Detected")
                    
                    if position.get('honeypot_risk', False):
                        st.write("• 🔴 Honeypot Risk Detected")
                        
                else:
                    st.write("• No safety data available")
                    st.write("• ⚠️ Trade with caution")
            
            with col4:
                # TweetScout social analysis
                st.write("**📱 Social Analysis:**")
                if social_activity > 0:
                    # Color code social activity
                    if social_activity >= 70:
                        social_color = "🔥"
                    elif social_activity >= 50:
                        social_color = "🟡"
                    else:
                        social_color = "🔵"
                    
                    st.write(f"• Social Activity: {social_color} {social_activity}/100")
                    
                    viral_score = position.get('viral_score', 0)
                    if viral_score > 0:
                        st.write(f"• Viral Potential: {viral_score}/100")
                    
                    mentions_24h = position.get('social_mentions_24h', 0)
                    if mentions_24h > 0:
                        st.write(f"• Mentions (24h): {mentions_24h}")
                    
                    sentiment = position.get('sentiment_score', 50)
                    if sentiment > 60:
                        st.write(f"• Sentiment: 😊 Positive ({sentiment}/100)")
                    elif sentiment < 40:
                        st.write(f"• Sentiment: 😞 Negative ({sentiment}/100)")
                    else:
                        st.write(f"• Sentiment: 😐 Neutral ({sentiment}/100)")
                        
                    if position.get('trending_potential', False):
                        st.write("• 🚀 Trending Potential Detected")
                        
                else:
                    st.write("• No social data available")
                    st.write("• 📊 Limited social insights")
            
            # Enhanced analysis summary
            if enriched:
                st.write("---")
                st.write("**🔬 Enhanced Analysis Summary:**")
                
                recommendation = position.get('recommendation', 'HOLD')
                overall_score = position.get('overall_score', 0)
                risk_level = position.get('risk_level', 'medium')
                
                analysis_col1, analysis_col2, analysis_col3 = st.columns(3)
                
                with analysis_col1:
                    # Recommendation with color coding
                    if "BUY" in recommendation:
                        rec_color = "🟢"
                    elif "SELL" in recommendation:
                        rec_color = "🔴"
                    elif "AVOID" in recommendation:
                        rec_color = "⛔"
                    else:
                        rec_color = "🟡"
                    
                    st.write(f"• Recommendation: {rec_color} {recommendation}")
                
                with analysis_col2:
                    st.write(f"• Overall Score: {overall_score}/100")
                
                with analysis_col3:
                    risk_colors = {
                        'low': '🟢',
                        'medium': '🟡', 
                        'high': '🔴',
                        'critical': '⛔'
                    }
                    risk_color = risk_colors.get(risk_level, '🟡')
                    st.write(f"• Risk Level: {risk_color} {risk_level.title()}")
                
                # Key insights
                key_strengths = position.get('key_strengths', [])
                key_risks = position.get('key_risks', [])
                
                if key_strengths or key_risks:
                    insight_col1, insight_col2 = st.columns(2)
                    
                    with insight_col1:
                        if key_strengths:
                            st.write("**✅ Key Strengths:**")
                            for strength in key_strengths[:3]:  # Show top 3
                                st.write(f"• {strength}")
                    
                    with insight_col2:
                        if key_risks:
                            st.write("**⚠️ Key Risks:**")
                            for risk in key_risks[:3]:  # Show top 3
                                st.write(f"• {risk}")

def render_portfolio_performance_chart(positions):
    """Render portfolio performance over time"""
    if not positions:
        return
        
    st.subheader("📈 Performance Tracking")
    
    # Create a simple performance visualization
    symbols = [pos['token_symbol'] for pos in positions]
    profits = [pos.get('current_profit_percentage', 0) for pos in positions]
    enrichment_status = [
        'Full Analysis' if pos.get('enriched', False) 
        else 'Partial Analysis' if pos.get('safety_score', 0) > 0 or pos.get('social_activity', 0) > 0
        else 'Basic Analysis' 
        for pos in positions
    ]
    
    # Create bar chart
    fig = go.Figure()
    
    # Color by enrichment status
    colors = []
    for status in enrichment_status:
        if status == 'Full Analysis':
            colors.append('#00CC88')
        elif status == 'Partial Analysis':
            colors.append('#FFB366')
        else:
            colors.append('#FF6B6B')
    
    fig.add_trace(go.Bar(
        x=symbols,
        y=profits,
        marker_color=colors,
        text=[f"{p:+.1f}%" for p in profits],
        textposition='auto',
        hovertemplate='<b>%{x}</b><br>P&L: %{y:+.2f}%<br>Status: %{customdata}<extra></extra>',
        customdata=enrichment_status
    ))
    
    fig.update_layout(
        title="Position Performance by Analysis Quality",
        xaxis_title="Token",
        yaxis_title="Profit/Loss (%)",
        showlegend=False,
        height=400
    )
    
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Add legend
    st.markdown("""
    **Analysis Quality Legend:**
    - 🟢 **Full Analysis**: RugCheck + TweetScout data available
    - 🟡 **Partial Analysis**: Either RugCheck or TweetScout data available  
    - 🔴 **Basic Analysis**: DexScreener data only
    """)

def render_portfolio_tab(data):
    """Render the complete portfolio tab"""
    agent_state = data.get('agent_state')
    
    if not agent_state:
        st.error("No agent state available")
        return
    
    active_positions = agent_state.get('active_positions', [])
    portfolio_metrics = agent_state.get('portfolio_metrics', {})
    
    if not active_positions:
        st.info("📭 No active positions. The agent is analyzing opportunities...")
        
        # Show discovery status
        validated_tokens = agent_state.get('validated_tokens', [])
        if validated_tokens:
            st.write(f"🔍 Currently analyzing {len(validated_tokens)} potential opportunities")
            
            # Show top 3 candidates
            st.write("**🎯 Top Candidates:**")
            for token in validated_tokens[:3]:
                enriched_status = "🔬" if token.get('enriched', False) else "📊"
                safety = token.get('safety_score', 0)
                social = token.get('social_activity', 0)
                st.write(f"• {enriched_status} {token.get('symbol', 'Unknown')} - Safety: {safety}/100, Social: {social}/100")
        
        return
    
    # Portfolio summary metrics
    st.subheader("📊 Portfolio Summary")
    
    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
    
    with summary_col1:
        total_value = sum(pos.get('current_value_usd', 0) for pos in active_positions)
        st.metric("Total Portfolio Value", f"${total_value:.2f}")
    
    with summary_col2:
        total_unrealized_pnl = sum(pos.get('unrealized_pnl_usd', 0) for pos in active_positions)
        st.metric("Unrealized P&L", f"${total_unrealized_pnl:+.2f}")
    
    with summary_col3:
        enriched_count = sum(1 for pos in active_positions if pos.get('enriched', False))
        enrichment_pct = (enriched_count / len(active_positions)) * 100 if active_positions else 0
        st.metric("Enrichment Coverage", f"{enrichment_pct:.0f}%", delta=f"{enriched_count}/{len(active_positions)}")
    
    with summary_col4:
        avg_safety = 0
        safety_positions = [pos for pos in active_positions if pos.get('safety_score', 0) > 0]
        if safety_positions:
            avg_safety = sum(pos.get('safety_score', 0) for pos in safety_positions) / len(safety_positions)
        st.metric("Avg Safety Score", f"{avg_safety:.1f}/100")
    
    # Render different portfolio views
    render_portfolio_allocation(active_positions)
    render_portfolio_performance_chart(active_positions)
    render_active_positions(active_positions)
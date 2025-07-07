# ui/components/tokens.py
"""
Updated Token Analysis Tab - Using RugCheck + TweetScout (No BitQuery)
"""
import streamlit as st
import pandas as pd

def render_token_summary_table(tokens):
    """Render token summary table with new enrichment data"""
    if tokens:
        token_summary = []
        for token in tokens[:10]:  # Show top 10
            # Use new enrichment fields
            safety_score = token.get('safety_score', 0)
            social_activity = token.get('social_activity', 0)
            recommendation = token.get('recommendation', 'UNKNOWN')
            risk_level = token.get('risk_level', 'unknown')
            
            token_summary.append({
                'Symbol': token.get('symbol', 'Unknown'),
                'Price': f"${token.get('price_usd', 0):.6f}",
                'Age (hrs)': f"{token.get('age_hours', 0):.1f}",
                'Liquidity': f"${token.get('liquidity_usd', 0):,.0f}",
                'Safety': f"{safety_score:.0f}/100",
                'Social': f"{social_activity:.0f}/100",
                'Risk Level': risk_level.title(),
                'Recommendation': recommendation,
                '24h Change': f"{token.get('price_change_24h', 0):+.1f}%"
            })
        
        df = pd.DataFrame(token_summary)
        st.dataframe(df, use_container_width=True)

def render_detailed_token_analysis(tokens):
    """Render detailed token analysis with RugCheck + TweetScout enhancements"""
    for token in tokens[:5]:  # Show detailed view for top 5
        safety_score = token.get('safety_score', 0)
        enriched = token.get('enriched', False)
        recommendation = token.get('recommendation', 'UNKNOWN')
        risk_level = token.get('risk_level', 'unknown')
        
        # Determine safety color
        if safety_score >= 70:
            safety_color = "green"
        elif safety_score >= 40:
            safety_color = "orange"
        else:
            safety_color = "red"
        
        # Enhanced title with enrichment indicator
        title = f"{token['symbol']} - {recommendation}"
        if enriched:
            data_sources = token.get('data_sources_used', {})
            sources = []
            if data_sources.get('rugcheck_used'):
                sources.append("RugCheck")
            if data_sources.get('tweetscout_used'):
                sources.append("TweetScout")
            title += f" ({'+'.join(sources)}) 🔬"
        
        with st.expander(title, expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Safety Score", f"{safety_score:.0f}/100")
                st.markdown(f"<div style='color: {safety_color};'>Risk: {risk_level.title()}</div>", 
                           unsafe_allow_html=True)
            
            with col2:
                social_score = token.get('social_activity', 0)
                viral_score = token.get('viral_score', 0)
                st.metric("Social Activity", f"{social_score:.0f}/100")
                st.metric("Viral Score", f"{viral_score:.0f}/100")
            
            with col3:
                whale_buy = token.get('whale_buy_pressure', 0)
                whale_sell = token.get('whale_sell_pressure', 0)
                st.metric("Whale Buy Pressure", f"{whale_buy:.0f}%")
                st.metric("Whale Sell Pressure", f"{whale_sell:.0f}%")
            
            with col4:
                market_health = token.get('market_health_score', 0)
                overall_score = token.get('overall_score', 0)
                st.metric("Market Health", f"{market_health:.0f}/100")
                st.metric("Overall Score", f"{overall_score:.0f}/100")
            
            # Risk factors section
            if enriched:
                risk_factors = token.get('risk_factors', [])
                if risk_factors:
                    st.write("**Risk Factors:**")
                    for risk in risk_factors[:3]:  # Top 3 risks
                        risk_type = risk.get('type', 'Unknown')
                        risk_level_detail = risk.get('level', 'info')
                        if risk_level_detail in ['danger', 'critical']:
                            st.error(f"🔴 {risk_type}")
                        elif risk_level_detail == 'warning':
                            st.warning(f"🟡 {risk_type}")
                        else:
                            st.info(f"ℹ️ {risk_type}")

def render_tokens_tab(data):
    """Render the tokens analysis tab with RugCheck + TweetScout data"""
    st.header("🔍 Token Analysis")
    
    # Get validated tokens
    agent_state = data.get('agent_state', {})
    tokens = agent_state.get('validated_tokens', [])
    
    if not tokens:
        st.info("No tokens discovered yet. The agent will discover and analyze tokens automatically.")
        return
    
    # Filter controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        min_safety_score = st.slider("Minimum Safety Score", 0, 100, 0)
    
    with col2:
        risk_level_filter = st.selectbox(
            "Risk Level Filter", 
            ["All", "Low", "Medium", "High", "Critical"]
        )
    
    with col3:
        enriched_only = st.checkbox("Show Enriched Only", False)
    
    # Apply filters
    filtered_tokens = tokens
    
    if min_safety_score > 0:
        filtered_tokens = [t for t in filtered_tokens if t.get('safety_score', 0) >= min_safety_score]
    
    if risk_level_filter != "All":
        filtered_tokens = [t for t in filtered_tokens if t.get('risk_level', '').lower() == risk_level_filter.lower()]
    
    if enriched_only:
        filtered_tokens = [t for t in filtered_tokens if t.get('enriched', False)]
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Tokens", len(tokens))
    
    with col2:
        enriched_count = len([t for t in tokens if t.get('enriched', False)])
        st.metric("Enriched Tokens", enriched_count)
    
    with col3:
        if enriched_count > 0:
            avg_safety = sum(t.get('safety_score', 0) for t in tokens if t.get('enriched', False)) / enriched_count
            st.metric("Avg Safety Score", f"{avg_safety:.1f}/100")
        else:
            st.metric("Avg Safety Score", "N/A")
    
    with col4:
        buy_recommendations = len([t for t in tokens if 'BUY' in t.get('recommendation', '')])
        st.metric("Buy Recommendations", buy_recommendations)
    
    # Display tokens
    if filtered_tokens:
        st.subheader("Token Summary")
        render_token_summary_table(filtered_tokens)
        
        st.subheader("Detailed Analysis")
        render_detailed_token_analysis(filtered_tokens)
    else:
        st.warning("No tokens match the selected filters.")

# ui/components/portfolio.py
"""
Updated Portfolio Tab - Using RugCheck + TweetScout (No BitQuery)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from ui.components.metrics import get_performance_color, format_currency

def render_portfolio_allocation(positions):
    """Render portfolio allocation chart"""
    if len(positions) > 1:
        st.subheader("Position Allocation")
        
        # Create pie chart of position values
        labels = [pos['token_symbol'] for pos in positions]
        values = [pos['current_value_usd'] for pos in positions]
        
        fig = px.pie(values=values, names=labels, title="Current Position Distribution")
        st.plotly_chart(fig, use_container_width=True)

def render_active_positions(positions):
    """Render detailed active positions display with RugCheck + TweetScout enhancements"""
    st.subheader("Active Positions")
    for i, position in enumerate(positions):
        profit_pct = position.get('current_profit_percentage', 0)
        enriched = position.get('enriched', False)
        
        # Get color for profit/loss display
        color = get_performance_color(profit_pct)
        
        # Enhanced title with enrichment indicator
        title = f"{position['token_symbol']} - {profit_pct:+.1f}% P&L"
        if enriched:
            safety_score = position.get('entry_safety_score', 0)
            recommendation = position.get('entry_recommendation', 'UNKNOWN')
            title += f" (Safety: {safety_score:.0f}/100, {recommendation}) 🔬"
        
        with st.expander(title, expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.write("**Position Details**")
                st.write(f"Amount: {position['amount']:.6f} {position['token_symbol']}")
                st.write(f"Entry Price: ${position['entry_price_usd']:.6f}")
                st.write(f"Current Price: ${position['current_price_usd']:.6f}")
                st.write(f"Value: {format_currency(position['current_value_usd'])}")
            
            with col2:
                st.write("**Performance**")
                st.markdown(f"P&L: <span style='color: {color}'>{profit_pct:+.1f}%</span>", 
                           unsafe_allow_html=True)
                profit_usd = position.get('unrealized_profit_usd', 0)
                st.write(f"Unrealized P&L: {format_currency(profit_usd)}")
                
                age_hours = position.get('position_age_hours', 0)
                st.write(f"Held for: {age_hours:.1f} hours")
            
            with col3:
                if enriched:
                    st.write("**Entry Analysis**")
                    entry_safety = position.get('entry_safety_score', 0)
                    entry_social = position.get('entry_social_activity', 0)
                    entry_viral = position.get('entry_viral_score', 0)
                    
                    st.write(f"Safety Score: {entry_safety:.0f}/100")
                    st.write(f"Social Activity: {entry_social:.0f}/100")
                    st.write(f"Viral Score: {entry_viral:.0f}/100")
                else:
                    st.write("**Basic Analysis**")
                    st.write("No enrichment data available")
            
            with col4:
                if enriched:
                    st.write("**Risk Assessment**")
                    entry_risk = position.get('entry_risk_level', 'unknown')
                    entry_recommendation = position.get('entry_recommendation', 'UNKNOWN')
                    
                    # Color code risk level
                    if entry_risk == 'low':
                        risk_color = 'green'
                    elif entry_risk == 'medium':
                        risk_color = 'orange'
                    else:
                        risk_color = 'red'
                    
                    st.markdown(f"Risk Level: <span style='color: {risk_color}'>{entry_risk.title()}</span>", 
                               unsafe_allow_html=True)
                    st.write(f"Entry Rec: {entry_recommendation}")
                    
                    # Risk factors
                    risk_factors = position.get('entry_risk_factors', [])
                    if risk_factors:
                        st.write("Key Risks:")
                        for risk in risk_factors[:2]:  # Top 2 risks
                            st.write(f"• {risk.get('type', 'Unknown')}")

def render_portfolio_tab(data):
    """Render the portfolio tab with RugCheck + TweetScout enhancements"""
    st.header("📈 Portfolio")
    
    agent_state = data.get('agent_state', {})
    positions = agent_state.get('active_positions', [])
    portfolio_metrics = agent_state.get('portfolio_metrics', {})
    
    if not positions:
        st.info("No active positions. The agent will create positions when good opportunities are found.")
        return
    
    # Portfolio overview metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_value = portfolio_metrics.get('total_value_sol', 0)
        st.metric("Total Value", f"{total_value:.6f} SOL")
    
    with col2:
        total_profit = portfolio_metrics.get('total_profit_sol', 0)
        profit_color = "normal" if total_profit >= 0 else "inverse"
        st.metric("Total P&L", f"{total_profit:+.6f} SOL", delta_color=profit_color)
    
    with col3:
        win_rate = portfolio_metrics.get('win_rate', 0)
        st.metric("Win Rate", f"{win_rate:.1%}")
    
    with col4:
        # Show enrichment coverage instead of BitQuery coverage
        enriched_positions = portfolio_metrics.get('enriched_positions_count', 0)
        total_positions = portfolio_metrics.get('active_positions_count', 0)
        coverage = (enriched_positions / max(total_positions, 1)) * 100
        st.metric("Enriched Positions", f"{enriched_positions}/{total_positions} ({coverage:.0f}%)")
    
    # Portfolio allocation chart
    render_portfolio_allocation(positions)
    
    # Detailed positions
    render_active_positions(positions)

# ui/components/insights.py
"""
Updated Agent Insights Tab - Using RugCheck + TweetScout (No BitQuery)
"""
import streamlit as st
import pandas as pd
import plotly.express as px

def render_enrichment_insights(data):
    """Render insights about token enrichment quality"""
    st.subheader("🔬 Token Enrichment Insights")
    
    agent_state = data.get('agent_state', {})
    tokens = agent_state.get('validated_tokens', [])
    
    if not tokens:
        st.info("No token data available for insights.")
        return
    
    # Enrichment quality breakdown
    enriched_tokens = [t for t in tokens if t.get('enriched', False)]
    
    if enriched_tokens:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            excellent_quality = len([t for t in enriched_tokens if t.get('enrichment_quality') == 'excellent'])
            st.metric("Excellent Quality", f"{excellent_quality}/{len(enriched_tokens)}")
        
        with col2:
            partial_quality = len([t for t in enriched_tokens if t.get('enrichment_quality') == 'partial'])
            st.metric("Partial Quality", f"{partial_quality}/{len(enriched_tokens)}")
        
        with col3:
            avg_overall_score = sum(t.get('overall_score', 0) for t in enriched_tokens) / len(enriched_tokens)
            st.metric("Avg Overall Score", f"{avg_overall_score:.1f}/100")
        
        # Data source usage
        st.write("**Data Source Usage:**")
        rugcheck_used = len([t for t in enriched_tokens if t.get('data_sources_used', {}).get('rugcheck_used')])
        tweetscout_used = len([t for t in enriched_tokens if t.get('data_sources_used', {}).get('tweetscout_used')])
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"RugCheck: {rugcheck_used}/{len(enriched_tokens)} tokens")
        with col2:
            st.write(f"TweetScout: {tweetscout_used}/{len(enriched_tokens)} tokens")

def render_safety_analysis_insights(data):
    """Render safety analysis insights from RugCheck"""
    st.subheader("🛡️ Safety Analysis Insights")
    
    agent_state = data.get('agent_state', {})
    tokens = agent_state.get('validated_tokens', [])
    enriched_tokens = [t for t in tokens if t.get('enriched', False)]
    
    if not enriched_tokens:
        st.info("No enriched tokens available for safety analysis.")
        return
    
    # Safety score distribution
    safety_scores = [t.get('safety_score', 0) for t in enriched_tokens]
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Safety score histogram
        fig = px.histogram(x=safety_scores, nbins=10, title="Safety Score Distribution")
        fig.update_xaxis(title="Safety Score")
        fig.update_yaxis(title="Number of Tokens")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Risk level breakdown
        risk_levels = [t.get('risk_level', 'unknown') for t in enriched_tokens]
        risk_counts = pd.Series(risk_levels).value_counts()
        
        fig = px.pie(values=risk_counts.values, names=risk_counts.index, title="Risk Level Distribution")
        st.plotly_chart(fig, use_container_width=True)
    
    # Common risk factors
    st.write("**Most Common Risk Factors:**")
    all_risk_factors = []
    for token in enriched_tokens:
        risk_factors = token.get('risk_factors', [])
        for risk in risk_factors:
            all_risk_factors.append(risk.get('type', 'Unknown'))
    
    if all_risk_factors:
        risk_factor_counts = pd.Series(all_risk_factors).value_counts().head(5)
        for risk_type, count in risk_factor_counts.items():
            st.write(f"• {risk_type}: {count} tokens")

def render_social_sentiment_insights(data):
    """Render social sentiment insights from TweetScout"""
    st.subheader("📱 Social Sentiment Insights")
    
    agent_state = data.get('agent_state', {})
    tokens = agent_state.get('validated_tokens', [])
    enriched_tokens = [t for t in tokens if t.get('enriched', False)]
    
    if not enriched_tokens:
        st.info("No enriched tokens available for social analysis.")
        return
    
    # Social activity metrics
    social_scores = [t.get('social_activity', 0) for t in enriched_tokens]
    viral_scores = [t.get('viral_score', 0) for t in enriched_tokens]
    
    col1, col2 = st.columns(2)
    
    with col1:
        avg_social = sum(social_scores) / len(social_scores) if social_scores else 0
        st.metric("Avg Social Activity", f"{avg_social:.1f}/100")
        
        high_social = len([s for s in social_scores if s > 60])
        st.metric("High Social Activity", f"{high_social}/{len(enriched_tokens)}")
    
    with col2:
        avg_viral = sum(viral_scores) / len(viral_scores) if viral_scores else 0
        st.metric("Avg Viral Score", f"{avg_viral:.1f}/100")
        
        viral_potential = len([t for t in enriched_tokens if t.get('trending_potential', False)])
        st.metric("Viral Potential", f"{viral_potential}/{len(enriched_tokens)}")
    
    # Social vs Viral correlation
    if social_scores and viral_scores:
        df = pd.DataFrame({
            'Social Activity': social_scores,
            'Viral Score': viral_scores,
            'Token': [t.get('symbol', 'Unknown') for t in enriched_tokens]
        })
        
        fig = px.scatter(df, x='Social Activity', y='Viral Score', hover_data=['Token'],
                        title="Social Activity vs Viral Potential")
        st.plotly_chart(fig, use_container_width=True)

def render_trading_recommendations_insights(data):
    """Render insights about trading recommendations"""
    st.subheader("💡 Trading Recommendations Insights")
    
    agent_state = data.get('agent_state', {})
    tokens = agent_state.get('validated_tokens', [])
    enriched_tokens = [t for t in tokens if t.get('enriched', False)]
    
    if not enriched_tokens:
        st.info("No enriched tokens available for recommendation analysis.")
        return
    
    # Recommendation distribution
    recommendations = [t.get('recommendation', 'UNKNOWN') for t in enriched_tokens]
    rec_counts = pd.Series(recommendations).value_counts()
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.pie(values=rec_counts.values, names=rec_counts.index, title="Recommendation Distribution")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Overall score vs recommendation
        overall_scores = [t.get('overall_score', 0) for t in enriched_tokens]
        df = pd.DataFrame({
            'Overall Score': overall_scores,
            'Recommendation': recommendations,
            'Token': [t.get('symbol', 'Unknown') for t in enriched_tokens]
        })
        
        fig = px.box(df, x='Recommendation', y='Overall Score', title="Score Distribution by Recommendation")
        st.plotly_chart(fig, use_container_width=True)

def render_insights_tab(data):
    """Render the agent insights tab with RugCheck + TweetScout data"""
    st.header("🧠 Agent Insights")
    
    # Token enrichment insights
    render_enrichment_insights(data)
    
    # Safety analysis insights
    render_safety_analysis_insights(data)
    
    # Social sentiment insights
    render_social_sentiment_insights(data)
    
    # Trading recommendations insights
    render_trading_recommendations_insights(data)

# Remove bitquery_status.py completely - it's no longer needed
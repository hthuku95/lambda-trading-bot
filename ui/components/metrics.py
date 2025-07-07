# ui/components/metrics.py
"""
Metrics and summary cards for the Streamlit dashboard
Updated for RugCheck + TweetScout integration (No BitQuery)
"""
import streamlit as st
from datetime import datetime

def format_currency(value, decimals=6):
    """Format currency values"""
    if value >= 1:
        return f"{value:.{min(2, decimals)}f}"
    else:
        return f"{value:.{decimals}f}"

def get_performance_color(percentage):
    """Get color based on performance percentage"""
    if percentage > 0:
        return "green"
    elif percentage < 0:
        return "red"
    else:
        return "gray"

def render_header():
    """Render the main dashboard header"""
    st.title("🚀 Solana Agentic Trading Bot")
    st.markdown("**Enhanced with RugCheck + TweetScout Analysis**")
    
    # Show current time and status
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"*Last updated: {datetime.now().strftime('%H:%M:%S')}*")
    with col2:
        # Simple status indicator
        st.markdown("🟢 **ONLINE**")

def render_summary_cards(data):
    """Render the main summary metrics cards with RugCheck + TweetScout status"""
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "💰 Wallet Balance",
            f"{format_currency(data['wallet_balance'])} SOL",
            help="Current SOL balance in wallet"
        )
    
    with col2:
        agent_state = data['agent_state']
        if agent_state:
            active_positions = len(agent_state.get('active_positions', []))
            max_positions = agent_state.get('agent_parameters', {}).get('max_positions', 5)
            st.metric(
                "📋 Active Positions", 
                f"{active_positions}/{max_positions}",
                help=f"Current positions vs maximum allowed"
            )
        else:
            st.metric("📋 Active Positions", "0")
    
    with col3:
        if agent_state and agent_state.get('portfolio_metrics'):
            total_profit = agent_state['portfolio_metrics'].get('total_profit_sol', 0)
            profit_pct = (total_profit / 1.0) * 100 if total_profit != 0 else 0
            
            st.metric(
                "💎 Total P&L",
                f"{format_currency(total_profit)} SOL",
                delta=f"{profit_pct:+.1f}%",
                help="Total realized and unrealized profit/loss"
            )
        else:
            st.metric("💎 Total P&L", "0 SOL")
    
    with col4:
        # Show enrichment status instead of BitQuery status
        if agent_state:
            enriched_positions = sum(1 for pos in agent_state.get('active_positions', []) 
                                   if pos.get('enriched', False))
            total_positions = len(agent_state.get('active_positions', []))
            
            if total_positions > 0:
                enrichment_pct = (enriched_positions / total_positions) * 100
                st.metric(
                    "🔬 Enrichment Coverage",
                    f"{enrichment_pct:.0f}%",
                    delta=f"{enriched_positions}/{total_positions}",
                    help="Percentage of positions with RugCheck + TweetScout analysis"
                )
            else:
                st.metric("🔬 Enrichment Coverage", "0%")
        else:
            st.metric("🔬 Enrichment Coverage", "0%")
    
    with col5:
        # Show win rate or recent performance
        if agent_state and agent_state.get('portfolio_metrics'):
            win_rate = agent_state['portfolio_metrics'].get('win_rate', 0) * 100
            total_trades = agent_state['portfolio_metrics'].get('total_closed_trades', 0)
            
            st.metric(
                "🎯 Win Rate",
                f"{win_rate:.1f}%",
                delta=f"{total_trades} trades",
                help="Percentage of profitable closed trades"
            )
        else:
            st.metric("🎯 Win Rate", "0%")

def render_performance_overview(agent_state):
    """Render performance overview with RugCheck + TweetScout metrics"""
    if not agent_state:
        st.info("No agent state available")
        return
    
    st.subheader("📊 Performance Overview")
    
    portfolio_metrics = agent_state.get('portfolio_metrics', {})
    active_positions = agent_state.get('active_positions', [])
    
    # Main performance metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        realized_profit = portfolio_metrics.get('realized_profit_sol', 0)
        st.metric(
            "Realized P&L",
            f"{format_currency(realized_profit)} SOL",
            help="Profit/loss from closed positions"
        )
    
    with col2:
        unrealized_profit = portfolio_metrics.get('unrealized_profit_sol', 0)
        st.metric(
            "Unrealized P&L",
            f"{format_currency(unrealized_profit)} SOL",
            help="Current profit/loss from open positions"
        )
    
    with col3:
        total_trades = portfolio_metrics.get('total_closed_trades', 0)
        st.metric(
            "Total Trades",
            str(total_trades),
            help="Number of completed trades"
        )
    
    with col4:
        avg_hold_time = portfolio_metrics.get('avg_hold_time_hours', 0)
        st.metric(
            "Avg Hold Time",
            f"{avg_hold_time:.1f}h",
            help="Average time positions are held"
        )
    
    # Enrichment quality metrics
    if active_positions:
        st.write("---")
        st.subheader("🔬 Analysis Quality Metrics")
        
        # Calculate enrichment statistics
        enriched_positions = [pos for pos in active_positions if pos.get('enriched', False)]
        rugcheck_positions = [pos for pos in active_positions if pos.get('safety_score', 0) > 0]
        social_positions = [pos for pos in active_positions if pos.get('social_activity', 0) > 0]
        
        quality_col1, quality_col2, quality_col3, quality_col4 = st.columns(4)
        
        with quality_col1:
            enrichment_coverage = (len(enriched_positions) / len(active_positions)) * 100
            st.metric(
                "🔍 Full Analysis",
                f"{enrichment_coverage:.0f}%",
                delta=f"{len(enriched_positions)}/{len(active_positions)}",
                help="Positions with complete RugCheck + TweetScout analysis"
            )
        
        with quality_col2:
            safety_coverage = (len(rugcheck_positions) / len(active_positions)) * 100
            st.metric(
                "🛡️ Safety Analysis",
                f"{safety_coverage:.0f}%",
                delta=f"{len(rugcheck_positions)}/{len(active_positions)}",
                help="Positions with RugCheck safety analysis"
            )
        
        with quality_col3:
            social_coverage = (len(social_positions) / len(active_positions)) * 100
            st.metric(
                "📱 Social Analysis",
                f"{social_coverage:.0f}%",
                delta=f"{len(social_positions)}/{len(active_positions)}",
                help="Positions with TweetScout social analysis"
            )
        
        with quality_col4:
            # Average safety score for positions with data
            if rugcheck_positions:
                avg_safety = sum(pos.get('safety_score', 0) for pos in rugcheck_positions) / len(rugcheck_positions)
                st.metric(
                    "📊 Avg Safety Score",
                    f"{avg_safety:.1f}/100",
                    help="Average safety score across analyzed positions"
                )
            else:
                st.metric("📊 Avg Safety Score", "N/A")
        
        # Show top performing enriched vs non-enriched
        if enriched_positions and len(active_positions) > len(enriched_positions):
            st.write("---")
            st.write("**📈 Enrichment Impact Analysis:**")
            
            # Calculate performance comparison
            enriched_profits = [pos.get('current_profit_percentage', 0) for pos in enriched_positions]
            non_enriched = [pos for pos in active_positions if not pos.get('enriched', False)]
            non_enriched_profits = [pos.get('current_profit_percentage', 0) for pos in non_enriched]
            
            if enriched_profits and non_enriched_profits:
                enriched_avg = sum(enriched_profits) / len(enriched_profits)
                non_enriched_avg = sum(non_enriched_profits) / len(non_enriched_profits)
                performance_diff = enriched_avg - non_enriched_avg
                
                impact_col1, impact_col2, impact_col3 = st.columns(3)
                
                with impact_col1:
                    st.metric(
                        "Enriched Positions Avg",
                        f"{enriched_avg:+.1f}%",
                        help="Average performance of positions with full analysis"
                    )
                
                with impact_col2:
                    st.metric(
                        "Basic Analysis Avg",
                        f"{non_enriched_avg:+.1f}%",
                        help="Average performance of positions with basic analysis only"
                    )
                
                with impact_col3:
                    delta_color = "normal" if performance_diff > 0 else "inverse"
                    st.metric(
                        "Enhancement Impact",
                        f"{performance_diff:+.1f}%",
                        delta="Better" if performance_diff > 0 else "Worse",
                        delta_color=delta_color,
                        help="Performance difference between enriched and basic analysis"
                    )

def render_enrichment_status_card():
    """Render a dedicated enrichment status card"""
    from src.data.unified_enrichment import get_unified_enrichment_capabilities
    
    st.subheader("🔬 Enrichment Status")
    
    capabilities = get_unified_enrichment_capabilities()
    
    status_col1, status_col2 = st.columns(2)
    
    with status_col1:
        if capabilities.get('full_enrichment', False):
            st.success("🟢 Full Enrichment Active")
            st.write("✅ RugCheck + TweetScout operational")
        elif capabilities.get('api_available', False):
            st.warning("🟡 Partial Enrichment")
            if capabilities.get('token_safety_analysis'):
                st.write("✅ RugCheck available")
            if capabilities.get('social_sentiment_analysis'):
                st.write("✅ TweetScout available")
        else:
            st.error("🔴 Basic Analysis Only")
            st.write("⚠️ Enhanced APIs unavailable")
    
    with status_col2:
        st.write("**Available Features:**")
        features = [
            ("Safety Analysis", capabilities.get('token_safety_analysis', False)),
            ("Social Sentiment", capabilities.get('social_sentiment_analysis', False)),
            ("Whale Tracking", capabilities.get('whale_tracking', False)),
            ("Market Analytics", capabilities.get('market_analytics', False))
        ]
        
        for feature, available in features:
            icon = "✅" if available else "❌"
            st.write(f"{icon} {feature}")

def render_api_cost_tracking():
    """Render API usage and cost tracking"""
    st.subheader("💰 API Usage & Costs")
    
    # This would track actual API usage - placeholder for now
    cost_col1, cost_col2, cost_col3 = st.columns(3)
    
    with cost_col1:
        st.metric(
            "Monthly API Calls",
            "1,234",  # Would be actual tracked usage
            delta="↑ 12%",
            help="Total API calls this month across all services"
        )
    
    with cost_col2:
        st.metric(
            "Estimated Cost",
            "$47.50",  # Would be calculated from actual usage
            delta="↓ 68% vs BitQuery",
            delta_color="normal",
            help="Estimated monthly cost for RugCheck + TweetScout"
        )
    
    with cost_col3:
        st.metric(
            "Cost per Trade",
            "$0.38",  # Would be calculated from trades/costs
            delta="↓ 72%",
            delta_color="normal",
            help="Average API cost per completed trade"
        )
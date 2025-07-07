# ui/components/trading_history.py
"""
Trading history tab component for the Streamlit dashboard
Updated for RugCheck + TweetScout integration (No BitQuery)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from ui.components.metrics import get_performance_color, format_currency
from datetime import datetime, timedelta

def render_transaction_stats(transactions):
    """Render transaction summary statistics with enrichment breakdown"""
    st.subheader("📊 Trading Summary")
    
    if not transactions:
        st.info("No trading history available")
        return
    
    # Basic transaction stats
    buy_txs = [tx for tx in transactions if tx.get('type') == 'buy']
    sell_txs = [tx for tx in transactions if tx.get('type') == 'sell']
    partial_sell_txs = [tx for tx in transactions if tx.get('type') == 'partial_sell']
    
    # Enrichment stats
    enriched_txs = [tx for tx in transactions if tx.get('enriched', False)]
    rugcheck_txs = [tx for tx in transactions if tx.get('safety_score', 0) > 0]
    tweetscout_txs = [tx for tx in transactions if tx.get('social_activity', 0) > 0]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Trades", len(transactions))
    with col2:
        st.metric("Buy Orders", len(buy_txs))
    with col3:
        st.metric("Sell Orders", len(sell_txs) + len(partial_sell_txs))
    with col4:
        enrichment_pct = (len(enriched_txs) / len(transactions)) * 100 if transactions else 0
        st.metric("Enhanced Trades", f"{enrichment_pct:.0f}%", delta=f"{len(enriched_txs)}/{len(transactions)}")
    
    # Show enrichment breakdown
    st.write("---")
    st.write("**🔬 Analysis Coverage:**")
    
    analysis_col1, analysis_col2, analysis_col3 = st.columns(3)
    
    with analysis_col1:
        full_coverage = (len(enriched_txs) / len(transactions)) * 100 if transactions else 0
        st.metric("Full Analysis", f"{full_coverage:.0f}%", help="RugCheck + TweetScout")
    
    with analysis_col2:
        safety_coverage = (len(rugcheck_txs) / len(transactions)) * 100 if transactions else 0
        st.metric("Safety Analysis", f"{safety_coverage:.0f}%", help="RugCheck only")
    
    with analysis_col3:
        social_coverage = (len(tweetscout_txs) / len(transactions)) * 100 if transactions else 0
        st.metric("Social Analysis", f"{social_coverage:.0f}%", help="TweetScout only")

def render_profit_distribution(transactions):
    """Render profit distribution chart with enrichment overlay"""
    sell_txs = [tx for tx in transactions if tx.get('type') in ['sell', 'partial_sell']]
    
    if not sell_txs:
        st.info("No completed trades to analyze")
        return
        
    st.subheader("📈 Profit Distribution Analysis")
    
    profits = [tx.get('profit_percentage', 0) for tx in sell_txs]
    enrichment_status = []
    
    for tx in sell_txs:
        if tx.get('enriched', False):
            enrichment_status.append('Full Analysis')
        elif tx.get('safety_score', 0) > 0 or tx.get('social_activity', 0) > 0:
            enrichment_status.append('Partial Analysis')
        else:
            enrichment_status.append('Basic Analysis')
    
    # Create histogram with enrichment coloring
    fig = px.histogram(
        x=profits, 
        color=enrichment_status,
        nbins=20, 
        title="Profit Distribution by Analysis Quality",
        color_discrete_map={
            'Full Analysis': '#00CC88',
            'Partial Analysis': '#FFB366', 
            'Basic Analysis': '#FF6B6B'
        }
    )
    
    fig.update_xaxis(title="Profit Percentage (%)")
    fig.update_yaxis(title="Number of Trades")
    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.7)
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Performance comparison
    if len(set(enrichment_status)) > 1:  # Multiple analysis types
        st.write("**📊 Performance by Analysis Quality:**")
        
        # Calculate stats for each group
        analysis_stats = {}
        for status in set(enrichment_status):
            status_profits = [p for p, s in zip(profits, enrichment_status) if s == status]
            if status_profits:
                analysis_stats[status] = {
                    'count': len(status_profits),
                    'avg_profit': sum(status_profits) / len(status_profits),
                    'win_rate': len([p for p in status_profits if p > 0]) / len(status_profits) * 100,
                    'best_trade': max(status_profits),
                    'worst_trade': min(status_profits)
                }
        
        # Display comparison
        for status, stats in analysis_stats.items():
            with st.expander(f"{status} - {stats['count']} trades"):
                stat_col1, stat_col2, stat_col3 = st.columns(3)
                
                with stat_col1:
                    st.metric("Avg Profit", f"{stats['avg_profit']:+.1f}%")
                with stat_col2:
                    st.metric("Win Rate", f"{stats['win_rate']:.1f}%")
                with stat_col3:
                    st.metric("Best/Worst", f"{stats['best_trade']:+.1f}% / {stats['worst_trade']:+.1f}%")

def render_transaction_filters():
    """Render transaction filter controls"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        tx_type_filter = st.selectbox("Filter by Type", ["All", "buy", "sell", "partial_sell"])
    
    with col2:
        analysis_filter = st.selectbox("Filter by Analysis", [
            "All", "Full Analysis", "Partial Analysis", "Basic Analysis"
        ])
    
    with col3:
        limit = st.number_input("Show last N transactions", min_value=5, max_value=100, value=20)
    
    with col4:
        show_details = st.checkbox("Show enrichment details", value=False)
    
    return tx_type_filter, analysis_filter, limit, show_details

def render_detailed_transactions(filtered_txs, show_details=False):
    """Render detailed transaction list with enrichment information"""
    if not filtered_txs:
        st.info("No transactions match the current filters")
        return
    
    st.subheader(f"📋 Transaction Details ({len(filtered_txs)} trades)")
    
    for i, tx in enumerate(filtered_txs):
        # Determine enrichment status
        enriched = tx.get('enriched', False)
        safety_score = tx.get('safety_score', 0)
        social_activity = tx.get('social_activity', 0)
        
        # Create transaction header
        tx_type = tx.get('type', 'unknown').upper()
        symbol = tx.get('token_symbol', 'Unknown')
        amount = tx.get('amount_sol', 0)
        price = tx.get('price_usd', 0)
        timestamp = tx.get('timestamp', '')
        
        # Color code by transaction type
        type_colors = {'BUY': '🟢', 'SELL': '🔴', 'PARTIAL_SELL': '🟡'}
        type_icon = type_colors.get(tx_type, '⚪')
        
        # Add enrichment indicator
        if enriched:
            enrichment_indicator = "🔬"
        elif safety_score > 0 or social_activity > 0:
            enrichment_indicator = "🔍"
        else:
            enrichment_indicator = "📊"
        
        header = f"{type_icon} {tx_type} {symbol} | {enrichment_indicator}"
        
        if tx_type in ['SELL', 'PARTIAL_SELL']:
            profit_pct = tx.get('profit_percentage', 0)
            profit_usd = tx.get('profit_usd', 0)
            header += f" | P&L: {profit_pct:+.1f}% (${profit_usd:+.2f})"
        
        with st.expander(header):
            # Basic transaction info
            info_col1, info_col2 = st.columns(2)
            
            with info_col1:
                st.write("**Transaction Details:**")
                st.write(f"• Symbol: {symbol}")
                st.write(f"• Type: {tx_type}")
                st.write(f"• Amount: {format_currency(amount)} SOL")
                st.write(f"• Price: ${price:.6f}")
                st.write(f"• Total Value: ${amount * price:.2f}")
                
                if timestamp:
                    st.write(f"• Time: {timestamp}")
                
                # Add transaction hash if available
                tx_hash = tx.get('transaction_hash', '')
                if tx_hash:
                    short_hash = f"{tx_hash[:8]}...{tx_hash[-8:]}"
                    st.write(f"• TX: {short_hash}")
            
            with info_col2:
                if tx_type in ['SELL', 'PARTIAL_SELL']:
                    st.write("**Performance:**")
                    profit_pct = tx.get('profit_percentage', 0)
                    profit_usd = tx.get('profit_usd', 0)
                    hold_time = tx.get('hold_time_hours', 0)
                    
                    # Color code profit
                    if profit_pct > 0:
                        profit_color = "🟢"
                    elif profit_pct < 0:
                        profit_color = "🔴"
                    else:
                        profit_color = "⚪"
                    
                    st.write(f"• P&L: {profit_color} {profit_pct:+.2f}%")
                    st.write(f"• Profit: ${profit_usd:+.2f}")
                    st.write(f"• Hold Time: {hold_time:.1f}h")
                    
                    # Show entry/exit prices
                    entry_price = tx.get('entry_price_usd', 0)
                    exit_price = tx.get('exit_price_usd', price)
                    if entry_price > 0:
                        st.write(f"• Entry: ${entry_price:.6f}")
                        st.write(f"• Exit: ${exit_price:.6f}")
                else:
                    st.write("**Position Info:**")
                    st.write("• Status: Open position")
                    if tx.get('stop_loss_percentage'):
                        st.write(f"• Stop Loss: -{tx.get('stop_loss_percentage'):.1f}%")
                    if tx.get('take_profit_percentage'):
                        st.write(f"• Take Profit: +{tx.get('take_profit_percentage'):.1f}%")
            
            # Show enrichment details if requested
            if show_details:
                st.write("---")
                st.write("**🔬 Analysis Details:**")
                
                analysis_col1, analysis_col2, analysis_col3 = st.columns(3)
                
                with analysis_col1:
                    st.write("**🛡️ Safety Analysis:**")
                    if safety_score > 0:
                        st.write(f"• Safety Score: {safety_score}/100")
                        if tx.get('contract_verified'):
                            st.write("• ✅ Contract Verified")
                        if tx.get('liquidity_locked'):
                            st.write("• ✅ Liquidity Locked")
                        if tx.get('rug_pull_risk'):
                            st.write("• ⚠️ Rug Pull Risk")
                        if tx.get('honeypot_risk'):
                            st.write("• ⚠️ Honeypot Risk")
                    else:
                        st.write("• No safety data")
                
                with analysis_col2:
                    st.write("**📱 Social Analysis:**")
                    if social_activity > 0:
                        st.write(f"• Activity: {social_activity}/100")
                        viral_score = tx.get('viral_score', 0)
                        if viral_score > 0:
                            st.write(f"• Viral Score: {viral_score}/100")
                        sentiment = tx.get('sentiment_score', 50)
                        st.write(f"• Sentiment: {sentiment}/100")
                        if tx.get('trending_potential'):
                            st.write("• 🚀 Trending Potential")
                    else:
                        st.write("• No social data")
                
                with analysis_col3:
                    st.write("**📊 Overall Assessment:**")
                    if enriched:
                        overall_score = tx.get('overall_score', 0)
                        recommendation = tx.get('recommendation', 'UNKNOWN')
                        risk_level = tx.get('risk_level', 'medium')
                        
                        st.write(f"• Overall: {overall_score}/100")
                        st.write(f"• Recommendation: {recommendation}")
                        st.write(f"• Risk: {risk_level.title()}")
                    else:
                        st.write("• Limited analysis")
                        st.write("• Basic metrics only")

def render_performance_timeline(transactions):
    """Render performance timeline with enrichment indicators"""
    if not transactions:
        return
        
    st.subheader("📈 Performance Timeline")
    
    # Filter to only sell transactions (completed trades)
    completed_trades = [tx for tx in transactions if tx.get('type') in ['sell', 'partial_sell']]
    
    if not completed_trades:
        st.info("No completed trades for timeline analysis")
        return
    
    # Sort by timestamp
    completed_trades.sort(key=lambda x: x.get('timestamp', ''))
    
    # Prepare data for plotting
    dates = []
    profits = []
    symbols = []
    enrichment_status = []
    cumulative_profit = 0
    cumulative_profits = []
    
    for tx in completed_trades:
        dates.append(tx.get('timestamp', ''))
        profit = tx.get('profit_percentage', 0)
        profits.append(profit)
        symbols.append(tx.get('token_symbol', 'Unknown'))
        
        cumulative_profit += profit
        cumulative_profits.append(cumulative_profit)
        
        # Determine enrichment status
        if tx.get('enriched', False):
            enrichment_status.append('Full Analysis')
        elif tx.get('safety_score', 0) > 0 or tx.get('social_activity', 0) > 0:
            enrichment_status.append('Partial Analysis')
        else:
            enrichment_status.append('Basic Analysis')
    
    if dates:
        # Create timeline chart
        fig = go.Figure()
        
        # Add cumulative profit line
        fig.add_trace(go.Scatter(
            x=dates,
            y=cumulative_profits,
            mode='lines+markers',
            name='Cumulative Profit %',
            line=dict(color='blue', width=2),
            marker=dict(size=8)
        ))
        
        # Add individual trade markers colored by enrichment
        color_map = {
            'Full Analysis': '#00CC88',
            'Partial Analysis': '#FFB366',
            'Basic Analysis': '#FF6B6B'
        }
        
        for status in set(enrichment_status):
            status_dates = [d for d, s in zip(dates, enrichment_status) if s == status]
            status_profits = [p for p, s in zip(cumulative_profits, enrichment_status) if s == status]
            status_symbols = [sym for sym, s in zip(symbols, enrichment_status) if s == status]
            
            fig.add_trace(go.Scatter(
                x=status_dates,
                y=status_profits,
                mode='markers',
                name=status,
                marker=dict(
                    color=color_map[status],
                    size=10,
                    symbol='circle'
                ),
                hovertemplate=f'<b>{status}</b><br>Symbol: %{{customdata}}<br>Cumulative: %{{y:.1f}}%<extra></extra>',
                customdata=status_symbols
            ))
        
        fig.update_layout(
            title="Trading Performance Timeline",
            xaxis_title="Date",
            yaxis_title="Cumulative Profit (%)",
            hovermode='x unified',
            height=500
        )
        
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        st.plotly_chart(fig, use_container_width=True)

def render_trading_history_tab(data):
    """Render the complete trading history tab"""
    agent_state = data.get('agent_state')
    
    if not agent_state:
        st.error("No agent state available")
        return
    
    transaction_history = agent_state.get('transaction_history', [])
    
    if not transaction_history:
        st.info("📭 No trading history available yet")
        st.write("Trades will appear here once the agent starts making transactions.")
        return
    
    # Render transaction statistics
    render_transaction_stats(transaction_history)
    
    # Render profit distribution
    render_profit_distribution(transaction_history)
    
    # Render performance timeline
    render_performance_timeline(transaction_history)
    
    # Render transaction filters and detailed list
    st.write("---")
    tx_type_filter, analysis_filter, limit, show_details = render_transaction_filters()
    
    # Apply filters
    filtered_txs = transaction_history.copy()
    
    # Filter by transaction type
    if tx_type_filter != "All":
        filtered_txs = [tx for tx in filtered_txs if tx.get('type') == tx_type_filter]
    
    # Filter by analysis type
    if analysis_filter != "All":
        if analysis_filter == "Full Analysis":
            filtered_txs = [tx for tx in filtered_txs if tx.get('enriched', False)]
        elif analysis_filter == "Partial Analysis":
            filtered_txs = [tx for tx in filtered_txs if 
                          not tx.get('enriched', False) and 
                          (tx.get('safety_score', 0) > 0 or tx.get('social_activity', 0) > 0)]
        elif analysis_filter == "Basic Analysis":
            filtered_txs = [tx for tx in filtered_txs if 
                          not tx.get('enriched', False) and 
                          tx.get('safety_score', 0) == 0 and 
                          tx.get('social_activity', 0) == 0]
    
    # Limit results
    filtered_txs = filtered_txs[-limit:] if limit > 0 else filtered_txs
    
    # Render detailed transactions
    render_detailed_transactions(filtered_txs, show_details)
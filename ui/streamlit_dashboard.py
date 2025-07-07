# ui/streamlit_dashboard.py
"""
Main Streamlit dashboard - modular version
"""
import streamlit as st
import sys
import os
import time

# Add the parent directory to the path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import utilities and components
from ui.utils import configure_page, initialize_session_state, load_dashboard_data
from ui.components import (
    render_sidebar,
    render_header,
    render_summary_cards,
    render_performance_overview,
    render_portfolio_tab,
    render_tokens_tab,
    render_trading_history_tab,
    render_insights_tab,
    render_system_status_tab
)

def main():
    """Main dashboard function"""
    # Configure page
    configure_page()
    
    # Initialize session state
    initialize_session_state()
    
    # Load dashboard data
    data = load_dashboard_data()
    
    # Render header with mode indicator
    render_header()
    
    # Render sidebar
    render_sidebar(data)
    
    # Render summary cards
    render_summary_cards(data)
    
    # Render performance overview
    if data.get('agent_state'):
        render_performance_overview(data['agent_state'])
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Portfolio", 
        "🔍 Token Analysis", 
        "📊 Trading History", 
        "🧠 Agent Insights", 
        "⚙️ System Status"
    ])
    
    # Render each tab
    with tab1:
        render_portfolio_tab(data)
    
    with tab2:
        render_tokens_tab(data)
    
    with tab3:
        render_trading_history_tab(data)
    
    with tab4:
        render_insights_tab(data)
    
    with tab5:
        render_system_status_tab(data)
    
    # Auto-refresh the dashboard when agent is running
    if st.session_state.agent_running:
        time.sleep(30)
        st.rerun()

if __name__ == "__main__":
    main()
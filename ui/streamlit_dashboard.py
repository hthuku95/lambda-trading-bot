# ui/streamlit_dashboard.py
"""
Main Streamlit dashboard - Complete version with enterprise authentication
All original functionality preserved with enhanced security
"""
import streamlit as st
import sys
import os

# Add the parent directory to the path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 🔐 AUTHENTICATION FIRST - Before any other imports
from src.auth.enterprise_auth import enterprise_auth_manager as auth_manager

# Require authentication before showing dashboard
auth_manager.require_auth()

# Only import dashboard components after authentication
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
    render_system_status_tab,
    render_backtesting_tab,
    render_approvals_tab,
    render_approval_banner,
)

def main():
    """Main dashboard function - Only accessible after authentication"""
    
    # Configure page settings
    configure_page()
    
    # Add logout button and user info to sidebar
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🔐 Security Info")
        
        # User information
        col1, col2 = st.columns([3, 1])
        with col1:
            username = st.session_state.get('username', 'User')
            st.markdown(f"👤 **Logged in as:** {username}")
            
            # Show session info
            login_time = st.session_state.get('login_time', 0)
            if login_time:
                from datetime import datetime
                login_datetime = datetime.fromtimestamp(login_time)
                st.markdown(f"🕒 **Login:** {login_datetime.strftime('%H:%M:%S')}")
        
        with col2:
            if st.button("🚪 Logout", help="Securely logout from dashboard"):
                auth_manager.logout()
                st.rerun()
        
        # Security status indicators
        st.markdown("---")
        st.markdown("#### 🛡️ Security Status")

        # Session timeout info
        session_timeout_hours = auth_manager.session_timeout / 3600
        st.info(f"⏱️ Session: {session_timeout_hours:.1f}h timeout")
        st.success("🔒 Authenticated")
    
    # Initialize session state for dashboard
    initialize_session_state()
    
    # Load all dashboard data
    data = load_dashboard_data()
    
    # Render main header with mode indicator
    render_header()
    
    # Render main sidebar (agent controls)
    render_sidebar(data)
    
    # Render summary metrics cards
    render_summary_cards(data)

    # Always-visible approval banner (shows only when a trade is pending)
    render_approval_banner()

    # Render performance overview section
    if data.get('agent_state'):
        render_performance_overview(data['agent_state'])
    
    # Create main dashboard tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📈 Portfolio",
        "🔍 Token Analysis",
        "📊 Trading History",
        "🧠 Agent Insights",
        "💬 Chat with Agents",
        "⚙️ System Status",
        "📊 Backtesting",
        "🔔 Approvals",
    ])

    # Render each tab content
    with tab1:
        render_portfolio_tab(data)

    with tab2:
        render_tokens_tab(data)

    with tab3:
        render_trading_history_tab(data)

    with tab4:
        render_insights_tab(data)

    with tab5:
        # Import and render chat tab
        from ui.components.agent_chat import render_chat_tab
        render_chat_tab()

    with tab6:
        render_system_status_tab(data)

    with tab7:
        render_backtesting_tab(data)

    with tab8:
        render_approvals_tab(data)

    # Auto-refresh when agent is running (non-blocking)
    if st.session_state.get('agent_running', False):
        st.markdown(
            "<meta http-equiv='refresh' content='30'>",
            unsafe_allow_html=True
        )
    
    # Footer with security notice
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            "<div style='text-align: center; color: #666; font-size: 0.8em;'>"
            "🔐 Secure Trading Dashboard | VPN + Authentication Required | "
            "All activities are logged for security"
            "</div>", 
            unsafe_allow_html=True
        )

if __name__ == "__main__":
    main()
# ui/utils.py
"""
Utility functions for the Streamlit dashboard
"""
import streamlit as st
from src.agent import load_agent_state
from src.blockchain.solana_client import get_wallet_balance
from src.memory.cache import get_cache_stats
from src.memory.astra_vector_store import get_memory_stats

@st.cache_data(ttl=10)  # Cache for 10 seconds to avoid too frequent calls
def load_dashboard_data():
    """Load all data needed for the dashboard"""
    try:
        agent_state = load_agent_state()
        wallet_balance = get_wallet_balance()
        cache_stats = get_cache_stats()
        memory_stats = get_memory_stats()
        
        return {
            'agent_state': agent_state,
            'wallet_balance': wallet_balance,
            'cache_stats': cache_stats,
            'memory_stats': memory_stats
        }
    except Exception as e:
        st.error(f"Error loading dashboard data: {e}")
        return {
            'agent_state': None,
            'wallet_balance': 0,
            'cache_stats': {},
            'memory_stats': {}
        }

def initialize_session_state():
    """Initialize Streamlit session state"""
    if 'agent_running' not in st.session_state:
        st.session_state.agent_running = False
    if 'agent_thread' not in st.session_state:
        st.session_state.agent_thread = None
    if 'agent_parameters' not in st.session_state:
        st.session_state.agent_parameters = {
            'dry_run': True,
            'max_positions': 5,
            'max_position_size_sol': 0.1,
            'min_position_size_sol': 0.01,
            'cycle_time_seconds': 300,
            'risk_tolerance': 'medium'
        }
    if 'trading_mode' not in st.session_state:
        st.session_state.trading_mode = 'custom'

def configure_page():
    """Configure the Streamlit page"""
    st.set_page_config(
        page_title="Solana Trading Agent Dashboard",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )
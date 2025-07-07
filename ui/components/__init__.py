# ui/components/__init__.py
"""
Updated Dashboard Components Module - RugCheck + TweetScout (No BitQuery)
"""
from .sidebar import render_sidebar
from .metrics import render_header, render_summary_cards, render_performance_overview
from .portfolio import render_portfolio_tab
from .tokens import render_tokens_tab
from .trading_history import render_trading_history_tab
from .insights import render_insights_tab
from .system_status import render_system_status_tab

__all__ = [
    'render_sidebar',
    'render_header',
    'render_summary_cards',
    'render_performance_overview',
    'render_portfolio_tab',
    'render_tokens_tab',
    'render_trading_history_tab',
    'render_insights_tab',
    'render_system_status_tab'
]

# Note: bitquery_status.py has been removed as it's no longer needed
# tests/conftest.py
"""
Shared pytest fixtures for the lambda-trading-bot test suite.

Design principles:
- DB integration tests use the REAL PostgreSQL database (from DATABASE_URL in .env)
- HTTP / LLM fixtures mock only the network transport layer (requests.get/post, LLM clients)
- Business-logic tests need no mocks at all
- Every fixture is documented so its purpose is clear
"""
import os
import sys
import json
import time
import tempfile
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone, timedelta

# ── Path setup ────────────────────────────────────────────────────────────────
# Ensure the project root is on sys.path so "src.*" and "ui.*" imports resolve
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Load .env so DATABASE_URL is available for integration tests ───────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


# ══════════════════════════════════════════════════════════════════════════════
# STATE / DATA FIXTURES  (pure-Python, no external dependencies)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def initial_state():
    """
    A minimal but valid AgentState dict that mirrors create_initial_state().
    Does NOT call create_initial_state() to avoid Solana RPC calls in unit tests.
    """
    now = datetime.now().isoformat()
    return {
        "wallet_balance_sol": 5.0,
        "wallet_balance_usd": 750.0,
        "simulated_balance_sol": 10.0,
        "active_positions": [],
        "total_portfolio_value_sol": 5.0,
        "total_portfolio_value_usd": 750.0,
        "discovered_tokens": [],
        "analyzed_tokens": [],
        "validated_tokens": [],
        "watchlist_tokens": [],
        "trading_decisions": [],
        "pending_orders": [],
        "transaction_history": [],
        "failed_transactions": [],
        "market_conditions": {},
        "ai_market_assessment": {},
        "market_sentiment": "neutral",
        "trend_analysis": {},
        "agent_reasoning": "Test state",
        "ai_confidence_level": 50.0,
        "ai_strategy": "discovery_and_analysis",
        "ai_focus_areas": ["token_discovery", "market_analysis"],
        "ai_learned_patterns": [],
        "current_cycle_stage": "initialization",
        "next_action": "discover_tokens",
        "cycle_start_time": now,
        "cycles_completed": 0,
        "agent_parameters": {
            "trading_mode": "dry_run",
            "model_provider": "google",
            "max_positions": 5,
            "max_position_size_sol": 0.1,
            "min_position_size_sol": 0.01,
            "risk_tolerance": "medium",
            "ai_temperature": 0.1,
            "cycle_time_seconds": 300,
            "enable_learning": True,
            "enable_memory": True,
        },
        "trading_mode": "dry_run",
        "risk_management": {
            "max_portfolio_risk": 0.15,
            "max_position_risk": 0.05,
            "stop_loss_threshold": -15.0,
            "take_profit_threshold": 25.0,
            "max_hold_time_hours": 24.0,
        },
        "max_positions": 5,
        "max_position_size_sol": 0.1,
        "min_position_size_sol": 0.01,
        "portfolio_allocation": {"cash": 0.7, "positions": 0.3},
        "portfolio_metrics": {
            "total_value_sol": 5.0,
            "unrealized_profit_sol": 0.0,
            "realized_profit_sol": 0.0,
            "daily_pnl": 0.0,
            "win_rate": 0.0,
            "last_updated": now,
        },
        "trading_performance": {},
        "ai_performance": {},
        "total_profit_sol": 0.0,
        "total_profit_usd": 0.0,
        "win_rate": 0.0,
        "sharpe_ratio": 0.0,
        "max_drawdown": 0.0,
        "total_trades": 0,
        "successful_trades": 0,
        "average_hold_time": 0.0,
        "average_profit_per_trade": 0.0,
        "balance_history": [5.0, 5.0, 5.1, 4.9, 5.2],
        "ai_memory_stats": {},
        "pattern_recognition": {},
        "strategy_evolution": [],
        "successful_strategies": [],
        "failed_strategies": [],
        "market_lessons_learned": [],
        "last_update_timestamp": now,
        "agent_health": {"status": "healthy", "last_check": now},
        "data_source_status": {},
        "execution_status": {"status": "ready"},
        "rugcheck_status": {},
        "tweetscout_status": {},
        "dexscreener_status": {},
        "tools_used_this_cycle": [],
        "memory_operations": [],
        "performance_log": [],
        "error_log": [],
        "recursion_counter": 0,
        "max_recursion_limit": 10,
        "bitquery_status": {},
        "enhanced_analytics": {},
    }


@pytest.fixture
def sample_token_data():
    """Realistic TokenData dict for a Solana memecoin."""
    return {
        "address": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "symbol": "BONK",
        "name": "Bonk",
        "price_usd": 0.000025,
        "liquidity_usd": 500000.0,
        "volume_24h": 1200000.0,
        "volume_1h": 75000.0,
        "volume_5m": 8000.0,
        "age_hours": 48.0,
        "market_cap": 1500000.0,
        "fdv": 2000000.0,
        "price_change_24h": 15.5,
        "price_change_1h": 3.2,
        "price_change_5m": 0.8,
        "price_change_15m": 1.1,
        "buy_count": 350,
        "sell_count": 120,
        "buy_ratio": 0.74,
        "total_transactions": 470,
        "pair_address": "PairXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "dex_id": "raydium",
        "chain_id": "solana",
        "url": "https://dexscreener.com/solana/PairXXXXXXXX",
        "labels": ["trending"],
        "boosts_active": 2,
        "safety_raw_data": {"score": 85, "risks": []},
        "contract_verified": True,
        "liquidity_locked": True,
        "ownership_concentration": 0.12,
        "honeypot_risk": False,
        "rug_pull_risk": False,
        "risk_factors": [],
        "social_raw_data": {"mentions": 500, "sentiment": "bullish"},
        "social_mentions_24h": 500,
        "total_engagement": 1500,
        "unique_users": 300,
        "verified_accounts": 15,
        "trending_potential": True,
        "whale_raw_data": {},
        "large_transactions_detected": False,
        "average_transaction_size": 120.0,
        "whale_dominance_score": 0.15,
        "ai_overall_score": 78.0,
        "ai_recommendation": "BUY",
        "ai_risk_assessment": "medium",
        "ai_reasoning": "Strong momentum with good safety metrics",
        "ai_confidence": 72.0,
        "ai_safety_score": 85.0,
        "ai_social_score": 70.0,
        "enriched": True,
        "safety_score": 85,
        "social_activity": 70,
        "discovery_source": "boosted_latest",
    }


@pytest.fixture
def sample_position():
    """Realistic open Position dict."""
    entry_time = datetime.now(timezone.utc) - timedelta(hours=4)
    return {
        "position_id": "pos_test_001",
        "token_address": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "token_symbol": "BONK",
        "entry_price_usd": 0.000020,
        "current_price_usd": 0.000025,
        "position_size_sol": 0.05,
        "current_value_usd": 62.5,
        "entry_time": entry_time.isoformat(),
        "current_profit_percentage": 25.0,
        "unrealized_pnl_usd": 12.5,
        "hold_time_hours": 4.0,
        "stop_loss_percentage": 15.0,
        "take_profit_percentage": 30.0,
        "status": "open",
        "enriched": True,
        "safety_score": 85,
        "social_activity": 70,
        "entry_ai_reasoning": "Strong buy signal",
        "model_provider": "google",
        "amount": 2500000,
    }


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE FIXTURES  (real PostgreSQL integration)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def db_available():
    """
    Session-scoped fixture: initialises the real PostgreSQL pool once.
    Tests that require this fixture are SKIPPED if the DB is unreachable.
    """
    db_url = os.environ.get("DATABASE_URL_INTERNAL") or os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not configured — skipping DB integration tests")

    from src.db.connection import init_pool, is_available
    ok = init_pool(min_conn=1, max_conn=3)
    if not ok:
        pytest.skip("PostgreSQL pool could not be initialised — skipping DB integration tests")

    from src.db.schema import ensure_schema
    ensure_schema()
    return True


@pytest.fixture
def db_conn(db_available):
    """
    Yields a real psycopg2 connection from the pool.
    Rolls back after each test to keep the DB clean.
    """
    from src.db.connection import _pool
    conn = _pool.getconn()
    conn.autocommit = False
    try:
        yield conn
    finally:
        conn.rollback()
        _pool.putconn(conn)


# ══════════════════════════════════════════════════════════════════════════════
# MOCK DB CONNECTION  (for unit tests that don't need a real DB)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_cursor():
    """A mock psycopg2 cursor with configurable fetchone / fetchall."""
    cur = MagicMock()
    cur.description = [("id",), ("name",)]
    cur.fetchone.return_value = (1,)
    cur.fetchall.return_value = []
    return cur


@pytest.fixture
def mock_db_conn(mock_cursor):
    """
    Patches src.db.connection.get_conn to yield a mock connection.
    Use this for unit tests that call DB functions without a real DB.
    """
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("src.db.connection.is_available", return_value=True), \
         patch("src.db.connection._pool") as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        mock_pool.putconn = MagicMock()
        yield mock_conn, mock_cursor


# ══════════════════════════════════════════════════════════════════════════════
# HTTP REQUEST MOCKS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_requests_get():
    """Patches requests.get globally. Returns a configurable mock Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {}
    with patch("requests.get", return_value=mock_resp) as m:
        yield m, mock_resp


@pytest.fixture
def mock_requests_session():
    """Patches requests.Session so Session.get returns a configurable mock."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {}
    mock_sess = MagicMock()
    mock_sess.get.return_value = mock_resp
    mock_sess.post.return_value = mock_resp
    with patch("requests.Session", return_value=mock_sess):
        yield mock_sess, mock_resp


# ══════════════════════════════════════════════════════════════════════════════
# FILE / TEMP DIR FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_state_file(tmp_path):
    """Temporary file path for state I/O tests."""
    return str(tmp_path / "agent_state.json")


@pytest.fixture
def state_file_with_content(tmp_state_file, initial_state):
    """Write a valid state JSON to a temp file and return its path."""
    with open(tmp_state_file, "w") as f:
        json.dump(initial_state, f)
    return tmp_state_file


# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT SESSION STATE MOCK
# ══════════════════════════════════════════════════════════════════════════════

class SessionStateProxy(dict):
    """
    Supports both attribute-style and dict-style access for st.session_state mocking.

    Streamlit source code uses ``st.session_state.key = value`` (attribute assignment)
    and ``'key' in st.session_state`` (containment check).  A plain dict only supports
    the latter, so tests that invoke Streamlit code need this proxy instead.
    """
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(key)


@pytest.fixture
def mock_st_session_state():
    """
    Mimics st.session_state as a SessionStateProxy (supports both attribute and
    dict-style access).  Patches streamlit.session_state for component tests.
    """
    state = SessionStateProxy()
    with patch("streamlit.session_state", new=state):
        yield state


@pytest.fixture
def mock_streamlit():
    """Suppress all Streamlit rendering calls so component code can run in tests."""
    from contextlib import ExitStack
    patches = [
        patch("streamlit.set_page_config"),
        patch("streamlit.title"),
        patch("streamlit.header"),
        patch("streamlit.subheader"),
        patch("streamlit.write"),
        patch("streamlit.text"),
        patch("streamlit.markdown"),
        patch("streamlit.error"),
        patch("streamlit.warning"),
        patch("streamlit.info"),
        patch("streamlit.success"),
        patch("streamlit.metric"),
        patch("streamlit.columns", return_value=[MagicMock(), MagicMock(), MagicMock()]),
        patch("streamlit.expander", return_value=MagicMock().__enter__()),
        patch("streamlit.tabs", return_value=[MagicMock() for _ in range(6)]),
        patch("streamlit.form", return_value=MagicMock().__enter__()),
        patch("streamlit.text_input", return_value="test"),
        patch("streamlit.form_submit_button", return_value=False),
        patch("streamlit.button", return_value=False),
        patch("streamlit.radio", return_value="single"),
        patch("streamlit.selectbox", return_value="anthropic"),
        patch("streamlit.stop"),
        patch("streamlit.rerun"),
        patch("streamlit.plotly_chart"),
        patch("streamlit.cache_data", lambda **kw: lambda f: f),
    ]
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield


# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE API RESPONSE PAYLOADS  (realistic, full-fidelity)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def dexscreener_pair_response():
    """Realistic DexScreener pair API response for a Solana memecoin."""
    return {
        "pairs": [
            {
                "chainId": "solana",
                "dexId": "raydium",
                "url": "https://dexscreener.com/solana/PairXXX",
                "pairAddress": "PairXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                "baseToken": {
                    "address": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    "name": "Bonk",
                    "symbol": "BONK",
                },
                "quoteToken": {"address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "symbol": "USDC"},
                "priceNative": "0.000025",
                "priceUsd": "0.000025",
                "txns": {
                    "m5": {"buys": 20, "sells": 5},
                    "h1": {"buys": 180, "sells": 60},
                    "h6": {"buys": 800, "sells": 200},
                    "h24": {"buys": 2500, "sells": 900},
                },
                "volume": {"m5": 8000, "h1": 75000, "h6": 350000, "h24": 1200000},
                "priceChange": {"m5": 0.8, "h1": 3.2, "h6": 8.5, "h24": 15.5},
                "liquidity": {"usd": 500000, "base": 20000000000, "quote": 250000},
                "fdv": 2000000,
                "marketCap": 1500000,
                "pairCreatedAt": int((time.time() - 48 * 3600) * 1000),
                "info": {
                    "imageUrl": "https://example.com/bonk.png",
                    "websites": [{"url": "https://bonk.io"}],
                    "socials": [
                        {"type": "twitter", "url": "https://twitter.com/bonk"},
                        {"type": "telegram", "url": "https://t.me/bonk"},
                    ],
                },
                "boosts": {"active": 2},
                "labels": ["trending"],
            }
        ]
    }


@pytest.fixture
def rugcheck_api_response():
    """Realistic RugCheck API response."""
    return {
        "score": 850,
        "score_normalised": 85,
        "risks": [
            {"name": "Low Liquidity", "description": "Liquidity below threshold", "level": "warn", "score": 50}
        ],
        "tokenMeta": {
            "name": "Bonk",
            "symbol": "BONK",
            "mutable": False,
            "updateAuthority": None,
        },
        "token": {
            "mintAuthority": None,
            "freezeAuthority": None,
            "supply": "60000000000000",
            "decimals": 5,
        },
        "markets": [
            {
                "liquidityA": "20000000000",
                "liquidityB": "250000",
                "lp": {
                    "lpLockedPct": 95.5,
                    "holders": [
                        {"pct": 95.5, "address": "LockAddress111"},
                        {"pct": 4.5, "address": "OwnerAddress222"},
                    ],
                },
            }
        ],
        "topHolders": [
            {"address": "Holder1", "amount": "1500000000000", "pct": 2.5},
            {"address": "Holder2", "amount": "900000000000", "pct": 1.5},
        ],
        "insiderNetworks": [],
        "verification": {"jup": True, "dex": True},
    }


@pytest.fixture
def jupiter_quote_response():
    """Realistic Jupiter v6 quote API response."""
    return {
        "inputMint": "So11111111111111111111111111111111111111112",
        "inAmount": "100000000",
        "outputMint": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "outAmount": "3800000000",
        "otherAmountThreshold": "3762000000",
        "swapMode": "ExactIn",
        "slippageBps": 100,
        "platformFee": None,
        "priceImpactPct": "0.15",
        "routePlan": [
            {
                "swapInfo": {
                    "ammKey": "AMMkeyXXXXXXXXXXXXXXX",
                    "label": "Raydium",
                    "inputMint": "So11111111111111111111111111111111111111112",
                    "outputMint": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    "inAmount": "100000000",
                    "outAmount": "3800000000",
                    "feeAmount": "300000",
                    "feeMint": "So11111111111111111111111111111111111111112",
                },
                "percent": 100,
            }
        ],
        "contextSlot": 12345678,
        "timeTaken": 0.025,
        "inputDecimals": 9,
        "outputDecimals": 5,
    }

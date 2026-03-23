# tests/conftest.py
"""
Shared pytest fixtures for the lambda-trading-bot test suite.

Design principles:
- ALL data is real — no synthetic prices, invented balances, or mock API responses
- DB integration tests use the REAL PostgreSQL database (from DATABASE_URL in .env)
- LLM tests call real APIs and are tagged @pytest.mark.integration
- Blockchain submission tests use Solana devnet and are tagged @pytest.mark.devnet
- The only mocks are Streamlit UI infrastructure (no way to run a real browser in tests)
"""
import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Load .env so DATABASE_URL and API keys are available ──────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


# ══════════════════════════════════════════════════════════════════════════════
# TOKEN CONSTANTS  (stable Solana tokens with persistent real-world data)
# ══════════════════════════════════════════════════════════════════════════════

BONK_ADDRESS = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
USDC_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL_ADDRESS  = "So11111111111111111111111111111111111111112"


# ══════════════════════════════════════════════════════════════════════════════
# STATE / DATA FIXTURES  (backed by real APIs)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def initial_state():
    """
    Real agent state from create_initial_state().
    Calls the real Solana RPC for wallet balance and CoinGecko for SOL price.
    Session-scoped — one API call per test run.
    """
    from src.agent.state import create_initial_state
    return create_initial_state()


@pytest.fixture(scope="session")
def sample_token_data():
    """
    Real token data from DexScreener for BONK (always has liquidity and data).
    Session-scoped — one API call per test run.
    """
    from src.data.dexscreener import get_token_pairs
    pairs = get_token_pairs("solana", BONK_ADDRESS)
    assert pairs, f"DexScreener must return data for BONK ({BONK_ADDRESS})"
    return pairs[0]


@pytest.fixture(scope="session")
def sample_position(sample_token_data):
    """
    A realistic open Position dict derived from real BONK market data.
    Uses real price from DexScreener so values are internally consistent.
    """
    real_price = float(sample_token_data.get("priceUsd") or sample_token_data.get("price_usd") or 0.000025)
    entry_price = real_price * 0.9  # simulate entry at 90% of current price
    entry_time = datetime.now(timezone.utc) - timedelta(hours=4)
    profit_pct = ((real_price - entry_price) / entry_price) * 100 if entry_price else 0.0
    return {
        "position_id": "pos_test_001",
        "token_address": BONK_ADDRESS,
        "token_symbol": "BONK",
        "entry_price_usd": entry_price,
        "current_price_usd": real_price,
        "position_size_sol": 0.05,
        "current_value_usd": real_price * 2_500_000,
        "entry_time": entry_time.isoformat(),
        "current_profit_percentage": profit_pct,
        "unrealized_pnl_usd": (real_price - entry_price) * 2_500_000,
        "hold_time_hours": 4.0,
        "stop_loss_percentage": 15.0,
        "take_profit_percentage": 30.0,
        "status": "open",
        "enriched": True,
        "entry_ai_reasoning": "Test position using real market data",
        "model_provider": "google",
        "amount": 2_500_000,
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
# MOCK DB CONNECTION  (for DB store unit tests that verify SQL construction)
# These are testing that the right SQL is generated — not market data.
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
    Use for DB store unit tests that verify SQL construction without a real DB.
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
# STREAMLIT SESSION STATE MOCK  (UI infrastructure — no data)
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

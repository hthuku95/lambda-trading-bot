# src/db/schema.py
"""
PostgreSQL schema — all CREATE TABLE IF NOT EXISTS statements.
Safe to call on every startup (idempotent).
"""
import logging
from src.db.connection import get_conn

logger = logging.getLogger("trading_agent.db")

_SCHEMA_SQL = """
-- ============================================================
-- AUTH
-- ============================================================
CREATE TABLE IF NOT EXISTS auth_login_attempts (
    id           BIGSERIAL PRIMARY KEY,
    client_key   TEXT NOT NULL,
    username     TEXT,
    attempt_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address   TEXT,
    success      BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_auth_attempts_client_time
    ON auth_login_attempts(client_key, attempt_time);

CREATE TABLE IF NOT EXISTS auth_lockouts (
    client_key   TEXT PRIMARY KEY,
    lockout_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_events (
    id          BIGSERIAL PRIMARY KEY,
    event_type  TEXT NOT NULL,
    username    TEXT,
    ip_address  TEXT,
    timestamp   TIMESTAMPTZ DEFAULT NOW(),
    details     JSONB
);

-- ============================================================
-- SYSTEM LOGS
-- ============================================================
CREATE TABLE IF NOT EXISTS system_logs (
    id          BIGSERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level       TEXT NOT NULL,
    logger_name TEXT,
    message     TEXT,
    extra       JSONB
);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON system_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_level     ON system_logs(level, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_logger    ON system_logs(logger_name, timestamp DESC);

-- ============================================================
-- TRADING SESSIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS trading_sessions (
    id                  TEXT PRIMARY KEY,
    model_provider      TEXT NOT NULL,
    trading_mode        TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'running',
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    ended_at            TIMESTAMPTZ,
    cycles_completed    INTEGER DEFAULT 0,
    total_profit_sol    DOUBLE PRECISION DEFAULT 0,
    final_balance_sol   DOUBLE PRECISION,
    initial_balance_sol DOUBLE PRECISION,
    parameters          JSONB
);

-- ============================================================
-- TRADING CYCLES
-- ============================================================
CREATE TABLE IF NOT EXISTS trading_cycles (
    id                     BIGSERIAL PRIMARY KEY,
    session_id             TEXT REFERENCES trading_sessions(id) ON DELETE CASCADE,
    cycle_number           INTEGER NOT NULL,
    model_provider         TEXT NOT NULL,
    trading_mode           TEXT NOT NULL,
    timestamp              TIMESTAMPTZ DEFAULT NOW(),
    duration_seconds       DOUBLE PRECISION,
    wallet_balance_sol     DOUBLE PRECISION,
    simulated_balance_sol  DOUBLE PRECISION,
    active_positions_count INTEGER DEFAULT 0,
    market_sentiment       TEXT,
    ai_strategy            TEXT,
    agent_reasoning        TEXT,
    tools_used             TEXT[],
    state_snapshot         JSONB
);
CREATE INDEX IF NOT EXISTS idx_cycles_session ON trading_cycles(session_id, cycle_number);
CREATE INDEX IF NOT EXISTS idx_cycles_ts      ON trading_cycles(timestamp DESC);

-- ============================================================
-- TRADES
-- ============================================================
CREATE TABLE IF NOT EXISTS trades (
    id                      BIGSERIAL PRIMARY KEY,
    session_id              TEXT REFERENCES trading_sessions(id) ON DELETE CASCADE,
    cycle_id                BIGINT REFERENCES trading_cycles(id) ON DELETE SET NULL,
    model_provider          TEXT NOT NULL,
    trading_mode            TEXT NOT NULL,
    trade_type              TEXT NOT NULL,
    token_address           TEXT NOT NULL,
    token_symbol            TEXT,
    amount_sol              DOUBLE PRECISION,
    price_usd               DOUBLE PRECISION,
    value_usd               DOUBLE PRECISION,
    dry_run                 BOOLEAN NOT NULL DEFAULT TRUE,
    reasoning               TEXT,
    ai_confidence           DOUBLE PRECISION,
    simulated_balance_after DOUBLE PRECISION,
    transaction_id          TEXT,
    success                 BOOLEAN DEFAULT TRUE,
    error_message           TEXT,
    timestamp               TIMESTAMPTZ DEFAULT NOW(),
    raw_data                JSONB
);
CREATE INDEX IF NOT EXISTS idx_trades_session  ON trades(session_id);
CREATE INDEX IF NOT EXISTS idx_trades_token    ON trades(token_address, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_type     ON trades(trade_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_provider ON trades(model_provider, timestamp DESC);

-- ============================================================
-- POSITIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS positions (
    id                  BIGSERIAL PRIMARY KEY,
    position_id         TEXT UNIQUE,
    session_id          TEXT REFERENCES trading_sessions(id) ON DELETE CASCADE,
    entry_trade_id      BIGINT REFERENCES trades(id) ON DELETE SET NULL,
    exit_trade_id       BIGINT REFERENCES trades(id) ON DELETE SET NULL,
    model_provider      TEXT NOT NULL,
    token_address       TEXT NOT NULL,
    token_symbol        TEXT,
    status              TEXT NOT NULL DEFAULT 'open',
    entry_time          TIMESTAMPTZ,
    exit_time           TIMESTAMPTZ,
    hold_time_hours     DOUBLE PRECISION,
    amount              DOUBLE PRECISION,
    position_size_sol   DOUBLE PRECISION,
    entry_price_usd     DOUBLE PRECISION,
    exit_price_usd      DOUBLE PRECISION,
    realized_pnl_sol    DOUBLE PRECISION,
    realized_pnl_usd    DOUBLE PRECISION,
    profit_percentage   DOUBLE PRECISION,
    peak_profit_pct     DOUBLE PRECISION,
    max_drawdown_pct    DOUBLE PRECISION,
    stop_loss_triggered BOOLEAN DEFAULT FALSE,
    profit_target_hit   BOOLEAN DEFAULT FALSE,
    entry_ai_score      DOUBLE PRECISION,
    entry_safety_score  DOUBLE PRECISION,
    entry_reasoning     TEXT,
    exit_reasoning      TEXT,
    strategy            TEXT,
    risk_level          TEXT
);
CREATE INDEX IF NOT EXISTS idx_positions_token    ON positions(token_address);
CREATE INDEX IF NOT EXISTS idx_positions_provider ON positions(model_provider, status);

-- ============================================================
-- AGENT STATE SNAPSHOTS
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_state_snapshots (
    id                     BIGSERIAL PRIMARY KEY,
    model_provider         TEXT NOT NULL,
    trading_mode           TEXT NOT NULL,
    timestamp              TIMESTAMPTZ DEFAULT NOW(),
    cycles_completed       INTEGER,
    wallet_balance_sol     DOUBLE PRECISION,
    simulated_balance_sol  DOUBLE PRECISION,
    total_profit_sol       DOUBLE PRECISION,
    total_profit_usd       DOUBLE PRECISION,
    win_rate               DOUBLE PRECISION,
    sharpe_ratio           DOUBLE PRECISION,
    max_drawdown           DOUBLE PRECISION,
    total_trades           INTEGER,
    successful_trades      INTEGER,
    active_positions_count INTEGER,
    portfolio_metrics      JSONB,
    state_json             JSONB
);
CREATE INDEX IF NOT EXISTS idx_snapshots_provider
    ON agent_state_snapshots(model_provider, timestamp DESC);

-- ============================================================
-- DISCOVERED TOKENS
-- ============================================================
CREATE TABLE IF NOT EXISTS discovered_tokens (
    id               BIGSERIAL PRIMARY KEY,
    session_id       TEXT REFERENCES trading_sessions(id) ON DELETE CASCADE,
    cycle_id         BIGINT REFERENCES trading_cycles(id) ON DELETE SET NULL,
    model_provider   TEXT NOT NULL,
    token_address    TEXT NOT NULL,
    token_symbol     TEXT,
    token_name       TEXT,
    discovery_source TEXT,
    price_usd        DOUBLE PRECISION,
    liquidity_usd    DOUBLE PRECISION,
    volume_24h       DOUBLE PRECISION,
    market_cap       DOUBLE PRECISION,
    age_hours        DOUBLE PRECISION,
    ai_score         DOUBLE PRECISION,
    safety_score     DOUBLE PRECISION,
    social_score     DOUBLE PRECISION,
    action_taken     TEXT,
    skip_reason      TEXT,
    timestamp        TIMESTAMPTZ DEFAULT NOW(),
    raw_data         JSONB
);
CREATE INDEX IF NOT EXISTS idx_disc_token   ON discovered_tokens(token_address, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_disc_session ON discovered_tokens(session_id);

-- ============================================================
-- ERRORS
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_errors (
    id             BIGSERIAL PRIMARY KEY,
    session_id     TEXT REFERENCES trading_sessions(id) ON DELETE CASCADE,
    cycle_id       BIGINT REFERENCES trading_cycles(id) ON DELETE SET NULL,
    model_provider TEXT,
    timestamp      TIMESTAMPTZ DEFAULT NOW(),
    error_type     TEXT,
    error_message  TEXT,
    stack_trace    TEXT,
    tool_name      TEXT,
    recoverable    BOOLEAN DEFAULT TRUE
);

-- ============================================================
-- CHAT HISTORY
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_messages (
    id             BIGSERIAL PRIMARY KEY,
    session_id     TEXT,
    model_provider TEXT NOT NULL,
    role           TEXT NOT NULL,
    content        TEXT,
    timestamp      TIMESTAMPTZ DEFAULT NOW(),
    metadata       JSONB
);
CREATE INDEX IF NOT EXISTS idx_chat_provider ON chat_messages(model_provider, timestamp DESC);
"""


def ensure_schema() -> bool:
    """Create all tables if they don't exist. Safe to call repeatedly."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(_SCHEMA_SQL)
        logger.info("PostgreSQL schema verified/created successfully")
        return True
    except Exception as e:
        logger.error(f"Schema creation failed: {e}")
        return False

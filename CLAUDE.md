# Lambda Trading Bot — CLAUDE.md

## SUPER INSTRUCTION — Research Errors Online First

**When any error is encountered (API errors, permission errors, library exceptions, "unexpected server error" responses), ALWAYS search for the solution online using the Agent tool BEFORE concluding it is a blocker, asking the user, or giving up.** Search DataStax forums, GitHub issues (astrapy, langchain, etc.), Stack Overflow, and official docs. The user considers this extremely important.

---

## What This Project Is

A production-grade Solana memecoin trading bot. It discovers, analyses, and trades tokens using two competing AI models (Claude Haiku and Gemini) running in parallel via LangGraph ReAct loops. Each agent has its own AstraDB vector memory collection. The Streamlit dashboard provides UI/control; `agent_daemon.py` runs independently as a systemd service.

## Environment

- **Python virtual environment**: `/home/harry/projects/DevThukuDotIO/SnowballResearch/env/`
- **Activate**: `source /home/harry/projects/DevThukuDotIO/SnowballResearch/env/bin/activate`
- **Working directory for all commands**: `lambda-trading-bot/`

## Architecture Overview

```
ui/streamlit_dashboard.py     ← Streamlit UI (separate process)
agent_daemon.py               ← Standalone daemon (systemd / shell scripts)
src/agent/
    __init__.py               ← Public API: start/stop/status
    langgraph_trading_agent.py ← LangGraph ReAct agent + all 30 tools + system prompt
    state.py                  ← State schema, load/save, metrics
    agent_chat.py             ← Chat interface for conversing with agents
    multi_agent_manager.py    ← Parallel Claude+Gemini execution
    wallet_sync.py            ← Wallet reconciliation / external cash flows
src/data/
    dexscreener.py            ← Token discovery + market data
    rugcheck_client.py        ← Safety analysis + bulk/insider/votes APIs
    social_intelligence.py    ← Social data (DexScreener social + Nansen)
    nansen_client.py          ← Nansen smart money intelligence
    jupiter.py                ← DEX swap quotes + execution
    sol_price.py              ← CoinGecko SOL/USD price feed (60s cache)
    unified_enrichment.py     ← Aggregates RugCheck + Social + DexScreener into one payload
src/backtesting/
    engine.py                 ← BacktestResult, detect_market_regime(), run_multi_timeframe_backtests()
    strategies.py             ← 24 strategies (momentum×5, reversal×5, quick_flip×4, safety_first×3,
                                 breakout×3, hybrid×4) via factory functions
    runner.py                 ← run_parallel_backtests() with ThreadPoolExecutor
    __init__.py               ← Public exports
src/memory/
    astra_vector_store.py     ← AstraDB vector store (VoyageAI voyage-4 embeddings)
src/blockchain/
    solana_client.py          ← Solana RPC + wallet + transaction signing + devnet support
src/auth/
    enterprise_auth.py        ← bcrypt auth + PostgreSQL rate limiting
src/db/
    __init__.py               ← init_db() — call once at startup
    connection.py             ← ThreadedConnectionPool; prefers DATABASE_URL_INTERNAL
    schema.py                 ← ensure_schema() — 13 tables, idempotent
    auth_store.py             ← login attempts, lockouts, auth events
    log_handler.py            ← PostgreSQLLogHandler — non-blocking queue-based
    trade_store.py            ← write ops: sessions, cycles, trades, positions, snapshots
    query_store.py            ← read ops: analytics queries backing the 6 DB tools
    backtest_store.py         ← save_backtest_result(), get_strategy_performance_by_regime()
```

## Default Models

- **Default agent model**: `google` (Gemini)
- **Claude model**: `claude-haiku-4-5-20251001` (Haiku chosen for cost — 90% cheaper than Opus)
- To override: set `model_provider` in agent parameters or call `CompleteLangGraphTradingAgent(model_provider="anthropic")`

## Key Design Rules

1. **Data layers are pure collectors** — `src/data/` files have zero judgment logic. All AI analysis happens in the agent tools layer.
2. **State files use absolute paths** — never relative. `_PROJECT_ROOT` and `_DEFAULT_STATE_FILE` constants defined at top of `state.py`.
3. **Atomic state writes** — `save_agent_state()` writes to `.tmp` then `os.replace()`. Never write directly.
4. **Tool output truncated at 4,000 chars** — prevents context window overflow in LangGraph cycles.
5. **No VPN enforcement** — VPN feature removed entirely. Do not add it back.
6. **No synthetic data** — no fake balances, no fabricated prices, no deprecated stubs anywhere. Dry-run reads real wallet + real Jupiter quotes; only final blockchain submission is withheld.
7. **SystemMessage preserved across tool calls** — `_call_model` separates system_msgs from other_msgs and keeps system_msgs outside the rolling truncation window (`system_msgs + other_msgs[-12:]`).

## Agent System Prompt Architecture

Each trading cycle injects two messages into the LangGraph graph:

1. **`SystemMessage`** from `_build_system_prompt(state)` — ~9,820-char operating manual covering:
   - 7-step decision loop (discover → analyse → backtest → score → execute → learn → report)
   - 5-signal scoring (100 pts): Viral Narrative 30 + Social Momentum 25 + Volume Velocity 25 + Safety Floor 10 + Marketing Firepower 10
   - Position sizing scaled to current wallet balance (25%/20%/15%/10% tiers)
   - Hard risk rules: -20% stop loss, 12h time stop, profit ladders (+5x/+15x/+50x)
   - All 24 strategies with regime guidance (bull/bear/sideways/volatile)
   - Human approval gate (≥5 SOL threshold)
   - Complete reference for all 30 tools

2. **`HumanMessage`** from `_create_context_message()` — per-cycle briefing with live wallet balance, open positions, recent trades, market regime

## Backtesting System

- **24 strategies** registered in `src/backtesting/strategies.py` via factory functions
- **3 timeframes** per token: 5m, 15m, 60m (via `run_multi_timeframe_backtests()`)
- **Market regime detection**: `detect_market_regime(candles)` → bull/bear/sideways/volatile
- **Universe sweep**: background thread fetches top-200 Solana tokens hourly, queues for 30-day/3-timeframe deep backtests
- **AstraDB storage**: every result tagged with `market_regime` + `interval_minutes` for regime-filtered retrieval
- **Agent tools**: `run_deep_backtest_tool` (72 simulations per token), `get_strategy_by_regime_tool` (DB query)
- **Queue format**: `(token_address: str, days_back: int, timeframes: list[int])`

## Render Deployment

| Service | Type | ID | URL |
|---------|------|----|-----|
| `lambda-trading-bot-daemon` | Background Worker | `srv-d6vj7kngi27c73f1hq20` | N/A |
| `lambda-trading-bot-dashboard` | Web Service | `srv-d6vj7sn5gffc73dc2or0` | https://lambda-trading-bot-dashboard.onrender.com |
| `lambda-trading-bot-db` | PostgreSQL | `dpg-d6v3oev5gffc73d3fjvg-a` | ohio, basic_256mb |

- `render.yaml` defines both services as a Blueprint — push to master triggers auto-redeploy.
- On Render, `DATABASE_URL_INTERNAL` is set automatically; `connection.py` prefers it.
- Local dev: DB gracefully disabled (all `src/db/` functions guard with `if not is_available(): return`).
- **psycopg2 note**: local venv uses source-built `psycopg2` (avoids bundled OpenSSL 1.1 bug);
  `requirements.txt` uses `psycopg2-binary` for Render build servers.
- **Render API key**: `rnd_DQdqlYHiyF7nxSvwFwy8hlbou9q0` (for programmatic env var updates)

## Render Environment Variables (Key ones)

| Variable | Value | Notes |
|----------|-------|-------|
| `MAX_POSITION_SIZE_SOL` | `1.0` | Updated from 0.1 |
| `HUMAN_APPROVAL_THRESHOLD_SOL` | `5.0` | Trades ≥ this need human sign-off |
| `HUMAN_APPROVAL_TIMEOUT_MINUTES` | `60` | Auto-reject after timeout |
| `NANSEN_API_KEY` | set | Smart money intelligence |
| `SANDBOX_INITIAL_BALANCE_SOL` | removed | Synthetic data removed |

## Known Pending Items (Optional Enhancements)

| Item | What's needed |
|------|--------------|
| LangSmith feedback loop | Attach P&L outcome feedback to LangSmith traces when positions close |

---

## Completed Work Log

### Sessions 1 + 2 — 2026-03-21 (Foundation)

- LangGraph ReAct dual-agent (Claude Haiku + Gemini) with 16 tools
- 10 production bugs fixed (imports, Jupiter mint swap, state paths, agent start)
- Security: bcrypt, rate limiting, position/slippage caps, removed plaintext debug prints
- Jupiter: dynamic decimals, `dynamicComputeUnitLimit`, priority fee `"auto"`, `restrictIntermediateTokens`
- LangGraph: persistent `thread_id`, LangSmith tracing, SqliteSaver checkpoints, 4,000-char tool truncation
- RugCheck: bulk, insider graph, community votes, JWT auth
- DexScreener: takeovers, promotions, 5m buyers/sellers, 6h volume
- AstraDB: VoyageAI voyage-4 (1024-dim), retry backoff, idempotent create, `$vector` excluded from results
- SOL/USD price feed, USD portfolio values, Sharpe ratio, max drawdown
- Atomic state writes, SIGHUP handler in daemon

### Session 3 — 2026-03-22 (PostgreSQL + Render)

- `src/db/` package (7 files): 13-table schema, ThreadedConnectionPool, non-blocking log handler
- `enterprise_auth.py` migrated SQLite → PostgreSQL
- 6 new DB query tools in agent tool belt
- Render deployment live (daemon + dashboard + PostgreSQL)

### Sessions 4–5 — 2026-03-24 (Production Hardening)

- **Real-data-only mandate**: removed all synthetic data (`simulated_balance_sol`, `_current_simulated_balance`, `SANDBOX_INITIAL_BALANCE_SOL`); dry-run now uses real wallet balance + real Jupiter quotes
- **TweetScout fully removed**: stubs deleted; replaced with Nansen + DexScreener social
- **`src/data/nansen_client.py`**: Nansen smart money API integration
- **341-test suite** across all modules; `pytest.ini` with `integration` and `devnet` markers
- **`src/backtesting/`**: engine, 24 strategies (via factory functions), parallel runner, AstraDB storage, `src/db/backtest_store.py`
- **Universe sweep** in `agent_daemon.py`: top-200 tokens hourly, 30-day/3-TF queue
- **Market regime detection**: `detect_market_regime()` tags all backtest results bull/bear/sideways/volatile
- **Human-in-the-loop**: `ui/components/approvals.py`, approval queue in daemon, dashboard notification
- **Perfect system prompts**: `_build_system_prompt()` 9,820-char operating manual + `_create_context_message()` per-cycle briefing; SystemMessage preserved across tool call truncation
- **`agent_chat.py`** system prompt rewritten with full 24-strategy reference, Nansen mentions, live portfolio state
- **All UI components** updated: TweetScout → Social Intelligence (Nansen + DexScreener) across 12 files
- **`render.yaml`** updated: `MAX_POSITION_SIZE_SOL` 0.1→1.0, `HUMAN_APPROVAL_THRESHOLD_SOL=5.0` added
- **Render env vars** set via API: `NANSEN_API_KEY`, approval thresholds, removed `SANDBOX_INITIAL_BALANCE_SOL`
- **`src/blockchain/solana_client.py`**: devnet support (`get_devnet_rpc_client()`, `send_devnet_transaction()`)
- **`.gitignore`**: added SQLite WAL files (`langgraph_checkpoints.db-shm`, `-wal`)
- **`src/db/backtest_store.py`**: `get_strategy_performance_by_regime()` query on PostgreSQL JSON path

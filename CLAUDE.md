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
    langgraph_trading_agent.py ← LangGraph ReAct agent + all 16 tools
    state.py                  ← State schema, load/save, metrics
    agent_chat.py             ← Chat interface for conversing with agents
    multi_agent_manager.py    ← Parallel Claude+Gemini training
    wallet_sync.py            ← Wallet reconciliation / external cash flows
src/data/
    dexscreener.py            ← Token discovery + market data
    rugcheck_client.py        ← Safety analysis + bulk/insider/votes APIs
    social_intelligence.py   ← TweetScout social data
    jupiter.py                ← DEX swap quotes + execution
    sol_price.py              ← CoinGecko SOL/USD price feed (60s cache)
src/memory/
    astra_vector_store.py     ← AstraDB vector store (VoyageAI voyage-4 embeddings)
src/blockchain/
    solana_client.py          ← Solana RPC + wallet + transaction signing
src/auth/
    enterprise_auth.py        ← bcrypt auth + SQLite rate limiting
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

## Known Pending User Actions

| Item | What's needed |
|------|--------------|
| TweetScout replacement | Decide on a replacement social data source (TweetScout deprecated; DexScreener social active) |
| LangSmith feedback loop | Attach P&L outcome feedback to LangSmith traces when positions close (optional enhancement) |
| Human-in-the-loop | Pause graph for trades above configurable SOL threshold (optional enhancement) |

## What Was Completed (Sessions 1 + 2 — 2026-03-21)

### Bugs Fixed
- BUG-1: `CompleteLangGraphTradingAgent` now imported in `__init__.py`
- BUG-2: Jupiter `get_quote()` now uses keyword args (mints were swapped)
- BUG-4: Duplicate `market_conditions` key in serializable state
- BUG-5: `del migrated_pos["bitquery_enriched"]` fixed → `.pop(..., None)`
- BUG-6: `check_system_status_tool` now passes `model_provider` to `get_stats()`
- BUG-8/10: All relative file paths → absolute paths (state.py, file_lock.py)
- BUG-9: `_agent_running = True` now set before thread starts

### Security
- Removed all `print()` debug statements from auth (were printing plaintext passwords)
- Removed expected username from failed-login UI expander
- Removed password length from audit log
- bcrypt password hashing implemented (plaintext fallback with migration warning)
- SQLite-backed rate limiting (survives Streamlit restarts)
- Position size cap: `MAX_POSITION_SIZE_SOL` env var (default 0.5 SOL)
- Slippage cap: 500 bps max in `get_swap_quote_tool`
- VPN enforcement completely removed

### Jupiter / Blockchain
- Fixed decimal handling to use `inputDecimals`/`outputDecimals` from API response
- `dynamicComputeUnitLimit: true` in swap payload
- Priority fee changed to `"auto"`
- `restrictIntermediateTokens: true` added to quote requests
- Pinned: `solana>=0.30.2`, `solders>=0.21.0`, `astrapy>=2.0.0`

### LangGraph / LangSmith
- Persistent `thread_id` per model+mode (not time-based)
- Per-cycle metadata in config: model, mode, cycle#, balance, positions
- Tool output truncated at 4,000 chars per message
- `get_agent_instance()` added (was missing, referenced by agent_chat.py)
- LangSmith: `LANGCHAIN_API_KEY` filled in `.env`, tracing active
- **SqliteSaver**: `langgraph-checkpoint-sqlite==2.0.11` installed; agent now uses `SqliteSaver` (persistent DB at `langgraph_checkpoints.db`) with `MemorySaver` as fallback

### Data Sources Expanded
- **RugCheck**: bulk reports, insider graph, community votes, most-viewed, verified tokens, JWT auth, health check via `/ping`
- **DexScreener**: community takeovers, promoted tokens, `buyers_5m`/`sellers_5m`, `volume_6h`, `liquidity_base`/`liquidity_quote`

### Memory
- VoyageAI upgraded: `voyage-3.5` → `voyage-4` with `output_dimension=1024`
- `search_similar_experiences()` uses `input_type="query"` (was always "document")
- AstraDB connectivity health check on startup with clear error message

### Features Completed
- SOL/USD price feed via CoinGecko free API (`src/data/sol_price.py`) — 60s cache
- `wallet_balance_usd`, `total_portfolio_value_usd`, `total_profit_usd` now populated
- Sharpe ratio (annualised) implemented in `update_portfolio_metrics()`
- Max drawdown (peak-to-trough) implemented using `balance_history` rolling window
- `data_sources_attempted` / `data_sources_successful` now populated in `social_intelligence.py`
- Agent chat system prompt is capital-flexible (scales to any balance, no hardcoded $ amounts)
- Atomic state file writes (`os.replace`)
- Streamlit auto-refresh uses `<meta http-equiv='refresh'>` (not `time.sleep(30)`)
- Legacy `pure_ai_agent.py` and `pure_ai_graph.py` deleted
- `agent_daemon.py` now handles SIGHUP for config reload without restart
- **Sandbox/dry-run virtual wallet**: `simulated_balance_sol` in state; dry-run cycles use a virtual 10 SOL balance (configurable via `SANDBOX_INITIAL_BALANCE_SOL` in `.env`); `get_wallet_balance_tool` returns simulated balance in dry-run; `execute_trade_tool` debits/credits `_current_simulated_balance`; balance persists across cycles in `agent_state.json`
- **TweetScout deprecated**: `social_intelligence.py` returns DexScreener social only; TweetScout fields return stubs (`{"status": "deprecated", ...}`)
- **AstraDB**: New database `lambda-trading-bot` (`6d689661-...`); org-level token in `.env`; time-based 60s retry backoff; `$vector` excluded from search results; idempotent `create_collection()` (no `list_collection_names()`); 3-attempt insert retry with exponential backoff

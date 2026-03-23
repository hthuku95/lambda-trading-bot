# ui/components/backtesting.py
"""
Backtesting & Strategy Performance dashboard component.
"""
import streamlit as st
from typing import Any, Dict, List


def render_backtest_leaderboard():
    """Show top backtest results from PostgreSQL."""
    st.subheader("Backtest Leaderboard")

    try:
        from src.db.backtest_store import get_backtest_leaderboard
        rows = get_backtest_leaderboard(limit=20)
    except Exception as e:
        st.info(f"Leaderboard unavailable: {e}")
        return

    if not rows:
        st.info(
            "No backtest results yet — database may be offline or no backtests have been run."
        )
        return

    # Build display list
    display = []
    for r in rows:
        display.append({
            "Token": r.get("token_symbol", "UNKNOWN"),
            "Strategy": r.get("strategy_name", ""),
            "Model": r.get("model_provider", ""),
            "Return %": r.get("total_return_pct", 0.0),
            "Win Rate": r.get("win_rate", 0.0),
            "Sharpe": r.get("sharpe_ratio", 0.0),
            "Max DD %": r.get("max_drawdown_pct", 0.0),
            "# Trades": r.get("num_trades", 0),
        })

    st.dataframe(display, use_container_width=True)


def render_backtest_calibration(data: Dict[str, Any]):
    """Show calibration accuracy: predicted vs actual P&L."""
    st.subheader("Prediction Calibration (Backtest vs Actual)")

    agent_state = data.get("agent_state", {}) if data else {}
    transaction_history: List[Dict] = agent_state.get("transaction_history", [])

    calibration_entries = [
        tx for tx in transaction_history
        if tx.get("trade_type") == "outcome_calibration"
    ]

    if not calibration_entries:
        st.info(
            "No calibration data yet — run some trades and backtests first."
        )
        return

    rows = []
    for entry in calibration_entries:
        token = entry.get("token_symbol") or entry.get("token_address", "UNKNOWN")
        actual = entry.get("actual_profit_pct", None)
        predicted = entry.get("backtest_predicted_return_pct", None)
        if actual is None or predicted is None:
            continue
        error = round(actual - predicted, 4)
        rows.append({
            "Token": token,
            "Actual Profit %": actual,
            "Predicted Return %": predicted,
            "Prediction Error %": error,
        })

    if not rows:
        st.info(
            "Calibration entries found but missing required fields "
            "(actual_profit_pct / backtest_predicted_return_pct)."
        )
        return

    st.dataframe(rows, use_container_width=True)

    # Scatter chart if plotly is available
    try:
        import plotly.express as px
        import pandas as pd

        df = pd.DataFrame(rows)
        fig = px.scatter(
            df,
            x="Predicted Return %",
            y="Actual Profit %",
            text="Token",
            title="Predicted vs Actual Return",
            labels={
                "Predicted Return %": "Backtest Predicted Return (%)",
                "Actual Profit %": "Actual Profit (%)",
            },
        )
        # Add a perfect-calibration diagonal
        min_val = min(df["Predicted Return %"].min(), df["Actual Profit %"].min())
        max_val = max(df["Predicted Return %"].max(), df["Actual Profit %"].max())
        fig.add_shape(
            type="line",
            x0=min_val, y0=min_val,
            x1=max_val, y1=max_val,
            line=dict(color="gray", dash="dash"),
        )
        fig.update_traces(textposition="top center")
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.info("Install plotly for scatter chart visualisation: `pip install plotly`")


def render_backtesting_tab(data: Dict[str, Any]):
    """Render the full Backtesting & Strategy Performance tab."""
    st.header("Backtesting & Strategy Performance")

    st.markdown(
        "This tab shows how strategies performed in backtests and how well "
        "those predictions matched live trading outcomes."
    )

    render_backtest_leaderboard()

    st.markdown("---")

    render_backtest_calibration(data)

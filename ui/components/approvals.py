# ui/components/approvals.py
"""
Human-in-the-loop trade approval panel.

Watches for trade_pending_approval.json in the project root and surfaces
Approve / Reject controls to the operator.  Writes decisions to
trade_approvals.json and removes the pending file once actioned.
"""
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import streamlit as st

# Project root is three levels up from this file:
#   ui/components/approvals.py  ->  ui/components/  ->  ui/  ->  <project_root>/
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_PENDING_FILE = os.path.join(_PROJECT_ROOT, "trade_pending_approval.json")
_APPROVAL_FILE = os.path.join(_PROJECT_ROOT, "trade_approvals.json")


def _load_pending() -> Dict[str, Any] | None:
    """Load pending approval file; return None if absent or expired."""
    if not os.path.exists(_PENDING_FILE):
        return None
    try:
        with open(_PENDING_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        return None

    # Check expiry
    expires_at_raw = data.get("expires_at")
    if expires_at_raw:
        try:
            if isinstance(expires_at_raw, (int, float)):
                expires_dt = datetime.fromtimestamp(expires_at_raw, tz=timezone.utc)
            else:
                expires_dt = datetime.fromisoformat(str(expires_at_raw).replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > expires_dt:
                # Expired — silently remove
                try:
                    os.remove(_PENDING_FILE)
                except OSError:
                    pass
                return None
        except Exception:
            pass  # If we can't parse expiry, treat as not expired

    return data


def _write_approval(trade_id: str, approved: bool, amount_sol: float | None = None):
    """Write the operator decision to trade_approvals.json (atomic replace)."""
    payload: Dict[str, Any] = {
        "trade_id": trade_id,
        "approved": approved,
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }
    if amount_sol is not None:
        payload["amount_sol"] = amount_sol

    tmp_path = _APPROVAL_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp_path, _APPROVAL_FILE)


def _remove_pending():
    """Delete the pending approval file after a decision is made."""
    try:
        os.remove(_PENDING_FILE)
    except OSError:
        pass


def render_approval_banner():
    """
    Check for a pending trade awaiting approval and render an action banner.

    If trade_pending_approval.json exists and has not expired, shows trade
    details plus Approve / Reject buttons.  The operator may also adjust the
    amount_sol before approving.
    """
    pending = _load_pending()
    if pending is None:
        return  # Nothing to show

    trade_id = pending.get("trade_id", "unknown")
    trade_type = pending.get("trade_type", "UNKNOWN")
    token = pending.get("token_symbol") or pending.get("token_address", "UNKNOWN")
    original_amount = float(pending.get("amount_sol", 0.0))
    reasoning = pending.get("reasoning", "No reasoning provided.")
    expires_at = pending.get("expires_at", "")

    st.warning(
        f"**Trade pending your approval** — "
        f"`{trade_type}` | Token: `{token}` | Amount: `{original_amount:.4f} SOL`"
    )

    with st.expander("Trade details & decision", expanded=True):
        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.markdown(f"**Trade ID:** `{trade_id}`")
            st.markdown(f"**Type:** {trade_type}")
            st.markdown(f"**Token:** {token}")
            st.markdown(f"**Requested amount:** {original_amount:.4f} SOL")
            if expires_at:
                st.markdown(f"**Expires at:** {expires_at}")
            st.markdown(f"**Agent reasoning:** {reasoning}")

        with col_right:
            adjusted_amount = st.number_input(
                "Amount SOL (adjustable)",
                min_value=0.0,
                value=original_amount,
                step=0.01,
                format="%.4f",
                key=f"approval_amount_{trade_id}",
            )

            col_approve, col_reject = st.columns(2)
            with col_approve:
                if st.button("Approve", key=f"approve_{trade_id}", type="primary"):
                    _write_approval(trade_id, approved=True, amount_sol=adjusted_amount)
                    _remove_pending()
                    st.success("Trade approved.")
                    st.rerun()

            with col_reject:
                if st.button("Reject", key=f"reject_{trade_id}"):
                    _write_approval(trade_id, approved=False)
                    _remove_pending()
                    st.error("Trade rejected.")
                    st.rerun()


def render_approvals_tab(data: Dict[str, Any]):
    """
    Full Approvals tab.

    Shows the current pending approval banner (if any) at the top, followed
    by a history of high-value trades (amount_sol >= 5.0) from
    transaction_history.
    """
    st.header("Trade Approvals")

    # Always show the pending banner at the top of the tab as well
    render_approval_banner()

    st.markdown("---")
    st.subheader("High-Value Trade History (>= 5 SOL)")

    agent_state = data.get("agent_state", {}) if data else {}
    transaction_history: List[Dict] = agent_state.get("transaction_history", [])

    high_value = [
        tx for tx in transaction_history
        if float(tx.get("amount_sol", 0) or 0) >= 5.0
    ]

    if not high_value:
        st.info(
            "No high-value trades (>= 5 SOL) recorded yet. "
            "These trades appear here for human review."
        )
        return

    rows = []
    for tx in sorted(high_value, key=lambda x: x.get("timestamp", 0), reverse=True):
        token = tx.get("token_symbol") or tx.get("token_address", "UNKNOWN")
        ts_raw = tx.get("timestamp")
        if ts_raw:
            try:
                ts_str = datetime.fromtimestamp(float(ts_raw)).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                ts_str = str(ts_raw)
        else:
            ts_str = ""

        rows.append({
            "Time": ts_str,
            "Type": tx.get("trade_type", tx.get("type", "")),
            "Token": token,
            "Amount SOL": round(float(tx.get("amount_sol", 0) or 0), 4),
            "Price USD": tx.get("price_usd", ""),
            "P&L %": tx.get("profit_pct", ""),
            "Status": tx.get("status", ""),
        })

    st.dataframe(rows, use_container_width=True)

# tests/test_solana_client.py
"""
Tests for src/blockchain/solana_client.py

Balance tests call real Solana RPC using the wallet in SOLANA_PRIVATE_KEY.
Blockchain submission tests are tagged @pytest.mark.devnet — they require
SOLANA_DEVNET_PRIVATE_KEY and use Solana devnet (no real funds).
"""
import os
import pytest
import base58
from solders.keypair import Keypair
from src.blockchain import solana_client


# ─────────────────────────────────────────────────────────────────────────────
# get_wallet_balance() — real Solana RPC call
# ─────────────────────────────────────────────────────────────────────────────

def test_get_wallet_balance_returns_nonnegative_float():
    """Real Solana wallet balance must be a non-negative float."""
    balance = solana_client.get_wallet_balance()
    assert isinstance(balance, float)
    assert balance >= 0.0


# ─────────────────────────────────────────────────────────────────────────────
# load_wallet_from_private_key() — key loading logic
# ─────────────────────────────────────────────────────────────────────────────

def test_load_wallet_from_private_key_success():
    """A freshly generated keypair must load correctly."""
    kp = Keypair()
    full_key_bytes = bytes(kp)
    private_key_b58 = base58.b58encode(full_key_bytes).decode("utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SOLANA_PRIVATE_KEY", private_key_b58)
        wallet = solana_client.load_wallet_from_private_key()

    assert isinstance(wallet, Keypair)
    assert wallet.pubkey() == kp.pubkey()


def test_load_wallet_from_private_key_missing():
    """ValueError must be raised if SOLANA_PRIVATE_KEY is not set."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SOLANA_PRIVATE_KEY", "")
        with pytest.raises(ValueError, match="Missing SOLANA_PRIVATE_KEY"):
            solana_client.load_wallet_from_private_key()


# ─────────────────────────────────────────────────────────────────────────────
# get_devnet_rpc_client() — returns a real devnet client
# ─────────────────────────────────────────────────────────────────────────────

def test_get_devnet_rpc_client_returns_client():
    from src.blockchain.solana_client import get_devnet_rpc_client
    from solana.rpc.api import Client
    client = get_devnet_rpc_client()
    assert isinstance(client, Client)


# ─────────────────────────────────────────────────────────────────────────────
# load_devnet_wallet() — requires SOLANA_DEVNET_PRIVATE_KEY
# ─────────────────────────────────────────────────────────────────────────────

def test_load_devnet_wallet_raises_without_key():
    """load_devnet_wallet() must raise ValueError when the env var is absent."""
    from src.blockchain.solana_client import load_devnet_wallet
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SOLANA_DEVNET_PRIVATE_KEY", "")
        with pytest.raises(ValueError, match="SOLANA_DEVNET_PRIVATE_KEY"):
            load_devnet_wallet()


def test_load_devnet_wallet_success():
    """load_devnet_wallet() must return a Keypair when the env var is set."""
    from src.blockchain.solana_client import load_devnet_wallet
    kp = Keypair()
    key_b58 = base58.b58encode(bytes(kp)).decode("utf-8")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SOLANA_DEVNET_PRIVATE_KEY", key_b58)
        wallet = load_devnet_wallet()
    assert isinstance(wallet, Keypair)
    assert wallet.pubkey() == kp.pubkey()


# ─────────────────────────────────────────────────────────────────────────────
# send_devnet_transaction() — real blockchain submission on devnet
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.devnet
def test_send_devnet_self_transfer():
    """
    Submits a minimal SOL self-transfer on Solana devnet to verify signing and
    submission mechanics.  Requires SOLANA_DEVNET_PRIVATE_KEY in .env.

    This test does NOT use Jupiter — devnet has no liquidity pools.
    A self-transfer (sending 0 lamports to yourself) is enough to exercise
    the signing and submission code path.
    """
    devnet_key = os.getenv("SOLANA_DEVNET_PRIVATE_KEY")
    if not devnet_key:
        pytest.skip("SOLANA_DEVNET_PRIVATE_KEY not set — skipping devnet test")

    from src.blockchain.solana_client import (
        get_devnet_rpc_client,
        load_devnet_wallet,
        send_devnet_transaction,
    )
    from solders.system_program import transfer, TransferParams
    from solders.transaction import VersionedTransaction
    from solders.message import MessageV0
    import base64

    devnet_client = get_devnet_rpc_client()
    devnet_wallet = load_devnet_wallet()

    # Get a recent blockhash
    blockhash_resp = devnet_client.get_latest_blockhash()
    recent_blockhash = blockhash_resp.value.blockhash

    # Build a minimal 0-lamport self-transfer
    ix = transfer(TransferParams(
        from_pubkey=devnet_wallet.pubkey(),
        to_pubkey=devnet_wallet.pubkey(),
        lamports=0,
    ))
    msg = MessageV0.try_compile(
        payer=devnet_wallet.pubkey(),
        instructions=[ix],
        address_lookup_table_accounts=[],
        recent_blockhash=recent_blockhash,
    )
    tx = VersionedTransaction(msg, [devnet_wallet])
    serialized = base64.b64encode(bytes(tx)).decode("utf-8")

    result = send_devnet_transaction(serialized)
    assert "result" in result or "error" in result
    # On devnet, a 0-lamport self-transfer should succeed
    if "error" in result:
        pytest.fail(f"Devnet transaction failed: {result['error']}")

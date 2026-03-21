
import pytest
from unittest.mock import MagicMock, patch
import base58
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed
from src.blockchain import solana_client

@pytest.fixture(autouse=True)
def mock_solana_wallet():
    """Mocks the wallet loaded from environment variables."""
    with patch('src.blockchain.solana_client.load_wallet_from_private_key') as mock_load:
        mock_keypair = Keypair()
        mock_load.return_value = mock_keypair
        yield mock_keypair

@pytest.fixture
def mock_solana_client():
    """Mocks the Solana RPC client."""
    with patch('src.blockchain.solana_client.client', spec=Client) as mock_client:
        yield mock_client

def test_get_wallet_balance_success(mock_solana_client):
    """Tests successful retrieval of wallet balance."""
    mock_solana_client.get_balance.return_value = MagicMock(value=1500000000)

    balance = solana_client.get_wallet_balance()
    
    assert balance == 1.5
    mock_solana_client.get_balance.assert_called_once()

def test_get_wallet_balance_failure_fallback(mock_solana_client):
    """Tests the fallback mechanism when the primary get_balance call fails."""
    # Make the primary method raise an exception
    mock_solana_client.get_balance.side_effect = Exception("Primary call failed")

    # Mock the requests.post for the fallback
    with patch('requests.post') as mock_post:
        mock_rpc_response = MagicMock()
        mock_rpc_response.status_code = 200
        mock_rpc_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {"context": {"slot": 1}, "value": 2000000000},
            "id": 1
        }
        mock_post.return_value = mock_rpc_response

        balance = solana_client.get_wallet_balance()

        assert balance == 2.0
        mock_post.assert_called_once()

def test_load_wallet_from_private_key_success():
    """
    Tests that a wallet can be successfully loaded from a valid private key.
    This test runs against the actual function but with a mocked environment.
    """
    # A valid base58 private key for a new, temporary keypair
    kp = Keypair()
    # The full keypair bytes are 64 bytes (32 private + 32 public)
    full_key_bytes = bytes(kp)
    private_key_b58 = base58.b58encode(full_key_bytes).decode('utf-8')

    with patch.dict('os.environ', {'SOLANA_PRIVATE_KEY': private_key_b58}):
        # We need to reload the module to make it use the mocked env var
        from importlib import reload
        reload(solana_client)
        
        wallet = solana_client.load_wallet_from_private_key()
        assert isinstance(wallet, Keypair)
        assert wallet.pubkey() == kp.pubkey()

def test_load_wallet_from_private_key_missing():
    """Tests that a ValueError is raised if the private key is missing."""
    with patch.dict('os.environ', {'SOLANA_PRIVATE_KEY': ''}):
        with pytest.raises(ValueError, match="Missing SOLANA_PRIVATE_KEY"):
            # We need to reload the module to make it use the mocked env var
            from importlib import reload
            reload(solana_client)
            solana_client.load_wallet_from_private_key()

# Note: Testing the send_serialized_transaction function is complex as it involves
# transaction signing and serialization. A full test would require a more elaborate setup.
# For this suite, we focus on the core client interactions that don't involve private key operations.

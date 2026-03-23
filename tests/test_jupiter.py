# tests/test_jupiter.py
"""
Tests for src/data/jupiter.py

All HTTP calls are mocked at the requests layer.
Business logic (lamport conversion, slippage, payload construction) is tested for real.
"""
import pytest
from unittest.mock import patch, MagicMock


SOL_MINT = "So11111111111111111111111111111111111111112"
TEST_TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


# ─────────────────────────────────────────────────────────────────────────────
# get_quote()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetQuote:
    @pytest.fixture
    def mock_quote_response(self, jupiter_quote_response):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = jupiter_quote_response
        return mock_resp

    def test_returns_quote_dict_on_success(self, mock_quote_response):
        with patch("requests.get", return_value=mock_quote_response):
            from src.data.jupiter import get_quote
            result = get_quote(TEST_TOKEN, amount_in_sol=0.1)
        assert result is not None
        assert "inAmount" in result
        assert "outAmount" in result

    def test_converts_sol_to_lamports_correctly(self, mock_quote_response):
        """0.1 SOL must be sent as 100_000_000 lamports."""
        with patch("requests.get", return_value=mock_quote_response) as mock_get:
            from src.data.jupiter import get_quote
            get_quote(TEST_TOKEN, amount_in_sol=0.1)
        call_params = mock_get.call_args[1]["params"]
        assert call_params["amount"] == int(0.1 * 1e9)  # 100_000_000

    def test_uses_sol_mint_as_input_when_amount_in_sol_given(self, mock_quote_response):
        with patch("requests.get", return_value=mock_quote_response) as mock_get:
            from src.data.jupiter import get_quote
            get_quote(TEST_TOKEN, amount_in_sol=0.5)
        params = mock_get.call_args[1]["params"]
        assert params["inputMint"] == SOL_MINT

    def test_passes_slippage_bps_to_api(self, mock_quote_response):
        with patch("requests.get", return_value=mock_quote_response) as mock_get:
            from src.data.jupiter import get_quote
            get_quote(TEST_TOKEN, amount_in_sol=0.1, slippage_bps=200)
        params = mock_get.call_args[1]["params"]
        assert params["slippageBps"] == 200

    def test_restrict_intermediate_tokens_always_set(self, mock_quote_response):
        with patch("requests.get", return_value=mock_quote_response) as mock_get:
            from src.data.jupiter import get_quote
            get_quote(TEST_TOKEN, amount_in_sol=0.1)
        params = mock_get.call_args[1]["params"]
        assert params.get("restrictIntermediateTokens") == "true"

    def test_returns_none_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("400 Bad Request")
        with patch("requests.get", return_value=mock_resp):
            from src.data.jupiter import get_quote
            result = get_quote(TEST_TOKEN, amount_in_sol=0.1)
        assert result is None

    def test_returns_none_on_request_exception(self):
        import requests
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("no conn")):
            from src.data.jupiter import get_quote
            result = get_quote(TEST_TOKEN, amount_in_sol=0.1)
        assert result is None

    def test_returns_none_on_malformed_json(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.side_effect = ValueError("not JSON")
        with patch("requests.get", return_value=mock_resp):
            from src.data.jupiter import get_quote
            result = get_quote(TEST_TOKEN, amount_in_sol=0.1)
        assert result is None

    def test_handles_non_sol_input_mint(self, mock_quote_response):
        """When input_mint and amount are given directly, they are passed through."""
        with patch("requests.get", return_value=mock_quote_response) as mock_get:
            from src.data.jupiter import get_quote
            get_quote(TEST_TOKEN, input_mint="OtherMintXXX", amount=5000000)
        params = mock_get.call_args[1]["params"]
        assert params["inputMint"] == "OtherMintXXX"
        assert params["amount"] == 5000000

    def test_uses_15_second_timeout(self, mock_quote_response):
        with patch("requests.get", return_value=mock_quote_response) as mock_get:
            from src.data.jupiter import get_quote
            get_quote(TEST_TOKEN, amount_in_sol=0.1)
        assert mock_get.call_args[1]["timeout"] == 15


# ─────────────────────────────────────────────────────────────────────────────
# get_swap_transaction()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetSwapTransaction:
    @pytest.fixture
    def swap_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "swapTransaction": "AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==",
        }
        return mock_resp

    def test_returns_base64_transaction_string(self, swap_response, jupiter_quote_response):
        with patch("requests.post", return_value=swap_response):
            from src.data.jupiter import get_swap_transaction
            result = get_swap_transaction(jupiter_quote_response, "WalletPubkeyXXX")
        assert result == "AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="

    def test_includes_quote_response_in_payload(self, swap_response, jupiter_quote_response):
        with patch("requests.post", return_value=swap_response) as mock_post:
            from src.data.jupiter import get_swap_transaction
            get_swap_transaction(jupiter_quote_response, "WalletPubkeyXXX")
        payload = mock_post.call_args[1]["json"]
        assert payload["quoteResponse"] == jupiter_quote_response

    def test_includes_user_public_key_in_payload(self, swap_response, jupiter_quote_response):
        with patch("requests.post", return_value=swap_response) as mock_post:
            from src.data.jupiter import get_swap_transaction
            get_swap_transaction(jupiter_quote_response, "MyWalletPubkey")
        payload = mock_post.call_args[1]["json"]
        assert payload["userPublicKey"] == "MyWalletPubkey"

    def test_includes_required_swap_config_flags(self, swap_response, jupiter_quote_response):
        with patch("requests.post", return_value=swap_response) as mock_post:
            from src.data.jupiter import get_swap_transaction
            get_swap_transaction(jupiter_quote_response, "PubkeyXXX")
        payload = mock_post.call_args[1]["json"]
        assert payload.get("wrapUnwrapSOL") is True
        assert payload.get("dynamicComputeUnitLimit") is True
        assert payload.get("createATA") is True

    def test_returns_none_when_swap_transaction_key_missing(self, jupiter_quote_response):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"error": "insufficient liquidity"}
        with patch("requests.post", return_value=mock_resp):
            from src.data.jupiter import get_swap_transaction
            result = get_swap_transaction(jupiter_quote_response, "PubkeyXXX")
        assert result is None

    def test_returns_none_on_http_error(self, jupiter_quote_response):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
        with patch("requests.post", return_value=mock_resp):
            from src.data.jupiter import get_swap_transaction
            result = get_swap_transaction(jupiter_quote_response, "PubkeyXXX")
        assert result is None

    def test_returns_none_on_connection_error(self, jupiter_quote_response):
        import requests
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError()):
            from src.data.jupiter import get_swap_transaction
            result = get_swap_transaction(jupiter_quote_response, "PubkeyXXX")
        assert result is None

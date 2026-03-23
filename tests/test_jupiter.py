# tests/test_jupiter.py
"""
Tests for src/data/jupiter.py

Tests that call the live Jupiter API are tagged @pytest.mark.integration.
Error-handling and parameter-construction tests use mocked HTTP responses.
"""
import pytest
from unittest.mock import patch, MagicMock

SOL_MINT   = "So11111111111111111111111111111111111111112"
USDC_MINT  = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
BONK_MINT  = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"


# ─────────────────────────────────────────────────────────────────────────────
# Real Jupiter quote (integration — requires network access)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def real_jupiter_quote():
    """
    Fetches a real SOL→USDC quote from Jupiter v6.
    Used in @pytest.mark.integration tests only.
    """
    from src.data.jupiter import get_quote
    quote = get_quote(USDC_MINT, amount_in_sol=0.01, slippage_bps=100)
    if quote is None:
        pytest.skip("Jupiter API unavailable — skipping integration test")
    return quote


# ─────────────────────────────────────────────────────────────────────────────
# Real-data structural tests (integration)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_real_quote_has_required_fields(real_jupiter_quote):
    for key in ("inputMint", "outputMint", "inAmount", "outAmount", "routePlan"):
        assert key in real_jupiter_quote, f"Missing key: {key}"


@pytest.mark.integration
def test_real_quote_in_amount_is_lamports(real_jupiter_quote):
    assert int(real_jupiter_quote["inAmount"]) == int(0.01 * 1e9)


@pytest.mark.integration
def test_real_quote_output_mint_is_usdc(real_jupiter_quote):
    assert real_jupiter_quote["outputMint"] == USDC_MINT


@pytest.mark.integration
def test_real_quote_out_amount_is_positive(real_jupiter_quote):
    assert int(real_jupiter_quote["outAmount"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# get_quote() — parameter construction tests (mocked transport layer)
# These test the Jupiter CLIENT code (lamport conversion, param names) —
# not market prices. Mocking the HTTP layer is necessary to test these
# deterministically without depending on network connectivity.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def _minimal_quote_resp():
    """Minimal structurally-valid Jupiter quote response for client tests."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "inputMint": SOL_MINT,
        "outputMint": BONK_MINT,
        "inAmount": "100000000",
        "outAmount": "5000000000",
        "swapMode": "ExactIn",
        "slippageBps": 100,
        "routePlan": [],
        "inputDecimals": 9,
        "outputDecimals": 5,
    }
    return mock_resp


class TestGetQuoteParameterConstruction:
    def test_converts_sol_to_lamports_correctly(self, _minimal_quote_resp):
        """0.1 SOL must be sent as 100_000_000 lamports."""
        with patch("requests.get", return_value=_minimal_quote_resp) as mock_get:
            from src.data.jupiter import get_quote
            get_quote(BONK_MINT, amount_in_sol=0.1)
        call_params = mock_get.call_args[1]["params"]
        assert call_params["amount"] == int(0.1 * 1e9)

    def test_uses_sol_mint_as_input_when_amount_in_sol_given(self, _minimal_quote_resp):
        with patch("requests.get", return_value=_minimal_quote_resp) as mock_get:
            from src.data.jupiter import get_quote
            get_quote(BONK_MINT, amount_in_sol=0.5)
        params = mock_get.call_args[1]["params"]
        assert params["inputMint"] == SOL_MINT

    def test_passes_slippage_bps_to_api(self, _minimal_quote_resp):
        with patch("requests.get", return_value=_minimal_quote_resp) as mock_get:
            from src.data.jupiter import get_quote
            get_quote(BONK_MINT, amount_in_sol=0.1, slippage_bps=200)
        params = mock_get.call_args[1]["params"]
        assert params["slippageBps"] == 200

    def test_restrict_intermediate_tokens_always_set(self, _minimal_quote_resp):
        with patch("requests.get", return_value=_minimal_quote_resp) as mock_get:
            from src.data.jupiter import get_quote
            get_quote(BONK_MINT, amount_in_sol=0.1)
        params = mock_get.call_args[1]["params"]
        assert params.get("restrictIntermediateTokens") == "true"

    def test_uses_15_second_timeout(self, _minimal_quote_resp):
        with patch("requests.get", return_value=_minimal_quote_resp) as mock_get:
            from src.data.jupiter import get_quote
            get_quote(BONK_MINT, amount_in_sol=0.1)
        assert mock_get.call_args[1]["timeout"] == 15

    def test_handles_non_sol_input_mint(self, _minimal_quote_resp):
        with patch("requests.get", return_value=_minimal_quote_resp) as mock_get:
            from src.data.jupiter import get_quote
            get_quote(BONK_MINT, input_mint="OtherMintXXX", amount=5000000)
        params = mock_get.call_args[1]["params"]
        assert params["inputMint"] == "OtherMintXXX"
        assert params["amount"] == 5000000


class TestGetQuoteErrors:
    def test_returns_none_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("400 Bad Request")
        with patch("requests.get", return_value=mock_resp):
            from src.data.jupiter import get_quote
            result = get_quote(BONK_MINT, amount_in_sol=0.1)
        assert result is None

    def test_returns_none_on_request_exception(self):
        import requests
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("no conn")):
            from src.data.jupiter import get_quote
            result = get_quote(BONK_MINT, amount_in_sol=0.1)
        assert result is None

    def test_returns_none_on_malformed_json(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.side_effect = ValueError("not JSON")
        with patch("requests.get", return_value=mock_resp):
            from src.data.jupiter import get_quote
            result = get_quote(BONK_MINT, amount_in_sol=0.1)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# get_swap_transaction() — payload construction and error handling
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def quote_for_swap(_minimal_quote_resp):
    """Use the minimal quote dict (not a network call) as input to swap builder."""
    return _minimal_quote_resp.json.return_value


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

    @pytest.fixture
    def sample_quote(self):
        """Minimal structurally-valid quote dict for swap builder tests."""
        return {
            "inputMint": SOL_MINT,
            "outputMint": BONK_MINT,
            "inAmount": "100000000",
            "outAmount": "5000000000",
            "swapMode": "ExactIn",
            "slippageBps": 100,
            "routePlan": [],
            "inputDecimals": 9,
            "outputDecimals": 5,
        }

    def test_returns_base64_transaction_string(self, swap_response, sample_quote):
        with patch("requests.post", return_value=swap_response):
            from src.data.jupiter import get_swap_transaction
            result = get_swap_transaction(sample_quote, "WalletPubkeyXXX")
        assert result == "AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="

    def test_includes_quote_response_in_payload(self, swap_response, sample_quote):
        with patch("requests.post", return_value=swap_response) as mock_post:
            from src.data.jupiter import get_swap_transaction
            get_swap_transaction(sample_quote, "WalletPubkeyXXX")
        payload = mock_post.call_args[1]["json"]
        assert payload["quoteResponse"] == sample_quote

    def test_includes_user_public_key_in_payload(self, swap_response, sample_quote):
        with patch("requests.post", return_value=swap_response) as mock_post:
            from src.data.jupiter import get_swap_transaction
            get_swap_transaction(sample_quote, "MyWalletPubkey")
        payload = mock_post.call_args[1]["json"]
        assert payload["userPublicKey"] == "MyWalletPubkey"

    def test_includes_required_swap_config_flags(self, swap_response, sample_quote):
        with patch("requests.post", return_value=swap_response) as mock_post:
            from src.data.jupiter import get_swap_transaction
            get_swap_transaction(sample_quote, "PubkeyXXX")
        payload = mock_post.call_args[1]["json"]
        assert payload.get("wrapUnwrapSOL") is True
        assert payload.get("dynamicComputeUnitLimit") is True
        assert payload.get("createATA") is True

    def test_returns_none_when_swap_transaction_key_missing(self, sample_quote):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"error": "insufficient liquidity"}
        with patch("requests.post", return_value=mock_resp):
            from src.data.jupiter import get_swap_transaction
            result = get_swap_transaction(sample_quote, "PubkeyXXX")
        assert result is None

    def test_returns_none_on_http_error(self, sample_quote):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
        with patch("requests.post", return_value=mock_resp):
            from src.data.jupiter import get_swap_transaction
            result = get_swap_transaction(sample_quote, "PubkeyXXX")
        assert result is None

    def test_returns_none_on_connection_error(self, sample_quote):
        import requests
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError()):
            from src.data.jupiter import get_swap_transaction
            result = get_swap_transaction(sample_quote, "PubkeyXXX")
        assert result is None

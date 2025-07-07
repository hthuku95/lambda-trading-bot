import requests
from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from base64 import b64decode
from solders.message import to_bytes_versioned
from solders.rpc.config import RpcSendTransactionConfig
from fetch_address import get_token_address, fetch_all_tokens
import base58
import os
import json
import logging
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("trading_bot")

# Solana RPC
solana_rpc = "https://api.mainnet-beta.solana.com"
client = Client(solana_rpc)

# Load your private key
private_key_base58 = os.getenv("SOLANA_PRIVATE_KEY")
if not private_key_base58:
    raise ValueError("SOLANA_PRIVATE_KEY not found in .env file")

wallet = Keypair.from_bytes(base58.b58decode(private_key_base58))

print("Wallet Public Key:", wallet.pubkey())

# Jupiter API URLs
quote_url = "https://quote-api.jup.ag/v6/quote"
swap_url = "https://quote-api.jup.ag/v6/swap"

# Token addresses (SOL to USDC example)
tokens = fetch_all_tokens()
USDT_MINT = get_token_address("USDT", tokens)
print(f"USDT MINT ADDRESS: {USDT_MINT}")
SOL_MINT = "So11111111111111111111111111111111111111112"

params = {
    "inputMint": SOL_MINT,
    "outputMint": USDT_MINT,
    "amount": int(0.05 * 10**9),  # 0.05 SOL
    "slippageBps": 50,
}

try:
    # Get best route
    logger.info("getting Quote")
    response = requests.get(quote_url, params=params)
    response.raise_for_status()
    quote = response.json()
    
    route = quote["routePlan"]
    print("Best Route:", json.dumps(route, indent=2))
    
    # Build the swap transaction
    logger.info("Building the swap transaction")
    swap_request = {
        "userPublicKey": str(wallet.pubkey()),
        "quoteResponse": quote,
        "wrapAndUnwrapSol": True,
    }
    
    swap_response = requests.post(swap_url, json=swap_request)
    swap_response.raise_for_status()
    swap = swap_response.json()
    
    # Decode the transaction
    tx_base64 = swap["swapTransaction"]
    tx_bytes = b64decode(tx_base64)
    transaction = VersionedTransaction.from_bytes(tx_bytes)
    
    # Sign the transaction message using the versioned format
    message_bytes = to_bytes_versioned(transaction.message)
    signature = wallet.sign_message(message_bytes)
    
    # Use populate to create a properly signed transaction
    signed_tx = VersionedTransaction.populate(transaction.message, [signature])
    
    # Submit the signed transaction
    txid = client.send_raw_transaction(bytes(signed_tx))
    
    print("Transaction submitted. TXID:", txid.value)
    
    # Confirm transaction
    confirmation = client.confirm_transaction(txid.value, commitment=Confirmed)
    print("Confirmation status:", confirmation)

except Exception as e:
    logger.error(f"Error Swapping Tokens: {e}")




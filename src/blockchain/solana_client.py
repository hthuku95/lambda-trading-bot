from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.message import to_bytes_versioned
from base64 import b64decode
import base58
import os
import json
import requests
import logging
import time
from dotenv import load_dotenv

# Configure logger
logger = logging.getLogger("trading_bot.solana")

# Load environment variables
load_dotenv()

# RPC client setup
def setup_rpc_client():
    """Set up RPC client with the best available endpoint"""
    # Get RPC URL from environment or use a reliable public node
    rpc_url = os.getenv("SOLANA_RPC_URL", "https://solana-rpc.publicnode.com")
    logger.info(f"Using Solana RPC URL: {rpc_url}")
    
    # Create client
    return Client(rpc_url), rpc_url

client, rpc_url = setup_rpc_client()

# Load wallet from private key
def load_wallet_from_private_key():
    """Load wallet from private key in environment variables"""
    private_key = os.getenv("SOLANA_PRIVATE_KEY")
    if not private_key:
        logger.error("No SOLANA_PRIVATE_KEY found in environment variables")
        raise ValueError("Missing SOLANA_PRIVATE_KEY in environment variables")
        
    try:
        # Decode the private key bytes
        key_bytes = base58.b58decode(private_key)
        
        # Create keypair
        keypair = Keypair.from_bytes(key_bytes)
        logger.info(f"Wallet loaded: {keypair.pubkey()}")
        return keypair
    except Exception as e:
        logger.error(f"Error loading wallet: {e}")
        raise

# Initialize wallet
wallet = load_wallet_from_private_key()
logger.info(f"Using wallet address: {wallet.pubkey()}")

# Get SOL balance
def get_wallet_balance(pubkey=None):
    """
    Get wallet balance in SOL
    
    Args:
        pubkey: Public key to check balance for (default: wallet.pubkey())
        
    Returns:
        float: SOL balance
    """
    if pubkey is None:
        pubkey = wallet.pubkey()
    
    try:
        # Get balance using RPC client
        balance_resp = client.get_balance(pubkey)
        
        # Access the value property (in lamports)
        balance_lamports = balance_resp.value
        
        # Convert lamports to SOL
        balance_sol = balance_lamports / 1e9
        
        return balance_sol
    except Exception as e:
        logger.error(f"Error getting wallet balance: {e}")
        
        # Try with a direct RPC call as fallback
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [str(pubkey)]
            }
            
            headers = {"Content-Type": "application/json"}
            response = requests.post(rpc_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result and "value" in result["result"]:
                    lamports = result["result"]["value"]
                    return lamports / 1e9  # Convert to SOL
            
            # If we get here, both attempts failed
            logger.error("Fallback balance check also failed")
            return 0
        except Exception as fallback_error:
            logger.error(f"Fallback balance check failed: {fallback_error}")
            return 0

# Send a serialized transaction - UPDATED VERSION based on jupiter_swap.py
def send_serialized_transaction(serialized_tx_base64, max_retries=3, retry_delay=2):
    """
    Send a serialized transaction to the Solana network
    
    Args:
        serialized_tx_base64: Base64 encoded transaction
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        dict: Transaction result or None if failed
    """
    logger.info("Sending transaction to Solana network")
    
    try:
        # Decode the transaction from base64
        tx_bytes = b64decode(serialized_tx_base64)
        transaction = VersionedTransaction.from_bytes(tx_bytes)
        
        # Sign the transaction message using the versioned format
        message_bytes = to_bytes_versioned(transaction.message)
        signature = wallet.sign_message(message_bytes)
        
        # Use populate to create a properly signed transaction
        signed_tx = VersionedTransaction.populate(transaction.message, [signature])
        
        # Submit the signed transaction with retry logic
        for attempt in range(max_retries):
            try:
                # Use client.send_raw_transaction for better error handling
                txid = client.send_raw_transaction(
                    bytes(signed_tx),
                    opts={"preflight_commitment": "confirmed", "skip_preflight": True}
                )
                
                if txid and hasattr(txid, 'value'):
                    logger.info(f"Transaction submitted. TXID: {txid.value}")
                    
                    # Try to confirm transaction
                    try:
                        confirmation = client.confirm_transaction(txid.value, commitment=Confirmed)
                        logger.info(f"Confirmation status: {confirmation}")
                    except Exception as confirm_error:
                        logger.warning(f"Could not confirm transaction, but it may still succeed: {confirm_error}")
                    
                    return {"result": txid.value}
                else:
                    logger.error("Failed to get transaction ID")
                    
                    # Retry if we have attempts left
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying transaction... ({attempt + 1}/{max_retries})")
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
            
            except Exception as e:
                logger.error(f"Error in attempt {attempt + 1}: {e}")
                
                # Retry if we have attempts left
                if attempt < max_retries - 1:
                    logger.info(f"Retrying transaction... ({attempt + 1}/{max_retries})")
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
        
        # If we get here, all retries failed
        logger.error("All transaction attempts failed")
        return {"error": {"message": "All transaction attempts failed"}}
        
    except Exception as e:
        logger.error(f"Error processing transaction: {e}")
        return {"error": {"message": str(e)}}

# Fallback method using direct RPC calls if the client approach fails
def send_serialized_transaction_fallback(serialized_tx_base64, max_retries=3, retry_delay=2):
    """
    Fallback method to send a transaction using direct RPC calls
    """
    logger.info("Using fallback method to send transaction")
    
    # Prepare RPC payload with optimized parameters
    rpc_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "sendTransaction",
        "params": [
            serialized_tx_base64,
            {
                "skipPreflight": True,       # Skip preflight checks for higher success rate
                "maxRetries": 5,             # Retry at RPC level
                "preflightCommitment": "confirmed",
                "encoding": "base64"
            }
        ]
    }
    
    headers = {"Content-Type": "application/json"}
    
    # Try multiple times with exponential backoff
    for attempt in range(max_retries):
        try:
            logger.info(f"Fallback transaction attempt {attempt + 1}/{max_retries}")
            
            # Send the request
            response = requests.post(rpc_url, json=rpc_payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                
                if "result" in result:
                    tx_sig = result["result"]
                    
                    # Check if we got a placeholder signature
                    if tx_sig == "1111111111111111111111111111111111111111111111111111111111111111":
                        logger.warning("Received placeholder signature (all 1s)")
                        logger.warning("This typically means the RPC node didn't process the transaction")
                        
                        # Try a different node if we have retries left
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                            continue  # Try again
                    
                    logger.info(f"Transaction submitted: {tx_sig}")
                    return {"result": tx_sig}
                    
                elif "error" in result:
                    error_msg = result.get("error", {}).get("message", "Unknown error")
                    logger.error(f"Transaction error: {error_msg}")
                    
                    # Check for specific errors that warrant retrying
                    if any(err in error_msg for err in ["timeout", "rate limit", "too busy", "blockhash", "timed out"]):
                        if attempt < max_retries - 1:
                            logger.info(f"Retrying transaction due to error: {error_msg}")
                            time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                            continue  # Try again
                    
                    return {"error": result["error"]}
            else:
                logger.error(f"RPC request failed: {response.status_code}")
                logger.error(response.text)
                
                # Try again if we have retries left
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    continue  # Try again
                
                return {"error": {"message": f"HTTP error: {response.status_code}"}}
                
        except Exception as e:
            logger.error(f"Error sending transaction: {e}")
            
            # Try again if we have retries left
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                continue  # Try again
            
            return {"error": {"message": str(e)}}
    
    # If we get here, all retries failed
    logger.error("All transaction attempts failed")
    return {"error": {"message": "All transaction attempts failed"}}

def get_token_balance(token_mint, owner_pubkey=None):
    """
    Get token balance for a specific token
    
    Args:
        token_mint: Token mint address
        owner_pubkey: Owner's public key (default: wallet.pubkey())
        
    Returns:
        float: Token balance or 0 if failed
    """
    if owner_pubkey is None:
        owner_pubkey = wallet.pubkey()
    
    try:
        # This is a simplified implementation - in a full version we would:
        # 1. Find the associated token account for this mint and owner
        # 2. Get the token account balance
        
        # For now, we'll use a direct RPC call approach
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                str(owner_pubkey),
                {
                    "mint": token_mint
                },
                {
                    "encoding": "jsonParsed"
                }
            ]
        }
        
        headers = {"Content-Type": "application/json"}
        response = requests.post(rpc_url, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            
            if "result" in result and "value" in result["result"]:
                accounts = result["result"]["value"]
                
                if not accounts:
                    # No token account found
                    return 0
                
                # Use the first account (there should only be one per mint)
                account = accounts[0]
                token_amount = account["account"]["data"]["parsed"]["info"]["tokenAmount"]
                
                # Get amount and decimals
                amount = int(token_amount["amount"])
                decimals = token_amount["decimals"]
                
                # Calculate human-readable balance
                balance = amount / (10 ** decimals)
                return balance
        
        # If we get here, the request failed
        logger.error(f"Failed to get token balance for {token_mint}")
        return 0
        
    except Exception as e:
        logger.error(f"Error getting token balance: {e}")
        return 0

def verify_transaction(signature, max_retries=5, retry_delay=2):
    """
    Verify if a transaction was successful
    
    Args:
        signature: Transaction signature
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        bool: True if transaction was successful, False otherwise
    """
    logger.info(f"Verifying transaction: {signature}")
    
    for attempt in range(max_retries):
        try:
            time.sleep(retry_delay)  # Wait for transaction to be confirmed
            
            # Get transaction details
            tx_data = client.get_transaction(signature)
            
            if tx_data and hasattr(tx_data, 'value') and tx_data.value:
                # Check if transaction was successful
                if hasattr(tx_data.value, 'err') and not tx_data.value.err:
                    logger.info("Transaction verified successful")
                    return True
                else:
                    logger.error(f"Transaction failed: {tx_data.value.err}")
                    return False
            
            # If we can't get transaction details yet, retry
            logger.info(f"Transaction not confirmed yet, retrying... ({attempt + 1}/{max_retries})")
            
        except Exception as e:
            logger.error(f"Error verifying transaction: {e}")
            
            # If not the last attempt, retry
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
            else:
                logger.error("Maximum verification attempts reached")
                return False
    
    # If we get here, all retries failed
    logger.error("Failed to verify transaction")
    return False
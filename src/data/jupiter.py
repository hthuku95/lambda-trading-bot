import requests
import json
import logging

# Configure logger
logger = logging.getLogger("trading_bot.jupiter")

# Jupiter API endpoints
SOL_MINT = "So11111111111111111111111111111111111111112"
JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"

def get_quote(output_mint, amount_in_sol=None, input_mint=None, amount=None, slippage_bps=100):
    """
    Fetch swap quote using Jupiter Aggregator.
    
    Args:
        output_mint: The mint address of the token to receive
        amount_in_sol: Amount of SOL to swap (for SOL to token swaps)
        input_mint: The mint address of the token to swap from (for non-SOL swaps)
        amount: Amount of input tokens in smallest units (for non-SOL swaps)
        slippage_bps: Slippage tolerance in basis points (1 bps = 0.01%)
    
    Returns:
        dict: Quote response from Jupiter or None if error
    """
    # If we're swapping from SOL
    if amount_in_sol is not None:
        input_mint = SOL_MINT
        amount = int(amount_in_sol * 1e9)  # Convert SOL to lamports
    
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": amount,
        "slippageBps": slippage_bps,
    }

    try:
        logger.info(f"Getting quote: {input_mint} → {output_mint}, amount: {amount}")
        response = requests.get(JUPITER_QUOTE_URL, params=params, timeout=15)
        response.raise_for_status()
        
        quote_data = response.json()
        
        # Calculate human-readable values for logging
        input_amount = int(quote_data.get('inAmount', 0))
        output_amount = int(quote_data.get('outAmount', 0))
        
        # Convert to human-readable format based on token
        if input_mint == SOL_MINT:
            input_amount_human = input_amount / 1e9  # SOL has 9 decimals
            input_token = "SOL"
        else:
            input_amount_human = input_amount / 1e6  # Most SPL tokens have 6 decimals
            input_token = quote_data.get('inputSymbol', 'token')
            
        if output_mint == SOL_MINT:
            output_amount_human = output_amount / 1e9  # SOL has 9 decimals
            output_token = "SOL"
        else:
            output_amount_human = output_amount / 1e6  # Most SPL tokens have 6 decimals
            output_token = quote_data.get('outputSymbol', 'token')
        
        # Log the quote details
        logger.info(f"Quote received: {output_amount_human:.6f} {output_token} for " +
                   f"{input_amount_human:.6f} {input_token}")
        logger.info(f"Route: {', '.join([step['swapInfo']['label'] for step in quote_data['routePlan']])}")
        
        return quote_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting Jupiter quote: {e}")
        return None
    except (ValueError, KeyError) as e:
        logger.error(f"Error parsing Jupiter quote: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_quote: {e}")
        return None

def get_swap_transaction(quote_response, user_pubkey):
    """
    Request a pre-built Jupiter swap transaction from a quote.
    
    Args:
        quote_response: Quote data from get_quote()
        user_pubkey: User's wallet public key
    
    Returns:
        str: Base64 encoded transaction or None if error
    """
    # Configure the swap request with parameters optimized for reliability
    payload = {
        "quoteResponse": quote_response,
        "userPublicKey": str(user_pubkey),
        "wrapUnwrapSOL": True,             # Auto-wrap/unwrap SOL
        "computeUnitPriceMicroLamports": 50000,  # Priority fee
        "asLegacyTransaction": False,      # Use versioned transactions
        "skipUserAccountsCheck": True,     # Skip redundant checks
        "maxAccounts": 64,                 # Allow more accounts (needed for complex swaps)
        "createATA": True                  # Automatically create token accounts
    }

    try:
        logger.info("Requesting swap transaction from Jupiter")
        response = requests.post(JUPITER_SWAP_URL, json=payload, timeout=15)
        response.raise_for_status()
        
        swap_data = response.json()
        
        if "swapTransaction" not in swap_data:
            logger.error(f"No swapTransaction in response: {swap_data}")
            return None
            
        tx_base64 = swap_data["swapTransaction"]
        logger.info(f"Received swap transaction ({len(tx_base64)} chars)")
        return tx_base64
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting swap transaction: {e}")
        return None
    except (ValueError, KeyError) as e:
        logger.error(f"Error parsing swap response: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_swap_transaction: {e}")
        return None

def handle_failed_transaction(message, transaction=None, error=None):
    """
    Handle and log failed transactions and attempt recovery where possible.
    
    Args:
        message: Error message
        transaction: Failed transaction data (if available)
        error: Error object (if available)
    """
    logger.error(message)
    
    if error:
        logger.error(f"Error details: {error}")
    
    # Check for known error patterns
    if transaction and isinstance(error, str):
        if "AccountNotFound" in error:
            logger.warning("Token account might not exist. Creating account for next attempt.")
            # The createATA parameter should handle this in future transactions
        elif "not enough SOL to pay for fees" in error:
            logger.warning("Insufficient SOL for transaction fees. Reduce position size.")
        elif "TokenAccountNotFound" in error:
            logger.warning("Associated Token Account not found.")
# src/data/dexscreener.py
"""
Enhanced DexScreener API Integration - Pure Data Collection Only
AI Agent determines all discovery strategies, search terms, and filtering criteria
No hardcoded judgment logic - raw data collection only
"""
import requests
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from src.memory.cache import get_cached_data, cache_data

# Configure logger
logger = logging.getLogger("trading_agent.dexscreener")

# DexScreener API endpoints (Official)
DEXSCREENER_BASE_URL = "https://api.dexscreener.com"

# Official API endpoints
ENDPOINTS = {
    "token_boosts_latest": f"{DEXSCREENER_BASE_URL}/token-boosts/latest/v1",
    "token_boosts_top": f"{DEXSCREENER_BASE_URL}/token-boosts/top/v1", 
    "token_profiles_latest": f"{DEXSCREENER_BASE_URL}/token-profiles/latest/v1",
    "search": f"{DEXSCREENER_BASE_URL}/latest/dex/search",
    "tokens_detail": f"{DEXSCREENER_BASE_URL}/tokens/v1",
    "token_pairs": f"{DEXSCREENER_BASE_URL}/token-pairs/v1",
    "pair_detail": f"{DEXSCREENER_BASE_URL}/latest/dex/pairs"
}

# Rate limiting constants
RATE_LIMITS = {
    "token_boosts": 60,    # 60 requests per minute
    "profiles": 60,        # 60 requests per minute  
    "search": 300,         # 300 requests per minute
    "tokens": 300,         # 300 requests per minute
    "pairs": 300           # 300 requests per minute
}

def make_api_call(url: str, params: Dict = None, timeout: int = 15, max_retries: int = 3) -> Optional[Dict]:
    """
    Make API call to DexScreener with retry logic and rate limiting
    
    Args:
        url: API endpoint URL
        params: Query parameters
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        
    Returns:
        dict: API response data or None on error
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            
            # Handle rate limiting
            if response.status_code == 429:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(f"Rate limited. Waiting {wait_time}s before retry {attempt+1}/{max_retries}")
                time.sleep(wait_time)
                continue
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API call failed (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
                
    logger.error(f"All API call attempts failed for: {url}")
    return None

def process_pair_data(pair_data: Dict) -> Dict[str, Any]:
    """
    Process raw pair data from DexScreener API into our standard format
    PURE DATA TRANSFORMATION - NO JUDGMENTS OR SCORING
    
    Args:
        pair_data: Raw pair data from API
        
    Returns:
        dict: Processed token data in standard format (raw data only)
    """
    try:
        # Extract base token info
        base_token = pair_data.get('baseToken', {})
        
        # Calculate pair age
        pair_created_at = pair_data.get('pairCreatedAt')
        age_hours = 0
        if pair_created_at:
            created_time = datetime.fromtimestamp(pair_created_at / 1000)  # Convert ms to seconds
            age_hours = (datetime.now() - created_time).total_seconds() / 3600
        
        # Extract transaction data
        txns = pair_data.get('txns', {})
        volume = pair_data.get('volume', {})
        price_change = pair_data.get('priceChange', {})
        liquidity = pair_data.get('liquidity', {})
        
        # Calculate buy/sell ratio (raw calculation, no interpretation)
        buy_count = 0
        sell_count = 0
        for timeframe, txn_data in txns.items():
            if isinstance(txn_data, dict):
                buy_count += txn_data.get('buys', 0)
                sell_count += txn_data.get('sells', 0)
        
        total_txns = buy_count + sell_count
        buy_ratio = (buy_count / total_txns) if total_txns > 0 else 0.5
        
        # Process the token data - RAW METRICS ONLY
        processed_token = {
            # Core identification
            "address": base_token.get('address', ''),
            "symbol": base_token.get('symbol', 'Unknown'),
            "name": base_token.get('name', ''),
            
            # Raw price data
            "price_usd": float(pair_data.get('priceUsd', 0)),
            
            # Raw liquidity data
            "liquidity_usd": float(liquidity.get('usd', 0)),
            
            # Raw volume data
            "volume_24h": float(volume.get('h24', 0)),
            "volume_1h": float(volume.get('h1', 0)),
            "volume_5m": float(volume.get('m5', 0)),
            
            # Raw time data
            "age_hours": age_hours,
            
            # Raw market cap data
            "market_cap": float(pair_data.get('marketCap', 0)),
            "fdv": float(pair_data.get('fdv', 0)),
            
            # Raw price change data
            "price_change_24h": float(price_change.get('h24', 0)),
            "price_change_1h": float(price_change.get('h1', 0)),
            "price_change_5m": float(price_change.get('m5', 0)),
            "price_change_15m": 0.0,  # Will be calculated if available
            
            # Raw transaction data
            "buy_count": buy_count,
            "sell_count": sell_count,
            "buy_ratio": buy_ratio,
            "total_transactions": total_txns,
            
            # Raw DEX data
            "pair_address": pair_data.get('pairAddress', ''),
            "dex_id": pair_data.get('dexId', ''),
            "chain_id": pair_data.get('chainId', ''),
            "url": pair_data.get('url', ''),
            "labels": pair_data.get('labels', []),
            "boosts_active": pair_data.get('boosts', {}).get('active', 0),
            
            # Placeholders for enrichment data (will be filled by other sources)
            "safety_raw_data": {},      # Will be populated by RugCheck
            "social_raw_data": {},      # Will be populated by TweetScout
            "whale_raw_data": {},       # Will be populated by whale analysis
            
            # AI analysis placeholders (will be filled by AI agent)
            "ai_overall_score": 0,
            "ai_recommendation": "",
            "ai_risk_assessment": "",
            "ai_reasoning": "",
            
            # Enrichment metadata
            "enriched": False,
            "enrichment_timestamp": "",
            "data_sources_used": {
                "dexscreener": True,
                "rugcheck": False,
                "tweetscout": False
            },
            
            # Data collection timestamp
            "data_collection_timestamp": datetime.now().isoformat()
        }
        
        return processed_token
        
    except Exception as e:
        logger.error(f"Error processing pair data: {e}")
        return {}

# ============================================================================
# PURE DATA COLLECTION FUNCTIONS - NO HARDCODED JUDGMENT LOGIC
# ============================================================================

def get_boosted_tokens_latest(chain_filter: str = "solana") -> List[Dict[str, Any]]:
    """
    Get latest boosted (trending/promoted) tokens - PURE DATA COLLECTION
    
    Args:
        chain_filter: Filter by blockchain (default: solana)
        
    Returns:
        list: List of raw boosted token data
    """
    cache_key = f"dex_boosted_latest_{chain_filter}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data
    
    logger.info("Fetching latest boosted tokens from DexScreener")
    
    try:
        data = make_api_call(ENDPOINTS["token_boosts_latest"])
        if not data:
            return []
        
        # Filter by chain if specified
        boosted_tokens = []
        if isinstance(data, list):
            tokens_list = data
        else:
            tokens_list = [data] if data else []
            
        for token_info in tokens_list:
            if chain_filter and token_info.get('chainId') != chain_filter:
                continue
                
            # Get token address and fetch detailed pair data
            token_address = token_info.get('tokenAddress')
            if token_address:
                pairs_data = get_token_pairs(chain_filter, token_address)
                for pair in pairs_data:
                    processed = process_pair_data(pair)
                    if processed:
                        processed['boost_info'] = token_info
                        boosted_tokens.append(processed)
        
        # Cache the results
        cache_data(cache_key, boosted_tokens, ttl_seconds=300)  # 5 minutes
        
        logger.info(f"Found {len(boosted_tokens)} boosted tokens")
        return boosted_tokens
        
    except Exception as e:
        logger.error(f"Error fetching boosted tokens: {e}")
        return []

def get_boosted_tokens_top(chain_filter: str = "solana") -> List[Dict[str, Any]]:
    """
    Get top boosted tokens - PURE DATA COLLECTION
    
    Args:
        chain_filter: Filter by blockchain (default: solana)
        
    Returns:
        list: List of raw top boosted token data
    """
    cache_key = f"dex_boosted_top_{chain_filter}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data
    
    logger.info("Fetching top boosted tokens from DexScreener")
    
    try:
        data = make_api_call(ENDPOINTS["token_boosts_top"])
        if not data:
            return []
        
        # Process similar to latest boosted tokens
        top_tokens = []
        if isinstance(data, list):
            tokens_list = data
        else:
            tokens_list = [data] if data else []
            
        for token_info in tokens_list:
            if chain_filter and token_info.get('chainId') != chain_filter:
                continue
                
            token_address = token_info.get('tokenAddress')
            if token_address:
                pairs_data = get_token_pairs(chain_filter, token_address)
                for pair in pairs_data:
                    processed = process_pair_data(pair)
                    if processed:
                        processed['boost_info'] = token_info
                        top_tokens.append(processed)
        
        # Cache the results
        cache_data(cache_key, top_tokens, ttl_seconds=300)
        
        logger.info(f"Found {len(top_tokens)} top boosted tokens")
        return top_tokens
        
    except Exception as e:
        logger.error(f"Error fetching top boosted tokens: {e}")
        return []

def get_latest_token_profiles(chain_filter: str = "solana") -> List[Dict[str, Any]]:
    """
    Get tokens with latest profiles - PURE DATA COLLECTION
    
    Args:
        chain_filter: Filter by blockchain (default: solana)
        
    Returns:
        list: List of raw tokens with profile data
    """
    cache_key = f"dex_profiles_latest_{chain_filter}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data
    
    logger.info("Fetching latest token profiles from DexScreener")
    
    try:
        data = make_api_call(ENDPOINTS["token_profiles_latest"])
        if not data:
            return []
        
        profile_tokens = []
        if isinstance(data, list):
            tokens_list = data
        else:
            tokens_list = [data] if data else []
            
        for token_info in tokens_list:
            if chain_filter and token_info.get('chainId') != chain_filter:
                continue
                
            token_address = token_info.get('tokenAddress')
            if token_address:
                pairs_data = get_token_pairs(chain_filter, token_address)
                for pair in pairs_data:
                    processed = process_pair_data(pair)
                    if processed:
                        processed['profile_info'] = token_info
                        profile_tokens.append(processed)
        
        # Cache the results
        cache_data(cache_key, profile_tokens, ttl_seconds=600)  # 10 minutes
        
        logger.info(f"Found {len(profile_tokens)} tokens with latest profiles")
        return profile_tokens
        
    except Exception as e:
        logger.error(f"Error fetching latest token profiles: {e}")
        return []

def search_tokens_by_query(query: str, max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Search for tokens using flexible query terms - PURE DATA COLLECTION
    
    Args:
        query: Search query (determined by AI agent)
        max_results: Maximum number of results to return
        
    Returns:
        list: List of raw tokens matching the search query
    """
    cache_key = f"dex_search_{query}_{max_results}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data
    
    logger.info(f"Searching DexScreener for query: '{query}'")
    
    try:
        params = {"q": query}
        data = make_api_call(ENDPOINTS["search"], params=params)
        
        if not data or 'pairs' not in data:
            logger.warning(f"No results found for query: '{query}'")
            return []
        
        search_results = []
        pairs = data['pairs'][:max_results]  # Limit results
        
        for pair in pairs:
            processed = process_pair_data(pair)
            if processed:
                processed['search_query'] = query
                search_results.append(processed)
        
        # Cache the results
        cache_data(cache_key, search_results, ttl_seconds=180)  # 3 minutes
        
        logger.info(f"Found {len(search_results)} tokens for query: '{query}'")
        return search_results
        
    except Exception as e:
        logger.error(f"Error searching tokens with query '{query}': {e}")
        return []

def get_token_details_batch(chain_id: str, token_addresses: List[str]) -> List[Dict[str, Any]]:
    """
    Get detailed information for multiple tokens - PURE DATA COLLECTION
    
    Args:
        chain_id: Blockchain identifier (e.g., "solana")
        token_addresses: List of token addresses (max 30)
        
    Returns:
        list: List of raw detailed token information
    """
    # Limit to 30 addresses as per API docs
    if len(token_addresses) > 30:
        logger.warning(f"Too many addresses ({len(token_addresses)}), limiting to 30")
        token_addresses = token_addresses[:30]
    
    addresses_str = ",".join(token_addresses)
    cache_key = f"dex_token_details_{chain_id}_{len(token_addresses)}_{hash(addresses_str)}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data
    
    logger.info(f"Fetching detailed data for {len(token_addresses)} tokens")
    
    try:
        url = f"{ENDPOINTS['tokens_detail']}/{chain_id}/{addresses_str}"
        data = make_api_call(url)
        
        if not data:
            return []
        
        detailed_tokens = []
        if isinstance(data, list):
            pairs_list = data
        else:
            pairs_list = [data] if data else []
            
        for pair in pairs_list:
            processed = process_pair_data(pair)
            if processed:
                detailed_tokens.append(processed)
        
        # Cache the results
        cache_data(cache_key, detailed_tokens, ttl_seconds=300)  # 5 minutes
        
        logger.info(f"Retrieved detailed data for {len(detailed_tokens)} tokens")
        return detailed_tokens
        
    except Exception as e:
        logger.error(f"Error fetching token details: {e}")
        return []

def get_token_pairs(chain_id: str, token_address: str) -> List[Dict[str, Any]]:
    """
    Get all trading pairs for a specific token - PURE DATA COLLECTION
    
    Args:
        chain_id: Blockchain identifier (e.g., "solana")
        token_address: Token address
        
    Returns:
        list: List of raw trading pairs for the token
    """
    cache_key = f"dex_token_pairs_{chain_id}_{token_address}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data
    
    try:
        url = f"{ENDPOINTS['token_pairs']}/{chain_id}/{token_address}"
        data = make_api_call(url)
        
        if not data:
            return []
        
        pairs_list = data if isinstance(data, list) else [data]
        
        # Cache the results
        cache_data(cache_key, pairs_list, ttl_seconds=300)  # 5 minutes
        
        return pairs_list
        
    except Exception as e:
        logger.error(f"Error fetching token pairs for {token_address}: {e}")
        return []

# ============================================================================
# PURE DATA FILTERING TOOLS (NO JUDGMENT - MECHANICAL FILTERING ONLY)
# ============================================================================

def filter_tokens_by_age(tokens: List[Dict[str, Any]], max_age_hours: float) -> List[Dict[str, Any]]:
    """
    Mechanical filter: Remove tokens older than specified age
    NO JUDGMENT LOGIC - Pure filtering tool for AI agent
    """
    filtered = [token for token in tokens if token.get('age_hours', 0) <= max_age_hours]
    logger.info(f"Filtered {len(tokens)} tokens to {len(filtered)} by age <= {max_age_hours}h")
    return filtered

def filter_tokens_by_liquidity(tokens: List[Dict[str, Any]], 
                              min_liquidity_usd: float, 
                              max_liquidity_usd: float = None) -> List[Dict[str, Any]]:
    """
    Mechanical filter: Remove tokens outside liquidity range
    NO JUDGMENT LOGIC - Pure filtering tool for AI agent
    """
    filtered = []
    for token in tokens:
        liquidity = token.get('liquidity_usd', 0)
        if liquidity >= min_liquidity_usd:
            if max_liquidity_usd is None or liquidity <= max_liquidity_usd:
                filtered.append(token)
    
    logger.info(f"Filtered {len(tokens)} tokens to {len(filtered)} by liquidity ${min_liquidity_usd:,.0f}+")
    return filtered

def filter_tokens_by_volume(tokens: List[Dict[str, Any]], 
                           min_volume_24h: float) -> List[Dict[str, Any]]:
    """
    Mechanical filter: Remove tokens with insufficient 24h volume
    NO JUDGMENT LOGIC - Pure filtering tool for AI agent
    """
    filtered = [token for token in tokens if token.get('volume_24h', 0) >= min_volume_24h]
    logger.info(f"Filtered {len(tokens)} tokens to {len(filtered)} by volume >= ${min_volume_24h:,.0f}")
    return filtered

def filter_tokens_by_market_cap(tokens: List[Dict[str, Any]], 
                               min_market_cap: float, 
                               max_market_cap: float = None) -> List[Dict[str, Any]]:
    """
    Mechanical filter: Remove tokens outside market cap range
    NO JUDGMENT LOGIC - Pure filtering tool for AI agent
    """
    filtered = []
    for token in tokens:
        market_cap = token.get('market_cap', 0) or token.get('fdv', 0)
        if market_cap >= min_market_cap:
            if max_market_cap is None or market_cap <= max_market_cap:
                filtered.append(token)
    
    logger.info(f"Filtered {len(tokens)} tokens to {len(filtered)} by market cap ${min_market_cap:,.0f}+")
    return filtered

def filter_tokens_by_price_change(tokens: List[Dict[str, Any]], 
                                 min_change_24h: float = None,
                                 max_change_24h: float = None) -> List[Dict[str, Any]]:
    """
    Mechanical filter: Remove tokens outside price change range
    NO JUDGMENT LOGIC - Pure filtering tool for AI agent
    """
    filtered = []
    for token in tokens:
        change_24h = token.get('price_change_24h', 0)
        
        include_token = True
        if min_change_24h is not None and change_24h < min_change_24h:
            include_token = False
        if max_change_24h is not None and change_24h > max_change_24h:
            include_token = False
            
        if include_token:
            filtered.append(token)
    
    logger.info(f"Filtered {len(tokens)} tokens to {len(filtered)} by price change criteria")
    return filtered

def sort_tokens_by_metric(tokens: List[Dict[str, Any]], 
                         sort_by: str, 
                         descending: bool = True) -> List[Dict[str, Any]]:
    """
    Mechanical sort: Sort tokens by specified metric
    NO JUDGMENT LOGIC - Pure sorting tool for AI agent
    """
    try:
        sorted_tokens = sorted(tokens, 
                             key=lambda x: x.get(sort_by, 0), 
                             reverse=descending)
        
        logger.info(f"Sorted {len(tokens)} tokens by {sort_by} ({'desc' if descending else 'asc'})")
        return sorted_tokens
        
    except Exception as e:
        logger.error(f"Error sorting tokens by {sort_by}: {e}")
        return tokens

# ============================================================================
# AI-DRIVEN DISCOVERY TOOLS (FOR AI AGENT USE)
# ============================================================================

def get_all_available_data_sources() -> List[str]:
    """
    Return all available data source types for AI agent to choose from
    """
    return [
        "boosted_latest",    # Latest boosted/trending tokens
        "boosted_top",       # Top boosted tokens by activity
        "profiles_latest",   # Tokens with latest profile updates
        "search_custom"      # Custom search with AI-determined terms
    ]

def get_discovery_capabilities() -> Dict[str, Any]:
    """
    Return discovery capabilities for AI agent planning
    """
    return {
        "data_sources": get_all_available_data_sources(),
        "filtering_options": [
            "age_hours", "liquidity_usd", "volume_24h", "market_cap", 
            "price_change_24h", "price_change_1h", "buy_ratio"
        ],
        "sorting_metrics": [
            "volume_24h", "liquidity_usd", "price_change_24h", "price_change_1h",
            "age_hours", "market_cap", "buy_ratio", "total_transactions"
        ],
        "max_results_per_source": 100,
        "cache_duration_seconds": 300,
        "rate_limits": RATE_LIMITS
    }

# ============================================================================
# REMOVED HARDCODED LOGIC FUNCTIONS
# ============================================================================

# REMOVED: get_comprehensive_token_discovery() with hardcoded search terms
# REMOVED: Fixed strategy definitions
# REMOVED: Hardcoded quality thresholds
# REMOVED: Legacy get_top_tokens() with hardcoded filtering

# AI Agent will now use individual data source functions and make its own
# strategic decisions about:
# - Which data sources to query
# - What search terms to use  
# - What filtering criteria to apply
# - How to prioritize and rank results

# ============================================================================
# Legacy Functions (minimal compatibility layer)
# ============================================================================

def get_top_tokens(chain="solana", max_results=20):
    """
    Legacy compatibility function - now returns raw boosted tokens
    AI agent should use individual source functions instead
    """
    logger.warning("Legacy get_top_tokens called - AI agent should use specific source functions")
    
    # Return raw boosted tokens without any hardcoded filtering
    tokens = get_boosted_tokens_latest(chain)
    return tokens[:max_results]

def get_token_details(token_address):
    """
    Legacy compatibility function
    """
    pairs_data = get_token_pairs("solana", token_address)
    return pairs_data
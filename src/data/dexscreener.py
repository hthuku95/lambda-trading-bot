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
        
        # Calculate buy/sell ratio using all timeframes (raw calculation, no interpretation)
        buy_count = 0
        sell_count = 0
        buyers_5m = 0
        sellers_5m = 0
        for timeframe, txn_data in txns.items():
            if isinstance(txn_data, dict):
                buy_count += txn_data.get('buys', 0)
                sell_count += txn_data.get('sells', 0)
                if timeframe == 'm5':
                    buyers_5m = txn_data.get('buyers', 0)   # Unique buyers (better pressure signal)
                    sellers_5m = txn_data.get('sellers', 0) # Unique sellers

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
            
            # Raw volume data (including 6h to fill h1–h24 gap)
            "volume_24h": float(volume.get('h24', 0)),
            "volume_6h": float(volume.get('h6', 0)),
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
            "buyers_5m": buyers_5m,    # Unique buyers in last 5 min (stronger pressure signal)
            "sellers_5m": sellers_5m,  # Unique sellers in last 5 min
            "buy_ratio": buy_ratio,
            "total_transactions": total_txns,

            # Raw liquidity breakdown
            "liquidity_usd": float(liquidity.get('usd', 0)),
            "liquidity_base": float(liquidity.get('base', 0)),   # Base token liquidity
            "liquidity_quote": float(liquidity.get('quote', 0)), # Quote token liquidity

            # Raw DEX data
            "pair_address": pair_data.get('pairAddress', ''),
            "dex_id": pair_data.get('dexId', ''),
            "chain_id": pair_data.get('chainId', ''),
            "url": pair_data.get('url', ''),
            "labels": pair_data.get('labels', []),
            "boosts_active": pair_data.get('boosts', {}).get('active', 0),
            
            # Placeholders for enrichment data (will be filled by other sources)
            "safety_raw_data": {},      # Will be populated by RugCheck
            "social_raw_data": {},      # Will be populated by Social Intelligence (Nansen + DexScreener)
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
                "social": False
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
# NEW DISCOVERY ENDPOINTS
# ============================================================================

def get_community_takeover_tokens(chain_filter: str = "solana") -> List[Dict[str, Any]]:
    """
    Get tokens undergoing community governance takeovers — strong community backing signal.
    Uses DexScreener /community-takeovers/latest/v1 endpoint.
    """
    cache_key = f"dexscreener_community_takeovers_{chain_filter}"
    cached = get_cached_data(cache_key)
    if cached:
        return cached

    url = f"{DEXSCREENER_BASE_URL}/community-takeovers/latest/v1"
    data = make_api_call(url, timeout=15)

    if not data:
        return []

    pairs = data if isinstance(data, list) else data.get('pairs', [])
    tokens = []
    for pair in pairs:
        if chain_filter and pair.get('chainId', '').lower() != chain_filter.lower():
            continue
        processed = process_pair_data(pair)
        if processed:
            processed['discovery_source'] = 'community_takeover'
            tokens.append(processed)

    cache_data(cache_key, tokens, ttl_seconds=300)
    logger.info(f"Found {len(tokens)} community takeover tokens on {chain_filter}")
    return tokens


def get_promoted_tokens(chain_filter: str = "solana") -> List[Dict[str, Any]]:
    """
    Get currently running paid promotions — detect over-hyped/manipulated tokens.
    Uses DexScreener /ads/latest/v1 endpoint.
    """
    cache_key = f"dexscreener_ads_{chain_filter}"
    cached = get_cached_data(cache_key)
    if cached:
        return cached

    url = f"{DEXSCREENER_BASE_URL}/ads/latest/v1"
    data = make_api_call(url, timeout=15)

    if not data:
        return []

    pairs = data if isinstance(data, list) else data.get('pairs', [])
    tokens = []
    for pair in pairs:
        if chain_filter and pair.get('chainId', '').lower() != chain_filter.lower():
            continue
        processed = process_pair_data(pair)
        if processed:
            processed['discovery_source'] = 'promoted_ad'
            tokens.append(processed)

    cache_data(cache_key, tokens, ttl_seconds=300)
    logger.info(f"Found {len(tokens)} promoted tokens on {chain_filter}")
    return tokens


# ============================================================================
# NEW ENHANCED TOOLS - 100% DexScreener API Coverage
# ============================================================================

def get_token_orders(chain_id: str, token_address: str) -> Dict[str, Any]:
    """
    Get order book information for a token

    Critical for understanding:
    - Market depth
    - Pending whale orders
    - Order flow patterns
    - Liquidity availability

    Args:
        chain_id: Blockchain identifier (e.g., "solana")
        token_address: Token address

    Returns:
        dict: Order book data including pending orders, status, and history
    """
    cache_key = f"dex_orders_{chain_id}_{token_address}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data

    logger.info(f"Fetching order book for token: {token_address}")

    try:
        url = f"{ENDPOINTS['pair_detail']}/orders/v1/{chain_id}/{token_address}"
        data = make_api_call(url)

        if not data:
            return {
                'token_address': token_address,
                'chain_id': chain_id,
                'has_orders': False,
                'orders_data': {},
                'error': 'No order data available'
            }

        result = {
            'token_address': token_address,
            'chain_id': chain_id,
            'has_orders': bool(data),
            'orders_data': data,
            'data_collection_timestamp': datetime.now().isoformat()
        }

        # Cache for 2 minutes (orders change frequently)
        cache_data(cache_key, result, ttl_seconds=120)

        logger.info(f"Retrieved order data for {token_address}")
        return result

    except Exception as e:
        logger.error(f"Error fetching orders for {token_address}: {e}")
        return {
            'token_address': token_address,
            'chain_id': chain_id,
            'has_orders': False,
            'orders_data': {},
            'error': str(e)
        }

def get_pair_details(chain_id: str, pair_address: str) -> Dict[str, Any]:
    """
    Get detailed information for a specific trading pair

    Provides deeper analysis than bulk endpoints:
    - Enhanced transaction data
    - Detailed liquidity breakdown
    - Pair-specific metrics
    - Real-time accuracy

    Args:
        chain_id: Blockchain identifier (e.g., "solana")
        pair_address: DEX pair address

    Returns:
        dict: Comprehensive pair data
    """
    cache_key = f"dex_pair_detail_{chain_id}_{pair_address}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data

    logger.info(f"Fetching detailed data for pair: {pair_address}")

    try:
        url = f"{ENDPOINTS['pair_detail']}/{chain_id}/{pair_address}"
        data = make_api_call(url)

        if not data or 'pairs' not in data:
            logger.warning(f"No pair details found for: {pair_address}")
            return {}

        # Process the most detailed pair data
        pairs = data.get('pairs', [])
        if not pairs:
            return {}

        pair = pairs[0]
        processed = process_pair_data(pair)

        # Cache for 3 minutes
        cache_data(cache_key, processed, ttl_seconds=180)

        logger.info(f"Retrieved detailed data for pair: {pair_address}")
        return processed

    except Exception as e:
        logger.error(f"Error fetching pair details for {pair_address}: {e}")
        return {}

def get_token_social_info(chain_id: str, token_address: str) -> Dict[str, Any]:
    """
    Extract social media and project information for a token

    Critical for legitimacy verification:
    - Official website
    - Twitter/X presence
    - Telegram community
    - Discord server
    - Project branding

    Args:
        chain_id: Blockchain identifier (e.g., "solana")
        token_address: Token address

    Returns:
        dict: Social links, websites, imagery, and project info
    """
    cache_key = f"dex_social_{chain_id}_{token_address}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data

    logger.info(f"Fetching social info for token: {token_address}")

    try:
        pairs_data = get_token_pairs(chain_id, token_address)

        if not pairs_data:
            return {
                'token_address': token_address,
                'has_social_data': False,
                'error': 'No pair data available'
            }

        # Extract info from first pair (usually most liquid)
        pair = pairs_data[0]
        info = pair.get('info', {})

        # Extract social links by type
        socials = info.get('socials', [])
        social_dict = {}
        for social in socials:
            social_type = social.get('type', 'unknown')
            social_dict[social_type] = social.get('url', '')

        social_data = {
            'token_address': token_address,
            'chain_id': chain_id,
            'has_social_data': True,

            # Visual branding
            'image_url': info.get('imageUrl', ''),
            'has_image': bool(info.get('imageUrl', '')),

            # Websites
            'websites': info.get('websites', []),
            'website_count': len(info.get('websites', [])),
            'has_website': len(info.get('websites', [])) > 0,
            'primary_website': info.get('websites', [{}])[0].get('url', '') if info.get('websites') else '',

            # Social media
            'socials': socials,
            'social_links': social_dict,
            'social_count': len(socials),

            # Specific platforms
            'has_twitter': 'twitter' in social_dict,
            'twitter_url': social_dict.get('twitter', ''),
            'has_telegram': 'telegram' in social_dict,
            'telegram_url': social_dict.get('telegram', ''),
            'has_discord': 'discord' in social_dict,
            'discord_url': social_dict.get('discord', ''),

            # Legitimacy score
            'legitimacy_score': (
                (10 if info.get('imageUrl') else 0) +
                (20 if len(info.get('websites', [])) > 0 else 0) +
                (30 if 'twitter' in social_dict else 0) +
                (20 if 'telegram' in social_dict else 0) +
                (20 if 'discord' in social_dict else 0)
            ),

            'data_collection_timestamp': datetime.now().isoformat()
        }

        # Cache for 30 minutes (social info doesn't change often)
        cache_data(cache_key, social_data, ttl_seconds=1800)

        logger.info(f"Retrieved social info for {token_address} (legitimacy: {social_data['legitimacy_score']}/100)")
        return social_data

    except Exception as e:
        logger.error(f"Error fetching social info for {token_address}: {e}")
        return {
            'token_address': token_address,
            'chain_id': chain_id,
            'has_social_data': False,
            'error': str(e)
        }

def compare_token_pairs(chain_id: str, token_address: str) -> Dict[str, Any]:
    """
    Compare all trading pairs for a token across different DEXs

    Helps identify:
    - Best execution venue
    - Arbitrage opportunities
    - Liquidity fragmentation
    - Price discrepancies

    Args:
        chain_id: Blockchain identifier (e.g., "solana")
        token_address: Token address

    Returns:
        dict: Comparison of all pairs with recommendations
    """
    cache_key = f"dex_compare_pairs_{chain_id}_{token_address}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data

    logger.info(f"Comparing all pairs for token: {token_address}")

    try:
        pairs_data = get_token_pairs(chain_id, token_address)

        if not pairs_data:
            return {
                'token_address': token_address,
                'error': 'No pairs found'
            }

        # Process all pairs
        processed_pairs = []
        for pair in pairs_data:
            processed = process_pair_data(pair)
            if processed:
                processed_pairs.append(processed)

        if not processed_pairs:
            return {
                'token_address': token_address,
                'error': 'No valid pairs processed'
            }

        # Sort by liquidity (most liquid first)
        sorted_by_liquidity = sorted(processed_pairs,
                                     key=lambda x: x.get('liquidity_usd', 0),
                                     reverse=True)

        # Find best pair for trading (highest liquidity + volume score)
        best_pair = None
        best_score = 0

        for pair in processed_pairs:
            # Score = liquidity + (volume * 0.1)
            liquidity = pair.get('liquidity_usd', 0)
            volume = pair.get('volume_24h', 0)
            score = liquidity + (volume * 0.1)

            if score > best_score:
                best_score = score
                best_pair = pair

        # Calculate price variance across pairs
        prices = [p.get('price_usd', 0) for p in processed_pairs if p.get('price_usd', 0) > 0]
        price_variance = 0
        has_arbitrage = False

        if len(prices) > 1:
            max_price = max(prices)
            min_price = min(prices)
            price_variance = (max_price - min_price) / min_price * 100 if min_price > 0 else 0
            has_arbitrage = price_variance > 2  # >2% difference = arbitrage opportunity

        # Calculate total liquidity across all pairs
        total_liquidity = sum(p.get('liquidity_usd', 0) for p in processed_pairs)
        total_volume_24h = sum(p.get('volume_24h', 0) for p in processed_pairs)

        result = {
            'token_address': token_address,
            'chain_id': chain_id,
            'total_pairs': len(processed_pairs),
            'all_pairs': processed_pairs,

            # Best pair recommendations
            'best_pair_for_trading': best_pair,
            'most_liquid_pair': sorted_by_liquidity[0] if sorted_by_liquidity else None,

            # Aggregate metrics
            'total_liquidity_usd': total_liquidity,
            'total_volume_24h': total_volume_24h,
            'average_liquidity_per_pair': total_liquidity / len(processed_pairs) if processed_pairs else 0,

            # Price analysis
            'price_variance_percent': price_variance,
            'has_arbitrage_opportunity': has_arbitrage,
            'min_price_usd': min(prices) if prices else 0,
            'max_price_usd': max(prices) if prices else 0,

            # Recommendations
            'recommendation': f"Use {best_pair.get('dex_id', 'N/A')} pair for best execution" if best_pair else "No recommendation available",
            'liquidity_concentration': (sorted_by_liquidity[0].get('liquidity_usd', 0) / total_liquidity * 100) if total_liquidity > 0 and sorted_by_liquidity else 0,

            'data_collection_timestamp': datetime.now().isoformat()
        }

        # Cache for 5 minutes
        cache_data(cache_key, result, ttl_seconds=300)

        logger.info(f"Compared {len(processed_pairs)} pairs for {token_address}")
        return result

    except Exception as e:
        logger.error(f"Error comparing pairs for {token_address}: {e}")
        return {
            'token_address': token_address,
            'error': str(e)
        }

def get_token_age_analysis(chain_id: str, token_address: str) -> Dict[str, Any]:
    """
    Detailed analysis of token age and pair creation history

    Important for risk assessment:
    - Very new tokens = higher risk
    - Multiple new pairs = potential rug setup
    - Oldest pair = original launch venue

    Args:
        chain_id: Blockchain identifier (e.g., "solana")
        token_address: Token address

    Returns:
        dict: Age analysis with risk indicators
    """
    cache_key = f"dex_age_analysis_{chain_id}_{token_address}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data

    logger.info(f"Analyzing token age for: {token_address}")

    try:
        pairs_data = get_token_pairs(chain_id, token_address)

        if not pairs_data:
            return {
                'token_address': token_address,
                'error': 'No pairs found for age analysis'
            }

        pair_ages = []
        for pair in pairs_data:
            created_at = pair.get('pairCreatedAt')
            if created_at:
                created_time = datetime.fromtimestamp(created_at / 1000)
                age_hours = (datetime.now() - created_time).total_seconds() / 3600
                pair_ages.append({
                    'pair_address': pair.get('pairAddress'),
                    'dex_id': pair.get('dexId'),
                    'created_at': created_time.isoformat(),
                    'age_hours': age_hours,
                    'age_days': age_hours / 24,
                    'liquidity_usd': pair.get('liquidity', {}).get('usd', 0)
                })

        if not pair_ages:
            return {
                'token_address': token_address,
                'error': 'No pair creation timestamps available'
            }

        # Sort by age (oldest first)
        pair_ages.sort(key=lambda x: x['age_hours'], reverse=True)

        oldest_pair = pair_ages[0]
        newest_pair = pair_ages[-1]
        average_age = sum(p['age_hours'] for p in pair_ages) / len(pair_ages)

        # Risk assessment based on oldest pair
        risk_level = 'unknown'
        risk_score = 0

        if oldest_pair['age_hours'] < 1:
            risk_level = 'extreme'
            risk_score = 100
        elif oldest_pair['age_hours'] < 24:
            risk_level = 'very_high'
            risk_score = 80
        elif oldest_pair['age_hours'] < 168:  # Less than 1 week
            risk_level = 'high'
            risk_score = 60
        elif oldest_pair['age_hours'] < 720:  # Less than 1 month
            risk_level = 'medium'
            risk_score = 40
        else:
            risk_level = 'low'
            risk_score = 20

        # Additional risk factors
        if len(pair_ages) == 1:
            risk_notes = "Single pair only - limited trading venues"
        elif newest_pair['age_hours'] < 24 and len(pair_ages) > 3:
            risk_notes = "Multiple new pairs created recently - possible manipulation setup"
        else:
            risk_notes = "Normal pair creation pattern"

        result = {
            'token_address': token_address,
            'chain_id': chain_id,
            'total_pairs': len(pair_ages),

            # Age metrics
            'oldest_pair': oldest_pair,
            'newest_pair': newest_pair,
            'average_age_hours': average_age,
            'average_age_days': average_age / 24,
            'all_pair_ages': pair_ages,

            # Risk assessment
            'risk_level': risk_level,
            'risk_score': risk_score,
            'risk_notes': risk_notes,

            # Flags
            'is_very_new': oldest_pair['age_hours'] < 24,
            'is_less_than_week': oldest_pair['age_hours'] < 168,
            'has_multiple_recent_pairs': sum(1 for p in pair_ages if p['age_hours'] < 24) > 2,

            # Recommendation
            'recommendation': f"Token is {risk_level} risk based on age ({oldest_pair['age_days']:.1f} days old)",

            'data_collection_timestamp': datetime.now().isoformat()
        }

        # Cache for 10 minutes
        cache_data(cache_key, result, ttl_seconds=600)

        logger.info(f"Age analysis for {token_address}: {risk_level} risk ({oldest_pair['age_days']:.1f} days)")
        return result

    except Exception as e:
        logger.error(f"Error analyzing token age for {token_address}: {e}")
        return {
            'token_address': token_address,
            'error': str(e)
        }

def analyze_boost_activity(chain_id: str, token_address: str) -> Dict[str, Any]:
    """
    Analyze promotional boost activity for a token

    Boosts indicate:
    - Marketing spend (project has funding)
    - Coordinated promotion
    - Trending potential
    - Developer engagement

    Args:
        chain_id: Blockchain identifier (e.g., "solana")
        token_address: Token address

    Returns:
        dict: Boost activity analysis and historical data
    """
    cache_key = f"dex_boost_analysis_{chain_id}_{token_address}"
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data

    logger.info(f"Analyzing boost activity for: {token_address}")

    try:
        # Check if token is in current boost lists
        boosted_latest = get_boosted_tokens_latest(chain_id)
        boosted_top = get_boosted_tokens_top(chain_id)

        is_boosted_latest = any(t.get('address') == token_address for t in boosted_latest)
        is_boosted_top = any(t.get('address') == token_address for t in boosted_top)

        # Get detailed boost info from pairs
        pairs_data = get_token_pairs(chain_id, token_address)
        active_boosts = 0
        boost_info = {}

        if pairs_data:
            pair = pairs_data[0]
            boosts_data = pair.get('boosts', {})
            active_boosts = boosts_data.get('active', 0)

            # Check if boost_info exists in processed token
            for token in boosted_latest + boosted_top:
                if token.get('address') == token_address:
                    boost_info = token.get('boost_info', {})
                    break

        # Promotion level classification
        if active_boosts >= 5:
            promotion_level = 'very_high'
            promotion_score = 100
        elif active_boosts >= 3:
            promotion_level = 'high'
            promotion_score = 75
        elif active_boosts > 0:
            promotion_level = 'medium'
            promotion_score = 50
        else:
            promotion_level = 'none'
            promotion_score = 0

        result = {
            'token_address': token_address,
            'chain_id': chain_id,

            # Boost status
            'is_currently_boosted': is_boosted_latest or is_boosted_top,
            'in_latest_boosts': is_boosted_latest,
            'in_top_boosts': is_boosted_top,
            'active_boost_count': active_boosts,
            'boost_details': boost_info,

            # Analysis
            'has_marketing_budget': active_boosts > 0,
            'promotion_level': promotion_level,
            'promotion_score': promotion_score,

            # Insights
            'is_heavily_promoted': active_boosts >= 5,
            'trending_potential': is_boosted_top,

            # Recommendation
            'recommendation': (
                f"{'High' if active_boosts >= 3 else 'Medium' if active_boosts > 0 else 'No'} marketing activity detected"
            ),

            'data_collection_timestamp': datetime.now().isoformat()
        }

        # Cache for 5 minutes (boosts change frequently)
        cache_data(cache_key, result, ttl_seconds=300)

        logger.info(f"Boost analysis for {token_address}: {promotion_level} promotion ({active_boosts} active)")
        return result

    except Exception as e:
        logger.error(f"Error analyzing boost activity for {token_address}: {e}")
        return {
            'token_address': token_address,
            'chain_id': chain_id,
            'error': str(e)
        }

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
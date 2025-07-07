# src/data/social_intelligence.py
"""
Social Intelligence API Integration - PURE DATA COLLECTION ONLY
Uses TweetScout API for crypto-specific social data collection
ZERO hardcoded judgment logic - AI agent makes all assessments
"""
import os
import requests
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from src.memory.cache import get_cached_data, cache_data
from src.data.dexscreener import get_token_pairs

# Configure logger
logger = logging.getLogger("trading_agent.social_intelligence")

# Load environment variables
load_dotenv()

# API Configuration
TWEETSCOUT_API_KEY = os.getenv("TWEETSCOUT_API_KEY")
TWEETSCOUT_BASE_URL = "https://api.tweetscout.io/v2"

class SocialIntelligenceClient:
    """Social Intelligence Client - Pure Data Collection Only"""
    
    def __init__(self):
        self.tweetscout_api_key = TWEETSCOUT_API_KEY
        self.tweetscout_base_url = TWEETSCOUT_BASE_URL
        
        if self.tweetscout_api_key:
            logger.info("Social Intelligence client initialized with TweetScout API key")
        else:
            logger.warning("Social Intelligence client initialized without TweetScout API key")
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for TweetScout API"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'TradingBot/1.0'
        }
        
        if self.tweetscout_api_key:
            headers['Authorization'] = f'Bearer {self.tweetscout_api_key}'
            
        return headers
    
    def check_api_health(self) -> Dict[str, Any]:
        """Check TweetScout API health and availability"""
        try:
            if not self.tweetscout_api_key:
                return {
                    "healthy": False,
                    "tweetscout_available": False,
                    "error": "No TweetScout API key configured",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Test TweetScout API with a simple account lookup
            headers = self.get_auth_headers()
            
            response = requests.get(
                f"{self.tweetscout_base_url}/account/info",
                headers=headers,
                params={"username": "bitcoin"},
                timeout=10
            )
            
            tweetscout_working = response.status_code == 200
            
            return {
                "healthy": tweetscout_working,
                "tweetscout_available": tweetscout_working,
                "status_code": response.status_code,
                "api_key_configured": bool(self.tweetscout_api_key),
                "response_time_ms": 0,  # Could be measured if needed
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"TweetScout API health check failed: {e}")
            return {
                "healthy": False,
                "tweetscout_available": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_token_social_data_raw(self, token_address: str, token_symbol: str = None) -> Dict[str, Any]:
        """
        Get RAW social data for a token - NO PROCESSING OR JUDGMENT
        Returns pure data for AI agent to analyze
        
        Args:
            token_address: Token contract address
            token_symbol: Token symbol (if known)
            
        Returns:
            Dict containing RAW social data only
        """
        cache_key = f"social_raw_data_{token_address}_{token_symbol}"
        cached_data = get_cached_data(cache_key)
        if cached_data:
            logger.debug(f"Using cached raw social data for {token_symbol or token_address}")
            return cached_data
        
        try:
            # Get token symbol if not provided
            if not token_symbol:
                token_symbol = self._get_token_symbol_from_dex(token_address)
            
            if not token_symbol:
                logger.warning(f"Could not determine symbol for token {token_address}")
                return self._get_empty_social_data(token_address)
            
            # Collect RAW data from all sources
            raw_data = {
                # Data collection metadata
                "token_address": token_address,
                "token_symbol": token_symbol,
                "data_collection_timestamp": datetime.now().isoformat(),
                "data_sources_attempted": [],
                "data_sources_successful": [],
                
                # TweetScout raw data
                "tweetscout_accounts": self._get_tweetscout_accounts_raw(token_symbol),
                "tweetscout_tweets": self._get_tweetscout_tweets_raw(token_symbol),
                "tweetscout_search_results": self._get_tweetscout_search_raw(token_symbol),
                
                # DexScreener social indicators
                "dexscreener_social": self._get_dexscreener_social_raw(token_address),
                
                # Error tracking
                "errors": [],
                "warnings": []
            }
            
            # Cache for 10 minutes
            cache_data(cache_key, raw_data, ttl_seconds=600)
            
            logger.info(f"Successfully collected raw social data for {token_symbol}")
            return raw_data
            
        except Exception as e:
            logger.error(f"Raw social data collection error for {token_symbol or token_address}: {e}")
            return self._get_empty_social_data(token_address, str(e))
    
    def _get_token_symbol_from_dex(self, token_address: str) -> Optional[str]:
        """Extract token symbol from DexScreener data"""
        try:
            pairs_data = get_token_pairs("solana", token_address)
            if pairs_data and len(pairs_data) > 0:
                base_token = pairs_data[0].get('baseToken', {})
                return base_token.get('symbol')
            return None
        except Exception as e:
            logger.error(f"Error getting token symbol from DEX: {e}")
            return None
    
    def _get_tweetscout_accounts_raw(self, token_symbol: str) -> Dict[str, Any]:
        """Get RAW account data from TweetScout - NO PROCESSING"""
        try:
            if not self.tweetscout_api_key:
                return {"error": "No API key", "accounts": []}
            
            headers = self.get_auth_headers()
            
            # Search for accounts related to the token
            search_queries = [
                f"${token_symbol}",
                token_symbol,
                f"{token_symbol}coin",
                f"{token_symbol}token"
            ]
            
            all_accounts = []
            for query in search_queries:
                try:
                    response = requests.get(
                        f"{self.tweetscout_base_url}/account/search",
                        headers=headers,
                        params={"query": query, "limit": 5},
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        accounts_data = response.json()
                        if isinstance(accounts_data, list):
                            for account in accounts_data:
                                # Get detailed account info
                                account_details = self._get_account_details_raw(account.get('username', ''))
                                if account_details:
                                    all_accounts.append(account_details)
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout searching for {query}")
                    continue
                except Exception as e:
                    logger.error(f"Error searching for {query}: {e}")
                    continue
            
            return {
                "search_queries_used": search_queries,
                "accounts_found": all_accounts,
                "total_accounts": len(all_accounts),
                "collection_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"TweetScout accounts error: {e}")
            return {"error": str(e), "accounts": []}
    
    def _get_account_details_raw(self, username: str) -> Optional[Dict[str, Any]]:
        """Get RAW account information from TweetScout - NO PROCESSING"""
        try:
            if not username or not self.tweetscout_api_key:
                return None
            
            headers = self.get_auth_headers()
            
            # Get basic account info
            account_response = requests.get(
                f"{self.tweetscout_base_url}/account/info",
                headers=headers,
                params={"username": username},
                timeout=10
            )
            
            if account_response.status_code != 200:
                return None
            
            account_info = account_response.json()
            
            # Get TweetScout score
            score_response = requests.get(
                f"{self.tweetscout_base_url}/account/score",
                headers=headers,
                params={"username": username},
                timeout=10
            )
            
            tweetscout_score_data = {}
            if score_response.status_code == 200:
                tweetscout_score_data = score_response.json()
            
            # Get top followers
            followers_response = requests.get(
                f"{self.tweetscout_base_url}/account/top-followers",
                headers=headers,
                params={"username": username},
                timeout=10
            )
            
            top_followers_data = {}
            if followers_response.status_code == 200:
                top_followers_data = followers_response.json()
            
            # Return RAW data - NO CALCULATIONS OR INTERPRETATIONS
            return {
                "username": username,
                "account_info_raw": account_info,
                "tweetscout_score_raw": tweetscout_score_data,
                "top_followers_raw": top_followers_data,
                "data_collection_timestamp": datetime.now().isoformat(),
                "api_responses": {
                    "account_status": account_response.status_code,
                    "score_status": score_response.status_code,
                    "followers_status": followers_response.status_code
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting account details for {username}: {e}")
            return None
    
    def _get_tweetscout_tweets_raw(self, token_symbol: str) -> Dict[str, Any]:
        """Get RAW tweets data from TweetScout - NO PROCESSING OR SENTIMENT ANALYSIS"""
        try:
            if not self.tweetscout_api_key:
                return {"error": "No API key", "tweets": []}
            
            headers = self.get_auth_headers()
            
            # Search for tweets mentioning the token
            keywords = [f"${token_symbol}", token_symbol, f"#{token_symbol}"]
            
            all_tweets_data = []
            for keyword in keywords:
                try:
                    response = requests.get(
                        f"{self.tweetscout_base_url}/tweets/search",
                        headers=headers,
                        params={
                            "query": keyword,
                            "limit": 50,
                            "days": 1  # Last 24 hours
                        },
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        tweets_data = response.json()
                        all_tweets_data.append({
                            "keyword": keyword,
                            "raw_response": tweets_data,
                            "api_status": response.status_code,
                            "collection_timestamp": datetime.now().isoformat()
                        })
                
                except Exception as e:
                    logger.error(f"Error searching tweets for {keyword}: {e}")
                    continue
            
            return {
                "keywords_searched": keywords,
                "tweets_data": all_tweets_data,
                "total_keyword_searches": len(all_tweets_data),
                "collection_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Tweet data collection error: {e}")
            return {"error": str(e), "tweets": []}
    
    def _get_tweetscout_search_raw(self, token_symbol: str) -> Dict[str, Any]:
        """Get RAW search results from TweetScout - NO PROCESSING"""
        try:
            if not self.tweetscout_api_key:
                return {"error": "No API key", "search_results": []}
            
            headers = self.get_auth_headers()
            
            # Various search approaches
            search_terms = [
                token_symbol,
                f"${token_symbol}",
                f"{token_symbol} token",
                f"{token_symbol} crypto",
                f"{token_symbol} solana"
            ]
            
            search_results = []
            for term in search_terms:
                try:
                    response = requests.get(
                        f"{self.tweetscout_base_url}/search",
                        headers=headers,
                        params={"q": term, "limit": 20},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        search_results.append({
                            "search_term": term,
                            "raw_response": response.json(),
                            "api_status": response.status_code,
                            "search_timestamp": datetime.now().isoformat()
                        })
                
                except Exception as e:
                    logger.error(f"Error in search for {term}: {e}")
                    continue
            
            return {
                "search_terms_used": search_terms,
                "search_results": search_results,
                "total_searches": len(search_results),
                "collection_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Search data collection error: {e}")
            return {"error": str(e), "search_results": []}
    
    def _get_dexscreener_social_raw(self, token_address: str) -> Dict[str, Any]:
        """Get RAW social indicators from DexScreener - NO PROCESSING"""
        try:
            pairs_data = get_token_pairs("solana", token_address)
            if not pairs_data:
                return {"error": "No pairs data", "social_indicators": {}}
            
            pair = pairs_data[0]
            info = pair.get('info', {})
            
            # Extract RAW social data - NO INTERPRETATION
            return {
                "pair_info_raw": info,
                "boost_data_raw": info.get('boost'),
                "socials_raw": info.get('socials', []),
                "websites_raw": info.get('websites', []),
                "labels_raw": pair.get('labels', []),
                "collection_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"DexScreener social data error: {e}")
            return {"error": str(e), "social_indicators": {}}
    
    def _get_empty_social_data(self, token_address: str, error_msg: str = None) -> Dict[str, Any]:
        """Return empty social data structure when collection fails"""
        return {
            "token_address": token_address,
            "token_symbol": None,
            "data_collection_timestamp": datetime.now().isoformat(),
            "data_sources_attempted": [],
            "data_sources_successful": [],
            
            "tweetscout_accounts": {"error": error_msg or "Collection failed", "accounts": []},
            "tweetscout_tweets": {"error": error_msg or "Collection failed", "tweets": []},
            "tweetscout_search_results": {"error": error_msg or "Collection failed", "search_results": []},
            "dexscreener_social": {"error": error_msg or "Collection failed", "social_indicators": {}},
            
            "errors": [error_msg] if error_msg else [],
            "warnings": ["No social data available"]
        }

# Initialize global client
social_intelligence_client = SocialIntelligenceClient()

# ============================================================================
# API FUNCTIONS - PURE DATA COLLECTION ONLY
# ============================================================================

def check_social_intelligence_health() -> Dict[str, Any]:
    """Check social intelligence APIs health - compatibility function"""
    return social_intelligence_client.check_api_health()

def get_social_intelligence_capabilities() -> Dict[str, bool]:
    """Get social intelligence capabilities - compatibility function"""
    health = check_social_intelligence_health()
    api_working = health.get("healthy", False)
    
    return {
        "social_data_collection": api_working,
        "account_analysis": api_working,
        "tweet_collection": api_working,
        "search_functionality": api_working,
        "api_available": api_working,
        "tweetscout_available": health.get("tweetscout_available", False),
        "credentials_configured": health.get("api_key_configured", False),
        
        # Note: These are data collection capabilities, not judgment capabilities
        "raw_data_only": True,
        "requires_ai_analysis": True
    }

def get_social_data_raw(token_address: str, token_symbol: str = None) -> Dict[str, Any]:
    """
    Get RAW social data for AI analysis - NO HARDCODED JUDGMENTS
    Replaces get_social_sentiment_analysis with pure data collection
    """
    return social_intelligence_client.get_token_social_data_raw(token_address, token_symbol)

def collect_social_intelligence(token_address: str, token_symbol: str = None) -> Dict[str, Any]:
    """
    Primary function for collecting social intelligence data
    Returns pure data for AI agent to analyze and make judgments
    """
    logger.info(f"Collecting social intelligence for {token_symbol or token_address}")
    
    # Get raw data
    raw_data = get_social_data_raw(token_address, token_symbol)
    
    # Add collection metadata
    raw_data["collection_method"] = "pure_data_collection"
    raw_data["requires_ai_analysis"] = True
    raw_data["ai_analysis_suggestions"] = [
        "Analyze account credibility and influence",
        "Assess tweet sentiment and engagement patterns",
        "Evaluate social momentum and viral potential",
        "Determine community health and authenticity",
        "Calculate social activity trends",
        "Identify influencer participation",
        "Assess discussion quality and sentiment"
    ]
    
    logger.info(f"Social intelligence data collected for {token_symbol or token_address}")
    return raw_data

# ============================================================================
# REMOVED FUNCTIONS - ALL HARDCODED JUDGMENT LOGIC ELIMINATED
# ============================================================================

# REMOVED: get_token_social_analysis() - Had hardcoded scoring
# REMOVED: _process_social_data() - Had hardcoded weighting and calculations
# REMOVED: _calculate_viral_score() - Had hardcoded viral potential algorithm
# REMOVED: _calculate_sentiment_score() - Had hardcoded sentiment calculation
# REMOVED: _estimate_mention_growth() - Had hardcoded growth rate logic
# REMOVED: All hardcoded scoring functions and thresholds

# The AI agent now receives pure data and makes all judgments using its knowledge
# and reasoning capabilities rather than predetermined algorithms

# ============================================================================
# COMPATIBILITY FUNCTIONS (for gradual migration)
# ============================================================================

def get_social_sentiment_analysis(token_address: str, token_symbol: str = None) -> Dict[str, Any]:
    """
    Legacy compatibility function - now returns raw data with AI analysis placeholder
    UI components expecting processed data will need to be updated to use AI analysis
    """
    logger.warning("Legacy get_social_sentiment_analysis called - returning raw data only")
    
    raw_data = get_social_data_raw(token_address, token_symbol)
    
    # Return structure similar to old format but with raw data and AI placeholders
    return {
        # Raw data (new)
        "raw_social_data": raw_data,
        
        # Placeholder values for legacy compatibility (will be filled by AI)
        "social_activity_score": 0,      # AI will calculate
        "viral_score": 0,                # AI will calculate
        "sentiment_score": 50,           # AI will calculate
        "trending_potential": False,     # AI will determine
        
        "social_mentions_24h": 0,        # AI will extract from raw data
        "total_engagement": 0,           # AI will calculate
        "unique_users": 0,               # AI will count
        "verified_accounts": 0,          # AI will identify
        
        "mentions_change_1h": 0.0,       # AI will calculate trend
        "social_momentum": 0.0,          # AI will assess
        "community_engagement": 0.0,     # AI will evaluate
        
        # Metadata
        "analysis_timestamp": datetime.now().isoformat(),
        "data_source": "raw_collection_only",
        "requires_ai_processing": True,
        "legacy_compatibility": True,
        "error": None if not raw_data.get("errors") else raw_data["errors"][0]
    }
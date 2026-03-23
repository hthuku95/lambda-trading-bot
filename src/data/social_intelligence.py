# src/data/social_intelligence.py
"""
Social Intelligence API Integration - PURE DATA COLLECTION ONLY
Collects on-chain social signals from DexScreener + Nansen smart money intelligence.
ZERO hardcoded judgment logic - AI agent makes all assessments.
TweetScout has been removed. No stub/deprecated fields are returned.
"""
import os
import requests
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
from src.memory.cache import get_cached_data, cache_data
from src.data.dexscreener import get_token_pairs

# Configure logger
logger = logging.getLogger("trading_agent.social_intelligence")

# Load environment variables
load_dotenv()

class SocialIntelligenceClient:
    """Social Intelligence Client - Pure Data Collection Only"""

    def __init__(self):
        try:
            from src.data.nansen_client import _is_available as nansen_available
            _nansen = nansen_available()
        except Exception:
            _nansen = False
        sources = ["DexScreener"] + (["Nansen"] if _nansen else [])
        logger.info(f"Social Intelligence client initialized (sources: {', '.join(sources)})")

    def check_api_health(self) -> Dict[str, Any]:
        """Check social intelligence health"""
        health: Dict[str, Any] = {
            "healthy": True,
            "dexscreener_social": True,
            "timestamp": datetime.now().isoformat(),
        }
        try:
            from src.data.nansen_client import check_nansen_health
            nansen_health = check_nansen_health()
            health["nansen"] = nansen_health.get("healthy", False)
            health["nansen_detail"] = nansen_health
        except Exception as e:
            health["nansen"] = False
            health["nansen_detail"] = {"error": str(e)}
        return health

    def get_token_social_data_raw(self, token_address: str, token_symbol: str = None) -> Dict[str, Any]:
        """
        Get RAW social data for a token - NO PROCESSING OR JUDGMENT.
        Returns DexScreener social signals + deprecated stubs for TweetScout fields.
        """
        cache_key = f"social_raw_data_{token_address}_{token_symbol}"
        cached = get_cached_data(cache_key)
        if cached:
            logger.debug(f"Using cached raw social data for {token_symbol or token_address}")
            return cached

        try:
            # Fetch pairs data (needed for symbol resolution and social links)
            pairs_data = get_token_pairs("solana", token_address)

            if not token_symbol:
                if pairs_data:
                    token_symbol = pairs_data[0].get('baseToken', {}).get('symbol')
                else:
                    logger.warning(f"Could not determine symbol for token {token_address}")
                    return self._get_empty_social_data(token_address)

            data_sources_attempted = ["dexscreener_social", "nansen"]
            data_sources_successful = []

            dexscreener_social = self._get_dexscreener_social_raw(pairs_data)
            if not dexscreener_social.get("error"):
                data_sources_successful.append("dexscreener_social")

            # Nansen smart money intelligence
            nansen_signal: Dict[str, Any] = {}
            try:
                from src.data.nansen_client import get_full_nansen_signal
                nansen_signal = get_full_nansen_signal(token_address, token_symbol or "")
                if nansen_signal.get("available"):
                    data_sources_successful.append("nansen")
            except Exception as ne:
                logger.debug(f"Nansen signal skipped for {token_address[:8]}...: {ne}")
                nansen_signal = {"available": False, "reason": str(ne)}

            raw_data = {
                "token_address": token_address,
                "token_symbol": token_symbol,
                "data_collection_timestamp": datetime.now().isoformat(),
                "data_sources_attempted": data_sources_attempted,
                "data_sources_successful": data_sources_successful,

                # DexScreener social signals (website/twitter/telegram links, boosts)
                "dexscreener_social": dexscreener_social,

                # Nansen smart money intelligence
                "nansen_signal": nansen_signal,

                "errors": [],
            }

            cache_data(cache_key, raw_data, ttl_seconds=600)
            logger.info(f"Raw social data collected for {token_symbol}")
            return raw_data

        except Exception as e:
            logger.error(f"Raw social data collection error for {token_symbol or token_address}: {e}")
            return self._get_empty_social_data(token_address, str(e))

    def _get_dexscreener_social_raw(self, pairs_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get RAW social indicators from already fetched DexScreener pairs data."""
        try:
            if not pairs_data:
                return {"error": "No pairs data provided", "social_indicators": {}}
            
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
            "data_sources_attempted": ["dexscreener_social", "nansen"],
            "data_sources_successful": [],
            "dexscreener_social": {"error": error_msg or "Collection failed", "social_indicators": {}},
            "nansen_signal": {"available": False, "reason": error_msg or "Collection failed"},
            "errors": [error_msg] if error_msg else [],
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
    return {
        "social_data_collection": True,
        "api_available": True,
        "dexscreener_social": True,
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
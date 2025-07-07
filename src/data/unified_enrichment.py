# src/data/unified_enrichment.py
"""
Unified Token Enrichment Module - PURE DATA AGGREGATION ONLY
Combines RugCheck and TweetScout raw data for AI analysis
ZERO hardcoded judgment logic - AI agent makes ALL assessments
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from src.data.rugcheck_client import rugcheck_client, check_rugcheck_api_health, get_token_safety_data_raw
from src.data.social_intelligence import social_intelligence_client, check_social_intelligence_health, get_social_data_raw
from src.data.dexscreener import get_token_pairs
from src.memory.cache import get_cached_data, cache_data

# Configure logger
logger = logging.getLogger("trading_agent.unified_enrichment")

class UnifiedTokenEnrichment:
    """Unified token enrichment - Pure data aggregation for AI analysis"""
    
    def __init__(self):
        self.rugcheck_client = rugcheck_client
        self.social_client = social_intelligence_client
    
    def check_api_availability(self) -> Dict[str, Any]:
        """Check availability of all enrichment APIs"""
        rugcheck_health = check_rugcheck_api_health()
        social_health = check_social_intelligence_health()
        
        return {
            "rugcheck_available": rugcheck_health.get("healthy", False),
            "tweetscout_available": social_health.get("healthy", False),
            "dexscreener_available": True,  # Always available for basic data
            "any_api_available": (
                rugcheck_health.get("healthy", False) or 
                social_health.get("healthy", False)
            ),
            "full_enrichment_available": (
                rugcheck_health.get("healthy", False) and 
                social_health.get("healthy", False)
            ),
            "rugcheck_health": rugcheck_health,
            "social_health": social_health,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_comprehensive_raw_data(self, token_address: str, token_symbol: str = None) -> Dict[str, Any]:
        """
        Get comprehensive raw token data from all sources - NO PROCESSING OR JUDGMENT
        Pure data aggregation for AI analysis
        
        Args:
            token_address: Token mint address
            token_symbol: Token symbol (optional)
            
        Returns:
            Dict containing RAW data from all sources
        """
        cache_key = f"unified_raw_data_{token_address}"
        cached_data = get_cached_data(cache_key)
        if cached_data:
            logger.debug(f"Using cached unified raw data for {token_address}")
            return cached_data
        
        logger.info(f"Starting comprehensive raw data collection for token {token_address}")
        
        try:
            # Get token symbol if not provided
            if not token_symbol:
                token_symbol = self._get_token_symbol(token_address)
            
            # Collect RAW data from all sources
            raw_data = {
                # Data collection metadata
                "token_address": token_address,
                "token_symbol": token_symbol,
                "data_collection_timestamp": datetime.now().isoformat(),
                "collection_method": "comprehensive_raw_aggregation",
                
                # DexScreener raw data (basic market data)
                "dexscreener_raw": self._get_dexscreener_raw_data(token_address),
                
                # RugCheck raw safety data
                "rugcheck_raw": get_token_safety_data_raw(token_address),
                
                # TweetScout raw social data
                "tweetscout_raw": get_social_data_raw(token_address, token_symbol),
                
                # Enhanced market analysis (using DEX data)
                "enhanced_market_raw": self._get_enhanced_market_raw_data(token_address),
                
                # Whale analysis raw data (enhanced from DEX data)
                "whale_analysis_raw": self._get_enhanced_whale_raw_data(token_address),
                
                # Data source status
                "data_sources_status": {
                    "dexscreener_success": True,  # Always attempt
                    "rugcheck_success": not bool(self._get_rugcheck_raw_data(token_address).get("error")),
                    "tweetscout_success": not bool(get_social_data_raw(token_address, token_symbol).get("error")),
                },
                
                # API availability status
                "api_availability": self.check_api_availability(),
                
                # AI analysis requirements
                "requires_ai_analysis": True,
                "ai_analysis_suggestions": [
                    "Synthesize safety, social, and market data for overall assessment",
                    "Calculate comprehensive risk-adjusted opportunity score",
                    "Generate trading recommendation based on all factors",
                    "Assess viral potential considering safety constraints",
                    "Determine optimal position sizing based on risk profile",
                    "Identify key decision factors and confidence levels",
                    "Compare against historical similar tokens",
                    "Generate entry/exit criteria and monitoring alerts"
                ],
                
                # Error tracking
                "errors": [],
                "warnings": [],
                "data_quality_notes": []
            }
            
            # Assess data quality
            raw_data = self._assess_data_quality(raw_data)
            
            # Cache for 5 minutes
            cache_data(cache_key, raw_data, ttl_seconds=300)
            
            logger.info(f"Completed comprehensive raw data collection for {token_symbol}")
            return raw_data
            
        except Exception as e:
            logger.error(f"Error in comprehensive raw data collection: {e}")
            return self._get_empty_comprehensive_data(token_address, token_symbol, str(e))
    
    def _get_token_symbol(self, token_address: str) -> Optional[str]:
        """Get token symbol from DexScreener"""
        try:
            pairs_data = get_token_pairs("solana", token_address)
            if pairs_data and len(pairs_data) > 0:
                base_token = pairs_data[0].get('baseToken', {})
                return base_token.get('symbol')
            return None
        except Exception as e:
            logger.error(f"Error getting token symbol: {e}")
            return None
    
    def _get_dexscreener_raw_data(self, token_address: str) -> Dict[str, Any]:
        """Get raw DexScreener data"""
        try:
            pairs_data = get_token_pairs("solana", token_address)
            if not pairs_data:
                return {"error": "No pairs data available", "pairs": []}
            
            return {
                "pairs_raw": pairs_data,
                "primary_pair": pairs_data[0] if pairs_data else {},
                "total_pairs": len(pairs_data),
                "collection_timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting DexScreener raw data: {e}")
            return {"error": str(e), "pairs": []}
    
    def _get_rugcheck_raw_data(self, token_address: str) -> Dict[str, Any]:
        """Get raw RugCheck data"""
        try:
            return get_token_safety_data_raw(token_address)
        except Exception as e:
            logger.error(f"Error getting RugCheck raw data: {e}")
            return {"error": str(e), "data_available": False}
    
    def _get_enhanced_market_raw_data(self, token_address: str) -> Dict[str, Any]:
        """Get enhanced market data from DEX sources - RAW DATA ONLY"""
        try:
            pairs_data = get_token_pairs("solana", token_address)
            if not pairs_data:
                return {"error": "No market data available"}
            
            pair = pairs_data[0]
            
            # Extract RAW market metrics - NO INTERPRETATION
            return {
                "liquidity_raw": pair.get('liquidity', {}),
                "volume_raw": pair.get('volume', {}),
                "price_change_raw": pair.get('priceChange', {}),
                "transactions_raw": pair.get('txns', {}),
                "market_cap_raw": pair.get('marketCap', 0),
                "fdv_raw": pair.get('fdv', 0),
                "price_usd_raw": pair.get('priceUsd', 0),
                "age_raw": pair.get('pairCreatedAt', 0),
                "dex_info_raw": {
                    "dex_id": pair.get('dexId', ''),
                    "chain_id": pair.get('chainId', ''),
                    "labels": pair.get('labels', []),
                    "url": pair.get('url', '')
                },
                "collection_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Enhanced market data error: {e}")
            return {"error": str(e)}
    
    def _get_enhanced_whale_raw_data(self, token_address: str) -> Dict[str, Any]:
        """Get enhanced whale data from DEX sources - RAW DATA ONLY"""
        try:
            pairs_data = get_token_pairs("solana", token_address)
            if not pairs_data:
                return {"error": "No whale data available"}
            
            pair = pairs_data[0]
            
            # Extract RAW transaction and volume data - NO ANALYSIS
            volume_data = pair.get('volume', {})
            txns_data = pair.get('txns', {})
            
            return {
                "volume_breakdown_raw": volume_data,
                "transaction_breakdown_raw": txns_data,
                "liquidity_data_raw": pair.get('liquidity', {}),
                "price_impact_raw": {},  # Would need additional API calls
                "holder_distribution_raw": {},  # Would need additional data sources
                "large_transactions_raw": [],  # Would need transaction history
                "collection_timestamp": datetime.now().isoformat(),
                "data_limitations": [
                    "Detailed whale data requires additional API integrations",
                    "Transaction history analysis needs blockchain scanner",
                    "Holder distribution requires specialized endpoints"
                ]
            }
            
        except Exception as e:
            logger.error(f"Enhanced whale data error: {e}")
            return {"error": str(e)}
    
    def _assess_data_quality(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess the quality of collected raw data - NO SCORING, JUST ASSESSMENT"""
        try:
            quality_assessment = {
                "overall_quality": "unknown",  # AI will determine
                "data_completeness": {},
                "data_freshness": {},
                "source_reliability": {},
                "coverage_analysis": {}
            }
            
            # Check data completeness (not quality scoring)
            dex_available = not bool(raw_data.get("dexscreener_raw", {}).get("error"))
            rugcheck_available = not bool(raw_data.get("rugcheck_raw", {}).get("error"))
            social_available = not bool(raw_data.get("tweetscout_raw", {}).get("error"))
            
            quality_assessment["data_completeness"] = {
                "dexscreener_complete": dex_available,
                "rugcheck_complete": rugcheck_available,
                "social_complete": social_available,
                "total_sources_available": sum([dex_available, rugcheck_available, social_available])
            }
            
            # Check data freshness
            current_time = datetime.now()
            quality_assessment["data_freshness"] = {
                "collection_timestamp": raw_data.get("data_collection_timestamp"),
                "age_minutes": 0,  # Just collected
                "is_fresh": True
            }
            
            # Add quality assessment to raw data
            raw_data["data_quality_assessment"] = quality_assessment
            
            # Add quality notes for AI
            if not rugcheck_available:
                raw_data["data_quality_notes"].append("RugCheck data unavailable - safety analysis limited")
            if not social_available:
                raw_data["data_quality_notes"].append("Social data unavailable - sentiment analysis limited")
            if not dex_available:
                raw_data["data_quality_notes"].append("DEX data unavailable - market analysis impossible")
            
            return raw_data
            
        except Exception as e:
            logger.error(f"Error assessing data quality: {e}")
            raw_data["data_quality_assessment"] = {"error": str(e)}
            return raw_data
    
    def _get_empty_comprehensive_data(self, token_address: str, token_symbol: str, error_msg: str) -> Dict[str, Any]:
        """Return empty comprehensive data when collection fails"""
        return {
            "token_address": token_address,
            "token_symbol": token_symbol,
            "data_collection_timestamp": datetime.now().isoformat(),
            "collection_method": "comprehensive_raw_aggregation",
            
            "dexscreener_raw": {"error": error_msg},
            "rugcheck_raw": {"error": error_msg},
            "tweetscout_raw": {"error": error_msg},
            "enhanced_market_raw": {"error": error_msg},
            "whale_analysis_raw": {"error": error_msg},
            
            "data_sources_status": {
                "dexscreener_success": False,
                "rugcheck_success": False,
                "tweetscout_success": False,
            },
            
            "api_availability": self.check_api_availability(),
            "requires_ai_analysis": True,
            "errors": [error_msg],
            "warnings": ["Comprehensive data collection failed"],
            "data_quality_notes": ["All data sources failed - analysis severely limited"]
        }


# Initialize global unified enrichment client
unified_enrichment = UnifiedTokenEnrichment()

# ============================================================================
# API FUNCTIONS - PURE DATA AGGREGATION ONLY
# ============================================================================

def get_unified_enrichment_capabilities() -> Dict[str, bool]:
    """Get unified enrichment capabilities - compatibility function"""
    availability = unified_enrichment.check_api_availability()
    
    return {
        "data_aggregation": True,           # Always available
        "safety_data_collection": availability.get("rugcheck_available", False),
        "social_data_collection": availability.get("tweetscout_available", False),
        "market_data_collection": True,     # Always available via DexScreener
        "comprehensive_data": availability.get("any_api_available", False),
        "full_enrichment": availability.get("full_enrichment_available", False),
        "api_available": availability.get("any_api_available", False),
        
        # Note: These are data collection capabilities only
        "raw_data_only": True,
        "requires_ai_analysis": True
    }

def get_comprehensive_raw_token_data(token_address: str, token_symbol: str = None) -> Dict[str, Any]:
    """
    Get comprehensive raw token data from all sources
    Replaces get_comprehensive_token_analysis with pure data collection
    """
    return unified_enrichment.get_comprehensive_raw_data(token_address, token_symbol)

def enrich_dexscreener_token_raw(token_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich DexScreener token data with raw analysis data
    Returns token data with additional raw data fields for AI processing
    """
    try:
        token_address = token_data.get('address', '')
        token_symbol = token_data.get('symbol', '')
        
        if not token_address:
            logger.warning("No token address provided for enrichment")
            return token_data
        
        # Get comprehensive raw data
        raw_analysis = get_comprehensive_raw_token_data(token_address, token_symbol)
        
        # Add raw data to token - NO PROCESSING
        enriched_token = token_data.copy()
        enriched_token.update({
            # Raw data containers
            "raw_safety_data": raw_analysis.get("rugcheck_raw", {}),
            "raw_social_data": raw_analysis.get("tweetscout_raw", {}),
            "raw_whale_data": raw_analysis.get("whale_analysis_raw", {}),
            "raw_market_data": raw_analysis.get("enhanced_market_raw", {}),
            
            # AI analysis placeholders (to be filled by AI agent)
            "ai_overall_score": 0,          # AI will calculate
            "ai_recommendation": "",        # AI will generate
            "ai_risk_assessment": "",       # AI will assess
            "ai_reasoning": "",             # AI will provide
            "ai_confidence": 0,             # AI will determine
            
            # Safety placeholders (AI will extract from raw data)
            "safety_score": 0,              # AI will interpret from RugCheck raw
            "contract_verified": False,     # AI will determine
            "liquidity_locked": False,      # AI will assess
            "ownership_concentration": 0,   # AI will calculate
            "honeypot_risk": False,         # AI will evaluate
            "rug_pull_risk": False,         # AI will assess
            "risk_level": "unknown",        # AI will classify
            "risk_factors": [],             # AI will extract
            
            # Social placeholders (AI will extract from raw data)
            "social_activity": 0,           # AI will calculate from TweetScout raw
            "viral_score": 0,               # AI will assess
            "sentiment_score": 50,          # AI will determine
            "social_mentions_24h": 0,       # AI will count
            "trending_potential": False,    # AI will evaluate
            "community_engagement": 0,      # AI will measure
            
            # Whale placeholders (AI will calculate from DEX raw data)
            "whale_buy_pressure": 0,        # AI will analyze
            "whale_sell_pressure": 0,       # AI will analyze
            "whale_transactions": [],       # AI will identify
            
            # Market placeholders (AI will interpret from DEX raw data)
            "market_health_score": 0,       # AI will calculate
            "volatility_score": 0,          # AI will assess
            "liquidity_quality": "unknown", # AI will classify
            "trading_activity_score": 0,    # AI will measure
            
            # Enrichment metadata
            "enriched": True,
            "enrichment_method": "raw_data_collection",
            "enrichment_timestamp": raw_analysis.get("data_collection_timestamp"),
            "enrichment_quality": "requires_ai_analysis",
            "data_sources_used": raw_analysis.get("data_sources_status", {}),
            "requires_ai_processing": True,
            
            # Legacy compatibility
            "bitquery_enriched": False,     # Always False now
            "mock_data": False
        })
        
        logger.info(f"Successfully enriched token {token_symbol} with raw data")
        return enriched_token
        
    except Exception as e:
        logger.error(f"Token enrichment failed: {e}")
        # Return original token data with error indication
        enriched_token = token_data.copy()
        enriched_token.update({
            "enriched": False,
            "enrichment_error": str(e),
            "requires_ai_processing": True,
            "raw_data_available": False
        })
        return enriched_token

# ============================================================================
# REMOVED FUNCTIONS - ALL HARDCODED JUDGMENT LOGIC ELIMINATED
# ============================================================================

# REMOVED: get_comprehensive_token_analysis() - Had hardcoded scoring and recommendations
# REMOVED: _calculate_overall_token_score() - Had hardcoded weighting algorithms
# REMOVED: _generate_token_recommendation() - Had hardcoded if/else recommendation logic
# REMOVED: _assess_enrichment_quality() - Had hardcoded quality scoring
# REMOVED: All hardcoded scoring, weighting, and recommendation functions

# The AI agent now receives pure aggregated data and makes all assessments
# using its knowledge and reasoning capabilities

# ============================================================================
# COMPATIBILITY FUNCTIONS (for gradual migration)
# ============================================================================

def get_comprehensive_token_analysis(token_address: str, token_symbol: str = None) -> Dict[str, Any]:
    """
    Legacy compatibility function - now returns raw data with AI analysis placeholders
    UI components expecting processed analysis will need to be updated
    """
    logger.warning("Legacy get_comprehensive_token_analysis called - returning raw data only")
    
    raw_data = get_comprehensive_raw_token_data(token_address, token_symbol)
    
    # Return structure similar to old format but with raw data and AI placeholders
    return {
        # Raw data (new)
        "comprehensive_raw_data": raw_data,
        
        # Legacy structure placeholders (will be filled by AI)
        "overall_score": 0,                 # AI will calculate
        "recommendation": "REQUIRES_AI_ANALYSIS",  # AI will generate
        "risk_level": "unknown",            # AI will assess
        
        # Component placeholders
        "safety_analysis": {"requires_ai_analysis": True},
        "social_analysis": {"requires_ai_analysis": True},
        "whale_analysis": {"requires_ai_analysis": True},
        "market_analytics": {"requires_ai_analysis": True},
        
        # Metadata
        "token_address": token_address,
        "token_symbol": token_symbol,
        "analysis_timestamp": datetime.now().isoformat(),
        "data_sources": raw_data.get("data_sources_status", {}),
        "enrichment_quality": "raw_data_only",
        "requires_ai_processing": True,
        "legacy_compatibility": True
    }

def get_market_sentiment_indicators() -> Dict[str, Any]:
    """Get market sentiment indicators using raw data aggregation"""
    try:
        # Use SOL as representative token for market sentiment
        sol_address = "So11111111111111111111111111111111111111112"
        raw_data = get_comprehensive_raw_token_data(sol_address, "SOL")
        
        return {
            # Raw market data for AI analysis
            "market_raw_data": raw_data,
            
            # Placeholder indicators (AI will calculate from raw data)
            "overall_social_sentiment": "requires_ai_analysis",
            "viral_activity_level": 0,      # AI will assess from social raw data
            "social_momentum": 0,           # AI will calculate
            "trader_growth": 0,             # AI will measure from transaction data
            "community_engagement": 0,      # AI will evaluate
            "trending_potential": False,    # AI will determine
            "market_health": 0,             # AI will calculate from market raw data
            
            "timestamp": datetime.now().isoformat(),
            "requires_ai_analysis": True,
            "data_source": "comprehensive_raw_aggregation"
        }
        
    except Exception as e:
        logger.error(f"Market sentiment indicators error: {e}")
        return {
            "overall_social_sentiment": "error",
            "viral_activity_level": 0,
            "social_momentum": 0,
            "trader_growth": 0,
            "community_engagement": 0,
            "trending_potential": False,
            "market_health": 0,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "requires_ai_analysis": True
        }
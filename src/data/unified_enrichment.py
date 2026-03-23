# src/data/unified_enrichment.py
"""
Unified Token Enrichment Module - PURE DATA AGGREGATION ONLY
Combines RugCheck, DexScreener, and Social Intelligence (DexScreener social + Nansen)
raw data for AI analysis.
ZERO hardcoded judgment logic - AI agent makes ALL assessments.
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
            "social_available": social_health.get("healthy", False),
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
        Get comprehensive raw token data from all sources - NO PROCESSING OR JUDGMENT.
        Sources: DexScreener (market + social links), RugCheck (safety), Nansen (smart money).
        Pure data aggregation for AI analysis.

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
            if not token_symbol:
                token_symbol = self._get_token_symbol(token_address)

            # Collect social data once (reused for status check)
            social_raw = get_social_data_raw(token_address, token_symbol)

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

                # Social intelligence raw data (DexScreener social links + Nansen smart money)
                "social_raw": social_raw,

                # Enhanced market analysis (using DEX data)
                "enhanced_market_raw": self._get_enhanced_market_raw_data(token_address),

                # Whale analysis raw data (enhanced from DEX data)
                "whale_analysis_raw": self._get_enhanced_whale_raw_data(token_address),

                # Data source status
                "data_sources_status": {
                    "dexscreener_success": True,  # Always attempt
                    "rugcheck_success": not bool(self._get_rugcheck_raw_data(token_address).get("error")),
                    "social_success": not bool(social_raw.get("error")),
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

            raw_data = self._assess_data_quality(raw_data)
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
            if pairs_data:
                return pairs_data[0].get('baseToken', {}).get('symbol')
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
            volume_data = pair.get('volume', {})
            txns_data = pair.get('txns', {})
            return {
                "volume_breakdown_raw": volume_data,
                "transaction_breakdown_raw": txns_data,
                "liquidity_data_raw": pair.get('liquidity', {}),
                "price_impact_raw": {},
                "holder_distribution_raw": {},
                "large_transactions_raw": [],
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
        dex_available      = not bool(raw_data.get("dexscreener_raw", {}).get("error"))
        rugcheck_available = not bool(raw_data.get("rugcheck_raw", {}).get("error"))
        social_available   = not bool(raw_data.get("social_raw", {}).get("error"))

        raw_data["data_quality_assessment"] = {
            "overall_quality": "unknown",  # AI will determine
            "data_completeness": {
                "dexscreener_complete": dex_available,
                "rugcheck_complete": rugcheck_available,
                "social_complete": social_available,
                "total_sources_available": sum([dex_available, rugcheck_available, social_available])
            },
            "data_freshness": {
                "collection_timestamp": raw_data.get("data_collection_timestamp"),
                "age_minutes": 0,
                "is_fresh": True
            },
            "source_reliability": {},
            "coverage_analysis": {}
        }
        raw_data["data_quality_notes"] = []

        if not rugcheck_available:
            raw_data["data_quality_notes"].append("RugCheck data unavailable - safety analysis limited")
        if not social_available:
            raw_data["data_quality_notes"].append("Social data unavailable - Nansen/DexScreener social analysis limited")
        if not dex_available:
            raw_data["data_quality_notes"].append("DEX data unavailable - market analysis impossible")

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
            "social_raw": {"error": error_msg},
            "enhanced_market_raw": {"error": error_msg},
            "whale_analysis_raw": {"error": error_msg},

            "data_sources_status": {
                "dexscreener_success": False,
                "rugcheck_success": False,
                "social_success": False,
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
    """Get unified enrichment capabilities"""
    availability = unified_enrichment.check_api_availability()
    return {
        "data_aggregation": True,
        "safety_data_collection": availability.get("rugcheck_available", False),
        "social_data_collection": availability.get("social_available", False),
        "market_data_collection": True,
        "comprehensive_data": availability.get("any_api_available", False),
        "full_enrichment": availability.get("full_enrichment_available", False),
        "api_available": availability.get("any_api_available", False),
        "raw_data_only": True,
        "requires_ai_analysis": True
    }

def get_comprehensive_raw_token_data(token_address: str, token_symbol: str = None) -> Dict[str, Any]:
    """Get comprehensive raw token data from all sources"""
    return unified_enrichment.get_comprehensive_raw_data(token_address, token_symbol)

def enrich_dexscreener_token_raw(token_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich DexScreener token data with raw analysis data from all sources.
    Returns token data with additional raw fields for AI processing.
    """
    try:
        token_address = token_data.get('address', '')
        token_symbol  = token_data.get('symbol', '')

        if not token_address:
            logger.warning("No token address provided for enrichment")
            return token_data

        raw_analysis = get_comprehensive_raw_token_data(token_address, token_symbol)

        enriched_token = token_data.copy()
        enriched_token.update({
            # Raw data containers
            "raw_safety_data":  raw_analysis.get("rugcheck_raw", {}),
            "raw_social_data":  raw_analysis.get("social_raw", {}),
            "raw_whale_data":   raw_analysis.get("whale_analysis_raw", {}),
            "raw_market_data":  raw_analysis.get("enhanced_market_raw", {}),

            # AI analysis placeholders (to be filled by AI agent)
            "ai_overall_score":   0,
            "ai_recommendation":  "",
            "ai_risk_assessment": "",
            "ai_reasoning":       "",
            "ai_confidence":      0,

            # Safety placeholders (AI will extract from rugcheck_raw)
            "safety_score":            0,
            "contract_verified":       False,
            "liquidity_locked":        False,
            "ownership_concentration": 0,
            "honeypot_risk":           False,
            "rug_pull_risk":           False,
            "risk_level":              "unknown",
            "risk_factors":            [],

            # Social placeholders (AI will extract from social_raw — Nansen + DexScreener)
            "social_activity":      0,
            "viral_score":          0,
            "sentiment_score":      50,
            "social_mentions_24h":  0,
            "trending_potential":   False,
            "community_engagement": 0,

            # Whale placeholders (AI will calculate from DEX raw data)
            "whale_buy_pressure":  0,
            "whale_sell_pressure": 0,
            "whale_transactions":  [],

            # Market placeholders
            "market_health_score":    0,
            "volatility_score":       0,
            "liquidity_quality":      "unknown",
            "trading_activity_score": 0,

            # Enrichment metadata
            "enriched":            True,
            "enrichment_method":   "raw_data_collection",
            "enrichment_timestamp": raw_analysis.get("data_collection_timestamp"),
            "enrichment_quality":  "requires_ai_analysis",
            "data_sources_used":   raw_analysis.get("data_sources_status", {}),
            "requires_ai_processing": True,

            # Legacy compatibility
            "bitquery_enriched": False,
            "mock_data":         False
        })

        logger.info(f"Successfully enriched token {token_symbol} with raw data")
        return enriched_token

    except Exception as e:
        logger.error(f"Token enrichment failed: {e}")
        enriched_token = token_data.copy()
        enriched_token.update({
            "enriched": False,
            "enrichment_error": str(e),
            "requires_ai_processing": True,
            "raw_data_available": False
        })
        return enriched_token


# ============================================================================
# COMPATIBILITY FUNCTIONS
# ============================================================================

def get_comprehensive_token_analysis(token_address: str, token_symbol: str = None) -> Dict[str, Any]:
    """Legacy compatibility — now returns raw data with AI analysis placeholders."""
    logger.warning("Legacy get_comprehensive_token_analysis called - returning raw data only")
    raw_data = get_comprehensive_raw_token_data(token_address, token_symbol)
    return {
        "comprehensive_raw_data": raw_data,
        "overall_score": 0,
        "recommendation": "REQUIRES_AI_ANALYSIS",
        "risk_level": "unknown",
        "safety_analysis": {"requires_ai_analysis": True},
        "social_analysis": {"requires_ai_analysis": True},
        "whale_analysis": {"requires_ai_analysis": True},
        "market_analytics": {"requires_ai_analysis": True},
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
        sol_address = "So11111111111111111111111111111111111111112"
        raw_data = get_comprehensive_raw_token_data(sol_address, "SOL")
        return {
            "market_raw_data": raw_data,
            "overall_social_sentiment": "requires_ai_analysis",
            "viral_activity_level": 0,
            "social_momentum": 0,
            "trader_growth": 0,
            "community_engagement": 0,
            "trending_potential": False,
            "market_health": 0,
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

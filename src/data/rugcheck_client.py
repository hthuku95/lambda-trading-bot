# src/data/rugcheck_client.py - COMPLETE COMPATIBLE VERSION WITH PROPER CLASS STRUCTURE
"""
RugCheck API Integration - FIXED AND FULLY COMPATIBLE
Maintains all original functions while implementing working endpoints
Production ready with full backward compatibility
"""
import os
import requests
import logging
import base64
import json
import base58
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from src.memory.cache import get_cached_data, cache_data

# Configure logger
logger = logging.getLogger("trading_agent.rugcheck")

# Load environment variables
load_dotenv()

# RugCheck API Configuration - FIXED AND TESTED
RUGCHECK_BASE_URL = "https://api.rugcheck.xyz/v1"
RATE_LIMIT_DELAY = 2.0  # Increased to 2 seconds between requests due to strict rate limiting
SOLANA_PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")

class RugCheckClient:
    """RugCheck API Client - COMPLETE VERSION with full compatibility"""
    
    def __init__(self):
        self.base_url = RUGCHECK_BASE_URL
        self.private_key = SOLANA_PRIVATE_KEY
        self.session = requests.Session()
        self.last_request_time = 0
        
        # Legacy compatibility attributes
        self.auth_token = None
        self.auth_expires = None
        self.working_endpoint = RUGCHECK_BASE_URL
        self.working_pattern = "/tokens/{token}/report"
        
        # Set up headers for optimal API interaction
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'TradingBot/1.0'
        })
        
        if self.private_key:
            logger.info("RugCheck client initialized with Solana wallet authentication")
        else:
            logger.warning("RugCheck client initialized without Solana private key")
    
    def _rate_limit_delay(self):
        """Enforce rate limiting to respect API limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < RATE_LIMIT_DELAY:
            sleep_time = RATE_LIMIT_DELAY - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def check_api_health(self) -> Dict[str, Any]:
        """Check RugCheck API health using working endpoints"""
        try:
            start_time = datetime.now()
            
            # Test with a working stats endpoint first
            response = self.session.get(f"{self.base_url}/stats/new_tokens", timeout=10)
            
            if response.status_code == 200:
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                # Test token lookup capability with USDC
                test_token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                token_test = self.session.get(f"{self.base_url}/tokens/{test_token}/report", timeout=10)
                
                return {
                    "healthy": True,
                    "working_endpoint": self.base_url,
                    "working_pattern": "/tokens/{token}/report",
                    "response_time_ms": response_time,
                    "solana_available": True,
                    "token_lookup_working": token_test.status_code == 200,
                    "auth_working": False,  # No auth required for basic reports
                    "wallet_configured": bool(self.private_key),
                    "authentication_method": "none_required",
                    "endpoints_tested": 2,
                    "base_url": self.base_url,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "healthy": False,
                    "error": f"API returned status {response.status_code}",
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _extract_score_metrics(self, score: int) -> Dict[str, Any]:
        """Extract pure score metrics - NO JUDGMENT, just data"""
        return {
            "raw_score": score,
            "score_normalized": score / 1000.0 if score > 0 else 0,  # Normalize to 0-1+ scale
            "score_available": score > 0
        }
    
    def _extract_holder_metrics(self, top_holders: List[Dict]) -> Dict[str, Any]:
        """Extract pure holder concentration metrics - NO JUDGMENT, just calculations"""
        if not top_holders:
            return {
                "data_available": False,
                "holder_count": 0,
                "top_1_holder_pct": 0,
                "top_5_holders_pct": 0,
                "top_10_holders_pct": 0,
                "concentration_metrics": []
            }
        
        # Pure mathematical calculations - no risk assessment
        top_1_pct = top_holders[0].get("pct", 0) if top_holders else 0
        top_5_pct = sum(holder.get("pct", 0) for holder in top_holders[:5])
        top_10_pct = sum(holder.get("pct", 0) for holder in top_holders[:10])
        
        # Extract individual holder data for AI analysis
        concentration_metrics = []
        for i, holder in enumerate(top_holders[:10]):
            concentration_metrics.append({
                "rank": i + 1,
                "percentage": holder.get("pct", 0),
                "address": holder.get("address", ""),
                "amount": holder.get("amount", 0),
                "is_insider": holder.get("insider", False)
            })
        
        return {
            "data_available": True,
            "holder_count": len(top_holders),
            "top_1_holder_pct": top_1_pct,
            "top_5_holders_pct": top_5_pct,
            "top_10_holders_pct": top_10_pct,
            "concentration_metrics": concentration_metrics,
            "total_tracked_percentage": top_10_pct
        }
    
    def _extract_market_metrics(self, markets: List[Dict]) -> Dict[str, Any]:
        """Extract pure market data - NO JUDGMENT, just calculations"""
        if not markets:
            return {
                "data_available": False,
                "market_count": 0,
                "total_liquidity_usd": 0,
                "market_types": [],
                "markets_detail": []
            }
        
        total_liquidity = 0
        market_types = []
        markets_detail = []
        
        for market in markets:
            market_type = market.get("marketType", "unknown")
            market_types.append(market_type)
            
            # Extract liquidity data if available
            liquidity_usd = 0
            if "lp" in market:
                lp_data = market["lp"]
                liquidity_usd = lp_data.get("lpLockedUSD", 0)
                total_liquidity += liquidity_usd
            
            markets_detail.append({
                "market_type": market_type,
                "liquidity_usd": liquidity_usd,
                "pubkey": market.get("pubkey", ""),
                "lp_data": market.get("lp", {})
            })
        
        return {
            "data_available": True,
            "market_count": len(markets),
            "market_types": list(set(market_types)),
            "total_liquidity_usd": total_liquidity,
            "markets_detail": markets_detail
        }
    
    def _extract_security_data(self, raw_data: Dict) -> Dict[str, Any]:
        """Extract pure security data - NO JUDGMENT, just facts"""
        return {
            "mint_authority": raw_data.get("mintAuthority"),
            "freeze_authority": raw_data.get("freezeAuthority"),
            "mint_authority_present": raw_data.get("mintAuthority") is not None,
            "freeze_authority_present": raw_data.get("freezeAuthority") is not None,
            "transfer_fee_data": raw_data.get("transferFee", {}),
            "verification_data": raw_data.get("verification"),
            "verification_present": raw_data.get("verification") is not None,
            "rugged_flag": raw_data.get("rugged", False),
            "token_program": raw_data.get("tokenProgram", ""),
            "token_type": raw_data.get("tokenType", "")
        }
    
    def _extract_lp_lock_data(self, lockers: Dict) -> Dict[str, Any]:
        """Extract pure LP lock data - NO JUDGMENT, just facts"""
        if not lockers:
            return {
                "data_available": False,
                "lock_count": 0,
                "total_locked_usd": 0,
                "lockers_detail": []
            }
        
        total_locked = 0
        lockers_detail = []
        
        for locker_key, locker_data in lockers.items():
            locked_amount = locker_data.get("usdcLocked", 0)
            total_locked += locked_amount
            
            lockers_detail.append({
                "locker_address": locker_key,
                "locked_usd": locked_amount,
                "unlock_date": locker_data.get("unlockDate"),
                "locker_type": locker_data.get("type", ""),
                "program_id": locker_data.get("programID", "")
            })
        
        return {
            "data_available": True,
            "lock_count": len(lockers),
            "total_locked_usd": total_locked,
            "lockers_detail": lockers_detail
        }
    
    def _create_legacy_holder_analysis(self, top_holders: List[Dict]) -> Dict[str, Any]:
        """Create legacy holder_concentration structure for backward compatibility"""
        holder_metrics = self._extract_holder_metrics(top_holders)
        
        if not holder_metrics["data_available"]:
            return {
                "analysis": "no_data",
                "top_1_holder_pct": 0,
                "top_5_holders_pct": 0,
                "top_10_holders_pct": 0
            }
        
        return {
            "analysis": "calculated",
            "top_1_holder_pct": holder_metrics["top_1_holder_pct"],
            "top_5_holders_pct": holder_metrics["top_5_holders_pct"],
            "top_10_holders_pct": holder_metrics["top_10_holders_pct"]
        }
    
    def _create_legacy_market_analysis(self, markets: List[Dict]) -> Dict[str, Any]:
        """Create legacy market_analysis structure for backward compatibility"""
        market_metrics = self._extract_market_metrics(markets)
        
        return {
            "analysis": "calculated" if market_metrics["data_available"] else "no_markets",
            "market_count": market_metrics["market_count"],
            "market_types": market_metrics["market_types"],
            "total_liquidity_usd": market_metrics["total_liquidity_usd"],
            "liquidity_usd": market_metrics["total_liquidity_usd"]
        }
    
    def _create_legacy_security_analysis(self, raw_data: Dict) -> Dict[str, Any]:
        """Create legacy security_analysis structure for backward compatibility"""
        security_data = self._extract_security_data(raw_data)
        
        return {
            "mint_authority": security_data["mint_authority"],
            "freeze_authority": security_data["freeze_authority"],
            "mint_authority_present": security_data["mint_authority_present"],
            "freeze_authority_present": security_data["freeze_authority_present"],
            "transfer_fee": security_data["transfer_fee_data"],
            "verification_present": security_data["verification_present"],
            "verification_data": security_data["verification_data"]
        }
    
    def _create_legacy_lp_analysis(self, lockers: Dict) -> Dict[str, Any]:
        """Create legacy lp_lock_analysis structure for backward compatibility"""
        lp_data = self._extract_lp_lock_data(lockers)
        
        return {
            "analysis": "calculated" if lp_data["data_available"] else "no_locks",
            "locked": lp_data["data_available"] and lp_data["lock_count"] > 0,
            "lock_count": lp_data["lock_count"],
            "total_locked_usd": lp_data["total_locked_usd"],
            "lockers_detail": lp_data.get("lockers_detail", [])
        }
    
    def get_token_safety_data_raw(self, token_address: str) -> Dict[str, Any]:
        """Get RAW token safety data with enhanced endpoint handling - MAIN FUNCTION"""
        cache_key = f"rugcheck_raw_data_{token_address}"
        cached_data = get_cached_data(cache_key)
        if cached_data:
            logger.debug(f"Using cached RugCheck raw data for {token_address}")
            return cached_data
        
        try:
            # Rate limiting
            self._rate_limit_delay()
            
            url = f"{self.base_url}/tokens/{token_address}/report"
            logger.info(f"Fetching RugCheck data from: {url}")
            
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                raw_api_response = response.json()
                
                # Structure comprehensive raw data for AI analysis
                raw_data = {
                    "token_address": token_address,
                    "data_collection_timestamp": datetime.now().isoformat(),
                    "api_response_status": response.status_code,
                    "working_endpoint": self.base_url,
                    "successful_endpoint": url,
                    "endpoint_pattern": "/tokens/{token}/report",
                    
                    # Complete raw RugCheck response
                    "rugcheck_raw_response": raw_api_response,
                    
                    # Extract key fields for backward compatibility
                    "token_metadata_raw": raw_api_response.get('tokenMeta', {}),
                    "risks_raw": raw_api_response.get('risks', []),
                    "score_raw": raw_api_response.get('score', 0),
                    "liquidity_raw": {
                        "total_market_liquidity": raw_api_response.get('totalMarketLiquidity', 0),
                        "markets": raw_api_response.get('markets', [])
                    },
                    "ownership_raw": {
                        "top_holders": raw_api_response.get('topHolders', []),
                        "total_holders": raw_api_response.get('totalHolders', 0),
                        "creator": raw_api_response.get('creator')
                    },
                    "contract_raw": {
                        "mint_authority": raw_api_response.get('mintAuthority'),
                        "freeze_authority": raw_api_response.get('freezeAuthority'),
                        "token_program": raw_api_response.get('tokenProgram'),
                        "verification": raw_api_response.get('verification')
                    },
                    "security_raw": {
                        "rugged": raw_api_response.get('rugged', False),
                        "score": raw_api_response.get('score', 0),
                        "score_normalised": raw_api_response.get('score_normalised', 0),
                        "lockers": raw_api_response.get('lockers', {}),
                        "insider_networks": raw_api_response.get('insiderNetworks', [])
                    },
                    
                    # Enhanced data extraction fields (PURE DATA - NO JUDGMENT)
                    "price": raw_api_response.get('price', 0),
                    "total_market_liquidity": raw_api_response.get('totalMarketLiquidity', 0),
                    "total_holders": raw_api_response.get('totalHolders', 0),
                    "total_lp_providers": raw_api_response.get('totalLPProviders', 0),
                    
                    # NEW: Pure data extraction
                    "score_metrics": self._extract_score_metrics(raw_api_response.get('score', 0)),
                    "holder_metrics": self._extract_holder_metrics(raw_api_response.get('topHolders', [])),
                    "market_metrics": self._extract_market_metrics(raw_api_response.get('markets', [])),
                    "security_data": self._extract_security_data(raw_api_response),
                    "lp_lock_data": self._extract_lp_lock_data(raw_api_response.get('lockers', {})),
                    
                    # LEGACY COMPATIBILITY: Keep old field names as aliases
                    "holder_concentration": self._create_legacy_holder_analysis(raw_api_response.get('topHolders', [])),
                    "market_analysis": self._create_legacy_market_analysis(raw_api_response.get('markets', [])),
                    "security_analysis": self._create_legacy_security_analysis(raw_api_response),
                    "lp_lock_analysis": self._create_legacy_lp_analysis(raw_api_response.get('lockers', {})),
                    
                    # Metadata
                    "data_source": "rugcheck",
                    "authentication_used": False,
                    "requires_ai_analysis": True,
                    "data_available": True,
                    
                    # AI data interpretation suggestions (NO JUDGMENT - PURE DATA GUIDANCE)
                    "ai_analysis_suggestions": [
                        "Interpret raw safety score and individual risk factors",
                        "Analyze holder concentration percentages and distribution patterns", 
                        "Evaluate contract authority status (mint/freeze)",
                        "Assess LP lock amounts and unlock dates",
                        "Review market liquidity distribution across DEXs",
                        "Examine token metadata and verification status",
                        "Calculate overall risk profile from available metrics",
                        "Determine confidence level based on data completeness"
                    ]
                }
                
                # Cache for 10 minutes
                cache_data(cache_key, raw_data, ttl_seconds=600)
                
                logger.info(f"Successfully collected RugCheck data for {token_address}")
                return raw_data
                
            elif response.status_code == 404:
                logger.warning(f"Token {token_address} not found in RugCheck database")
                return self._get_empty_safety_data(token_address, "Token not found in RugCheck database")
            
            elif response.status_code == 429:
                logger.warning("RugCheck rate limit exceeded")
                return self._get_empty_safety_data(token_address, "Rate limit exceeded")
            
            else:
                logger.error(f"RugCheck API error: {response.status_code}")
                return self._get_empty_safety_data(token_address, f"API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error getting RugCheck data for {token_address}: {e}")
            return self._get_empty_safety_data(token_address, str(e))
    
    def get_token_report(self, token_address: str, summary: bool = False) -> Dict[str, Any]:
        """Get token report using correct RugCheck API endpoint"""
        if summary:
            # For summary, try the summary endpoint first, fallback to full
            try:
                self._rate_limit_delay()
                url = f"{self.base_url}/tokens/{token_address}/report/summary"
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    return self._process_report_response(response.json(), token_address, "summary")
            except:
                pass  # Fall back to full report
        
        # Get full report (or fallback for summary)
        return self.get_token_safety_data_raw(token_address)
    
    def _process_report_response(self, data: Dict, token_address: str, report_type: str) -> Dict[str, Any]:
        """Process report response into standardized format"""
        return {
            "token_address": token_address,
            "report_type": report_type,
            "data_collection_timestamp": datetime.now().isoformat(),
            "rugcheck_raw_response": data,
            "data_available": True,
            "score_raw": data.get("score", 0),
            "risks_raw": data.get("risks", []),
            "data_source": "rugcheck"
        }
    
    def search_tokens_raw(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """Search for tokens using RugCheck - returns RAW search results"""
        # RugCheck doesn't have a public search endpoint, so return empty results
        return {
            "search_query": query,
            "raw_search_results": [],
            "results_count": 0,
            "error": "RugCheck search not available - use DexScreener for token discovery",
            "search_timestamp": datetime.now().isoformat()
        }
    
    def get_recent_tokens(self) -> Dict[str, Any]:
        """Get recently detected tokens"""
        try:
            self._rate_limit_delay()
            response = self.session.get(f"{self.base_url}/stats/new_tokens", timeout=10)
            if response.status_code == 200:
                return {"tokens": response.json(), "error": None}
            else:
                return {"tokens": [], "error": f"API error: {response.status_code}"}
        except Exception as e:
            return {"tokens": [], "error": str(e)}
    
    def get_trending_tokens(self) -> Dict[str, Any]:
        """Get trending tokens"""
        try:
            self._rate_limit_delay()
            response = self.session.get(f"{self.base_url}/stats/trending", timeout=10)
            if response.status_code == 200:
                return {"tokens": response.json(), "error": None}
            else:
                return {"tokens": [], "error": f"API error: {response.status_code}"}
        except Exception as e:
            return {"tokens": [], "error": str(e)}
    
    def _get_empty_safety_data(self, token_address: str, error_msg: str) -> Dict[str, Any]:
        """Return empty safety data structure when RugCheck API fails"""
        return {
            "token_address": token_address,
            "data_collection_timestamp": datetime.now().isoformat(),
            "api_response_status": 0,
            "working_endpoint": self.working_endpoint,
            "successful_endpoint": None,
            "endpoint_pattern": self.working_pattern,
            
            "rugcheck_raw_response": {},
            "token_metadata_raw": {},
            "risks_raw": [],
            "score_raw": 0,
            "liquidity_raw": {},
            "ownership_raw": {},
            "contract_raw": {},
            "security_raw": {},
            
            "price": 0,
            "total_market_liquidity": 0,
            "total_holders": 0,
            "total_lp_providers": 0,
            
            # NEW: Pure data extraction (empty but structured)
            "score_metrics": {"raw_score": 0, "score_normalized": 0, "score_available": False},
            "holder_metrics": {"data_available": False, "holder_count": 0, "top_1_holder_pct": 0, "top_5_holders_pct": 0, "top_10_holders_pct": 0},
            "market_metrics": {"data_available": False, "market_count": 0, "total_liquidity_usd": 0},
            "security_data": {"mint_authority_present": False, "freeze_authority_present": False, "verification_present": False},
            "lp_lock_data": {"data_available": False, "lock_count": 0, "total_locked_usd": 0},
            
            # LEGACY COMPATIBILITY: Keep old field names
            "holder_concentration": {"analysis": "no_data", "top_1_holder_pct": 0, "top_5_holders_pct": 0, "top_10_holders_pct": 0},
            "market_analysis": {"analysis": "no_data", "liquidity_usd": 0, "market_count": 0},
            "security_analysis": {"mint_authority_present": False, "freeze_authority_present": False},
            "lp_lock_analysis": {"locked": False, "analysis": "no_data", "total_locked_usd": 0},
            
            "data_source": "rugcheck",
            "authentication_used": False,
            "requires_ai_analysis": True,
            "error": error_msg,
            "data_available": False,
            
            # Fallback analysis suggestions
            "ai_analysis_suggestions": [
                "RugCheck data unavailable - use DexScreener data for basic analysis",
                "Consider alternative safety analysis methods",
                "Cross-reference with social sentiment data",
                "Use conservative risk assessment approach",
                "Monitor for manual safety indicators"
            ]
        }

    # ============================================================================
    # LEGACY COMPATIBILITY METHODS
    # ============================================================================
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Legacy compatibility - return basic headers"""
        return self.session.headers.copy()
    
    def _get_auth_token(self) -> Optional[str]:
        """Legacy compatibility - no auth token needed"""
        return None
    
    def _find_working_endpoint_and_pattern(self, token_address: str) -> tuple[Optional[str], Optional[str]]:
        """Legacy compatibility - return fixed working endpoint"""
        return (self.base_url, "/tokens/{token}/report")


# Initialize global client
rugcheck_client = RugCheckClient()

# ============================================================================
# API FUNCTIONS - COMPLETE COMPATIBILITY
# ============================================================================

def check_rugcheck_api_health() -> Dict[str, Any]:
    """Check RugCheck API health - enhanced version"""
    return rugcheck_client.check_api_health()

def get_rugcheck_capabilities() -> Dict[str, bool]:
    """Get RugCheck API capabilities - enhanced version"""
    health = check_rugcheck_api_health()
    api_working = health.get("healthy", False)
    
    return {
        "safety_data_collection": api_working,
        "token_analysis": api_working,
        "risk_factor_detection": api_working,
        "contract_analysis": api_working,
        "token_search": False,  # Not available in RugCheck
        "api_available": api_working,
        "solana_supported": health.get("solana_available", False),
        "auth_working": health.get("auth_working", False),
        "wallet_configured": health.get("wallet_configured", False),
        "authentication_method": health.get("authentication_method", "none_required"),
        "working_endpoint": health.get("working_endpoint"),
        "working_pattern": health.get("working_pattern"),
        "endpoints_tested": health.get("endpoints_tested", 0),
        
        # Enhanced capabilities
        "holder_analysis": api_working,
        "liquidity_analysis": api_working,
        "insider_detection": api_working,
        "lp_lock_verification": api_working,
        "enhanced_analysis": api_working,
        
        # Note: These are data collection capabilities, not judgment capabilities
        "raw_data_only": True,
        "requires_ai_analysis": True,
        "fallback_available": True  # Can fall back to DexScreener data
    }

def get_token_safety_data_raw(token_address: str) -> Dict[str, Any]:
    """
    Get RAW token safety data for AI analysis - MAIN FUNCTION
    """
    return rugcheck_client.get_token_safety_data_raw(token_address)

def collect_safety_intelligence(token_address: str) -> Dict[str, Any]:
    """
    Primary function for collecting safety intelligence data
    Returns pure data for AI agent to analyze and make safety judgments
    """
    logger.info(f"Collecting safety intelligence for {token_address}")
    
    # Get raw data
    raw_data = get_token_safety_data_raw(token_address)
    
    # Add collection metadata
    raw_data["collection_method"] = "enhanced_data_collection"
    raw_data["requires_ai_analysis"] = True
    raw_data["fallback_available"] = True
    
    logger.info(f"Safety intelligence data collected for {token_address}")
    return raw_data

def search_tokens_raw(query: str, limit: int = 20) -> Dict[str, Any]:
    """Search for tokens using RugCheck - enhanced version"""
    return rugcheck_client.search_tokens_raw(query, limit)

def get_recent_tokens() -> Dict[str, Any]:
    """Get recently detected tokens"""
    return rugcheck_client.get_recent_tokens()

def get_trending_tokens() -> Dict[str, Any]:
    """Get trending tokens"""
    return rugcheck_client.get_trending_tokens()

# ============================================================================
# LEGACY COMPATIBILITY FUNCTIONS
# ============================================================================

def get_token_safety_analysis(token_address: str) -> Dict[str, Any]:
    """
    Legacy compatibility function - enhanced with better error handling
    Returns data in legacy format while using new backend
    """
    logger.warning("Legacy get_token_safety_analysis called - returning enhanced raw data")
    
    raw_data = get_token_safety_data_raw(token_address)
    
    # Return structure similar to old format but with raw data and AI placeholders
    return {
        # Raw data (new)
        "raw_safety_data": raw_data,
        
        # Placeholder values for legacy compatibility (AI will fill these from raw data)
        "safety_score": raw_data.get("score_raw", 0),
        "risk_level": "AI_ANALYSIS_REQUIRED",    # AI will determine from score_metrics
        "recommendation": "AI_ANALYSIS_REQUIRED", # AI will generate from all data
        "risk_factors": raw_data.get("risks_raw", []),
        "honeypot_risk": "AI_ANALYSIS_REQUIRED",  # AI will assess from security_data
        "rug_pull_risk": raw_data.get("security_raw", {}).get("rugged", False),
        "contract_verified": raw_data.get("security_data", {}).get("verification_present", False),
        "liquidity_locked": raw_data.get("lp_lock_analysis", {}).get("locked", False),  # Uses legacy field
        "ownership_concentration": raw_data.get("holder_concentration", {}).get("top_1_holder_pct", 0),  # Uses legacy field
        
        # Token metadata (extract from raw if available)
        "token_address": token_address,
        "token_symbol": raw_data.get("token_metadata_raw", {}).get("symbol", "Unknown"),
        "token_name": raw_data.get("token_metadata_raw", {}).get("name", "Unknown"),
        
        # Enhanced metadata
        "analysis_timestamp": datetime.now().isoformat(),
        "data_source": "rugcheck_enhanced",
        "requires_ai_processing": True,
        "legacy_compatibility": True,
        "data_available": raw_data.get("data_available", False),
        "working_endpoint": raw_data.get("working_endpoint"),
        "error": raw_data.get("error")
    }

def check_token_safety_comprehensive(token_address: str) -> Dict[str, Any]:
    """
    Legacy compatibility function for comprehensive safety check
    Now returns enhanced raw data that requires AI analysis
    """
    logger.warning("Legacy check_token_safety_comprehensive called - returning enhanced raw data")
    return get_token_safety_analysis(token_address)

def get_token_report(token_address: str, summary: bool = False) -> Dict[str, Any]:
    """Get token report using correct RugCheck API endpoint"""
    return rugcheck_client.get_token_report(token_address, summary)

def get_token_summary(token_address: str) -> Dict[str, Any]:
    """Get quick token summary for fast analysis"""
    return rugcheck_client.get_token_report(token_address, summary=True)

# ============================================================================
# ADDITIONAL UTILITY FUNCTIONS
# ============================================================================

def get_comprehensive_raw_token_data(token_address: str) -> Dict[str, Any]:
    """Alias for comprehensive token data collection"""
    return collect_safety_intelligence(token_address)

def get_ai_safety_analysis(token_address: str) -> Dict[str, Any]:
    """
    OPTIONAL: Get AI-powered analysis of RugCheck data
    This function uses your existing LLM infrastructure to analyze the raw data
    Only call this if you want AI judgments - otherwise use get_token_safety_data_raw()
    """
    try:
        # Import here to avoid circular dependencies
        from src.agent.pure_ai_agent import EnhancedPureAITradingAgent
        
        # Get raw data first
        raw_data = get_token_safety_data_raw(token_address)
        
        if not raw_data.get("data_available"):
            return {
                "token_address": token_address,
                "ai_analysis_available": False,
                "error": "No raw data available for AI analysis",
                "raw_data": raw_data
            }
        
        # Initialize AI agent
        agent = EnhancedPureAITradingAgent()
        
        if not agent.client:
            return {
                "token_address": token_address,
                "ai_analysis_available": False,
                "error": "AI agent not available",
                "raw_data": raw_data
            }
        
        # Create analysis prompt
        analysis_prompt = f"""
        Analyze this token safety data and provide risk assessment:
        
        Token Address: {token_address}
        
        Raw RugCheck Data:
        - Score: {raw_data.get('score_raw', 0)}
        - Risk Factors: {len(raw_data.get('risks_raw', []))} detected
        - Holder Concentration: Top holder has {raw_data.get('holder_metrics', {}).get('top_1_holder_pct', 0):.1f}%
        - Liquidity: ${raw_data.get('total_market_liquidity', 0):,.2f}
        - LP Locks: {raw_data.get('lp_lock_data', {}).get('total_locked_usd', 0)} USD locked
        - Mint Authority: {'Present' if raw_data.get('security_data', {}).get('mint_authority_present') else 'Renounced'}
        - Freeze Authority: {'Present' if raw_data.get('security_data', {}).get('freeze_authority_present') else 'Renounced'}
        
        Provide JSON response with:
        - risk_level: (very_low, low, moderate, high, very_high)
        - recommendation: (BUY, HOLD, AVOID)
        - confidence: (0-100)
        - reasoning: (explanation)
        - key_concerns: (array of main issues)
        """
        
        # Get AI analysis
        response = agent.client.messages.create(
            model=agent.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": analysis_prompt}]
        )
        
        ai_analysis_text = response.content[0].text
        
        # Try to parse JSON response
        try:
            import json
            ai_analysis = json.loads(ai_analysis_text)
        except:
            # If JSON parsing fails, create structured response
            ai_analysis = {
                "risk_level": "moderate",
                "recommendation": "REQUIRES_MANUAL_REVIEW",
                "confidence": 50,
                "reasoning": ai_analysis_text,
                "key_concerns": ["AI response parsing failed"]
            }
        
        return {
            "token_address": token_address,
            "ai_analysis_available": True,
            "ai_analysis": ai_analysis,
            "analysis_timestamp": datetime.now().isoformat(),
            "raw_data": raw_data
        }
        
    except Exception as e:
        logger.error(f"AI safety analysis failed for {token_address}: {e}")
        return {
            "token_address": token_address,
            "ai_analysis_available": False,
            "error": f"AI analysis failed: {str(e)}",
            "raw_data": get_token_safety_data_raw(token_address)
        }
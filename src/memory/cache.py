# src/memory/cache.py
"""
Memory and Caching System for Trading Agent
Provides in-memory caching with TTL expiration
"""
import time
import threading
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Configure logger
logger = logging.getLogger("trading_agent.cache")

# Global cache storage
_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.RLock()

def cache_data(key: str, data: Any, ttl_seconds: int = 300) -> None:
    """
    Cache data with a specified time-to-live
    
    Args:
        key: Unique cache key
        data: Data to cache
        ttl_seconds: Time-to-live in seconds
    """
    with _cache_lock:
        expiry = time.time() + ttl_seconds
        _cache[key] = {
            "data": data,
            "expiry": expiry,
            "created_at": datetime.now().isoformat()
        }
        logger.debug(f"Cached data for key '{key}' with TTL of {ttl_seconds} seconds")

def get_cached_data(key: str) -> Optional[Any]:
    """
    Retrieve data from cache if it exists and is not expired
    
    Args:
        key: Cache key to retrieve
        
    Returns:
        Any: Cached data or None if not found or expired
    """
    with _cache_lock:
        if key not in _cache:
            return None
            
        cache_entry = _cache[key]
        current_time = time.time()
        
        # Check if expired
        if current_time > cache_entry["expiry"]:
            # Remove expired entry
            del _cache[key]
            logger.debug(f"Cache entry for key '{key}' has expired")
            return None
            
        logger.debug(f"Retrieved cached data for key '{key}'")
        return cache_entry["data"]

def clear_cache(key: Optional[str] = None) -> None:
    """
    Clear the cache, either a specific key or all entries
    
    Args:
        key: Specific key to clear, or None to clear all
    """
    with _cache_lock:
        if key is None:
            _cache.clear()
            logger.debug("Cleared all cache entries")
        elif key in _cache:
            del _cache[key]
            logger.debug(f"Cleared cache entry for key '{key}'")

def clear_expired_entries() -> int:
    """
    Clear all expired cache entries
    
    Returns:
        int: Number of entries cleared
    """
    cleared_count = 0
    current_time = time.time()
    
    with _cache_lock:
        keys_to_clear = [
            key for key, entry in _cache.items()
            if current_time > entry["expiry"]
        ]
        
        for key in keys_to_clear:
            del _cache[key]
            cleared_count += 1
            
    if cleared_count > 0:
        logger.debug(f"Cleared {cleared_count} expired cache entries")
        
    return cleared_count

def get_cache_stats() -> Dict[str, Any]:
    """
    Get statistics about the current cache
    
    Returns:
        dict: Cache statistics
    """
    with _cache_lock:
        total_entries = len(_cache)
        current_time = time.time()
        
        expired_entries = sum(
            1 for entry in _cache.values()
            if current_time > entry["expiry"]
        )
        
        active_entries = total_entries - expired_entries
        
        # Calculate average remaining TTL for active entries
        avg_ttl = 0
        if active_entries > 0:
            ttl_sum = sum(
                max(0, entry["expiry"] - current_time)
                for entry in _cache.values()
                if current_time <= entry["expiry"]
            )
            avg_ttl = ttl_sum / active_entries
            
        return {
            "total_entries": total_entries,
            "active_entries": active_entries,
            "expired_entries": expired_entries,
            "avg_remaining_ttl_seconds": avg_ttl,
            "timestamp": datetime.now().isoformat()
        }

# Initialize a background thread to periodically clear expired entries
def _init_cache_cleaner():
    def clean_periodically():
        while True:
            time.sleep(60)  # Run every minute
            try:
                clear_expired_entries()
            except Exception as e:
                logger.error(f"Error in cache cleaner: {e}")
    
    cleaner_thread = threading.Thread(
        target=clean_periodically,
        daemon=True,
        name="CacheCleaner"
    )
    cleaner_thread.start()
    logger.debug("Started cache cleaner background thread")

# Initialize the cleaner thread
_init_cache_cleaner()
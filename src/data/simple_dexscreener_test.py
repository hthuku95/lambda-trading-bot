#!/usr/bin/env python3
# simple_dexscreener_test.py
"""
Simple test script for DexScreener API
Run this from: src/data/ directory
"""
import requests
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# DexScreener API endpoints
ENDPOINTS = {
    "token_boosts_latest": "https://api.dexscreener.com/token-boosts/latest/v1",
    "token_boosts_top": "https://api.dexscreener.com/token-boosts/top/v1", 
    "token_profiles_latest": "https://api.dexscreener.com/token-profiles/latest/v1",
    "search": "https://api.dexscreener.com/latest/dex/search"
}

def test_api_endpoint(name, url, params=None):
    """Test a specific API endpoint"""
    print(f"\n🔍 Testing {name}:")
    print(f"   URL: {url}")
    
    try:
        response = requests.get(url, params=params, timeout=15)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if isinstance(data, list):
                print(f"   ✅ Success: Found {len(data)} items")
                if data:
                    print(f"   📊 Sample item keys: {list(data[0].keys())}")
            elif isinstance(data, dict):
                if 'pairs' in data:
                    pairs = data['pairs']
                    print(f"   ✅ Success: Found {len(pairs)} pairs")
                    if pairs:
                        print(f"   📊 Sample pair keys: {list(pairs[0].keys())}")
                else:
                    print(f"   ✅ Success: Response keys: {list(data.keys())}")
            else:
                print(f"   ✅ Success: Response type: {type(data)}")
                
        elif response.status_code == 429:
            print(f"   ⚠️  Rate limited - too many requests")
        else:
            print(f"   ❌ Failed: {response.status_code} - {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print(f"   ⏰ Timeout - API might be slow")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request error: {e}")
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")

def test_search_functionality():
    """Test search with different queries"""
    print(f"\n🔍 Testing Search Functionality:")
    
    search_queries = ["sol", "pump", "meme", "SOL/USDC", "solana"]
    
    for query in search_queries:
        print(f"\n   Searching for: '{query}'")
        try:
            params = {"q": query}
            response = requests.get(ENDPOINTS["search"], params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                pairs = data.get('pairs', [])
                print(f"   ✅ Found {len(pairs)} results")
                
                if pairs:
                    # Show sample results
                    for i, pair in enumerate(pairs[:3]):
                        base_token = pair.get('baseToken', {})
                        symbol = base_token.get('symbol', 'Unknown')
                        price = pair.get('priceUsd', '0')
                        print(f"      {i+1}. {symbol} - ${price}")
            else:
                print(f"   ❌ Search failed: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Search error for '{query}': {e}")

def test_token_details():
    """Test getting details for a specific token"""
    print(f"\n🔍 Testing Token Details:")
    
    # Use SOL as a test token (should always exist)
    sol_address = "So11111111111111111111111111111111111111112"
    url = f"https://api.dexscreener.com/tokens/v1/solana/{sol_address}"
    
    try:
        response = requests.get(url, timeout=15)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: Found {len(data)} trading pairs for SOL")
            
            if data:
                pair = data[0]
                print(f"   📊 Sample pair data:")
                print(f"      Symbol: {pair.get('baseToken', {}).get('symbol', 'Unknown')}")
                print(f"      Price: ${pair.get('priceUsd', '0')}")
                print(f"      Liquidity: ${pair.get('liquidity', {}).get('usd', '0'):,.0f}")
                print(f"      Volume 24h: ${pair.get('volume', {}).get('h24', '0'):,.0f}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def main():
    """Run all tests"""
    print("🚀 SIMPLE DEXSCREENER API TEST")
    print("=" * 60)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Test individual endpoints
    test_api_endpoint("Latest Boosted Tokens", ENDPOINTS["token_boosts_latest"])
    test_api_endpoint("Top Boosted Tokens", ENDPOINTS["token_boosts_top"])
    test_api_endpoint("Latest Token Profiles", ENDPOINTS["token_profiles_latest"])
    
    # Test search functionality
    test_search_functionality()
    
    # Test token details
    test_token_details()
    
    print("\n" + "="*60)
    print("✅ SIMPLE TEST COMPLETED")
    print("="*60)
    print("\nIf you see successful responses above, the DexScreener API is working!")
    print("You can now proceed to implement the full enhanced system.")

if __name__ == "__main__":
    main()
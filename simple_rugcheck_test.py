# simple_rugcheck_test.py
"""
Simple test to verify RugCheck fixes - minimal API calls to avoid rate limits
"""
import sys

# Add the project root to the path for imports
sys.path.append('.')

try:
    from src.data.rugcheck_client import (
        check_rugcheck_api_health,
        get_token_safety_data_raw,
        RugCheckClient
    )
    print("✅ Imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def simple_test():
    print("🧪 SIMPLE RUGCHECK TEST")
    print("=" * 40)
    
    # Test 1: Check if legacy methods exist
    print("1. Testing RugCheckClient methods...")
    client = RugCheckClient()
    
    required_methods = [
        '_create_legacy_holder_analysis',
        '_create_legacy_market_analysis', 
        '_create_legacy_security_analysis',
        '_create_legacy_lp_analysis'
    ]
    
    missing_methods = []
    for method in required_methods:
        if not hasattr(client, method):
            missing_methods.append(method)
    
    if missing_methods:
        print(f"   ❌ Missing methods: {missing_methods}")
        print("   💡 The RugCheckClient class needs these legacy compatibility methods")
        return False
    else:
        print("   ✅ All required methods present")
    
    # Test 2: API Health (no rate limiting)
    print("\n2. Testing API health...")
    health = check_rugcheck_api_health()
    if health.get("healthy"):
        print(f"   ✅ API healthy - Base URL: {health.get('working_endpoint', 'Unknown')}")
    else:
        print(f"   ⚠️  API not healthy: {health.get('error', 'Unknown')}")
    
    # Test 3: Rate limit setting
    print(f"\n3. Rate limit delay: {client.session.headers}")
    print(f"   📍 Base URL: {client.base_url}")
    
    print("\n🎯 Fix Status:")
    if not missing_methods:
        print("✅ RugCheck implementation is ready for testing")
        print("💡 Run with longer delays between requests to avoid rate limits")
    else:
        print("❌ Implementation needs the missing methods added")
    
    return len(missing_methods) == 0

if __name__ == "__main__":
    success = simple_test()
    sys.exit(0 if success else 1)
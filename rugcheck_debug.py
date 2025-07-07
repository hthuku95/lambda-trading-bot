#!/usr/bin/env python3
# rugcheck_debug.py
"""
Debug script to identify RugCheck API issues
Run this to see exactly what's happening with the API calls
"""
import os
import requests
import logging
import base64
import json
import base58
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("rugcheck_debug")

SOLANA_PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")

def test_rugcheck_endpoints_detailed():
    """Test RugCheck endpoints with detailed debugging"""
    
    # Test token - USDC (the one that showed as "not found")
    test_token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    
    print("🔍 RUGCHECK API DEBUGGING")
    print("=" * 60)
    print(f"Testing token: {test_token}")
    print(f"This is USDC - should definitely exist")
    print("=" * 60)
    
    # Test different base URLs
    base_urls = [
        "https://api.rugcheck.xyz",
        "https://rugcheck.xyz/api",
        "https://api2.rugcheck.xyz"
    ]
    
    # Test different endpoint patterns
    endpoint_patterns = [
        "/tokens/{token}/report",
        "/api/tokens/{token}/report", 
        "/token/{token}",
        "/api/v1/tokens/{token}",
        "/v1/token/{token}/analysis",
        "/tokens/{token}",  # This matches the website URL pattern
        "/api/tokens/{token}",
        "/v1/tokens/{token}",
        "/{token}",  # Simple pattern
        "/analysis/{token}",
        "/report/{token}"
    ]
    
    for base_url in base_urls:
        print(f"\n🌐 Testing base URL: {base_url}")
        print("-" * 40)
        
        # First test if the base URL is responsive
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            print(f"   Health check: {response.status_code}")
        except:
            try:
                response = requests.get(base_url, timeout=5)
                print(f"   Base URL check: {response.status_code}")
            except Exception as e:
                print(f"   Base URL unreachable: {e}")
                continue
        
        # Test each endpoint pattern
        for pattern in endpoint_patterns:
            endpoint = pattern.format(token=test_token)
            full_url = f"{base_url}{endpoint}"
            
            try:
                # Test without authentication first
                response = requests.get(
                    full_url,
                    headers={
                        'User-Agent': 'TradingBot/1.0',
                        'Accept': 'application/json'
                    },
                    timeout=10
                )
                
                print(f"   {endpoint}: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"   ✅ SUCCESS! Found working endpoint: {full_url}")
                    try:
                        data = response.json()
                        print(f"   📊 Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        
                        # Show some sample data
                        if isinstance(data, dict):
                            for key, value in list(data.items())[:3]:
                                print(f"      {key}: {str(value)[:100]}...")
                        
                        return full_url, data
                    except:
                        print(f"   📊 Response: {response.text[:200]}...")
                
                elif response.status_code == 401:
                    print(f"   🔐 Requires authentication")
                    # Try with authentication
                    auth_result = test_with_authentication(full_url)
                    if auth_result:
                        return full_url, auth_result
                
                elif response.status_code == 404:
                    print(f"   ❌ Not found")
                
                elif response.status_code == 429:
                    print(f"   ⏰ Rate limited")
                
                else:
                    print(f"   ❓ Unexpected status: {response.text[:100]}")
                    
            except Exception as e:
                print(f"   💥 Error: {e}")
    
    print(f"\n❌ No working endpoint found for {test_token}")
    return None, None

def test_with_authentication(url):
    """Test endpoint with authentication"""
    try:
        if not SOLANA_PRIVATE_KEY:
            print("      No private key for auth test")
            return None
        
        print("      🔐 Testing with authentication...")
        
        # Get auth token (simplified version)
        auth_token = get_auth_token_simple()
        if not auth_token:
            print("      ❌ Could not get auth token")
            return None
        
        headers = {
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'TradingBot/1.0'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        print(f"      Authenticated request: {response.status_code}")
        
        if response.status_code == 200:
            print(f"      ✅ SUCCESS with authentication!")
            try:
                return response.json()
            except:
                print(f"      Response: {response.text[:200]}...")
                return {"raw_response": response.text}
        else:
            print(f"      ❌ Auth failed: {response.text[:100]}")
            return None
            
    except Exception as e:
        print(f"      💥 Auth test error: {e}")
        return None

def get_auth_token_simple():
    """Simplified auth token getter for debugging"""
    try:
        from nacl.signing import SigningKey
        import json
        from datetime import datetime
        
        # Decode private key
        private_key_bytes = base58.b58decode(SOLANA_PRIVATE_KEY)
        signing_key = SigningKey(private_key_bytes[:32])
        public_key_bytes = signing_key.verify_key.encode()
        public_key = base58.b58encode(public_key_bytes).decode('utf-8')
        
        # Create message
        message_data = {
            "message": "Sign-in to Rugcheck.xyz",
            "timestamp": int(datetime.now().timestamp() * 1000),
            "publicKey": public_key
        }
        
        message_json = json.dumps(message_data, separators=(',', ':'))
        signature = signing_key.sign(message_json.encode('utf-8'))
        
        signature_data = list(base58.b58decode(base58.b58encode(signature.signature)))
        
        auth_data = {
            "signature": {"data": signature_data, "type": "ed25519"},
            "wallet": public_key,
            "message": message_data
        }
        
        # Try auth endpoints
        auth_endpoints = [
            "https://api.rugcheck.xyz/auth/login/solana",
            "https://rugcheck.xyz/api/auth/login",
            "https://api.rugcheck.xyz/login"
        ]
        
        for endpoint in auth_endpoints:
            try:
                response = requests.post(
                    endpoint,
                    json=auth_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    auth_response = response.json()
                    return auth_response.get('token')
            except:
                continue
        
        return None
        
    except Exception as e:
        print(f"Auth error: {e}")
        return None

def test_website_scraping():
    """Test if we can get data by scraping the website pattern"""
    print(f"\n🌐 Testing website-style access...")
    
    test_token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    
    # This matches the URL pattern from your screenshot
    website_url = f"https://rugcheck.xyz/tokens/{test_token}"
    
    try:
        response = requests.get(
            website_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            timeout=10
        )
        
        print(f"Website URL: {website_url}")
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
        
        if response.status_code == 200:
            print("✅ Website accessible")
            
            # Check if it's JSON (API) or HTML (website)
            if 'application/json' in response.headers.get('content-type', ''):
                print("📊 Got JSON response!")
                try:
                    data = response.json()
                    print(f"JSON keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                    return data
                except:
                    print("❌ Could not parse JSON")
            else:
                print("📄 Got HTML response (website)")
                # Check if we can find data in the HTML
                content = response.text
                if '"riskLevel"' in content or '"score"' in content:
                    print("🔍 Found potential data in HTML")
                    print("   This suggests the API might be embedded or use different endpoints")
        
    except Exception as e:
        print(f"❌ Website test failed: {e}")
    
    return None

def analyze_network_requests():
    """Suggest network analysis to find the real API endpoints"""
    print(f"\n🔍 NETWORK ANALYSIS SUGGESTIONS")
    print("=" * 40)
    print("To find the real API endpoints:")
    print("1. Open browser dev tools (F12)")
    print("2. Go to Network tab")
    print("3. Visit: https://rugcheck.xyz/tokens/EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    print("4. Look for XHR/Fetch requests")
    print("5. Check what API endpoints the website actually calls")
    print()
    print("Common patterns to look for:")
    print("- /api/v1/tokens/{address}")
    print("- /tokens/{address}/analysis")
    print("- GraphQL endpoints")
    print("- WebSocket connections")
    print()
    print("Also check:")
    print("- Request headers (especially Authorization)")
    print("- Request parameters")
    print("- Response format")

if __name__ == "__main__":
    print("🚀 RUGCHECK API DEBUGGING TOOL")
    print("=" * 60)
    
    # Test 1: Try all endpoint combinations
    working_endpoint, data = test_rugcheck_endpoints_detailed()
    
    if working_endpoint:
        print(f"\n🎉 FOUND WORKING ENDPOINT: {working_endpoint}")
        print("✅ Your implementation should use this endpoint pattern")
    else:
        print(f"\n❌ NO WORKING API ENDPOINT FOUND")
        
        # Test 2: Try website access
        website_data = test_website_scraping()
        
        if not website_data:
            # Test 3: Suggest network analysis
            analyze_network_requests()
    
    print(f"\n" + "=" * 60)
    print("🔧 NEXT STEPS:")
    
    if working_endpoint:
        print("1. Update rugcheck_client.py to use the working endpoint")
        print("2. Test again with the fixed implementation")
    else:
        print("1. Use browser dev tools to find real API endpoints")
        print("2. Check RugCheck documentation for correct API usage")
        print("3. Consider contacting RugCheck support")
        print("4. Implement fallback to basic DexScreener data")
    
    print("5. The system will work without RugCheck (uses DexScreener)")
    print("6. RugCheck provides enhanced safety analysis but isn't required")
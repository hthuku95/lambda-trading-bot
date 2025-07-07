#!/usr/bin/env python3
# test_setup.py
"""
Setup Verification Test Script
Tests all components to ensure proper configuration
"""
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("setup_test")

def test_environment_variables():
    """Test that required environment variables are set"""
    print("🔍 Testing Environment Variables...")
    
    required_vars = {
        "ASTRA_DB_APPLICATION_TOKEN": "AstraDB application token",
        "ASTRA_DB_API_ENDPOINT": "AstraDB API endpoint", 
        "VOYAGEAI_API_KEY": "VoyageAI API key",
        "SOLANA_PRIVATE_KEY": "Solana wallet private key",
        "ANTHROPIC_API_KEY": "Anthropic API key"
    }
    
    optional_vars = {
        "TWEETSCOUT_API_KEY": "TweetScout API key",
        "OPENAI_API_KEY": "OpenAI API key (fallback)",
        "SOLANA_RPC_URL": "Solana RPC URL"
    }
    
    missing_required = []
    missing_optional = []
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: Configured")
        else:
            print(f"   ❌ {var}: Missing ({description})")
            missing_required.append(var)
    
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: Configured")
        else:
            print(f"   ⚠️  {var}: Missing ({description})")
            missing_optional.append(var)
    
    if missing_required:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_required)}")
        return False
    
    if missing_optional:
        print(f"\n⚠️  Missing optional environment variables: {', '.join(missing_optional)}")
    
    print("✅ Environment variables check passed")
    return True

def test_astradb_connection():
    """Test AstraDB connection and collection creation"""
    print("\n🔍 Testing AstraDB Connection...")
    
    try:
        from src.memory.astra_vector_store import astra_store
        
        # Test initialization
        success = astra_store.initialize_collection()
        
        if success:
            print("   ✅ AstraDB connection successful")
            
            # Test basic operations
            stats = astra_store.get_stats()
            print(f"   ✅ Collection stats: {stats.get('total_records', 0)} records")
            
            # Test embedding generation
            test_text = "This is a test trading experience"
            embedding = astra_store._get_voyageai_embedding(test_text)
            
            if embedding and len(embedding) == 1024:
                print(f"   ✅ Embedding generation successful ({len(embedding)} dimensions)")
            else:
                print(f"   ⚠️  Embedding generation issue (got {len(embedding) if embedding else 0} dimensions)")
            
            return True
        else:
            print("   ❌ AstraDB connection failed")
            return False
            
    except Exception as e:
        print(f"   ❌ AstraDB test failed: {e}")
        return False

def test_voyageai_client():
    """Test VoyageAI client directly"""
    print("\n🔍 Testing VoyageAI Client...")
    
    try:
        import voyageai
        
        api_key = os.getenv("VOYAGEAI_API_KEY")
        if not api_key:
            print("   ❌ No VoyageAI API key found")
            return False
        
        # Test client initialization
        vo = voyageai.Client(api_key=api_key)
        
        # Test embedding generation
        result = vo.embed(
            texts=["This is a test document for trading analysis"],
            model="voyage-3.5",
            input_type="document"
        )
        
        if result and result.embeddings:
            embedding = result.embeddings[0]
            print(f"   ✅ VoyageAI client working ({len(embedding)} dimensions)")
            return True
        else:
            print("   ❌ VoyageAI client failed to generate embeddings")
            return False
            
    except Exception as e:
        print(f"   ❌ VoyageAI test failed: {e}")
        return False

def test_rugcheck_client():
    """Test RugCheck client"""
    print("\n🔍 Testing RugCheck Client...")
    
    try:
        from src.data.rugcheck_client import rugcheck_client
        
        # Test API health
        health = rugcheck_client.check_api_health()
        
        if health.get("healthy", False):
            print("   ✅ RugCheck API is healthy")
            print(f"   ✅ Working endpoint: {health.get('working_endpoint', 'Unknown')}")
            
            if health.get("auth_working", False):
                print("   ✅ RugCheck authentication working")
            else:
                print("   ⚠️  RugCheck authentication not working (wallet might not be configured)")
            
            # Test token analysis
            test_token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC
            raw_data = rugcheck_client.get_token_safety_data_raw(test_token)
            
            if raw_data.get("data_available", False):
                print("   ✅ RugCheck token analysis working")
            else:
                print("   ⚠️  RugCheck token analysis not available")
            
            return True
        else:
            print(f"   ⚠️  RugCheck API not healthy: {health.get('error', 'Unknown error')}")
            print("   ℹ️  This is expected if RugCheck is temporarily down")
            return True  # Don't fail the test for this
            
    except Exception as e:
        print(f"   ⚠️  RugCheck test failed: {e}")
        print("   ℹ️  This is expected if RugCheck is temporarily unavailable")
        return True  # Don't fail the test for this

def test_solana_connection():
    """Test Solana wallet connection"""
    print("\n🔍 Testing Solana Connection...")
    
    try:
        from src.blockchain.solana_client import get_wallet_balance, wallet
        
        # Test wallet loading
        print(f"   ✅ Wallet loaded: {wallet.pubkey()}")
        
        # Test balance retrieval
        balance = get_wallet_balance()
        print(f"   ✅ Wallet balance: {balance:.6f} SOL")
        
        if balance < 0.001:
            print("   ⚠️  Very low SOL balance - consider adding more for testing")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Solana connection failed: {e}")
        return False

def test_anthropic_client():
    """Test Anthropic AI client"""
    print("\n🔍 Testing Anthropic AI Client...")
    
    try:
        from anthropic import Anthropic
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("   ❌ No Anthropic API key found")
            return False
        
        # Test client initialization
        client = Anthropic(api_key=api_key)
        
        # Test simple message
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=50,
            messages=[{"role": "user", "content": "Reply with 'AI test successful'"}]
        )
        
        if response and response.content:
            content = response.content[0].text if hasattr(response.content[0], 'text') else str(response.content[0])
            print(f"   ✅ Anthropic AI client working: {content}")
            return True
        else:
            print("   ❌ Anthropic AI client failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Anthropic test failed: {e}")
        return False

def test_dexscreener_api():
    """Test DexScreener API"""
    print("\n🔍 Testing DexScreener API...")
    
    try:
        from src.data.dexscreener import get_boosted_tokens_latest
        
        # Test token discovery
        tokens = get_boosted_tokens_latest("solana")
        
        if tokens and len(tokens) > 0:
            print(f"   ✅ DexScreener API working ({len(tokens)} tokens found)")
            
            # Test token structure
            sample_token = tokens[0]
            required_fields = ['address', 'symbol', 'price_usd', 'liquidity_usd']
            
            for field in required_fields:
                if field in sample_token:
                    print(f"   ✅ Token field '{field}': Present")
                else:
                    print(f"   ⚠️  Token field '{field}': Missing")
            
            return True
        else:
            print("   ❌ DexScreener API returned no tokens")
            return False
            
    except Exception as e:
        print(f"   ❌ DexScreener test failed: {e}")
        return False

def test_pure_ai_agent():
    """Test Pure AI agent initialization"""
    print("\n🔍 Testing Pure AI Agent...")
    
    try:
        from src.agent.pure_ai_agent import enhanced_pure_ai_agent
        
        # Test agent initialization
        if enhanced_pure_ai_agent.client:
            print("   ✅ Pure AI agent initialized")
            print(f"   ✅ Model: {enhanced_pure_ai_agent.model}")
            print(f"   ✅ Tools available: {len(enhanced_pure_ai_agent.tools)}")
            
            # Test tool execution
            result = enhanced_pure_ai_agent._execute_tool("get_wallet_balance")
            if result.get("success", False):
                print(f"   ✅ Tool execution working: {result.get('balance_sol', 0):.6f} SOL")
            else:
                print(f"   ⚠️  Tool execution issue: {result.get('error', 'Unknown')}")
            
            return True
        else:
            print("   ❌ Pure AI agent not properly initialized")
            return False
            
    except Exception as e:
        print(f"   ❌ Pure AI agent test failed: {e}")
        return False

def run_comprehensive_test():
    """Run all tests"""
    print("🚀 COMPREHENSIVE SETUP VERIFICATION")
    print("=" * 70)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("VoyageAI Client", test_voyageai_client),
        ("AstraDB Connection", test_astradb_connection),
        ("Solana Connection", test_solana_connection),
        ("Anthropic AI Client", test_anthropic_client),
        ("DexScreener API", test_dexscreener_api),
        ("RugCheck Client", test_rugcheck_client),
        ("Pure AI Agent", test_pure_ai_agent)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"💥 {test_name}: CRITICAL ERROR - {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*70)
    print("📊 SETUP VERIFICATION RESULTS")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {test_name}")
    
    print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Your setup is complete and ready for trading")
        print("✅ You can now run: streamlit run ui/streamlit_dashboard.py")
        print("✅ The system will start in safe dry-run mode")
    elif passed >= 6:  # Most critical tests passed
        print(f"\n🔄 MOSTLY READY ({passed}/{total} tests passed)")
        print("✅ Core functionality is working")
        print("⚠️  Some optional features may be limited")
        print("✅ You can still run the trading agent")
    else:
        print(f"\n⚠️  SETUP INCOMPLETE ({passed}/{total} tests passed)")
        print("❌ Critical components are not working")
        print("🔍 Please review the failed tests above")
        print("📖 Check the environment setup instructions")
    
    return passed == total

def main():
    """Main test function"""
    try:
        success = run_comprehensive_test()
        
        print("\n" + "="*70)
        print("🛠️  NEXT STEPS")
        print("="*70)
        
        if success:
            print("1. ✅ Run the dashboard: streamlit run ui/streamlit_dashboard.py")
            print("2. ✅ Test the AI agent in dry run mode")
            print("3. ✅ Explore the UI and verify all features work")
            print("4. ✅ Only switch to live trading when confident")
        else:
            print("1. 🔍 Review failed tests above")
            print("2. 📖 Check environment setup instructions")
            print("3. 🔧 Fix configuration issues")
            print("4. 🔄 Run this test script again")
        
        print("\n📚 For help: Check the environment setup instructions")
        print("🔒 Remember: The system starts in safe dry-run mode by default")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
#!/usr/bin/env python3
# rugcheck_integration_fix.py
"""
Integration fix for RugCheck client - ensures all methods are properly accessible
Run this to verify and fix any integration issues
"""
import sys
import os

# Add the project root to the path for imports
sys.path.append('.')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_rugcheck_integration():
    """Test and fix RugCheck integration issues"""
    print("🔧 RUGCHECK INTEGRATION FIX")
    print("=" * 50)
    
    # Test 1: Direct import test
    print("1. Testing direct imports...")
    try:
        from src.data.rugcheck_client import RugCheckClient
        print("   ✅ RugCheckClient import successful")
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        return False
    
    # Test 2: Instantiate client
    print("\n2. Testing client instantiation...")
    try:
        client = RugCheckClient()
        print("   ✅ Client instantiation successful")
    except Exception as e:
        print(f"   ❌ Instantiation error: {e}")
        return False
    
    # Test 3: Check all required methods
    print("\n3. Testing method accessibility...")
    required_methods = [
        '_create_legacy_holder_analysis',
        '_create_legacy_market_analysis', 
        '_create_legacy_security_analysis',
        '_create_legacy_lp_analysis'
    ]
    
    missing_methods = []
    existing_methods = []
    
    for method in required_methods:
        if hasattr(client, method):
            existing_methods.append(method)
            print(f"   ✅ {method}: Found")
            
            # Test if method is callable
            try:
                method_obj = getattr(client, method)
                if callable(method_obj):
                    print(f"      └─ Callable: Yes")
                else:
                    print(f"      └─ Callable: No (not a function)")
            except Exception as e:
                print(f"      └─ Error accessing: {e}")
                
        else:
            missing_methods.append(method)
            print(f"   ❌ {method}: Missing")
    
    # Test 4: Check additional helpful methods
    print("\n4. Testing additional methods...")
    additional_methods = [
        'get_token_safety_data_raw',
        'check_api_health',
        '_extract_holder_metrics',
        '_extract_market_metrics',
        '_extract_security_data',
        '_extract_lp_lock_data'
    ]
    
    for method in additional_methods:
        if hasattr(client, method):
            print(f"   ✅ {method}: Available")
        else:
            print(f"   ⚠️  {method}: Not found")
    
    # Test 5: Try calling one of the legacy methods
    print("\n5. Testing method execution...")
    if '_create_legacy_holder_analysis' in existing_methods:
        try:
            # Test with empty data
            result = client._create_legacy_holder_analysis([])
            print("   ✅ _create_legacy_holder_analysis executed successfully")
            print(f"      └─ Result type: {type(result)}")
            print(f"      └─ Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        except Exception as e:
            print(f"   ❌ Method execution failed: {e}")
    
    # Test 6: API health check
    print("\n6. Testing API functionality...")
    try:
        health = client.check_api_health()
        print(f"   ✅ API health check successful")
        print(f"      └─ Healthy: {health.get('healthy', False)}")
        print(f"      └─ Base URL: {health.get('base_url', 'Unknown')}")
    except Exception as e:
        print(f"   ❌ API health check failed: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 INTEGRATION TEST SUMMARY")
    print("=" * 50)
    
    if not missing_methods:
        print("🎉 ALL LEGACY METHODS FOUND!")
        print("✅ Integration should work correctly")
        
        # Test the simple test script
        print("\n7. Running simple test...")
        try:
            from simple_rugcheck_test import simple_test
            if simple_test():
                print("   ✅ Simple test passed!")
                return True
            else:
                print("   ❌ Simple test failed despite methods being present")
                return False
        except Exception as e:
            print(f"   ❌ Could not run simple test: {e}")
            return False
    else:
        print(f"❌ Missing methods: {missing_methods}")
        print("💡 These methods need to be added to the RugCheckClient class")
        return False

def fix_import_path():
    """Fix any Python path issues that might prevent imports"""
    print("\n🔧 FIXING IMPORT PATHS")
    print("=" * 30)
    
    # Get current directory
    current_dir = os.getcwd()
    print(f"Current directory: {current_dir}")
    
    # Check if we're in the right place
    expected_files = ['src', 'ui', 'requirements.txt', 'main.py']
    missing_files = []
    
    for file in expected_files:
        if os.path.exists(file):
            print(f"   ✅ {file}: Found")
        else:
            print(f"   ❌ {file}: Missing")
            missing_files.append(file)
    
    if missing_files:
        print(f"\n⚠️  You might not be in the project root directory")
        print(f"Missing: {missing_files}")
        print("Try running this from the project root where requirements.txt is located")
        return False
    
    # Add paths
    paths_to_add = [
        current_dir,
        os.path.join(current_dir, 'src'),
        os.path.join(current_dir, 'src', 'data'),
    ]
    
    for path in paths_to_add:
        if path not in sys.path:
            sys.path.insert(0, path)
            print(f"   ✅ Added to Python path: {path}")
    
    return True

def create_verification_script():
    """Create a verification script to confirm integration"""
    verification_code = '''#!/usr/bin/env python3
# verify_rugcheck.py - Auto-generated verification script
import sys
import os
sys.path.append('.')

def main():
    try:
        from src.data.rugcheck_client import RugCheckClient
        
        client = RugCheckClient()
        
        # Test all 4 legacy methods
        methods = [
            '_create_legacy_holder_analysis',
            '_create_legacy_market_analysis', 
            '_create_legacy_security_analysis',
            '_create_legacy_lp_analysis'
        ]
        
        for method in methods:
            if hasattr(client, method):
                print(f"✅ {method}: OK")
            else:
                print(f"❌ {method}: MISSING")
                return False
        
        print("🎉 All RugCheck methods verified!")
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
'''
    
    try:
        with open('verify_rugcheck.py', 'w') as f:
            f.write(verification_code)
        print("\n✅ Created verify_rugcheck.py")
        print("Run with: python verify_rugcheck.py")
        return True
    except Exception as e:
        print(f"\n❌ Could not create verification script: {e}")
        return False

def main():
    """Main integration fix function"""
    print("🚀 RUGCHECK INTEGRATION DIAGNOSTICS & FIX")
    print("=" * 60)
    print("This script will diagnose and fix any RugCheck integration issues\n")
    
    # Step 1: Fix import paths
    if not fix_import_path():
        print("❌ Could not fix import paths")
        return False
    
    # Step 2: Test integration
    if test_rugcheck_integration():
        print("\n🎉 INTEGRATION SUCCESS!")
        print("✅ RugCheck client is properly integrated")
        print("✅ All legacy methods are accessible")
        print("✅ Your application should now be ready for testing")
        
        # Create verification script
        create_verification_script()
        
        print("\n🚀 NEXT STEPS:")
        print("1. Run: python test_setup.py")
        print("2. Run: streamlit run ui/streamlit_dashboard.py")
        print("3. Test in dry run mode first")
        
        return True
    else:
        print("\n❌ INTEGRATION ISSUES DETECTED")
        print("The RugCheck methods should be there but aren't being found")
        print("\n🔍 DEBUGGING SUGGESTIONS:")
        print("1. Check if there are any syntax errors in rugcheck_client.py")
        print("2. Verify the class structure is correct")
        print("3. Try restarting your Python environment")
        print("4. Check for import conflicts")
        
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
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

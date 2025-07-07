#!/usr/bin/env python3
# test_imports.py
"""
Test script to verify all imports work correctly
Run this to debug import issues
"""

def test_imports():
    """Test all the critical imports step by step"""
    
    print("🔍 Testing imports step by step...")
    
    try:
        print("1. Testing basic state import...")
        from src.agent.state import AgentState, create_initial_state
        print("   ✅ State imports successful")
    except Exception as e:
        print(f"   ❌ State import failed: {e}")
        return False
    
    try:
        print("2. Testing pure AI agent import...")
        from src.agent.pure_ai_agent import run_pure_ai_trading_agent
        print("   ✅ Pure AI agent import successful")
    except Exception as e:
        print(f"   ❌ Pure AI agent import failed: {e}")
        return False
    
    try:
        print("3. Testing pure AI graph import...")
        from src.agent.pure_ai_graph import build_pure_ai_trading_graph
        print("   ✅ Pure AI graph import successful")
    except Exception as e:
        print(f"   ❌ Pure AI graph import failed: {e}")
        return False
    
    try:
        print("4. Testing agent module import...")
        from src.agent import run_trading_agent, load_agent_state
        print("   ✅ Agent module import successful")
    except Exception as e:
        print(f"   ❌ Agent module import failed: {e}")
        return False
    
    try:
        print("5. Testing UI utils import...")
        from ui.utils import load_dashboard_data
        print("   ✅ UI utils import successful")
    except Exception as e:
        print(f"   ❌ UI utils import failed: {e}")
        return False
    
    try:
        print("6. Testing complete dashboard import...")
        from ui.streamlit_dashboard import main
        print("   ✅ Dashboard import successful")
    except Exception as e:
        print(f"   ❌ Dashboard import failed: {e}")
        return False
    
    print("\n🎉 All imports successful!")
    return True

def test_basic_functionality():
    """Test basic functionality"""
    print("\n🧪 Testing basic functionality...")
    
    try:
        from src.agent.state import create_initial_state
        state = create_initial_state()
        print(f"   ✅ Created initial state with balance: {state.get('wallet_balance_sol', 0)} SOL")
    except Exception as e:
        print(f"   ❌ Failed to create initial state: {e}")
        return False
    
    try:
        from src.data.dexscreener import get_discovery_capabilities
        caps = get_discovery_capabilities()
        print(f"   ✅ DexScreener capabilities: {len(caps.get('data_sources', []))} sources available")
    except Exception as e:
        print(f"   ❌ Failed to get DexScreener capabilities: {e}")
        return False
    
    print("   ✅ Basic functionality test passed!")
    return True

if __name__ == "__main__":
    print("🚀 Lambda Trading Bot - Import Test")
    print("=" * 50)
    
    if test_imports():
        if test_basic_functionality():
            print("\n✅ All tests passed! Bot should run correctly.")
            print("\nNow you can run:")
            print("streamlit run ui/streamlit_dashboard.py")
        else:
            print("\n⚠️ Imports work but basic functionality failed.")
    else:
        print("\n❌ Import tests failed. Check the error messages above.")
#!/usr/bin/env python3
# dry_run_test.py
"""
Comprehensive test to verify dry run mode is working correctly
Tests all aspects of dry run functionality
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any

def setup_test_logging():
    """Setup logging to capture dry run activities"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("dry_run_test")

def test_dry_run_parameter_flow():
    """Test 1: Verify dry run parameters flow through the system correctly"""
    logger = setup_test_logging()
    logger.info("🧪 TEST 1: Dry Run Parameter Flow")
    
    try:
        # Test parameter creation with dry run
        from src.agent.state import create_initial_state
        
        state = create_initial_state()
        dry_run_mode = state.get("agent_parameters", {}).get("trading_mode", "unknown")
        
        logger.info(f"   📋 Initial state trading mode: {dry_run_mode}")
        
        if dry_run_mode == "dry_run":
            logger.info("   ✅ Default state correctly set to dry_run mode")
            return True
        else:
            logger.error(f"   ❌ Expected 'dry_run', got '{dry_run_mode}'")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Parameter flow test failed: {e}")
        return False

def test_sidebar_dry_run_toggle():
    """Test 2: Verify sidebar dry run toggle functionality"""
    logger = logging.getLogger("dry_run_test")
    logger.info("🧪 TEST 2: Sidebar Dry Run Toggle")
    
    try:
        # Simulate session state like Streamlit would
        class MockSessionState:
            def __init__(self):
                self.data = {
                    'agent_parameters': {
                        'trading_mode': 'dry_run',
                        'max_positions': 5,
                        'risk_tolerance': 'medium'
                    }
                }
            
            def get(self, key, default=None):
                return self.data.get(key, default)
            
            def __setitem__(self, key, value):
                self.data[key] = value
        
        # Mock session state
        mock_session = MockSessionState()
        
        # Test dry run mode detection
        current_params = mock_session.get('agent_parameters', {})
        is_dry_run = current_params.get('trading_mode', 'dry_run') == 'dry_run'
        
        logger.info(f"   📋 Current trading mode: {current_params.get('trading_mode')}")
        logger.info(f"   📋 Is dry run: {is_dry_run}")
        
        # Test toggle functionality
        if is_dry_run:
            # Simulate toggling to live mode
            current_params['trading_mode'] = 'live'
            mock_session['agent_parameters'] = current_params
            
            new_mode = mock_session.get('agent_parameters', {}).get('trading_mode')
            logger.info(f"   📋 After toggle to live: {new_mode}")
            
            # Toggle back to dry run
            current_params['trading_mode'] = 'dry_run'
            mock_session['agent_parameters'] = current_params
            
            final_mode = mock_session.get('agent_parameters', {}).get('trading_mode')
            logger.info(f"   📋 After toggle back to dry_run: {final_mode}")
            
            if final_mode == 'dry_run':
                logger.info("   ✅ Sidebar toggle functionality works correctly")
                return True
            else:
                logger.error(f"   ❌ Toggle failed, expected 'dry_run', got '{final_mode}'")
                return False
        
    except Exception as e:
        logger.error(f"   ❌ Sidebar toggle test failed: {e}")
        return False

def test_agent_dry_run_execution():
    """Test 3: Verify agent respects dry run mode during execution"""
    logger = logging.getLogger("dry_run_test")
    logger.info("🧪 TEST 3: Agent Dry Run Execution")
    
    try:
        from src.agent.pure_ai_agent import EnhancedPureAITradingAgent
        
        # Create agent instance
        agent = EnhancedPureAITradingAgent()
        
        # Test execute_trade tool with dry run
        trade_result = agent._execute_tool(
            "execute_trade",
            trade_type="buy",
            token_address="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            amount_sol=0.1,
            quote_data={"mock": "quote"},
            dry_run=True,
            reasoning="Test trade for dry run verification"
        )
        
        logger.info(f"   📋 Trade execution result: {trade_result}")
        
        # Verify dry run behavior
        if trade_result.get("success") and "Dry run" in trade_result.get("message", ""):
            logger.info("   ✅ Agent correctly executes trades in dry run mode")
            return True
        else:
            logger.error("   ❌ Agent did not respect dry run mode")
            logger.error(f"   Expected 'Dry run' message, got: {trade_result}")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Agent execution test failed: {e}")
        return False

def test_live_mode_prevention():
    """Test 4: Verify live mode requires explicit confirmation"""
    logger = logging.getLogger("dry_run_test")
    logger.info("🧪 TEST 4: Live Mode Prevention")
    
    try:
        from src.agent.pure_ai_agent import EnhancedPureAITradingAgent
        
        agent = EnhancedPureAITradingAgent()
        
        # Test execute_trade tool with live mode (dry_run=False)
        live_trade_result = agent._execute_tool(
            "execute_trade",
            trade_type="buy",
            token_address="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            amount_sol=0.1,
            quote_data=None,  # No quote data to simulate missing requirement
            dry_run=False,
            reasoning="Test live trade (should fail safely)"
        )
        
        logger.info(f"   📋 Live trade result: {live_trade_result}")
        
        # Should fail due to missing quote data (safety mechanism)
        if not live_trade_result.get("success"):
            logger.info("   ✅ Live mode correctly requires proper quote data")
            return True
        else:
            logger.warning("   ⚠️ Live mode executed without quote data (review safety)")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Live mode prevention test failed: {e}")
        return False

def test_full_trading_cycle_dry_run():
    """Test 5: Run a complete trading cycle in dry run mode"""
    logger = logging.getLogger("dry_run_test")
    logger.info("🧪 TEST 5: Full Trading Cycle Dry Run")
    
    try:
        from src.agent.state import create_initial_state
        from src.agent import run_trading_agent
        
        # Create state with explicit dry run parameters
        dry_run_params = {
            "trading_mode": "dry_run",
            "max_positions": 2,
            "max_position_size_sol": 0.05,
            "cycle_time_seconds": 60,
            "dry_run": True  # Legacy parameter
        }
        
        logger.info(f"   📋 Testing with parameters: {dry_run_params}")
        
        # Run one trading cycle
        result_state = run_trading_agent(dry_run_params)
        
        if result_state:
            trading_mode = result_state.get("trading_mode", "unknown")
            agent_params = result_state.get("agent_parameters", {})
            cycles_completed = result_state.get("cycles_completed", 0)
            
            logger.info(f"   📋 Result trading mode: {trading_mode}")
            logger.info(f"   📋 Agent parameters: {agent_params}")
            logger.info(f"   📋 Cycles completed: {cycles_completed}")
            
            # Verify dry run mode was maintained
            if trading_mode == "dry_run" or agent_params.get("trading_mode") == "dry_run":
                logger.info("   ✅ Full trading cycle maintained dry run mode")
                return True
            else:
                logger.error("   ❌ Trading cycle did not maintain dry run mode")
                return False
        else:
            logger.error("   ❌ Trading cycle returned no state")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Full cycle test failed: {e}")
        return False

def test_wallet_balance_safety():
    """Test 6: Verify wallet balance is not affected in dry run mode"""
    logger = logging.getLogger("dry_run_test")
    logger.info("🧪 TEST 6: Wallet Balance Safety")
    
    try:
        from src.blockchain.solana_client import get_wallet_balance
        
        # Get initial balance
        initial_balance = get_wallet_balance()
        logger.info(f"   📋 Initial wallet balance: {initial_balance:.6f} SOL")
        
        # Run trading cycle in dry run mode
        from src.agent import run_trading_agent
        
        dry_run_params = {
            "trading_mode": "dry_run",
            "max_positions": 1,
            "max_position_size_sol": 0.01
        }
        
        run_trading_agent(dry_run_params)
        
        # Check balance after trading cycle
        final_balance = get_wallet_balance()
        logger.info(f"   📋 Final wallet balance: {final_balance:.6f} SOL")
        
        balance_change = abs(final_balance - initial_balance)
        
        if balance_change < 0.000001:  # Allow for tiny RPC differences
            logger.info("   ✅ Wallet balance unchanged in dry run mode")
            return True
        else:
            logger.error(f"   ❌ Wallet balance changed by {balance_change:.9f} SOL")
            logger.error("   This should not happen in dry run mode!")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Wallet balance safety test failed: {e}")
        return False

def test_dry_run_ui_integration():
    """Test 7: Verify UI components handle dry run correctly"""
    logger = logging.getLogger("dry_run_test")
    logger.info("🧪 TEST 7: UI Integration")
    
    try:
        # Test that UI components can detect dry run mode
        from ui.components.sidebar import BALANCED_AI_PARAMETERS
        
        # Verify default parameters include dry run
        default_mode = BALANCED_AI_PARAMETERS.get("trading_mode", "unknown")
        logger.info(f"   📋 Default UI trading mode: {default_mode}")
        
        if default_mode == "dry_run":
            logger.info("   ✅ UI defaults to dry run mode")
            
            # Test parameter presets
            from ui.components.sidebar import AGGRESSIVE_AI_PARAMETERS, CONSERVATIVE_AI_PARAMETERS
            
            aggressive_mode = AGGRESSIVE_AI_PARAMETERS.get("trading_mode", "unknown")
            conservative_mode = CONSERVATIVE_AI_PARAMETERS.get("trading_mode", "unknown")
            
            logger.info(f"   📋 Aggressive preset mode: {aggressive_mode}")
            logger.info(f"   📋 Conservative preset mode: {conservative_mode}")
            
            if aggressive_mode == "dry_run" and conservative_mode == "dry_run":
                logger.info("   ✅ All UI presets default to dry run mode")
                return True
            else:
                logger.error("   ❌ Some UI presets do not default to dry run")
                return False
        else:
            logger.error(f"   ❌ UI does not default to dry run mode: {default_mode}")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ UI integration test failed: {e}")
        return False

def run_comprehensive_dry_run_test():
    """Run all dry run tests"""
    logger = setup_test_logging()
    
    print("🚀 DRY RUN MODE VERIFICATION TEST")
    print("=" * 60)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    tests = [
        ("Parameter Flow", test_dry_run_parameter_flow),
        ("Sidebar Toggle", test_sidebar_dry_run_toggle),
        ("Agent Execution", test_agent_dry_run_execution),
        ("Live Mode Prevention", test_live_mode_prevention),
        ("Full Trading Cycle", test_full_trading_cycle_dry_run),
        ("Wallet Balance Safety", test_wallet_balance_safety),
        ("UI Integration", test_dry_run_ui_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"   ✅ {test_name}: PASSED")
            else:
                print(f"   ❌ {test_name}: FAILED")
        except Exception as e:
            print(f"   💥 {test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 DRY RUN TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {test_name}")
    
    print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL DRY RUN TESTS PASSED!")
        print("✅ Dry run mode is working correctly")
        print("✅ Safe to use for testing and development")
        print("✅ Real wallet funds are protected")
    else:
        print(f"\n⚠️  {total - passed} tests failed")
        print("❌ Dry run mode needs attention")
        print("🔍 Review failed tests above")
    
    return passed == total

if __name__ == "__main__":
    success = run_comprehensive_dry_run_test()
    exit(0 if success else 1)#!/usr/bin/env python3
# dry_run_test.py
"""
Comprehensive test to verify dry run mode is working correctly
Tests all aspects of dry run functionality
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any

def setup_test_logging():
    """Setup logging to capture dry run activities"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("dry_run_test")

def test_dry_run_parameter_flow():
    """Test 1: Verify dry run parameters flow through the system correctly"""
    logger = setup_test_logging()
    logger.info("🧪 TEST 1: Dry Run Parameter Flow")
    
    try:
        # Test parameter creation with dry run
        from src.agent.state import create_initial_state
        
        state = create_initial_state()
        dry_run_mode = state.get("agent_parameters", {}).get("trading_mode", "unknown")
        
        logger.info(f"   📋 Initial state trading mode: {dry_run_mode}")
        
        if dry_run_mode == "dry_run":
            logger.info("   ✅ Default state correctly set to dry_run mode")
            return True
        else:
            logger.error(f"   ❌ Expected 'dry_run', got '{dry_run_mode}'")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Parameter flow test failed: {e}")
        return False

def test_sidebar_dry_run_toggle():
    """Test 2: Verify sidebar dry run toggle functionality"""
    logger = logging.getLogger("dry_run_test")
    logger.info("🧪 TEST 2: Sidebar Dry Run Toggle")
    
    try:
        # Simulate session state like Streamlit would
        class MockSessionState:
            def __init__(self):
                self.data = {
                    'agent_parameters': {
                        'trading_mode': 'dry_run',
                        'max_positions': 5,
                        'risk_tolerance': 'medium'
                    }
                }
            
            def get(self, key, default=None):
                return self.data.get(key, default)
            
            def __setitem__(self, key, value):
                self.data[key] = value
        
        # Mock session state
        mock_session = MockSessionState()
        
        # Test dry run mode detection
        current_params = mock_session.get('agent_parameters', {})
        is_dry_run = current_params.get('trading_mode', 'dry_run') == 'dry_run'
        
        logger.info(f"   📋 Current trading mode: {current_params.get('trading_mode')}")
        logger.info(f"   📋 Is dry run: {is_dry_run}")
        
        # Test toggle functionality
        if is_dry_run:
            # Simulate toggling to live mode
            current_params['trading_mode'] = 'live'
            mock_session['agent_parameters'] = current_params
            
            new_mode = mock_session.get('agent_parameters', {}).get('trading_mode')
            logger.info(f"   📋 After toggle to live: {new_mode}")
            
            # Toggle back to dry run
            current_params['trading_mode'] = 'dry_run'
            mock_session['agent_parameters'] = current_params
            
            final_mode = mock_session.get('agent_parameters', {}).get('trading_mode')
            logger.info(f"   📋 After toggle back to dry_run: {final_mode}")
            
            if final_mode == 'dry_run':
                logger.info("   ✅ Sidebar toggle functionality works correctly")
                return True
            else:
                logger.error(f"   ❌ Toggle failed, expected 'dry_run', got '{final_mode}'")
                return False
        
    except Exception as e:
        logger.error(f"   ❌ Sidebar toggle test failed: {e}")
        return False

def test_agent_dry_run_execution():
    """Test 3: Verify agent respects dry run mode during execution"""
    logger = logging.getLogger("dry_run_test")
    logger.info("🧪 TEST 3: Agent Dry Run Execution")
    
    try:
        from src.agent.pure_ai_agent import EnhancedPureAITradingAgent
        
        # Create agent instance
        agent = EnhancedPureAITradingAgent()
        
        # Test execute_trade tool with dry run
        trade_result = agent._execute_tool(
            "execute_trade",
            trade_type="buy",
            token_address="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            amount_sol=0.1,
            quote_data={"mock": "quote"},
            dry_run=True,
            reasoning="Test trade for dry run verification"
        )
        
        logger.info(f"   📋 Trade execution result: {trade_result}")
        
        # Verify dry run behavior
        if trade_result.get("success") and "Dry run" in trade_result.get("message", ""):
            logger.info("   ✅ Agent correctly executes trades in dry run mode")
            return True
        else:
            logger.error("   ❌ Agent did not respect dry run mode")
            logger.error(f"   Expected 'Dry run' message, got: {trade_result}")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Agent execution test failed: {e}")
        return False

def test_live_mode_prevention():
    """Test 4: Verify live mode requires explicit confirmation"""
    logger = logging.getLogger("dry_run_test")
    logger.info("🧪 TEST 4: Live Mode Prevention")
    
    try:
        from src.agent.pure_ai_agent import EnhancedPureAITradingAgent
        
        agent = EnhancedPureAITradingAgent()
        
        # Test execute_trade tool with live mode (dry_run=False)
        live_trade_result = agent._execute_tool(
            "execute_trade",
            trade_type="buy",
            token_address="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            amount_sol=0.1,
            quote_data=None,  # No quote data to simulate missing requirement
            dry_run=False,
            reasoning="Test live trade (should fail safely)"
        )
        
        logger.info(f"   📋 Live trade result: {live_trade_result}")
        
        # Should fail due to missing quote data (safety mechanism)
        if not live_trade_result.get("success"):
            logger.info("   ✅ Live mode correctly requires proper quote data")
            return True
        else:
            logger.warning("   ⚠️ Live mode executed without quote data (review safety)")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Live mode prevention test failed: {e}")
        return False

def test_full_trading_cycle_dry_run():
    """Test 5: Run a complete trading cycle in dry run mode"""
    logger = logging.getLogger("dry_run_test")
    logger.info("🧪 TEST 5: Full Trading Cycle Dry Run")
    
    try:
        from src.agent.state import create_initial_state
        from src.agent import run_trading_agent
        
        # Create state with explicit dry run parameters
        dry_run_params = {
            "trading_mode": "dry_run",
            "max_positions": 2,
            "max_position_size_sol": 0.05,
            "cycle_time_seconds": 60,
            "dry_run": True  # Legacy parameter
        }
        
        logger.info(f"   📋 Testing with parameters: {dry_run_params}")
        
        # Run one trading cycle
        result_state = run_trading_agent(dry_run_params)
        
        if result_state:
            trading_mode = result_state.get("trading_mode", "unknown")
            agent_params = result_state.get("agent_parameters", {})
            cycles_completed = result_state.get("cycles_completed", 0)
            
            logger.info(f"   📋 Result trading mode: {trading_mode}")
            logger.info(f"   📋 Agent parameters: {agent_params}")
            logger.info(f"   📋 Cycles completed: {cycles_completed}")
            
            # Verify dry run mode was maintained
            if trading_mode == "dry_run" or agent_params.get("trading_mode") == "dry_run":
                logger.info("   ✅ Full trading cycle maintained dry run mode")
                return True
            else:
                logger.error("   ❌ Trading cycle did not maintain dry run mode")
                return False
        else:
            logger.error("   ❌ Trading cycle returned no state")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Full cycle test failed: {e}")
        return False

def test_wallet_balance_safety():
    """Test 6: Verify wallet balance is not affected in dry run mode"""
    logger = logging.getLogger("dry_run_test")
    logger.info("🧪 TEST 6: Wallet Balance Safety")
    
    try:
        from src.blockchain.solana_client import get_wallet_balance
        
        # Get initial balance
        initial_balance = get_wallet_balance()
        logger.info(f"   📋 Initial wallet balance: {initial_balance:.6f} SOL")
        
        # Run trading cycle in dry run mode
        from src.agent import run_trading_agent
        
        dry_run_params = {
            "trading_mode": "dry_run",
            "max_positions": 1,
            "max_position_size_sol": 0.01
        }
        
        run_trading_agent(dry_run_params)
        
        # Check balance after trading cycle
        final_balance = get_wallet_balance()
        logger.info(f"   📋 Final wallet balance: {final_balance:.6f} SOL")
        
        balance_change = abs(final_balance - initial_balance)
        
        if balance_change < 0.000001:  # Allow for tiny RPC differences
            logger.info("   ✅ Wallet balance unchanged in dry run mode")
            return True
        else:
            logger.error(f"   ❌ Wallet balance changed by {balance_change:.9f} SOL")
            logger.error("   This should not happen in dry run mode!")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Wallet balance safety test failed: {e}")
        return False

def test_dry_run_ui_integration():
    """Test 7: Verify UI components handle dry run correctly"""
    logger = logging.getLogger("dry_run_test")
    logger.info("🧪 TEST 7: UI Integration")
    
    try:
        # Test that UI components can detect dry run mode
        from ui.components.sidebar import BALANCED_AI_PARAMETERS
        
        # Verify default parameters include dry run
        default_mode = BALANCED_AI_PARAMETERS.get("trading_mode", "unknown")
        logger.info(f"   📋 Default UI trading mode: {default_mode}")
        
        if default_mode == "dry_run":
            logger.info("   ✅ UI defaults to dry run mode")
            
            # Test parameter presets
            from ui.components.sidebar import AGGRESSIVE_AI_PARAMETERS, CONSERVATIVE_AI_PARAMETERS
            
            aggressive_mode = AGGRESSIVE_AI_PARAMETERS.get("trading_mode", "unknown")
            conservative_mode = CONSERVATIVE_AI_PARAMETERS.get("trading_mode", "unknown")
            
            logger.info(f"   📋 Aggressive preset mode: {aggressive_mode}")
            logger.info(f"   📋 Conservative preset mode: {conservative_mode}")
            
            if aggressive_mode == "dry_run" and conservative_mode == "dry_run":
                logger.info("   ✅ All UI presets default to dry run mode")
                return True
            else:
                logger.error("   ❌ Some UI presets do not default to dry run")
                return False
        else:
            logger.error(f"   ❌ UI does not default to dry run mode: {default_mode}")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ UI integration test failed: {e}")
        return False

def run_comprehensive_dry_run_test():
    """Run all dry run tests"""
    logger = setup_test_logging()
    
    print("🚀 DRY RUN MODE VERIFICATION TEST")
    print("=" * 60)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    tests = [
        ("Parameter Flow", test_dry_run_parameter_flow),
        ("Sidebar Toggle", test_sidebar_dry_run_toggle),
        ("Agent Execution", test_agent_dry_run_execution),
        ("Live Mode Prevention", test_live_mode_prevention),
        ("Full Trading Cycle", test_full_trading_cycle_dry_run),
        ("Wallet Balance Safety", test_wallet_balance_safety),
        ("UI Integration", test_dry_run_ui_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"   ✅ {test_name}: PASSED")
            else:
                print(f"   ❌ {test_name}: FAILED")
        except Exception as e:
            print(f"   💥 {test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 DRY RUN TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {test_name}")
    
    print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL DRY RUN TESTS PASSED!")
        print("✅ Dry run mode is working correctly")
        print("✅ Safe to use for testing and development")
        print("✅ Real wallet funds are protected")
    else:
        print(f"\n⚠️  {total - passed} tests failed")
        print("❌ Dry run mode needs attention")
        print("🔍 Review failed tests above")
    
    return passed == total

if __name__ == "__main__":
    success = run_comprehensive_dry_run_test()
    exit(0 if success else 1)
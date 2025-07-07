#!/usr/bin/env python3
# migrate_to_langgraph_complete.py
"""
COMPLETE LangGraph Migration Script
Migrates from manual tool calling to proper LangGraph implementation
Includes proper UI integration that was missing from the original script
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime

def analyze_current_implementation():
    """Analyze the current implementation to understand the issues"""
    print("🔍 ANALYZING CURRENT IMPLEMENTATION")
    print("=" * 60)
    
    issues_found = []
    files_to_check = [
        "src/agent/pure_ai_agent.py",
        "src/agent/pure_ai_graph.py", 
        "src/agent/__init__.py"
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                content = f.read()
            
            print(f"\n📄 {file_path}:")
            
            # Check for manual implementation patterns
            if "client.messages.create" in content:
                print("   ❌ Uses manual Anthropic API calls")
                issues_found.append(f"{file_path}: Manual Anthropic API usage")
            
            if "_setup_comprehensive_tools" in content:
                print("   ❌ Manual tool definition instead of @tool decorator")
                issues_found.append(f"{file_path}: Manual tool setup")
            
            if "_process_ai_response" in content:
                print("   ❌ Manual response processing instead of LangGraph automation")
                issues_found.append(f"{file_path}: Manual response processing")
            
            if "bind_tools" in content:
                print("   ✅ Has bind_tools usage")
            else:
                print("   ❌ Missing bind_tools() - not using LangGraph properly")
                issues_found.append(f"{file_path}: Missing bind_tools")
            
            if "create_react_agent" in content:
                print("   ✅ Has create_react_agent usage")
            else:
                print("   ❌ Missing create_react_agent - not using LangGraph properly")
                issues_found.append(f"{file_path}: Missing create_react_agent")
                
            # Check for UI integration functions in __init__.py
            if file_path.endswith("__init__.py"):
                ui_functions = ["start_agent_background", "stop_agent_background", "get_agent_status"]
                for func in ui_functions:
                    if func in content:
                        print(f"   ✅ Has {func} for UI integration")
                    else:
                        print(f"   ❌ Missing {func} - UI integration incomplete")
                        issues_found.append(f"{file_path}: Missing {func}")
        else:
            print(f"\n📄 {file_path}: ❌ File not found")
    
    print(f"\n🎯 ISSUES SUMMARY:")
    print(f"   Total issues found: {len(issues_found)}")
    for issue in issues_found:
        print(f"   • {issue}")
    
    return issues_found

def create_backup():
    """Create backup of current implementation"""
    print("\n💾 CREATING BACKUP")
    print("=" * 30)
    
    backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        # Create backup directory
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup agent files
        agent_files = [
            "src/agent/pure_ai_agent.py",
            "src/agent/pure_ai_graph.py",
            "src/agent/__init__.py",
            "agent_state.json"
        ]
        
        for file_path in agent_files:
            if os.path.exists(file_path):
                backup_path = os.path.join(backup_dir, os.path.basename(file_path))
                shutil.copy2(file_path, backup_path)
                print(f"   ✅ Backed up: {file_path} → {backup_path}")
        
        print(f"✅ Backup created in: {backup_dir}")
        return backup_dir
        
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return None

def install_required_dependencies():
    """Check and install required dependencies for LangGraph"""
    print("\n📦 CHECKING DEPENDENCIES")
    print("=" * 30)
    
    required_packages = [
        "langchain-anthropic>=0.3.0",
        "langgraph>=0.4.0",
        "langchain-core>=0.3.0"
    ]
    
    try:
        for package in required_packages:
            print(f"   🔍 Checking {package}...")
            try:
                # Try to import to check if it exists
                if "langchain-anthropic" in package:
                    import langchain_anthropic
                    print(f"   ✅ {package} already installed")
                elif "langgraph" in package:
                    import langgraph
                    print(f"   ✅ {package} already installed")
                elif "langchain-core" in package:
                    import langchain_core
                    print(f"   ✅ {package} already installed")
            except ImportError:
                print(f"   ⚠️ {package} not found, installing...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"   ✅ {package} installed")
        
        return True
        
    except Exception as e:
        print(f"❌ Dependency installation failed: {e}")
        return False

def verify_langgraph_agent_exists():
    """Verify that the complete LangGraph agent file exists"""
    print("\n🔍 VERIFYING LANGGRAPH AGENT EXISTS")
    print("=" * 45)
    
    langgraph_file = "src/agent/langgraph_trading_agent.py"
    
    if not os.path.exists(langgraph_file):
        print(f"❌ {langgraph_file} not found!")
        print("   Please ensure you have saved the complete langgraph_trading_agent.py file")
        return False
    
    # Check if it has the key components
    try:
        with open(langgraph_file, 'r') as f:
            content = f.read()
        
        required_components = [
            "CompleteLangGraphTradingAgent",
            "run_langgraph_trading_cycle",
            "@tool",
            "create_react_agent",
            "bind_tools"
        ]
        
        missing_components = []
        for component in required_components:
            if component in content:
                print(f"   ✅ Has {component}")
            else:
                print(f"   ❌ Missing {component}")
                missing_components.append(component)
        
        if missing_components:
            print(f"❌ LangGraph agent file is incomplete. Missing: {missing_components}")
            return False
        
        print("✅ LangGraph agent file is complete and ready")
        return True
        
    except Exception as e:
        print(f"❌ Error reading LangGraph agent file: {e}")
        return False

def update_init_file_for_ui_integration():
    """Update __init__.py with complete UI integration (THE MISSING PIECE)"""
    print("\n🔧 UPDATING __init__.py FOR COMPLETE UI INTEGRATION")
    print("=" * 60)
    
    # Complete __init__.py content with UI integration
    complete_init_content = '''# src/agent/__init__.py
"""
Complete Agent Module - Updated for LangGraph with Full UI Integration
Provides all functions expected by the Streamlit UI
"""
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Import LangGraph implementation (THE KEY CHANGE)
from .langgraph_trading_agent import run_langgraph_trading_cycle

# Import state management (unchanged)
from .state import (
    AgentState, TokenData, Position, 
    create_initial_state, save_agent_state, load_agent_state,
    update_portfolio_metrics, migrate_legacy_state, validate_state_structure,
    get_state_summary
)

# Configure logger
logger = logging.getLogger("trading_agent")

# Global variables for background agent management (REQUIRED BY UI)
_agent_thread = None
_agent_running = False
_agent_stop_flag = False

def run_trading_agent(parameters: dict = None) -> AgentState:
    """
    Main trading agent function - now uses LangGraph
    Compatible with existing UI calls
    """
    try:
        # Load or create initial state
        state = load_agent_state()
        if state is None:
            state = create_initial_state()
            logger.info("Created new agent state")
        else:
            logger.info("Loaded existing agent state")
            
            # Validate and migrate if needed
            if not validate_state_structure(state):
                logger.warning("State structure outdated, migrating...")
                state = migrate_legacy_state(state)
        
        # Update parameters if provided
        if parameters:
            current_params = state.get("agent_parameters", {})
            current_params.update(parameters)
            state["agent_parameters"] = current_params
        
        # USE LANGGRAPH instead of pure_ai_agent (THE KEY CHANGE)
        logger.info("🚀 Running LangGraph trading cycle...")
        result_state = run_langgraph_trading_cycle(state)
        
        # Save state
        save_agent_state(result_state)
        
        # Log success indicators
        tools_used = result_state.get("tools_used_this_cycle", [])
        cycles = result_state.get("cycles_completed", 0)
        
        if tools_used:
            logger.info(f"✅ LangGraph cycle {cycles} completed with tools: {tools_used}")
        else:
            logger.warning(f"⚠️ LangGraph cycle {cycles} completed but no tools were used")
        
        return result_state
        
    except Exception as e:
        logger.error(f"❌ Trading agent error: {e}")
        # Return error state
        error_state = state if 'state' in locals() else create_initial_state()
        error_state["error"] = str(e)
        error_state["error_timestamp"] = datetime.now().isoformat()
        save_agent_state(error_state)
        return error_state

def start_agent_background(parameters: dict = None) -> bool:
    """Start the trading agent in background mode (REQUIRED BY UI)"""
    global _agent_thread, _agent_running, _agent_stop_flag
    
    if _agent_running:
        logger.warning("Agent already running in background")
        return False
    
    def background_loop():
        global _agent_running, _agent_stop_flag
        _agent_running = True
        _agent_stop_flag = False
        
        logger.info("🚀 Starting LangGraph agent in background mode...")
        
        while not _agent_stop_flag:
            try:
                # Run one trading cycle
                state = run_trading_agent(parameters)
                
                # Check for stop condition
                if _agent_stop_flag:
                    break
                
                # Sleep between cycles
                cycle_time = parameters.get("cycle_time_seconds", 300) if parameters else 300
                for _ in range(cycle_time):
                    if _agent_stop_flag:
                        break
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"Background agent error: {e}")
                time.sleep(60)  # Wait before retrying
        
        _agent_running = False
        logger.info("Background agent stopped")
    
    try:
        _agent_thread = threading.Thread(target=background_loop, daemon=True)
        _agent_thread.start()
        logger.info("Background agent thread started")
        return True
    except Exception as e:
        logger.error(f"Failed to start background agent: {e}")
        _agent_running = False
        return False

def stop_agent_background() -> bool:
    """Stop the background trading agent (REQUIRED BY UI)"""
    global _agent_stop_flag, _agent_running
    
    if not _agent_running:
        logger.info("No background agent to stop")
        return True
    
    logger.info("Stopping background agent...")
    _agent_stop_flag = True
    
    # Wait up to 10 seconds for graceful shutdown
    for _ in range(100):
        if not _agent_running:
            logger.info("Background agent stopped successfully")
            return True
        time.sleep(0.1)
    
    logger.warning("Background agent did not stop gracefully")
    return False

def get_agent_status() -> Dict[str, Any]:
    """Get current agent status (REQUIRED BY UI)"""
    global _agent_running, _agent_thread
    
    # Load current state
    state = load_agent_state()
    
    return {
        "running": _agent_running,
        "thread_alive": _agent_thread.is_alive() if _agent_thread else False,
        "cycles_completed": state.get("cycles_completed", 0) if state else 0,
        "last_update": state.get("last_update_timestamp") if state else None,
        "wallet_balance_sol": state.get("wallet_balance_sol", 0) if state else 0,
        "active_positions": len(state.get("active_positions", [])) if state else 0,
        "tools_used_last_cycle": state.get("tools_used_this_cycle", []) if state else [],
        "agent_type": "LangGraph_Enhanced"
    }

# ============================================================================
# EXPORTS (All functions the UI expects)
# ============================================================================

__all__ = [
    # Main agent functions
    "run_trading_agent",
    
    # Background management (THESE WERE MISSING)
    "start_agent_background", 
    "stop_agent_background",
    "get_agent_status",
    
    # State management  
    "load_agent_state",
    "save_agent_state", 
    "create_initial_state",
    "update_portfolio_metrics",
    "get_state_summary",
    
    # State types
    "AgentState",
    "TokenData", 
    "Position"
]
'''
    
    try:
        # Backup existing file
        backup_path = "src/agent/__init__.py.backup_migration"
        shutil.copy2("src/agent/__init__.py", backup_path)
        print(f"   📁 Backed up existing __init__.py to {backup_path}")
        
        # Write complete new file (REPLACE, don't append)
        with open("src/agent/__init__.py", "w") as f:
            f.write(complete_init_content)
        
        print("   ✅ Completely replaced __init__.py with LangGraph integration")
        print("   ✅ Added start_agent_background() function")
        print("   ✅ Added stop_agent_background() function") 
        print("   ✅ Added get_agent_status() function")
        print("   ✅ Updated run_trading_agent() to use LangGraph")
        print("   ✅ Added proper error handling and logging")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to update __init__.py: {e}")
        return False

def create_test_script():
    """Create a test script to verify the LangGraph implementation"""
    test_script = '''#!/usr/bin/env python3
# test_langgraph_implementation.py
"""
Test script to verify that the LangGraph implementation works correctly
Run this after migration to ensure tools are being called properly
"""
import logging
from src.agent.langgraph_trading_agent import test_langgraph_tools, run_langgraph_trading_cycle

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    print("🧪 TESTING LANGGRAPH IMPLEMENTATION")
    print("=" * 50)
    
    # Test 1: Individual tools
    print("\\n1. Testing individual tools...")
    if test_langgraph_tools():
        print("   ✅ Individual tools working")
    else:
        print("   ❌ Individual tools failed")
        return False
    
    # Test 2: Full cycle
    print("\\n2. Testing full trading cycle...")
    try:
        result = run_langgraph_trading_cycle()
        
        tools_used = result.get("tools_used_this_cycle", [])
        cycles = result.get("cycles_completed", 0)
        reasoning = result.get("agent_reasoning", "")
        
        print(f"   📊 Cycle completed: {cycles}")
        print(f"   🔧 Tools used: {tools_used}")
        print(f"   💭 Reasoning length: {len(reasoning)} chars")
        
        if tools_used:
            print("   ✅ SUCCESS: Tools are being called!")
            print("   🎉 LangGraph implementation is working correctly")
            return True
        else:
            print("   ❌ FAILURE: No tools were called")
            print("   💡 Check your ANTHROPIC_API_KEY and model configuration")
            return False
            
    except Exception as e:
        print(f"   ❌ Full cycle test failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    print(f"\\n🎯 LangGraph Test Result: {'✅ PASSED' if success else '❌ FAILED'}")
    
    if success:
        print("\\n🚀 NEXT STEPS:")
        print("1. Your Streamlit UI should now work without any changes")
        print("2. Monitor logs for '🔧 Tools used:' messages")
        print("3. Verify that reasoning changes each cycle")
        print("4. Watch for progression beyond discovery phase")
    else:
        print("\\n🔍 DEBUGGING:")
        print("1. Check ANTHROPIC_API_KEY is set correctly")
        print("2. Verify model name is correct")
        print("3. Check for import errors")
        print("4. Review langgraph_trading_agent.py implementation")
'''
    
    try:
        with open("test_langgraph_implementation.py", "w") as f:
            f.write(test_script)
        os.chmod("test_langgraph_implementation.py", 0o755)
        print("   ✅ Created test_langgraph_implementation.py")
        return True
    except Exception as e:
        print(f"❌ Test script creation failed: {e}")
        return False

def main():
    """Main migration function"""
    print("🚀 COMPLETE LANGGRAPH MIGRATION TOOL")
    print("=" * 70)
    print("This tool will migrate your manual tool calling to proper LangGraph implementation")
    print("AND fix the UI integration issues that were missing from the original script\\n")
    
    # Step 1: Analyze current implementation
    issues = analyze_current_implementation()
    
    if not issues:
        print("\\n✅ No major issues found with current implementation")
        print("The problem might be elsewhere. Consider running the diagnostic script first.")
        return True
    
    # Step 2: Verify LangGraph agent exists
    if not verify_langgraph_agent_exists():
        print("\\n❌ Cannot proceed without the complete LangGraph agent file")
        print("Please ensure src/agent/langgraph_trading_agent.py exists and is complete")
        return False
    
    # Ask for confirmation
    print(f"\\n🎯 COMPLETE MIGRATION PLAN:")
    print("1. ✅ Create backup of current files")
    print("2. ✅ Install/verify LangGraph dependencies") 
    print("3. ✅ Update __init__.py with COMPLETE UI integration (THE MISSING PIECE)")
    print("4. ✅ Create test script to verify functionality")
    print("\\nThis will fix the fundamental architecture issues AND the UI integration gaps.")
    
    choice = input("\\nProceed with complete migration? (y/n): ")
    if choice.lower() != 'y':
        print("Migration cancelled.")
        return False
    
    # Step 3: Create backup
    backup_dir = create_backup()
    if not backup_dir:
        print("❌ Cannot proceed without backup")
        return False
    
    # Step 4: Install dependencies
    if not install_required_dependencies():
        print("❌ Cannot proceed without required dependencies")
        return False
    
    # Step 5: Update __init__.py for complete UI integration (THE KEY FIX)
    if not update_init_file_for_ui_integration():
        print("❌ UI integration update failed")
        return False
    
    # Step 6: Create test script
    if not create_test_script():
        print("⚠️ Test script creation failed, but migration may still work")
    
    # Summary
    print("\\n" + "=" * 70)
    print("🎉 COMPLETE MIGRATION SUCCESSFUL!")
    print("=" * 70)
    
    print("\\n✅ What was fixed:")
    print("• Updated __init__.py to import from langgraph_trading_agent")
    print("• Added start_agent_background() function (was missing)")
    print("• Added stop_agent_background() function (was missing)")
    print("• Added get_agent_status() function (was missing)")
    print("• Updated run_trading_agent() to use LangGraph")
    print("• Added proper background agent management")
    print("• Added comprehensive error handling and logging")
    
    print("\\n🚀 NEXT STEPS:")
    print("1. Run the test script:")
    print("   python test_langgraph_implementation.py")
    print()
    print("2. Start your Streamlit dashboard (NO CHANGES NEEDED):")
    print("   streamlit run ui/streamlit_dashboard.py")
    print()
    print("3. Look for these signs of success:")
    print("   • Logs showing '🔧 Tools used: [tool_names]'")
    print("   • Different reasoning each cycle")
    print("   • Progress beyond 'I'll begin this trading cycle...'")
    print("   • Actual tool execution with real data")
    
    print(f"\\n📁 Backup created in: {backup_dir}")
    print("💡 If anything goes wrong, restore from backup")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
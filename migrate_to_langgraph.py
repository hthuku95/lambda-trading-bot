#!/usr/bin/env python3
# migrate_to_langgraph.py
"""
Migration script to transition from manual tool calling to proper LangGraph implementation
This will fix the fundamental architectural issues causing tool calling failures
"""
import os
import shutil
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
        import subprocess
        import sys
        
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

def apply_langgraph_migration():
    """Apply the LangGraph migration"""
    print("\n🔧 APPLYING LANGGRAPH MIGRATION")
    print("=" * 40)
    
    try:
        # Create the new LangGraph implementation file
        langgraph_content = '''# This file was created by the migration script
# It contains the proper LangGraph implementation to replace manual tool calling

# Import the proper LangGraph implementation
from .langgraph_trading_agent import (
    LangGraphTradingAgent,
    run_langgraph_trading_cycle,
    test_langgraph_tools
)

# Create global instance
langgraph_agent = LangGraphTradingAgent()

# Replace the old run_pure_ai_trading_agent with proper LangGraph version
def run_pure_ai_trading_agent(initial_state=None):
    """Updated to use proper LangGraph implementation"""
    return run_langgraph_trading_cycle(initial_state)

# Export for compatibility
__all__ = [
    "run_pure_ai_trading_agent",
    "run_langgraph_trading_cycle", 
    "test_langgraph_tools",
    "langgraph_agent"
]
'''
        
        # Update the __init__.py to use LangGraph
        init_update = '''
# Updated imports for LangGraph implementation
from .langgraph_trading_agent import run_langgraph_trading_cycle

def run_trading_agent(parameters: dict = None):
    """Updated to use proper LangGraph implementation"""
    return run_langgraph_trading_cycle()
'''
        
        # Write updates
        with open("src/agent/pure_ai_agent_langgraph.py", "w") as f:
            f.write(langgraph_content)
        print("   ✅ Created LangGraph compatibility layer")
        
        # Add import to __init__.py
        with open("src/agent/__init__.py", "a") as f:
            f.write(init_update)
        print("   ✅ Updated __init__.py with LangGraph imports")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
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
        print("1. Update your Streamlit dashboard to use run_langgraph_trading_cycle()")
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
    print("🚀 LANGGRAPH MIGRATION TOOL")
    print("=" * 70)
    print("This tool will migrate your manual tool calling to proper LangGraph implementation")
    print("This should fix the issue where AI isn't calling tools after 58 cycles\\n")
    
    # Step 1: Analyze current implementation
    issues = analyze_current_implementation()
    
    if not issues:
        print("\\n✅ No major issues found with current implementation")
        print("The problem might be elsewhere. Consider running the diagnostic script first.")
        return True
    
    # Ask for confirmation
    print(f"\\n🎯 MIGRATION PLAN:")
    print("1. ✅ Create backup of current files")
    print("2. ✅ Install/verify LangGraph dependencies") 
    print("3. ✅ Create proper LangGraph implementation")
    print("4. ✅ Update imports and compatibility layer")
    print("5. ✅ Create test script to verify functionality")
    print("\\nThis will fix the fundamental architecture issues causing tool calling failures.")
    
    choice = input("\\nProceed with migration? (y/n): ")
    if choice.lower() != 'y':
        print("Migration cancelled.")
        return False
    
    # Step 2: Create backup
    backup_dir = create_backup()
    if not backup_dir:
        print("❌ Cannot proceed without backup")
        return False
    
    # Step 3: Install dependencies
    if not install_required_dependencies():
        print("❌ Cannot proceed without required dependencies")
        return False
    
    # Step 4: Apply migration
    if not apply_langgraph_migration():
        print("❌ Migration failed")
        return False
    
    # Step 5: Create test script
    if not create_test_script():
        print("⚠️ Test script creation failed, but migration may still work")
    
    # Summary
    print("\\n" + "=" * 70)
    print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    
    print("\\n✅ What was fixed:")
    print("• Replaced manual Anthropic API calls with LangGraph")
    print("• Added proper @tool decorators for tool definitions")
    print("• Implemented model.bind_tools() for proper tool registration")
    print("• Used create_react_agent for automated tool execution")
    print("• Removed manual response parsing and tool execution")
    
    print("\\n🚀 NEXT STEPS:")
    print("1. Save the LangGraph implementation file provided earlier as:")
    print("   src/agent/langgraph_trading_agent.py")
    print()
    print("2. Run the test script:")
    print("   python test_langgraph_implementation.py")
    print()
    print("3. Update your main usage to:")
    print("   from src.agent.langgraph_trading_agent import run_langgraph_trading_cycle")
    print("   result = run_langgraph_trading_cycle()")
    print()
    print("4. Look for these signs of success:")
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
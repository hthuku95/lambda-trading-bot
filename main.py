#!/usr/bin/env python3
# main_pure_ai.py - Pure AI Trading Bot Runner
"""
Pure AI Solana Trading Bot
No hardcoded rules - AI makes ALL decisions
"""
import os
import logging
import time
from datetime import datetime
from dotenv import load_dotenv

from src.agent.pure_ai_agent import run_pure_ai_trading_agent
from src.blockchain.solana_client import get_wallet_balance

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pure_ai_trading.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("pure_ai_trading")

def check_pure_ai_setup():
    """Check if pure AI setup is complete"""
    print("🤖 Checking Pure AI Setup...")
    
    # Check Anthropic API key
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        print("   ✅ Anthropic API Key configured")
    else:
        print("   ❌ Anthropic API Key missing")
        print("      Add ANTHROPIC_API_KEY to your .env file")
        return False
    
    # Check AstraDB configuration
    astra_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    astra_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
    
    if astra_token and astra_endpoint:
        print("   ✅ AstraDB configured")
        # Test connection
        try:
            from src.memory.astra_vector_store import astra_store
            if astra_store.initialize_collection():
                print("   ✅ AstraDB connection successful")
            else:
                print("   ⚠️  AstraDB connection failed - using fallback memory")
        except Exception as e:
            print(f"   ⚠️  AstraDB connection error: {e} - using fallback")
    else:
        print("   ⚠️  AstraDB not configured - using fallback memory")
        print("      Add ASTRA_DB_APPLICATION_TOKEN and ASTRA_DB_API_ENDPOINT to .env")
    
    # Check wallet
    try:
        balance = get_wallet_balance()
        print(f"   ✅ Wallet connected: {balance:.4f} SOL")
        if balance < 0.01:
            print("   ⚠️  Low wallet balance - consider adding more SOL")
    except Exception as e:
        print(f"   ❌ Wallet connection failed: {e}")
        return False
    
    return True

def run_continuous_trading():
    """Run continuous trading cycles"""
    print("🔄 Starting continuous trading mode...")
    print("   Press Ctrl+C to stop")
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            print(f"\n🚀 Starting Trading Cycle {cycle_count}")
            print("-" * 40)
            
            try:
                # Run the pure AI agent
                final_state = run_pure_ai_trading_agent()
                
                # Display results
                balance = final_state.get('wallet_balance_sol', 0)
                positions = final_state.get('active_positions', [])
                
                print(f"💰 Balance: {balance:.4f} SOL")
                print(f"📊 Positions: {len(positions)}")
                
                if positions:
                    for pos in positions:
                        symbol = pos.get('token_symbol', 'Unknown')
                        profit = pos.get('current_profit_percentage', 0)
                        print(f"   📈 {symbol}: {profit:+.1f}%")
                
                # Wait before next cycle (AI decides timing, but minimum 3 minutes)
                wait_time = 180  # 3 minutes minimum
                print(f"⏰ Waiting {wait_time}s until next cycle...")
                time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Trading cycle {cycle_count} error: {e}")
                print(f"❌ Cycle {cycle_count} error: {e}")
                print("⏰ Waiting 60s before retry...")
                time.sleep(60)
                
    except KeyboardInterrupt:
        print(f"\n⏹️  Trading stopped after {cycle_count} cycles")

def main():
    """Main function for pure AI trading bot"""
    print("🚀 Pure AI Solana Trading Bot")
    print("=" * 50)
    
    if not check_pure_ai_setup():
        print("❌ Setup incomplete. Please check your configuration.")
        return
    
    print("🧠 Pure AI Trading Agent Ready")
    print("   • No hardcoded rules")
    print("   • AI makes ALL decisions")
    print("   • Uses tools and memory")
    print("   • Learns from experience")
    print("")
    
    # Ask user for trading mode
    print("Select trading mode:")
    print("1. Single cycle (test)")
    print("2. Continuous trading")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        try:
            print("🧪 Running single test cycle...")
            final_state = run_pure_ai_trading_agent()
            
            print("✅ Test cycle completed")
            print(f"💰 Final Balance: {final_state.get('wallet_balance_sol', 0):.4f} SOL")
            print(f"📊 Active Positions: {len(final_state.get('active_positions', []))}")
            
        except Exception as e:
            logger.error(f"Test cycle error: {e}")
            print(f"❌ Test cycle error: {e}")
    
    elif choice == "2":
        run_continuous_trading()
    
    else:
        print("Invalid choice. Exiting.")

if __name__ == "__main__":
    main()
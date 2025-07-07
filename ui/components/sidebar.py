# ui/components/sidebar.py
"""
Updated Sidebar - Pure AI Agent Integration
Compatible with new architecture and enhanced features
"""
import streamlit as st
import threading
import time
import logging
from datetime import datetime

# Updated import for new agent architecture
from src.agent import (
    run_trading_agent, start_agent_background, stop_agent_background, 
    get_agent_status, load_agent_state, save_agent_state
)

# Configure logger
logger = logging.getLogger("trading_agent.ui")

# Predefined trading modes for Pure AI Agent
AGGRESSIVE_AI_PARAMETERS = {
    "trading_mode": "dry_run",
    "max_positions": 8,
    "max_position_size_sol": 0.3,
    "min_position_size_sol": 0.02,
    "cycle_time_seconds": 180,
    "risk_tolerance": "high",
    "ai_temperature": 0.1,
    "discovery_strategy": "comprehensive",
    "enable_learning": True,
    "enable_memory": True,
    "target_profit_threshold": 30,
    "stop_loss_threshold": -15,
    "max_hold_time_hours": 6
}

CONSERVATIVE_AI_PARAMETERS = {
    "trading_mode": "dry_run", 
    "max_positions": 3,
    "max_position_size_sol": 0.05,
    "min_position_size_sol": 0.01,
    "cycle_time_seconds": 600,
    "risk_tolerance": "low",
    "ai_temperature": 0.05,
    "discovery_strategy": "profiles_latest",
    "enable_learning": True,
    "enable_memory": True,
    "target_profit_threshold": 15,
    "stop_loss_threshold": -10,
    "max_hold_time_hours": 24
}

BALANCED_AI_PARAMETERS = {
    "trading_mode": "dry_run",
    "max_positions": 5,
    "max_position_size_sol": 0.1,
    "min_position_size_sol": 0.01,
    "cycle_time_seconds": 300,
    "risk_tolerance": "medium",
    "ai_temperature": 0.1,
    "discovery_strategy": "boosted_latest",
    "enable_learning": True,
    "enable_memory": True,
    "target_profit_threshold": 25,
    "stop_loss_threshold": -12,
    "max_hold_time_hours": 12
}

def render_trading_mode_selector():
    """Render the AI trading mode selection"""
    st.subheader("🧠 AI Trading Mode")
    
    # Get current mode from session state
    current_mode = st.session_state.get('ai_trading_mode', 'balanced')
    
    mode = st.radio(
        "Select AI Strategy:",
        ["balanced", "aggressive", "conservative", "custom"],
        index=["balanced", "aggressive", "conservative", "custom"].index(current_mode),
        format_func=lambda x: {
            "balanced": "🎯 Balanced AI (Recommended)",
            "aggressive": "🚀 Aggressive AI (High Risk/Reward)", 
            "conservative": "🛡️ Conservative AI (Safety First)",
            "custom": "⚙️ Custom Parameters"
        }[x]
    )
    
    # Update parameters based on mode selection
    if mode != current_mode:
        st.session_state.ai_trading_mode = mode
        
        if mode == "aggressive":
            st.session_state.agent_parameters = AGGRESSIVE_AI_PARAMETERS.copy()
        elif mode == "conservative": 
            st.session_state.agent_parameters = CONSERVATIVE_AI_PARAMETERS.copy()
        elif mode == "balanced":
            st.session_state.agent_parameters = BALANCED_AI_PARAMETERS.copy()
        # Custom mode keeps existing parameters
        
        st.rerun()

def render_trading_mode_toggle():
    """Render the dry run vs live trading toggle"""
    st.subheader("⚡ Execution Mode")
    
    current_params = st.session_state.get('agent_parameters', BALANCED_AI_PARAMETERS)
    is_dry_run = current_params.get('trading_mode', 'dry_run') == 'dry_run'
    
    # Create toggle for dry run mode
    dry_run = st.toggle("Safe Mode (Dry Run)", value=is_dry_run)
    
    # Update trading mode in parameters
    if dry_run != is_dry_run:
        current_params['trading_mode'] = 'dry_run' if dry_run else 'live'
        st.session_state.agent_parameters = current_params
    
    # Display current mode with clear warning/confirmation
    if dry_run:
        st.success("✅ **SAFE MODE ACTIVE**")
        st.info("🔒 All trades are simulated - No real money at risk")
        st.write("• AI will analyze and make decisions")
        st.write("• Trade execution is simulated only")
        st.write("• Perfect for testing and learning")
    else:
        st.error("⚠️ **LIVE TRADING MODE**")
        st.warning("🚨 Real money will be used for trades!")
        st.write("• AI will execute actual trades")
        st.write("• SOL will be spent on positions")
        st.write("• Profits and losses are real")
        
        # Additional confirmation for live mode
        if not st.session_state.get('live_mode_confirmed', False):
            confirm_live = st.checkbox("✅ I understand and accept the risks of live trading")
            st.session_state.live_mode_confirmed = confirm_live
            
            if not confirm_live:
                st.error("Please confirm understanding of live trading risks")
                # Force back to dry run if not confirmed
                current_params['trading_mode'] = 'dry_run'
                st.session_state.agent_parameters = current_params

def render_mode_description():
    """Render description for the current AI mode"""
    current_mode = st.session_state.get('ai_trading_mode', 'balanced')
    
    if current_mode == 'aggressive':
        st.info("""
        🚀 **Aggressive AI Mode**
        - 3-minute decision cycles
        - Up to 8 concurrent positions
        - 30% max position size
        - Targets high-momentum tokens
        - Goal: 100-500%+ daily gains
        - Higher risk tolerance
        """)
    elif current_mode == 'conservative':
        st.info("""
        🛡️ **Conservative AI Mode**
        - 10-minute decision cycles
        - Max 3 positions at once
        - 5% max position size
        - Focus on established tokens
        - Goal: 20-100% weekly gains
        - Prioritizes safety over speed
        """)
    elif current_mode == 'balanced':
        st.info("""
        🎯 **Balanced AI Mode** (Recommended)
        - 5-minute decision cycles
        - Up to 5 concurrent positions
        - 10% max position size
        - Mix of safety and opportunity
        - Goal: 50-200% weekly gains
        - Balanced risk/reward approach
        """)

def render_custom_parameters():
    """Render custom parameter controls for advanced users"""
    if st.session_state.get('ai_trading_mode') == 'custom':
        st.subheader("⚙️ Custom AI Parameters")
        
        current_params = st.session_state.get('agent_parameters', BALANCED_AI_PARAMETERS)
        
        # Core trading parameters
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Position Management:**")
            max_positions = st.number_input(
                "Max Concurrent Positions", 
                min_value=1, 
                max_value=10, 
                value=current_params.get('max_positions', 5),
                help="Maximum number of tokens to hold simultaneously"
            )
            
            min_position_size = st.number_input(
                "Min Position Size (SOL)", 
                min_value=0.001, 
                max_value=1.0, 
                value=current_params.get('min_position_size_sol', 0.01),
                step=0.001,
                format="%.3f",
                help="Minimum SOL amount per position"
            )
            
            max_position_size = st.number_input(
                "Max Position Size (SOL)", 
                min_value=0.01, 
                max_value=10.0, 
                value=current_params.get('max_position_size_sol', 0.1),
                step=0.01,
                format="%.2f",
                help="Maximum SOL amount per position"
            )
        
        with col2:
            st.write("**AI Behavior:**")
            cycle_time = st.number_input(
                "Decision Cycle Time (seconds)", 
                min_value=60, 
                max_value=3600, 
                value=current_params.get('cycle_time_seconds', 300),
                help="How often AI makes trading decisions"
            )
            
            risk_tolerance = st.selectbox(
                "Risk Tolerance", 
                ["low", "medium", "high"],
                index=["low", "medium", "high"].index(current_params.get('risk_tolerance', 'medium')),
                help="AI's appetite for risky trades"
            )
            
            ai_temperature = st.slider(
                "AI Creativity (Temperature)",
                min_value=0.01,
                max_value=0.5,
                value=current_params.get('ai_temperature', 0.1),
                step=0.01,
                help="Higher = more creative/varied decisions"
            )
        
        # Trading strategy parameters
        st.write("**Trading Strategy:**")
        strat_col1, strat_col2 = st.columns(2)
        
        with strat_col1:
            discovery_strategy = st.selectbox(
                "Token Discovery Strategy",
                ["comprehensive", "boosted_latest", "boosted_top", "profiles_latest"],
                index=["comprehensive", "boosted_latest", "boosted_top", "profiles_latest"].index(
                    current_params.get('discovery_strategy', 'comprehensive')
                ),
                help="How AI discovers new trading opportunities"
            )
            
            target_profit = st.number_input(
                "Target Profit (%)",
                min_value=5,
                max_value=100,
                value=current_params.get('target_profit_threshold', 25),
                help="Profit target for position exits"
            )
        
        with strat_col2:
            stop_loss = st.number_input(
                "Stop Loss (%)",
                min_value=-50,
                max_value=-1,
                value=current_params.get('stop_loss_threshold', -12),
                help="Maximum acceptable loss per position"
            )
            
            max_hold_time = st.number_input(
                "Max Hold Time (hours)",
                min_value=0.5,
                max_value=72.0,
                value=current_params.get('max_hold_time_hours', 12),
                step=0.5,
                help="Maximum time to hold any position"
            )
        
        # AI learning parameters
        st.write("**AI Learning:**")
        learning_col1, learning_col2 = st.columns(2)
        
        with learning_col1:
            enable_learning = st.checkbox(
                "Enable AI Learning",
                value=current_params.get('enable_learning', True),
                help="Allow AI to learn from trading experiences"
            )
        
        with learning_col2:
            enable_memory = st.checkbox(
                "Enable Memory Search",
                value=current_params.get('enable_memory', True),
                help="Allow AI to search historical trading patterns"
            )
        
        # Update parameters
        current_params.update({
            'max_positions': max_positions,
            'min_position_size_sol': min_position_size,
            'max_position_size_sol': max_position_size,
            'cycle_time_seconds': cycle_time,
            'risk_tolerance': risk_tolerance,
            'ai_temperature': ai_temperature,
            'discovery_strategy': discovery_strategy,
            'target_profit_threshold': target_profit,
            'stop_loss_threshold': stop_loss,
            'max_hold_time_hours': max_hold_time,
            'enable_learning': enable_learning,
            'enable_memory': enable_memory
        })
        
        st.session_state.agent_parameters = current_params

def render_agent_controls():
    """Render AI agent start/stop controls with enhanced status"""
    st.subheader("🤖 AI Agent Control")
    
    # Get current agent status
    agent_status = get_agent_status()
    is_running = st.session_state.get('agent_running', False)
    
    # Display current status
    if is_running:
        st.success("🟢 **AI Agent is ACTIVE**")
        st.write(f"• Status: {agent_status.get('status', 'unknown').title()}")
        if 'summary' in agent_status:
            summary = agent_status['summary']
            st.write(f"• Cycles Completed: {summary.get('cycles_completed', 0)}")
            st.write(f"• Portfolio Value: {summary.get('total_portfolio_value', 0):.4f} SOL")
            st.write(f"• Active Positions: {summary.get('active_positions_count', 0)}")
            st.write(f"• Current Strategy: {summary.get('ai_strategy', 'Unknown')}")
    else:
        st.error("🔴 **AI Agent is STOPPED**")
        st.write("• Ready to start trading")
        st.write("• No active trading cycles")
    
    # Control buttons
    control_col1, control_col2, control_col3 = st.columns(3)
    
    with control_col1:
        if st.button("🚀 Start AI Agent", type="primary", disabled=is_running):
            if not is_running:
                try:
                    # Get current parameters
                    parameters = st.session_state.get('agent_parameters', BALANCED_AI_PARAMETERS)
                    
                    # Start background agent
                    success = start_agent_background(parameters)
                    
                    if success:
                        st.session_state.agent_running = True
                        st.success("🚀 AI Agent started successfully!")
                        logger.info(f"AI Agent started with parameters: {parameters}")
                    else:
                        st.error("❌ Failed to start AI Agent")
                        logger.error("Failed to start AI Agent")
                        
                except Exception as e:
                    st.error(f"❌ Error starting agent: {str(e)}")
                    logger.error(f"Error starting agent: {e}")
                
                st.rerun()
    
    with control_col2:
        if st.button("🛑 Stop AI Agent", disabled=not is_running):
            if is_running:
                try:
                    stop_agent_background()
                    st.session_state.agent_running = False
                    st.warning("🛑 AI Agent stopped")
                    logger.info("AI Agent stopped by user")
                except Exception as e:
                    st.error(f"❌ Error stopping agent: {str(e)}")
                    logger.error(f"Error stopping agent: {e}")
                
                st.rerun()
    
    with control_col3:
        if st.button("🔄 Run Single Cycle", disabled=is_running):
            try:
                with st.spinner("🧠 AI is analyzing and making decisions..."):
                    parameters = st.session_state.get('agent_parameters', BALANCED_AI_PARAMETERS)
                    result_state = run_trading_agent(parameters)
                    
                    if result_state:
                        st.success("✅ Single cycle completed!")
                        
                        # Show cycle results
                        cycles = result_state.get("cycles_completed", 0)
                        balance = result_state.get("wallet_balance_sol", 0)
                        positions = len(result_state.get("active_positions", []))
                        reasoning = result_state.get("agent_reasoning", "")
                        
                        st.info(f"🎯 Cycle {cycles} Results:")
                        st.write(f"• Balance: {balance:.4f} SOL")
                        st.write(f"• Positions: {positions}")
                        
                        if reasoning:
                            with st.expander("🧠 AI Reasoning"):
                                st.write(reasoning[:500] + "..." if len(reasoning) > 500 else reasoning)
                    else:
                        st.error("❌ Cycle failed")
                        
            except Exception as e:
                st.error(f"❌ Error running cycle: {str(e)}")
                logger.error(f"Error running single cycle: {e}")

def render_agent_performance():
    """Render AI agent performance metrics"""
    try:
        agent_status = get_agent_status()
        
        if agent_status.get('status') == 'not_initialized':
            st.info("🤖 AI Agent not yet initialized")
            return
        
        if 'summary' in agent_status:
            summary = agent_status['summary']
            
            st.subheader("📊 AI Performance")
            
            perf_col1, perf_col2, perf_col3 = st.columns(3)
            
            with perf_col1:
                st.metric(
                    "Cycles Completed",
                    summary.get('cycles_completed', 0),
                    help="Number of AI decision cycles completed"
                )
                
                st.metric(
                    "Win Rate",
                    f"{summary.get('win_rate', 0) * 100:.1f}%",
                    help="Percentage of profitable trades"
                )
            
            with perf_col2:
                st.metric(
                    "Portfolio Value",
                    f"{summary.get('total_portfolio_value', 0):.4f} SOL",
                    help="Current total portfolio value"
                )
                
                st.metric(
                    "Total Trades",
                    summary.get('total_trades', 0),
                    help="Total number of completed trades"
                )
            
            with perf_col3:
                st.metric(
                    "Active Positions",
                    summary.get('active_positions_count', 0),
                    help="Currently held positions"
                )
                
                st.metric(
                    "AI Strategy",
                    summary.get('ai_strategy', 'Unknown'),
                    help="Current AI trading strategy"
                )
        
        # Last update info
        last_update = agent_status.get('last_update', '')
        if last_update:
            try:
                from datetime import datetime
                update_time = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                time_ago = datetime.now() - update_time.replace(tzinfo=None)
                
                if time_ago.total_seconds() < 60:
                    time_str = f"{int(time_ago.total_seconds())}s ago"
                elif time_ago.total_seconds() < 3600:
                    time_str = f"{int(time_ago.total_seconds() / 60)}m ago"
                else:
                    time_str = f"{int(time_ago.total_seconds() / 3600)}h ago"
                
                st.caption(f"Last update: {time_str}")
            except:
                st.caption(f"Last update: {last_update[:19]}")
                
    except Exception as e:
        st.error(f"Error displaying performance: {e}")
        logger.error(f"Error in render_agent_performance: {e}")

def render_sidebar(data):
    """Render the complete updated sidebar"""
    with st.sidebar:
        st.header("🧠 Pure AI Trading Agent")
        st.caption("Powered by Claude Sonnet 4")
        
        # Trading mode selection
        render_trading_mode_selector()
        
        # Dry run toggle with detailed explanation
        render_trading_mode_toggle()
        
        # Mode description
        render_mode_description()
        
        # Custom parameters (if custom mode selected)
        render_custom_parameters()
        
        # Agent controls
        render_agent_controls()
        
        # Performance metrics
        render_agent_performance()
        
        # System information
        st.markdown("---")
        st.subheader("ℹ️ System Info")
        
        # Data sources status
        try:
            from src.data.unified_enrichment import get_unified_enrichment_capabilities
            capabilities = get_unified_enrichment_capabilities()
            
            st.write("**Data Sources:**")
            sources = [
                ("DexScreener", True),  # Always available
                ("RugCheck", capabilities.get('safety_data_collection', False)),
                ("TweetScout", capabilities.get('social_data_collection', False)),
                ("Vector Memory", capabilities.get('api_available', False))
            ]
            
            for source, available in sources:
                icon = "✅" if available else "❌"
                st.write(f"{icon} {source}")
                
        except Exception as e:
            st.write("⚠️ Error checking data sources")
            logger.error(f"Error checking capabilities: {e}")
        
        # Auto-refresh info
        st.markdown("---")
        st.info("💡 **Tip:** Dashboard auto-refreshes every 30 seconds when agent is running")
        
        # Manual refresh button
        if st.button("🔄 Refresh Dashboard"):
            st.rerun()
        
        # Footer with mode indicator
        trading_mode = st.session_state.get('agent_parameters', {}).get('trading_mode', 'dry_run')
        if trading_mode == 'dry_run':
            st.success("🔒 **SAFE MODE ACTIVE**")
        else:
            st.error("⚠️ **LIVE TRADING MODE**")
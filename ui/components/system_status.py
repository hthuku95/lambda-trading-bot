# ui/components/system_status.py
"""
Updated System Status Component - Using RugCheck + TweetScout with Wallet Authentication
Clean implementation with proper authentication method detection
"""
import streamlit as st
import os
from datetime import datetime
from typing import Dict, Any
from src.data.unified_enrichment import get_unified_enrichment_capabilities
from src.data.rugcheck_client import check_rugcheck_api_health
from src.data.social_intelligence import check_social_intelligence_health

def render_api_health_status(data):
    """Render API health status for RugCheck + TweetScout"""
    st.subheader("🔌 API Health Status")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**RugCheck API**")
        rugcheck_health = check_rugcheck_api_health()
        
        if rugcheck_health.get("healthy", False):
            st.success("🟢 Online")
            st.write(f"• Solana Support: {'✅' if rugcheck_health.get('solana_available') else '❌'}")
            st.write(f"• Authentication: {'✅ Wallet Configured' if rugcheck_health.get('wallet_configured') else '⚪ No Wallet (not needed for basic use)'}")
            auth_working = rugcheck_health.get('auth_working')
            if auth_working is True:
                st.write("• Auth Status: ✅ Working (bulk endpoints unlocked)")
            elif auth_working is False:
                st.write("• Auth Status: ❌ Failed (bulk fallback: individual requests)")
            else:
                st.write("• Auth Status: ⚪ Not configured (core endpoints are unauthenticated)")
            st.write(f"• Bulk Endpoints: {'✅ Available' if rugcheck_health.get('bulk_endpoints_available') else '⚪ Using individual requests'}")
            if rugcheck_health.get('supported_chains'):
                st.write(f"• Supported Chains: {rugcheck_health.get('supported_chains')}")
            st.write(f"• Response Time: {rugcheck_health.get('response_time_ms', 0):.0f}ms")
        else:
            st.error("🔴 Offline")
            error_msg = rugcheck_health.get('error', 'Unknown error')
            st.write(f"**Error:** {error_msg}")
            if rugcheck_health.get('wallet_configured'):
                st.write("• Wallet: ✅ Configured")
            else:
                st.write("• Wallet: ❌ Missing SOLANA_PRIVATE_KEY")
    
    with col2:
        st.write("**TweetScout API**")
        social_health = check_social_intelligence_health()
        
        if social_health.get("healthy", False):
            st.success("🟢 Online")
            st.write(f"• API Key: {'✅ Configured' if social_health.get('api_key_configured') else '❌ Missing'}")
            st.write("• Social Analysis: ✅ Available")
            if social_health.get('response_time_ms'):
                st.write(f"• Response Time: {social_health.get('response_time_ms', 0):.0f}ms")
        else:
            st.error("🔴 Offline")
            error_msg = social_health.get('error', 'Unknown error')
            st.write(f"**Error:** {error_msg}")
    
    # Nansen section
    st.write("**Nansen Smart Money API**")
    try:
        from src.data.nansen_client import check_nansen_health
        nansen = check_nansen_health()
        if nansen.get("healthy"):
            st.success("🟢 Online")
        else:
            reason = nansen.get("reason", "unavailable")
            if "not set" in reason:
                st.info(f"⚪ Not configured — set NANSEN_API_KEY to enable smart money signals")
            elif "credits" in reason.lower():
                st.warning(f"🟡 Credits depleted — resets on plan cycle")
            else:
                st.warning(f"🟡 {reason}")
    except Exception as e:
        st.info("⚪ Nansen not configured")

    # Overall system capabilities
    st.write("---")
    st.write("**System Capabilities**")
    capabilities = get_unified_enrichment_capabilities()
    
    cap_col1, cap_col2 = st.columns(2)
    
    with cap_col1:
        st.write(f"• Token Safety Analysis: {'✅' if capabilities.get('token_safety_analysis') else '❌'}")
        st.write(f"• Social Sentiment Analysis: {'✅' if capabilities.get('social_sentiment_analysis') else '❌'}")
        st.write(f"• Whale Tracking: {'✅' if capabilities.get('whale_tracking') else '❌'}")
    
    with cap_col2:
        st.write(f"• Market Analytics: {'✅' if capabilities.get('market_analytics') else '❌'}")
        st.write(f"• Comprehensive Analysis: {'✅' if capabilities.get('comprehensive_analysis') else '❌'}")
        st.write(f"• Full Enrichment: {'✅' if capabilities.get('full_enrichment') else '❌'}")

def render_system_tests(data):
    """Render system testing interface"""
    st.subheader("🧪 System Tests")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔍 Test RugCheck"):
            with st.spinner("Testing RugCheck..."):
                try:
                    from src.data.rugcheck_client import rugcheck_client
                    # Test with a known token (USDC)
                    test_token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                    result = rugcheck_client.get_token_safety_analysis(test_token)
                    
                    if result and not result.get('error'):
                        st.success("✅ RugCheck test passed")
                        st.write(f"Token: {result.get('token_symbol', 'Unknown')}")
                        st.write(f"Safety Score: {result.get('safety_score', 0):.1f}/100")
                        st.write(f"Risk Level: {result.get('risk_level', 'Unknown')}")
                        st.write(f"Recommendation: {result.get('recommendation', 'Unknown')}")
                    else:
                        st.error("❌ RugCheck test failed")
                        st.write(f"Error: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    st.error(f"❌ Test failed: {str(e)}")
    
    with col2:
        if st.button("📱 Test TweetScout"):
            with st.spinner("Testing TweetScout..."):
                try:
                    from src.data.social_intelligence import social_intelligence_client
                    # Test social intelligence
                    result = social_intelligence_client.check_api_health()
                    
                    if result.get('healthy'):
                        st.success("✅ TweetScout test passed")
                        st.write(f"Status: {result.get('status', 'Unknown')}")
                        if result.get('response_time_ms'):
                            st.write(f"Response Time: {result.get('response_time_ms')}ms")
                    else:
                        st.error("❌ TweetScout test failed")
                        st.write(f"Error: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    st.error(f"❌ Test failed: {str(e)}")
    
    with col3:
        if st.button("🔧 Test Unified Analysis"):
            with st.spinner("Testing unified analysis..."):
                try:
                    from src.data.unified_enrichment import unified_enrichment
                    # Test with a known token
                    test_token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                    result = unified_enrichment.get_comprehensive_token_analysis(test_token)
                    
                    if result and not result.get('error'):
                        st.success("✅ Unified analysis test passed")
                        st.write(f"Overall Score: {result.get('overall_score', 0):.1f}/100")
                        st.write(f"Data Sources: {result.get('data_sources', {})}")
                        st.write(f"Quality: {result.get('enrichment_quality', 'Unknown')}")
                    else:
                        st.error("❌ Unified analysis test failed")
                        st.write(f"Error: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    st.error(f"❌ Test failed: {str(e)}")

def render_environment_status():
    """Render environment and configuration status"""
    st.subheader("🌍 Environment Status")
    
    # Check environment variables for wallet-based authentication
    env_status = {
        "SOLANA_PRIVATE_KEY": bool(os.getenv("SOLANA_PRIVATE_KEY")),
        "TWEETSCOUT_API_KEY": bool(os.getenv("TWEETSCOUT_API_KEY")),
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
        "SOLANA_RPC_URL": bool(os.getenv("SOLANA_RPC_URL"))
    }
    
    st.write("**Environment Variables:**")
    for key, configured in env_status.items():
        status_icon = "✅" if configured else "❌"
        status_text = "Configured" if configured else "Missing"
        
        # Add context for each variable
        if key == "SOLANA_PRIVATE_KEY":
            description = " (Required for RugCheck wallet auth & trading)"
        elif key == "TWEETSCOUT_API_KEY":
            description = " (Required for social intelligence)"
        elif key == "OPENAI_API_KEY":
            description = " (Required for AI agent operations)"
        elif key == "SOLANA_RPC_URL":
            description = " (Required for blockchain operations)"
        else:
            description = ""
            
        st.write(f"• {key}: {status_icon} {status_text}{description}")
    
    # Authentication methods status
    st.write("---")
    st.write("**Authentication Methods:**")
    st.write("✅ RugCheck: Solana Wallet Authentication")
    st.write("✅ TweetScout: API Key Authentication")
    st.write("✅ Solana RPC: Direct Connection")
    st.write("✅ OpenAI: API Key Authentication")
    
    # Migration status
    st.write("---")
    st.write("**Migration Status:**")
    st.write("✅ BitQuery dependencies removed")
    st.write("✅ RugCheck wallet authentication implemented")
    st.write("✅ TweetScout client implemented")
    st.write("✅ Unified enrichment active")
    st.write("✅ UI components updated")
    st.write("✅ System status aligned with wallet auth")
    
    # System info
    st.write("---")
    st.write("**System Information:**")
    st.write(f"• Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.write("• Data Sources: RugCheck + TweetScout + DexScreener")
    st.write("• Architecture: Unified Enrichment")
    st.write("• Migration: Complete")
    st.write("• Authentication: Wallet-Based (RugCheck) + API Keys (TweetScout)")

def render_troubleshooting_guide():
    """Render troubleshooting guide for common issues"""
    st.subheader("🔍 Troubleshooting Guide")
    
    with st.expander("Common Issues & Solutions"):
        st.markdown("""
        **RugCheck Wallet Authentication Issues:**
        - `ImportError: Base58Encoder`: PyNaCl import issue - update rugcheck_client.py
        - `401 Unauthorized`: Check your SOLANA_PRIVATE_KEY in .env file
        - `Signature verification failed`: Ensure private key format is correct (base58)
        - `No private key available`: Set SOLANA_PRIVATE_KEY environment variable
        
        **TweetScout API Issues:**
        - `403 Forbidden`: Verify your TWEETSCOUT_API_KEY is valid
        - `402 Payment Required`: Check your TweetScout account billing
        - Slow responses: TweetScout API can be slower than expected
        
        **Solana Wallet Issues:**
        - Invalid private key format: Ensure key is in base58 format
        - RPC connection failed: Check SOLANA_RPC_URL is set and accessible
        - Transaction signing failed: Verify wallet has sufficient SOL for gas
        
        **General Issues:**
        - No enrichment data: Check that SOLANA_PRIVATE_KEY and TWEETSCOUT_API_KEY are configured
        - Cache issues: Use the "Force Cache Clear" button
        - Import errors: Ensure all dependencies are installed correctly
        
        **Environment Setup:**
        1. Create a .env file in the project root
        2. Add your Solana private key: `SOLANA_PRIVATE_KEY=your_base58_private_key`
        3. Add TweetScout API key: `TWEETSCOUT_API_KEY=your_api_key`
        4. Add OpenAI API key: `OPENAI_API_KEY=your_openai_key`
        5. Add Solana RPC URL: `SOLANA_RPC_URL=your_rpc_endpoint`
        """)
    
    with st.expander("Wallet Authentication Setup"):
        st.markdown("""
        **Setting up Solana Wallet Authentication for RugCheck:**
        
        1. **Get your Solana private key in base58 format:**
           - From Phantom: Export private key (base58 string)
           - From Solflare: Export private key (base58 string)
           - From CLI: Use `solana-keygen` to generate or export
        
        2. **Add to environment:**
           ```
           SOLANA_PRIVATE_KEY=your_base58_private_key_here
           ```
        
        3. **Security Notes:**
           - Private key is only used for message signing (authentication)
           - No funds are at risk from RugCheck authentication
           - Key never leaves your local environment
           - Standard Web3 authentication practice
        
        4. **Testing Authentication:**
           - Use the "Test RugCheck" button above
           - Check system logs for authentication success
           - Verify wallet address matches your expectations
        """)

def render_system_status_tab(data):
    """Main system status tab renderer"""
    st.header("⚙️ System Status")
    
    # Quick status overview
    st.subheader("📊 Quick Status Overview")
    
    # Get health status
    rugcheck_health = check_rugcheck_api_health()
    try:
        social_health = check_social_intelligence_health()
    except:
        social_health = {"healthy": False, "error": "Module not available"}
    
    capabilities = get_unified_enrichment_capabilities()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if rugcheck_health.get("healthy"):
            st.success("🟢 RugCheck\nONLINE")
        else:
            st.error("🔴 RugCheck\nOFFLINE")
    
    with col2:
        if social_health.get("healthy"):
            st.success("🟢 TweetScout\nONLINE")
        else:
            st.error("🔴 TweetScout\nOFFLINE")
    
    with col3:
        if capabilities.get("full_enrichment"):
            st.success("🟢 Full Analysis\nAVAILABLE")
        elif capabilities.get("api_available"):
            st.warning("🟡 Partial Analysis\nAVAILABLE")
        else:
            st.error("🔴 Analysis\nLIMITED")
    
    with col4:
        wallet_configured = bool(os.getenv("SOLANA_PRIVATE_KEY"))
        if wallet_configured:
            st.success("🟢 Wallet\nCONFIGURED")
        else:
            st.error("🔴 Wallet\nMISSING")
    
    st.write("---")
    
    # Detailed status sections
    render_api_health_status(data)
    st.write("---")
    render_system_tests(data)
    st.write("---")
    render_environment_status()
    st.write("---")
    render_troubleshooting_guide()
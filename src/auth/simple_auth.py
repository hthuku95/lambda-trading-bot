# src/auth/simple_auth.py
"""
Simple private authentication for the trading dashboard with VPN security
No signups, no 2FA - just secure VPN + credential access for the owner
"""
import os
import hashlib
import streamlit as st
from typing import Optional
from src.auth.vpn_security import vpn_security

class SimpleAuth:
    def __init__(self):
        # Get credentials from environment variables
        self.admin_username = os.getenv("DASHBOARD_USERNAME", "admin")
        self.admin_password = os.getenv("DASHBOARD_PASSWORD", "trading2025!")
        self.session_timeout = 24 * 60 * 60  # 24 hours in seconds
        
    def hash_password(self, password: str) -> str:
        """Hash password for secure comparison"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify login credentials"""
        return (username == self.admin_username and 
                password == self.admin_password)
    
    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated"""
        return st.session_state.get("authenticated", False)
    
    def login(self, username: str, password: str) -> bool:
        """Attempt to log in user"""
        if self.verify_credentials(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.login_time = st.session_state.get("login_time", 0)
            return True
        return False
    
    def logout(self):
        """Log out the current user"""
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.login_time = None
    
    def require_auth(self):
        """Require both VPN connection and authentication"""
        # First check VPN access
        vpn_security.require_vpn()
        
        # Then check authentication
        if not self.is_authenticated():
            self.show_login_page()
            st.stop()
    
    def show_login_page(self):
        """Display the login form with VPN status"""
        st.set_page_config(
            page_title="🔐 Secure Access Required",
            page_icon="🔐",
            layout="centered"
        )
        
        # Center the login form
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            # VPN Status indicator
            client_ip = vpn_security.get_client_ip()
            is_vpn, vpn_message = vpn_security.check_vpn_access()
            
            if is_vpn:
                st.success(f"🛡️ VPN Connected: {client_ip}")
            
            st.markdown("# 🔐 Secure Access")
            st.markdown("### Private Trading Dashboard")
            st.markdown("---")
            
            # Login form
            with st.form("login_form"):
                st.markdown("#### Enter Your Credentials")
                username = st.text_input("Username", placeholder="Enter username")
                password = st.text_input("Password", type="password", placeholder="Enter password")
                
                col_a, col_b = st.columns(2)
                
                with col_a:
                    login_button = st.form_submit_button("🚀 Access Dashboard", use_container_width=True)
                
                with col_b:
                    if st.form_submit_button("❌ Cancel", use_container_width=True):
                        st.stop()
            
            # Handle login attempt
            if login_button:
                if username and password:
                    if self.login(username, password):
                        st.success("✅ Access Granted! Redirecting...")
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials. Access denied.")
                        st.info("🔒 This is a private dashboard. Only authorized users can access.")
                else:
                    st.warning("⚠️ Please enter both username and password")
            
            # Security notices
            st.markdown("---")
            st.markdown("🛡️ **Security**: VPN + Authentication Required")
            st.markdown(f"📍 **Your IP**: {client_ip}")
            
            # Optional: Show your contact info
            st.markdown("📧 *For access requests, contact the system administrator*")

# Create global auth instance
auth_manager = SimpleAuth()
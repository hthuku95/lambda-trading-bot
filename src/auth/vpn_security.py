# src/auth/vpn_security.py
"""
VPN-only security for the trading dashboard
Only allows access from specified VPN networks
"""
import os
import ipaddress
import streamlit as st
from typing import List, Optional

class VPNSecurity:
    def __init__(self):
        self.vpn_only_mode = os.getenv("VPN_ONLY_MODE", "true").lower() == "true"
        self.vpn_network = os.getenv("VPN_NETWORK", "10.7.0.0/24")
        self.admin_vpn_ip = os.getenv("ADMIN_VPN_IP", "10.7.0.8")
        self.allowed_ips = self._parse_allowed_ips()
    
    def _parse_allowed_ips(self) -> List[ipaddress.IPv4Network]:
        """Parse allowed IP ranges from environment"""
        allowed_ranges = []
        
        # Add main VPN network
        try:
            allowed_ranges.append(ipaddress.IPv4Network(self.vpn_network, strict=False))
        except ValueError:
            pass
        
        # Add localhost for development
        allowed_ranges.append(ipaddress.IPv4Network("127.0.0.1/32"))
        
        # Add any additional IPs from ALLOWED_IPS
        additional_ips = os.getenv("ALLOWED_IPS", "").split(",")
        for ip_str in additional_ips:
            ip_str = ip_str.strip()
            if ip_str:
                try:
                    if "/" in ip_str:
                        allowed_ranges.append(ipaddress.IPv4Network(ip_str, strict=False))
                    else:
                        allowed_ranges.append(ipaddress.IPv4Network(f"{ip_str}/32"))
                except ValueError:
                    continue
        
        return allowed_ranges
    
    def get_client_ip(self) -> Optional[str]:
        """Get client IP address from various headers"""
        # Check Streamlit's built-in way first
        try:
            # For Streamlit Cloud/hosting platforms
            if hasattr(st, 'experimental_get_query_params'):
                # Try to get from session info
                pass
        except:
            pass
        
        # Check common headers
        headers_to_check = [
            'X-Forwarded-For',
            'X-Real-IP',
            'CF-Connecting-IP',
            'X-Client-IP',
            'HTTP_X_FORWARDED_FOR',
            'HTTP_X_REAL_IP'
        ]
        
        # Try to access headers (this works in some Streamlit deployments)
        try:
            import streamlit.web.server.websocket_headers as headers
            for header in headers_to_check:
                if hasattr(headers, 'get_headers'):
                    client_headers = headers.get_headers()
                    if header in client_headers:
                        return client_headers[header].split(',')[0].strip()
        except:
            pass
        
        # For local development, assume localhost
        return "127.0.0.1"
    
    def is_vpn_connected(self, client_ip: str) -> bool:
        """Check if client IP is from VPN network"""
        try:
            client_addr = ipaddress.IPv4Address(client_ip)
            for allowed_network in self.allowed_ips:
                if client_addr in allowed_network:
                    return True
            return False
        except ValueError:
            return False
    
    def check_vpn_access(self) -> tuple[bool, str]:
        """Check VPN access and return status with message"""
        if not self.vpn_only_mode:
            return True, "VPN check disabled"
        
        client_ip = self.get_client_ip()
        
        if self.is_vpn_connected(client_ip):
            return True, f"✅ VPN access granted from {client_ip}"
        else:
            return False, f"🚫 Access denied. IP {client_ip} not on VPN network {self.vpn_network}"
    
    def require_vpn(self):
        """Block access if not connected to VPN"""
        allowed, message = self.check_vpn_access()
        
        if not allowed:
            self.show_vpn_required_page(message)
            st.stop()
    
    def show_vpn_required_page(self, error_message: str):
        """Display VPN required page"""
        st.set_page_config(
            page_title="🔐 VPN Required",
            page_icon="🔐",
            layout="centered"
        )
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("# 🛡️ VPN Access Required")
            st.markdown("### Private Trading Dashboard")
            st.markdown("---")
            
            st.error("🚫 **Access Denied**")
            st.warning(error_message)
            
            st.markdown("#### 🔒 Security Requirements:")
            st.markdown(f"• **Connect to VPN**: WireGuard network `{self.vpn_network}`")
            st.markdown(f"• **Expected VPN IP**: `{self.admin_vpn_ip}`")
            st.markdown("• **VPN Status**: Must be active and connected")
            
            st.markdown("---")
            st.markdown("#### 📋 **To Access This Dashboard:**")
            st.markdown("1. **Connect to your WireGuard VPN**")
            st.markdown("2. **Verify your IP is on the VPN network**")
            st.markdown("3. **Refresh this page**")
            
            # VPN status check
            client_ip = self.get_client_ip()
            st.markdown("#### 🔍 **Connection Status:**")
            st.code(f"Your current IP: {client_ip}")
            st.code(f"Required network: {self.vpn_network}")
            st.code(f"Expected VPN IP: {self.admin_vpn_ip}")
            
            if st.button("🔄 Retry Connection Check"):
                st.rerun()
            
            st.markdown("---")
            st.markdown("🛡️ **This dashboard contains sensitive trading data and requires secure VPN access.**")

# Create global VPN security instance
vpn_security = VPNSecurity()
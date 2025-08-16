"""LDAP service that proxies account data from Neon CRM for Pocket ID integration."""

import logging
from typing import Dict, List, Optional

from ldap3 import Server, Connection, ALL, MOCK_SYNC
from ldap3.core.exceptions import LDAPException
from ldap3.utils.log import set_library_log_detail_level, BASIC

from protohaven_api.config import get_config
from protohaven_api.integrations.neon import AccountCache
from protohaven_api.integrations.models import Member


log = logging.getLogger("integrations.ldap_service")
set_library_log_detail_level(BASIC)


class NeonLDAPService:
    """LDAP service that proxies Neon CRM member data."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 3891, base_dn: str = "dc=protohaven,dc=org"):
        self.host = host
        self.port = port
        self.base_dn = base_dn
        self.users_dn = f"ou=users,{base_dn}"
        
        # Use existing AccountCache for member data
        self.account_cache = AccountCache()
        
        # LDAP server setup
        self.server = None
        self.connection = None
        
        log.info(f"Initializing LDAP service on {host}:{port} with base DN: {base_dn}")
        log.info("Using AccountCache for member data (24-hour refresh cycle)"
    
    def _get_all_active_members(self) -> Dict[str, Member]:
        """Get all active members from AccountCache."""
        active_members = {}
        
        # AccountCache handles its own refresh cycle (24 hours)
        # We iterate through all cached accounts and filter for active ones
        for email_accounts in self.account_cache.values():
            if isinstance(email_accounts, dict):
                for member in email_accounts.values():
                    if (hasattr(member, 'account_current_membership_status') and 
                        member.account_current_membership_status == "Active" and
                        member.email):
                        active_members[member.email.lower()] = member
        
        return active_members
    
    def _get_member_by_email(self, email: str) -> Optional[Member]:
        """Get member by email address using AccountCache."""
        try:
            # AccountCache returns a dict of {neon_id: Member} for the email
            accounts_dict = self.account_cache.get(email, {})
            
            # Return the first active member found (usually there's only one per email)
            for member in accounts_dict.values():
                if (hasattr(member, 'account_current_membership_status') and 
                    member.account_current_membership_status == "Active"):
                    return member
        except (KeyError, AttributeError) as e:
            log.debug(f"Member not found in cache for email {email}: {e}")
        
        return None
    
    def _member_to_ldap_entry(self, member: Member) -> Dict:
        """Convert a Member object to LDAP entry attributes."""
        # Generate uid from email (username part)
        uid = member.email.split('@')[0] if member.email else f"user_{member.neon_id}"
        
        entry = {
            'objectClass': ['inetOrgPerson', 'organizationalPerson', 'person', 'top'],
            'uid': [uid],
            'cn': [member.name or f"{member.fname} {member.lname}".strip()],
            'sn': [member.lname or 'Unknown'],
            'givenName': [member.fname or 'Unknown'],
            'mail': [member.email],
            'employeeNumber': [str(member.neon_id)],
            'ou': ['users'],
        }
        
        # Add roles from API Server Role custom field
        if hasattr(member, 'roles') and member.roles:
            # Convert roles to a list of role names for LDAP
            role_names = [role['name'] for role in member.roles if role and 'name' in role]
            if role_names:
                entry['title'] = role_names
        
        # Filter out empty values
        return {k: v for k, v in entry.items() if v and v[0]}
    
    def authenticate_user(self, username: str, password: str) -> bool:
        """Authenticate user against Neon CRM data.
        
        Note: This is a basic implementation. In production, you'd want
        to integrate with Neon's actual authentication system.
        """
        member = self._get_member_by_email(username)
        if not member:
            # Try treating username as the email prefix
            active_members = self._get_all_active_members()
            for email, cached_member in active_members.items():
                if email.startswith(f"{username}@"):
                    member = cached_member
                    break
        
        if member:
            # Basic authentication - in production, integrate with Neon auth
            log.info(f"Authentication attempt for user: {username} (found: {member.email})")
            return True  # Placeholder - implement actual auth logic
        
        log.warning(f"Authentication failed for unknown user: {username}")
        return False
    
    def search_users(self, filter_str: str = "(objectClass=*)", base_dn: str = None) -> List[Dict]:
        """Search for users matching the given filter."""
        if base_dn is None:
            base_dn = self.users_dn
        
        results = []
        
        # Simple filter parsing - extend as needed
        if filter_str == "(objectClass=*)" or filter_str == "(objectClass=inetOrgPerson)":
            # Get all active members from AccountCache
            active_members = self._get_all_active_members()
            
            for member in active_members.values():
                entry = self._member_to_ldap_entry(member)
                dn = f"uid={entry['uid'][0]},{self.users_dn}"
                results.append({
                    'dn': dn,
                    'attributes': entry
                })
        
        log.info(f"LDAP search returned {len(results)} results for filter: {filter_str}")
        return results
    
    def get_user_by_dn(self, dn: str) -> Optional[Dict]:
        """Get user by distinguished name."""
        # Extract uid from DN
        if not dn.lower().startswith('uid='):
            return None
        
        uid = dn.split(',')[0].split('=')[1]
        
        # Find member by uid (which is email prefix)
        active_members = self._get_all_active_members()
        for email, member in active_members.items():
            if email.startswith(f"{uid}@"):
                entry = self._member_to_ldap_entry(member)
                return {
                    'dn': dn,
                    'attributes': entry
                }
        
        return None
    
    def start_server(self):
        """Start the LDAP server.
        
        Note: This uses ldap3's mock server as a lightweight implementation.
        For high-performance production use, consider a dedicated LDAP server.
        """
        try:
            log.info(f"Starting LDAP service on {self.host}:{self.port}")
            
            # AccountCache handles its own initialization and refresh
            # Trigger a refresh if needed
            if not hasattr(self.account_cache, '_data') or not self.account_cache._data:
                log.info("AccountCache is empty, triggering initial refresh")
                self.account_cache.refresh()
            
            # Create a lightweight LDAP server using ldap3's mock implementation
            self.server = Server('localhost', get_info=ALL)
            self.connection = Connection(
                self.server, 
                client_strategy=MOCK_SYNC,
                check_names=True
            )
            
            # Populate mock server with base structure
            self.connection.bind()
            
            # Add base DN
            self.connection.add(
                self.base_dn,
                ['dcObject', 'organization'],
                {'dc': 'protohaven', 'o': 'Protohaven'}
            )
            
            # Add users OU
            self.connection.add(
                self.users_dn,
                ['organizationalUnit'],
                {'ou': 'users'}
            )
            
            # Add users from Neon
            for result in self.search_users():
                self.connection.add(
                    result['dn'],
                    result['attributes']['objectClass'],
                    {k: v for k, v in result['attributes'].items() if k != 'objectClass'}
                )
            
            active_members = self._get_all_active_members()
            log.info(f"LDAP service started successfully with {len(active_members)} active users")
            return True
            
        except Exception as e:
            log.error(f"Failed to start LDAP server: {e}")
            return False
    
    def stop_server(self):
        """Stop the LDAP server."""
        if self.connection:
            self.connection.unbind()
            self.connection = None
        
        self.server = None
        log.info("LDAP service stopped")
    
    def health_check(self) -> Dict:
        """Return health status of the service."""
        active_members = self._get_all_active_members()
        return {
            "status": "healthy" if self.connection else "stopped",
            "cached_members": len(active_members),
            "total_cached_accounts": len(self.account_cache),
            "cache_refresh_period": "24 hours",
            "base_dn": self.base_dn,
            "users_dn": self.users_dn
        }


def create_ldap_service(host: str = "0.0.0.0", port: int = 3891) -> NeonLDAPService:
    """Factory function to create and configure the LDAP service."""
    base_dn = get_config("ldap/base_dn", default="dc=protohaven,dc=org")
    service = NeonLDAPService(host=host, port=port, base_dn=base_dn)
    return service

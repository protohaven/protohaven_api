#!/usr/bin/env python3
"""Demo LDAP service with mock data to show functionality without full Neon dependencies."""

import logging
import threading
import time
from typing import Dict, List, Optional
from unittest.mock import Mock

from ldap3 import Server, Connection, ALL, MOCK_SYNC
from ldap3.core.exceptions import LDAPException
from ldap3.utils.log import set_library_log_detail_level, BASIC


log = logging.getLogger("demo_ldap_service")
set_library_log_detail_level(BASIC)


class MockMember:
    """Mock Member class for demonstration."""
    
    def __init__(self, neon_id: int, fname: str, lname: str, email: str, membership_level: str = "Basic"):
        self.neon_id = neon_id
        self.fname = fname
        self.lname = lname
        self.email = email
        self.membership_level = membership_level
    
    @property
    def name(self) -> str:
        return f"{self.fname} {self.lname}"


class DemoNeonLDAPService:
    """Demo LDAP service with mock Neon CRM member data."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 3891, base_dn: str = "dc=protohaven,dc=org"):
        self.host = host
        self.port = port
        self.base_dn = base_dn
        self.users_dn = f"ou=users,{base_dn}"
        
        # Mock member data
        self._members_cache = self._create_mock_members()
        
        # LDAP server setup
        self.server = None
        self.connection = None
        
        log.info(f"Initializing demo LDAP service on {host}:{port} with base DN: {base_dn}")
    
    def _create_mock_members(self) -> Dict[str, MockMember]:
        """Create mock member data for demonstration."""
        mock_members = [
            MockMember(1001, "Alice", "Johnson", "alice.johnson@example.com", "Premium"),
            MockMember(1002, "Bob", "Smith", "bob.smith@example.com", "Basic"),
            MockMember(1003, "Carol", "Williams", "carol.williams@example.com", "Student"),
            MockMember(1004, "David", "Brown", "david.brown@example.com", "Premium"),
            MockMember(1005, "Eve", "Davis", "eve.davis@example.com", "Basic"),
        ]
        
        cache = {}
        for member in mock_members:
            # Index by email
            cache[member.email.lower()] = member
            # Also index by Neon ID
            cache[f"neon_{member.neon_id}"] = member
        
        return cache
    
    def _get_member_by_email(self, email: str) -> Optional[MockMember]:
        """Get member by email address."""
        return self._members_cache.get(email.lower())
    
    def _member_to_ldap_entry(self, member: MockMember) -> Dict:
        """Convert a Member object to LDAP entry attributes."""
        # Generate uid from email (username part)
        uid = member.email.split('@')[0] if member.email else f"user_{member.neon_id}"
        
        entry = {
            'objectClass': ['inetOrgPerson', 'organizationalPerson', 'person', 'top'],
            'uid': [uid],
            'cn': [member.name],
            'sn': [member.lname],
            'givenName': [member.fname],
            'mail': [member.email],
            'employeeNumber': [str(member.neon_id)],
            'ou': ['users'],
        }
        
        # Add membership level if available
        if hasattr(member, 'membership_level') and member.membership_level:
            entry['title'] = [member.membership_level]
        
        # Filter out empty values
        return {k: v for k, v in entry.items() if v and v[0]}
    
    def authenticate_user(self, username: str, password: str) -> bool:
        """Authenticate user against mock CRM data."""
        member = self._get_member_by_email(username)
        if not member:
            # Try treating username as the email prefix
            for email, cached_member in self._members_cache.items():
                if email.startswith(f"{username}@") and not email.startswith('neon_'):
                    member = cached_member
                    break
        
        if member:
            log.info(f"Authentication attempt for user: {username} (found: {member.email})")
            # For demo purposes, accept any non-empty password
            return bool(password.strip())
        
        log.warning(f"Authentication failed for unknown user: {username}")
        return False
    
    def search_users(self, filter_str: str = "(objectClass=*)", base_dn: str = None) -> List[Dict]:
        """Search for users matching the given filter."""
        if base_dn is None:
            base_dn = self.users_dn
        
        results = []
        
        # Simple filter parsing - extend as needed
        if filter_str == "(objectClass=*)" or filter_str == "(objectClass=inetOrgPerson)":
            # Return all users
            for key, member in self._members_cache.items():
                if key.startswith('neon_'):
                    continue  # Skip duplicate neon_id entries
                
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
        for email, member in self._members_cache.items():
            if email.startswith(f"{uid}@") and not email.startswith('neon_'):
                entry = self._member_to_ldap_entry(member)
                return {
                    'dn': dn,
                    'attributes': entry
                }
        
        return None
    
    def start_server(self):
        """Start the LDAP server."""
        try:
            log.info(f"Starting demo LDAP service on {self.host}:{self.port}")
            
            # For demonstration, we'll create a mock server
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
            
            # Add users from mock data
            for result in self.search_users():
                self.connection.add(
                    result['dn'],
                    result['attributes']['objectClass'],
                    {k: v for k, v in result['attributes'].items() if k != 'objectClass'}
                )
            
            log.info(f"Demo LDAP service started successfully with {len(self._members_cache)//2} users")
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
        log.info("Demo LDAP service stopped")
    
    def health_check(self) -> Dict:
        """Return health status of the service."""
        return {
            "status": "healthy" if self.connection else "stopped",
            "cached_members": len(self._members_cache)//2,  # Divide by 2 because we have email and neon_id entries
            "base_dn": self.base_dn,
            "users_dn": self.users_dn,
            "demo_mode": True
        }
    
    def demo_usage(self):
        """Demonstrate LDAP service functionality."""
        print("=== Demo LDAP Service Usage ===")
        print(f"Base DN: {self.base_dn}")
        print(f"Users DN: {self.users_dn}")
        print("\n--- Available Users ---")
        
        users = self.search_users()
        for user in users:
            attrs = user['attributes']
            print(f"DN: {user['dn']}")
            print(f"  Name: {attrs['cn'][0]}")
            print(f"  Email: {attrs['mail'][0]}")
            print(f"  Membership: {attrs.get('title', ['N/A'])[0]}")
            print()
        
        print("--- Authentication Tests ---")
        test_cases = [
            ("alice.johnson@example.com", "password123", True),
            ("alice.johnson", "password123", True),
            ("bob.smith@example.com", "", False),
            ("unknown@example.com", "password", False),
        ]
        
        for username, password, expected in test_cases:
            result = self.authenticate_user(username, password)
            status = "✓" if result == expected else "✗"
            print(f"{status} {username} + '{password}' -> {result} (expected {expected})")
        
        print("\n--- Health Check ---")
        health = self.health_check()
        for key, value in health.items():
            print(f"  {key}: {value}")


def main():
    """Main demo function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    print("Starting Neon CRM LDAP Service Demo")
    print("=====================================\n")
    
    # Create and start service
    service = DemoNeonLDAPService()
    
    if service.start_server():
        print("Service started successfully!\n")
        service.demo_usage()
        service.stop_server()
        print("\nDemo completed successfully!")
    else:
        print("Failed to start service.")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

"""Tests for the LDAP service integration with Neon CRM."""

import pytest
from unittest.mock import Mock, patch

from protohaven_api.integrations.ldap_service import NeonLDAPService, create_ldap_service
from protohaven_api.integrations.models import Member


class TestNeonLDAPService:
    """Test cases for NeonLDAPService."""
    
    def test_init(self):
        """Test service initialization."""
        service = NeonLDAPService()
        assert service.host == "0.0.0.0"
        assert service.port == 3891
        assert service.base_dn == "dc=protohaven,dc=org"
        assert service.users_dn == "ou=users,dc=protohaven,dc=org"
    
    def test_init_custom_params(self):
        """Test service initialization with custom parameters."""
        service = NeonLDAPService(
            host="127.0.0.1", 
            port=1389, 
            base_dn="dc=test,dc=org"
        )
        assert service.host == "127.0.0.1"
        assert service.port == 1389
        assert service.base_dn == "dc=test,dc=org"
        assert service.users_dn == "ou=users,dc=test,dc=org"
    
    def test_member_to_ldap_entry(self):
        """Test conversion of Member to LDAP entry."""
        service = NeonLDAPService()
        
        # Create a mock member
        member = Mock(spec=Member)
        member.neon_id = 12345
        member.fname = "John"
        member.lname = "Doe"
        member.name = "John Doe"
        member.email = "john.doe@example.com"
        member.roles = [{'name': 'Shop Tech', 'id': '238'}, {'name': 'Admin', 'id': '239'}]
        
        entry = service._member_to_ldap_entry(member)
        
        assert entry['uid'] == ['john.doe']
        assert entry['cn'] == ['John Doe']
        assert entry['sn'] == ['Doe']
        assert entry['givenName'] == ['John']
        assert entry['mail'] == ['john.doe@example.com']
        assert entry['employeeNumber'] == ['12345']
        assert entry['title'] == ['Shop Tech', 'Admin']
        assert 'inetOrgPerson' in entry['objectClass']
    
    def test_member_to_ldap_entry_minimal(self):
        """Test conversion with minimal member data."""
        service = NeonLDAPService()
        
        member = Mock(spec=Member)
        member.neon_id = 67890
        member.fname = None
        member.lname = None
        member.name = None
        member.email = "user@example.com"
        member.roles = None
        
        entry = service._member_to_ldap_entry(member)
        
        assert entry['uid'] == ['user']
        assert entry['sn'] == ['Unknown']
        assert entry['givenName'] == ['Unknown']
        assert entry['mail'] == ['user@example.com']
        assert entry['employeeNumber'] == ['67890']
        # No title field should be present when roles is None
        assert 'title' not in entry
    
    def test_member_to_ldap_entry_roles(self):
        """Test conversion with various role configurations."""
        service = NeonLDAPService()
        
        # Test with single role
        member = Mock(spec=Member)
        member.neon_id = 1
        member.fname = "Test"
        member.lname = "User"
        member.name = "Test User"
        member.email = "test@example.com"
        member.roles = [{'name': 'Admin', 'id': '239'}]
        
        entry = service._member_to_ldap_entry(member)
        assert entry['title'] == ['Admin']
        
        # Test with multiple roles
        member.roles = [
            {'name': 'Admin', 'id': '239'},
            {'name': 'Shop Tech', 'id': '238'},
            {'name': 'Instructor', 'id': '75'}
        ]
        
        entry = service._member_to_ldap_entry(member)
        assert entry['title'] == ['Admin', 'Shop Tech', 'Instructor']
        
        # Test with empty roles list
        member.roles = []
        entry = service._member_to_ldap_entry(member)
        assert 'title' not in entry
        
        # Test with malformed roles
        member.roles = [{'id': '239'}, {'name': 'Admin', 'id': '239'}]
        entry = service._member_to_ldap_entry(member)
        assert entry['title'] == ['Admin']
    
    def test_get_all_active_members(self):
        """Test getting all active members from AccountCache."""
        service = NeonLDAPService()
        
        # Mock active member
        mock_member1 = Mock(spec=Member)
        mock_member1.neon_id = 1
        mock_member1.email = "user1@example.com"
        mock_member1.account_current_membership_status = "Active"
        
        # Mock inactive member (should be filtered out)
        mock_member2 = Mock(spec=Member)
        mock_member2.neon_id = 2
        mock_member2.email = "user2@example.com"
        mock_member2.account_current_membership_status = "Inactive"
        
        # Mock the AccountCache data structure
        service.account_cache._data = {
            "user1@example.com": {1: mock_member1},
            "user2@example.com": {2: mock_member2}
        }
        
        active_members = service._get_all_active_members()
        
        # Verify only active member is returned
        assert len(active_members) == 1
        assert "user1@example.com" in active_members
        assert active_members["user1@example.com"] == mock_member1
    
    def test_get_member_by_email(self):
        """Test getting member by email address using AccountCache."""
        service = NeonLDAPService()
        
        # Mock active member
        mock_member = Mock(spec=Member)
        mock_member.account_current_membership_status = "Active"
        
        # Mock AccountCache get method
        service.account_cache.get = Mock(return_value={1: mock_member})
        
        result = service._get_member_by_email("test@example.com")
        assert result == mock_member
        service.account_cache.get.assert_called_with("test@example.com", {})
        
        # Test case insensitivity is handled by AccountCache
        result = service._get_member_by_email("TEST@EXAMPLE.COM")
        assert result == mock_member
        
        # Test not found
        service.account_cache.get = Mock(return_value={})
        result = service._get_member_by_email("notfound@example.com")
        assert result is None
    
    def test_authenticate_user(self):
        """Test user authentication."""
        service = NeonLDAPService()
        
        # Mock member
        mock_member = Mock(spec=Member)
        mock_member.email = "test@example.com"
        mock_member.account_current_membership_status = "Active"
        
        # Mock _get_member_by_email
        service._get_member_by_email = Mock(return_value=mock_member)
        
        # Test email-based authentication
        assert service.authenticate_user("test@example.com", "password") is True
        
        # Mock _get_all_active_members for username-based auth
        service._get_member_by_email = Mock(return_value=None)  # Email lookup fails
        service._get_all_active_members = Mock(return_value={"test@example.com": mock_member})
        
        # Test username-based authentication (email prefix)
        assert service.authenticate_user("test", "password") is True
        
        # Test unknown user
        service._get_member_by_email = Mock(return_value=None)
        service._get_all_active_members = Mock(return_value={})
        assert service.authenticate_user("unknown@example.com", "password") is False
    
    def test_search_users(self):
        """Test LDAP user search functionality."""
        service = NeonLDAPService()
        
        # Mock member
        mock_member = Mock(spec=Member)
        mock_member.neon_id = 1
        mock_member.fname = "John"
        mock_member.lname = "Doe"
        mock_member.name = "John Doe"
        mock_member.email = "john@example.com"
        
        # Mock _get_all_active_members
        service._get_all_active_members = Mock(return_value={"john@example.com": mock_member})
        
        results = service.search_users("(objectClass=*)")
        
        assert len(results) == 1
        assert results[0]['dn'] == "uid=john,ou=users,dc=protohaven,dc=org"
        assert results[0]['attributes']['cn'] == ['John Doe']
        assert results[0]['attributes']['mail'] == ['john@example.com']
    
    def test_health_check(self):
        """Test health check functionality."""
        service = NeonLDAPService()
        
        # Mock methods
        service._get_all_active_members = Mock(return_value={})
        service.account_cache.__len__ = Mock(return_value=5)
        
        health = service.health_check()
        
        assert health['status'] == 'stopped'
        assert health['cached_members'] == 0
        assert health['total_cached_accounts'] == 5
        assert health['cache_refresh_period'] == '24 hours'
        assert health['base_dn'] == 'dc=protohaven,dc=org'
        assert health['users_dn'] == 'ou=users,dc=protohaven,dc=org'
    
    @patch('protohaven_api.integrations.ldap_service.get_config')
    def test_create_ldap_service(self, mock_get_config):
        """Test factory function for creating LDAP service."""
        mock_get_config.return_value = "dc=custom,dc=org"
        
        service = create_ldap_service(host="127.0.0.1", port=1389)
        
        assert service.host == "127.0.0.1"
        assert service.port == 1389
        assert service.base_dn == "dc=custom,dc=org"
        mock_get_config.assert_called_once_with("ldap/base_dn", default="dc=protohaven,dc=org")

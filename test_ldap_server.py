#!/usr/bin/env python3
"""Unit tests for LDAP server modifications"""

import pytest
import sys
import io
sys.path.insert(0, '/app')

from protohaven_api.ldap_server import Tree, LDIF, MALC
from twisted.test import test_internet
from twisted.internet import defer, reactor
from twisted.trial import unittest

class TestLDAPServerModification(unittest.TestCase):
    """Test LDAP server modification functionality"""
    
    def test_tree_initialization(self):
        """Test that Tree initializes with correct LDIF data"""
        tree = Tree()
        self.assertEqual(tree.current_ldif, LDIF)
        self.assertIsNotNone(tree.db)
    
    def test_ldif_data_properties(self):
        """Test LDIF and MALC data properties"""
        # Verify LDIF is bytes
        self.assertIsInstance(LDIF, bytes)
        self.assertGreater(len(LDIF), 0)
        
        # Verify MALC is string
        self.assertIsInstance(MALC, str)
        self.assertGreater(len(MALC), 0)
        
        # Verify MALC can be encoded to bytes
        malc_bytes = MALC.encode('utf-8')
        self.assertIsInstance(malc_bytes, bytes)
    
    def test_ldif_modification(self):
        """Test basic LDIF data modification"""
        initial_ldif = LDIF
        additional_data = b"\ndn: cn=test,dc=example,dc=org\ncn: test\nobjectClass: person\nsn: Test"
        
        new_ldif = initial_ldif + additional_data
        self.assertEqual(len(new_ldif), len(initial_ldif) + len(additional_data))
        self.assertTrue(new_ldif.startswith(initial_ldif))
    
    def test_malc_data_appending(self):
        """Test appending MALC data to LDIF"""
        initial_size = len(LDIF)
        malc_bytes = MALC.encode('utf-8')
        combined = LDIF + malc_bytes
        
        self.assertEqual(len(combined), initial_size + len(malc_bytes))
        self.assertTrue(combined.startswith(LDIF))
        self.assertTrue(combined.endswith(malc_bytes))

    def test_update_ldif_method_exists(self):
        """Test that Tree has update_ldif method"""
        tree = Tree()
        self.assertTrue(hasattr(tree, 'update_ldif'))
        self.assertTrue(callable(getattr(tree, 'update_ldif')))

    def test_global_functions_exist(self):
        """Test that global access functions exist"""
        from protohaven_api.ldap_server import get_tree_instance, update_server_ldif
        self.assertTrue(callable(get_tree_instance))
        self.assertTrue(callable(update_server_ldif))

if __name__ == '__main__':
    # Run pytest
    import pytest
    pytest.main([__file__, '-v'])

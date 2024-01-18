"""Unit tests for role-based authentication"""
import unittest

from protohaven_api import rbac

# from unittest.mock import patch


class RBACTest(unittest.TestCase):
    """Tests for role based authentication"""

    def test_require_login_redirect(self):
        """require_login() redirects when not logged in"""
        fn = rbac.require_login(lambda: "called")
        result = fn()
        self.assertTrue(result)

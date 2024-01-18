"""Unit tests for role-based authentication"""
from protohaven_api import rbac


def test_require_login_redirect(self):
    """require_login() redirects when not logged in"""
    fn = rbac.require_login(lambda: "called")
    result = fn()
    self.assertTrue(result)

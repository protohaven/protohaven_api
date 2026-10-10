# pylint: skip-file
"""Verify staff page access controls"""

from protohaven_api.integrations.models import Role
from protohaven_api.testing import fixture_client, setup_session


def test_staff_page_denied_to_non_staff(client):
    """A logged-in non-staff account cannot load the staff dashboard."""
    setup_session(client, [Role.SHOP_TECH])

    response = client.get("/staff")

    assert response.status_code == 401
    assert b"Access Denied" in response.data

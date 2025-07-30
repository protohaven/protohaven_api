"""Handlers for equipment reservation"""

import logging

from flask import Blueprint, request

from protohaven_api.integrations import booked
from protohaven_api.integrations.models import Role
from protohaven_api.rbac import require_login_role

log = logging.getLogger("handlers.reservations")

page = Blueprint("reservations", __name__)


@page.route("/reservations/set_tool", methods=["POST"])
@require_login_role(Role.ADMIN)
def reservations_set_tool():
    """Set the tool availability in Booked scheduler"""
    data = request.json
    rid = data["id"]
    avail = data["available"]
    return booked.set_resource_status(
        rid, booked.STATUS_AVAILABLE if avail else booked.STATUS_UNAVAILABLE
    )

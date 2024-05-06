"""Handlers for equipment reservation"""
import datetime
import logging

from dateutil import parser as dateparser
from flask import Blueprint, Response, current_app, redirect, request

from protohaven_api.integrations import booked
from protohaven_api.rbac import Role, require_login_role

log = logging.getLogger("handlers.reservations")

page = Blueprint("reservations", __name__)


@page.route("/reservations/set_tool", methods=["POST"])
@require_login_role(Role.ADMIN)
def instructor_class_update():
    """Confirm or unconfirm a class to run, by the instructor"""
    data = request.json
    rid = data["id"]
    avail = data["available"]
    return booked.set_resource_status(
        rid, booked.STATUS_AVAILABLE if avail else booked.STATUS_UNAVAILABLE
    )

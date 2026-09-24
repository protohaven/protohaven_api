"""Booked QA fixture helpers."""

from dataclasses import dataclass

from protohaven_api.integrations import booked
from protohaven_api.qa.base import QAContext


@dataclass
class MockBookedUser:
    """Handle for a QA-created Booked user."""

    user_id: str
    email: str


def create_user(ctx: QAContext, fname: str, lname: str, email: str) -> MockBookedUser:
    """Create a Booked user and register cleanup."""
    result = booked.create_user_as_member(fname, lname, email)
    if result.get("errors"):
        raise RuntimeError(f"Failed to create Booked user: {result}")
    user_id = result["userId"]
    ctx.cleanup.register(
        f"delete Booked user {user_id}", lambda: booked.delete_user(user_id)
    )
    return MockBookedUser(user_id=user_id, email=email)


def create_resource(ctx: QAContext, name: str) -> str:
    """Create a Booked resource and register cleanup."""
    result = booked.create_resource(name)
    resource_id = result["resourceId"]
    ctx.cleanup.register(
        f"delete Booked resource {resource_id}",
        lambda: booked.delete_resource(resource_id),
    )
    return resource_id


def reserve(
    ctx: QAContext,
    resource_id: str,
    start,
    end,
    title: str,
) -> str:
    """Create an automation reservation and register cleanup."""
    result = booked.reserve_resource(resource_id, start, end, title=title)
    refnum = result["referenceNumber"]
    ctx.cleanup.register(
        f"delete Booked reservation {refnum}",
        lambda: booked.delete_reservation(refnum),
    )
    return refnum

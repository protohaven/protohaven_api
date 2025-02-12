"""Role based access control for logged in users using session data from Neon CRM"""

import base64
import logging
from binascii import Error as B64Error
from dataclasses import dataclass

from flask import (  # pylint: disable=import-error
    Response,
    redirect,
    request,
    session,
    url_for,
)

from protohaven_api.config import get_config

enabled = True  # pylint: disable=invalid-name

log = logging.getLogger("rbac")


def set_rbac(en):
    """Changes global RBAC enabled state"""
    global enabled  # pylint: disable=global-statement
    enabled = en


def is_enabled():
    """Return whether RBAC is currently enabled"""
    return enabled


@dataclass
class Role:
    """Every Neon user has zero or more roles that can be checked for access."""

    INSTRUCTOR = {"name": "Instructor", "id": "75"}
    PRIVATE_INSTRUCTOR = {"name": "Private Instructor", "id": "246"}
    BOARD_MEMBER = {"name": "Board Member", "id": "244"}
    STAFF = {"name": "Staff", "id": "245"}
    SHOP_TECH = {"name": "Shop Tech", "id": "238"}
    SHOP_TECH_LEAD = {"name": "Shop Tech Lead", "id": "241"}
    EDUCATION_LEAD = {"name": "Education Lead", "id": "247"}
    ONBOARDING = {"name": "Onboarding", "id": "240"}
    ADMIN = {"name": "Admin", "id": "239"}
    SOFTWARE_DEV = {"id": "258", "name": "Software Dev"}
    MAINTENANCE_CREW = {"id": "259", "name": "Maintenance Crew"}
    MEMBERSHIP_AND_PROGRAMMING = {
        "id": "260",
        "name": "Membership and Programming Committee",
    }
    STRATEGIC_PLANNING = {"id": "261", "name": "Strategic Planning Committee"}
    FINANCE = {"id": "262", "name": "Finance Committee"}
    EXECUTIVE = {"id": "263", "name": "Executive Committee"}
    OPERATIONS = {"id": "266", "name": "Operations Committee"}

    AUTOMATION = {"name": "Automation", "id": None}

    @classmethod
    def as_dict(cls):
        """Return dictionary mapping name to the value of each field"""
        results = {}
        for f in dir(cls()):
            v = getattr(cls, f)
            if isinstance(v, dict) and v.get("id") is not None:
                results[v["name"]] = v
        return results

    @classmethod
    def can_onboard(cls, r):
        """Returns True if an onboarder can set this role in /onboarding/wizard"""
        return r in (cls.INSTRUCTOR, cls.PRIVATE_INSTRUCTOR, cls.SHOP_TECH)


def require_login(fn):
    """Decorator that requires the user to be logged in"""

    def do_login_check(*args, **kwargs):
        if is_enabled():
            if session.get("neon_id") is None:
                session["redirect_to_login_url"] = request.url
                return redirect(url_for("auth.login_user_neon_oauth"))
        return fn(*args, **kwargs)

    do_login_check.__name__ = fn.__name__
    return do_login_check


def roles_from_api_key(api_key):
    """Gets roles from the passed API key"""
    if api_key is None:
        return None
    codes = get_config("general/external_access_codes")
    try:
        api_key = base64.b64decode(api_key).decode("utf8").strip()
    except (B64Error, UnicodeDecodeError):
        pass
    return codes.get(api_key)


def get_roles():
    """Gets all the roles accessible by the incoming request/user.
    The payload and headers are searched for API keys"""
    api_key = request.values.get("api_key", None)
    if not api_key:
        api_key = request.headers.get("X-Protohaven-APIKey", None)
    if api_key is not None:
        return roles_from_api_key(api_key)

    acct = session.get("neon_account")
    if acct is None:
        return None
    result = []
    for cf in acct.get("accountCustomFields", []):
        if cf["name"] == "API server role":
            for ov in cf["optionValues"]:
                result.append(ov.get("name"))
            break
    return result


def require_login_role(*role):
    """Decorator that requires the use to be logged in and have a particular role"""

    def fn_setup(fn):
        def do_role_check(*args, **kwargs):
            if not is_enabled():
                log.warning(f"BYPASS for {role}")
                return fn(*args, **kwargs)
            roles = get_roles()
            if roles is None:
                session["redirect_to_login_url"] = request.url
                return redirect(url_for("auth.login_user_neon_oauth"))
            # Check for presence of role. Note that shop techs are a special case; leads can do
            # anything that a shop tech is allowed to do.
            # Admins can also do anything.
            for r in role:
                if (
                    r["name"] in roles
                    or (r == Role.SHOP_TECH and Role.SHOP_TECH_LEAD["name"] in roles)
                    or Role.ADMIN["name"] in roles
                ):
                    return fn(*args, **kwargs)

            return Response(
                "Access Denied - if you think this is an error, try going to "
                "https://api.protohaven.org/logout and then log in again.",
                status=401,
            )

        do_role_check.__name__ = fn.__name__
        return do_role_check

    return fn_setup


def am_role(*role):
    """Returns True if the current session is one of the roles provided"""
    return (not is_enabled()) or require_login_role(*role)(lambda: True)() is True

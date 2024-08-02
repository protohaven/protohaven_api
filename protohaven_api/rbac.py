"""Role based access control for logged in users using session data from Neon CRM"""

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


def set_rbac(en):
    """Changes global RBAC enabled state"""
    global enabled  # pylint: disable=global-statement
    enabled = en


def is_enabled():
    """Return whether RBAC is currently enabled"""
    return enabled


@dataclass
class Role:
    """Every Neon user has zero or more roles that can be checked for access"""

    INSTRUCTOR = {"name": "Instructor", "id": "75"}
    BOARD_MEMBER = {"name": "Board Member", "id": "244"}
    STAFF = {"name": "Staff", "id": "245"}
    SHOP_TECH = {"name": "Shop Tech", "id": "238"}
    SHOP_TECH_LEAD = {"name": "Shop Tech Lead", "id": "241"}
    ONBOARDING = {"name": "Onboarding", "id": "240"}
    ADMIN = {"name": "Admin", "id": "239"}


def require_login(fn):
    """Decorator that requires the user to be logged in"""

    def do_login_check(*args, **kwargs):
        if enabled:
            if session.get("neon_id") is None:
                session["redirect_to_login_url"] = request.url
                return redirect(url_for("auth.login_user_neon_oauth"))
        return fn(*args, **kwargs)

    do_login_check.__name__ = fn.__name__
    return do_login_check


def get_roles():
    """Gets all the roles accessible by the incoming request/user.
    The payload and headers are searched for API keys"""
    api_key = request.values.get("api_key", None)
    if not api_key:
        api_key = request.headers.get("X-Protohaven-APIKey", None)
    if api_key is not None:
        roles = get_config()["general"].get("external_access_codes").get(api_key)
        return roles

    neon_acct = session.get("neon_account")
    if neon_acct is None:
        return None
    acct = neon_acct.get("individualAccount") or neon_acct.get("companyAccount")
    if acct is None:
        return None

    result = []
    for cf in acct.get("accountCustomFields", []):
        if cf["name"] == "API server role":
            for ov in cf["optionValues"]:
                result.append(ov.get("name"))
            break
    return result


def require_login_role(role):
    """Decorator that requires the use to be logged in and have a particular role"""

    def fn_setup(fn):
        def do_role_check(*args, **kwargs):
            if not enabled:
                print("BYPASS for ", role)
                return fn(*args, **kwargs)
            roles = get_roles()
            if roles is None:
                session["redirect_to_login_url"] = request.url
                return redirect(url_for("auth.login_user_neon_oauth"))
            if role["name"] in roles:
                return fn(*args, **kwargs)
            return Response(
                "Access Denied - if you think this is an error, try going to "
                "https://api.protohaven.org/logout and then log in again.",
                status=401,
            )

        do_role_check.__name__ = fn.__name__
        return do_role_check

    return fn_setup

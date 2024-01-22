"""Role based access control for logged in users using session data from Neon CRM"""

from dataclasses import dataclass

from flask import redirect, request, session, url_for  # pylint: disable=import-error

from protohaven_api.config import get_config
from protohaven_api.handlers.auth import login_user_neon_oauth


@dataclass
class Role:
    """Every Neon user has zero or more roles that can be checked for access"""

    INSTRUCTOR = {"name": "Instructor", "id": "75"}
    SHOP_TECH = {"name": "Shop Tech", "id": "238"}
    SHOP_TECH_LEAD = {"name": "Shop Tech Lead", "id": "241"}
    ONBOARDING = {"name": "Onboarding", "id": "240"}
    ADMIN = {"name": "Admin", "id": "239"}


def require_login(fn):
    """Decorator that requires the user to be logged in"""

    def do_login_check(*args, **kwargs):
        if session.get("neon_id") is None:
            session["redirect_to_login_url"] = request.url
            return redirect(url_for("auth." + login_user_neon_oauth.__name__))
        return fn(*args, **kwargs)

    do_login_check.__name__ = fn.__name__
    return do_login_check


def get_roles():
    """Gets all the roles accessible by the incoming request/user"""
    if "api_key" in request.values:
        roles = (
            get_config()["general"]
            .get("external_access_codes")
            .get(request.values.get("api_key"))
        )
        print("Request with API key - roles", roles)
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
            roles = get_roles()
            if roles is None:
                session["redirect_to_login_url"] = request.url
                return redirect(url_for("auth." + login_user_neon_oauth.__name__))
            if role["name"] in roles:
                return fn(*args, **kwargs)
            return "Access Denied"

        do_role_check.__name__ = fn.__name__
        return do_role_check

    return fn_setup
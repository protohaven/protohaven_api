"""Role based access control for logged in users using session data from Neon CRM"""

import base64
import logging
from binascii import Error as B64Error
from typing import Any, Callable, Dict, List, Optional

from flask import (  # pylint: disable=import-error
    Response,
    redirect,
    request,
    session,
    url_for,
)

from protohaven_api.config import get_config
from protohaven_api.integrations.models import Member, Role

enabled = True  # pylint: disable=invalid-name

log = logging.getLogger("rbac")


def set_rbac(en: bool) -> None:
    """Changes global RBAC enabled state"""
    global enabled  # pylint: disable=global-statement
    enabled = en


def is_enabled() -> bool:
    """Return whether RBAC is currently enabled"""
    return enabled


def require_login(fn: Callable) -> Callable:
    """Decorator that requires the user to be logged in"""

    def do_login_check(*args: Any, **kwargs: Any) -> Any:
        if is_enabled():
            if session.get("neon_id") is None:
                session["redirect_to_login_url"] = request.url
                return redirect(url_for("auth.login_user_neon_oauth"))
        return fn(*args, **kwargs)

    do_login_check.__name__ = fn.__name__
    return do_login_check


def roles_from_api_key(api_key: Optional[str]) -> Optional[List[str] | str]:
    """Gets roles from the passed API key"""
    if api_key is None:
        return None
    codes = get_config("general/external_access_codes")
    try:
        api_key = base64.b64decode(api_key).decode("utf8").strip()
    except (B64Error, UnicodeDecodeError):
        pass
    return codes.get(api_key)


def get_roles() -> Optional[List[str]]:
    """Gets all the roles accessible by the incoming request/user.
    The payload and headers are searched for API keys"""
    api_key = request.values.get("api_key", None)
    if not api_key:
        api_key = request.headers.get("X-Protohaven-APIKey", None)
    if api_key is not None:
        role = roles_from_api_key(api_key)
        return role if isinstance(role, list) else ([role] if role else None)

    acct = Member.from_neon_fetch(session.get("neon_account"))
    # Check for presence of "individualAccount", as previous session implementations
    # stripped this part of the Neon structure. When this returns none,
    # `require_login_role` redirects to login.
    if acct is None or "individualAccount" not in acct.neon_raw_data:
        return None
    return [v["name"] for v in acct.roles] if acct.roles else []


def require_dev_environment() -> Callable:
    """Require the server to be running a non-prod (i.e. Dev) environment"""

    def fn_setup(fn: Callable) -> Callable:
        def do_dev_check(*args: Any, **kwargs: Any) -> Any:
            if get_config("general/server_mode").lower() == "prod":
                return Response("Access Denied", status=401)
            return fn(*args, **kwargs)

        do_dev_check.__name__ = fn.__name__
        return do_dev_check

    return fn_setup


def require_login_role(
    *role: Dict[str, Any], redirect_to_login: bool = True
) -> Callable:
    """Decorator that requires the use to be logged in and have a particular role"""

    def fn_setup(fn: Callable) -> Callable:
        def do_role_check(*args: Any, **kwargs: Any) -> Any:
            if not is_enabled():
                log.warning(f"BYPASS for {role}")
                return fn(*args, **kwargs)
            roles = get_roles()
            if roles is None:
                if not redirect_to_login:
                    api_base = get_config(
                        "general/external_urls/protohaven_api",
                        "https://api.protohaven.org",
                    )
                    return Response(
                        "Access Denied - you are not logged in. "
                        f"Please visit {api_base}/login to see this content.",
                        status=401,
                    )

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

            api_base = get_config(
                "general/external_urls/protohaven_api", "https://api.protohaven.org"
            )
            return Response(
                "Access Denied - if you think this is an error, try going to "
                f"{api_base}/logout and then log in again.",
                status=401,
            )

        do_role_check.__name__ = fn.__name__
        return do_role_check

    return fn_setup


def am_role(*role: Dict[str, Any]) -> bool:
    """Returns True if the current session is one of the roles provided"""
    return (not is_enabled()) or require_login_role(*role)(lambda: True)() is True


def am_lead_role() -> bool:
    """Returns True if the current session is a priviliged role"""
    return am_role(
        Role.ADMIN,
        Role.SHOP_TECH_LEAD,
        Role.EDUCATION_LEAD,
        Role.STAFF,
        Role.BOARD_MEMBER,
    )

"""User auth handlers for login/logout and metadata"""
import logging

from flask import Blueprint, redirect, request, session

from protohaven_api import oauth
from protohaven_api.integrations import neon

page = Blueprint("auth", __name__, template_folder="templates")

log = logging.getLogger("handlers.auth")


def user_email():
    """Get the logged in user's email"""
    try:
        acct = session.get("neon_account")["individualAccount"]
        return acct["primaryContact"]["email1"]
    except TypeError:
        return None


def user_fullname():
    """Get the logged in user's full name"""
    try:
        acct = session.get("neon_account")["individualAccount"]
        return (
            acct["primaryContact"]["firstName"]
            + " "
            + acct["primaryContact"]["lastName"]
        )
    except TypeError:
        return None


def _redirect_uri():
    return f"{request.url_root}oauth_redirect"


@page.route("/login")
def login_user_neon_oauth():
    """Redirect to Neon CRM oauth server"""
    referrer = request.values.get(
        "referrer"
    )  # Start with GET param override as it's most explicit
    if referrer is None:
        referrer = request.referrer
    if referrer is None:
        referrer = session.get("redirect_to_login_url")
    if referrer is None or referrer == "/login":
        referrer = "/"
    session["login_referrer"] = referrer

    log.info(f"Set login referrer: {session['login_referrer']}")
    return redirect(oauth.prep_request(_redirect_uri()))


@page.route("/logout")
def logout():
    """Log out the curernt user and destroy the session data"""
    session["neon_id"] = None
    session["neon_account"] = None
    return "You've been logged out"


@page.route("/oauth_redirect")
def neon_oauth_redirect():
    """Redirect back to the page the user came from for login"""
    code = request.args.get("code")
    rep = oauth.retrieve_token(_redirect_uri(), code)
    session["neon_id"] = rep.get("access_token")
    session["neon_account"] = neon.fetch_account(session["neon_id"])
    referrer = session.get("login_referrer", "/")
    log.info(f"Login referrer redirect: {referrer}")
    return redirect(referrer)

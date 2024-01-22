"""User auth handlers for login/logout and metadata"""
from flask import Blueprint, redirect, request, session, url_for

from protohaven_api import oauth
from protohaven_api.integrations import neon

page = Blueprint("auth", __name__, template_folder="templates")


def user_email():
    """Get the logged in user's email"""
    acct = session.get("neon_account")["individualAccount"]
    return acct["primaryContact"]["email1"]


def user_fullname():
    """Get the logged in user's full name"""
    acct = session.get("neon_account")["individualAccount"]
    return (
        acct["primaryContact"]["firstName"] + " " + acct["primaryContact"]["lastName"]
    )


@page.route("/login")
def login_user_neon_oauth():
    """Redirect to Neon CRM oauth server"""
    referrer = request.referrer
    if referrer is None:
        referrer = session.get("redirect_to_login_url")
    if referrer is None or referrer == "/login":
        referrer = "/"
    session["login_referrer"] = referrer

    print("Set login referrer:", session["login_referrer"])
    return redirect(oauth.prep_request("https://api.protohaven.org/oauth_redirect"))
    # request.url_root + url_for(neon_oauth_redirect.__name__)))


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
    rep = oauth.retrieve_token(url_for("auth." + neon_oauth_redirect.__name__), code)
    session["neon_id"] = rep.get("access_token")
    session["neon_account"] = neon.fetch_account(session["neon_id"])
    referrer = session.get("login_referrer", "/")
    print("Login referrer redirect:", referrer)
    return redirect(referrer)

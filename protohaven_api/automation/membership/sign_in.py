"""Automation for handling people signing in at the front desk"""

import logging
import datetime
from dateutil import parser as dateparser
from collections import defaultdict
from protohaven_api.config import tznow, tz
from protohaven_api.integrations import airtable, forms, neon, comms
from protohaven_api.warm_cache import WarmCache

from protohaven_api.integrations.data.models import SignInEvent

log = logging.getLogger("automation.membership.sign_in")

def notify_async(content):
    """Sends message to membership automation channel.
    Messages are sent asynchronously and not awaited"""
    return comms.send_discord_message(content, "#membership-automation", blocking=False)


def result_base():
    """Baseline result structure"""
    return {
        "notfound": False,
        "status": False,
        "violations": [],
        "waiver_signed": False,
        "announcements": [],
        "firstname": "member",
    }

# Sign-ins need to be speedy; if it takes more than half a second, folks will
# disengage.
def _cached_member_emails():
    log.debug("Fetching member emails for cache")
    result = defaultdict(list)
    for a in neon.get_active_members(["Email 1", "Company ID"]):
        result[a["Email 1"]].append(a)
    log.debug(f"Fetched {len(result)} emails")
    return dict(result)
member_email_cache = WarmCache(
    _cached_member_emails, datetime.timedelta(hours=12),
    neon.search_member, datetime.timedelta(hours=4)
)


def activate_membership():
    """Activate a member's deferred membership"""
    rep = neon.set_membership_start_date(m["Account ID"], tznow())
    if rep.status_code != 200:
        notify_async(
            f"@Staff: Error {rep.status_code} activating membership for "
            f"#{m['Account ID']}: "
            f"\n{rep.content}\n"
            "Please sync with software folks to diagnose in protohaven_api. "
            "Allowing the member through anyways."
        )
    else:
        neon.update_account_automation_run_status(
            m["Account ID"], "activated"
        )
        msg = comms.Msg.tmpl(
            "membership_activated", fname=m.get("First Name"), target=email
        )
        comms.send_email(msg.subject, msg.body, email, msg.html)

def log_sign_in(data, result, send):
    """Logs a sign-in based on form data. Sends both to Airtable and Google Forms"""
    # Note: setting `purpose` this way tricks the form into not requiring other fields
    assert result["waiver_signed"] is True
    form_data = SignInEvent(
        email=data["email"],
        dependent_info=data["dependent_info"],
        waiver_ack=result["waiver_signed"],
        referrer=data.get("referrer"),
        purpose="I'm a member, just signing in!",
        am_member=(data["person"] == "member"),
    )
    send("Logging sign-in...", 95)

    rep = forms.submit_google_form("signin", form_data.to_google_form())
    log.info(f"Google form submitted, response {rep}")
    rep = airtable.insert_signin(form_data)
    log.info(f"Airtable log submitted, response {rep}")

def get_or_activate_member(email, send):
    """Fetch the candidate account from Neon, preferring active memberships.
    If automation deferred any particular membership, activate it now."""
    # Only select individuals as members, not companies
    mm = [
        m
        for m in member_email_cache[email]
        if m.get("Account ID") != m.get("Company ID")
    ]
    if len(mm) > 1:
        # Warn to membership automation channel that we have an account to deduplicate
        urls = [
            f"  https://protohaven.app.neoncrm.com/admin/accounts/{m['Account ID']}"
            for m in mm
        ]
        notify_async(
            f"Sign-in with {email} returned multiple accounts "
            f"in Neon with same email:\n" + "\n".join(urls) + "\n@Staff: please "
            "[deduplicate](https://protohaven.org/wiki/software/membership_validation)"
        )
        log.info("Notified of multiple accounts")

    m = None
    for m in mm:
        for acf in (m.get("individualAccount") or {}).get("accountCustomFields", []):
            if acf["name"] == "Account Automation Ran" and acf["value"].startswith(
                "deferred"
            ):
                send("Activating membership...", 50)
                # Do this all in a thread so we're not wasting time
                Thread(target=activate_membership, args=(m,), daemon=True)
                return m, True
        if (m.get("Account Current Membership Status") or "").upper() == "ACTIVE":
            return m, False
    return m, False

def handle_side_notifications(m, result):
    """Some accounts are marked as requiring notification when they sign in"""
    if "On Sign In" in (m.get("Notify Board & Staff") or ""):
        log.warning(f"Member sign-in with notify bit set: {m}")
        notify_async(
            f"@Board and @Staff: [{result['firstname']} ({data['email']})]({data['url']}) "
            "just signed in at the front desk with `Notify Board & Staff = On Sign In`. "
            "This indicator suggests immediate followup with this member is needed. "
            "Click the name/email link for notes in Neon CRM."
        )
        log.info("Notified of member-of-interest sign in")
    if result["status"] != "Active":
        notify_async(
            f"[{result['firstname']} ({data['email']})]({data['url']}) just signed in "
            "at the front desk but has a non-Active membership status in Neon: "
            f"status is {result['status']} "
            "([wiki](https://protohaven.org/wiki/software/membership_validation))\n"
        )
        log.info("Notified of non-active member sign in")
    elif len(result["violations"]) > 0:
        notify_async(
            f"[{result['firstname']} ({data['email']})]({data['url']}) just signed in "
            f"at the front desk with violations: `{result['violations']}` "
            "([wiki](https://protohaven.org/wiki/software/membership_validation))\n"
        )
        log.info("Notified of sign-in with violations")

def handle_storage(account_id):
    """Check member for storage violations"""
    for pv in airtable.get_policy_violations():
        if str(pv["fields"].get("Neon ID")) != str(account_id) or pv[
            "fields"
        ].get("Closure"):
            continue
        yield pv

def handle_waiver(account_id, prev_waiver_ack, waiver_ack):
    """Check that the waiver has been acknowledged"""
    return neon.update_waiver_status(
        account_id,
        prev_waiver_ack,
        waiver_ack,
    )

def handle_announcements(last_ack, roles:str, clearances:list, is_active, testing):
    """Handle fetching and display of announcements, plus updating
       acknowledgement date"""
    if last_ack:
        last_ack = dateparser.parse(
            last_ack
        ).astimezone(tz)
    else:
        last_ack = tznow() - datetime.timedelta(30)

    if testing:  # Show testing announcements if ?testing=<anything> in URL
        roles.append("Testing")
    if is_active:
        roles.append("Member")
    result = list(
        airtable.get_announcements_after(
            last_ack, roles, set(clearances)
        )
    )
    # Don't send others' survey responses to the frontend
    for a in result:
        if "Sign-In Survey Responses" in a:
            del a["Sign-In Survey Responses"]
    return result

def as_member(data, send):
    """Sign in as a member (per Neon CRM)"""
    result = result_base()
    send("Searching member database...", 40)
    m = get_or_activate_member(data["email"], send)

    log.info(f"Member {m}")
    if not m:
        result["notfound"] = True
    else:
        # Preferably select the Neon account with active membership.
        # Note that the last `m` remains in context regardless of if we break.
        result["status"] = m.get("Account Current Membership Status", "Unknown")
        result["firstname"] = m.get("First Name")
        data[
            "url"
        ] = f"https://protohaven.app.neoncrm.com/admin/accounts/{m['Account ID']}"

        send("Fetching announcements...", 55)
        handle_announcements(
            last_ack = m.get("Announcements Acknowledged", None),
            roles = [
                r
                for r in (m.get("API server role", "") or "").split("|")  # Can be None
                if r.strip() != ""
            ],
            is_active = result["status"] == "Active",
            testing = data.get("testing"),
            clearances = [] if not m.get("Clearances") else m["Clearances"].split("|"),
        )

        send("Checking storage...", 70)
        result["violations"] = list(handle_storage(m["Account ID"]))

        handle_side_notifications(m, result)

        send("Checking waiver...", 90)
        result["waiver_signed"] = handle_waiver(
            m["Account ID"],
            m.get("Waiver Accepted"), 
            data.get("waiver_ack", False),
        )

    if (result["notfound"] is False and result["waiver_signed"]):
        log_sign_in(data, result, send)
    return result

def as_guest(data, send):
    """Sign in as a guest (no Neon info)"""
    result = result_base()
    result["waiver_signed"] = data.get("waiver_ack", False)
    result["firstname"] = "Guest"
    if data.get("referrer"):
        log_sign_in(data, result, send)
    return result

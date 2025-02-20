"""Automation for handling people signing in at the front desk"""

import datetime
import logging
import multiprocessing as mp
import re
import traceback

from dateutil import parser as dateparser

from protohaven_api.config import get_config, tz, tznow
from protohaven_api.integrations import airtable, comms, forms, neon, neon_base
from protohaven_api.integrations.data.models import SignInEvent

log = logging.getLogger("automation.membership.sign_in")

WAIVER_FMT = "version {version} on {accepted}"
WAIVER_REGEX = r"version (.+?) on (.*)"

# This is the process pool for async execution of long-running
# commands produced during the sign-in process, e.g. membership
# activation, sign in form submission, waiver ack updates.
pool = None  # pylint: disable=invalid-name


def initialize(num_procs=2):
    """Initialize caching & process pools for faster results"""
    log.info("Initializing")
    global pool  # pylint: disable=global-statement
    pool = mp.Pool(num_procs)  # pylint: disable=consider-using-with


def _pool_err_cb(exc):
    log.error(f"Pool process errored: {exc}")


def _apply_async(func, args):
    pool.apply_async(func, args, error_callback=_pool_err_cb)


def notify_async(content):
    """Sends message to membership automation channel.
    Messages are sent asynchronously and not awaited"""
    return comms.send_discord_message(content, "#membership-automation", blocking=False)


def result_base():
    """Baseline result structure"""
    return {
        "neon_id": "",
        "notfound": False,
        "status": "Unknown",
        "violations": [],
        "waiver_signed": False,
        "announcements": [],
        "firstname": "member",
    }


def activate_membership(account_id, fname, email):
    """Activate a member's deferred membership"""
    automation_ran = neon_base.get_custom_field(
        account_id, neon.CustomField.ACCOUNT_AUTOMATION_RAN
    )
    if "deferred" not in automation_ran:
        log.error(f"activate_membership called on non-deferred account {account_id}")
        return

    try:
        membership_id = neon.get_latest_membership_id(account_id)
        if not membership_id:
            raise RuntimeError(
                f"Could not fetch latest membership for account {account_id}"
            )
        log.info(f"Resolved account {account_id} latest membership ID {membership_id}")
        neon.set_membership_date_range(
            membership_id, tznow(), tznow() + datetime.timedelta(days=30)
        )
    except RuntimeError as e:
        notify_async(
            f"@Staff: Error activating membership for "
            f"#{account_id}: "
            f"\n{e}\n"
            "Please sync with software folks to diagnose in protohaven_api. "
            "Allowing the member through anyways."
        )
        return

    neon.update_account_automation_run_status(account_id, "activated")
    msg = comms.Msg.tmpl("membership_activated", fname=fname, target=email)
    comms.send_email(msg.subject, msg.body, [email], msg.html)
    log.info(f"Sent email {msg}")
    notify_async(
        f"Activated deferred membership for {fname} ({email}, "
        f"#{account_id}) as they've just signed in at the front desk"
    )


def submit_forms(form_data):
    """Submits sign in forms to log the event"""
    rep = forms.submit_google_form("signin", form_data.to_google_form())
    log.info(f"Google form submitted, response {rep}")
    rep = airtable.insert_signin(form_data.to_airtable())
    log.info(f"Airtable log submitted, response {rep}")


def log_sign_in(data, result, meta):
    """Logs a sign-in based on form data. Sends both to Airtable and Google Forms"""
    # Note: setting `purpose` this way tricks the form into not requiring other fields
    form_data = SignInEvent(
        email=data["email"],
        dependent_info=data["dependent_info"],
        waiver_ack=result["waiver_signed"],
        referrer=data.get("referrer"),
        purpose="I'm a member, just signing in!",
        am_member=(data["person"] == "member"),
        full_name=meta.get("full_name") or "",
        clearances=meta.get("clearances") or [],
        violations=meta.get("violations") or [],
        status=result.get("status") or "UNKNOWN",
    )
    _apply_async(submit_forms, args=(form_data,))


def get_member_and_activation_state(email):
    """Fetch the candidate account from Neon, preferring active memberships.
    Returns (member info, is_deferred)

    See Onboarding V2 proposal for deferral info at
    https://docs.google.com/document/d/1O8qsvyWyVF7qY0cBQTNUcT60DdfMaLGg8FUDQdciivM/edit?usp=sharing
    """
    # Only select individuals as members, not companies
    mm = neon.cache.get(email.strip(), {})
    mm = [m for m in mm.values() if m.get("Account ID") != m.get("Company ID")]
    if len(mm) == 0:
        return None, False

    if len(mm) > 1:
        # Warn to membership automation channel that we have an account to deduplicate
        urls = [
            f"  [#{m['Account ID']}]"
            + f"(https://protohaven.app.neoncrm.com/admin/accounts/{m['Account ID']}) "
            + f"{m.get('First Name')} {m.get('Last Name')} ({m.get('Email 1')})"
            for m in mm
        ]
        notify_async(
            f"Sign-in with {email} returned multiple accounts "
            f"in Neon with same email:\n" + "\n".join(urls) + "\n@Staff: please "
            "[deduplicate](https://protohaven.org/wiki/software/membership_validation)"
        )
        log.info("Notified of multiple accounts")

    m = None
    # Deferred memberships are returned first, followed by active membership accounts
    # and then inactive ones.
    for m in mm:
        unverified_amp = "AMP" in (m.get("Membership Level") or "") and not m.get(
            "Income Based Rate"
        )
        if (m.get("Account Automation Ran") or "").startswith("deferred"):
            if unverified_amp:
                notify_async(
                    f"Sign-in attempt by {email} with missing `Income Based Rate` "
                    "and/or `Proof of Income` field in Neon "
                    f"CRM.\nThe AMP member is not considered active until their income has been "
                    f"verified.\n@Staff: please meet with the member and verify their income, so "
                    f"they can use the shop."
                )
                log.info("Notified of unverified AMP status")
            else:
                return m, True
        if (m.get("Account Current Membership Status") or "").upper() == "ACTIVE":
            return m, False
    return m, False


def handle_notify_board_and_staff(notify_str, fname, email, url):
    """Some accounts are marked as requiring notification when they sign in"""
    if "On Sign In" in notify_str:
        log.warning(f"Member sign-in with notify bit set: {fname} {email} {url}")
        notify_async(
            f"@Board and @Staff: [{fname} ({email})]({url}) "
            "just signed in at the front desk with `Notify Board & Staff = On Sign In`. "
            "This indicator suggests immediate followup with this member is needed. "
            "Click the name/email link for notes in Neon CRM."
        )
        log.info("Notified of member-of-interest sign in")


def handle_notify_inactive(status_str, fname, email, url):
    """Send a notification if an inactive member tries signing in"""
    if status_str.lower() != "active":
        notify_async(
            f"[{fname} ({email})]({url}) just signed in "
            "at the front desk but has a non-Active membership status in Neon: "
            f"status is {status_str} "
            "([wiki](https://protohaven.org/wiki/software/membership_validation))\n"
        )
        log.info("Notified of non-active member sign in")


def handle_notify_violations(violations, fname, email, url):
    """Send async alert when member signs in with active violations"""
    if len(violations) > 0:
        notify_async(
            f"[{fname} ({email})]({url}) just signed in "
            f"at the front desk with violations: `{violations}` "
            "([wiki](https://protohaven.org/wiki/software/membership_validation))\n"
        )
        log.info("Notified of sign-in with violations")


def handle_waiver(  # pylint: disable=too-many-arguments
    user_id,
    waiver_status,
    ack,
    now=None,
    current_version=None,
    expiration_days=None,
):
    """Update the liability waiver status of a Neon account. Return True if
    the account is bound by the waiver, False otherwise."""

    # Lazy load config entries to prevent parsing errors on init
    now = now or tznow()
    current_version = current_version or get_config("neon/waiver_published_date")
    expiration_days = expiration_days or get_config("neon/waiver_expiration_days")

    if ack:
        # Always overwrite existing signature data since re-acknowledged
        # Done async to reduce login delay
        new_status = WAIVER_FMT.format(
            version=current_version, accepted=now.strftime("%Y-%m-%d")
        )
        _apply_async(neon.set_waiver_status, (user_id, new_status))
        return True

    # Precondition: ack = false
    # Check if signature on file, version is current, and not expired
    last_version = None
    last_signed = None
    if waiver_status is not None:
        match = re.match(WAIVER_REGEX, waiver_status)
        if match is not None:
            log.debug(str(match))
            last_version = match[1]
            last_signed = dateparser.parse(match[2]).astimezone(tz)
    if last_version is None:
        return False
    if last_version != current_version:
        return False
    expiry = last_signed + datetime.timedelta(days=expiration_days)
    return now < expiry


def handle_announcements(last_ack, roles: str, clearances: list, is_active, testing):
    """Handle fetching and display of announcements, plus updating
    acknowledgement date"""
    if last_ack:
        last_ack = dateparser.parse(last_ack).astimezone(tz)
    else:
        last_ack = tznow() - datetime.timedelta(30)

    if testing:  # Show testing announcements if ?testing=<anything> in URL
        roles.append("Testing")
    if is_active:
        roles.append("Member")
    result = list(airtable.cache.announcements_after(last_ack, roles, set(clearances)))
    # Don't send others' survey responses to the frontend
    for a in result:
        if "Sign-In Survey Responses" in a:
            del a["Sign-In Survey Responses"]
    return result


def as_member(data, send):
    """Sign in as a member (per Neon CRM)"""
    result = result_base()
    send("Searching member database...", 40)
    log.info(f"Received sign in request '{data['email']}'")
    m, should_activate = get_member_and_activation_state(data["email"])
    if not m:
        result["notfound"] = True
        log.warning(f"Email {data['email']} not in cached accounts")
        return result

    if should_activate:
        send("Activating membership...", 50)
        log.info(f"Activating membership on account {m['Account ID']}")
        # Do this all in a thread so we're not wasting time
        _apply_async(
            activate_membership, args=(m["Account ID"], m["First Name"], data["email"])
        )
        result["status"] = "Active"  # Assume the activation went through
    else:
        result["status"] = m.get("Account Current Membership Status", "Unknown")

    result["neon_id"] = m.get("Account ID")
    result["firstname"] = m.get("First Name")
    data["url"] = f"https://protohaven.app.neoncrm.com/admin/accounts/{m['Account ID']}"

    meta = {"full_name": f"{m.get('First Name')} {m.get('Last Name')}"}

    try:
        send("Fetching announcements...", 55)
        meta["clearances"] = (
            [] if not m.get("Clearances") else m["Clearances"].split("|")
        )
        result["announcements"] = handle_announcements(
            last_ack=m.get("Announcements Acknowledged", None),
            roles=[
                r
                for r in (m.get("API server role", "") or "").split("|")  # Can be None
                if r.strip() != ""
            ],
            is_active=result["status"] == "Active",
            testing=data.get("testing"),
            clearances=meta["clearances"],
        )
    except Exception:  # pylint: disable=broad-exception-caught
        traceback.print_exc()
        notify_async(
            f"Error fetching announcements (member #{data['email']}) - see log"
        )

    try:
        send("Checking storage...", 70)
        result["violations"] = list(airtable.cache.violations_for(m["Account ID"]))
    except Exception:  # pylint: disable=broad-exception-caught
        traceback.print_exc()
        notify_async(f"Error checking storage (member #{data['email']}) - see log")

    try:
        # These are sent out of band, no need to alert the sign-in member
        handle_notify_board_and_staff(
            m.get("Notify Board & Staff") or "",
            result["firstname"],
            data["email"],
            data["url"],
        )
        handle_notify_inactive(
            str(result["status"]), result["firstname"], data["email"], data["url"]
        )
        handle_notify_violations(
            result["violations"], result["firstname"], data["email"], data["url"]
        )
    except Exception:  # pylint: disable=broad-exception-caught
        traceback.print_exc()
        notify_async(f"Error routing notifications (member #{data['email']}) - see log")

    send("Checking waiver...", 90)
    result["waiver_signed"] = handle_waiver(
        m["Account ID"],
        m.get("Waiver Accepted"),
        data.get("waiver_ack", False),
    )

    # Regardless of the state of the waiver or membership, we want to know when
    # people interact with the sign in kiosk. Always log all sign-in attempts
    # so we have forensics for later.
    send("Logging sign-in...", 95)
    log_sign_in(data, result, meta)
    log.info(f"Sign in result for {data['email']}: {result}")
    return result


def as_guest(data):
    """Sign in as a guest (no Neon info)"""
    result = result_base()
    result["waiver_signed"] = data.get("waiver_ack", False)
    result["firstname"] = "Guest"
    if data.get("referrer"):  # i.e. the survey was completed or passed
        log_sign_in(data, result, {})
    return result

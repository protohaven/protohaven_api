"""Automation for Neon memberships"""
import logging
import random
import string
from functools import lru_cache

from dateutil import parser as dateparser

from protohaven_api.config import get_config, tz
from protohaven_api.integrations import neon
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("membership_automation")

# The "start date" for members' memberships which haven't yet been
# activated via logging in at the front desk
PLACEHOLDER_START_DATE = dateparser.parse("9001-01-01")
DEFAULT_COUPON_AMOUNT = 75  # USD


def generate_coupon_id(n=8):
    """https://stackoverflow.com/a/2257449"""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


@lru_cache(maxsize=1)
def get_sample_classes(coupon_amount):
    """Fetch sample classes within the coupon amount for advertising in the welcome email"""
    sample_classes = []
    for e in neon.fetch_published_upcoming_events(back_days=-1):
        ok, num_remaining = event_is_suggestible(e["id"], coupon_amount)
        if not ok:
            continue
        sample_classes.append(
            {
                "date": dateparser.parse(
                    e["startDate"] + " " + e["startTime"]
                ).astimezone(tz),
                "name": e["name"],
                "remaining": num_remaining,
                "id": e["id"],
            }
        )
        log.info(sample_classes[-1])
        if len(sample_classes) >= 3:
            break
    sample_classes.sort(key=lambda s: s["date"])
    return sample_classes


def event_is_suggestible(event_id, max_price):
    """Return True if the event with `event_id` has open seats within $`max_price`"""
    for t in neon.fetch_tickets(event_id):
        if (
            t["name"] == "Single Registration"
            and t["fee"] > 0
            and t["fee"] <= max_price
            and t["numberRemaining"] > 0
        ):
            return True, t["numberRemaining"]
    return False, 0


def init_membership(  # pylint: disable=too-many-arguments
    account_id,
    email,
    fname,
    coupon_amount=DEFAULT_COUPON_AMOUNT,
    apply=True,
    target=None,
    _id=None,
):
    """
    This method initializes a membership by setting a start date,
    generating a coupon if applicable, and updating the automation run status.

    Action is gated on email configured in in config.yaml
    """
    include_filter = get_config("neon/webhooks/new_membership/include_filter", None)
    if include_filter is not None and email not in include_filter:
        log.info(f"Skipping init (no match in include_filter {include_filter})")
        return None

    log.info(f"Setting #{account_id} start date to {PLACEHOLDER_START_DATE}")

    def _ok(rep, action):
        if rep.status_code != 200:
            log.error(f"Error {rep.status_code} {action}: {rep.content}")
            return False
        return True

    if apply and not _ok(
        neon.set_membership_start_date(account_id, PLACEHOLDER_START_DATE),
        "setting start date",
    ):
        return None

    cid = None
    if coupon_amount > 0:
        cid = generate_coupon_id()
        if apply and not _ok(
            neon.create_coupon_code(cid, coupon_amount), "generating coupon"
        ):
            return None

    if apply and not _ok(
        neon.update_account_automation_run_status(account_id, "deferred"),
        "logging automation run",
    ):
        return None

    if cid:
        return Msg.tmpl(
            "init_membership",
            fname=fname,
            coupon_amount=coupon_amount,
            coupon_code=cid,
            sample_classes=get_sample_classes(coupon_amount),
            target=target,
            id=_id,
        )

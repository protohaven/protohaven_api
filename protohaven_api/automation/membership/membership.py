"""Automation for Neon memberships"""
import datetime
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
DEFERRED_STATUS = "deferred"


def generate_coupon_id(n=8):
    """https://stackoverflow.com/a/2257449"""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


@lru_cache(maxsize=1)
def get_sample_classes(coupon_amount):
    """Fetch sample classes within the coupon amount for advertising in the welcome email"""
    sample_classes = []
    for e in neon.fetch_upcoming_events(back_days=-1):
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


def init_membership(  # pylint: disable=too-many-arguments,inconsistent-return-statements
    account_id,
    membership_id,
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
    assert account_id and membership_id
    include_filter = get_config("neon/webhooks/new_membership/include_filter", None)
    if include_filter is not None and email not in include_filter:
        log.info(
            f"Skipping membership init (no match in include_filter {include_filter})"
        )
        return None

    log.info(f"Setting #{account_id} start date to {PLACEHOLDER_START_DATE}")

    if apply:
        neon.set_membership_date_range(
            membership_id,
            PLACEHOLDER_START_DATE,
            PLACEHOLDER_START_DATE + datetime.timedelta(days=30),
        )

    cid = None
    if coupon_amount > 0:
        cid = generate_coupon_id()
        if apply:
            neon.create_coupon_code(cid, coupon_amount)

    if apply:
        neon.update_account_automation_run_status(account_id, DEFERRED_STATUS)

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

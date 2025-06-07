"""Automation for Neon memberships"""

import datetime
import logging
import random
import string
from functools import lru_cache

from dateutil import parser as dateparser

from protohaven_api.automation.classes import events as eauto
from protohaven_api.config import get_config
from protohaven_api.integrations import airtable, comms, neon
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
    for evt in eauto.fetch_upcoming_events(back_days=-1, fetch_tickets=True):
        num_remaining = evt.has_open_seats_below_price(coupon_amount)
        if not num_remaining:
            continue
        sample_classes.append(
            {
                "date": evt.start_date,
                "name": evt.name,
                "remaining": num_remaining,
                "id": evt.neon_id,
            }
        )
        log.info(sample_classes[-1])
        if len(sample_classes) >= 3:
            break
    sample_classes.sort(key=lambda s: s["date"])
    return sample_classes


def try_cached_coupon(coupon_amount, assignee, apply):
    """Tries to fetch a cached coupon from Airtable, creating one in-situ
    if there is not a valid one of the correct amount present."""
    coupon = airtable.get_next_available_coupon()
    if not coupon:
        comms.send_discord_message(
            "WARNING: no valid coupon available in Airtable requiring"
            "unstable, in-place creation of new one. See Discounts table "
            "in airtable, also `restock_discounts` cronicle job",
            "#finance-automation",
            blocking=False,
        )
        cid = generate_coupon_id()
        if apply:
            neon.create_coupon_code(cid, coupon_amount)
        return cid

    if coupon["fields"]["Amount"] != coupon_amount:
        comms.send_discord_message(
            "WARNING: pricing mismatch on cached discounts requiring "
            "unstable, in-place creation of new one. See Discounts table "
            "in airtable, also `restock_discounts` cronicle job",
            "#finance-automation",
            blocking=False,
        )
        cid = generate_coupon_id()
        if apply:
            neon.create_coupon_code(cid, coupon_amount)
        return cid

    cid = coupon["fields"]["Code"]
    airtable.mark_coupon_assigned(coupon["id"], assignee)
    return cid


def init_membership(  # pylint: disable=too-many-arguments,inconsistent-return-statements
    account_id,
    membership_name,
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
    result = []
    include_filter = get_config("neon/webhooks/new_membership/include_filter") or ""
    if include_filter.strip() != "":
        include_filter = {s.strip().lower() for s in include_filter.split(",")}
        if email.strip().lower() not in include_filter:
            log.info(
                f"Skipping membership init (no match in include_filter: {include_filter})"
            )
            return result

    membership_name_filter = (
        get_config("neon/webhooks/new_membership/excluded_membership_types") or "None"
    )
    if isinstance(membership_name_filter, str) and membership_name_filter != "None":
        membership_name_filter = [
            m.strip().lower() for m in membership_name_filter.split(",")
        ]
        if membership_name.strip().lower() in membership_name_filter:
            log.info(
                f"Skipping membership init for {membership_name} as it's present "
                f"in excluded membershi ptypes: {membership_name_filter}"
            )
            return result

    log.info(f"Setting #{account_id} start date to {PLACEHOLDER_START_DATE}")

    if apply:
        neon.set_membership_date_range(
            membership_id,
            PLACEHOLDER_START_DATE,
            PLACEHOLDER_START_DATE + datetime.timedelta(days=30),
        )

    cid = None
    if coupon_amount > 0:
        cid = try_cached_coupon(coupon_amount, email, apply)

    if apply:
        neon.update_account_automation_run_status(account_id, DEFERRED_STATUS)

    if cid:
        result.append(
            Msg.tmpl(
                "init_membership",
                fname=fname,
                coupon_amount=coupon_amount,
                coupon_code=cid,
                sample_classes=get_sample_classes(coupon_amount),
                target=target,
                id=_id,
            )
        )
    if "AMP" in membership_name:
        result.append(
            Msg.tmpl(
                "verify_income",
                fname=fname,
                target=target,
                id=_id,
            )
        )
    return result

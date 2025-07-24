"""Commands related to financial information and alerting"""

import argparse
import datetime
import logging
import re
from collections import defaultdict

from dateutil import parser as dateparser

from protohaven_api.automation.membership import membership as memauto
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import tz, tznow  # pylint: disable=import-error
from protohaven_api.integrations import (  # pylint: disable=import-error
    airtable,
    neon,
    neon_base,
    sales,
)
from protohaven_api.integrations.comms import Msg
from protohaven_api.integrations.models import Role

log = logging.getLogger("cli.finances")


class Commands:
    """Commands for managing classes in Airtable and Neon"""

    @command()
    def transaction_alerts(self, _1, _2):  # pylint: disable=too-many-locals
        """Send alerts about recent/unresolved transaction issues"""
        log.info("Fetching customer mapping")
        cust_map = sales.get_customer_name_map()
        log.info(f"Fetched {len(cust_map)} customers")
        log.info("Fetching subscription plans")
        sub_plan_map = sales.get_subscription_plan_map()
        log.info(f"Fetched {len(sub_plan_map)} subscription plans")
        assert len(sub_plan_map) > 0  # We should at least have some plans
        now = tznow()
        log.info("Fetching subscriptions")

        unpaid = []
        untaxed = []
        n = 0
        for sub in sales.get_subscriptions()["subscriptions"]:
            if sub["status"] != "ACTIVE":
                continue
            n += 1

            sub_id = sub["id"]
            url = f"https://squareup.com/dashboard/subscriptions-list/{sub_id}"
            log.debug(f"Subscription {sub_id}: {sub}")
            plan, price = sub_plan_map.get(
                sub["plan_variation_id"], (sub["plan_variation_id"], 0)
            )
            if price == 0:
                log.warning(
                    f"Subscription plan not resolved: {sub['plan_variation_id']}"
                )
                continue
            tax_pct = sales.subscription_tax_pct(sub, price)

            log.debug(f"{plan} ${price/100} tax={tax_pct}%")
            cust = cust_map.get(sub["customer_id"], sub["customer_id"])

            if tax_pct < 6.9 or tax_pct > 7.1:
                untaxed.append(f"- {cust} - {plan} - {tax_pct}% tax ([link]({url}))")
                log.info(untaxed[-1])

            charged_through = dateparser.parse(sub["charged_through_date"]).astimezone(
                tz
            )
            if charged_through + datetime.timedelta(days=1) < now:
                unpaid.append(
                    f"- {cust} - {plan} - charged through {charged_through} ([link]({url}))"
                )
                log.info(unpaid[-1])

        log.info(
            f"Processed {n} active subscriptions - {len(unpaid)} unpaid, {len(untaxed)} untaxed"
        )
        result = []
        if len(unpaid) > 0 or len(untaxed) > 0:
            result = [
                Msg.tmpl(
                    "square_validation_action_needed",
                    unpaid=unpaid,
                    untaxed=untaxed,
                    target="#finance-automation",
                )
            ]
        print_yaml(result)
        log.info("Done")

    def _validate_role_membership(self, acct, role):
        roles = acct.roles or []
        if role not in roles:
            has = ",".join([r["name"] for r in roles]) or "none"
            yield f"Needs role {role['name']}, has {has}"
            log.info(f"Missing role {role['name']}: {acct.neon_id}")

    def _validate_addl_family_membership(
        self, household_id, household_paying_member_count
    ):
        if household_paying_member_count <= 0:
            yield (
                "Missing required non-additional paid member in household "
                + f"[#{household_id}](https://protohaven.app.neoncrm.com/"
                + f"np/admin/account/householdDetails.do?householdId={household_id})"
            )
            log.info(
                f"Missing paid family member: #{household_id} has {household_paying_member_count}"
            )

    def _validate_employer_membership(self, company_id, company_member_count):
        if company_member_count < 2:
            yield (
                "Missing required 2+ members in company "
                + f"[#{company_id}](https://protohaven.app.neoncrm.com/admin/accounts/{company_id})"
            )
            log.info(
                f"Missing company members: #{company_id} has {company_member_count}"
            )

    def _validate_amp_membership(self, acct):
        if not acct.income_based_rate:
            yield "Income based rate field not set for AMP membership"
            return

        # We may wish to enable this later, once we have the time to request it of all AMP members
        # if not details.get('income_proof'):
        #    results.append(f"Proof of income not provided for AMP membership")
        ms = acct.latest_membership(active_only=True)
        term_type = re.search(r"(ELI|VLI|LI)", ms.term)
        if term_type is not None:
            ibr_match = {
                "LI": "Low Income",
                "VLI": "Very Low Income",
                "ELI": "Extremely Low Income",
            }.get(term_type[1])
            if ibr_match not in acct.income_based_rate:
                yield (
                    f"Mismatch between Income based rate ({acct.income_based_rate}) "
                    f"and membership type {term_type[1]}"
                )
                log.info(f"AMP mismatch: {acct.neon_id}")

    @command(
        arg(
            "--member_ids",
            help="Space-separated list of Neon IDs to validate",
            type=str,
        ),
    )
    def validate_memberships(self, args, pct):
        """Loops through all accounts and verifies that memberships are correctly set"""
        if args.member_ids is not None:
            args.member_ids = [m.strip() for m in args.member_ids.split(",")]
            log.warning(f"Filtering to member IDs: {args.member_ids}")
        problems = list(self._validate_memberships_internal(args.member_ids, pct))
        if len(problems) > 0:
            print_yaml(
                Msg.tmpl(
                    "membership_validation_problems",
                    problems=problems,
                    target="#membership-automation",
                )
            )
        else:
            print_yaml([])
        log.info(f"Done ({len(problems)} validation problems found)")

    def _validate_memberships_internal(
        self, member_ids=None, pct=None
    ):  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """Implementation of validate_memberships, callable internally"""
        household_paying_member_count = defaultdict(int)
        company_member_count = defaultdict(int)
        member_data = {}
        if pct:
            pct.set_stages(2)
        else:
            pct = {}

        # We search for NOT a bogus email to get all accounts, then collect
        # data before analysis in order to count paying household & company members
        log.info("Collecting members")
        n = 0

        def filter_acct(acct):
            if acct.account_current_membership_status.lower() != "active":
                return False
            if member_ids is not None and str(acct.neon_id) not in member_ids:
                return False
            if acct.is_company():
                return False
            return True

        for i, acct in enumerate(
            neon.search_active_members(
                [
                    "Account Current Membership Status",
                    "Company ID",
                    neon.CustomField.API_SERVER_ROLE,
                ],
                also_fetch=filter_acct,
                fetch_memberships=filter_acct,
            )
        ):
            # This should really pull total from paginated_search
            pct[0] = max(0.5, i / 6000)
            log.info(f"#{acct.neon_id}")
            if not filter_acct(acct):
                continue
            member_data[acct.neon_id] = acct
            for ms in acct.memberships(active_only=True):
                if "Additional" not in ms.level and ms.fee > 0:
                    household_paying_member_count[acct.household_id] += 1
            company_member_count[acct.company_id] += 1
            n += 1

        log.info(
            f"Loaded {len(member_data)} active members, "
            f"{len(household_paying_member_count)} households, "
            f"{len(company_member_count)} companies"
        )

        log.info("Validating members")

        for i, md in enumerate(member_data.items()):
            aid, acct = md
            pct[1] = i / len(member_data)
            if member_ids is not None and aid not in member_ids:
                continue
            for r in self._validate_membership_singleton(
                acct,
                household_paying_member_count.get(acct.household_id, 0),
                company_member_count.get(acct.household_id, 0),
            ):
                yield {
                    "name": acct.name,
                    "result": r,
                    "account_id": acct.neon_id,
                }

    def _validate_membership_singleton(
        self, acct, household_paying_member_count, company_member_count, now=None
    ):  # pylint: disable=too-many-branches
        """Validate membership of a single member"""
        if now is None:
            now = tznow()
        # Filter out future and unsuccessful membership registrations

        num = 0
        am = None
        for am in acct.memberships(active_only=True):
            if (am.start_date and am.start_date > now) or (
                am.status or "SUCCEEDED"
            ) != "SUCCEEDED":
                continue
            num += 1

            if am.fee <= 0 and am.level not in (
                "Shop Tech",
                "Board Member",
                "Staff",
                "Software Developer",
            ):
                if acct.zero_cost_ok_until is None or acct.zero_cost_ok_until < tznow():
                    yield (
                        f"Abnormal zero-cost membership {am.level} "
                        "('Zero Cost OK Until' date missing, expired, invalid, or not YYYY-MM-DD)"
                    )
                    log.info(
                        f"Abnormal zero-cost: {acct.neon_id} - active membership {am.neon_id}"
                    )
            if am.end_date is None or am.end_date == datetime.datetime.max:
                yield f"Membership {am.level} with no end date (infinite duration)"
                log.info(
                    f"Infinite duration: {acct.neon_id} - active membership {am.neon_id}"
                )

        if num > 1:
            yield f"Multiple active memberships: want 1, got {num}"
            log.info(f"Multiple active memberships: {acct.neon_id}")

        if am.level in (
            "General Membership",
            "Weekend Membership",
            "Weeknight Membership",
            "Founding Member",
            "Primary Family Membership",
            "Youth Program",
        ):
            return  # Ignore remaining validations

        if "AMP" in am.level:
            yield from self._validate_amp_membership(acct)
        elif am.level == "Shop Tech":
            yield from self._validate_role_membership(acct, Role.SHOP_TECH)
        elif am.level == "Instructor":
            yield from self._validate_role_membership(acct, Role.INSTRUCTOR)
        elif am.level == "Board Member":
            yield from self._validate_role_membership(acct, Role.BOARD_MEMBER)
        elif am.level == "Software Developer":
            yield from self._validate_role_membership(acct, Role.SOFTWARE_DEV)
        elif am.level == "Staff":
            yield from self._validate_role_membership(acct, Role.STAFF)
        elif am.level == "Additional Family Membership":
            yield from self._validate_addl_family_membership(
                acct.household_id, household_paying_member_count
            )
        elif am.level in (
            "Corporate Membership",
            "Company Membership",
            "Non-Profit Membership",
        ):
            yield from self._validate_employer_membership(
                acct.company_id, company_member_count
            )
        else:
            yield f"Unhandled membership: '{am.level}'"
        return

    def _refresh_role_memberships(
        self, args, summary, role, level, term
    ):  # pylint: disable=too-many-arguments
        now = tznow()
        for acct in neon.search_members_with_role(
            role, also_fetch=True, fetch_memberships=True
        ):
            if len(summary) >= args.limit:
                log.info("Processing limit reached; exiting")
                break
            if args.exclude and str(acct.neon_id) in args.exclude:
                log.info(f"Skipping {acct.neon_id}: in exclusion list")
                continue
            if args.filter and str(acct.neon_id) not in args.filter:
                log.info(f"Skipping {acct.neon_id}: not in filter")
                continue
            if (
                role == Role.SOFTWARE_DEV
                and args.filter_dev
                and str(acct.neon_id) not in args.filter_dev
            ):
                log.info(f"Skipping {acct.neon_id}: not in software dev filter")
                continue

            s = {
                "fname": acct.fname,
                "lname": acct.lname,
                "account_id": acct.neon_id,
                "membership_id": "Not created",
                "new_end": "N/A",
                "membership_type": role["name"],
            }
            log.info(f"Processing {role['name']} #{acct.neon_id}")
            end, autorenew = acct.last_membership_expiration_date()
            if autorenew:
                log.info("Latest membership is autorenewing; skipping")
                continue

            if end is None:
                s["end_date"] = "N/A"
                end = tznow()

            if now + datetime.timedelta(days=args.expiry_threshold) < end:
                continue  # Skip if active membership not expiring soon

            # Precondition: shop tech has no future or active membership
            # expiring later than args.expiry_threshold, and args.apply is set
            s["end_date"] = end.strftime("%Y-%m-%d")
            summary.append(s)
            if not args.apply:
                log.info(f"DRY RUN: create membership for tech #{acct.neon_id}")
                continue

            new_end = end + datetime.timedelta(days=1 + args.duration_days)
            ret = neon.create_zero_cost_membership(
                acct.neon_id,
                end + datetime.timedelta(days=1),
                new_end,
                level=level,
                term=term,
            )
            log.info(f"New membership response: {ret}")
            if ret:
                summary[-1]["membership_id"] = ret["id"]
                summary[-1]["new_end"] = new_end.strftime("%Y-%m-%d")

    @command(
        arg(
            "--filter",
            help="CSV of Neon IDs to restrict processing",
            type=str,
            default="",
        ),
        arg(
            "--exclude",
            help="CSV of Neon IDs to prevent processing",
            default="",
        ),
        arg(
            "--filter_dev",
            help="CSV of Neon IDs to restrict processing for software devs",
            default="",
        ),
        arg(
            "--apply",
            help="When true, actually create new memberships",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--limit",
            help="Refresh a max of this many memberships for this invocation",
            type=int,
            default=3,
        ),
        arg(
            "--duration_days",
            help="How long the new membership should run",
            type=int,
            default=30,
        ),
        arg(
            "--expiry_threshold",
            help="How many days before membership expiration we consider 'renewable'",
            type=int,
            default=4,
        ),
    )
    def refresh_volunteer_memberships(self, args, _):
        """If a volunteer's membership is due to expire soon, create a
        future membership that starts when the previous one ends."""
        if args.filter:
            args.filter = {a.strip() for a in args.filter.split(",")}
            log.info(f"filtering to {args.filter}")
        if args.filter_dev:
            args.filter_dev = {a.strip() for a in args.filter_dev.split(",")}
            log.info(f"filtering software devs to {args.filter_dev}")
        if args.exclude:
            args.exclude = {a.strip() for a in args.exclude.split(",")}
            log.info(f"excluding {args.exclude}")
        summary = []
        log.info("Refreshing shop tech lead memberships...")
        self._refresh_role_memberships(
            args,
            summary,
            Role.SHOP_TECH_LEAD,
            level={"id": 19, "name": "Shop Tech"},
            term={"id": 61, "name": "Shop Tech"},
        )
        log.info("Refreshing shop tech memberships...")
        self._refresh_role_memberships(
            args,
            summary,
            Role.SHOP_TECH,
            level={"id": 19, "name": "Shop Tech"},
            term={"id": 61, "name": "Shop Tech"},
        )
        log.info("Refreshing software dev memberships...")
        self._refresh_role_memberships(
            args,
            summary,
            Role.SOFTWARE_DEV,
            level={"id": 33, "name": "Software Developer"},
            term={"id": 115, "name": "Software Developer"},
        )

        if len(summary) > 0:
            print_yaml(
                Msg.tmpl(
                    "volunteer_refresh_summary",
                    n=len(summary),
                    summary=summary,
                    target="#membership-automation",
                )
            )
        else:
            print_yaml([])

    @command(
        arg(
            "--apply",
            help="When true, actually defer membership start date",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--coupon_amount",
            help="Create a copon with this price and generate comms about it",
            type=int,
            default=memauto.DEFAULT_COUPON_AMOUNT,
        ),
        arg(
            "--max_days_ago",
            help="Only apply to Neon accounts created within this many days from present",
            type=int,
            default=30,
        ),
        arg(
            "--limit",
            help="Initialize a max of this many memberships for this invocation",
            type=int,
            default=3,
        ),
        arg(
            "--filter",
            help="CSV of Neon IDs to restrict processing",
            type=str,
            default="",
        ),
    )
    def init_new_memberships(self, args, _):
        """Perform initialization steps for new members: deferring membership until first
        sign-in and creation of a coupon for their first class.

        See proposal doc:
        https://docs.google.com/document/d/1O8qsvyWyVF7qY0cBQTNUcT60DdfMaLGg8FUDQdciivM/edit
        """
        if args.filter:
            args.filter = {a.strip() for a in args.filter.split(",")}
            log.info(f"Filtering to {args.filter}")

        log.info(
            "Looping through new members to defer their start date and provide coupons"
        )
        result = []
        summary = []
        num = 0
        for m in neon.search_new_members_needing_setup(
            args.max_days_ago, also_fetch=True
        ):
            if args.filter and m.neon_id not in args.filter:
                log.debug(f"Skipping {m.neon_id}: not in filter")
                continue

            mem = m.latest_membership()
            if not mem:
                raise RuntimeError(f"No latest membership for member {m.neon_id}")
            kwargs = {
                "account_id": m.neon_id,
                "membership_name": mem.name,
                "membership_id": mem.neon_id,
                "email": m.email,
                "fname": m.fname,
                "coupon_amount": args.coupon_amount,
                "apply": args.apply,
                "target": m.email,
                "_id": f"init member {m.neon_id}",
            }
            summary.append(kwargs)
            result += memauto.init_membership(**kwargs)
            num += 1
            if num >= args.limit:
                log.info("Max number of initializations reached; stopping")
                break

        result = [r for r in result if r is not None]
        if len(result) > 0:
            result.append(
                Msg.tmpl(
                    "membership_init_summary",
                    summary=summary,
                    target="#membership-automation",
                )
            )
        print_yaml(result)

    @command(
        arg(
            "--apply",
            help="When true, actually create coupons",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--coupon_amount",
            help="Create coupons with this price",
            type=int,
            default=memauto.DEFAULT_COUPON_AMOUNT,
        ),
        arg(
            "--remaining_days_valid",
            help="Coupons expiring fewer than this many days from now are considered unusable",
            type=int,
            default=30,
        ),
        arg(
            "--expiration_days",
            help="Number of days until created coupons expire",
            type=int,
            default=90,
        ),
        arg(
            "--limit",
            help="Max number of coupons to create in this invocation",
            type=int,
            default=5,
        ),
        arg(
            "--target_qty",
            help="Number of coupons to have stockpiled",
            type=int,
            default=50,
        ),
    )
    def restock_discounts(self, args, _):
        """Create a batch of coupons for staging in the Discounts table of
        Airtable. We fetch coupons from this table rather than directly
        from Neon as the Neon process for creating a coupon is much more
        brittle and likely to fail in the moment."""
        now = tznow()
        use_by = now + datetime.timedelta(args.remaining_days_valid)
        cur_qty = airtable.get_num_valid_unassigned_coupons(use_by)
        log.info(f"{cur_qty}/{args.target_qty} available coupons in Airtable")
        if args.target_qty - cur_qty < args.limit:
            log.info("Missing coupons less than --limit, cancelling")
            print_yaml([])
            return

        to_add = [
            memauto.generate_coupon_id()
            for _ in range(min(args.limit, args.target_qty - cur_qty))
        ]
        log.info(f"Creating the following coupons: {to_add}")

        expiry = now + datetime.timedelta(days=args.expiration_days)

        nsesh = None
        if args.apply:
            log.info("Logging into Neon for coupon code creation")
            nsesh = neon_base.NeonOne()

        for cid in to_add:
            if not args.apply:
                log.warning(f"SKIP: create coupon code {cid} and push to airtable")
                continue
            log.info(f"Creating code {cid}...")
            nsesh.create_single_use_abs_event_discount(
                cid, args.coupon_amount, now, expiry
            )
            log.info(f"Coupon code created: {cid}")
            status_code, content = airtable.create_coupon(
                cid,
                args.coupon_amount,
                expiry - datetime.timedelta(args.remaining_days_valid),
                expiry,
            )
            if status_code != 200:
                raise RuntimeError(f"Failed to push coupon to airtable: {content}")
            log.info("...and pushed to airtable")

        print_yaml(
            [
                Msg.tmpl(
                    "discount_creation_summary",
                    num=len(to_add),
                    cur_qty=cur_qty,
                    target_qty=args.target_qty,
                    use_by=use_by.strftime("%Y-%m-%d"),
                    target="#finance-automation",
                )
            ]
        )

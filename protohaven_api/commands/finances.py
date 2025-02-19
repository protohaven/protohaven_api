"""Commands related to financial information and alerting"""

import argparse
import datetime
import logging
import pickle
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
from protohaven_api.rbac import Role

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

    def _validate_role_membership(self, details, role):
        log.debug(f"Validate role membership: {role['name']}")
        results = []
        roles = details.get("roles", [])
        if role["name"] not in roles:
            results.append(f"Needs role {role['name']}, has {roles}")
            log.info(f"Missing role {role['name']}: {details}")
        return results

    def _validate_addl_family_membership(self, details):
        log.debug("Validate additional family membership")
        results = []
        if details["household_paying_member_count"] <= 0:
            results.append(
                f"Missing required non-additional paid member in household #{details['hid']}"
            )
            log.info(f"Missing paid family member: {details}")
        return results

    def _validate_employer_membership(self, details):
        log.debug("Validate employer membership")
        results = []
        if details["company_member_count"] < 2:
            results.append(f"Missing required 2+ members in company #{details['cid']}")
            log.info(f"Missing company members: {details}")
        return results

    def _validate_amp_membership(self, details):
        log.debug("Validate AMP membership")
        results = []
        if not details.get("amp"):
            results.append("Income based rate field not set for AMP membership")
        # We may wish to enable this later, once we have the time to request it of all AMP members
        # if not details.get('income_proof'):
        #    results.append(f"Proof of income not provided for AMP membership")
        if details.get("amp"):
            term_type = re.search(r"(ELI|VLI|LI)", details["term"])
            ibr = details["amp"]
            if term_type is not None:
                ibr_match = {
                    "LI": "Low Income",
                    "VLI": "Very Low Income",
                    "ELI": "Extremely Low Income",
                }.get(term_type[1])
                if ibr_match not in ibr:
                    results.append(
                        f"Mismatch between Income based rate ({ibr}) "
                        f"and membership type {term_type[1]}"
                    )
                    log.info(f"AMP mismatch: {details}")
        return results

    def _suggest_membership(  # pylint: disable=too-many-return-statements
        self, details, num_household, num_addl_household, num_company
    ):
        """Look at role bits, AMP information, and company association to see whether
         the 'best' membership fit is applied.

        Zero-cost memberships matching the highest role are prioritized, followed by
        Company, family, amp, and finally general memberships.
        """
        if details.get("roles"):
            if Role.STAFF["name"] in details["roles"]:
                return ["Staff"]
            if Role.BOARD_MEMBER["name"] in details["roles"]:
                return ["Board Member"]
            if Role.SHOP_TECH_LEAD["name"] in details["roles"]:
                return ["Shop Tech Lead"]
            if Role.SHOP_TECH["name"] in details["roles"]:
                return ["Shop Tech"]
            if (
                Role.INSTRUCTOR["name"] in details["roles"]
                or Role.ONBOARDING["name"] in details["roles"]
            ):
                return ["Instructor"]
        if num_company > 0:
            return ["Non-Profit Membership", "Company Membership"]
        if num_household > 1 and (num_household - num_addl_household) > 0:
            return ["Additional Family Membership"]
        if details.get("amp"):
            return details["amp"]
        return ["General"]

    @command(
        arg(
            "--write_cache",
            help="write intermediate data to a cache file",
            type=str,
        ),
        arg("--read_cache", help="run off pickle cache file", type=str),
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
        problems = list(
            self._validate_memberships_internal(
                args.write_cache, args.read_cache, args.member_ids, pct
            )
        )
        if len(problems) > 0:
            print_yaml(
                Msg.tmpl(
                    "membership_validation_problems",
                    problems=problems,
                    target="#membership-automation",
                )
            )
        log.info(f"Done ({len(problems)} validation problems found)")

    def _validate_memberships_internal(
        self, write_cache=None, read_cache=None, member_ids=None, pct=None
    ):  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """Implementation of validate_memberships, callable internally"""
        household_paying_member_count = defaultdict(int)
        household_num_addl_members = defaultdict(int)
        company_member_count = defaultdict(int)
        member_data = {}
        if pct:
            pct.set_stages(2)
        else:
            pct = {}

        if read_cache:
            with open(read_cache, "rb") as f:
                (
                    member_data,
                    household_paying_member_count,
                    household_num_addl_members,
                    company_member_count,
                ) = pickle.load(f)
            pct[0] = 1.0
        else:
            # We search for NOT a bogus email to get all accounts, then collect
            # data before analysis in order to count paying household & company members
            log.info("Collecting member details")
            n = 0
            for i, mem in enumerate(
                neon.search_member("noreply@protohaven.org", operator="NOT_EQUAL")
            ):
                # This should really pull total from paginated_search
                pct[0] = max(0.5, i / 6000)
                log.info(f"#{mem['Account ID']}")
                if mem["Account Current Membership Status"].lower() != "active":
                    continue
                aid = mem["Account ID"]
                if member_ids is not None and aid not in member_ids:
                    continue
                hid = mem["Household ID"]
                level = mem["Membership Level"]
                acct, is_company = neon_base.fetch_account(mem["Account ID"])
                if acct is None or is_company:
                    continue

                active_memberships = []
                now = tznow().replace(hour=0, minute=0, second=0, microsecond=0)
                has_fee = False
                for ms in neon.fetch_memberships(mem["Account ID"]):
                    start = (
                        dateparser.parse(ms.get("termStartDate")).astimezone(tz)
                        if ms.get("termStartDate")
                        else None
                    )
                    end = (
                        dateparser.parse(ms.get("termEndDate")).astimezone(tz)
                        if ms.get("termEndDate")
                        else None
                    )
                    if not end or end >= now:
                        has_fee = has_fee or ms["fee"] != 0
                        active_memberships.append(
                            {
                                "fee": ms["fee"],
                                "renew": ms["autoRenewal"],
                                "level": ms["membershipLevel"]["name"],
                                "term": ms["membershipTerm"]["name"],
                                "status": ms["status"],
                                "start_date": start,
                                "end_date": end,
                            }
                        )

                details = {
                    "aid": aid,
                    "hid": hid,
                    "name": f"{mem['First Name']} {mem['Last Name']}",
                    "cid": mem["Company ID"],
                    "level": level,
                    "term": mem["Membership Term"],
                    "active_memberships": active_memberships,
                }
                for acf in acct.get("accountCustomFields", []):
                    if acf["name"] == "Zero-Cost Membership OK Until Date":
                        try:
                            details["zero_cost_ok_until"] = dateparser.parse(
                                acf["value"]
                            ).astimezone(tz)
                        except dateparser.ParserError as e:
                            log.error(e)
                            details["zero_cost_ok_until"] = None

                    if acf["name"] == "Income Based Rate":
                        details["amp"] = acf["optionValues"][0]["name"]
                    elif acf["name"] == "Proof of Income":
                        details["income_proof"] = acf
                    elif acf.get("company"):
                        details["company"] = acf
                    elif acf["name"] == "API server role":
                        details["roles"] = [ov["name"] for ov in acf["optionValues"]]
                member_data[aid] = details
                if "Additional" in level:
                    household_num_addl_members[hid] += 1
                elif has_fee:
                    household_paying_member_count[hid] += 1
                company_member_count[mem["Company ID"]] += 1
                n += 1
            if write_cache:
                with open(write_cache, "wb") as f:
                    pickle.dump(
                        (
                            member_data,
                            dict(household_paying_member_count),
                            dict(household_num_addl_members),
                            dict(company_member_count),
                        ),
                        f,
                    )

        log.info(
            f"Loaded details of {len(member_data)} active members, "
            f"{len(household_paying_member_count)} households, "
            f"{len(company_member_count)} companies"
        )

        log.info("Validating member details")

        for i, md in enumerate(member_data.items()):
            aid, details = md
            pct[1] = i / len(member_data)
            if member_ids is not None and aid not in member_ids:
                continue

            # suggested = self._suggest_membership(details,
            #                                     household_member_count.get(details['hid'], 0),
            #                                     household_num_addl_members.get(details['hid'], 0),
            #                                     company_member_count.get(details['cid'], 0))
            # if level not in suggested:
            #     result.append(f"has level {level}, suggest {suggested}")
            details[
                "household_paying_member_count"
            ] = household_paying_member_count.get(details["hid"], 0)
            details["household_num_addl_members"] = household_num_addl_members.get(
                details["hid"], 0
            )
            details["company_member_count"] = company_member_count.get(
                details["cid"], 0
            )
            result = self._validate_membership_singleton(details)
            for r in result:
                yield {
                    "name": details["name"],
                    "result": r,
                    "account_id": details["aid"],
                }

    def _validate_membership_singleton(
        self, details, now=None
    ):  # pylint: disable=too-many-branches
        """Validate membership of a single member"""
        level = details["level"].strip()
        result = []
        if now is None:
            now = tznow()
        # Filter out future and unsuccessful membership registrations

        num = 0
        for am in details["active_memberships"]:
            if (
                am.get("start_date", now) > now
                or am.get("status", "SUCCEEDED") != "SUCCEEDED"
            ):
                continue
            num += 1

            if am["fee"] <= 0 and am["level"] not in (
                "Shop Tech",
                "Board Member",
                "Staff",
            ):
                if (
                    details.get("zero_cost_ok_until") is None
                    or details["zero_cost_ok_until"] < tznow()
                ):
                    result.append(
                        f"Abnormal zero-cost membership {am['level']} "
                        "('Zero Cost OK Until' date missing, expired, invalid, or not YYYY-MM-DD)"
                    )
                    log.info(f"Abnormal zero-cost: {details} - active membership {am}")
            if am.get("end_date") is None:
                result.append(
                    f"Membership {am.get('level')} with no end date (infinite duration)"
                )
                log.info(f"Infinite duration: {details} - active membership {am}")

        if num > 1:
            result.append(
                f"Multiple active memberships: {len(details['active_memberships'])} total"
            )
            log.info(f"Multiple active memberships: {details}")

        if level in (
            "General Membership",
            "Weekend Membership",
            "Weeknight Membership",
            "Founding Member",
            "Primary Family Membership",
            "Youth Program",
        ):
            return result  # Ignore remaining validations

        if "AMP" in level:
            result += self._validate_amp_membership(details)
        elif level == "Shop Tech":
            result += self._validate_role_membership(details, Role.SHOP_TECH)
        elif level == "Instructor":
            result += self._validate_role_membership(details, Role.INSTRUCTOR)
        elif level in "Board Member":
            result += self._validate_role_membership(details, Role.BOARD_MEMBER)
        elif level == "Staff":
            result += self._validate_role_membership(details, Role.STAFF)
        elif level == "Additional Family Membership":
            result += self._validate_addl_family_membership(details)
        elif level in (
            "Corporate Membership",
            "Company Membership",
            "Non-Profit Membership",
        ):
            result += self._validate_employer_membership(details)
        else:
            result += [f"Unhandled membership: '{level}'"]
        return result

    def _last_expiring_membership(self, account_id):
        result = None
        for m in neon.fetch_memberships(account_id):
            if not m.get("termEndDate"):
                log.warning(f"Found etenal membership {m}")
                return dateparser.parse("9000-01-01")
            end = dateparser.parse(m.get("termEndDate")).astimezone(tz)
            if not result or result < end:
                result = end
        return result

    @command(
        arg(
            "--filter",
            help="CSV of Neon IDs to restrict processing",
            type=str,
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
        now = tznow()
        summary = []
        for t in neon.get_members_with_role(Role.SHOP_TECH, []):
            if len(summary) >= args.limit:
                log.info("Processing limit reached; exiting")
                break

            log.info(f"Processing tech {t}")
            end = self._last_expiring_membership(t["Account ID"])
            if now + datetime.timedelta(days=args.expiry_threshold) < end:
                continue  # Skip if active membership not expiring soon

            # Precondition: shop tech has no future or active membership
            # expiring later than args.expiry_threshold, and args.apply is set
            summary.append(
                {
                    "fname": t["First Name"].strip(),
                    "lname": t["Last Name"].strip(),
                    "end_date": end.strftime("%Y-%m-%d"),
                    "account_id": t["Account ID"],
                    "membership_id": "DRYRUN",
                    "new_end": "N/A",
                    "membership_type": "Shop Tech",
                }
            )
            if not args.apply:
                log.info(f"DRY RUN: create membership for tech {t}")
                continue

            new_end = end + datetime.timedelta(days=1 + args.duration_days)
            ret = neon.create_zero_cost_membership(
                t["Account ID"],
                end + datetime.timedelta(days=1),
                new_end,
                level={"id": 19, "name": "Shop Tech"},
                term={"id": 61, "name": "Shop Tech"},
            )
            log.info(f"New membership response: {ret}")
            if ret:
                summary[-1]["membership_id"] = ret["id"]
                summary[-1]["new_end"] = new_end.strftime("%Y-%m-%d")

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
        for m in neon.get_new_members_needing_setup(
            args.max_days_ago, extra_fields=["Email 1"]
        ):
            aid = m["Account ID"]
            if args.filter and aid not in args.filter:
                log.debug(f"Skipping {aid}: not in filter")
                continue

            membership_id = neon.get_latest_membership_id(aid)
            if not membership_id:
                raise RuntimeError(f"No latest membership for member {aid}")
            kwargs = {
                "account_id": aid,
                "membership_id": membership_id,
                "email": m["Email 1"],
                "fname": m["First Name"],
                "coupon_amount": args.coupon_amount,
                "apply": args.apply,
                "target": m["Email 1"],
                "_id": f"init member {aid}",
            }
            summary.append(kwargs)
            result.append(*memauto.init_membership(**kwargs))
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

"""Commands related to financial information and alerting"""
import datetime
import logging

import yaml
from dateutil import parser as dateparser

from protohaven_api.commands.decorator import command
from protohaven_api.config import tz, tznow  # pylint: disable=import-error
from protohaven_api.integrations import sales  # pylint: disable=import-error

log = logging.getLogger("cli.finances")


class Commands:
    """Commands for managing classes in Airtable and Neon"""

    @command()
    def transaction_alerts(self, _):
        """Send alerts about recent/unresolved transaction issues"""
        log.info("Fetching customer mapping")
        cust_map = sales.get_customer_name_map()
        log.info(f"Fetched {len(cust_map)} customers")
        log.info("Fetching subscription plans")
        sub_plan_map = sales.get_subscription_plan_map()
        log.info(f"Fetched {len(sub_plan_map)} subscription plans")
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
            log.debug(f"Subscription {sub_id}")
            plan, price = sub_plan_map.get(
                sub["plan_variation_id"], (sub["plan_variation_id"], 0)
            )
            tax_pct = sales.subscription_tax_pct(sub, price)

            log.debug(f"{plan} ${price/100} tax={tax_pct}%")
            cust = cust_map.get(sub["customer_id"], sub["customer_id"])

            if tax_pct < 6.9 or tax_pct > 7.1:
                untaxed.append(f"- {cust} - {plan} - {tax_pct}% tax, {url}")

            charged_through = dateparser.parse(sub["charged_through_date"]).astimezone(
                tz
            )
            if charged_through + datetime.timedelta(days=1) < now:
                unpaid.append(
                    f"- {cust} - {plan} - charged through {charged_through}, {url}"
                )

        log.info(
            f"Processed {n} active subscriptions - {len(unpaid)} unpaid, {len(untaxed)} untaxed"
        )

        body = ""
        if len(unpaid) > 0:
            body = (
                f"{len(unpaid)} subscriptions active but not caught up on payments:\n"
            )
            body += "\n".join(unpaid)

        if len(untaxed) > 0:
            body += (
                f"\n{len(untaxed)} subscriptions active but do not have 7% sales tax:\n"
            )
            body += "\n".join(untaxed)

        result = []
        if body != "":
            result = [
                {
                    "id": None,
                    "subject": "Square Validation",
                    "body": body,
                    "target": "#finance-automation",
                }
            ]

        print(yaml.dump(result, default_flow_style=False, default_style=""))
        log.info(f"Done")

    @command()
    def neon_failed_membership_txns(self, args):
        """Fetches and prepares comms to mention failed transactions in Neon"""
        raise NotImplementedError()

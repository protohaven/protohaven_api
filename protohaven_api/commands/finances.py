"""Commands related to financial information and alerting"""
import argparse
import logging
import re

import yaml
from dateutil import parser as dateparser
import datetime

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import tz, tznow  # pylint: disable=import-error
from protohaven_api.integrations import neon, sales  # pylint: disable=import-error

log = logging.getLogger("cli.finances")

class Commands:
    """Commands for managing classes in Airtable and Neon"""

    @command()
    def transaction_alerts(self, args):
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

            if sub['status'] != "ACTIVE":
                continue
            n += 1
            #tax_pct = float(sub.get('tax_percentage', "0.0"))
            plan = sub_plan_map.get(sub['plan_variation_id'], sub['plan_variation_id'])
            sub_id = sub['id']
            cust = cust_map.get(sub['customer_id'], sub['customer_id'])

            # For whatever reason, the tax_percentage field doesn't show on all subscriptions,
            # even if those subscriptions have tax. need to dig deeper before enabling this.
            #if tax_pct < 6.9 or tax_pct > 7.1:
            #    untaxed.append(f"- {cust} - {plan} - {tax_pct}% tax ({sub_id})")

            charged_through = dateparser.parse(sub['charged_through_date']).astimezone(tz)
            if charged_through + datetime.timedelta(days=1) < now:
                unpaid.append(f"- {cust} - {plan} - charged through {charged_through} ({sub_id})")
    
        log.info(f"Processed {n} active subscriptions - {len(unpaid)} unpaid")

        body = ""
        if len(unpaid) > 0:
            body = f"{len(unpaid)} subscriptions active but not caught up on payments:\n"
            body += "\n".join(unpaid)

        # if len(untaxed) > 0:
        #     body += f"\n{len(untaxed)} subscriptions active but do not have 7% sales tax:\n"
        #     body += "\n".join(untaxed)

        result = []
        if body != []:
            result = [{"id": None, "subject": "Square Validation", "body": body, "target": "#finance-automation"}]

        print(yaml.dump(result, default_flow_style=False, default_style=""))
        log.info("Done")

    @command()
    def neon_failed_membership_txns(self, args):
        raise NotImplementedError()

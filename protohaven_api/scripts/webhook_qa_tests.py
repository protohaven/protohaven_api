"""Integration tests for varous API webhooks; see docs/qa.md"""
import argparse
import datetime
from base64 import b64encode
from urllib.parse import urlencode

import requests

from protohaven_api.automation.membership import membership as memauto
from protohaven_api.config import get_config, tznow
from protohaven_api.integrations import neon, neon_base
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector


def run_user_clearances_webhook_test(params):
    """Test /usr/clearances webhook by creating, then deleting a clearance that
    resolves to multiple tool clearances."""

    def _do_req(method, data=None):
        """Makes a request against clearances endpoint"""
        url = f"{params.base_url}/user/clearances?"
        rep = requests.request(
            method,
            url + urlencode(data) if data else url,
            headers={"X-Protohaven-APIKey": params.api_key},
            verify=params.verify_ssl,
            allow_redirects=False,
            timeout=30,
        )
        print(rep.status_code, rep.content)
        assert rep.status_code == 200
        return rep

    print("\nChecking clearances for", params.user)
    rep = _do_req("GET", {"emails": params.user})
    codes = set(rep.json()[params.user])
    if "HRB" in codes or "IRN" in codes:
        print("IMW clearance codes already present; removing to setup for test")
        _do_req("DELETE", {"emails": params.user, "codes": "IMW"})
        print("Fetching current clearances for", params.user)
        _do_req("GET", {"emails": params.user})

    print("\nIssuing PATCH for IMW clearance code (resolves to HRB, IRN)")
    _do_req("PATCH", {"emails": params.user, "codes": "IMW"})

    print("\nPatched; getting new info")
    rep = _do_req("GET", {"emails": params.user})
    codes = set(rep.json()[params.user])
    if "HRB" not in codes or "IRN" not in codes:
        raise RuntimeError(
            "HRB, IRN must both be present in the list above; test failed"
        )

    print(
        "\nGood, HRB and IRN are present. Issuing DELETE on the IMW code to remove them again"
    )
    _do_req("DELETE", {"emails": params.user, "codes": "IMW"})

    print("\nDeleted; getting new info")
    rep = _do_req("GET", {"emails": params.user})
    codes = set(rep.json()[params.user])
    if "HRB" in codes or "IRN" in codes:
        raise RuntimeError(
            "HRB, IRN must both be absent in the list above; test failed"
        )
    print("\n**Test passed - HRB and IRN removed successfully.**")


def run_neon_membership_created_callback_test(params):
    """Test the /admin/neon_membership_created_callback by making the test
    user look brand new (no memberships and no Account Automation Ran field
    data) then creating a membership and manually calling the callback.

    Because the created membership is $0, the prod instance ignores the
    created membership. Our manual call lies about the cost of the membership
    so that the callback actually executes and defers the membership."""
    print("\nFetching current user data")
    m = list(neon.search_member(params.user))
    if len(m) == 0:
        raise RuntimeError(f"No Neon account for {params.user}")
    m = m[0]
    print(f"\nFound account #{m['Account ID']}")
    for mem in neon.fetch_memberships(m["Account ID"]):
        mem_id = int(mem["id"])
        assert mem_id and mem_id != 0
        print("Membership", mem)
        print("Deleting membership", mem_id)
        # Note: this is a `neon_base` call and not a function in `neon` as it feels
        # pretty risky to have a "delete this normally archival data" function just
        # laying around to be used elsewhere.
        print(neon_base.delete("api_key2", f"/memberships/{mem_id}"))

    print("\nResetting Automation Ran custom field")
    print(
        neon_base.set_custom_fields(
            m["Account ID"],
            (neon.CustomField.ACCOUNT_AUTOMATION_RAN, ""),
            is_company=False,
        )
    )

    print("\nCreating new membership")
    # Zero fees are normally not auto-deferred on prod; allows us to test
    # without triggering automation on the prod target
    mem = neon.create_zero_cost_membership(
        m["Account ID"], tznow(), tznow() + datetime.timedelta(days=30)
    )
    print(mem)

    print("\nTriggering membership creation callback")
    url = f"{params.base_url}/admin/neon_membership_created_callback"
    rep = requests.post(
        url,
        json={
            "customParameters": {
                "api_key": params.api_key.decode("utf8"),
            },
            "data": {
                "membershipEnrollment": {
                    "accountId": m["Account ID"],
                    "membershipId": mem["id"],
                    "membershipName": "Test Membership",
                    "fee": 115,  # We lie about the fee to trigger execution
                    "enrollmentType": "JOIN",
                },
                "transaction": {
                    "transactionStatus": "SUCCEEDED",
                },
            },
        },
        verify=params.verify_ssl,
        allow_redirects=False,
        timeout=30,
    )
    print(rep.status_code, rep.content)
    assert rep.status_code == 200

    mem = list(neon.fetch_memberships(m["Account ID"]))[0]
    want_date_str = memauto.PLACEHOLDER_START_DATE.strftime("%Y-%m-%d")
    if mem.get("termStartDate") != want_date_str:
        raise RuntimeError(
            f"Term start date incorrect - wanted {want_date_str}, got {mem.get('termStartDate')}"
        )

    automation_ran = neon_base.get_custom_field(
        m["Account ID"], neon.CustomField.ACCOUNT_AUTOMATION_RAN
    )
    print(automation_ran)
    if not automation_ran.startswith(memauto.DEFERRED_STATUS):
        raise RuntimeError(
            f'Account Automation Ran custom field is "{automation_ran}"; '
            f"wanted 'deferred' prefix"
        )
    print(
        "\n**Test passed - account has deferred status set and membership start "
        "date set appropriately**"
    )

    print(f"Cleaning up membership {mem['id']}")
    # Note: this is a `neon_base` call and not a function in `neon` as it feels
    # pretty risky to have a "delete this normally archival data" function just
    # laying around to be used elsewhere.
    print(neon_base.delete("api_key2", f"/memberships/{mem['id']}"))

    print("\nResetting Automation Ran custom field again")
    print(
        neon_base.set_custom_fields(
            m["Account ID"],
            (neon.CustomField.ACCOUNT_AUTOMATION_RAN, ""),
            is_company=False,
        )
    )


def run_get_maintenance_data_webhook_test(params):
    """Test /admin/get_maintenance_data for use with the Bookstack wiki custom widget."""

    def _do_req(method, data):
        """Makes a request against the protohaven_api server"""
        url = f"{params.base_url}/admin/get_maintenance_data?"
        rep = requests.request(
            method,
            url + urlencode(data) if data else url,
            headers={"X-Protohaven-APIKey": params.api_key},
            verify=params.verify_ssl,
            allow_redirects=False,
            timeout=30,
        )
        print(rep.status_code, rep.content)
        assert rep.status_code == 200
        return rep

    test_tool = "DRL"
    print(f"\nGetting maintenance data for {test_tool}")
    rep = _do_req("GET", {"tool_code": test_tool})
    print(rep)

    input("check reply, enter to continue:")
    print("\n**Test passed - maintenance data fetched and looks good.**")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base_url",
        default="https://staging.api.protohaven.org",
        help="base URL to test",
    )
    parser.add_argument(
        "--user",
        default="hello+testnonmember@protohaven.org",
        help="email of user for testing",
    )
    parser.add_argument(
        "--api_key",
        default=None,
        help="base64-encoded API key to use (defaults to what's in config.yaml)",
    )
    parser.add_argument(
        "--verify_ssl",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="if True, prevent web request if SSL cert is invalid",
    )
    parser.add_argument(
        "test",
        default="all",
        help="specific tests to run - one of (new_member, clearance, all)",
    )
    args = parser.parse_args()

    init_connector(Connector)
    if not args.api_key:
        args.api_key = [
            k
            for k, v in get_config("general/external_access_codes").items()
            if "Automation" in v
        ][0]
        args.api_key = b64encode(args.api_key.encode())

    print(f"Test: {args.test}\n\n- target: {args.base_url}\n- user: {args.user}")
    if args.test in ("new_member", "all"):
        print("\nRunning test: new_member")
        print("\n====== THIS AFFECTS PROD DATA =====\n")
        print("- member's entire membership history will be deleted")
        print("- member Account Automation Ran custom field will be cleared")
        print(f"- email will be sent to {args.user}")
        print("\n====== THIS AFFECTS PROD DATA =====\n")
        input("Press enter to continue, or Ctrl+C to quit.")
        run_neon_membership_created_callback_test(args)
    if args.test in ("clearance", "all"):
        print("\nRunning test: clearance")
        print("\n====== THIS AFFECTS PROD DATA =====\n")
        print("- member's HRB, IRN clearances will be revoked")
        print("\n====== THIS AFFECTS PROD DATA =====\n")
        input("Press enter to continue, or Ctrl+C to quit.")
        run_user_clearances_webhook_test(args)
    if args.test in ("maintenance", "all"):
        print("\nRunning test: maintenance")
        input("Press enter to continue, or Ctrl+C to quit.")
        run_get_maintenance_data_webhook_test(args)

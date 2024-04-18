"""Tests for NeonOne integration methods"""
# pylint: skip-file
import datetime
import json

from protohaven_api.config import tznow
from protohaven_api.integrations import neon
from protohaven_api.rbac import Role

TEST_USER = 1234
NOW = tznow()
NOWSTR = NOW.strftime("%Y-%m-%d")
OLDSTR = (NOW - datetime.timedelta(days=90)).strftime("%Y-%m-%d")


def test_update_waiver_status_no_data(mocker):
    """When given no existing waiver data for the user, only return
    true if the user has just acknowledged the waiver"""
    m = mocker.patch.object(neon, "set_waiver_status")
    mocker.patch.object(neon, "cfg")
    assert neon.update_waiver_status(TEST_USER, None, False) is False
    m.assert_not_called()  # No mutation

    # Acknowledgement triggers update
    assert neon.update_waiver_status(TEST_USER, None, True) is True
    m.assert_called()


def test_update_waiver_status_checks_version(mocker):
    """update_waiver_status returns false if the most recent signed
    version of the waiver is not the current version hosted by the server"""
    m = mocker.patch.object(neon, "set_waiver_status")
    mocker.patch.object(neon, "cfg", return_value=3)
    args = [TEST_USER, False]
    kwargs = {"now": NOW, "current_version": NOWSTR}
    assert (
        neon.update_waiver_status(
            args[0], f"version {OLDSTR} on {NOWSTR}", args[1], **kwargs
        )
        is False
    )
    assert (
        neon.update_waiver_status(
            args[0], f"version {NOWSTR} on {NOWSTR}", args[1], **kwargs
        )
        is True
    )
    m.assert_not_called()  # No mutation

    # Acknowledgement triggers update
    assert (
        neon.update_waiver_status(
            args[0], f"version {OLDSTR} on {NOWSTR}", True, **kwargs
        )
        is True
    )
    m.assert_called()


def test_update_waiver_status_checks_expiration(mocker):
    """update_waiver_status returns false if the most recent signed
    waiver data of the user is older than `expiration_days`"""
    m = mocker.patch.object(neon, "set_waiver_status")
    args = [TEST_USER, f"version {OLDSTR} on {OLDSTR}", False]
    kwargs = {"now": NOW, "current_version": OLDSTR}

    assert neon.update_waiver_status(*args, **kwargs, expiration_days=1000) is True
    assert neon.update_waiver_status(*args, **kwargs, expiration_days=30) is False
    m.assert_not_called()  # No mutation

    # Acknowledgement triggers update
    args[-1] = True
    assert neon.update_waiver_status(*args, **kwargs, expiration_days=30) is True
    m.assert_called()


def test_patch_member_role(mocker):
    """Member role patch adds to existing roles"""
    mocker.patch.object(neon, "search_member", return_value={"Account ID": 1324})
    mocker.patch.object(
        neon,
        "fetch_account",
        return_value={
            "individualAccount": {
                "accountCustomFields": [
                    {
                        "id": neon.CUSTOM_FIELD_API_SERVER_ROLE,
                        "optionValues": [{"name": "TEST", "id": "1234"}],
                    }
                ]
            }
        },
    )
    mocker.patch.object(neon, "get_connector")
    mocker.patch.object(neon, "cfg")
    nrq = neon.get_connector().neon_request
    nrq.return_value = mocker.MagicMock(), None
    neon.patch_member_role("a@b.com", Role.INSTRUCTOR, True)
    nrq.assert_called()
    assert json.loads(nrq.call_args.kwargs["body"])["individualAccount"][
        "accountCustomFields"
    ][0]["optionValues"] == [
        {"name": "TEST", "id": "1234"},
        {"name": "Instructor", "id": "75"},
    ]


def test_patch_member_role_rm(mocker):
    """Member role patch preserves remaining roles"""
    mocker.patch.object(neon, "search_member", return_value={"Account ID": 1324})
    mocker.patch.object(
        neon,
        "fetch_account",
        return_value={
            "individualAccount": {
                "accountCustomFields": [
                    {
                        "id": neon.CUSTOM_FIELD_API_SERVER_ROLE,
                        "optionValues": [
                            {"name": "TEST", "id": "1234"},
                            {"name": "Instructor", "id": "75"},
                        ],
                    }
                ]
            }
        },
    )
    mocker.patch.object(neon, "get_connector")
    mocker.patch.object(neon, "cfg")
    nrq = neon.get_connector().neon_request
    nrq.return_value = mocker.MagicMock(), None
    neon.patch_member_role("a@b.com", Role.INSTRUCTOR, False)
    nrq.assert_called()
    assert json.loads(nrq.call_args.kwargs["body"])["individualAccount"][
        "accountCustomFields"
    ][0]["optionValues"] == [{"name": "TEST", "id": "1234"}]


def test_set_tech_custom_fields(mocker):
    mocker.patch.object(
        neon, "fetch_account", return_value={"individualAccount": {"AccountId": 12345}}
    )
    mocker.patch.object(neon, "get_connector")
    mocker.patch.object(neon, "cfg")
    nrq = neon.get_connector().neon_request
    nrq.return_value = mocker.MagicMock(), None

    neon.set_tech_custom_fields("13245", interest="doing things")

    nrq.assert_called()
    assert json.loads(nrq.call_args.kwargs["body"]) == {
        "individualAccount": {
            "accountCustomFields": [{"id": 148, "value": "doing things"}]
        }
    }


def test_set_clearances_some_non_matching(mocker):
    """Ensure that if some clearances don't fully resolve into codes, the remaining
    clearances are still applied"""
    mocker.patch.object(
        neon, "fetch_clearance_codes", return_value=[{"code": "T1", "id": "test_id"}]
    )
    mocker.patch.object(
        neon,
        "fetch_account",
        return_value={"individualAccount": {"id": TEST_USER}},
    )
    mocker.patch.object(neon, "get_connector")
    mocker.patch.object(neon, "cfg")
    nrq = neon.get_connector().neon_request
    nrq.return_value = mocker.MagicMock(), None

    neon.set_clearances(TEST_USER, ["T1", "T2"])
    _, args, kwargs = nrq.mock_calls[0]
    assert kwargs["body"] == json.dumps(
        {
            "individualAccount": {
                "accountCustomFields": [{"id": 75, "optionValues": [{"id": "test_id"}]}]
            }
        }
    )

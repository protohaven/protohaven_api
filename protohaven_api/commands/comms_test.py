"""Test methods for comms-oriented CLI commands"""

# pylint: skip-file
from collections import namedtuple
from unittest.mock import call

import pytest

from protohaven_api.commands import comms as c
from protohaven_api.testing import idfn, mkcli

Tc = namedtuple(
    "Tc",
    "desc,data,args,email,log,discord,intents_notified,scheduled_state",
    defaults=[None for _ in range(7)],
)


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Create CLI fixture"""
    return mkcli(capsys, c)


@pytest.mark.parametrize(
    "tc",
    [
        Tc("None data", None, []),
        Tc("Empty data", [], []),
        Tc(
            "No ID",
            {
                "target": "a@a.com",
                "subject": "Test Subject",
                "body": "Test Body",
            },
            [],
            email=call("Test Subject", "Test Body", ["a@a.com"], False),
            log=call("", "a@a.com", "Test Subject", "Sent"),
        ),
        Tc(
            "With ID",
            {
                "target": "a@a.com",
                "subject": "Test Subject",
                "body": "Test Body",
                "id": "123",
            },
            [],
            email=call("Test Subject", "Test Body", ["a@a.com"], False),
            log=call("123", "a@a.com", "Test Subject", "Sent"),
        ),
        Tc(
            "Discord DM",
            {
                "target": "@discorduser",
                "subject": "Test Subject",
                "body": "Test Body",
                "id": "123",
            },
            [],
            log=call("123", "@discorduser", "Test Subject", "Sent"),
            discord=call("Test Subject\n\nTest Body", "@discorduser"),
        ),
        Tc(
            "Discord Channel",
            {
                "target": "#channel",
                "subject": "Test Subject",
                "body": "Test Body",
                "id": "123",
            },
            [],
            log=call("123", "#channel", "Test Subject", "Sent"),
            discord=call("Test Subject\n\nTest Body", "#channel"),
        ),
        Tc(
            "Side effect cancel",
            {
                "target": "@testuser",
                "subject": "Test Subject",
                "body": "Test Body",
                "side_effect": {"cancel": 12345},
            },
            [],
            log=call("", "@testuser", "Test Subject", "Sent"),
            discord=call("Test Subject\n\nTest Body", "@testuser"),
            scheduled_state=call("12345", scheduled=False),
        ),
        Tc(
            "Intent",
            {
                "target": "#channel",
                "subject": "Test Subject",
                "body": "Test Body",
                "intents": ["a", "b"],
            },
            [],
            intents_notified=call(["a", "b"]),
            log=call("", "#channel", "Test Subject", "Sent"),
            discord=call("Test Subject\n\nTest Body", "#channel"),
        ),
        Tc(
            "No Apply",
            [
                {
                    "target": "#channel",
                    "subject": "Test Subject",
                    "body": "Test Body",
                    "intents": ["a", "b"],
                    "id": "123",
                },
                {
                    "target": "a@b.com",
                    "subject": "Test Subject",
                    "body": "Test Body",
                    "intents": ["a", "b"],
                    "id": "123",
                    "side_effect": {"cancel": 12345},
                },
            ],
            ["--no-apply"],
        ),
    ],
    ids=idfn,
)
def test_send_comms(mocker, tc, cli):
    """Tes comms sent without an id (most basic)"""
    mocker.patch.object(c.comms, "send_discord_message")
    mocker.patch.object(c.comms, "send_email")
    mocker.patch.object(c.airtable, "log_intents_notified")
    mocker.patch.object(c.airtable, "log_comms")
    mocker.patch.object(c.eauto, "set_event_scheduled_state")
    mocker.patch.object(
        c.Commands,
        "_load_comms_data",
        return_value=(
            tc.data if isinstance(tc.data, list) or tc.data is None else [tc.data]
        ),
    )
    cli("send_comms", ["--path", "/asdf/ghsdf", "--confirm", *tc.args])
    for fn, tcall in [
        (c.comms.send_email, tc.email),
        (c.airtable.log_comms, tc.log),
        (c.comms.send_discord_message, tc.discord),
        (c.airtable.log_intents_notified, tc.intents_notified),
        (c.eauto.set_event_scheduled_state, tc.scheduled_state),
    ]:
        if tcall:
            fn.assert_has_calls([tcall])
        else:
            fn.assert_not_called()

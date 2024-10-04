"""Unit tests for comms_templates module"""
import pytest

from protohaven_api.comms_templates import get_all_templates, render


def test_comms_render():
    """Test that comms templates are rendered"""
    assert render("test_template", val="test_body") == (
        "Test Subject",
        "test_body",
        False,
    )


@pytest.mark.parametrize("tmpl", get_all_templates())
def test_templates_handle_subject(tmpl):
    """Test that all templates have a conditional based on `subject` var and no args"""

    # Some templates won't render without some variables defined.
    # Dummy vars are defined here in order for the test to run
    extras = {
        "discord_nick_change_summary": {"n": 1, "m": 1},
        "registrant_class_confirmed": {"signups": 2, "capacity": 4, "days": 2},
        "suspension_started": {"accrued": 5},
        "tech_daily_tasks": {"new_count": 3},
        "violation_ongoing": {"accrued": 5},
        "violation_started": {"fee": 5},
    }
    subject, body, _ = render(tmpl, **extras.get(tmpl, {}))
    assert subject != body


def test_templates_html_detection():
    """Test that templates properly detect html header"""
    _, _, got = render("test_template")
    assert not got
    _, _, got = render("test_html_template")
    assert got

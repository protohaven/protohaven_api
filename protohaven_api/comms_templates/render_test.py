"""Unit tests for comms_templates module"""
from protohaven_api.comms_templates import render


def test_comms_render():
    """Test that comms templates are rendered"""
    assert render("test_template", val="test_body") == ("Test Subject", "test_body")

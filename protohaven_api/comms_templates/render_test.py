from protohaven_api.comms_templates import render

def test_comms_render():
    assert render("test_template", val="test_body") == ("Test Subject", "test_body")


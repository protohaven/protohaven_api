"""Test cronicle integration"""

from protohaven_api.integrations import cronicle as c


def test_exec_details_footer(mocker):
    """Test that exec details footer is sucessfully linked"""
    mocker.patch.object(c, "get_execution_log_link", return_value="TEST_LINK")
    assert "TEST_LINK" in c.exec_details_footer()


def test_exec_details_footer_empty(mocker):
    """Test that the footer is empty when not run in a Cronicle job context"""
    mocker.patch.object(c, "get_execution_log_link", return_value=None)
    assert c.exec_details_footer() == ""

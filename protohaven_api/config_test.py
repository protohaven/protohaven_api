# pylint: skip-file
from protohaven_api import config as c


def test_exec_details_footer(mocker):
    mocker.patch.object(c, "get_execution_log_link", return_value="TEST_LINK")
    assert "TEST_LINK" in c.exec_details_footer()


def test_exec_details_footer_empty(mocker):
    mocker.patch.object(c, "get_execution_log_link", return_value=None)
    assert c.exec_details_footer() == ""

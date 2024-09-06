from protohaven_api import config as c


def test_exec_details_footer(mocker):
    mocker.patch.object(c, "get_execution_log_link", return_value="TEST_LINK")
    assert "TEST_LINK" in exec_details_footer()


def test_exec_details_footer(mocker):
    mocker.patch.object(c, "get_execution_log_link", return_value=None)
    assert exec_details_footer() == ""

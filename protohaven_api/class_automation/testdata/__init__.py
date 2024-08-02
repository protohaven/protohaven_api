"""Simple testing assert to check test output against file contents"""

import os

dirname = os.path.dirname(__file__)


def assert_matches_testdata(got, fname):
    """Raises an exception if `got` does not match the contents of `./{fname}`"""
    with open(f"{dirname}/{fname}", "r", encoding="utf8") as f:
        data = f.read()
    assert data.strip() != ""
    print(got)
    print(data)
    if got.strip() != data.strip():
        raise AssertionError(
            "Test data mismatch:\n\n"
            + f"============== TEST DATA FROM {fname} ==============\n"
            + data
            + "\n"
            + "=============== END TEST DATA FROM {fname} ============\n\n"
            + "=============== TEST RESULT ==================\n"
            + got
            + "\n"
            + "=============== END TEST RESULT ================\n\n"
            + f"You'll need to copy the test result into {dirname}/{fname} "
            + "to pass the test"
        )

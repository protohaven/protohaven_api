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
    assert got.strip() == data.strip()

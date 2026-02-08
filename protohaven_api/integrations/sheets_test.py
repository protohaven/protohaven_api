"""Test of sheets integration module"""

import datetime
import logging
import re
from collections import defaultdict
from collections.abc import Mapping
from typing import Any, List

import pytest
from dateutil import tz as dtz

from protohaven_api.config import get_config, safe_parse_datetime
from protohaven_api.integrations import sheets as s

log = logging.getLogger("integrations.sheets_test")
tz = dtz.gettz("America/New_York")


def a1_to_indexes(a1_notation: str) -> List[int | str | None]:
    """Converts A1 notation into a quadrant
    Args:
        a1_notation: A1 notation of a quadrant of cells in a sheet. Can
        include/exclude rows or columns to imply the entire width/height of the
        sheet. Examples of valid A1 notation include Sheet!A1, A1:B2, B3:200,
        B4:C.
    returns:
        A list with the parsed sheet name, column starting index, row starting
        index, column ending index, and row ending index. All index values are
        inclusive. If a value can't be parsed, None will be returned instead,
        typically implying expanding to the maximum possible range.
    """
    # Slightly cursed regex to extract sheet and columns.
    matches = re.match(
        "(?:([^!]*)!)?([A-Z]+)?([0-9]+)?(?:(?::)([A-Z]+)?([0-9]+)?)?", a1_notation
    )
    if matches:
        return matches.groups()
    raise ValueError(
        "Unable to parse"
        "<Sheet>!<Col1>[<Row1>][![<Col2>][<Row2>]] from"
        f"{a1_notation}"
    )


class FakeResult:
    """A faked result type from the Sheets service."""

    def __init__(self, data):
        self.data = data

    def execute(self):
        """Dummy method"""
        return self

    def get(self, key: str, default_result: Any):  # pylint: disable=unused-argument
        """Returns the matching data, if any.

        Args:
            key: This is a part of the Google generated method signature but is
            ignored.
            default_result: Returned in case data is empty.

        Returns:
            A 2D array of matching data, if any.
        """
        if self.data:
            return self.data
        return default_result


class FakeSheetService:
    """A fake of the Sheets service.

    Queries the provided data via A1 notation and should largely behave like the
    real thing.

    Args:
        data: A map of maps, where the first layer is the spreadsheet name, the second
        the sheet name, and the final value the 2d matrix of data in the sheet.
    """

    def __init__(self, data: Mapping[str, Mapping[str, Mapping[str, List[List[str]]]]]):
        self.data = data

    def spreadsheets(self):
        """Dummy method"""
        return self

    def values(self):
        """Dummy method"""
        return self

    # pylint: disable=invalid-name,redefined-builtin
    def get(self, spreadsheetId="", range="") -> FakeResult:
        """Gets the range from the spreadsheet with ID spreadsheetId.

        Args:
            spreadsheetId: The ID of the spreadsheet to retrieve the data from.
            range: The A1-notation style quadrant of data to return.

        Raises:
            KeyError: If the spreadsheetId doesn't appear in the data passed to
            the constructor.
            ValueError: If the range argument can't be parsed.

        Returns:
            A FakeResult holding the matching data.
        """
        if not spreadsheetId in self.data:
            raise KeyError(f'Spreadsheet "{spreadsheetId}" not in self.data.')
        sheet, col1, row1, col2, row2 = a1_to_indexes(range)
        if not sheet:
            sheet = self.data[spreadsheetId].keys()[0]
        data = self.data[spreadsheetId][sheet]
        if not data:
            return FakeResult([])
        if col1:
            # pylint: disable=consider-using-generator
            col1_n = sum([ord(str.upper(n)) - 65 for n in col1])
            # pylint: enable=consider-using-generator
        else:
            col1_n = 0
        if row1:
            row1_n = int(row1) - 1
        else:
            row1_n = 0
        if col2:
            # pylint: disable=consider-using-generator
            col2_n = (
                sum([ord(str.upper(n)) - 65 for n in col2]) + 1
            )  # pylint: disable=consider-using-generator
            # pylint: enable=consider-using-generator
        else:
            col2_n = len(data[0])
        if row2:
            row2_n = int(row2)
        else:
            row2_n = len(data)
        log.info(
            f"Returning columns {col1_n} through {col2_n} for rows "
            f"{row1_n} through {row2_n}"
        )
        return FakeResult([row[col1_n:col2_n] for row in data[row1_n:row2_n]])

    # pylint: enable=invalid-name,redefined-builtin


def install_fake_sheets_service(
    sheets, mocker, data: Mapping[str, Mapping[str, List[List[str]]]]
):
    """Helper that installs the fake and mocks the credentials calls.

    Args:
        s: The sheets module
        mocker: The mocker class provided to the test case.
        data: Map of maps corresponding to spreadsheets/sheets/data matrix.
    """
    mocker.patch.object(
        sheets.service_account.Credentials, "from_service_account_file", return_value={}
    )

    mocker.patch.object(sheets, "build", return_value=FakeSheetService(data))


def test_get_sheets_range(mocker):
    """Test getting range from sheets."""
    install_fake_sheets_service(
        s, mocker, {"sheet_name": {"Sheet1": [["foo"], ["bar"]]}}
    )

    expected = [["foo"], ["bar"]]

    result = s.get_sheet_range("sheet_name", "Sheet1!A:B")

    assert result == expected


def test_get_sheets_range_fails(mocker):
    """Test getting range from sheets."""
    install_fake_sheets_service(s, mocker, {"sheet_name": {"Sheet1": []}})

    with pytest.raises(RuntimeError):
        s.get_sheet_range("sheet_name", "Sheet1!A:B")


def test_get_instructor_submissions_raw(mocker):
    """Test getting instructor submissions data."""
    data = defaultdict(dict)
    sheet_id = get_config("sheets/ids/instructor_hours")
    now = str(datetime.datetime.now())
    data[sheet_id]["Form Responses 1"] = [["Timestamp", "foo"], [now, "bar"]]
    install_fake_sheets_service(s, mocker, data)

    expected = {"Timestamp": safe_parse_datetime(now), "foo": "bar"}

    for row in s.get_instructor_submissions_raw(0):
        assert row == expected


def test_get_passing_student_clearances(mocker):
    """Test getting student clearance data."""
    data = defaultdict(dict)
    sheet_id = get_config("sheets/ids/instructor_hours")
    now = str(datetime.datetime.now(tz=tz))
    data[sheet_id]["Form Responses 1"] = [
        ["Timestamp", s.PASS_HDR, s.CLEARANCE_HDR, s.TOOLS_HDR],
        [now, "foo@gmail.com", "123:code,456:code", "band_saw:tool,welder:tool"],
    ]
    install_fake_sheets_service(s, mocker, data)

    expected = (
        "foo@gmail.com",
        ["band_saw", "welder"],
        safe_parse_datetime(now),
    )

    for row in s.get_passing_student_clearances(from_row=0):
        assert row == expected


def test_get_sign_ins_between(mocker):
    """Tests retrieving sign-in data between two dates."""
    sheet_id = get_config("sheets/ids/welcome_waiver_form")
    data = defaultdict(dict)
    begin = datetime.datetime(2026, 1, 1, tzinfo=tz)
    end = datetime.datetime(2026, 1, 31, tzinfo=tz)
    before_start = begin - datetime.timedelta(days=1)
    in_range = begin + datetime.timedelta(days=10)
    after_end = end + datetime.timedelta(days=1)
    rows = [[] for _ in range(0, 12199)]
    rows[0] = [
        "Email address (members must use the address from your Neon "
        "Protohaven account)",
        "Timestamp",
        "First Name",
        "Last Name",
    ]
    entries = [
        ["before_start@gmail.com", str(before_start), "before", "start"],
        ["inclusive_start@gmail.com", str(begin), "inclusive", "start"],
        ["middle_range@gmail.com", str(in_range), "middle", "range"],
        ["inclusive_end@gmail.com", str(end), "inclusive", "end"],
        ["after_end@gmail.com", str(after_end), "after", "end"],
    ]
    rows = rows + entries
    data[sheet_id]["Form Responses 1"] = rows

    install_fake_sheets_service(s, mocker, data)
    expected = [
        dict(zip(["email", "timestamp", "first", "last"], entry))
        for entry in entries[1:-1]
    ]
    for entry in expected:
        entry["timestamp"] = safe_parse_datetime(entry["timestamp"])

    for row in s.get_sign_ins_between(begin, end):
        assert row == expected.pop(0)


def test_get_ops_budget_state(mocker):
    """Tests retrieving budget state."""
    sheet_id = get_config("sheets/ids/shop_manager_logbook")
    data = defaultdict(dict)
    data[sheet_id]["Budget Summary"] = [
        [],
        ["Header1", "Value1"],
        ["Header2", "Value2"],
    ]
    install_fake_sheets_service(s, mocker, data)

    expected = {"header1": "value1", "header2": "value2"}

    assert s.get_ops_budget_state() == expected


def test_get_ops_event_log(mocker):
    """Tests getting a range of ops event logs."""
    sheet_id = get_config("sheets/ids/shop_manager_logbook")
    data = defaultdict(dict)
    begin = datetime.datetime(2026, 1, 1, tzinfo=tz)
    end = datetime.datetime(2026, 1, 31, tzinfo=tz)
    before_start = begin - datetime.timedelta(days=1)
    in_range = begin + datetime.timedelta(days=10)
    after_end = end + datetime.timedelta(days=1)
    headers = ["Date", "col1", "col2", "col3", "col4"]
    rows = [headers]
    entries = [
        [str(before_start), "foo", "bar", "biz", "baz"],
        [str(begin), "quux", "quuz", "quuf", "quut"],
        [str(in_range), "alice", "bob", "charlie", "daniel"],
        [str(end), "quick", "brown", "fox", "jumped"],
        [str(after_end), "call", "me", "ishmael", "please"],
    ]
    rows = rows + entries
    data[sheet_id]["Event Log"] = rows

    install_fake_sheets_service(s, mocker, data)
    expected = [dict(zip(headers, entry)) for entry in entries[1:-1]]
    for entry in expected:
        entry["Date"] = safe_parse_datetime(entry["Date"])

    for row in s.get_ops_event_log(begin, end):
        assert row == expected.pop(0)


def test_get_ops_inventory(mocker):
    """Test for the ops inventory method."""
    data = defaultdict(dict)
    sheet_id = get_config("sheets/ids/shop_manager_logbook")
    headers = ["Recorded Qty", "Target Qty", "col1", "col2", "col3", "col4"]
    data[sheet_id]["Inventory"] = [headers, ["1", "2", "foo", "bar", "biz", "baz"]]
    install_fake_sheets_service(s, mocker, data)

    expected = {
        "Recorded Qty": 1,
        "Target Qty": 2,
        "col1": "foo",
        "col2": "bar",
        "col3": "biz",
        "col4": "baz",
    }

    for row in s.get_ops_inventory():
        assert row == expected

"""Read from google spreadsheets"""

import datetime
import io
import logging
import re
import tarfile
from typing import Iterator

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from protohaven_api.config import get_config, safe_parse_datetime
from protohaven_api.integrations.models import ClearanceCodeShort, Email

log = logging.getLogger("integrations.sheets")


def _get_service_client(name: str, version: str):
    """
    The usual credentials.json uses protohaven-cli@
    protohaven-api.iam.gserviceaccount.com service account,
    managed by the `workshop` account.
    This account must have read access for the call to succeed.
    """
    creds = service_account.Credentials.from_service_account_file(
        get_config("sheets/credentials_path"), scopes=get_config("sheets/scopes")
    )
    service = build(name, version, credentials=creds)
    return service


def get_sheet_range(sheet_id, range_name):
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    service = _get_service_client("sheets", "v4")
    # Call the Sheets API
    sheet = service.spreadsheets()  # pylint: disable=no-member
    result = sheet.values().get(spreadsheetId=sheet_id, range=range_name).execute()
    values = result.get("values", [])

    if not values:
        raise RuntimeError("No data found")
    return values


def get_instructor_submissions_raw(from_row=1300):
    """Get log submissions from instructors

    Note: columns up to Neon ID are included
    """
    sheet_id = get_config("sheets/ids/instructor_hours")
    headers = get_sheet_range(sheet_id, "Form Responses 1!A1:N")[0]
    for row in get_sheet_range(sheet_id, f"Form Responses 1!A{from_row}:N"):
        data = dict(zip(headers, row))
        if not data.get("Timestamp"):
            continue
        data["Timestamp"] = safe_parse_datetime(data["Timestamp"])
        yield data


PASS_HDR = "Protohaven emails of each student who PASSED (This should be the email address they used to sign up for the class or for their Protohaven account). If none of them passed, enter N/A."  # pylint: disable=line-too-long
CLEARANCE_HDR = "Which clearance(s) was covered?"
TOOLS_HDR = "Which tools were cleared (if any?)"


def get_passing_student_clearances(
    dt=None, from_row=1300
) -> Iterator[tuple[Email, list[ClearanceCodeShort], datetime.datetime]]:
    """Minimally parse and return instructor submissions after from_row in the sheet.
    Yields a sequence of clearance info for each student that passed a class.
    """
    for sub in get_instructor_submissions_raw(from_row):
        if dt is not None and sub["Timestamp"] < dt:
            continue
        emails = sub.get(PASS_HDR)
        mm = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", emails)
        if not mm:
            log.warning(f"No valid emails parsed from row: {emails}")
        emails = [
            m.replace("(", "").replace(")", "").replace(",", "").strip() for m in mm
        ]

        tool_codes = sub.get(TOOLS_HDR)
        tool_codes = (
            # Handle e.g. "Welding - WGR: Tungsten Grinder" -> "WGR"
            [s.split(":")[0].split(" ")[-1].strip() for s in tool_codes.split(",")]
            if tool_codes
            else None
        )
        for e in emails:
            yield (e.strip().lower(), tool_codes, sub["Timestamp"])


def get_sign_ins_between(start, end):
    """Returns sign-in events between start and end dates. Not very efficient."""
    sheet_id = get_config("sheets/ids/welcome_waiver_form")
    headers = get_sheet_range(sheet_id, "Form Responses 1!A1:D")[0]
    # Remap long header names
    headers = [
        {
            "Email address (members must use the address from your Neon Protohaven account)": "email",  # pylint: disable=line-too-long
            "Timestamp": "timestamp",
            "First Name": "first",
            "Last Name": "last",
        }.get(h, h)
        for h in headers
    ]
    for row in get_sheet_range(sheet_id, "Form Responses 1!A12200:D"):
        data = dict(zip(headers, row))
        t = safe_parse_datetime(data["timestamp"])
        if start <= t <= end:
            data["timestamp"] = t
            yield data


def get_ops_budget_state():
    """Returns ops budgeting state from shop manager logbook"""
    sheet_id = get_config("sheets/ids/shop_manager_logbook")
    headers = [
        h.strip().lower()
        for row in get_sheet_range(sheet_id, "Budget Summary!A2:A")
        for h in row
    ]
    values = [
        v.strip().lower()
        for row in get_sheet_range(sheet_id, "Budget Summary!B2:B")
        for v in row
    ]
    data = dict(zip(headers, values))
    return data


def get_ops_event_log(start=None, end=None):
    """Returns all events logged in the shop manager logbook between start and end dates."""
    sheet_id = get_config("sheets/ids/shop_manager_logbook")
    headers = get_sheet_range(sheet_id, "Event Log!A1:E1")[0]
    for row in get_sheet_range(sheet_id, "Event Log!A2:E"):
        data = dict(zip(headers, row))
        t = safe_parse_datetime(data["Date"])
        if (not start or start <= t) and (not end or t <= end):
            data["Date"] = t
            yield data


def get_ops_inventory():
    """Returns all inventory information in the shop manager logbook"""
    sheet_id = get_config("sheets/ids/shop_manager_logbook")
    headers = get_sheet_range(sheet_id, "Inventory!A1:F1")[0]
    for row in get_sheet_range(sheet_id, "Inventory!A2:F"):
        d = dict(zip(headers, row))
        d["Recorded Qty"] = int(d["Recorded Qty"])
        d["Target Qty"] = int(d["Target Qty"])
        yield d


def _download_sheet(sheets_id: str):
    # create drive api client
    drive = _get_service_client("drive", "v3")
    # pylint: disable=maybe-no-member
    request = drive.files().export_media(
        fileId=sheets_id,
        mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    file = io.BytesIO()
    downloader = MediaIoBaseDownload(file, request)
    done = False
    while done is False:
        _, done = downloader.next_chunk()
    return file


def fetch_sheets_backup(dest: str):
    """Writes a tarball of the sheets found in sheets/ids
    Args:
        dest: the output location for the tarball
    Returns:
        None
    """
    with tarfile.open(dest, "w:gz") as tar:
        for [name, sheets_id] in get_config("sheets/ids").items():
            log.error(name)
            log.error(sheets_id)
            data_stream = _download_sheet(sheets_id)
            content = data_stream.getvalue()
            data_len = len(content)
            info = tarfile.TarInfo(name=f"{name}.xls")
            info.size = data_len
            # We pass the stream back to the beginning before adding
            data_stream.seek(0)
            tar.addfile(tarinfo=info, fileobj=data_stream)

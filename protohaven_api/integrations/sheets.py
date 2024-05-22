"""Read from google spreadsheets"""
import logging

from dateutil import parser as dateparser
from google.oauth2 import service_account
from googleapiclient.discovery import build

from protohaven_api.config import get_config, tz

log = logging.getLogger("integrations.sheets")
cfg = get_config()["sheets"]


def get_sheet_range(sheet_id, range_name):
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    creds = service_account.Credentials.from_service_account_file(
        "credentials.json", scopes=cfg["scopes"]
    )
    service = build("sheets", "v4", credentials=creds)
    # Call the Sheets API
    sheet = service.spreadsheets()  # pylint: disable=no-member
    result = sheet.values().get(spreadsheetId=sheet_id, range=range_name).execute()
    values = result.get("values", [])

    if not values:
        raise RuntimeError("No data found")
    return values


def get_instructor_submissions(from_row=800):
    """Get log submissions from instructors"""
    headers = get_sheet_range(cfg["instructor_hours"], "Form Responses 1!A1:M")[0]
    for row in get_sheet_range(
        cfg["instructor_hours"], f"Form Responses 1!A{from_row}:M"
    ):
        data = dict(zip(headers, row))
        data["Timestamp"] = dateparser.parse(data["Timestamp"])
        yield data


def get_sign_ins_between(start, end):
    """Returns sign-in events between start and end dates. Not very efficient."""
    log.info(cfg["welcome_waiver_form"])
    headers = get_sheet_range(cfg["welcome_waiver_form"], "Form Responses 1!A1:D")[0]
    for row in get_sheet_range(cfg["welcome_waiver_form"], "Form Responses 1!A12200:D"):
        data = dict(zip(headers, row))
        t = dateparser.parse(data["Timestamp"]).astimezone(tz)
        if start <= t <= end:
            data["Timestamp"] = t
            yield data


if __name__ == "__main__":
    for r in get_instructor_submissions(from_row=800):
        log.info(str(r))

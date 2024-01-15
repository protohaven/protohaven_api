"""Read from google spreadsheets"""
import os.path

from dateutil import parser as dateparser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from protohaven_api.config import get_config

# If modifying these scopes, delete the file token.json.


cfg = get_config()["sheets"]


def get_sheet_range(sheet_id, range_name):
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", cfg["scopes"])
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", cfg["scopes"]
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w", encoding="utf-8") as token:
            token.write(creds.to_json())

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


if __name__ == "__main__":
    for r in get_instructor_submissions(from_row=800):
        print(r)

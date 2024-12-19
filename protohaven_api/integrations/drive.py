"""Google drive file upload integration"""
import logging

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from protohaven_api.config import get_config

log = logging.getLogger("integrations.drive")


def _svc():
    """Creates the service"""
    creds = service_account.Credentials.from_service_account_file(
        get_config("drive/credentials_path"), scopes=get_config("drive/scopes")
    )
    return build("drive", "v3", credentials=creds)


def get_drive_map():
    """Return mapping of drive names to IDs using Drive API V3."""
    response = _svc().drives().list().execute()  # pylint: disable=no-member
    print(response)
    return {drive["name"]: drive["id"] for drive in response.get("drives", [])}


def upload_file(src, mimetype, dest, parent_id):
    """Uploads a file to Google Drive on the specified `parent_id`"""
    media = MediaFileUpload(src, mimetype=mimetype, resumable=True)
    file_metadata = {
        "name": str(dest),
        "parents": [parent_id],  # Use the drive ID for a shared drive location
    }

    log.info(f"Uploading {src} to {dest} on gdrive {parent_id}")
    file = (
        _svc()  # pylint: disable=no-member
        .files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True,  # https://stackoverflow.com/a/56468780
        )
        .execute()
    )

    return file.get("id")

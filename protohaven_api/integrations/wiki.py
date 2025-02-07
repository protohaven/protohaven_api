"""Functions for interfacing with Bookstack, hosted at https://wiki.protohaven.org"""

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector


def get_maintenance_data(book_slug):
    """Fetches maintenance information stored in Bookstack as tags"""
    thresh = get_config("bookstack/maintenance/approval_threshold")
    return get_connector().bookstack_request(
        "GET", f"/maintenance_data/{book_slug}?approval_threshold={thresh}"
    )


def fetch_db_backup(dest):
    """Fetches a backup of the postgres DB for the wiki"""
    return get_connector().bookstack_download("/backups/dump_db", dest)


def fetch_files_backup(dest):
    """Fetches an archive of all files uploaded to the wiki"""
    return get_connector().bookstack_download("/backups/dump_files", dest)

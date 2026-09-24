"""Google Drive QA fixture helpers."""

from protohaven_api.integrations import drive
from protohaven_api.qa.base import QAContext


def upload_file(
    ctx: QAContext, src: str, mimetype: str, dest: str
) -> str:
    """Upload a file into the configured QA Drive folder and register cleanup."""
    if not ctx.drive_folder_id:
        raise RuntimeError("QA Drive folder ID is required")
    file_id = drive.upload_file(src, mimetype, dest, ctx.drive_folder_id)
    ctx.cleanup.register(
        f"delete Drive file {file_id}", lambda: drive.delete_file(file_id)
    )
    return file_id

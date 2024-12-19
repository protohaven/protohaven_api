import protohaven_api.integrations.drive as d


def test_get_drive_map(mocker):
    """Test drive name to ID mapping."""
    mock_response = {
        "drives": [
            {"name": "DriveA", "id": "123"},
            {"name": "DriveB", "id": "456"},
        ]
    }
    mock_svc = mocker.patch.object(d, "_svc")
    mock_svc().drives().list().execute.return_value = mock_response

    expected = {"DriveA": "123", "DriveB": "456"}
    got = d.get_drive_map()
    assert got == expected


def test_upload_file(mocker):
    """Test upload_file functionality"""
    mock_media_upload = mocker.patch.object(d, "MediaFileUpload")
    mock_svc = mocker.patch.object(d, "_svc")
    mock_files_create = mock_svc.return_value.files.return_value.create
    mock_files_create.return_value.execute.return_value = {"id": "test_id"}

    src = "path/to/source/file"
    mimetype = "test/mimetype"
    dest = "destination/file"
    parent_id = "parent_id"

    file_id = d.upload_file(src, mimetype, dest, parent_id)

    mock_media_upload.assert_called_once_with(src, mimetype=mimetype, resumable=True)
    mock_svc.assert_called_once()
    mock_files_create.assert_called_once_with(
        body={"name": dest, "parents": [parent_id]},
        media_body=mock_media_upload.return_value,
        fields="id",
        supportsAllDrives=True,
    )
    assert file_id == "test_id"

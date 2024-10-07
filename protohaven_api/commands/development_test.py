import pickle

from protohaven_api.commands import development as dev
from protohaven_api.testing import d


def test_gen_mock_data(mocker, tmp_path):
    for n in (
        "fetch_events",
        "fetch_attendees",
        "fetch_clearance_codes",
        "fetch_memberships",
    ):
        mocker.patch.object(dev.neon, n, return_value=[])
    mocker.patch.object(
        dev.neon, "fetch_account", return_value={"individualAccount": {}}
    )
    mocker.patch.object(dev.airtable, "get_all_records", return_value=[])
    dev.Commands().gen_mock_data(
        ["--path", str(tmp_path / "test.pkl"), "--after", d(0).isoformat()]
    )
    with open(str(tmp_path / "test.pkl"), "rb") as f:
        got = pickle.load(f)
    assert isinstance(got, dict)

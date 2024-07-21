from protohaven_api.integrations.data.loader import mock_data
from dataclasses import dataclass


@dataclass
class DevResponse:
    def __init__(self, data):
        self.status_code = 200
        self.content = json.dumps(data)



def handle(self, mode, base, tbl, rec, suffix, data):
    """Dev handler for airtable web requests"""
    if mode == "GET":
        d = self.data['airtable'][base][tbl]
        return DevResponse({'records': d})

    raise NotImplementedError(
        f"Mock data handler for Airtable request with mode {mode}, baes {base}, tbl {tbl}, rec {rec}, suffix {suffix}, data {data}"
    )

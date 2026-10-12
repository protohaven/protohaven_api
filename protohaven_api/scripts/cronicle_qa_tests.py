"""Compatibility wrapper for Cronicle QA.

Use the CLI command instead:

    python3 -m protohaven_api.cli cronicle_qa --api_key=... --image=...
"""

import sys

from protohaven_api.commands.qa import Commands
from protohaven_api.integrations.cronicle import Progress

if __name__ == "__main__":
    Commands().cronicle_qa(sys.argv[1:], Progress())

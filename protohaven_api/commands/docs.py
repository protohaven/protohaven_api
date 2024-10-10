"""Commands related to documentation"""

import logging

from protohaven_api.automation.docs.docs import validate as validate_docs
from protohaven_api.commands.decorator import command, print_yaml

log = logging.getLogger("cli.docs")


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for managing roles of members"""

    @command()
    def validate_docs(self, _):
        """Go through list of tools in airtable, ensure all of them have
        links to a tool guide and a clearance doc that resolve successfully"""
        result = validate_docs()
        print_yaml([result])

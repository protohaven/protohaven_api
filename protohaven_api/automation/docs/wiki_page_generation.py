"""Autogenerate stub wiki pages to remain consistent with tooling.
This should not have to be run frequently.

It may also require IP whitelisting via support chat from Namecheap, as
they have very restrictive bot ratelimits for accessing hosted services.
"""
import dokuwiki

from protohaven_api.config import get_config

URL = "https://protohaven.org/wiki/lib/exe/xmlrpc.php"
wiki = dokuwiki.DokuWiki(URL, get_config("wiki/user"), get_config("wiki/password"))


def gen_stub_clearance_content(toolname):
    """Formatted stub body for new wiki page"""
    return f"""====== {toolname} Clearance (STUB) ======

{{{{section>tools:clearance_template&noheader&nofooter}}}}

====== Tool Specific Instruction ======

===== Point out the following tool features =====

TODO

===== Identify & mitigate common hazards =====

TODO

===== Allowable Materials =====

TODO

===== Safe Setup/Operation/Cleanup =====

TODO

===== Knowledge and Technique =====

TODO"""


with open("clearancepages.txt", encoding="utf-8") as f:
    data = f.read()

pages = [d.split(", ") for d in data.split("\n") if d.strip() != ""]
for name, url in pages:
    print(name, url)
    print(wiki.pages.set(url, gen_stub_clearance_content(name)))

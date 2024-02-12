"""Autogenerate stub wiki pages to remain consistent with tooling.
This should not have to be run frequently.

It may also require IP whitelisting via support chat from Namecheap, as
they have very restrictive bot ratelimits for accessing hosted services.
"""
import dokuwiki

from protohaven_api.config import get_config

cfg = get_config()["wiki"]

URL = "https://protohaven.org/wiki/lib/exe/xmlrpc.php"
wiki = dokuwiki.DokuWiki(URL, cfg["user"], cfg["password"])


print(wiki.pages.list())
# Pass the credentials to the transport layer.
# client.transport.set_basic_auth(cfg['user'], cfg['password'])

# response = client.dokuwiki.login(cfg['user'], cfg['password'])
# print(client.dokuwiki.getTitle())
# print(client.dokuwiki.getPagelist())

print(wiki.pages.set("test_page", "test_content"))

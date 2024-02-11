import dokuwiki

from protohaven_api.config import get_config

cfg = get_config()["wiki"]

url = f"https://protohaven.org/wiki/lib/exe/xmlrpc.php"
try:
    wiki = dokuwiki.DokuWiki(url, cfg["user"], cfg["password"])
except (DokuWikiError, Exception) as err:
    print("unable to connect: %s" % err)


print(wiki.pages.list())
# Pass the credentials to the transport layer.
# client.transport.set_basic_auth(cfg['user'], cfg['password'])

# response = client.dokuwiki.login(cfg['user'], cfg['password'])
# print(client.dokuwiki.getTitle())
# print(client.dokuwiki.getPagelist())

print(wiki.pages.set("test_page", "test_content"))

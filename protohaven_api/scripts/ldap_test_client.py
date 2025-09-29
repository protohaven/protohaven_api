"""Very basic test client to exercise behavior of ldap_server.py"""

from ldaptor.protocols.ldap import ldapclient, ldapconnector, ldapsyntax
from twisted.internet import defer, reactor


@defer.inlineCallbacks
def example():
    """Runs example LDAP query"""
    serverip = b"127.0.0.1"
    basedn = b"dc=protohaven,dc=org"
    query = b"(cn=*Dav*)"
    c = ldapconnector.LDAPClientCreator(reactor, ldapclient.LDAPClient)
    overrides = {basedn: (serverip, 5001)}
    print("Connecting...")
    client = yield c.connect(basedn, overrides=overrides)
    print("Binding")
    yield client.bind()  # binddn, bindpw)
    print("Bound")
    o = ldapsyntax.LDAPEntry(client, basedn)
    print("Searching")
    results = yield o.search(filterText=query)
    print("Results:")
    for entry in results:
        print(entry.getLDIF())


if __name__ == "__main__":
    print("Setting up")
    df = example()
    df.addErrback(lambda err: err.printTraceback())
    df.addCallback(lambda _: reactor.stop())  # pylint: disable=no-member
    print("Running reactor")
    reactor.run()

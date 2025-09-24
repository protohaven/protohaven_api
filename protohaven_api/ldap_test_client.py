from ldaptor.protocols.ldap import ldapclient, ldapconnector, ldapsyntax
from twisted.internet import defer, reactor


@defer.inlineCallbacks
def example():
    # The following arguments may be also specified as unicode strings
    # but it is recommended to use byte strings for ldaptor objects
    serverip = b'127.0.0.1'
    basedn = b'dc=example,dc=org'
    binddn = b'bob@example.org'
    bindpw = b'secret'
    query = b'(cn=*Malc*)'
    c = ldapconnector.LDAPClientCreator(reactor, ldapclient.LDAPClient)
    overrides = {basedn: (serverip, 5001)}
    print("Connecting...")
    client = yield c.connect(basedn, overrides=overrides)
    print("Binding")
    yield client.bind() #binddn, bindpw)
    print("Bound")
    o = ldapsyntax.LDAPEntry(client, basedn)
    print("Searching")
    results = yield o.search(filterText=query)
    print("Results:")
    for entry in results:
        print(entry.getLDIF())

if __name__ == '__main__':
    print("Setting up")
    df = example()
    df.addErrback(lambda err: err.printTraceback())
    df.addCallback(lambda _: reactor.stop())
    print("Running reactor")
    reactor.run()

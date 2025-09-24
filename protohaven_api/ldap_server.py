"""LDAP Server Implementation"""
import io
import sys

from ldaptor.inmemory import fromLDIFFile
from ldaptor.interfaces import IConnectedLDAPEntry
from ldaptor.protocols.ldap.ldapserver import LDAPServer
from twisted.application import service
from twisted.internet.endpoints import serverFromString
from twisted.internet.protocol import ServerFactory
from twisted.python import log
from twisted.python.components import registerAdapter

LDIF = b"""\
dn: dc=org
dc: org
objectClass: dcObject

dn: dc=example,dc=org
dc: example
objectClass: dcObject
objectClass: organization

dn: ou=people,dc=example,dc=org
objectClass: organizationalUnit
ou: people

dn: cn=bob,ou=people,dc=example,dc=org
cn: bob
gn: Bob
mail: bob@example.org
objectclass: top
objectclass: person
objectClass: inetOrgPerson
sn: Roberts

dn: gn=John+sn=Smith,ou=people, dc=example,dc=org
objectClass: addressbookPerson
gn: John
sn: Smith
telephoneNumber: 555-1234
facsimileTelephoneNumber: 555-1235
description: This is a description that can span multi
 ple lines as long as the non-first lines are inden
 ted in the LDIF.

"""

MALC = """
dn: gn=John+sn=Doe,ou=people,dc=example,dc=org
objectClass: addressbookPerson
cn: Jon Malcovich Doe
gn: John
sn: Doe
street: Back alley
postOfficeBox: 123
postalCode: 54321
postalAddress: Backstreet
st: NY
l: New York City
c: US
"""


class Tree:
    def __init__(self):
        self.current_ldif = LDIF
        self.f = io.BytesIO(self.current_ldif)
        self.db = None
        ld = fromLDIFFile(self.f)
        ld.addCallback(self.ldifRead)

    def ldifRead(self, result): # pylint: disable=invalid-name
        self.f.close()
        self.db = result
    
    def update_ldif(self, new_ldif_data):
        """Update the LDIF data and reload the database"""
        self.current_ldif = new_ldif_data
        # Create a new file handle for the new data
        new_f = io.BytesIO(self.current_ldif)
        ld = fromLDIFFile(new_f)
        
        def handle_result(result):
            new_f.close()
            self.db = result
            return result
            
        ld.addCallback(handle_result)
        return ld


class LDAPServerFactory(ServerFactory):
    protocol = LDAPServer
    debug = True

    def __init__(self, tree):
        self.tree = tree

    @property
    def root(self):
        """Always return the current database root"""
        return self.tree.db

    def buildProtocol(self, _):
        proto = self.protocol()
        proto.debug = self.debug
        proto.factory = self
        return proto


# Global tree instance for external access
tree_instance = None

def get_tree_instance():
    """Get the global tree instance"""
    return tree_instance

def update_server_ldif(new_ldif_data):
    """Update the server's LDIF data"""
    if tree_instance:
        tree_instance.update_ldif(new_ldif_data)
        return True
    return False

if __name__ == "__main__":
    from twisted.internet import reactor
    port = int(sys.argv[1]) if len(sys.argv) == 2 else 8080
    log.startLogging(sys.stderr)
    tree = Tree()
    tree_instance = tree  # Make it accessible globally
    # When the LDAP Server protocol wants to manipulate the DIT, it invokes
    # `root = interfaces.IConnectedLDAPEntry(self.factory)` to get the root
    # of the DIT.  The factory that creates the protocol must therefore
    # be adapted to the IConnectedLDAPEntry interface.
    registerAdapter(lambda x: x.root, LDAPServerFactory, IConnectedLDAPEntry)
    factory = LDAPServerFactory(tree)
    application = service.Application("ldaptor-server")
    myService = service.IServiceCollection(application)
    serverEndpointStr = f"tcp:{port}"
    e = serverFromString(reactor, serverEndpointStr)
    d = e.listen(factory)
    reactor.run()

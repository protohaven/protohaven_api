"""LDAP Server Implementation"""

import io
import sys

from ldaptor.inmemory import fromLDIFFile
from ldaptor.interfaces import IConnectedLDAPEntry
from ldaptor.protocols.ldap.ldapserver import LDAPServer
from twisted.application import service
from twisted.internet import reactor
from twisted.internet.endpoints import serverFromString
from twisted.internet.protocol import ServerFactory
from twisted.python import log
from twisted.python.components import registerAdapter

from protohaven_api.config import get_config
from protohaven_api.integrations import neon
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.integrations.data.dev_connector import DevConnector

server_mode = get_config("general/server_mode").lower()
init_connector(Connector if server_mode == "prod" else DevConnector)

LDIF_BASE = """\
dn: dc=org
dc: org
objectClass: dcObject

dn: dc=protohaven,dc=org
dc: protohaven
objectClass: dcObject
objectClass: organization

dn: ou=people,dc=protohaven,dc=org
objectClass: organizationalUnit
ou: people

dn: ou=groups,dc=protohaven,dc=org
objectClass: organizationalUnit
ou: groups"""


def as_ldif(acct):
    """Converts a Member account to an LDIF text format"""
    data = [
        ("dn", f"uid={acct.neon_id},ou=people,dc=protohaven,dc=org"),
        ("cn", acct.name),
        ("gn", acct.fname),
        ("sn", acct.lname),
        ("uid", acct.neon_id),
    ]
    if acct.email:
        data.append(("mail", acct.email))

    for role in acct.roles or []:
        data.append(("memberOf", f"cn={role['name']},ou=groups,dc=protohaven,dc=org"))

    if acct.account_current_membership_status in ("Active", "Future"):
        data.append(("memberOf", "cn=Members,ou=groups,dc=protohaven,dc=org"))

    data += [
        ("objectClass", "person"),
        ("objectClass", "organizationalPerson"),
        ("objectClass", "inetOrgPerson"),
    ]
    return "\n".join([f"{k}: {v}" for k, v in data])


class Tree:  # pylint: disable=too-few-public-methods
    """Provides directory tree"""

    def __init__(self):
        self.db = None
        self.current_ldif = None

    def update_ldif_from_neon_cache(self):
        """Iterate through the AccountCache and convert all entries to LDIF format"""
        ldif = [LDIF_BASE]
        log.msg("populating members")
        seen_ids = set()
        # Reaching into the warmdict directly isn't great; would be good to improve later
        with neon.cache.mu:
            for accts in neon.cache.cache.values():
                for m in accts.values():
                    if m.neon_id in seen_ids:
                        log.msg(
                            f"ERROR: {m.neon_id} already added to LDAP! "
                            "LDAP `dn` records must be unique; ignoring this account"
                        )
                        continue
                    seen_ids.add(m.neon_id)
                    ldif.append(as_ldif(m))

        # IMPORTANT: Trailing newlines are required for LDIF parsing; throws exception otherwise
        # https://github.com/twisted/ldaptor/blob/60f00e716790397a1196db30186b0d111edb45a3/ldaptor/protocols/ldap/ldifprotocol.py#L130
        built = "\n\n".join(ldif) + "\n\n"
        log.msg("Updating LDIF")
        self.update_ldif(built.encode("utf8"))

    def update_ldif(self, new_ldif_data: bytes):
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

        def handle_err(err):
            err.printDetailedTraceback(file=sys.stderr)

        ld.addErrback(handle_err)


class LDAPServerFactory(ServerFactory):
    """Constructs an LDAP server for use with Twisted"""

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


def main():
    """Runs an LDAP server, populated by Neon data"""

    port = int(sys.argv[1]) if len(sys.argv) == 2 else 8080
    log.startLogging(sys.stderr)
    tree = Tree()

    log.msg("Starting AccountCache")
    neon.cache.on_update_complete = tree.update_ldif_from_neon_cache
    neon.cache.start()

    # When the LDAP Server protocol wants to manipulate the DIT, it invokes
    # `root = interfaces.IConnectedLDAPEntry(self.factory)` to get the root
    # of the DIT.  The factory that creates the protocol must therefore
    # be adapted to the IConnectedLDAPEntry interface.
    registerAdapter(lambda x: x.root, LDAPServerFactory, IConnectedLDAPEntry)
    factory = LDAPServerFactory(tree)
    application = service.Application("ldaptor-server")
    service.IServiceCollection(application)
    e = serverFromString(reactor, f"tcp:{port}")
    e.listen(factory)
    reactor.run()  # pylint: disable=no-member


if __name__ == "__main__":
    main()

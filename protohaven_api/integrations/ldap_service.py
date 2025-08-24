"""LDAP service that provides an LDAP server with account data from Neon CRM for Pocket ID integration."""

import logging
import threading
import time
from typing import Dict, List, Optional, Any

from twisted.internet import reactor, endpoints
from twisted.internet.defer import succeed
from twisted.python import log as twisted_log
from ldaptor.protocols import pureldap
from ldaptor.protocols.ldap.ldapserver import LDAPServer
from ldaptor.inmemory import fromLDIFFile
from ldaptor.interfaces import IConnectedLDAPEntry
from ldaptor import ldapfilter
from ldaptor.ldiftree import LDIFTreeEntry
from ldaptor.protocols.ldap import ldaperrors
from zope.interface import implementer

from protohaven_api.config import get_config
from protohaven_api.integrations import neon
from protohaven_api.integrations.models import Member

log = logging.getLogger("integrations.ldap_service")

# Suppress Twisted's default logging to stdout
twisted_log.startLogging(open('/dev/null', 'w'))


@implementer(IConnectedLDAPEntry)
class NeonLDAPEntry(LDIFTreeEntry):
    """LDAP entry backed by Neon CRM data."""
    
    def __init__(self, dn: str, attributes: Dict[str, List[bytes]], service: 'NeonLDAPService'):
        self.dn = dn
        self.service = service
        # Convert string attributes to bytes for ldaptor
        self._attributes = {}
        for key, values in attributes.items():
            if isinstance(values, list):
                self._attributes[key] = [v.encode('utf-8') if isinstance(v, str) else v for v in values]
            else:
                self._attributes[key] = [values.encode('utf-8') if isinstance(values, str) else values]
    
    def __getitem__(self, key):
        return self._attributes.get(key, [])
    
    def get(self, key, default=None):
        return self._attributes.get(key, default)
    
    def keys(self):
        return self._attributes.keys()
    
    def items(self):
        return self._attributes.items()


class NeonLDAPTree:
    """LDAP directory tree backed by Neon CRM data."""
    
    def __init__(self, service: 'NeonLDAPService'):
        self.service = service
        self.base_dn = service.base_dn
        self.users_dn = service.users_dn
    
    def lookup(self, dn: str) -> Optional[NeonLDAPEntry]:
        """Look up an entry by distinguished name."""
        dn_lower = dn.lower()
        
        # Handle base DN
        if dn_lower == self.base_dn.lower():
            return NeonLDAPEntry(
                self.base_dn,
                {
                    'objectClass': ['dcObject', 'organization'],
                    'dc': ['protohaven'],
                    'o': ['Protohaven']
                },
                self.service
            )
        
        # Handle users OU
        if dn_lower == self.users_dn.lower():
            return NeonLDAPEntry(
                self.users_dn,
                {
                    'objectClass': ['organizationalUnit'],
                    'ou': ['users']
                },
                self.service
            )
        
        # Handle user entries
        if dn_lower.startswith('uid=') and dn_lower.endswith(f',{self.users_dn.lower()}'):
            uid = dn.split(',')[0].split('=')[1]
            member = neon.cache.by_neon_id.get(uid)
            if member and self._is_active_member(member):
                attributes = self.service._member_to_ldap_entry(member)
                return NeonLDAPEntry(dn, attributes, self.service)
        
        return None
    
    def _is_active_member(self, member: Member) -> bool:
        """Check if member is active."""
        return (
            hasattr(member, "account_current_membership_status")
            and member.account_current_membership_status == "Active"
            and member.email
        )
    
    def search(self, base_dn: str, scope: int, filter_obj, attributes: List[str] = None) -> List[NeonLDAPEntry]:
        """Search for entries matching the criteria."""
        results = []
        base_dn_lower = base_dn.lower()
        
        # Base object search
        if scope == pureldap.LDAP_SCOPE_baseObject:
            entry = self.lookup(base_dn)
            if entry and self._matches_filter(entry, filter_obj):
                results.append(entry)
        
        # One level search
        elif scope == pureldap.LDAP_SCOPE_singleLevel:
            if base_dn_lower == self.base_dn.lower():
                # Return users OU
                ou_entry = self.lookup(self.users_dn)
                if ou_entry and self._matches_filter(ou_entry, filter_obj):
                    results.append(ou_entry)
            
            elif base_dn_lower == self.users_dn.lower():
                # Return all active members
                active_members = self._get_active_members()
                for member in active_members.values():
                    attributes_dict = self.service._member_to_ldap_entry(member)
                    dn = f"uid={attributes_dict['uid'][0]},{self.users_dn}"
                    entry = NeonLDAPEntry(dn, attributes_dict, self.service)
                    if self._matches_filter(entry, filter_obj):
                        results.append(entry)
        
        # Subtree search
        elif scope == pureldap.LDAP_SCOPE_wholeSubtree:
            # Include base entry if it matches
            base_entry = self.lookup(base_dn)
            if base_entry and self._matches_filter(base_entry, filter_obj):
                results.append(base_entry)
            
            # Include all descendants
            if base_dn_lower == self.base_dn.lower() or base_dn_lower == self.users_dn.lower():
                # Include users OU if searching from base
                if base_dn_lower == self.base_dn.lower():
                    ou_entry = self.lookup(self.users_dn)
                    if ou_entry and self._matches_filter(ou_entry, filter_obj):
                        results.append(ou_entry)
                
                # Include all active members
                active_members = self._get_active_members()
                for member in active_members.values():
                    attributes_dict = self.service._member_to_ldap_entry(member)
                    dn = f"uid={attributes_dict['uid'][0]},{self.users_dn}"
                    entry = NeonLDAPEntry(dn, attributes_dict, self.service)
                    if self._matches_filter(entry, filter_obj):
                        results.append(entry)
        
        log.info(f"LDAP search base={base_dn} scope={scope} returned {len(results)} results")
        return results
    
    def _get_active_members(self) -> Dict[str, Member]:
        """Get all active members from Neon cache."""
        active_members = {}
        for email_accounts in neon.cache.values():
            if isinstance(email_accounts, dict):
                for member in email_accounts.values():
                    if self._is_active_member(member):
                        active_members[member.email.lower()] = member
        return active_members
    
    def _matches_filter(self, entry: NeonLDAPEntry, filter_obj) -> bool:
        """Check if entry matches the LDAP filter."""
        if filter_obj is None:
            return True
        
        # Simple filter matching - extend as needed
        try:
            return ldapfilter.matches(filter_obj, entry._attributes)
        except Exception as e:
            log.warning(f"Filter matching error: {e}")
            return True  # Default to include if filter parsing fails


class NeonLDAPServer(LDAPServer):
    """LDAP server that serves Neon CRM member data."""
    
    def __init__(self, service: 'NeonLDAPService'):
        self.service = service
        self.tree = NeonLDAPTree(service)
    
    def getRootDSE(self, request, reply):
        """Return root DSE information."""
        root_dse = NeonLDAPEntry(
            "",
            {
                'objectClass': ['top'],
                'supportedLDAPVersion': ['3'],
                'namingContexts': [self.service.base_dn],
                'supportedControl': [],
                'supportedExtension': [],
                'vendorName': ['Protohaven LDAP Service'],
                'vendorVersion': ['1.0.0']
            },
            self.service
        )
        
        return succeed(root_dse)
    
    def handle_LDAPBindRequest(self, request, controls, reply):
        """Handle LDAP bind requests."""
        # Simple bind - accept all binds for now
        if request.dn == '' and request.auth == '':
            # Anonymous bind
            reply(pureldap.LDAPBindResponse(resultCode=0))
        else:
            # Simple authentication - in production, integrate with actual auth
            log.warning(f"Bind attempt for DN: {request.dn}")
            reply(pureldap.LDAPBindResponse(resultCode=0))  # Accept all for now
    
    def handle_LDAPSearchRequest(self, request, controls, reply):
        """Handle LDAP search requests."""
        try:
            base_dn = str(request.baseObject)
            scope = request.scope
            filter_obj = request.filter
            attributes = [str(attr) for attr in request.attributes] if request.attributes else None
            
            log.info(f"LDAP search: base={base_dn}, scope={scope}, filter={filter_obj}")
            
            # Perform search
            results = self.tree.search(base_dn, scope, filter_obj, attributes)
            
            # Send search result entries
            for entry in results:
                # Filter attributes if requested
                entry_attributes = entry._attributes
                if attributes and '*' not in attributes:
                    entry_attributes = {k: v for k, v in entry_attributes.items() if k in attributes}
                
                search_result = pureldap.LDAPSearchResultEntry(
                    objectName=entry.dn,
                    attributes=[(k, v) for k, v in entry_attributes.items()]
                )
                reply(search_result)
            
            # Send search result done
            reply(pureldap.LDAPSearchResultDone(resultCode=0))
            
        except Exception as e:
            log.error(f"Search error: {e}")
            reply(pureldap.LDAPSearchResultDone(resultCode=1, errorMessage=str(e)))


class NeonLDAPService:
    """LDAP service that provides an LDAP server with Neon CRM member data."""
    
    def __init__(self, host: str, port: int, base_dn: str):
        self.host = host
        self.port = port
        self.base_dn = base_dn
        self.users_dn = f"ou=users,{base_dn}"
        self.server_thread = None
        self.running = False
        log.info(f"Initializing LDAP service on {host}:{port} with base DN: {base_dn}")
    
    def _member_to_ldap_entry(self, member: Member) -> Dict[str, List[str]]:
        """Convert a Member object to LDAP entry attributes."""
        entry = {
            'objectClass': ['inetOrgPerson', 'organizationalPerson', 'person', 'top'],
            'uid': [str(member.neon_id)],
            'cn': [member.name or f"{member.fname} {member.lname}".strip()],
            'sn': [member.lname or "Unknown"],
            'givenName': [member.fname or "Unknown"],
            'mail': [member.email],
            'employeeNumber': [str(member.neon_id)],
            'ou': ['users'],
        }
        
        # Add roles from API Server Role custom field
        if hasattr(member, "roles") and member.roles:
            role_names = [
                role["name"] for role in member.roles if role and "name" in role
            ]
            if role_names:
                entry['title'] = role_names
        
        # Filter out empty values
        return {k: v for k, v in entry.items() if v and v[0]}
    
    def start_server(self) -> bool:
        """Start the LDAP server in a background thread."""
        if self.running:
            log.warning("LDAP server is already running")
            return True
        
        try:
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            # Wait a moment for server to start
            time.sleep(1)
            
            log.info(f"LDAP service started on {self.host}:{self.port}")
            self.running = True
            return True
            
        except Exception as e:
            log.error(f"Failed to start LDAP server: {e}")
            return False
    
    def _run_server(self):
        """Run the LDAP server in Twisted reactor."""
        try:
            # Create server factory
            def serverFactory():
                return NeonLDAPServer(self)
            
            # Create endpoint and listen
            endpoint = endpoints.TCP4ServerEndpoint(reactor, self.port, interface=self.host)
            endpoint.listen(serverFactory)
            
            # Run reactor in this thread
            reactor.run(installSignalHandlers=False)
            
        except Exception as e:
            log.error(f"LDAP server error: {e}")
            self.running = False
    
    def stop_server(self):
        """Stop the LDAP server."""
        if self.running:
            try:
                reactor.stop()
                if self.server_thread:
                    self.server_thread.join(timeout=5)
                log.info("LDAP service stopped")
            except Exception as e:
                log.warning(f"Error stopping LDAP server: {e}")
            finally:
                self.running = False
    
    def health_check(self) -> Dict[str, Any]:
        """Return health status of the service."""
        return {
            'status': 'running' if self.running else 'stopped',
            'host': self.host,
            'port': self.port,
            'base_dn': self.base_dn,
            'users_dn': self.users_dn,
            'cached_accounts': len(neon.cache),
            'cache_refresh_period_sec': neon.cache.REFRESH_PD_SEC,
        }


def create_ldap_service(host: str = '127.0.0.1', port: int = 3389) -> NeonLDAPService:
    """Factory function to create and configure the LDAP service."""
    base_dn = get_config("ldap/base_dn")
    service = NeonLDAPService(host=host, port=port, base_dn=base_dn)
    return service

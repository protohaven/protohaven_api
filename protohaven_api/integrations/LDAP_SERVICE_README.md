# Neon CRM LDAP Proxy Service

This service provides an LDAP interface to Neon CRM member data, suitable for integration with Pocket ID or other LDAP-based authentication systems.

## Features

- **LDAP Directory Interface**: Exposes Neon CRM member data via standard LDAP protocol
- **Member Data Mapping**: Maps Neon member fields to standard LDAP attributes
- **Authentication Support**: Basic authentication against Neon member database
- **Caching**: Uses existing AccountCache infrastructure (24-hour refresh cycle)
- **Standalone Operation**: Can run independently of the main application
- **Pocket ID Compatible**: Designed for integration with Pocket ID authentication

## Files

- `ldap_service.py` - Main LDAP service implementation (uses real Neon CRM data)
- `ldap_server.py` - Standalone server runner with command-line interface
- `test_ldap_service.py` - Unit tests for the LDAP service

## LDAP Schema Mapping

Neon CRM member data is mapped to LDAP attributes as follows:

| LDAP Attribute     | Neon CRM Field           | Description                    |
|-------------------|--------------------------|--------------------------------|
| `uid`             | Email prefix             | Username (part before @)       |
| `cn`              | Full Name                | Common name                    |
| `sn`              | Last Name                | Surname                        |
| `givenName`       | First Name               | Given name                     |
| `mail`            | Email                    | Email address                  |
| `employeeNumber`  | Neon ID                  | Unique member ID               |
| `title`           | API Server Role          | Admin, Shop Tech, Staff, etc.  |
| `ou`              | "users"                  | Organizational unit            |
| `objectClass`     | inetOrgPerson, etc.      | LDAP object classes            |

**Note**: The `title` attribute contains role names from the "API Server Role" custom field in Neon CRM. Multiple roles are supported and will appear as multiple values in the `title` attribute.

## Directory Structure

```
dc=protohaven,dc=org
└── ou=users,dc=protohaven,dc=org
    ├── uid=alice.johnson,ou=users,dc=protohaven,dc=org
    ├── uid=bob.smith,ou=users,dc=protohaven,dc=org
    └── ...
```

## Installation

1. Install dependencies:
   ```bash
   pip install ldap3==2.9.1
   ```

2. Ensure Neon CRM API credentials are configured in your environment.

## Usage

### Running the Service

```bash
# Basic usage
python protohaven_api/integrations/ldap_server.py

# Custom host and port
python protohaven_api/integrations/ldap_server.py --host 127.0.0.1 --port 1389

# Test mode (validate setup without starting server)
python protohaven_api/integrations/ldap_server.py --test-mode

# Debug logging
python protohaven_api/integrations/ldap_server.py --log-level DEBUG
```

### As a Module

```python
from protohaven_api.integrations.ldap_service import create_ldap_service

# Create and start service
service = create_ldap_service(host="127.0.0.1", port=1389)
if service.start_server():
    print("LDAP service started")
    
    # Service is now running and can accept LDAP connections
    # ...
    
    service.stop_server()
else:
    print("Failed to start service")
```

## Configuration

The service uses the following configuration options:

- `ldap/base_dn` - LDAP base DN (default: "dc=protohaven,dc=org")
- Neon CRM API credentials (inherited from existing configuration)

## Integration with Pocket ID

To integrate with Pocket ID:

1. Start the LDAP service on a accessible host/port
2. Configure Pocket ID to use LDAP authentication with:
   - **Server**: Your LDAP service host:port
   - **Base DN**: `dc=protohaven,dc=org`
   - **User DN**: `ou=users,dc=protohaven,dc=org`
   - **User Filter**: `(uid=%s)` or `(mail=%s)`
   - **Attributes**: Map as needed for your Pocket ID setup

## Authentication Flow

1. User attempts to authenticate with Pocket ID
2. Pocket ID queries the LDAP service for user information
3. LDAP service looks up the user in cached Neon CRM data
4. If user exists, authentication succeeds (basic implementation)
5. User attributes are returned to Pocket ID for session setup

## Limitations and Production Notes

- **Authentication**: Current implementation provides basic authentication validation. For production use, integrate with Neon's actual authentication system.
- **Performance**: Service uses AccountCache with 24-hour refresh cycle, shared with other Neon integrations for efficiency.
- **Security**: Consider TLS/SSL for production LDAP connections.
- **Monitoring**: Add proper monitoring and health checks for production deployment.
- **Scalability**: For high-traffic scenarios, consider connection pooling and load balancing.

## Testing

Run the unit tests:

```bash
pytest protohaven_api/integrations/test_ldap_service.py -v
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed and the Python path includes the project root.

2. **Neon API Errors**: Verify Neon CRM API credentials are properly configured.

3. **LDAP Connection Issues**: Check host/port accessibility and firewall settings.

4. **Cache Issues**: The service uses AccountCache with 24-hour refresh cycle. For immediate updates, restart the service or manually refresh the AccountCache.

### Debug Mode

Run with debug logging to see detailed operation:

```bash
python protohaven_api/integrations/ldap_server.py --log-level DEBUG
```

### Health Check

Query the service health programmatically:

```python
service = create_ldap_service()
health = service.health_check()
print(health)
# Output: {'status': 'stopped', 'cached_members': 0, 'base_dn': '...', ...}
```

## Development

For development and testing:

1. Run unit tests to verify functionality
2. Test integration with actual LDAP clients (ldapsearch, Pocket ID, etc.)
3. Monitor logs for debugging and optimization

## Architecture Notes

The service is designed to be:

- **Standalone**: Can run independently of the main application
- **Lightweight**: Minimal dependencies and resource usage
- **Extensible**: Easy to modify for different LDAP schemas or authentication methods
- **Production-Ready**: Includes proper logging, error handling, and graceful shutdown

For production deployment, consider containerizing the service and using proper orchestration tools.

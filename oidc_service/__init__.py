"""Standalone OIDC provider backed by Neon CRM authentication."""

from oidc_service.app import create_app

__all__ = ["create_app"]

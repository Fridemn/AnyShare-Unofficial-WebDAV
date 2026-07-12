"""WsgiDAV application factory."""

from __future__ import annotations

from typing import Any

from wsgidav.wsgidav_app import WsgiDAVApp

from anyshare_unofficial.webdav.provider import AnyShareDAVProvider


def create_app(
    provider: AnyShareDAVProvider,
    *,
    username: str,
    password: str,
    verbose: int = 1,
) -> WsgiDAVApp:
    """Create an authenticated WsgiDAV application for one AnyShare account."""
    if not username or not password:
        raise ValueError("A non-empty WebDAV username and password are required")
    config: dict[str, Any] = {
        "provider_mapping": {"/": provider},
        "verbose": verbose,
        "logging": {"enable": verbose > 0},
        "http_authenticator": {
            "accept_basic": True,
            "accept_digest": False,
            "default_to_digest": False,
        },
        "simple_dc": {
            "user_mapping": {
                "*": {
                    username: {"password": password},
                }
            }
        },
        "lock_storage": True,
        "property_manager": True,
        "dir_browser": {"enable": False},
    }
    return WsgiDAVApp(config)

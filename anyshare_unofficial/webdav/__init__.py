"""WebDAV gateway for authenticated AnyShare document libraries.

Install the optional dependencies with ``pip install 'AnyShare-Unofficial[webdav]'``.
Imports are lazy so the core SDK remains usable without WsgiDAV.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from anyshare_unofficial.webdav.app import create_app
    from anyshare_unofficial.webdav.provider import AnyShareDAVProvider
    from anyshare_unofficial.webdav.repository import AnyShareRepository, DAVNode

__all__ = ["AnyShareDAVProvider", "AnyShareRepository", "DAVNode", "create_app"]


def __getattr__(name: str) -> Any:
    if name == "create_app":
        from anyshare_unofficial.webdav.app import create_app

        return create_app
    if name == "AnyShareDAVProvider":
        from anyshare_unofficial.webdav.provider import AnyShareDAVProvider

        return AnyShareDAVProvider
    if name in ("AnyShareRepository", "DAVNode"):
        from anyshare_unofficial.webdav import repository

        return getattr(repository, name)
    raise AttributeError(name)

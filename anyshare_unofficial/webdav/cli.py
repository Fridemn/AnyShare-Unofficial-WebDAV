"""Command-line entry point for the AnyShare WebDAV gateway."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from anyshare_unofficial import AuthenticatedClient


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Expose AnyShare document libraries over WebDAV")
    parser.add_argument("--base-url", default=os.environ.get("ANYSHARE_BASE_URL"))
    parser.add_argument("--host", default=os.environ.get("ANYSHARE_DAV_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("ANYSHARE_DAV_PORT", "18765")))
    parser.add_argument("--username", default=os.environ.get("ANYSHARE_DAV_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("ANYSHARE_DAV_PASSWORD"))
    parser.add_argument(
        "--readonly",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("ANYSHARE_DAV_READONLY"),
    )
    parser.add_argument(
        "--cache-ttl",
        type=float,
        default=float(os.environ.get("ANYSHARE_DAV_CACHE_TTL", "5")),
    )
    parser.add_argument(
        "--insecure",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("ANYSHARE_DAV_INSECURE"),
        help="Disable TLS verification for AnyShare and signed download URLs",
    )
    parser.add_argument("--certfile", default=os.environ.get("ANYSHARE_DAV_CERTFILE"))
    parser.add_argument("--keyfile", default=os.environ.get("ANYSHARE_DAV_KEYFILE"))
    parser.add_argument(
        "--quiet",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("ANYSHARE_DAV_QUIET"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    cookie = os.environ.get("ANYSHARE_AUTH_COOKIE")
    missing = [
        name
        for name, value in (
            ("--base-url/ANYSHARE_BASE_URL", args.base_url),
            ("ANYSHARE_AUTH_COOKIE", cookie),
            ("--username/ANYSHARE_DAV_USERNAME", args.username),
            ("--password/ANYSHARE_DAV_PASSWORD", args.password),
        )
        if not value
    ]
    if missing:
        parser.error("missing required settings: " + ", ".join(missing))
    if bool(args.certfile) != bool(args.keyfile):
        parser.error("--certfile and --keyfile must be supplied together")

    try:
        from cheroot import wsgi
        from cheroot.ssl.builtin import BuiltinSSLAdapter
        from wsgidav.wsgidav_app import WsgiDAVApp  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on optional installation
        raise SystemExit("Install WebDAV dependencies: pip install 'AnyShare-Unofficial[webdav]'") from exc

    from anyshare_unofficial.webdav.app import create_app
    from anyshare_unofficial.webdav.provider import AnyShareDAVProvider
    from anyshare_unofficial.webdav.repository import AnyShareRepository

    client = AuthenticatedClient(cookie, base_url=args.base_url, verify=not args.insecure)
    repository = AnyShareRepository(
        client,
        cache_ttl=args.cache_ttl,
        download_verify=not args.insecure,
    )
    provider = AnyShareDAVProvider(repository, readonly=args.readonly)
    app = create_app(provider, username=args.username, password=args.password, verbose=0 if args.quiet else 1)
    server = wsgi.Server((args.host, args.port), app, server_name="AnyShare WebDAV")
    if args.certfile:
        server.ssl_adapter = BuiltinSSLAdapter(args.certfile, args.keyfile)
    scheme = "https" if args.certfile else "http"
    try:
        print(f"AnyShare WebDAV listening on {scheme}://{args.host}:{args.port}/")
        server.start()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        client.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

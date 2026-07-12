"""Configuration shared by the Windows service and mount helper."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dotenv import dotenv_values


TRUTHY = {"1", "true", "yes", "on"}


def _as_bool(value: str | None, default: bool = False) -> bool:
    return default if value is None else value.strip().lower() in TRUTHY


def _required(values: dict[str, str], name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required setting {name}")
    return value


def _optional_path(value: str, base_dir: Path) -> Path | None:
    if not value.strip():
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base_dir / path).resolve()


def default_env_path() -> Path:
    configured = os.environ.get("ANYSHARE_MOUNT_ENV_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / ".env"


@dataclass(frozen=True)
class MountConfig:
    env_file: Path
    base_url: str
    auth_cookie: str = field(repr=False)
    dav_username: str
    dav_password: str = field(repr=False)
    host: str = "127.0.0.1"
    port: int = 18765
    readonly: bool = False
    cache_ttl: float = 5.0
    upstream_verify: bool = True
    certfile: Path | None = None
    keyfile: Path | None = None
    drive: str = "X:"
    mount_url: str = ""
    mount_tls_verify: bool = True
    mount_wait_seconds: float = 60.0

    @property
    def local_url(self) -> str:
        if self.mount_url:
            return self.mount_url
        scheme = "https" if self.certfile else "http"
        host = "127.0.0.1" if self.host in {"0.0.0.0", "::"} else self.host
        return f"{scheme}://{host}:{self.port}/"

    @property
    def webdav_remote_name(self) -> str:
        """Return the UNC form understood by the Windows WebClient redirector."""
        url = self.local_url
        if url.startswith("\\\\"):
            return url
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("ANYSHARE_MOUNT_URL must be an HTTP(S) URL or WebDAV UNC path")
        default_port = 443 if parsed.scheme == "https" else 80
        port = parsed.port or default_port
        ssl_part = "@SSL" if parsed.scheme == "https" else ""
        port_part = f"@{port}" if port != default_port else ""
        path = unquote(parsed.path).strip("/").replace("/", "\\")
        suffix = f"\\{path}" if path else ""
        return f"\\\\{parsed.hostname}{ssl_part}{port_part}\\DavWWWRoot{suffix}"

    @classmethod
    def from_env_file(cls, path: str | Path | None = None) -> "MountConfig":
        env_file = Path(path).expanduser().resolve() if path else default_env_path()
        if not env_file.is_file():
            raise FileNotFoundError(f"Environment file not found: {env_file}")

        file_values = {key: value or "" for key, value in dotenv_values(env_file).items()}
        values = {**file_values, **{key: value for key, value in os.environ.items() if key.startswith("ANYSHARE_")}}
        base_dir = env_file.parent
        certfile = _optional_path(values.get("ANYSHARE_DAV_CERTFILE", ""), base_dir)
        keyfile = _optional_path(values.get("ANYSHARE_DAV_KEYFILE", ""), base_dir)
        if bool(certfile) != bool(keyfile):
            raise ValueError("ANYSHARE_DAV_CERTFILE and ANYSHARE_DAV_KEYFILE must be set together")

        drive = values.get("ANYSHARE_MOUNT_DRIVE", "X:").strip().upper()
        if not re.fullmatch(r"[A-Z]:", drive):
            raise ValueError("ANYSHARE_MOUNT_DRIVE must look like X:")
        port = int(values.get("ANYSHARE_DAV_PORT", "18765"))
        if not 1 <= port <= 65535:
            raise ValueError("ANYSHARE_DAV_PORT must be between 1 and 65535")

        return cls(
            env_file=env_file,
            base_url=_required(values, "ANYSHARE_BASE_URL"),
            auth_cookie=_required(values, "ANYSHARE_AUTH_COOKIE"),
            dav_username=_required(values, "ANYSHARE_DAV_USERNAME"),
            dav_password=_required(values, "ANYSHARE_DAV_PASSWORD"),
            host=values.get("ANYSHARE_DAV_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=port,
            readonly=_as_bool(values.get("ANYSHARE_DAV_READONLY")),
            cache_ttl=float(values.get("ANYSHARE_DAV_CACHE_TTL", "5")),
            upstream_verify=not _as_bool(values.get("ANYSHARE_DAV_INSECURE")),
            certfile=certfile,
            keyfile=keyfile,
            drive=drive,
            mount_url=values.get("ANYSHARE_MOUNT_URL", "").strip(),
            mount_tls_verify=_as_bool(values.get("ANYSHARE_MOUNT_TLS_VERIFY"), default=True),
            mount_wait_seconds=float(values.get("ANYSHARE_MOUNT_WAIT_SECONDS", "60")),
        )

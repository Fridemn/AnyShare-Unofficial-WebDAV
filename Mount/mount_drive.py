"""Map the WebDAV endpoint into the current interactive Windows session."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Mount.config import MountConfig, default_env_path  # noqa: E402


def wait_until_ready(config: MountConfig) -> None:
    deadline = time.monotonic() + config.mount_wait_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.request(
                "OPTIONS",
                config.local_url,
                auth=(config.dav_username, config.dav_password),
                verify=config.mount_tls_verify,
                timeout=3,
            )
            if response.status_code < 500:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(1)
    raise TimeoutError(f"WebDAV gateway did not become ready: {last_error or config.local_url}")


def mount_drive(config: MountConfig, *, force: bool = False) -> None:
    if os.name != "nt":
        raise RuntimeError("Drive mapping is only available on Windows")
    import win32netcon
    import win32wnet
    import pywintypes

    try:
        current = win32wnet.WNetGetConnection(config.drive)
    except pywintypes.error:
        current = None
    if current:
        if current.rstrip("\\/").casefold() == config.webdav_remote_name.rstrip("\\/").casefold():
            return
        if not force:
            raise RuntimeError(f"{config.drive} is already mapped to another resource")
        win32wnet.WNetCancelConnection2(config.drive, win32netcon.CONNECT_UPDATE_PROFILE, True)

    resource = win32wnet.NETRESOURCE()
    resource.dwType = win32netcon.RESOURCETYPE_DISK
    resource.lpLocalName = config.drive
    resource.lpRemoteName = config.webdav_remote_name
    win32wnet.WNetAddConnection2(
        resource,
        config.dav_password,
        config.dav_username,
        win32netcon.CONNECT_UPDATE_PROFILE,
    )


def unmount_drive(config: MountConfig, *, force: bool = False) -> None:
    if os.name != "nt":
        raise RuntimeError("Drive mapping is only available on Windows")
    import win32netcon
    import win32wnet

    win32wnet.WNetCancelConnection2(
        config.drive,
        win32netcon.CONNECT_UPDATE_PROFILE,
        force,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(default_env_path()))
    parser.add_argument("--unmount", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-wait", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = MountConfig.from_env_file(args.env_file)
        if args.unmount:
            unmount_drive(config, force=args.force)
        else:
            if not args.no_wait:
                wait_until_ready(config)
            mount_drive(config, force=args.force)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

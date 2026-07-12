"""Map the WebDAV endpoint into the current interactive Windows session."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.config import MountConfig, default_env_path  # noqa: E402


PROPFIND_BODY = b'''<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:"><D:prop><D:displayname/></D:prop></D:propfind>'''


def _propfind(config: MountConfig, depth: str) -> httpx.Response:
    return httpx.request(
        "PROPFIND",
        config.local_url,
        auth=(config.dav_username, config.dav_password),
        headers={"Depth": depth, "Content-Type": "application/xml"},
        content=PROPFIND_BODY,
        verify=config.mount_tls_verify,
        timeout=15,
    )


def _response_detail(response: httpx.Response) -> str:
    detail = " ".join(response.text.split())[:300]
    return f": {detail}" if detail else ""


def probe_webdav(config: MountConfig) -> None:
    """Verify local DAV authentication, then force an AnyShare root listing."""
    local_response = _propfind(config, "0")
    if local_response.status_code != 207:
        message = (
            "Local WebDAV authentication failed "
            f"with HTTP {local_response.status_code}{_response_detail(local_response)}"
        )
        if local_response.status_code in {401, 403}:
            raise PermissionError(message)
        raise RuntimeError(message)

    response = _propfind(config, "1")
    if response.status_code != 207:
        message = (
            "AnyShare root listing through WebDAV failed "
            f"with HTTP {response.status_code}{_response_detail(response)}"
        )
        if response.status_code in {401, 403}:
            raise PermissionError(message)
        raise RuntimeError(message)


def wait_until_ready(config: MountConfig) -> None:
    deadline = time.monotonic() + config.mount_wait_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            probe_webdav(config)
            return
        except (httpx.HTTPError, RuntimeError) as exc:
            last_error = exc
        time.sleep(1)
    raise TimeoutError(f"WebDAV gateway did not become ready: {last_error or config.local_url}")


def mount_targets(config: MountConfig) -> tuple[str, ...]:
    targets = [config.webdav_remote_name, config.local_url]
    return tuple(dict.fromkeys(targets))


def _same_remote(left: str, right: str) -> bool:
    return left.rstrip("\\/").casefold() == right.rstrip("\\/").casefold()


def _verify_drive_access(drive: str) -> None:
    with os.scandir(f"{drive}\\") as entries:
        next(entries, None)


def mount_drive(config: MountConfig, *, force: bool = False) -> str:
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
        expected = any(_same_remote(current, target) for target in mount_targets(config))
        if expected:
            try:
                _verify_drive_access(config.drive)
                return current
            except OSError as exc:
                if not force:
                    raise RuntimeError(
                        f"{config.drive} is mapped but cannot be read; retry with --force: {exc}"
                    ) from exc
        elif not force:
            raise RuntimeError(f"{config.drive} is already mapped to another resource: {current}")
        win32wnet.WNetCancelConnection2(config.drive, win32netcon.CONNECT_UPDATE_PROFILE, True)

    errors: list[str] = []
    for target in mount_targets(config):
        resource = win32wnet.NETRESOURCE()
        resource.dwType = win32netcon.RESOURCETYPE_DISK
        resource.lpLocalName = config.drive
        resource.lpRemoteName = target
        try:
            win32wnet.WNetAddConnection2(
                resource,
                config.dav_password,
                config.dav_username,
                win32netcon.CONNECT_UPDATE_PROFILE,
            )
            _verify_drive_access(config.drive)
            return target
        except (OSError, pywintypes.error) as exc:
            errors.append(f"{target}: {exc}")
            try:
                win32wnet.WNetCancelConnection2(config.drive, win32netcon.CONNECT_UPDATE_PROFILE, True)
            except pywintypes.error:
                pass
    raise RuntimeError("Windows created no readable WebDAV mapping; " + " | ".join(errors))


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
    parser.add_argument("--log-file", help="append mount status to this file")
    return parser


def _log(path: str | None, message: str) -> None:
    if not path:
        return
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as target:
        target.write(f"{timestamp} {message}\n")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = MountConfig.from_env_file(args.env_file)
        if args.unmount:
            unmount_drive(config, force=args.force)
            message = f"UNMOUNTED {config.drive}"
        else:
            if not args.no_wait:
                wait_until_ready(config)
            target = mount_drive(config, force=args.force)
            message = f"MOUNTED {config.drive} -> {target}"
        print(message)
        _log(args.log_file, message)
        return 0
    except Exception as exc:
        message = f"ERROR: {exc}"
        print(message, file=sys.stderr)
        _log(args.log_file, message)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

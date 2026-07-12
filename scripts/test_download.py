#!/usr/bin/env python3
"""Browse AnyShare content and download one file using settings from .env."""

from __future__ import annotations

import argparse
import os
import sys
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from dotenv import load_dotenv

# Running ``python scripts/test_download.py`` puts ``scripts/`` first on
# sys.path. Prefer this checkout over an older globally installed package.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from anyshare_unofficial import AnyShareError, AuthenticatedClient, FileItem, FolderItem  # noqa: E402


@dataclass(frozen=True)
class LocatedFile:
    item: FileItem
    relative_path: PurePosixPath


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env", help="dotenv file (default: .env)")
    parser.add_argument(
        "--doc-lib",
        help="document library name or zero-based index (default: first library)",
    )
    parser.add_argument(
        "--remote-path",
        help="file path relative to the document library, for example: folder/report.pdf",
    )
    parser.add_argument("--output-dir", default="downloads", help="local output directory")
    parser.add_argument("--max-depth", type=int, default=10, help="search depth when --remote-path is omitted")
    parser.add_argument("--overwrite", action="store_true", help="overwrite an existing local file")
    parser.add_argument("--list-only", action="store_true", help="only list the selected library root")
    return parser


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing {name}; configure it in .env or the process environment")
    return value


def choose_doc_lib(libraries, selector: str | None):
    if not libraries:
        raise LookupError("The current account has no accessible document libraries")
    if selector is None:
        return libraries[0]
    if selector.isdigit():
        index = int(selector)
        if index >= len(libraries):
            raise LookupError(f"Document library index out of range: {index}")
        return libraries[index]
    exact = [library for library in libraries if library.name == selector]
    candidates = exact or [library for library in libraries if library.name.casefold() == selector.casefold()]
    if len(candidates) != 1:
        raise LookupError(f"Document library not found or ambiguous: {selector}")
    return candidates[0]


def list_entries(client: AuthenticatedClient, folder_id: str) -> list[FileItem | FolderItem]:
    return list(client.iter_folder(folder_id))


def resolve_file(client: AuthenticatedClient, root_id: str, remote_path: str) -> LocatedFile:
    path = PurePosixPath(remote_path.replace("\\", "/"))
    parts = [part for part in path.parts if part not in ("", "/")]
    if not parts or any(part in (".", "..") for part in parts):
        raise ValueError(f"Invalid remote path: {remote_path!r}")

    parent_id = root_id
    for index, segment in enumerate(parts):
        entries = list_entries(client, parent_id)
        exact = [entry for entry in entries if entry.name == segment]
        candidates = exact or [entry for entry in entries if entry.name.casefold() == segment.casefold()]
        if len(candidates) != 1:
            raise FileNotFoundError(f"Remote path segment not found or ambiguous: {segment}")
        entry = candidates[0]
        is_last = index == len(parts) - 1
        if is_last:
            if entry.is_dir:
                raise IsADirectoryError(remote_path)
            return LocatedFile(item=entry, relative_path=PurePosixPath(*parts))
        if not entry.is_dir:
            raise NotADirectoryError("/".join(parts[: index + 1]))
        parent_id = entry.id
    raise FileNotFoundError(remote_path)


def find_first_file(client: AuthenticatedClient, root_id: str, max_depth: int) -> LocatedFile:
    queue: deque[tuple[str, PurePosixPath, int]] = deque([(root_id, PurePosixPath(), 0)])
    while queue:
        folder_id, relative_dir, depth = queue.popleft()
        entries = list_entries(client, folder_id)
        for entry in entries:
            relative_path = relative_dir / entry.name
            if not entry.is_dir:
                return LocatedFile(item=entry, relative_path=relative_path)
        if depth < max_depth:
            for entry in entries:
                if entry.is_dir:
                    queue.append((entry.id, relative_dir / entry.name, depth + 1))
    raise FileNotFoundError(f"No file found within search depth {max_depth}")


def print_entries(entries: Sequence[FileItem | FolderItem]) -> None:
    if not entries:
        print("  (empty)")
        return
    for entry in entries:
        kind = "DIR " if entry.is_dir else "FILE"
        size = "-" if entry.is_dir else str(entry.size)
        print(f"  [{kind}] {entry.name} ({size} bytes)")


def download(client: AuthenticatedClient, located: LocatedFile, output_dir: Path, overwrite: bool) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / located.item.name
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Local file already exists: {destination}; use --overwrite to replace it")
    return client.download_file(located.item.id, destination, savename=located.item.name)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(Path(args.env_file).expanduser(), override=False)

    try:
        base_url = require_env("ANYSHARE_BASE_URL")
        cookie = require_env("ANYSHARE_AUTH_COOKIE")
        verify = os.environ.get("ANYSHARE_DAV_INSECURE", "false").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }

        with AuthenticatedClient(cookie, base_url=base_url, verify=verify) as client:
            user = client.get_current_user()
            libraries = client.list_doc_libs()
            print(f"Authenticated as: {user.name}")
            print("Document libraries:")
            for index, library in enumerate(libraries):
                print(f"  [{index}] {library.name} ({library.type})")

            library = choose_doc_lib(libraries, args.doc_lib)
            root_entries = list_entries(client, library.id)
            print(f"Root content of {library.name!r}:")
            print_entries(root_entries)
            if args.list_only:
                return 0

            located = (
                resolve_file(client, library.id, args.remote_path)
                if args.remote_path
                else find_first_file(client, library.id, args.max_depth)
            )
            print(f"Selected remote file: {located.relative_path} ({located.item.size} bytes)")
            destination = download(client, located, Path(args.output_dir), args.overwrite)
            print(f"Downloaded to: {destination.resolve()}")
            return 0
    except (AnyShareError, OSError, ValueError, LookupError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

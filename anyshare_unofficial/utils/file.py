"""Local file utilities for computing hashes and metadata."""

from __future__ import annotations

import hashlib
import zlib
from dataclasses import dataclass
from io import BufferedReader
from pathlib import Path


@dataclass
class LocalFile:
    """Information about a local file to be uploaded.

    Wraps a buffered reader handle along with pre-computed metadata
    (name, size, MD5, CRC32) needed by the AnyShare upload API.
    """

    handle: BufferedReader
    name: str
    size: int
    md5: str  # 32 lowercase hex characters
    crc32: str  # 8 lowercase hex characters

    @classmethod
    def from_path(cls, path: str | Path, *, name: str | None = None) -> "LocalFile":
        """Create a LocalFile instance from a file path.

        Raises FileNotFoundError if the path does not point to an existing file.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path.absolute())

        md5 = hashlib.md5()
        crc32 = 0
        size = 0
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                md5.update(chunk)
                crc32 = zlib.crc32(chunk, crc32)

        instance = cls(
            handle=path.open("rb"),
            name=name or path.name,
            size=size,
            md5=md5.hexdigest().lower(),
            crc32=f"{crc32 & 0xFFFFFFFF:08x}",
        )
        return instance

    def close(self) -> None:
        """Close the underlying file handle."""
        self.handle.close()

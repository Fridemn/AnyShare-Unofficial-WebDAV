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
    def from_path(cls, path: str | Path) -> "LocalFile":
        """Create a LocalFile instance from a file path.

        Raises FileNotFoundError if the path does not point to an existing file.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path.absolute())

        file_data = path.read_bytes()
        instance = cls(
            handle=path.open("rb"),
            name=path.name,
            size=len(file_data),
            md5=hashlib.md5(file_data).hexdigest().lower(),
            crc32=f"{zlib.crc32(file_data):08x}",
        )
        del file_data
        return instance

    def close(self) -> None:
        """Close the underlying file handle."""
        self.handle.close()

"""GNS path utilities for AnyShare object IDs.

GNS paths are AnyShare's internal addressing scheme, using the format:
    gns://{doc_lib_id}/{folder_id}/.../{file_or_folder_id}

These paths must be URL-encoded when used in API request paths.
"""

from __future__ import annotations

from urllib.parse import quote_plus

GNS_PREFIX = "gns://"


def is_gns_path(path: str) -> bool:
    """Check whether a string is a valid GNS path."""
    return path.startswith(GNS_PREFIX) and len(path) > len(GNS_PREFIX)


def parse_gns_path(path: str) -> list[str]:
    """Parse a GNS path into its component segments.

    >>> parse_gns_path("gns://A/B/C")
    ['A', 'B', 'C']
    """
    if not is_gns_path(path):
        raise ValueError(f"Not a valid GNS path: {path}")
    # Strip prefix and split, filtering empty segments from trailing slashes
    return [s for s in path[len(GNS_PREFIX):].split("/") if s]


def build_gns_path(*segments: str) -> str:
    """Build a GNS path from segments.

    >>> build_gns_path("A", "B", "C")
    'gns://A/B/C'
    """
    return GNS_PREFIX + "/".join(segments)


def quote_gns_path(gns_path: str) -> str:
    """URL-encode a GNS path for use in API request paths."""
    return quote_plus(gns_path)

"""Cookie string parsing utility."""

from __future__ import annotations


def parse_cookie_string(cookie_str: str) -> dict[str, str]:
    """Parse a browser-exported cookie string into a key-value dictionary.

    Input format (from browser DevTools):
        "key1=value1; key2=value2; key3=value3"

    Returns:
        dict: e.g. {"key1": "value1", "key2": "value2", "key3": "value3"}

    The function strips whitespace around keys but preserves values as-is.
    """
    result: dict[str, str] = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if not item:
            continue
        kv = item.split("=", 1)
        if len(kv) == 2:
            result[kv[0]] = kv[1]
        elif len(kv) == 1 and kv[0]:
            result[kv[0]] = ""
    return result

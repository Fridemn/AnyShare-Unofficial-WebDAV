"""Seekable reader backed by HTTP Range requests."""

from __future__ import annotations

import io

import httpx


class HTTPRangeReader(io.RawIOBase):
    """Expose a signed HTTP URL as the seekable stream expected by WsgiDAV."""

    def __init__(self, url: str, size: int, *, timeout: float = 60.0, verify: bool = True) -> None:
        super().__init__()
        self.url = url
        self.size = size
        self._position = 0
        self._client = httpx.Client(timeout=timeout, follow_redirects=True, verify=verify)
        self._response: httpx.Response | None = None
        self._chunks = None
        self._buffer = bytearray()

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_CUR:
            offset += self._position
        elif whence == io.SEEK_END:
            offset += self.size
        elif whence != io.SEEK_SET:
            raise ValueError(f"Unknown seek mode: {whence}")
        if offset < 0:
            raise ValueError("Negative seek position")
        self._close_response()
        self._position = min(offset, self.size)
        return self._position

    def _open_response(self) -> None:
        if self._response is not None or self._position >= self.size:
            return
        headers = {"Range": f"bytes={self._position}-"} if self._position else {}
        request = self._client.build_request("GET", self.url, headers=headers)
        response = self._client.send(request, stream=True)
        try:
            response.raise_for_status()
        except Exception:
            response.close()
            raise
        if self._position and response.status_code != 206:
            response.close()
            raise OSError("Upstream download URL does not support byte ranges")
        self._response = response
        self._chunks = response.iter_raw(chunk_size=64 * 1024)

    def read(self, size: int = -1) -> bytes:
        if self.closed or self._position >= self.size:
            return b""
        self._open_response()
        remaining = self.size - self._position
        wanted = remaining if size is None or size < 0 else min(size, remaining)
        assert self._chunks is not None
        while len(self._buffer) < wanted:
            try:
                self._buffer.extend(next(self._chunks))
            except StopIteration:
                break
        result = bytes(self._buffer[:wanted])
        del self._buffer[:wanted]
        self._position += len(result)
        return result

    def _close_response(self) -> None:
        if self._response is not None:
            self._response.close()
        self._response = None
        self._chunks = None
        self._buffer.clear()

    def close(self) -> None:
        if not self.closed:
            self._close_response()
            self._client.close()
        super().close()

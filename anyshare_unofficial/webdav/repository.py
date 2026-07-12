"""Filesystem-shaped adapter around :class:`AuthenticatedClient`."""

from __future__ import annotations

import posixpath
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from anyshare_unofficial import AuthenticatedClient, OnDup
from anyshare_unofficial.models.common import DocLibInfo
from anyshare_unofficial.models.fileobj import FileItem, FolderItem


@dataclass(frozen=True)
class DAVNode:
    """Metadata required to expose one AnyShare object as a DAV resource."""

    path: str
    name: str
    docid: str | None
    is_collection: bool
    size: int = 0
    rev: str = ""
    created_at: datetime | None = None
    modified_at: datetime | None = None
    virtual: bool = False

    @property
    def created_timestamp(self) -> float | None:
        return self.created_at.timestamp() if self.created_at else None

    @property
    def modified_timestamp(self) -> float | None:
        return self.modified_at.timestamp() if self.modified_at else None


class AnyShareRepository:
    """Resolve DAV paths and perform filesystem-like AnyShare operations."""

    def __init__(
        self,
        client: AuthenticatedClient,
        *,
        cache_ttl: float = 5.0,
        download_verify: bool = True,
    ) -> None:
        self.client = client
        self.cache_ttl = max(0.0, cache_ttl)
        self.download_verify = download_verify
        self._cache: dict[str, tuple[float, list[DAVNode]]] = {}
        self._lock = threading.RLock()
        self._started_at = datetime.now(timezone.utc)

    @staticmethod
    def normalize_path(path: str) -> str:
        if not path or path == "/":
            return "/"
        if "\x00" in path:
            raise ValueError("NUL is not allowed in DAV paths")
        parts = [part for part in path.replace("\\", "/").split("/") if part]
        if any(part in (".", "..") for part in parts):
            raise ValueError("Relative DAV path segments are not allowed")
        return "/" + "/".join(parts)

    @staticmethod
    def child_path(parent: str, name: str) -> str:
        if not name or "/" in name or "\\" in name or name in (".", ".."):
            raise ValueError(f"Invalid DAV member name: {name!r}")
        return "/" + name if parent == "/" else f"{parent}/{name}"

    def _doclib_nodes(self) -> list[DAVNode]:
        libraries = self.client.list_doc_libs()
        counts: dict[str, int] = {}
        for library in libraries:
            counts[library.name.casefold()] = counts.get(library.name.casefold(), 0) + 1
        return [self._doclib_node(lib, counts[lib.name.casefold()] > 1) for lib in libraries]

    @staticmethod
    def _doclib_node(library: DocLibInfo, disambiguate: bool) -> DAVNode:
        suffix = library.id.rstrip("/").split("/")[-1][-8:]
        name = f"{library.name} [{suffix}]" if disambiguate else library.name
        return DAVNode(
            path=f"/{name}",
            name=name,
            docid=library.id,
            is_collection=True,
            rev=library.rev,
            created_at=library.created_at,
            modified_at=library.modified_at,
        )

    @staticmethod
    def _item_node(parent_path: str, item: FileItem | FolderItem) -> DAVNode:
        return DAVNode(
            path=AnyShareRepository.child_path(parent_path, item.name),
            name=item.name,
            docid=item.id,
            is_collection=item.is_dir,
            size=max(0, item.size),
            rev=item.rev,
            created_at=item.created_at,
            modified_at=item.modified_at,
        )

    def _cached_children(self, node: DAVNode) -> list[DAVNode]:
        key = node.docid or "/"
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and cached[0] > now:
            return cached[1]
        if node.virtual:
            children = self._doclib_nodes()
        else:
            assert node.docid is not None
            children = [self._item_node(node.path, item) for item in self.client.iter_folder(node.docid)]
        self._cache[key] = (now + self.cache_ttl, children)
        return children

    def invalidate(self) -> None:
        with self._lock:
            self._cache.clear()

    def root(self) -> DAVNode:
        return DAVNode(
            path="/",
            name="",
            docid=None,
            is_collection=True,
            modified_at=self._started_at,
            virtual=True,
        )

    def list_children(self, node: DAVNode) -> list[DAVNode]:
        if not node.is_collection:
            raise NotADirectoryError(node.path)
        with self._lock:
            return list(self._cached_children(node))

    def resolve(self, path: str) -> DAVNode | None:
        path = self.normalize_path(path)
        if path == "/":
            return self.root()
        current = self.root()
        for segment in path.lstrip("/").split("/"):
            children = self.list_children(current)
            exact = [child for child in children if child.name == segment]
            candidates = exact or [child for child in children if child.name.casefold() == segment.casefold()]
            if len(candidates) != 1:
                return None
            current = candidates[0]
        return current

    def get_download(self, node: DAVNode) -> tuple[str, int]:
        if node.is_collection or not node.docid:
            raise IsADirectoryError(node.path)
        auth, result = self.client.get_download_url(node.docid, savename=node.name, rev=node.rev)
        return auth.url, result.size or node.size

    def create_collection(self, parent: DAVNode, name: str) -> DAVNode:
        if parent.virtual or not parent.docid:
            raise PermissionError("Document libraries cannot be created through WebDAV")
        self.client.create_directory(parent.docid, name, ondup=OnDup.FORBID)
        self.invalidate()
        node = self.resolve(self.child_path(parent.path, name))
        if node is None:
            raise FileNotFoundError(name)
        return node

    def upload(self, parent: DAVNode, name: str, local_path: str | Path) -> DAVNode:
        if parent.virtual or not parent.docid:
            raise PermissionError("Files cannot be uploaded to the DAV root")
        self.client.upload_file_s3(
            local_path,
            parent.docid,
            ondup=OnDup.OVERWRITE,
            remote_name=name,
        )
        self.invalidate()
        node = self.resolve(self.child_path(parent.path, name))
        if node is None:
            raise FileNotFoundError(name)
        return node

    def delete(self, node: DAVNode) -> None:
        if node.virtual or not node.docid:
            raise PermissionError("The DAV root cannot be deleted")
        self.client.delete_file(node.docid)
        self.invalidate()

    def move(self, node: DAVNode, dest_path: str) -> DAVNode:
        """Move a node, using a download/upload fallback for file renames."""
        dest_path = self.normalize_path(dest_path)
        dest_parent_path, dest_name = posixpath.split(dest_path)
        dest_parent = self.resolve(dest_parent_path or "/")
        if dest_parent is None or not dest_parent.is_collection or not dest_parent.docid:
            raise FileNotFoundError(dest_parent_path)
        source_parent_path = posixpath.dirname(node.path) or "/"

        if node.is_collection:
            if source_parent_path == dest_parent.path:
                assert node.docid is not None
                self.client.rename_directory(node.docid, dest_name, ondup=OnDup.FORBID)
            elif dest_name == node.name:
                assert node.docid is not None
                self.client.move_file(node.docid, dest_parent.docid, ondup=OnDup.FORBID)
            else:
                raise NotImplementedError("Moving and renaming a directory in one request is not supported")
        elif dest_name == node.name:
            assert node.docid is not None
            self.client.move_file(node.docid, dest_parent.docid, ondup=OnDup.OVERWRITE)
        else:
            # AnyShare v7 API coverage in this project has no file rename call.
            # Preserve DAV behavior with a copy-then-delete fallback.
            with tempfile.TemporaryDirectory(prefix="anyshare-dav-move-") as temp_dir:
                temp_path = Path(temp_dir) / node.name
                assert node.docid is not None
                self.client.download_file(node.docid, temp_path, savename=node.name)
                self.upload(dest_parent, dest_name, temp_path)
                self.client.delete_file(node.docid)

        self.invalidate()
        result = self.resolve(dest_path)
        if result is None:
            raise FileNotFoundError(dest_path)
        return result

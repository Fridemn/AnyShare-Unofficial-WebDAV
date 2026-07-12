"""WsgiDAV provider backed by AnyShare document libraries."""

from __future__ import annotations

import mimetypes
import os
import posixpath
import tempfile
from collections.abc import Callable
from typing import Any, TypeVar

from wsgidav.dav_error import (
    DAVError,
    HTTP_BAD_GATEWAY,
    HTTP_BAD_REQUEST,
    HTTP_CONFLICT,
    HTTP_FORBIDDEN,
    HTTP_INTERNAL_ERROR,
    HTTP_NOT_FOUND,
    HTTP_NOT_IMPLEMENTED,
)
from wsgidav.dav_provider import DAVCollection, DAVNonCollection, DAVProvider

from anyshare_unofficial.exceptions import AnyShareAuthError, AnyShareError, AnyShareNetworkError
from anyshare_unofficial.webdav.http_file import HTTPRangeReader
from anyshare_unofficial.webdav.repository import AnyShareRepository, DAVNode

T = TypeVar("T")


def _translate_errors(callback: Callable[[], T]) -> T:
    try:
        return callback()
    except DAVError:
        raise
    except ValueError as exc:
        raise DAVError(HTTP_BAD_REQUEST, str(exc)) from exc
    except FileNotFoundError as exc:
        raise DAVError(HTTP_NOT_FOUND, str(exc)) from exc
    except FileExistsError as exc:
        raise DAVError(HTTP_CONFLICT, str(exc)) from exc
    except (PermissionError, AnyShareAuthError) as exc:
        raise DAVError(HTTP_FORBIDDEN, str(exc)) from exc
    except NotImplementedError as exc:
        raise DAVError(HTTP_NOT_IMPLEMENTED, str(exc)) from exc
    except AnyShareNetworkError as exc:
        raise DAVError(HTTP_BAD_GATEWAY, str(exc)) from exc
    except AnyShareError as exc:
        raise DAVError(HTTP_BAD_GATEWAY, str(exc)) from exc
    except Exception as exc:
        raise DAVError(HTTP_INTERNAL_ERROR, str(exc)) from exc


class AnyShareDAVProvider(DAVProvider):
    """Expose an :class:`AnyShareRepository` as a WebDAV filesystem."""

    def __init__(self, repository: AnyShareRepository, *, readonly: bool = False) -> None:
        super().__init__()
        self.repository = repository
        self.readonly = readonly

    def is_readonly(self) -> bool:
        return self.readonly

    def get_resource_inst(self, path: str, environ: dict[str, Any]):
        node = _translate_errors(lambda: self.repository.resolve(path))
        if node is None:
            return None
        if node.is_collection:
            return AnyShareCollection(node, environ)
        return AnyShareFile(node, environ)


class _AnyShareResourceMixin:
    node: DAVNode
    provider: AnyShareDAVProvider

    def get_display_name(self) -> str:
        return self.node.name

    def get_creation_date(self) -> float | None:
        return self.node.created_timestamp

    def get_last_modified(self) -> float | None:
        return self.node.modified_timestamp

    def get_etag(self) -> str | None:
        return self.node.rev or None

    def support_etag(self) -> bool:
        return bool(self.node.rev)

    def delete(self):
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        return _translate_errors(lambda: self.provider.repository.delete(self.node))

    def handle_move(self, dest_path: str):
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        self.node = _translate_errors(lambda: self.provider.repository.move(self.node, dest_path))
        return True

    def handle_copy(self, dest_path: str, *, depth_infinity: bool):
        raise DAVError(HTTP_NOT_IMPLEMENTED, "COPY is not implemented by the AnyShare gateway")


class AnyShareCollection(_AnyShareResourceMixin, DAVCollection):
    def __init__(self, node: DAVNode, environ: dict[str, Any]) -> None:
        self.node = node
        super().__init__(node.path, environ)

    def get_member_names(self) -> list[str]:
        return _translate_errors(lambda: [node.name for node in self.provider.repository.list_children(self.node)])

    def get_member(self, name: str):
        path = self.provider.repository.child_path(self.node.path, name)
        return self.provider.get_resource_inst(path, self.environ)

    def create_collection(self, name: str):
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        node = _translate_errors(lambda: self.provider.repository.create_collection(self.node, name))
        return AnyShareCollection(node, self.environ)

    def create_empty_resource(self, name: str):
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        path = self.provider.repository.child_path(self.node.path, name)
        node = DAVNode(path=path, name=name, docid=None, is_collection=False)
        return AnyShareFile(node, self.environ, upload_parent=self.node)

    def support_recursive_delete(self) -> bool:
        return True

    def support_recursive_move(self) -> bool:
        return False


class AnyShareFile(_AnyShareResourceMixin, DAVNonCollection):
    def __init__(
        self,
        node: DAVNode,
        environ: dict[str, Any],
        *,
        upload_parent: DAVNode | None = None,
    ) -> None:
        self.node = node
        self.upload_parent = upload_parent
        self._temp_path: str | None = None
        super().__init__(node.path, environ)

    def get_content_length(self) -> int:
        return self.node.size

    def get_content_type(self) -> str:
        return mimetypes.guess_type(self.node.name)[0] or "application/octet-stream"

    def support_ranges(self) -> bool:
        return True

    def get_content(self) -> HTTPRangeReader:
        url, size = _translate_errors(lambda: self.provider.repository.get_download(self.node))
        return HTTPRangeReader(url, size, verify=self.provider.repository.download_verify)

    def begin_write(self, *, content_type: str | None = None):
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        handle = tempfile.NamedTemporaryFile(prefix="anyshare-dav-put-", delete=False)
        self._temp_path = handle.name
        return handle

    def end_write(self, *, with_errors: bool) -> None:
        temp_path = self._temp_path
        self._temp_path = None
        if not temp_path:
            return
        try:
            if with_errors:
                return
            parent = self.upload_parent
            if parent is None:
                parent_path = posixpath.dirname(self.node.path) or "/"
                parent = _translate_errors(lambda: self.provider.repository.resolve(parent_path))
            if parent is None:
                raise DAVError(HTTP_CONFLICT, "Upload parent does not exist")
            self.node = _translate_errors(
                lambda: self.provider.repository.upload(parent, self.node.name, temp_path)
            )
        finally:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass

    def copy_move_single(self, dest_path: str, *, is_move: bool):
        if is_move:
            self.node = _translate_errors(lambda: self.provider.repository.move(self.node, dest_path))
            return
        raise DAVError(HTTP_NOT_IMPLEMENTED, "COPY is not implemented by the AnyShare gateway")

"""Offline tests for the WebDAV gateway and SDK adaptations."""

from __future__ import annotations

import base64
import io
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, call, patch

from anyshare_unofficial import AuthenticatedClient, FileItem, FolderContent
from anyshare_unofficial.models.common import DocLibInfo
from anyshare_unofficial.webdav.app import create_app
from anyshare_unofficial.webdav.cli import _parser
from anyshare_unofficial.webdav.http_file import HTTPRangeReader
from anyshare_unofficial.webdav.provider import AnyShareDAVProvider
from anyshare_unofficial.webdav.repository import AnyShareRepository, DAVNode


NOW = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


class TestWebDAVEnvironment(unittest.TestCase):
    def test_process_environment_supplies_defaults(self) -> None:
        environment = {
            "ANYSHARE_BASE_URL": "https://from-environment.example",
            "ANYSHARE_DAV_HOST": "0.0.0.0",
            "ANYSHARE_DAV_PORT": "9090",
            "ANYSHARE_DAV_READONLY": "true",
            "ANYSHARE_DAV_CACHE_TTL": "12.5",
        }
        with patch.dict(os.environ, environment, clear=True):
            args = _parser().parse_args([])

        self.assertEqual(args.base_url, "https://from-environment.example")
        self.assertEqual(args.host, "0.0.0.0")
        self.assertEqual(args.port, 9090)
        self.assertTrue(args.readonly)
        self.assertEqual(args.cache_ttl, 12.5)

    def test_command_line_overrides_environment_booleans(self) -> None:
        with patch.dict(os.environ, {"ANYSHARE_DAV_READONLY": "true"}, clear=True):
            args = _parser().parse_args(["--no-readonly", "--port", "7000"])
            self.assertFalse(args.readonly)
            self.assertEqual(args.port, 7000)


class TestAuthenticatedPagination(unittest.TestCase):
    def test_iter_folder_follows_markers(self) -> None:
        first = FileItem(
            id="gns://lib/a",
            name="a.txt",
            size=1,
            rev="rev-a",
            created_at=NOW,
            modified_at=NOW,
        )
        second = FileItem(
            id="gns://lib/b",
            name="b.txt",
            size=2,
            rev="rev-b",
            created_at=NOW,
            modified_at=NOW,
        )
        client = object.__new__(AuthenticatedClient)
        client.browse_folder = Mock(  # type: ignore[method-assign]
            side_effect=[
                FolderContent(files=[first], next_marker="next-1"),
                FolderContent(files=[second]),
            ]
        )

        self.assertEqual([item.name for item in client.iter_folder("gns://lib", page_size=1)], ["a.txt", "b.txt"])
        self.assertEqual(
            client.browse_folder.call_args_list,
            [
                call("gns://lib", limit=1, sort=unittest.mock.ANY, direction=unittest.mock.ANY, mode=unittest.mock.ANY, marker=""),
                call("gns://lib", limit=1, sort=unittest.mock.ANY, direction=unittest.mock.ANY, mode=unittest.mock.ANY, marker="next-1"),
            ],
        )


class TestRepository(unittest.TestCase):
    def setUp(self) -> None:
        self.client = Mock()
        self.client.list_doc_libs.return_value = [
            DocLibInfo(
                id="gns://library-1",
                name="My Documents",
                type="user_doc_lib",
                rev="lib-rev",
                created_at=NOW,
                modified_at=NOW,
                created_by={"id": "u", "name": "User", "type": "user"},
                modified_by={"id": "u", "name": "User", "type": "user"},
            )
        ]
        self.client.iter_folder.return_value = iter(
            [
                FileItem(
                    id="gns://library-1/report",
                    name="report.txt",
                    size=7,
                    rev="file-rev",
                    created_at=NOW,
                    modified_at=NOW,
                )
            ]
        )
        self.repository = AnyShareRepository(self.client, cache_ttl=60)

    def test_resolves_virtual_root_library_and_file(self) -> None:
        root = self.repository.resolve("/")
        library = self.repository.resolve("/My Documents")
        file_node = self.repository.resolve("/My Documents/report.txt")

        self.assertTrue(root and root.virtual)
        self.assertEqual(library.docid, "gns://library-1")  # type: ignore[union-attr]
        self.assertEqual(file_node.size, 7)  # type: ignore[union-attr]
        self.assertEqual(file_node.rev, "file-rev")  # type: ignore[union-attr]
        self.client.list_doc_libs.assert_called_once_with()
        self.client.iter_folder.assert_called_once_with("gns://library-1")

    def test_case_insensitive_lookup_for_windows(self) -> None:
        node = self.repository.resolve("/my documents/REPORT.TXT")
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "report.txt")  # type: ignore[union-attr]

    def test_rejects_relative_segments(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.resolve("/My Documents/../secret")


class TestHTTPRangeReader(unittest.TestCase):
    def test_reads_and_seeks_using_ranges(self) -> None:
        first = Mock(status_code=200)
        first.iter_raw.return_value = iter([b"0123456789"])
        ranged = Mock(status_code=206)
        ranged.iter_raw.return_value = iter([b"56789"])
        client = Mock()
        client.build_request.side_effect = lambda method, url, headers: (method, url, headers)
        client.send.side_effect = [first, ranged]

        with patch("anyshare_unofficial.webdav.http_file.httpx.Client", return_value=client) as client_class:
            with HTTPRangeReader("https://download.example/file", 10) as reader:
                self.assertEqual(reader.read(3), b"012")
                self.assertEqual(reader.seek(5), 5)
                self.assertEqual(reader.read(3), b"567")

        self.assertEqual(client.build_request.call_args_list[1].kwargs["headers"], {"Range": "bytes=5-"})
        client_class.assert_called_once_with(timeout=60.0, follow_redirects=True, verify=True)
        first.close.assert_called_once_with()


class _StaticRepository:
    def __init__(self) -> None:
        self.root_node = DAVNode(path="/", name="", docid=None, is_collection=True, virtual=True, modified_at=NOW)
        self.library = DAVNode(path="/Library", name="Library", docid="gns://lib", is_collection=True, rev="lib", modified_at=NOW)
        self.file: DAVNode | None = None
        self.uploaded = b""

    def resolve(self, path: str):
        if path != "/":
            path = path.rstrip("/")
        nodes = {"/": self.root_node, "/Library": self.library}
        if self.file:
            nodes[self.file.path] = self.file
        return nodes.get(path)

    def list_children(self, node: DAVNode):
        if node.path == "/":
            return [self.library]
        return [self.file] if node.path == "/Library" and self.file else []

    @staticmethod
    def child_path(parent: str, name: str) -> str:
        return f"/{name}" if parent == "/" else f"{parent}/{name}"

    def upload(self, parent: DAVNode, name: str, local_path: str):
        with open(local_path, "rb") as source:
            self.uploaded = source.read()
        self.file = DAVNode(
            path=f"{parent.path}/{name}",
            name=name,
            docid="gns://lib/upload",
            is_collection=False,
            size=len(self.uploaded),
            rev="uploaded-rev",
            modified_at=NOW,
        )
        return self.file


class TestWsgiDAVApp(unittest.TestCase):
    @staticmethod
    def _environ(method: str, path: str, body: bytes = b"") -> dict[str, object]:
        auth = base64.b64encode(b"dav:secret").decode("ascii")
        return {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "SCRIPT_NAME": "",
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "80",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": io.BytesIO(body),
            "wsgi.errors": io.StringIO(),
            "wsgi.multithread": False,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
            "CONTENT_LENGTH": str(len(body)),
            "HTTP_AUTHORIZATION": f"Basic {auth}",
        }

    def test_authenticated_propfind_lists_library(self) -> None:
        provider = AnyShareDAVProvider(_StaticRepository())  # type: ignore[arg-type]
        app = create_app(provider, username="dav", password="secret", verbose=0)
        body = b'<?xml version="1.0"?><propfind xmlns="DAV:"><allprop/></propfind>'
        environ = self._environ("PROPFIND", "/", body)
        environ.update({"CONTENT_TYPE": "application/xml", "HTTP_DEPTH": "1"})
        status: list[str] = []

        def start_response(value: str, headers: list[tuple[str, str]], exc_info=None):
            status.append(value)

        response = b"".join(app(environ, start_response))
        self.assertEqual(status, ["207 Multi-Status"])
        self.assertIn(b"Library", response)

    def test_put_uploads_request_body(self) -> None:
        repository = _StaticRepository()
        provider = AnyShareDAVProvider(repository)  # type: ignore[arg-type]
        app = create_app(provider, username="dav", password="secret", verbose=0)
        environ = self._environ("PUT", "/Library/hello.txt", b"hello dav")
        environ["CONTENT_TYPE"] = "text/plain"
        status: list[str] = []

        def start_response(value: str, headers: list[tuple[str, str]], exc_info=None):
            status.append(value)

        b"".join(app(environ, start_response))
        self.assertEqual(status, ["201 Created"])
        self.assertEqual(repository.uploaded, b"hello dav")


if __name__ == "__main__":
    unittest.main()

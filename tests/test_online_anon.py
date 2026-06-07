"""Online integration tests for AnonymousClient.

Requires ``TEST_ONLINE=1``, ``TEST_BASE_URL``, and ``TEST_SHARING_LINK``.
Upload tests require a sharing link with upload permission.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from tests import load_test_env, online_tests_enabled

_env = load_test_env()
TEST_BASE_URL = _env.get("TEST_BASE_URL", "")
TEST_SHARING_LINK = _env.get("TEST_SHARING_LINK", "")

_HAS_BASE_URL = online_tests_enabled(_env) and bool(TEST_BASE_URL) and "example." not in TEST_BASE_URL
_HAS_SHARING_LINK = bool(TEST_SHARING_LINK) and "example." not in TEST_SHARING_LINK and _HAS_BASE_URL

_skip_no_link = unittest.skipUnless(
    _HAS_SHARING_LINK,
    "TEST_ONLINE=1, TEST_BASE_URL, and TEST_SHARING_LINK are required for online anonymous tests",
)

# ---------------------------------------------------------------------------
# Read-only tests (only need a sharing link)
# ---------------------------------------------------------------------------


class TestAnonymousClientInit(unittest.TestCase):

    @_skip_no_link
    def test_init_succeeds(self) -> None:
        from anyshare_unofficial import AnonymousClient

        client = AnonymousClient(TEST_SHARING_LINK, base_url=TEST_BASE_URL)
        try:
            self.assertIsNotNone(client._sharing_id)
            self.assertIn("Bearer", client._client.headers.get("Authorization", ""))
        finally:
            client.close()

    @_skip_no_link
    def test_context_manager(self) -> None:
        from anyshare_unofficial import AnonymousClient

        with AnonymousClient(TEST_SHARING_LINK, base_url=TEST_BASE_URL) as client:
            self.assertIsNotNone(client._sharing_id)


class TestAnonymousListEntries(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_SHARING_LINK:
            return
        from anyshare_unofficial import AnonymousClient

        cls.client = AnonymousClient(TEST_SHARING_LINK, base_url=TEST_BASE_URL)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.close()

    @_skip_no_link
    def test_list_entries_returns_nonempty(self) -> None:
        entries = self.client.list_entries()
        self.assertIsInstance(entries, list)
        self.assertGreater(len(entries), 0, "Sharing link should have at least one entry")

    @_skip_no_link
    def test_list_entries_are_file_or_folder(self) -> None:
        from anyshare_unofficial import FileItem, FolderItem

        entries = self.client.list_entries()
        for e in entries[:10]:  # check first 10
            self.assertIsInstance(e, (FileItem, FolderItem))
            self.assertTrue(e.id.startswith("gns://"), f"ID should be GNS path: {e.id}")
            self.assertIsInstance(e.name, str)
            self.assertGreater(len(e.name), 0)

    @_skip_no_link
    def test_get_first_entry(self) -> None:
        from anyshare_unofficial import FileItem, FolderItem

        first = self.client.get_first_entry()
        self.assertIsInstance(first, (FileItem, FolderItem))


class TestAnonymousBrowseFolder(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_SHARING_LINK:
            return
        from anyshare_unofficial import AnonymousClient

        cls.client = AnonymousClient(TEST_SHARING_LINK, base_url=TEST_BASE_URL)
        cls._first_entry = cls.client.get_first_entry()

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.close()

    @_skip_no_link
    def test_browse_first_entry(self) -> None:
        from anyshare_unofficial import FolderContent

        # Only browse if the first entry is a folder
        if not self._first_entry.is_dir:
            self.skipTest("First entry is not a folder")

        content = self.client.browse_folder(self._first_entry.id)
        self.assertIsInstance(content, FolderContent)
        self.assertIsInstance(content.dirs, list)
        self.assertIsInstance(content.files, list)

    @_skip_no_link
    def test_browse_with_sorting(self) -> None:
        from anyshare_unofficial import FolderContent, SortDirection, SortField

        if not self._first_entry.is_dir:
            self.skipTest("First entry is not a folder")

        content = self.client.browse_folder(
            self._first_entry.id,
            sort=SortField.TIME,
            direction=SortDirection.DESC,
            limit=10,
        )
        self.assertIsInstance(content, FolderContent)
        self.assertLessEqual(len(content.dirs) + len(content.files), 10)

    @_skip_no_link
    def test_browse_files_only(self) -> None:
        from anyshare_unofficial import ObjectMode

        if not self._first_entry.is_dir:
            self.skipTest("First entry is not a folder")

        content = self.client.browse_folder(self._first_entry.id, mode=ObjectMode.FILES)
        self.assertEqual(content.dirs, [])

    @_skip_no_link
    def test_browse_dirs_only(self) -> None:
        from anyshare_unofficial import ObjectMode

        if not self._first_entry.is_dir:
            self.skipTest("First entry is not a folder")

        content = self.client.browse_folder(self._first_entry.id, mode=ObjectMode.DIRS)
        self.assertEqual(content.files, [])

    @_skip_no_link
    def test_invalid_gns_path_raises(self) -> None:
        from anyshare_unofficial import AnyShareInputError

        with self.assertRaises(AnyShareInputError):
            self.client.browse_folder("not-a-gns-path")


class TestAnonymousDownload(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_SHARING_LINK:
            return
        from anyshare_unofficial import AnonymousClient, FileItem

        cls.client = AnonymousClient(TEST_SHARING_LINK, base_url=TEST_BASE_URL)
        entries = cls.client.list_entries()
        cls._first_file: FileItem | None = None
        for e in entries:
            if not e.is_dir:
                cls._first_file = e  # type: ignore
                break

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.close()

    @_skip_no_link
    def test_get_download_url_returns_auth(self) -> None:
        from anyshare_unofficial import DownloadAuth, OsDownloadResult

        if self._first_file is None:
            self.skipTest("No file found in sharing link")

        auth, result = self.client.get_download_url(self._first_file)
        self.assertIsInstance(auth, DownloadAuth)
        self.assertIsInstance(result, OsDownloadResult)
        self.assertTrue(auth.url.startswith("https://"), f"Unexpected URL: {auth.url}")
        self.assertEqual(auth.method, "GET")

    @_skip_no_link
    def test_download_url_for_dir_raises(self) -> None:
        from anyshare_unofficial import AnyShareInputError, FolderItem

        first = self.client.get_first_entry()
        if not first.is_dir:
            self.skipTest("First entry is not a folder")

        with self.assertRaises(AnyShareInputError):
            self.client.get_download_url(first)  # type: ignore


# ---------------------------------------------------------------------------
# Upload tests (require upload permission on the sharing link)
# ---------------------------------------------------------------------------


class TestAnonymousUpload(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_SHARING_LINK:
            return
        from anyshare_unofficial import AnonymousClient

        cls.client = AnonymousClient(TEST_SHARING_LINK, base_url=TEST_BASE_URL)
        cls._target_dir = cls.client.get_first_entry()
        if not cls._target_dir.is_dir:
            # Find a folder
            entries = cls.client.list_entries()
            for e in entries:
                if e.is_dir:
                    cls._target_dir = e
                    break

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.close()

    @_skip_no_link
    def test_upload_file(self) -> None:
        from anyshare_unofficial import OnDup

        if not self._target_dir.is_dir:
            self.skipTest("No folder found to upload into")

        # Create a tiny temp file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("AnyShare upload test content.")
            tmp_path = f.name

        try:
            result = self.client.upload_file(
                tmp_path,
                self._target_dir.id,
                ondup=OnDup.OVERWRITE,
            )
            self.assertIsNotNone(result)
            self.assertIsInstance(result.name, str)
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()

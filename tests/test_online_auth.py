"""Online integration tests for AuthenticatedClient.

Requires ``TEST_ONLINE=1``, ``TEST_BASE_URL``, and ``TEST_AUTH_COOKIE``.
State-modifying tests also require ``TEST_DIR_PATH``.
"""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from tests import load_test_env, online_tests_enabled

_env = load_test_env()
TEST_BASE_URL = _env.get("TEST_BASE_URL", "")
TEST_AUTH_COOKIE = _env.get("TEST_AUTH_COOKIE", "")
TEST_DIR_PATH = _env.get("TEST_DIR_PATH", "")

_HAS_BASE_URL = online_tests_enabled(_env) and bool(TEST_BASE_URL) and "example." not in TEST_BASE_URL
_HAS_COOKIE = bool(TEST_AUTH_COOKIE) and "your_session" not in TEST_AUTH_COOKIE and _HAS_BASE_URL
_HAS_TEST_DIR = bool(TEST_DIR_PATH) and "your_test" not in TEST_DIR_PATH and _HAS_COOKIE

_skip_no_cookie = unittest.skipUnless(
    _HAS_COOKIE,
    "TEST_ONLINE=1, TEST_BASE_URL, and TEST_AUTH_COOKIE are required for online authenticated tests",
)
_skip_no_test_dir = unittest.skipUnless(
    _HAS_TEST_DIR,
    "TEST_ONLINE=1, TEST_DIR_PATH, TEST_BASE_URL, and TEST_AUTH_COOKIE are required for online stateful tests",
)


# ======================================================================
# Read-only tests — only need a valid cookie
# ======================================================================


class TestAuthenticatedInit(unittest.TestCase):

    @_skip_no_cookie
    def test_init_succeeds(self) -> None:
        from anyshare_unofficial import AuthenticatedClient

        client = AuthenticatedClient(TEST_AUTH_COOKIE, base_url=TEST_BASE_URL)
        try:
            self.assertIn("Bearer", client._client.headers.get("Authorization", ""))
        finally:
            client.close()

    @_skip_no_cookie
    def test_refresh_token(self) -> None:
        from anyshare_unofficial import AuthenticatedClient

        client = AuthenticatedClient(TEST_AUTH_COOKIE, base_url=TEST_BASE_URL)
        try:
            client.refresh_token(force=True)
            self.assertIn("Bearer", client._client.headers.get("Authorization", ""))
        finally:
            client.close()

    @_skip_no_cookie
    def test_missing_auth_cookie_raises(self) -> None:
        from anyshare_unofficial import AnyShareAuthError, AuthenticatedClient

        with self.assertRaises(AnyShareAuthError):
            AuthenticatedClient("bad_cookie=foo_bar", base_url=TEST_BASE_URL)


class TestUserAndAuth(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_COOKIE:
            return
        from anyshare_unofficial import AuthenticatedClient

        cls.client = AuthenticatedClient(TEST_AUTH_COOKIE, base_url=TEST_BASE_URL)  # type: ignore[has-type]

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.close()

    @_skip_no_cookie
    def test_get_current_user(self) -> None:
        from anyshare_unofficial import UserInfo

        user = self.client.get_current_user()
        self.assertIsInstance(user, UserInfo)
        self.assertIsInstance(user.name, str)
        self.assertGreater(len(user.name), 0, "User name should not be empty")
        self.assertIsInstance(user.userid, str)

    @_skip_no_cookie
    def test_get_config(self) -> None:
        from anyshare_unofficial import AuthConfig

        config = self.client.get_config()
        self.assertIsInstance(config, AuthConfig)

    @_skip_no_cookie
    def test_get_user_basic_info(self) -> None:
        from anyshare_unofficial import UserBasicInfo

        user = self.client.get_current_user()
        info = self.client.get_user_basic_info(user.userid)
        self.assertIsInstance(info, UserBasicInfo)
        self.assertIsInstance(info.directdepinfos, list)
        if info.directdepinfos:
            dep = info.directdepinfos[0]
            self.assertTrue(hasattr(dep, "deppath"))
            self.assertTrue(hasattr(dep, "depid"))
            self.assertTrue(hasattr(dep, "name"))

    @_skip_no_cookie
    def test_get_login_config(self) -> None:
        from anyshare_unofficial import LoginConfig

        config = self.client.get_login_config()
        self.assertIsInstance(config, LoginConfig)


class TestDocLibs(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_COOKIE:
            return
        from anyshare_unofficial import AuthenticatedClient

        cls.client = AuthenticatedClient(TEST_AUTH_COOKIE, base_url=TEST_BASE_URL)  # type: ignore[has-type]

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.close()

    @_skip_no_cookie
    def test_list_doc_libs(self) -> None:
        from anyshare_unofficial import DocLibInfo

        libs = self.client.list_doc_libs()
        self.assertIsInstance(libs, list)
        self.assertGreater(len(libs), 0, "User should have at least one doc lib")
        for lib in libs:
            self.assertIsInstance(lib, DocLibInfo)
            self.assertTrue(lib.id.startswith("gns://"))

    @_skip_no_cookie
    def test_list_doc_libs_with_type_filter(self) -> None:
        from anyshare_unofficial import DocLibType

        libs = self.client.list_doc_libs(type_=[DocLibType.USER])
        for lib in libs:
            self.assertEqual(lib.type, "user_doc_lib")

    @_skip_no_cookie
    def test_list_classified_doc_libs(self) -> None:
        libs = self.client.list_classified_doc_libs()
        self.assertIsInstance(libs, list)


class TestBrowseFolder(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_COOKIE:
            return
        from anyshare_unofficial import AuthenticatedClient

        cls.client = AuthenticatedClient(TEST_AUTH_COOKIE, base_url=TEST_BASE_URL)  # type: ignore[has-type]
        libs = cls.client.list_doc_libs()
        if libs:
            cls._root_gns = libs[0].id
        else:
            cls._root_gns = ""

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.close()

    @_skip_no_cookie
    def test_browse_root_of_first_lib(self) -> None:
        from anyshare_unofficial import FolderContent

        if not self._root_gns:
            self.skipTest("No doc lib available")

        content = self.client.browse_folder(self._root_gns, limit=5)
        self.assertIsInstance(content, FolderContent)
        self.assertIsNotNone(content.doc_lib)

    @_skip_no_cookie
    def test_entries_have_expected_shape(self) -> None:
        from anyshare_unofficial import FileItem, FolderItem

        if not self._root_gns:
            self.skipTest("No doc lib available")

        content = self.client.browse_folder(self._root_gns, limit=20)
        for d in content.dirs:
            self.assertIsInstance(d, FolderItem)
            self.assertTrue(d.is_dir)
            self.assertTrue(d.id.startswith("gns://"))
        for f in content.files:
            self.assertIsInstance(f, FileItem)
            self.assertFalse(f.is_dir)
            self.assertTrue(f.id.startswith("gns://"))


class TestQuotaAndPermissions(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_COOKIE:
            return
        from anyshare_unofficial import AuthenticatedClient

        cls.client = AuthenticatedClient(TEST_AUTH_COOKIE, base_url=TEST_BASE_URL)  # type: ignore[has-type]
        libs = cls.client.list_doc_libs()
        cls._test_docid = libs[0].id if libs else ""

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.close()

    @_skip_no_cookie
    def test_get_quota(self) -> None:
        from anyshare_unofficial import QuotaInfo

        quota = self.client.get_quota()
        self.assertIsInstance(quota, QuotaInfo)
        self.assertGreaterEqual(quota.allocated, 0)
        self.assertGreaterEqual(quota.used, 0)

    @_skip_no_cookie
    def test_check_permission(self) -> None:
        if not self._test_docid:
            self.skipTest("No doc lib available")

        result = self.client.check_permission(self._test_docid, "display")
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, "result"))
        self.assertEqual(result.result, 0, "Permission should be granted (result=0)")

    @_skip_no_cookie
    def test_get_share_config(self) -> None:
        from anyshare_unofficial import ShareDocConfig

        config = self.client.get_share_config()
        self.assertIsInstance(config, ShareDocConfig)

    @_skip_no_cookie
    def test_get_lock_info(self) -> None:
        if not self._test_docid:
            self.skipTest("No doc lib available")

        info = self.client.get_lock_info(self._test_docid)
        self.assertIsNotNone(info)
        self.assertTrue(hasattr(info, "islocked"))


class TestContactsAndDepartments(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_COOKIE:
            return
        from anyshare_unofficial import AuthenticatedClient

        cls.client = AuthenticatedClient(TEST_AUTH_COOKIE, base_url=TEST_BASE_URL)  # type: ignore[has-type]

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.close()

    @_skip_no_cookie
    def test_get_contact_groups(self) -> None:
        from anyshare_unofficial import ContactGroup

        groups = self.client.get_contact_groups()
        self.assertIsInstance(groups, list)
        for g in groups:
            self.assertIsInstance(g, ContactGroup)
            self.assertIsInstance(g.id, str)
            self.assertIsInstance(g.groupname, str)

    @_skip_no_cookie
    def test_get_contact_persons(self) -> None:
        groups = self.client.get_contact_groups()
        if not groups:
            self.skipTest("No contact groups available")

        persons = self.client.get_contact_persons(groups[0].id)
        self.assertIsInstance(persons, list)
        for person in persons:
            self.assertIsInstance(person, dict)

    @_skip_no_cookie
    def test_get_department_roots(self) -> None:
        from anyshare_unofficial import DepartmentInfo

        roots = self.client.get_department_roots()
        self.assertIsInstance(roots, list)
        for d in roots:
            self.assertIsInstance(d, DepartmentInfo)
            self.assertIsInstance(d.depid, str)
            self.assertIsInstance(d.name, str)

    @_skip_no_cookie
    def test_get_sub_departments(self) -> None:
        from anyshare_unofficial import DepartmentInfo

        roots = self.client.get_department_roots()
        if not roots:
            self.skipTest("No departments available")

        subs = self.client.get_sub_departments(roots[0].depid)
        self.assertIsInstance(subs, list)
        for d in subs:
            self.assertIsInstance(d, DepartmentInfo)
            self.assertIsInstance(d.depid, str)
            self.assertIsInstance(d.name, str)

    @_skip_no_cookie
    def test_get_department_users(self) -> None:
        from anyshare_unofficial import DepartmentUserInfo

        roots = self.client.get_department_roots()
        if not roots:
            self.skipTest("No departments available")

        users = self.client.get_department_users(roots[0].depid)
        self.assertIsInstance(users, list)
        for user in users:
            self.assertIsInstance(user, DepartmentUserInfo)
            self.assertIsInstance(user.userid, str)
            self.assertIsInstance(user.name, str)


class TestShareManagement(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_COOKIE:
            return
        from anyshare_unofficial import AuthenticatedClient

        cls.client = AuthenticatedClient(TEST_AUTH_COOKIE, base_url=TEST_BASE_URL)  # type: ignore[has-type]

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.close()

    @_skip_no_cookie
    def test_list_shares_with_users(self) -> None:
        result = self.client.list_shares_with_users(limit=5)
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, "entries"))

    @_skip_no_cookie
    def test_list_shares_with_anyone(self) -> None:
        result = self.client.list_shares_with_anyone(limit=5)
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, "entries"))

    @_skip_no_cookie
    def test_list_blocked_doc_libs(self) -> None:
        from anyshare_unofficial import BlockedDocLibListResult

        result = self.client.list_blocked_doc_libs()
        self.assertIsInstance(result, BlockedDocLibListResult)
        self.assertIsInstance(result.entries, list)
        self.assertIsInstance(result.total_count, int)


class TestMessages(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_COOKIE:
            return
        from anyshare_unofficial import AuthenticatedClient

        cls.client = AuthenticatedClient(TEST_AUTH_COOKIE, base_url=TEST_BASE_URL)  # type: ignore[has-type]

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.close()

    @_skip_no_cookie
    def test_get_notifications(self) -> None:
        from anyshare_unofficial import NotificationListResult

        notifications = self.client.get_notifications(limit=5)
        self.assertIsInstance(notifications, NotificationListResult)
        self.assertIsInstance(notifications.entries, list)
        self.assertIsInstance(notifications.total_count, int)


# ======================================================================
# State-modifying tests — require TEST_DIR_PATH
# ======================================================================


class _StateModifyingMixin:
    """Mixin that creates a unique test subdirectory inside TEST_DIR_PATH
    and cleans it up after all tests in the class complete."""

    client: object
    _test_subdir_gns: str
    _test_subdir_name: str

    @classmethod
    def _setup_test_dir(cls) -> None:
        from anyshare_unofficial import AuthenticatedClient, OnDup
        from anyshare_unofficial.utils.gns import build_gns_path, parse_gns_path

        client = AuthenticatedClient(TEST_AUTH_COOKIE, base_url=TEST_BASE_URL)
        cls.client = client

        segments = parse_gns_path(TEST_DIR_PATH)
        ts = int(time.time() * 1000)
        cls._test_subdir_name = f"_anyshare_test_{ts}"
        result = client.create_directory(TEST_DIR_PATH, cls._test_subdir_name, ondup=OnDup.RENAME)
        cls._test_subdir_gns = build_gns_path(*segments, result.docid.split("/")[-1])

    @classmethod
    def _teardown_test_dir(cls) -> None:
        if hasattr(cls, "client") and hasattr(cls, "_test_subdir_gns"):
            try:
                cls.client.delete_file(cls._test_subdir_gns)  # type: ignore[union-attr]
            except Exception:
                pass  # Best-effort cleanup
        if hasattr(cls, "client"):
            cls.client.close()  # type: ignore[union-attr]


class TestDirectoryCRUD(_StateModifyingMixin, unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_TEST_DIR:
            return
        cls._setup_test_dir()

    @classmethod
    def tearDownClass(cls) -> None:
        if not _HAS_TEST_DIR:
            return
        cls._teardown_test_dir()

    @_skip_no_test_dir
    def test_create_directory(self) -> None:
        from anyshare_unofficial import DirCreateResult, OnDup

        result = self.client.create_directory(  # type: ignore[attr-defined]
            self._test_subdir_gns, "nested_folder", ondup=OnDup.RENAME
        )
        self.assertIsInstance(result, DirCreateResult)
        self.assertTrue(result.docid.startswith("gns://"))

    @_skip_no_test_dir
    def test_rename_directory(self) -> None:
        from anyshare_unofficial import OnDup

        # Create a dir first
        r = self.client.create_directory(  # type: ignore[attr-defined]
            self._test_subdir_gns, "to_rename", ondup=OnDup.RENAME
        )
        # Rename it
        self.client.rename_directory(r.docid, "renamed_folder", ondup=OnDup.RENAME)  # type: ignore[attr-defined]

    @_skip_no_test_dir
    def test_get_suggest_dir_name(self) -> None:
        name = self.client.get_suggest_dir_name(self._test_subdir_gns, "test_folder")  # type: ignore[attr-defined]
        self.assertIsInstance(name, str)
        self.assertGreater(len(name), 0)


class TestFileCRUD(_StateModifyingMixin, unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_TEST_DIR:
            return
        cls._setup_test_dir()

    @classmethod
    def tearDownClass(cls) -> None:
        if not _HAS_TEST_DIR:
            return
        cls._teardown_test_dir()

    def _upload_tmp_file(self, content: str = "test content") -> str:
        from anyshare_unofficial import OnDup

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write(content)
            tmp_path = f.name

        try:
            end_result = self.client.upload_file_s3(  # type: ignore[attr-defined]
                tmp_path,
                self._test_subdir_gns,
                ondup=OnDup.OVERWRITE,
            )
            # Look up the uploaded file's docid by browsing the test dir
            content_dir = self.client.browse_folder(self._test_subdir_gns)  # type: ignore[attr-defined]
            for f_item in content_dir.files:
                if f_item.name == Path(tmp_path).name:
                    return f_item.id
            # Fallback: construct from test dir path
            return f"{self._test_subdir_gns}/{end_result.name}"
        finally:
            os.unlink(tmp_path)

    @_skip_no_test_dir
    def test_upload_s3_and_delete(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("Hello from AnyShare test!")
            tmp_path = f.name

        try:
            from anyshare_unofficial import OnDup

            result = self.client.upload_file_s3(  # type: ignore[attr-defined]
                tmp_path, self._test_subdir_gns, ondup=OnDup.OVERWRITE
            )
            self.assertIsInstance(result.name, str)
            self.assertGreater(len(result.name), 0)

            # Find the uploaded file to get its docid
            content_dir = self.client.browse_folder(self._test_subdir_gns)  # type: ignore[attr-defined]
            uploaded = None
            for f_item in content_dir.files:
                if f_item.name == Path(tmp_path).name:
                    uploaded = f_item
                    break

            if uploaded is not None:
                self.client.delete_file(uploaded.id)  # type: ignore[attr-defined]
        finally:
            os.unlink(tmp_path)

    @_skip_no_test_dir
    def test_get_file_metadata(self) -> None:
        from anyshare_unofficial import FileMetadata

        docid = self._upload_tmp_file("metadata test")
        try:
            meta = self.client.get_file_metadata(docid)  # type: ignore[attr-defined]
            self.assertIsInstance(meta, FileMetadata)
            self.assertEqual(meta.docid, docid)
        finally:
            self.client.delete_file(docid)  # type: ignore[attr-defined]

    @_skip_no_test_dir
    def test_get_item_detail(self) -> None:
        from anyshare_unofficial import ItemDetail
        from anyshare_unofficial.utils.gns import parse_gns_path

        docid = self._upload_tmp_file("detail test")
        try:
            # get_item_detail expects a short object ID (last GNS segment)
            object_id = parse_gns_path(docid)[-1]
            detail = self.client.get_item_detail(object_id)  # type: ignore[attr-defined]
            self.assertIsInstance(detail, ItemDetail)
        finally:
            self.client.delete_file(docid)  # type: ignore[attr-defined]

    @_skip_no_test_dir
    def test_move_file(self) -> None:
        from anyshare_unofficial import MoveResult, OnDup

        # Create a subdir to move into
        r = self.client.create_directory(  # type: ignore[attr-defined]
            self._test_subdir_gns, "move_dest", ondup=OnDup.RENAME
        )
        dest_docid = r.docid

        docid = self._upload_tmp_file("move me")
        try:
            result = self.client.move_file(docid, dest_docid, ondup=OnDup.OVERWRITE)  # type: ignore[attr-defined]
            self.assertIsInstance(result, MoveResult)
        finally:
            # Clean up: delete moved file (docid may have changed)
            try:
                self.client.delete_file(docid)  # type: ignore[attr-defined]
            except Exception:
                pass

    @_skip_no_test_dir
    def test_get_suggest_name(self) -> None:
        # getsuggestname expects a PARENT DIRECTORY docid, not a file docid
        name = self.client.get_suggest_name(self._test_subdir_gns, "test_file_name")  # type: ignore[attr-defined]
        self.assertIsInstance(name, str)
        self.assertGreater(len(name), 0)


class TestUploadS3(_StateModifyingMixin, unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_TEST_DIR:
            return
        cls._setup_test_dir()

    @classmethod
    def tearDownClass(cls) -> None:
        if not _HAS_TEST_DIR:
            return
        cls._teardown_test_dir()

    @_skip_no_test_dir
    def test_upload_s3_and_download(self) -> None:
        from anyshare_unofficial import OnDup, OsEndUploadResult

        content = "S3 upload test content."
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write(content)
            tmp_path = f.name

        try:
            result = self.client.upload_file_s3(  # type: ignore[attr-defined]
                tmp_path, self._test_subdir_gns, ondup=OnDup.OVERWRITE
            )
            self.assertIsInstance(result, OsEndUploadResult)
            self.assertIsInstance(result.name, str)

            # Download the uploaded file to verify
            dest_dir = tempfile.mkdtemp()
            try:
                docid = f"{self._test_subdir_gns}/{result.name}"
                # Try to get download URL — the docid might need to be the
                # actual GNS path; browse the test dir to find the uploaded file
                content_dir = self.client.browse_folder(self._test_subdir_gns)  # type: ignore[attr-defined]
                uploaded = None
                for f_item in content_dir.files:
                    if f_item.name == Path(tmp_path).name:
                        uploaded = f_item
                        break

                if uploaded is not None:
                    downloaded = self.client.download_file(  # type: ignore[attr-defined]
                        uploaded.id,
                        dest_dir,
                        savename=uploaded.name,
                    )
                    self.assertTrue(
                        Path(downloaded).exists(),
                        f"Downloaded file should exist at {downloaded}",
                    )
                    downloaded_content = Path(downloaded).read_text()
                    self.assertEqual(downloaded_content, content)

                    # Clean up the uploaded file on the server
                    self.client.delete_file(uploaded.id)  # type: ignore[attr-defined]
            finally:
                # Clean up local download dir
                import shutil

                shutil.rmtree(dest_dir, ignore_errors=True)
        finally:
            os.unlink(tmp_path)


class TestPreduploadCheck(_StateModifyingMixin, unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_TEST_DIR:
            return
        cls._setup_test_dir()

    @classmethod
    def tearDownClass(cls) -> None:
        if not _HAS_TEST_DIR:
            return
        cls._teardown_test_dir()

    @_skip_no_test_dir
    def test_predupload_check(self) -> None:
        import hashlib

        data = b"predupload check data"
        result = self.client.predupload_check(  # type: ignore[attr-defined]
            file_size=len(data),
            slice_md5=hashlib.md5(data).hexdigest(),
        )
        self.assertIsInstance(result, bool)


class TestWalkFolder(_StateModifyingMixin, unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not _HAS_TEST_DIR:
            return
        cls._setup_test_dir()

    @classmethod
    def tearDownClass(cls) -> None:
        if not _HAS_TEST_DIR:
            return
        cls._teardown_test_dir()

    @_skip_no_test_dir
    def test_walk_folder_on_test_dir(self) -> None:
        from anyshare_unofficial import FileItem

        # Upload a small file first so there's something to walk
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("walk test")
            tmp_path = f.name

        try:
            from anyshare_unofficial import OnDup

            result = self.client.upload_file_s3(  # type: ignore[attr-defined]
                tmp_path, self._test_subdir_gns, ondup=OnDup.OVERWRITE
            )

            files = self.client.walk_folder(self._test_subdir_gns)  # type: ignore[attr-defined]
            self.assertIsInstance(files, list)
            for f_item in files:
                self.assertIsInstance(f_item, FileItem)
                self.assertFalse(f_item.is_dir)

            # Clean up: find and delete the uploaded file
            content_dir = self.client.browse_folder(self._test_subdir_gns)  # type: ignore[attr-defined]
            for f_item in content_dir.files:
                if f_item.name == Path(tmp_path).name:
                    self.client.delete_file(f_item.id)  # type: ignore[attr-defined]
                    break
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()

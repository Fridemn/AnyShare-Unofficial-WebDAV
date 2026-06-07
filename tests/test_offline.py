"""Offline unit tests for utilities, models, and client helper behavior."""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import Mock

# ---------------------------------------------------------------------------
# Package-level imports
# ---------------------------------------------------------------------------


class TestPackageImports(unittest.TestCase):

    def test_all_exports_present(self) -> None:
        import anyshare_unofficial

        for name in anyshare_unofficial.__all__:
            self.assertTrue(
                hasattr(anyshare_unofficial, name),
                f"__all__ lists '{name}' but it is not importable",
            )


# ---------------------------------------------------------------------------
# GNS path utilities
# ---------------------------------------------------------------------------


class TestGnsUtils(unittest.TestCase):

    def test_is_gns_path_positive(self) -> None:
        from anyshare_unofficial.utils.gns import is_gns_path

        self.assertTrue(is_gns_path("gns://A/B/C"))

    def test_is_gns_path_negative(self) -> None:
        from anyshare_unofficial.utils.gns import is_gns_path

        self.assertFalse(is_gns_path("/normal/path"))
        self.assertFalse(is_gns_path("gns://"))
        self.assertFalse(is_gns_path(""))

    def test_parse_gns_path_normal(self) -> None:
        from anyshare_unofficial.utils.gns import parse_gns_path

        self.assertEqual(parse_gns_path("gns://A/B/C"), ["A", "B", "C"])

    def test_parse_gns_path_single(self) -> None:
        from anyshare_unofficial.utils.gns import parse_gns_path

        self.assertEqual(parse_gns_path("gns://DOCLIB123"), ["DOCLIB123"])

    def test_parse_gns_path_invalid_raises(self) -> None:
        from anyshare_unofficial.utils.gns import parse_gns_path

        with self.assertRaises(ValueError):
            parse_gns_path("not-gns")

    def test_build_gns_path(self) -> None:
        from anyshare_unofficial.utils.gns import build_gns_path

        self.assertEqual(build_gns_path("A", "B", "C"), "gns://A/B/C")

    def test_build_gns_path_single(self) -> None:
        from anyshare_unofficial.utils.gns import build_gns_path

        self.assertEqual(build_gns_path("ROOT"), "gns://ROOT")

    def test_roundtrip(self) -> None:
        from anyshare_unofficial.utils.gns import build_gns_path, parse_gns_path

        original = "gns://LIB/FOLDER/FILE"
        self.assertEqual(build_gns_path(*parse_gns_path(original)), original)

    def test_quote_gns_path(self) -> None:
        from anyshare_unofficial.utils.gns import quote_gns_path

        quoted = quote_gns_path("gns://A/B")
        # Should be URL-safe (forward slashes become %2F)
        self.assertNotIn("/", quoted.removeprefix("gns%3A%2F%2F"))


# ---------------------------------------------------------------------------
# Cookie parsing
# ---------------------------------------------------------------------------


class TestCookieParsing(unittest.TestCase):

    def test_normal_cookie_string(self) -> None:
        from anyshare_unofficial.utils.cookie import parse_cookie_string

        result = parse_cookie_string("a=1; b=2; c=3")
        self.assertDictEqual(result, {"a": "1", "b": "2", "c": "3"})

    def test_cookie_with_special_chars(self) -> None:
        from anyshare_unofficial.utils.cookie import parse_cookie_string

        result = parse_cookie_string("Authorization=Bearer%20xxx; JSESSIONID=abc123")
        self.assertEqual(result["Authorization"], "Bearer%20xxx")
        self.assertEqual(result["JSESSIONID"], "abc123")

    def test_empty_cookie_string(self) -> None:
        from anyshare_unofficial.utils.cookie import parse_cookie_string

        self.assertDictEqual(parse_cookie_string(""), {})

    def test_cookie_without_equals(self) -> None:
        from anyshare_unofficial.utils.cookie import parse_cookie_string

        result = parse_cookie_string("flag")
        self.assertDictEqual(result, {"flag": ""})


# ---------------------------------------------------------------------------
# LocalFile
# ---------------------------------------------------------------------------


class TestLocalFile(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        self.tmp.write(b"Hello, AnyShare!")
        self.tmp.close()

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_from_path(self) -> None:
        from anyshare_unofficial.utils.file import LocalFile

        lf = LocalFile.from_path(self.tmp.name)
        try:
            self.assertEqual(lf.name, Path(self.tmp.name).name)
            self.assertEqual(lf.size, 16)  # "Hello, AnyShare!" = 16 bytes
            expected_md5 = hashlib.md5(b"Hello, AnyShare!").hexdigest().lower()
            expected_crc32 = f"{zlib.crc32(b'Hello, AnyShare!'):08x}"
            self.assertEqual(lf.md5, expected_md5)
            self.assertEqual(lf.crc32, expected_crc32)
            self.assertTrue(lf.handle.readable())
        finally:
            lf.close()

    def test_file_not_found(self) -> None:
        from anyshare_unofficial.utils.file import LocalFile

        with self.assertRaises(FileNotFoundError):
            LocalFile.from_path("/nonexistent/path/file.txt")


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------


class TestObjectItemModels(unittest.TestCase):

    def test_file_and_folder_is_dir_properties(self) -> None:
        from anyshare_unofficial import FileItem, FolderItem

        file_item = FileItem.model_validate(
            {
                "id": "gns://DOCLIB/FOLDER/file.txt",
                "name": "report.pdf",
                "size": 102400,
                "rev": "a1b2c3d4e5f6789012345678abcdef01",
                "created_at": "2025-06-01T12:00:00Z",
                "modified_at": "2025-06-05T08:30:00Z",
                "created_by": {"id": "user1", "name": "Alice", "type": "user"},
                "modified_by": {"id": "user1", "name": "Alice", "type": "user"},
                "storage_name": "s3_key_abc",
            }
        )
        folder_item = FolderItem.model_validate(
            {
                "id": "gns://DOCLIB/FOLDER",
                "name": "MyFolder",
                "size": -1,
                "rev": "deadbeefcafebabedeadbeefcafebabe",
                "created_at": "2025-06-01T12:00:00Z",
                "modified_at": "2025-06-05T08:30:00Z",
            }
        )

        self.assertFalse(file_item.is_dir)
        self.assertTrue(folder_item.is_dir)


class TestAuthModels(unittest.TestCase):

    def test_user_basic_info_accepts_deppath_only_department(self) -> None:
        from anyshare_unofficial import UserBasicInfo

        info = UserBasicInfo.model_validate({"directdepinfos": [{"deppath": "示例组织/成员分组/示例部门"}]})

        self.assertEqual(len(info.directdepinfos), 1)
        dep = info.directdepinfos[0]
        self.assertEqual(dep.deppath, "示例组织/成员分组/示例部门")
        self.assertIsNone(dep.depid)
        self.assertIsNone(dep.name)

    def test_user_basic_info_accepts_full_department(self) -> None:
        from anyshare_unofficial import UserBasicInfo

        info = UserBasicInfo.model_validate(
            {
                "directdepinfos": [
                    {
                        "depid": "dep-1",
                        "name": "示例部门",
                        "deppath": "示例组织/成员分组/示例部门",
                    }
                ]
            }
        )

        dep = info.directdepinfos[0]
        self.assertEqual(dep.depid, "dep-1")
        self.assertEqual(dep.name, "示例部门")
        self.assertEqual(dep.deppath, "示例组织/成员分组/示例部门")

    def test_user_info_keeps_department_reference_strict(self) -> None:
        from pydantic import ValidationError

        from anyshare_unofficial import UserInfo

        with self.assertRaises(ValidationError):
            UserInfo.model_validate(
                {
                    "account": "alice",
                    "directdepinfos": [{"deppath": "示例组织/成员分组/示例部门"}],
                }
            )


class TestContactParsing(unittest.TestCase):

    def test_get_contact_groups_parses_wrapped_response(self) -> None:
        from anyshare_unofficial import AuthenticatedClient, ContactGroup

        response = Mock()
        response.json.return_value = {
            "groups": [
                {
                    "count": 0,
                    "groupname": "临时联系人",
                    "id": "00000000-0000-4000-8000-000000000002",
                }
            ]
        }
        client = object.__new__(AuthenticatedClient)
        client._post = Mock(return_value=response)  # type: ignore[method-assign]

        groups = client.get_contact_groups()

        client._post.assert_called_once_with("/api/eacp/v1/contactor/getgroups")
        self.assertEqual(len(groups), 1)
        self.assertIsInstance(groups[0], ContactGroup)
        self.assertEqual(groups[0].groupname, "临时联系人")

    def test_get_contact_persons_parses_wrapped_response(self) -> None:
        from anyshare_unofficial import AuthenticatedClient

        response = Mock()
        response.json.return_value = {"userinfos": [{"userid": "user-1", "name": "Alice"}]}
        client = object.__new__(AuthenticatedClient)
        client._post = Mock(return_value=response)  # type: ignore[method-assign]

        persons = client.get_contact_persons("group-1", start=10, limit=20)

        client._post.assert_called_once_with(
            "/api/eacp/v1/contactor/getpersons",
            json={"groupid": "group-1", "start": 10, "limit": 20},
        )
        self.assertEqual(persons, [{"userid": "user-1", "name": "Alice"}])

    def test_get_contact_persons_accepts_empty_wrapper(self) -> None:
        from anyshare_unofficial import AuthenticatedClient

        response = Mock()
        response.json.return_value = {"userinfos": []}
        client = object.__new__(AuthenticatedClient)
        client._post = Mock(return_value=response)  # type: ignore[method-assign]

        self.assertEqual(client.get_contact_persons("group-1"), [])


class TestDepartmentParsing(unittest.TestCase):

    def test_get_department_roots_parses_wrapped_response(self) -> None:
        from anyshare_unofficial import AuthenticatedClient, DepartmentInfo

        response = Mock()
        response.json.return_value = {
            "depinfos": [
                {
                    "depid": "dep-root",
                    "name": "示例组织",
                    "isconfigable": False,
                }
            ]
        }
        client = object.__new__(AuthenticatedClient)
        client._post = Mock(return_value=response)  # type: ignore[method-assign]

        roots = client.get_department_roots()

        client._post.assert_called_once_with("/api/eacp/v1/department/getroots")
        self.assertEqual(len(roots), 1)
        self.assertIsInstance(roots[0], DepartmentInfo)
        self.assertEqual(roots[0].depid, "dep-root")
        self.assertEqual(roots[0].name, "示例组织")
        self.assertFalse(roots[0].isconfigable)

    def test_get_sub_departments_parses_wrapped_response(self) -> None:
        from anyshare_unofficial import AuthenticatedClient, DepartmentInfo

        response = Mock()
        response.json.return_value = {
            "depinfos": [
                {
                    "depid": "dep-child",
                    "name": "示例子部门",
                    "isconfigable": True,
                }
            ]
        }
        client = object.__new__(AuthenticatedClient)
        client._post = Mock(return_value=response)  # type: ignore[method-assign]

        departments = client.get_sub_departments("dep-root")

        client._post.assert_called_once_with(
            "/api/eacp/v1/department/getsubdeps",
            json={"depid": "dep-root"},
        )
        self.assertEqual(len(departments), 1)
        self.assertIsInstance(departments[0], DepartmentInfo)
        self.assertEqual(departments[0].depid, "dep-child")
        self.assertEqual(departments[0].name, "示例子部门")
        self.assertTrue(departments[0].isconfigable)

    def test_get_department_roots_accepts_empty_wrapper(self) -> None:
        from anyshare_unofficial import AuthenticatedClient

        response = Mock()
        response.json.return_value = {"depinfos": []}
        client = object.__new__(AuthenticatedClient)
        client._post = Mock(return_value=response)  # type: ignore[method-assign]

        self.assertEqual(client.get_department_roots(), [])

    def test_get_department_users_parses_wrapped_response(self) -> None:
        from anyshare_unofficial import AuthenticatedClient, DepartmentUserInfo

        response = Mock()
        response.json.return_value = {
            "userinfos": [
                {
                    "account": "example_user",
                    "csflevel": 5,
                    "mail": "",
                    "name": "example_user",
                    "userid": "00000000-0000-4000-8000-000000000001",
                }
            ]
        }
        client = object.__new__(AuthenticatedClient)
        client._post = Mock(return_value=response)  # type: ignore[method-assign]

        users = client.get_department_users("dep-root")

        client._post.assert_called_once_with(
            "/api/eacp/v1/department/getsubusers",
            json={"depid": "dep-root"},
        )
        self.assertEqual(len(users), 1)
        self.assertIsInstance(users[0], DepartmentUserInfo)
        self.assertEqual(users[0].account, "example_user")

    def test_get_department_users_accepts_empty_wrapper(self) -> None:
        from anyshare_unofficial import AuthenticatedClient

        response = Mock()
        response.json.return_value = {"userinfos": []}
        client = object.__new__(AuthenticatedClient)
        client._post = Mock(return_value=response)  # type: ignore[method-assign]

        self.assertEqual(client.get_department_users("dep-root"), [])


class TestSharingModels(unittest.TestCase):

    def test_link_config_permissions_use_permission_type(self) -> None:
        from anyshare_unofficial import LinkConfig, PermissionType

        config = LinkConfig.model_validate({"allow": ["display", "download"], "expires_at": "1970-01-01T00:00:00"})

        self.assertEqual(config.allow, [PermissionType.DISPLAY, PermissionType.DOWNLOAD])

    def test_perm_config_permissions_use_permission_type(self) -> None:
        from anyshare_unofficial import PermConfig, PermissionType

        config = PermConfig.model_validate({"allow": ["preview", "cache"], "deny": ["delete"]})

        self.assertEqual(config.allow, [PermissionType.PREVIEW, PermissionType.CACHE])
        self.assertEqual(config.deny, [PermissionType.DELETE])

    def test_sharing_permissions_reject_unknown_values(self) -> None:
        from pydantic import ValidationError

        from anyshare_unofficial import LinkConfig, PermConfig

        with self.assertRaises(ValidationError):
            LinkConfig.model_validate({"allow": ["unknown"]})

        with self.assertRaises(ValidationError):
            PermConfig.model_validate({"deny": ["unknown"]})

    def test_link_config_limit_helpers(self) -> None:
        from datetime import datetime

        from anyshare_unofficial import LinkConfig

        no_limits = LinkConfig.model_validate(
            {
                "expires_at": "1970-01-01T00:00:00",
                "limited_times": -1,
            }
        )
        self.assertTrue(no_limits.has_no_expire_time())
        self.assertFalse(no_limits.is_expired(current_time=datetime(2100, 1, 1)))
        self.assertTrue(no_limits.has_no_times_limit())
        self.assertFalse(no_limits.is_exceeded_times_limit())

        limited = LinkConfig.model_validate(
            {
                "expires_at": "2026-01-02T00:00:00",
                "accessed_times": 3,
                "limited_times": 3,
            }
        )
        self.assertFalse(limited.has_no_expire_time())
        self.assertFalse(limited.is_expired(current_time=datetime(2026, 1, 1)))
        self.assertTrue(limited.is_expired(current_time=datetime(2026, 1, 2)))
        self.assertFalse(limited.has_no_times_limit())
        self.assertTrue(limited.is_exceeded_times_limit())

    def test_perm_config_can_respects_deny_allow_and_default(self) -> None:
        from anyshare_unofficial import PermConfig, PermissionType

        config = PermConfig.model_validate({"allow": ["preview"], "deny": ["delete"]})

        self.assertFalse(config.can(PermissionType.DELETE))
        self.assertTrue(config.can(PermissionType.PREVIEW))
        self.assertFalse(config.can(PermissionType.CACHE))
        self.assertTrue(config.can(PermissionType.CACHE, default=True))

    def test_perm_config_normalizes_accessible_by(self) -> None:
        from anyshare_unofficial import PermConfig

        singleton = PermConfig.model_validate(
            {
                "accessible_by": {
                    "id": "user-1",
                    "name": "Alice",
                    "type": "user",
                }
            }
        )
        self.assertEqual(len(singleton.accessible_by), 1)
        self.assertEqual(singleton.accessible_by[0].id, "user-1")

        self.assertEqual(PermConfig.model_validate({"accessible_by": None}).accessible_by, [])

    def test_list_blocked_doc_libs_parses_wrapped_response(self) -> None:
        from anyshare_unofficial import AuthenticatedClient, BlockedDocLibListResult

        response = Mock()
        response.json.return_value = {
            "total_count": 1,
            "entries": [
                {
                    "id": "doc-lib-1",
                    "name": "Blocked Library",
                    "doc_lib_type": "user_doc_lib",
                }
            ],
        }
        client = object.__new__(AuthenticatedClient)
        client._get = Mock(return_value=response)  # type: ignore[method-assign]

        result = client.list_blocked_doc_libs(offset=2, limit=3)

        client._get.assert_called_once_with(
            "/api/doc-share/v1/blocked-doc-lib",
            params={"offset": 2, "limit": 3},
        )
        self.assertIsInstance(result, BlockedDocLibListResult)
        self.assertEqual(result.total_count, 1)
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.entries[0].id, "doc-lib-1")


class TestMessageModels(unittest.TestCase):

    def test_get_notifications_parses_wrapped_response(self) -> None:
        from anyshare_unofficial import AuthenticatedClient, NotificationListResult

        response = Mock()
        response.json.return_value = {
            "entries": [
                {
                    "id": "notice-1",
                    "read": False,
                    "channel": "doc-share/v1/share-with-users-on",
                    "payload": {"allow": ["display", "preview", "download", "cache"]},
                    "created_at": "2026-06-05T15:28:41+08:00",
                }
            ],
            "total_count": 1,
            "next_marker": "",
        }
        client = object.__new__(AuthenticatedClient)
        client._get = Mock(return_value=response)  # type: ignore[method-assign]

        result = client.get_notifications(read=True, limit=3)

        client._get.assert_called_once_with(
            "/api/message/v1/notifications",
            params={"read": "true", "limit": 3},
        )
        self.assertIsInstance(result, NotificationListResult)
        self.assertEqual(result.total_count, 1)
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.entries[0].id, "notice-1")


# ---------------------------------------------------------------------------
# DownloadAuth / UploadAuth parsing
# ---------------------------------------------------------------------------


class TestDownloadAuth(unittest.TestCase):

    def test_parse_valid(self) -> None:
        from anyshare_unofficial import DownloadAuth

        auth_list = [
            "GET",
            "https://s3.example.com/bucket/key?AWSAccessKeyId=AKID&Signature=sig",
        ]
        auth = DownloadAuth.parse_auth_list(auth_list)
        self.assertEqual(auth.method, "GET")
        self.assertEqual(auth.url, "https://s3.example.com/bucket/key?AWSAccessKeyId=AKID&Signature=sig")

    def test_parse_wrong_length_raises(self) -> None:
        from anyshare_unofficial import DownloadAuth

        with self.assertRaises(ValueError):
            DownloadAuth.parse_auth_list(["GET"])

        with self.assertRaises(ValueError):
            DownloadAuth.parse_auth_list(["GET", "url", "extra"])

    def test_parse_wrong_method_raises(self) -> None:
        from anyshare_unofficial import DownloadAuth

        with self.assertRaises(ValueError):
            DownloadAuth.parse_auth_list(["POST", "https://example.com/"])


class TestUploadAuth(unittest.TestCase):

    def _make_auth_list(self) -> list[str]:
        return [
            "POST",
            "https://s3.example.com/bucket/upload-key",
            "AWSAccessKeyId: AKID_TEST",
            "Content-Type: application/octet-stream",
            "Policy: eyJleHBpcmF0aW9uIjoiMjAyNS0xMi0zMSJ9",
            "Signature: abc123signature",
            "key: uploads/file.pdf",
        ]

    def test_parse_valid(self) -> None:
        from anyshare_unofficial import UploadAuth

        url, auth = UploadAuth.parse_auth_list(self._make_auth_list())
        self.assertEqual(url, "https://s3.example.com/bucket/upload-key")
        self.assertEqual(auth.method, "POST")
        self.assertEqual(auth.aws_access_key_id, "AKID_TEST")
        self.assertEqual(auth.content_type, "application/octet-stream")
        self.assertEqual(auth.policy, "eyJleHBpcmF0aW9uIjoiMjAyNS0xMi0zMSJ9")
        self.assertEqual(auth.signature, "abc123signature")
        self.assertEqual(auth.key, "uploads/file.pdf")

    def test_parse_wrong_length_raises(self) -> None:
        from anyshare_unofficial import UploadAuth

        with self.assertRaises(ValueError):
            UploadAuth.parse_auth_list(["POST", "url"])

    def test_parse_wrong_method_raises(self) -> None:
        from anyshare_unofficial import UploadAuth

        bad = self._make_auth_list()
        bad[0] = "GET"
        with self.assertRaises(ValueError):
            UploadAuth.parse_auth_list(bad)

    def test_as_form_data(self) -> None:
        from anyshare_unofficial import UploadAuth

        _url, auth = UploadAuth.parse_auth_list(self._make_auth_list())
        form = auth.as_form_data()
        self.assertDictEqual(
            form,
            {
                "AWSAccessKeyId": "AKID_TEST",
                "Content-Type": "application/octet-stream",
                "Policy": "eyJleHBpcmF0aW9uIjoiMjAyNS0xMi0zMSJ9",
                "Signature": "abc123signature",
                "key": "uploads/file.pdf",
            },
        )


# ---------------------------------------------------------------------------
# BaseClient lifecycle (no server needed for constructor)
# ---------------------------------------------------------------------------


class TestBaseClientLifecycle(unittest.TestCase):

    def test_context_manager(self) -> None:
        from anyshare_unofficial import BaseClient

        with BaseClient(base_url="https://example.com") as client:
            self.assertIsNotNone(client)
            self.assertIsNotNone(client._client)

    def test_close(self) -> None:
        from anyshare_unofficial import BaseClient

        client = BaseClient(base_url="https://example.com")
        self.assertFalse(client._client.is_closed)
        client.close()
        self.assertTrue(client._client.is_closed)


class TestBaseClientUploadHelpers(unittest.TestCase):

    def test_begin_upload_posts_expected_payload(self) -> None:
        from anyshare_unofficial import BaseClient, OnDup
        from anyshare_unofficial.utils.file import LocalFile

        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".txt") as f:
            f.write(b"hello")
            temp_path = f.name

        client = BaseClient(base_url="https://example.com")
        local_file = LocalFile.from_path(temp_path)
        try:
            post_response = Mock()
            post_response.json.return_value = {
                "authrequest": [
                    "POST",
                    "https://s3.example/upload",
                    "AWSAccessKeyId: access-key",
                    "Content-Type: application/octet-stream",
                    "Policy: policy-value",
                    "Signature: signature-value",
                    "key: object-key",
                ],
                "docid": "gns://DL/dir/file.txt",
                "name": "file.txt",
                "rev": "rev-1",
            }
            client._post = Mock(return_value=post_response)  # type: ignore[method-assign]

            upload_auth, result = client._begin_upload(local_file, "gns://DL/dir", ondup=OnDup.OVERWRITE)

            client._post.assert_called_once()
            path = client._post.call_args.args[0]
            payload = client._post.call_args.kwargs["json"]
            self.assertEqual(path, "/api/efast/v1/file/osbeginupload")
            self.assertEqual(payload["reqmethod"], "POST")
            self.assertEqual(payload["name"], Path(temp_path).name)
            self.assertEqual(payload["docid"], "gns://DL/dir")
            self.assertEqual(payload["ondup"], OnDup.OVERWRITE.value)
            self.assertEqual(payload["length"], 5)
            self.assertEqual(payload["gns_dir_path"], "gns://DL/dir")
            self.assertIsInstance(payload["client_mtime"], int)
            self.assertEqual(upload_auth.url, "https://s3.example/upload")
            self.assertEqual(upload_auth.key, "object-key")
            self.assertEqual(result.docid, "gns://DL/dir/file.txt")
        finally:
            local_file.close()
            client.close()
            os.unlink(temp_path)

    def test_post_upload_data_sends_multipart_form(self) -> None:
        from anyshare_unofficial import BaseClient, UploadAuth
        from anyshare_unofficial.utils.file import LocalFile

        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".bin") as f:
            f.write(b"content")
            temp_path = f.name

        client = BaseClient(base_url="https://example.com")
        local_file = LocalFile.from_path(temp_path)
        try:
            upload_auth = UploadAuth(
                url="https://s3.example/upload",
                aws_access_key_id="access-key",
                content_type="application/octet-stream",
                policy="policy-value",
                signature="signature-value",
                key="object-key",
            )
            post_response = Mock()
            client._client.post = Mock(return_value=post_response)  # type: ignore[method-assign]

            client._post_upload_data(upload_auth, local_file)

            client._client.post.assert_called_once_with(
                "https://s3.example/upload",
                data=upload_auth.as_form_data(),
                files={"file": (Path(temp_path).name, local_file.handle, "application/octet-stream")},
            )
            post_response.raise_for_status.assert_called_once_with()
        finally:
            local_file.close()
            client.close()
            os.unlink(temp_path)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()

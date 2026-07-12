"""Cross-platform tests for Windows mount configuration."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.config import MountConfig
from scripts.mount_drive import mount_targets, probe_webdav
from scripts.prepare_service_runtime import _copy, _first_existing


BASE_ENV = """\
ANYSHARE_BASE_URL=https://anyshare.example.com
ANYSHARE_AUTH_COOKIE=Authorization=Bearer secret
ANYSHARE_DAV_USERNAME=anyshare-x
ANYSHARE_DAV_PASSWORD=dav-password
ANYSHARE_DAV_HOST=127.0.0.1
ANYSHARE_DAV_PORT=18765
ANYSHARE_MOUNT_DRIVE=X:
"""


class TestMountConfig(unittest.TestCase):
    def _load(self, extra: str = "") -> MountConfig:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        env_file = Path(temp_dir.name) / ".env"
        env_file.write_text(BASE_ENV + extra, encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            return MountConfig.from_env_file(env_file)

    def test_loads_gateway_and_drive_settings(self) -> None:
        config = self._load()
        self.assertEqual(config.local_url, "http://127.0.0.1:18765/")
        self.assertEqual(config.webdav_remote_name, r"\\127.0.0.1@18765\DavWWWRoot")
        self.assertEqual(config.drive, "X:")
        self.assertNotIn("Bearer secret", repr(config))
        self.assertNotIn("dav-password", repr(config))

    def test_https_url_becomes_webclient_unc(self) -> None:
        config = self._load("ANYSHARE_MOUNT_URL=https://dav.example.com:8443/root/path\n")
        self.assertEqual(
            config.webdav_remote_name,
            r"\\dav.example.com@SSL@8443\DavWWWRoot\root\path",
        )

    def test_mount_targets_try_unc_then_url(self) -> None:
        config = self._load()
        self.assertEqual(
            mount_targets(config),
            (r"\\127.0.0.1@18765\DavWWWRoot", "http://127.0.0.1:18765/"),
        )

    @patch("scripts.mount_drive.httpx.request")
    def test_probe_uses_authenticated_propfind(self, request: Mock) -> None:
        request.return_value = Mock(status_code=207, text="")
        config = self._load()

        probe_webdav(config)

        self.assertEqual(request.call_count, 2)
        args, kwargs = request.call_args_list[0]
        self.assertEqual(args, ("PROPFIND", "http://127.0.0.1:18765/"))
        self.assertEqual(kwargs["auth"], ("anyshare-x", "dav-password"))
        self.assertEqual(kwargs["headers"]["Depth"], "0")
        self.assertEqual(request.call_args_list[1].kwargs["headers"]["Depth"], "1")

    @patch("scripts.mount_drive.httpx.request")
    def test_probe_rejects_authentication_failure(self, request: Mock) -> None:
        request.return_value = Mock(status_code=401, text="Unauthorized")
        with self.assertRaisesRegex(PermissionError, "Local WebDAV authentication.*HTTP 401"):
            probe_webdav(self._load())

    @patch("scripts.mount_drive.httpx.request")
    def test_probe_identifies_upstream_listing_failure(self, request: Mock) -> None:
        request.side_effect = [
            Mock(status_code=207, text=""),
            Mock(status_code=403, text="Authentication failed"),
        ]
        with self.assertRaisesRegex(PermissionError, "AnyShare root listing.*HTTP 403"):
            probe_webdav(self._load())

    def test_process_environment_overrides_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(BASE_ENV, encoding="utf-8")
            with patch.dict(os.environ, {"ANYSHARE_MOUNT_DRIVE": "Y:"}, clear=True):
                config = MountConfig.from_env_file(env_file)
        self.assertEqual(config.drive, "Y:")

    def test_rejects_invalid_drive(self) -> None:
        with self.assertRaisesRegex(ValueError, "ANYSHARE_MOUNT_DRIVE"):
            self._load("ANYSHARE_MOUNT_DRIVE=invalid\n")

    def test_requires_certificate_pair(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be set together"):
            self._load("ANYSHARE_DAV_CERTFILE=server.crt\n")

    def test_service_runtime_repair_accepts_moved_host(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "site-packages" / "pythonservice.exe"
            moved = Path(temp_dir) / "pythonservice.exe"
            moved.write_bytes(b"host")
            self.assertEqual(_first_existing(missing, moved), moved)

    @patch("scripts.prepare_service_runtime.shutil.copy2")
    def test_service_runtime_repair_skips_identical_file(self, copy2: Mock) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "source"
            destination_dir = Path(temp_dir) / "destination"
            source_dir.mkdir()
            destination_dir.mkdir()
            (source_dir / "python3.dll").write_bytes(b"same runtime")
            (destination_dir / "python3.dll").write_bytes(b"same runtime")

            _copy(source_dir / "python3.dll", destination_dir)

        copy2.assert_not_called()


if __name__ == "__main__":
    unittest.main()

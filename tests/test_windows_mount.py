"""Cross-platform tests for Windows mount configuration."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Mount.config import MountConfig


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


if __name__ == "__main__":
    unittest.main()

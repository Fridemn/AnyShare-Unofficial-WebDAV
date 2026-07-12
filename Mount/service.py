"""Windows service that runs the AnyShare WebDAV gateway from .env."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Mount.config import MountConfig  # noqa: E402
from anyshare_unofficial import AuthenticatedClient  # noqa: E402
from anyshare_unofficial.webdav.app import create_app  # noqa: E402
from anyshare_unofficial.webdav.provider import AnyShareDAVProvider  # noqa: E402
from anyshare_unofficial.webdav.repository import AnyShareRepository  # noqa: E402


def create_server(config: MountConfig):
    """Build the gateway directly from core classes without spawning the CLI."""
    from cheroot import wsgi
    from cheroot.ssl.builtin import BuiltinSSLAdapter

    client = AuthenticatedClient(
        config.auth_cookie,
        base_url=config.base_url,
        verify=config.upstream_verify,
    )
    repository = AnyShareRepository(
        client,
        cache_ttl=config.cache_ttl,
        download_verify=config.upstream_verify,
    )
    provider = AnyShareDAVProvider(repository, readonly=config.readonly)
    app = create_app(provider, username=config.dav_username, password=config.dav_password, verbose=0)
    server = wsgi.Server((config.host, config.port), app, server_name="AnyShare WebDAV")
    if config.certfile and config.keyfile:
        server.ssl_adapter = BuiltinSSLAdapter(str(config.certfile), str(config.keyfile))
    return client, server


if os.name == "nt":
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    class AnyShareWebDAVService(win32serviceutil.ServiceFramework):
        _svc_name_ = "AnyShareUnofficialWebDAVX18765"
        _svc_display_name_ = "AnyShare Unofficial WebDAV X: (18765)"
        _svc_description_ = "Exposes AnyShare document libraries through a local WebDAV endpoint."
        _exe_name_ = str(Path(sys.executable).resolve().parent / "pythonservice.exe")

        def __init__(self, args) -> None:
            super().__init__(args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.client = None
            self.server = None
            self.worker: threading.Thread | None = None

        def SvcStop(self) -> None:  # noqa: N802
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)
            if self.server is not None:
                self.server.stop()

        def SvcDoRun(self) -> None:  # noqa: N802
            try:
                config = MountConfig.from_env_file()
                self.client, self.server = create_server(config)
                self.worker = threading.Thread(
                    target=self.server.start,
                    name="anyshare-webdav-server",
                    daemon=True,
                )
                self.worker.start()
                servicemanager.LogInfoMsg(
                    f"{self._svc_name_} listening on {config.local_url}"
                )

                while win32event.WaitForSingleObject(self.stop_event, 1000) != win32event.WAIT_OBJECT_0:
                    if not self.worker.is_alive():
                        raise RuntimeError("WebDAV server stopped unexpectedly")
            except Exception as exc:
                servicemanager.LogErrorMsg(f"{self._svc_name_} failed: {exc}")
                raise
            finally:
                if self.server is not None:
                    self.server.stop()
                if self.worker is not None:
                    self.worker.join(timeout=10)
                if self.client is not None:
                    self.client.close()


def main() -> int:
    if os.name != "nt":
        print("This service can only be installed or run on Windows.", file=sys.stderr)
        return 1
    win32serviceutil.HandleCommandLine(
        AnyShareWebDAVService,
        serviceClassString="Mount.service.AnyShareWebDAVService",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

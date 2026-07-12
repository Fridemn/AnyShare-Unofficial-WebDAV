"""Place the native pywin32 service runtime next to the venv interpreter."""

from __future__ import annotations

import os
import shutil
import site
import sys
from pathlib import Path


def _copy(source: Path, destination_dir: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Required Windows service runtime file is missing: {source}")
    destination = destination_dir / source.name
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def _first_existing(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "Required Windows service runtime file is missing: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def prepare_runtime() -> Path:
    if os.name != "nt":
        raise RuntimeError("The pywin32 service runtime can only be prepared on Windows")

    scripts_dir = Path(sys.executable).resolve().parent
    base_dir = Path(sys.base_prefix).resolve()
    site_packages = next(Path(path) for path in site.getsitepackages() if Path(path).name == "site-packages")
    version_suffix = f"{sys.version_info.major}{sys.version_info.minor}"

    for name in ("python3.dll", f"python{version_suffix}.dll"):
        _copy(base_dir / name, scripts_dir)
    for name in (f"pywintypes{version_suffix}.dll", f"pythoncom{version_suffix}.dll"):
        _copy(site_packages / "pywin32_system32" / name, scripts_dir)
    # A previous pywin32 service installation may have moved pythonservice.exe
    # from site-packages/win32 into the venv root. Accept both layouts so the
    # installer can repair an already-installed but non-starting service.
    _copy(
        _first_existing(
            site_packages / "win32" / "pythonservice.exe",
            scripts_dir.parent / "pythonservice.exe",
        ),
        scripts_dir,
    )
    _copy(site_packages / "win32" / "servicemanager.pyd", scripts_dir)

    host = scripts_dir / "pythonservice.exe"
    print(f"Prepared isolated pywin32 service host: {host}")
    return host


if __name__ == "__main__":
    prepare_runtime()

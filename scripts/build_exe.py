"""Build the standalone VEDA desktop app for the current OS with PyInstaller.

    pip install -e ".[build]"
    python scripts/build_exe.py            # -> dist/VEDA.exe | dist/VEDA | dist/VEDA.app
    python scripts/build_exe.py --archive  # also writes dist/VEDA-<version>-<os>-<arch>.zip

Works on Windows, macOS and Linux; each OS builds its own binary.
"""
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
WORK = ROOT / "build" / "pyinstaller"
SPEC = ROOT / "packaging" / "veda.spec"


def _version() -> str:
    ns: dict = {}
    exec((ROOT / "src" / "veda" / "__init__.py").read_text(encoding="utf-8"), ns)
    return ns["__version__"]


def _os_tag() -> str:
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def _artifact() -> Path:
    if sys.platform == "win32":
        return DIST / "VEDA.exe"
    if sys.platform == "darwin":
        return DIST / "VEDA.app"
    return DIST / "VEDA"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--archive", action="store_true",
                    help="zip the build output for distribution")
    args = ap.parse_args()

    shutil.rmtree(WORK, ignore_errors=True)
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", str(DIST), "--workpath", str(WORK), str(SPEC)],
        check=True, cwd=ROOT,
    )
    out = _artifact()
    if not out.exists():
        print(f"build finished but {out} is missing", file=sys.stderr)
        return 1
    print(f"built {out}")

    if args.archive:
        arch = platform.machine().lower().replace("amd64", "x86_64")
        name = f"VEDA-{_version()}-{_os_tag()}-{arch}"
        if sys.platform == "darwin":
            # ditto keeps the .app bundle's symlinks and permissions intact
            zip_path = DIST / f"{name}.zip"
            subprocess.run(["ditto", "-c", "-k", "--keepParent", str(out), str(zip_path)],
                           check=True)
        else:
            staging = DIST / name
            shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir()
            shutil.copy2(out, staging / out.name)
            for doc in ("README.md", "LICENSE", "THIRD_PARTY_LICENSES.md"):
                shutil.copy2(ROOT / doc, staging / doc)
            zip_path = Path(shutil.make_archive(str(DIST / name), "zip", DIST, name))
            shutil.rmtree(staging)
        print(f"archived {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

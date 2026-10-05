"""Build the standalone VEDA desktop app for the current OS with PyInstaller.

    pip install -e ".[build]"
    python scripts/build_exe.py            # -> dist/VEDA/VEDA.exe | dist/VEDA/VEDA | dist/VEDA.app
    python scripts/build_exe.py --archive  # also writes dist/VEDA-<version>-<os>-<arch>.zip
                                           # (the app plus licences and guides in one folder)

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
# placed beside the app in the distributed zip
DOCS = ("README.md", "USAGE.md", "CHANGELOG.md", "DATA_POLICY.md", "TERMS.md",
        "LICENSE", "THIRD_PARTY_LICENSES.md")


def _version() -> str:
    ns: dict = {}
    exec((ROOT / "src" / "veda" / "__init__.py").read_text(encoding="utf-8"), ns)
    return ns["__version__"]


def _os_tag() -> str:
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def _artifact() -> Path:
    """The folder (or .app bundle) to distribute."""
    return DIST / ("VEDA.app" if sys.platform == "darwin" else "VEDA")


def _launcher() -> Path:
    if sys.platform == "win32":
        return DIST / "VEDA" / "VEDA.exe"
    if sys.platform == "darwin":
        return DIST / "VEDA.app"
    return DIST / "VEDA" / "VEDA"


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
    if not _launcher().exists():
        print(f"build finished but {_launcher()} is missing", file=sys.stderr)
        return 1
    print(f"built {_launcher()}")

    if args.archive:
        # VEDA-<version>-<os>-<arch>/ holds the app (VEDA.exe or VEDA with _internal/, or
        # VEDA.app) and the documents a user needs beside it: licences, terms, guides.
        arch = platform.machine().lower().replace("amd64", "x86_64")
        name = f"VEDA-{_version()}-{_os_tag()}-{arch}"
        staging = DIST / name
        shutil.rmtree(staging, ignore_errors=True)
        if sys.platform == "darwin":
            staging.mkdir()
            # ditto keeps the .app bundle's symlinks and permissions intact
            subprocess.run(["ditto", str(out), str(staging / out.name)], check=True)
        else:
            shutil.copytree(out, staging)          # VEDA.exe/VEDA plus _internal/
        for doc in DOCS:
            shutil.copy2(ROOT / doc, staging / doc)
        zip_path = DIST / f"{name}.zip"
        zip_path.unlink(missing_ok=True)
        if sys.platform == "darwin":
            subprocess.run(["ditto", "-c", "-k", "--keepParent", str(staging), str(zip_path)],
                           check=True)
        else:
            zip_path = Path(shutil.make_archive(str(DIST / name), "zip", DIST, name))
        shutil.rmtree(staging)
        print(f"archived {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

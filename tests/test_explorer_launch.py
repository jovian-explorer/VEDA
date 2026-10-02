"""
Frozen-build launch verification (Windows): ``dist/VEDA/VEDA.exe``, else the installed app.

Reproduces the conditions under which Windows Explorer launches an EXE:
the CWD is something other than the EXE directory (Desktop, home, temp),
so every bundled resource must resolve from ``sys._MEIPASS``.

Build with ``python scripts/build_exe.py``, or install a release (the tests then check
the installed app); they skip when neither exists.  ``VEDA_EXE`` names another EXE.
Each launch uses ``--no-window`` and a throwaway VEDA_HOME, and only the
process tree started by the test is terminated.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
EXE = next((p for p in (
    Path(os.environ["VEDA_EXE"]) if os.environ.get("VEDA_EXE") else None,
    PROJECT / "dist" / "VEDA" / "VEDA.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "VEDA" / "VEDA" / "VEDA.exe",
) if p is not None and p.is_file()), PROJECT / "dist" / "VEDA" / "VEDA.exe")

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="Windows EXE launch test"),
    pytest.mark.skipif(not EXE.is_file(), reason=f"EXE not built at {EXE}"),
]


def _launch_from_cwd(cwd: Path, timeout_s: int = 120) -> tuple[bool, str, Path]:
    """Launch the EXE with the given CWD; return (alive_when_healthy, startup log, home)."""
    # inside the run's test folder (tests/conftest.py), which is deleted at the end
    home = Path(tempfile.mkdtemp(prefix="veda-launch-home-", dir=os.environ.get("VEDA_HOME")))
    env = dict(os.environ, VEDA_HOME=str(home))
    log_path = home / "logs" / "startup.log"
    proc = subprocess.Popen(
        [str(EXE), "--no-window"], cwd=str(cwd), env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    log = ""
    try:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if log_path.is_file():
                log = log_path.read_text(encoding="utf-8", errors="replace")
                if "Backend healthy" in log or "ERROR" in log:
                    break
            if proc.poll() is not None:
                break
            time.sleep(0.5)
        alive = proc.poll() is None
    finally:
        # /T kills the onefile bootloader and its child, and nothing else.
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, timeout=15)
        proc.wait(timeout=15)
    return alive, log, home


def _assert_healthy(cwd: Path) -> Path:
    alive, log, home = _launch_from_cwd(cwd)
    assert log, "startup log was not written"
    assert "Frontend assets are missing" not in log, log[-400:]
    assert "Backend healthy" in log, log[-400:]
    assert alive, "process exited before it was stopped"
    return home


def test_folder_build_layout() -> None:
    """Folder build: the launcher plus _internal/ with the frontend and data files."""
    internal = EXE.parent / "_internal"
    assert (internal / "veda" / "frontend" / "index.html").is_file()
    assert (internal / "veda" / "archives" / "references.json").is_file()
    assert (internal / "veda" / "sampledata").is_dir()


def test_launch_from_exe_dir() -> None:
    _assert_healthy(EXE.parent)


def test_launch_from_home() -> None:
    _assert_healthy(Path.home())


def test_launch_from_temp() -> None:
    tmpdir = Path(tempfile.mkdtemp(dir=os.environ.get("VEDA_HOME")))
    try:
        _assert_healthy(tmpdir)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_no_error_log() -> None:
    home = _assert_healthy(Path.home())
    err = home / "logs" / "startup-error.log"
    assert not err.exists(), err.read_text(encoding="utf-8", errors="replace")[:400]

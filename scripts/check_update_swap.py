"""End-to-end check of the automatic update's swap step on a freshly built release zip.

    python scripts/check_update_swap.py dist/VEDA-<version>-<os>-<arch>.zip

Unpacks the zip twice into a temporary folder: once as the "installed" copy, once as
the staged update beside it (``<folder>.update``, as autoupdate.check_and_stage leaves
it).  A data folder with a settings.json and a downloaded file is made elsewhere.  Then
the platform's swap script (autoupdate._helper_script: PowerShell on Windows, sh on macOS
and Linux) is started for a stand-in "running VEDA" process, and the check waits for:

* the swap to wait until that process has exited,
* the installed folder to be the staged copy (a marker file) and the old one to be
  ``<folder>.previous``,
* the new build to be started with the same command-line options (it answers
  /api/health on the port given by ``--port``, and /api/meta names the data folder given
  by VEDA_HOME),
* the data folder to be unchanged apart from VEDA's own ``updates/`` and ``logs/``.

Exits non-zero with a message on the first failure.  Used by the release workflow on
Windows, macOS and Linux runners.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", flush=True)
    sys.exit(1)


def unpack(zip_path: Path, dest: Path) -> Path:
    dest.mkdir(parents=True)
    if sys.platform == "darwin":
        subprocess.run(["ditto", "-x", "-k", str(zip_path), str(dest)], check=True)
    else:
        from veda.autoupdate import extract
        return extract(zip_path, dest)
    tops = [p for p in dest.iterdir() if p.is_dir()]
    return tops[0]


def snapshot(folder: Path) -> dict:
    out = {}
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder).as_posix()
        if p.is_file() and not rel.startswith(("updates/", "logs/", "cache/matplotlib/", "webview2-cache/")):
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_json(url: str):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    zip_path = Path(sys.argv[1]).resolve()
    work = Path(tempfile.mkdtemp(prefix="veda-swap-"))
    data = work / "data home"                     # (a space in the path on purpose)
    data.mkdir()
    (data / "settings.json").write_text(json.dumps({"ui_theme": "light", "plot_dpi": 600}, indent=2))
    (data / "cache" / "archive" / "x").mkdir(parents=True)
    (data / "cache" / "archive" / "x" / "product.tab").write_bytes(os.urandom(4096))
    os.environ["VEDA_HOME"] = str(data)            # before veda is imported: its data folder

    from veda import autoupdate                     # noqa: E402 - after VEDA_HOME

    root_parent = work / "apps"
    installed = unpack(zip_path, root_parent / "installed")
    root = root_parent / "VEDA-test"
    shutil.move(str(installed), str(root))
    shutil.rmtree(root_parent / "installed", ignore_errors=True)
    staged_top = unpack(zip_path, root_parent / "staging")
    staged = root_parent / "VEDA-test.update"
    shutil.move(str(staged_top), str(staged))
    shutil.rmtree(root_parent / "staging", ignore_errors=True)
    (root / "OLD_COPY").write_text("old")
    (staged / "NEW_COPY").write_text("new")
    if autoupdate.install_problem(root) is not None and "source" not in (autoupdate.install_problem(root) or ""):
        fail(f"install_problem: {autoupdate.install_problem(root)}")
    before = snapshot(data)

    # a stand-in for the running VEDA: the script must wait for it to exit
    stand_in = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(6)"])
    autoupdate.os.getpid = lambda: stand_in.pid
    port = free_port()
    script, cmd = autoupdate._helper_script(root, staged, root_parent / "VEDA-test.previous",
                                            ["--no-window", "--port", str(port)])
    print("swap script:", script, flush=True)
    t0 = time.time()
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if sys.platform == "win32":
        subprocess.Popen(cmd, creationflags=0x00000200 | 0x08000000, **kw)
    else:
        subprocess.Popen(cmd, start_new_session=True, **kw)

    time.sleep(2)
    if (root / "NEW_COPY").exists():
        fail("the swap did not wait for the running VEDA to exit")
    stand_in.wait()
    deadline = time.time() + 240
    health = None
    while time.time() < deadline:
        try:
            health = get_json(f"http://127.0.0.1:{port}/api/health")
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(1)
    log = (data / "updates" / "install.log")
    print(log.read_text() if log.exists() else "(no install.log)", flush=True)
    if health is None:
        fail(f"the new build did not answer on port {port} (the --port option) within 240 s")
    print(f"new build up after {time.time() - t0:.0f} s: {health}", flush=True)
    meta = get_json(f"http://127.0.0.1:{port}/api/meta")
    if not (root / "NEW_COPY").exists() or (root / "OLD_COPY").exists():
        fail("the installed folder is not the staged copy")
    if not (root_parent / "VEDA-test.previous" / "OLD_COPY").exists():
        fail("the old installation was not kept as .previous")
    if staged.exists():
        fail("the staged folder is still there")
    data_root = Path(meta["paths"]["data_root"]).resolve()
    if data_root != data.resolve():
        fail(f"the new build uses the data folder {data_root}, not {data} (VEDA_HOME not passed on)")
    after = snapshot(data)
    if after != before:
        changed = sorted(set(before) ^ set(after) | {k for k in before if after.get(k) != before[k]})
        fail(f"the data folder changed: {changed}")
    # stop the new build
    # (only processes started from the test folder: never another VEDA on the machine)
    if sys.platform == "win32":
        subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                        f"Get-Process VEDA -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{root}*' }}"
                        " | Stop-Process -Force"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", str(root)], capture_output=True)
    time.sleep(2)
    shutil.rmtree(work, ignore_errors=True)
    print("OK: waited for exit, swapped, kept .previous, restarted with the same options and data folder; "
          "data folder unchanged", flush=True)


if __name__ == "__main__":
    main()

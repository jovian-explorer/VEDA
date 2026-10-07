"""Weekly automatic update of a published build.

Once a week (Settings > Network, on by default; *Check now* any time) a published build
of VEDA asks GitHub for the latest release.  When it is newer, the zip for this platform
is downloaded into the data folder (``updates/``), checked against the size and SHA-256
digest GitHub lists for it, and unpacked beside the installation (``<folder>.update``).
The next time VEDA starts it hands over to a small script that waits for it to exit,
renames the installation to ``<folder>.previous``, moves the new one into its place and
starts it again with the same arguments; the new build then deletes the previous one.

Only the installation folder is replaced: the data folder (downloads, settings.json,
logs) is a different folder and is never touched, and an installation that holds the
data folder (VEDA_HOME inside it) or cannot be renamed is not updated automatically.
Copies run from source (no build number) are never updated.

State (last check, the staged build, the notes of the installed one) is kept in
``updates/state.json`` in the data folder.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from . import __version__
from .config import DATA_ROOT, SETTINGS
from .updates import BUILD, REPO, is_newer, parse_tag

UPDATES_DIR = DATA_ROOT / "updates"
STATE_PATH = UPDATES_DIR / "state.json"
CHECK_EVERY_S = 7 * 24 * 3600
_API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"

_lock = threading.Lock()
_job: Dict[str, Any] = {"running": False, "message": "", "done": 0, "total": 0, "error": None}


# ---------------------------------------------------------------- state

def load_state() -> Dict[str, Any]:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: Dict[str, Any]) -> None:
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
    os.replace(tmp, STATE_PATH)


def installed_notes(build: Optional[int]) -> Optional[Dict[str, Any]]:
    """Release notes of this build, when it was installed by the updater."""
    inst = load_state().get("installed") or {}
    if build is not None and inst.get("build") == build:
        return {"tag": inst.get("tag"), "name": inst.get("name"), "notes": inst.get("notes") or "",
                "url": inst.get("url")}
    return None


# ---------------------------------------------------------------- this installation

def platform_tag() -> str:
    """The part of a release zip's name for this computer (scripts/build_exe.py)."""
    os_tag = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    arch = platform.machine().lower().replace("amd64", "x86_64").replace("aarch64", "arm64")
    return f"{os_tag}-{arch}"


def install_root() -> Optional[Path]:
    """The folder that was unzipped: VEDA.exe or VEDA with _internal/ (Windows, Linux),
    or the folder holding VEDA.app (macOS).  None when not a frozen build."""
    if not getattr(sys, "frozen", False):
        return None
    exe = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        for parent in exe.parents:
            if parent.suffix == ".app":
                return parent.parent
        return None
    return exe.parent


def _launcher(root: Path) -> Path:
    if sys.platform == "darwin":
        return root / "VEDA.app"
    return root / ("VEDA.exe" if sys.platform == "win32" else "VEDA")


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def install_problem(root: Optional[Path] = None) -> Optional[str]:
    """Why this copy cannot update itself, or None."""
    if BUILD.get("number") is None:
        return "this copy runs from source (only published builds update themselves)"
    root = root or install_root()
    if root is None:
        return "the installation folder could not be found"
    if _inside(DATA_ROOT, root):
        return "the data folder is inside the installation folder"
    if not _launcher(root).exists():
        return f"{_launcher(root).name} is not in {root}"
    if not os.access(root.parent, os.W_OK):
        return f"{root.parent} is not writable"
    return None


def _staged_dir(root: Path) -> Path:
    return root.parent / f"{root.name}.update"


def _previous_dir(root: Path) -> Path:
    return root.parent / f"{root.name}.previous"


# ---------------------------------------------------------------- checking and downloading

def status() -> Dict[str, Any]:
    st = load_state()
    last = st.get("last_check")
    staged = st.get("staged") or None
    return {"enabled": bool(SETTINGS.auto_update), "network": bool(SETTINGS.network_enabled),
            "problem": install_problem(), "last_check": last,
            "next_check": (last + CHECK_EVERY_S) if last else None,
            "staged": None if not staged else {k: staged.get(k) for k in ("tag", "name", "build", "staged_at")},
            "installed": st.get("installed", {}).get("tag") if st.get("installed") else None,
            "job": dict(_job), "version": __version__, "build": BUILD.get("number")}


def due(now: Optional[float] = None) -> bool:
    if not (SETTINGS.auto_update and SETTINGS.network_enabled) or install_problem() is not None:
        return False
    last = load_state().get("last_check")
    return not last or (now or time.time()) - float(last) >= CHECK_EVERY_S


def _latest_release() -> Dict[str, Any]:
    from .archives import net
    r = net.session().get(_API_LATEST, timeout=SETTINGS.network_timeout_s,
                          headers={"Accept": "application/vnd.github+json"})
    r.raise_for_status()
    return r.json()


def pick_asset(release: Dict[str, Any], tag: Optional[str] = None) -> Optional[Dict[str, Any]]:
    tag = tag or platform_tag()
    for a in release.get("assets") or []:
        name = a.get("name", "")
        if name.endswith(".zip") and f"-{tag}." in name:
            return a
    return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(path: Path, size: Optional[int], digest: Optional[str]) -> None:
    """Raise ValueError unless the file has the listed size and SHA-256 digest
    ("sha256:<hex>") and is a readable zip."""
    if size is not None and path.stat().st_size != int(size):
        raise ValueError(f"the download has {path.stat().st_size} bytes, the release lists {size}")
    if digest:
        algo, _, want = digest.partition(":")
        if algo.lower() != "sha256" or not want:
            raise ValueError(f"unknown digest {digest!r}")
        got = _sha256(path)
        if got.lower() != want.lower():
            raise ValueError(f"SHA-256 {got} does not match the release's {want}")
    with zipfile.ZipFile(path) as zf:
        bad = zf.testzip()
        if bad:
            raise ValueError(f"{bad} in the download is damaged")


def extract(zip_path: Path, dest: Path) -> Path:
    """Unpack the release zip into ``dest`` and return its top folder (the one holding
    the launcher).  macOS uses ditto (keeps the app bundle's links and permissions);
    elsewhere the files' Unix permissions are restored from the zip."""
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    if sys.platform == "darwin":
        subprocess.run(["ditto", "-x", "-k", str(zip_path), str(dest)], check=True)
    else:
        with zipfile.ZipFile(zip_path) as zf:
            root = dest.resolve()
            for info in zf.infolist():
                target = (dest / info.filename).resolve()
                if not _inside(target, root):
                    raise ValueError(f"{info.filename} would be written outside the update folder")
                zf.extract(info, dest)
                mode = (info.external_attr >> 16) & 0o777
                if mode and os.name != "nt":
                    os.chmod(target, mode)
    tops = [p for p in dest.iterdir() if p.is_dir()]
    top = tops[0] if len(tops) == 1 else dest
    if not _launcher(top).exists():
        raise ValueError(f"the release has no {_launcher(top).name}")
    return top


def _progress(done: int, total: int, message: str) -> None:
    _job.update(done=done, total=total, message=message)


def check_and_stage(force: bool = False, release: Optional[Dict[str, Any]] = None,
                    progress: Callable[[int, int, str], None] = _progress) -> Dict[str, Any]:
    """Look for a newer published build and, when there is one, download, verify and
    unpack it beside the installation.  Returns {"result": "latest" | "staged" |
    "already staged" | "disabled" | "error", ...}."""
    problem = install_problem()
    if problem:
        return {"result": "disabled", "reason": problem}
    if not SETTINGS.network_enabled:
        return {"result": "disabled", "reason": "downloads are turned off (Settings > Network)"}
    if not force and not due():
        return {"result": "disabled", "reason": "checked less than a week ago"}
    root = install_root()
    assert root is not None
    rel = release or _latest_release()
    tag = rel.get("tag_name", "")
    st = load_state()
    st["last_check"] = time.time()
    if not is_newer(tag, __version__, BUILD.get("number")):
        save_state(st)
        return {"result": "latest", "tag": tag}
    staged = st.get("staged") or {}
    if staged.get("tag") == tag and Path(staged.get("path", "")).exists():
        save_state(st)
        return {"result": "already staged", "tag": tag}
    asset = pick_asset(rel)
    if asset is None:
        # (not counted as a check: a release is listed before all its files are uploaded)
        return {"result": "error", "reason": f"release {tag} has no download for {platform_tag()} yet"}
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    part = UPDATES_DIR / (asset["name"] + ".part")
    from .archives import net
    total = int(asset.get("size") or 0)
    progress(0, total, f"Downloading {asset['name']}")
    with net.session().get(asset["browser_download_url"], stream=True, timeout=SETTINGS.network_timeout_s) as r:
        r.raise_for_status()
        done = 0
        with open(part, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
                done += len(chunk)
                progress(done, total, f"Downloading {asset['name']}")
    try:
        progress(total, total, "Checking the download")
        verify(part, asset.get("size"), asset.get("digest"))
        progress(total, total, "Unpacking")
        work = UPDATES_DIR / "unpacked"
        top = extract(part, work)
        target = _staged_dir(root)
        shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(top), str(target))
        shutil.rmtree(work, ignore_errors=True)
    finally:
        part.unlink(missing_ok=True)
    _, build = parse_tag(tag)
    st["staged"] = {"tag": tag, "name": rel.get("name") or tag, "build": build, "notes": rel.get("body") or "",
                    "url": rel.get("html_url"), "path": str(target), "sha256": (asset.get("digest") or "").partition(":")[2],
                    "size": asset.get("size"), "staged_at": time.time()}
    save_state(st)
    return {"result": "staged", "tag": tag}


def start_check(force: bool = False) -> Dict[str, Any]:
    """Run check_and_stage in the background (one at a time)."""
    with _lock:
        if _job["running"]:
            return status()
        _job.update(running=True, error=None, message="Checking for a newer build", done=0, total=0, result=None)

    def run():
        try:
            res = check_and_stage(force=force)
            _job.update(result=res, message={"latest": "This is the latest build",
                                             "staged": "The new build will be installed when VEDA next starts",
                                             "already staged": "The new build will be installed when VEDA next starts",
                                             }.get(res["result"], res.get("reason", "")))
        except Exception as exc:  # noqa: BLE001 - offline, rate limited, bad download
            _job.update(error=str(exc)[:300], message="")
        finally:
            _job["running"] = False
    threading.Thread(target=run, daemon=True, name="veda-update").start()
    return status()


def scheduler() -> None:
    """Background loop of a running app: the weekly check (first after a minute, so it
    does not compete with start-up), then every hour whether a week has passed."""
    def loop():
        time.sleep(60)
        while True:
            try:
                if due():
                    start_check(force=False)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(3600)
    if install_problem() is None:
        threading.Thread(target=loop, daemon=True, name="veda-update-scheduler").start()


# ---------------------------------------------------------------- installing on start-up

def finish_install() -> None:
    """At start-up: when this build is the one that was staged, it has been installed:
    keep its notes for "What's new" and remove the previous installation."""
    st = load_state()
    staged = st.get("staged")
    build = BUILD.get("number")
    if not staged or build is None or staged.get("build") != build:
        return
    root = install_root()
    st["installed"] = {k: staged.get(k) for k in ("tag", "name", "build", "notes", "url")}
    st["installed"]["installed_at"] = time.time()
    st.pop("staged", None)
    save_state(st)
    if root is not None:
        shutil.rmtree(_previous_dir(root), ignore_errors=True)
        shutil.rmtree(_staged_dir(root), ignore_errors=True)


def _helper_script(root: Path, staged: Path, previous: Path, args) -> tuple:
    """(script path, command) for the platform's swap-and-restart script."""
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    log = UPDATES_DIR / "install.log"
    pid = os.getpid()
    if sys.platform == "win32":
        def q(p):
            return "'" + str(p).replace("'", "''") + "'"
        arglist = ", ".join(q(a) for a in args)
        exe = root / "VEDA.exe"
        body = f"""$ErrorActionPreference = 'Stop'
function Log($m) {{ Add-Content -LiteralPath {q(log)} -Value ("[" + (Get-Date -Format s) + "] " + $m) }}
function Start-Veda {{ if ({len(args)} -gt 0) {{ Start-Process -FilePath {q(exe)} -WorkingDirectory {q(root)} -ArgumentList @({arglist}) }} else {{ Start-Process -FilePath {q(exe)} -WorkingDirectory {q(root)} }} }}
Log 'waiting for VEDA (process {pid}) to exit'
try {{ Wait-Process -Id {pid} -Timeout 120 -ErrorAction SilentlyContinue }} catch {{ }}
if (Test-Path -LiteralPath {q(previous)}) {{ Remove-Item -LiteralPath {q(previous)} -Recurse -Force }}
$moved = $false
for ($i = 0; $i -lt 60 -and -not $moved; $i++) {{
  try {{ Move-Item -LiteralPath {q(root)} -Destination {q(previous)}; $moved = $true }} catch {{ Start-Sleep -Milliseconds 500 }}
}}
if (-not $moved) {{ Log 'could not move the installation aside; starting the old build'; Start-Veda; exit 1 }}
try {{ Move-Item -LiteralPath {q(staged)} -Destination {q(root)} }}
catch {{ Log ('could not move the new build in: ' + $_); Move-Item -LiteralPath {q(previous)} -Destination {q(root)}; Start-Veda; exit 1 }}
Log 'installed; starting the new build'
Start-Veda
"""
        script = UPDATES_DIR / "install_update.ps1"
        script.write_text(body, encoding="utf-8-sig")
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-WindowStyle", "Hidden", "-File", str(script)]
        return script, cmd

    def q(p):
        return "'" + str(p).replace("'", "'\\''") + "'"
    # the executable itself, not `open VEDA.app`: LaunchServices does not pass this
    # process's environment on, so a VEDA_HOME data folder would be lost on macOS
    exe = root / "VEDA.app" / "Contents" / "MacOS" / "VEDA" if sys.platform == "darwin" else root / "VEDA"
    start = f"nohup {q(exe)} {' '.join(q(a) for a in args)} >/dev/null 2>&1 &"
    body = f"""#!/bin/sh
log() {{ echo "[$(date '+%Y-%m-%dT%H:%M:%S')] $1" >> {q(log)}; }}
start_veda() {{
  {start}
}}
log 'waiting for VEDA (process {pid}) to exit'
n=0; while kill -0 {pid} 2>/dev/null && [ $n -lt 240 ]; do sleep 0.5; n=$((n+1)); done
rm -rf {q(previous)}
if ! mv {q(root)} {q(previous)}; then log 'could not move the installation aside'; start_veda; exit 1; fi
if ! mv {q(staged)} {q(root)}; then log 'could not move the new build in'; mv {q(previous)} {q(root)}; start_veda; exit 1; fi
log 'installed; starting the new build'
start_veda
"""
    script = UPDATES_DIR / "install_update.sh"
    script.write_text(body, encoding="utf-8")
    os.chmod(script, 0o755)
    return script, ["/bin/sh", str(script)]


def install_staged_on_start(args) -> bool:
    """At start-up of a published build, before anything else: when a newer build is
    staged and complete, start the swap script and return True (the caller exits at
    once; the script starts the new build with the same ``args``)."""
    if install_problem() is not None:
        return False
    st = load_state()
    staged = st.get("staged")
    root = install_root()
    if not staged or root is None:
        return False
    path = Path(staged.get("path", ""))
    if staged.get("build") is None or BUILD.get("number") is None or staged["build"] <= BUILD["number"] \
            or path != _staged_dir(root) or not _launcher(path).exists():
        return False
    _, cmd = _helper_script(root, path, _previous_dir(root), list(args))
    kw: Dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                          "close_fds": True, "cwd": str(UPDATES_DIR)}
    if sys.platform == "win32":
        # a new process group without a window (DETACHED_PROCESS would leave PowerShell
        # without the console it needs: it did not run at all), out of VEDA's job if allowed
        flags = 0x00000200 | 0x08000000                     # CREATE_NEW_PROCESS_GROUP, CREATE_NO_WINDOW
        try:
            subprocess.Popen(cmd, creationflags=flags | 0x01000000, **kw)   # CREATE_BREAKAWAY_FROM_JOB
        except OSError:
            subprocess.Popen(cmd, creationflags=flags, **kw)
        return True
    subprocess.Popen(cmd, start_new_session=True, **kw)
    return True

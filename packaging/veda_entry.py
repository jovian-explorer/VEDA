"""PyInstaller entry script for the VEDA desktop app."""
import multiprocessing
import os
import sys


def _persistent_matplotlib_dir() -> None:
    """Give Matplotlib a lasting config folder in VEDA's cache.

    PyInstaller's runtime hook points MPLCONFIGDIR at a new temporary folder on every
    start (for one-file builds, whose files move each run) and deletes it only on a
    normal exit.  Matplotlib then rebuilds its font list on every launch, and each
    killed process, including every worker process, leaves a folder in the temp
    directory.  VEDA is a one-folder build, so a folder per install location works.
    """
    hook_dir = os.environ.get("MPLCONFIGDIR")
    try:
        import hashlib
        from veda.config import CACHE_DIR
        key = hashlib.sha1(os.path.abspath(getattr(sys, "_MEIPASS", sys.executable)).encode("utf-8")).hexdigest()[:10]
        target = CACHE_DIR / "matplotlib" / key
        target.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(target)
    except Exception:  # noqa: BLE001 - keep the hook's folder
        return
    if hook_dir and hook_dir != os.environ["MPLCONFIGDIR"]:
        import shutil
        shutil.rmtree(hook_dir, ignore_errors=True)


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        _persistent_matplotlib_dir()      # before workers start: they run this too
    # Worker processes (Settings > Performance) start this same executable; freeze_support
    # hands them to multiprocessing before the desktop app is imported.
    multiprocessing.freeze_support()
    from veda.desktop import main
    raise SystemExit(main())

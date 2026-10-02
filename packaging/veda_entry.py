"""PyInstaller entry script for the VEDA desktop app."""
import multiprocessing

if __name__ == "__main__":
    # Worker processes (Settings > Performance) start this same executable; freeze_support
    # hands them to multiprocessing before the desktop app is imported.
    multiprocessing.freeze_support()
    from veda.desktop import main
    raise SystemExit(main())

"""PyInstaller entry script for the VEDA desktop app."""
import multiprocessing

from veda.desktop import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # required for a PyInstaller onefile build
    raise SystemExit(main())

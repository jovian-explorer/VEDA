"""VEDA Root Launcher.

Usage:
    python app.py                 # Launches VEDA and opens local browser
    python app.py --no-window     # Starts API server only without opening browser
    python app.py --port 8765     # Runs on specific port
"""
import sys
import os
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from app import main

if __name__ == "__main__":
    sys.exit(main())

"""Application paths and configuration for VEDA.

Planetary science data laboratory for multi-mission spacecraft observations.
Everything the app writes lives under a single writable root:
    %LOCALAPPDATA%\\VEDA\\            (Windows)
    ~/.local/share/VEDA/            (Linux/macOS fallback)
        cache/      downloaded PDS/PSA/DARTS granules & images
        exports/    generated scientific figures, NetCDF, CSV files
        settings.json
        logs/       startup and diagnostic logs
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict

APP_NAME = "VEDA"
APP_TITLE = "VEDA — Visualization, Exploration, and Data Analysis"
APP_VERSION = "2.0.0"


def _data_root() -> Path:
    env = os.environ.get("VEDA_HOME")
    if env:
        return Path(env).expanduser()
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / APP_NAME
    return Path(os.path.expanduser("~")) / ".local" / "share" / APP_NAME


DATA_ROOT = _data_root()
CACHE_DIR = DATA_ROOT / "cache"
EXPORT_DIR = DATA_ROOT / "exports"
LOG_DIR = DATA_ROOT / "logs"
SETTINGS_PATH = DATA_ROOT / "settings.json"


def bundle_root() -> Path:
    """Directory holding read-only bundled assets (frontend, sampledata)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    # When running from backend/, root is 1 level above backend
    return Path(__file__).resolve().parents[2]


def frontend_dir() -> Path:
    return bundle_root() / "frontend"


def sampledata_dir() -> Path:
    return bundle_root() / "sampledata"


def ensure_dirs() -> None:
    for d in (DATA_ROOT, CACHE_DIR, EXPORT_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


@dataclass
class Settings:
    """Persisted user settings for VEDA planetary laboratory."""
    ui_theme: str = "dark"
    ui_font_size: int = 14
    ui_mode: str = "research"
    plot_theme: str = "dark"
    plot_dpi: int = 300
    units_temperature: str = "K"
    auto_download_sample: bool = True
    default_body: str = "venus"
    default_mission: str = "akatsuki"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def load(cls) -> Settings:
        ensure_dirs()
        if not SETTINGS_PATH.is_file():
            s = cls()
            s.save()
            return s
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()

    def save(self) -> None:
        ensure_dirs()
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
                json.dump(self.to_dict(), fh, indent=2)
        except Exception:
            pass


SETTINGS = Settings.load()

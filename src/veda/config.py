"""Application paths and configuration for VEDA.

Planetary science data laboratory for multi-mission spacecraft observations.
Everything the app writes lives under a single writable root:
    %LOCALAPPDATA%\\VEDA\\                     (Windows)
    ~/Library/Application Support/VEDA/      (macOS)
    $XDG_DATA_HOME/VEDA or ~/.local/share/VEDA/ (Linux)
    $VEDA_HOME                               (override, any OS)
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

from . import __version__

APP_NAME = "VEDA"
APP_TITLE = "VEDA: Visualization, Exploration, and Data Analysis"
APP_VERSION = __version__


def _data_root() -> Path:
    env = os.environ.get("VEDA_HOME")
    if env:
        return Path(env).expanduser()
    home = Path(os.path.expanduser("~"))
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else home / "AppData" / "Local") / APP_NAME
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_NAME
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else home / ".local" / "share") / APP_NAME


DATA_ROOT = _data_root()
CACHE_DIR = DATA_ROOT / "cache"
EXPORT_DIR = DATA_ROOT / "exports"
LOG_DIR = DATA_ROOT / "logs"
SETTINGS_PATH = DATA_ROOT / "settings.json"


def bundle_root() -> Path:
    """Directory holding read-only bundled assets (frontend, sampledata).

    The assets ship inside the ``veda`` package, so this is the package
    directory for source checkouts and pip installs alike.  In a PyInstaller
    build the spec places them under ``<_MEIPASS>/veda``.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "veda"
    return Path(__file__).resolve().parent


def frontend_dir() -> Path:
    return bundle_root() / "frontend"


def sampledata_dir() -> Path:
    return bundle_root() / "sampledata"


def ensure_dirs() -> None:
    for d in (DATA_ROOT, CACHE_DIR, EXPORT_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


# Allowed values for each setting: a tuple of choices or an inclusive (min, max)
# range.  Anything else in settings.json is replaced by the default on load, so
# a hand-edited or corrupted file can never break the UI.
SETTING_CHOICES: Dict[str, Any] = {
    "ui_theme": ("dark", "light", "system"),
    "ui_font_size": (11, 20),
    "plot_dpi": (72, 1200),
    "units_temperature": ("K", "C"),
    "units_pressure": ("hPa", "bar", "Pa"),
    "network_enabled": (False, True),
    "network_timeout_s": (5, 300),
    "spice_auto_download": (False, True),
    "spice_auto_limit_mb": (10, 5000),
    "product_confirm_mb": (10, 20000),
    "cpu_workers": (1, 64),
    "download_workers": (1, 16),
    "default_body": None,       # validated against the body registry
    "default_mission": None,    # validated against the mission registry
}


@dataclass
class Settings:
    """Persisted user settings for VEDA planetary laboratory."""
    ui_theme: str = "dark"
    ui_font_size: int = 14
    plot_dpi: int = 300
    units_temperature: str = "K"
    units_pressure: str = "hPa"
    network_enabled: bool = True
    network_timeout_s: int = 30
    # Download the SPICE kernels an observation needs without asking (up to the size limit)
    spice_auto_download: bool = True
    spice_auto_limit_mb: int = 400
    # Ask before downloading a single product file larger than this (photon lists, big cubes)
    product_confirm_mb: int = 250
    # Worker processes for CPU-heavy batch work (reading and deriving many profiles,
    # climatologies, batch export); 1 keeps everything in the main process.
    cpu_workers: int = max(1, min(64, (os.cpu_count() or 2) - 1))
    # Simultaneous downloads from an archive (indexing, fetching selections)
    download_workers: int = 4
    default_body: str = "venus"
    default_mission: str = "akatsuki"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def validate(key: str, value: Any) -> Any:
        """Return the normalised value, or raise ValueError with a readable message."""
        if key not in SETTING_CHOICES:
            raise ValueError(f"Unknown setting '{key}'")
        rule = SETTING_CHOICES[key]
        default = getattr(Settings(), key)
        if isinstance(default, bool):
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be true or false")
            return value
        if isinstance(default, int):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
                raise ValueError(f"{key} must be a whole number")
            lo, hi = rule
            if not lo <= int(value) <= hi:
                raise ValueError(f"{key} must be between {lo} and {hi}")
            return int(value)
        if not isinstance(value, str):
            raise ValueError(f"{key} must be text")
        if rule is None:
            from .core.registry import get_body, get_mission
            lookup = get_body if key == "default_body" else get_mission
            if lookup(value) is None:
                raise ValueError(f"{key}: '{value}' is not a known id")
            return value
        if value not in rule:
            raise ValueError(f"{key} must be one of: {', '.join(rule)}")
        return value

    def update(self, patch: Dict[str, Any]) -> None:
        """Validate every key first, then apply all or nothing."""
        clean = {k: self.validate(k, v) for k, v in patch.items()}
        for k, v in clean.items():
            setattr(self, k, v)

    def reset(self) -> None:
        for k, v in Settings().to_dict().items():
            setattr(self, k, v)

    @classmethod
    def load(cls) -> Settings:
        ensure_dirs()
        s = cls()
        if not SETTINGS_PATH.is_file():
            s.save()
            return s
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return s
        if isinstance(data, dict):
            for k, v in data.items():
                try:
                    setattr(s, k, cls.validate(k, v))
                except ValueError:
                    pass  # keep the default for unknown or invalid entries
        return s

    def save(self) -> None:
        ensure_dirs()
        tmp = SETTINGS_PATH.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.to_dict(), fh, indent=2)
            os.replace(tmp, SETTINGS_PATH)  # atomic: no half-written file on crash
        except OSError:
            pass


SETTINGS = Settings.load()

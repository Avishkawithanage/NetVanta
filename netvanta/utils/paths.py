"""Filesystem locations used by NetVanta."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    """Per-user data folder (settings, history database, logs).

    Set NETVANTA_HOME to relocate it (used by the tests).
    """
    override = os.environ.get("NETVANTA_HOME")
    base = Path(override) if override else Path(os.environ.get("APPDATA", str(Path.home()))) / "NetVanta"
    base.mkdir(parents=True, exist_ok=True)
    return base


def log_file() -> Path:
    return data_dir() / "netvanta.log"


def database_file() -> Path:
    return data_dir() / "netvanta.db"


def settings_file() -> Path:
    return data_dir() / "settings.json"


def resource_path(relative: str) -> Path:
    """Locate a bundled resource both from source and from a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / relative

"""JSON settings with defaults, type coercion, limits and atomic writes."""

from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path

from ..defaults import DEFAULT_SETTINGS, LIMITS, LOG_LEVELS, THEMES

log = logging.getLogger("netvanta.settings")


class SettingsStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.values: dict = copy.deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        self.values = copy.deepcopy(DEFAULT_SETTINGS)
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError):
            log.warning("Settings file unreadable; using defaults", exc_info=True)
            return
        if isinstance(stored, dict):
            for key, value in stored.items():
                if key in DEFAULT_SETTINGS:
                    self.values[key] = self._coerce(key, value)

    @staticmethod
    def _coerce(key: str, value):
        default = DEFAULT_SETTINGS[key]
        try:
            if isinstance(default, bool):
                value = bool(value)
            elif isinstance(default, int):
                value = int(value)
            elif isinstance(default, float):
                value = float(value)
            elif isinstance(default, str):
                value = str(value)
            elif isinstance(default, list):
                value = [str(v) for v in value] if isinstance(value, list) else default
        except (TypeError, ValueError):
            return copy.deepcopy(default)
        if key in LIMITS:
            low, high = LIMITS[key]
            value = type(default)(min(max(value, low), high))
        if key == "theme" and value not in THEMES:
            return default
        if key == "log_level" and value not in LOG_LEVELS:
            return default
        return value

    def get(self, key: str):
        return self.values[key]

    def set(self, key: str, value) -> None:
        self.values[key] = self._coerce(key, value)

    def save(self) -> str:
        """Write atomically. Returns an error message, or '' on success."""
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self.values, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
            return ""
        except OSError as exc:
            log.error("Could not save settings: %s", exc)
            return f"Could not save settings: {exc.strerror or exc}"

    def reset(self) -> None:
        self.values = copy.deepcopy(DEFAULT_SETTINGS)
        self.save()

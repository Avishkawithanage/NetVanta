"""Shared application context handed to every view."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..data.database import Database
from ..data.repositories import HistoryRepository, TargetRepository
from ..data.settings_store import SettingsStore
from ..services.monitor_service import MonitorManager
from .bridge import UiBridge


@dataclass
class AppContext:
    root: object
    bridge: UiBridge
    settings: SettingsStore
    db: Database
    history: HistoryRepository
    targets: TargetRepository
    monitor: MonitorManager
    navigate: Callable[[str], None] = lambda name: None
    open_tool: Callable[[str, bool], None] = lambda name, run: None
    extras: dict = field(default_factory=dict)

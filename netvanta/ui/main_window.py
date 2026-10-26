"""Main window: sidebar navigation and view stack."""

from __future__ import annotations

import logging

import customtkinter as ctk

from .. import APP_NAME, __version__
from ..data.database import Database
from ..data.repositories import HistoryRepository, TargetRepository
from ..data.settings_store import SettingsStore
from ..services.monitor_service import MonitorManager
from ..utils.paths import database_file, resource_path, settings_file
from . import theme
from .bridge import UiBridge
from .context import AppContext
from .dashboard_view import DashboardView
from .history_view import HistoryView
from .monitor_view import MonitorView
from .settings_view import SettingsView
from .troubleshooting_view import TroubleshootingView

log = logging.getLogger("netvanta.ui")

NAV = [
    ("Dashboard", "▦", DashboardView),
    ("Troubleshooting", "⚒", TroubleshootingView),
    ("Live Monitor", "◉", MonitorView),
    ("History & Reports", "☰", HistoryView),
    ("Settings / About", "⚙", SettingsView),
]


class MainWindow(ctk.CTk):
    def __init__(self):
        settings = SettingsStore(settings_file())
        ctk.set_appearance_mode(settings.get("theme"))
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=theme.BG)
        self.title(f"{APP_NAME} {__version__}")
        self.geometry(f"1240x{min(800, self.winfo_screenheight() - 90)}")
        self.minsize(1000, 660)
        icon = resource_path("assets/netvanta.ico")
        if icon.exists():
            try:
                self.iconbitmap(str(icon))
            except Exception:
                log.debug("could not set window icon")
        theme.apply_tree_style(self)

        db = Database(database_file())
        history, targets = HistoryRepository(db), TargetRepository(db)
        bridge = UiBridge(self)
        monitor = MonitorManager(targets, history)
        self.ctx = AppContext(self, bridge, settings, db, history, targets, monitor)
        self.ctx.navigate = self.show
        self.ctx.open_tool = self.open_tool

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_sidebar()
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=18, pady=16)
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.views: dict[str, ctk.CTkFrame] = {}
        for name, _icon, cls in NAV:
            view = cls(self.content, self.ctx)
            view.grid(row=0, column=0, sticky="nsew")
            self.views[name] = view
        self.show("Dashboard")
        for i, (name, *_rest) in enumerate(NAV, start=1):
            self.bind(f"<Control-Key-{i}>", lambda _e, n=name: self.show(n))
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        if settings.get("monitor_autostart"):
            monitor.start_all()

    def _build_sidebar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=theme.SIDEBAR, corner_radius=0, width=220)
        bar.grid(row=0, column=0, sticky="nsw")
        bar.grid_propagate(False)
        ctk.CTkLabel(bar, text=APP_NAME, font=theme.font(24, "bold"), text_color=theme.ACCENT).pack(anchor="w", padx=20, pady=(22, 0))
        ctk.CTkLabel(bar, text="Network toolkit", font=theme.font(12), text_color=theme.MUTED).pack(anchor="w", padx=20, pady=(0, 20))
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for i, (name, icon, _cls) in enumerate(NAV, start=1):
            btn = ctk.CTkButton(bar, text=f"  {icon}   {name}", anchor="w", height=40, corner_radius=8, font=theme.font(14),
                                fg_color="transparent", hover_color=theme.SURFACE_ALT, text_color=theme.TEXT,
                                command=lambda n=name: self.show(n))
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[name] = btn
        ctk.CTkLabel(bar, text=f"v{__version__}   Ctrl+1..5", font=theme.font(11), text_color=theme.MUTED).pack(side="bottom", pady=14)

    def show(self, name: str) -> None:
        view = self.views.get(name)
        if not view:
            return
        view.tkraise()
        for key, btn in self.nav_buttons.items():
            active = key == name
            btn.configure(fg_color=theme.ACCENT if active else "transparent", text_color="#ffffff" if active else theme.TEXT)
        if hasattr(view, "on_show"):
            view.on_show()

    def open_tool(self, tool: str, run: bool = False) -> None:
        self.show("Troubleshooting")
        self.views["Troubleshooting"].show_tool(tool, run)

    def on_close(self) -> None:
        try:
            self.ctx.monitor.shutdown()
            self.ctx.bridge.close()
            self.ctx.db.close()
        except Exception:
            log.exception("error during shutdown")
        self.destroy()


def run(smoke: bool = False) -> int:
    window = MainWindow()
    if smoke:
        window.update()
        for name in list(window.views):
            window.show(name)
            window.update()
        window.after(300, window.on_close)
    window.mainloop()
    return 0

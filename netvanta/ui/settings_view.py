"""Settings and About."""

from __future__ import annotations

import os
import platform
from importlib import metadata
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import APP_NAME, __version__
from ..defaults import LIMITS, LOG_LEVELS, THEMES
from ..utils import logging_setup
from ..utils.paths import data_dir, log_file
from ..utils.validation import ValidationError, validate_number, validate_resolver, validate_url
from . import theme
from .context import AppContext
from .widgets.common import card, danger_button, primary_button, secondary_button, title_block

PRIVACY = (
    "Privacy: NetVanta stores settings, history and logs only on this PC. It has no telemetry and no account. "
    "It contacts the internet only when you press Internet Check, Public IP, run a Quick Diagnosis (its two external steps) "
    "or use the Dashboard's 'Check internet now'."
)
HELP = (
    "Troubleshooting: if a tool reports that PowerShell data is unavailable, make sure Windows PowerShell is installed and "
    "not blocked by policy. If ping shows no reply to a device you know is on, its firewall may block ICMP - try the TCP Port Test."
)


def _pkg_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "bundled"


class SettingsView(ctk.CTkScrollableFrame):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.vars: dict[str, ctk.StringVar] = {}
        title_block(self, "Settings & About", "Defaults used by the tools. Changes apply after you press Save.").pack(anchor="w", pady=(0, 10))

        box = card(self)
        box.pack(fill="x", pady=(0, 12))
        s = ctx.settings
        grid = ctk.CTkFrame(box, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=14)
        rows = [
            ("Default ping packets", "ping_count"), ("Ping timeout (ms)", "ping_timeout_ms"), ("Ping interval (s)", "ping_interval_s"),
            ("Monitor interval (s)", "monitor_interval_s"), ("Monitor timeout (ms)", "monitor_timeout_ms"),
            ("DNS server (empty = system)", "dns_resolver"), ("DNS test hostname", "dns_test_host"),
            ("Public IP endpoint (https)", "public_ip_endpoint"),
        ]
        for i, (label, key) in enumerate(rows):
            ctk.CTkLabel(grid, text=label, anchor="w", font=theme.font(13), text_color=theme.MUTED, width=210).grid(row=i, column=0, sticky="w", pady=4)
            var = ctk.StringVar(value=str(s.get(key)))
            self.vars[key] = var
            ctk.CTkEntry(grid, textvariable=var, width=320, height=32).grid(row=i, column=1, sticky="w", pady=4)

        base = len(rows)
        ctk.CTkLabel(grid, text="Theme", anchor="w", font=theme.font(13), text_color=theme.MUTED).grid(row=base, column=0, sticky="w", pady=4)
        self.theme = ctk.CTkComboBox(grid, values=list(THEMES), width=160, height=32, state="readonly")
        self.theme.set(s.get("theme"))
        self.theme.grid(row=base, column=1, sticky="w", pady=4)
        ctk.CTkLabel(grid, text="Log level", anchor="w", font=theme.font(13), text_color=theme.MUTED).grid(row=base + 1, column=0, sticky="w", pady=4)
        self.level = ctk.CTkComboBox(grid, values=list(LOG_LEVELS), width=160, height=32, state="readonly")
        self.level.set(s.get("log_level"))
        self.level.grid(row=base + 1, column=1, sticky="w", pady=4)
        ctk.CTkLabel(grid, text="Export folder", anchor="w", font=theme.font(13), text_color=theme.MUTED).grid(row=base + 2, column=0, sticky="w", pady=4)
        self.export_var = ctk.StringVar(value=s.get("export_dir"))
        row = ctk.CTkFrame(grid, fg_color="transparent")
        row.grid(row=base + 2, column=1, sticky="w")
        ctk.CTkEntry(row, textvariable=self.export_var, width=240, height=32, placeholder_text="ask every time").pack(side="left")
        secondary_button(row, "Browse…", self.browse, width=70).pack(side="left", padx=6)
        ctk.CTkLabel(grid, text="Internet endpoints\n(one https URL per line)", anchor="w", justify="left", font=theme.font(13),
                     text_color=theme.MUTED).grid(row=base + 3, column=0, sticky="nw", pady=4)
        self.endpoints = ctk.CTkTextbox(grid, width=320, height=80)
        self.endpoints.grid(row=base + 3, column=1, sticky="w", pady=4)
        self.endpoints.insert("1.0", "\n".join(s.get("internet_endpoints")))
        self.autostart = ctk.CTkCheckBox(grid, text="Start Live Monitor automatically when NetVanta opens")
        if s.get("monitor_autostart"):
            self.autostart.select()
        self.autostart.grid(row=base + 4, column=0, columnspan=2, sticky="w", pady=(8, 2))

        buttons = ctk.CTkFrame(box, fg_color="transparent")
        buttons.pack(anchor="w", padx=16, pady=(0, 14))
        primary_button(buttons, "Save settings", self.save, width=130).pack(side="left")
        danger_button(buttons, "Reset to defaults", self.reset, width=150).pack(side="left", padx=8)
        self.message = ctk.CTkLabel(buttons, text="", font=theme.font(12), text_color=theme.MUTED)
        self.message.pack(side="left", padx=8)

        about = card(self)
        about.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(about, text=f"About {APP_NAME}", font=theme.font(15, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
        info = (
            f"Version: {__version__}\nPython: {platform.python_version()}  ({platform.system()} {platform.release()})\n"
            f"customtkinter: {_pkg_version('customtkinter')}   dnspython: {_pkg_version('dnspython')}\n"
            f"Data folder: {data_dir()}\nLog file: {log_file()}"
        )
        ctk.CTkLabel(about, text=info, justify="left", anchor="w", font=theme.MONO, text_color=theme.TEXT).pack(anchor="w", padx=16)
        links = ctk.CTkFrame(about, fg_color="transparent")
        links.pack(anchor="w", padx=16, pady=8)
        secondary_button(links, "Open data folder", lambda: self._open(data_dir()), width=140).pack(side="left")
        secondary_button(links, "Open log file", lambda: self._open(log_file()), width=120).pack(side="left", padx=8)
        ctk.CTkLabel(about, text=PRIVACY, wraplength=860, justify="left", anchor="w", font=theme.font(12), text_color=theme.MUTED).pack(anchor="w", padx=16, pady=(4, 4))
        ctk.CTkLabel(about, text=HELP, wraplength=860, justify="left", anchor="w", font=theme.font(12), text_color=theme.MUTED).pack(anchor="w", padx=16, pady=(0, 14))

    def browse(self) -> None:
        folder = filedialog.askdirectory(title="Choose export folder")
        if folder:
            self.export_var.set(folder)

    @staticmethod
    def _open(path) -> None:
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except (OSError, AttributeError) as exc:
            messagebox.showerror("NetVanta", f"Could not open it: {exc}")

    def save(self) -> None:
        try:
            values = {}
            for key in ("ping_count", "ping_timeout_ms", "monitor_interval_s", "monitor_timeout_ms"):
                lo, hi = LIMITS[key]
                values[key] = validate_number(self.vars[key].get(), key.replace("_", " "), lo, hi)
            lo, hi = LIMITS["ping_interval_s"]
            values["ping_interval_s"] = validate_number(self.vars["ping_interval_s"].get(), "ping interval", lo, hi, integer=False)
            values["dns_resolver"] = validate_resolver(self.vars["dns_resolver"].get())
            values["dns_test_host"] = self.vars["dns_test_host"].get().strip() or "www.microsoft.com"
            values["public_ip_endpoint"] = validate_url(self.vars["public_ip_endpoint"].get())
            urls = [validate_url(u) for u in self.endpoints.get("1.0", "end").splitlines() if u.strip()]
            if not urls:
                raise ValidationError("Keep at least one internet endpoint.")
            values["internet_endpoints"] = urls
        except ValidationError as exc:
            self.message.configure(text=str(exc), text_color="#ef4444")
            return
        folder = self.export_var.get().strip()
        if folder and not os.path.isdir(folder):
            self.message.configure(text="The export folder does not exist.", text_color="#ef4444")
            return
        values.update(theme=self.theme.get(), log_level=self.level.get(), export_dir=folder,
                      monitor_autostart=bool(self.autostart.get()))
        for key, value in values.items():
            self.ctx.settings.set(key, value)
        error = self.ctx.settings.save()
        if error:
            self.message.configure(text=error, text_color="#ef4444")
            return
        logging_setup.set_level(self.ctx.settings.get("log_level"))
        ctk.set_appearance_mode(self.ctx.settings.get("theme"))
        theme.apply_tree_style(self.ctx.root)
        self.message.configure(text="Saved.", text_color="#22c55e")

    def reset(self) -> None:
        if not messagebox.askyesno("Reset settings", "Reset all settings to their defaults?"):
            return
        self.ctx.settings.reset()
        ctk.set_appearance_mode(self.ctx.settings.get("theme"))
        theme.apply_tree_style(self.ctx.root)
        for key, var in self.vars.items():
            var.set(str(self.ctx.settings.get(key)))
        self.theme.set(self.ctx.settings.get("theme"))
        self.level.set(self.ctx.settings.get("log_level"))
        self.export_var.set("")
        self.endpoints.delete("1.0", "end")
        self.endpoints.insert("1.0", "\n".join(self.ctx.settings.get("internet_endpoints")))
        self.autostart.deselect()
        self.message.configure(text="Defaults restored.", text_color="#22c55e")

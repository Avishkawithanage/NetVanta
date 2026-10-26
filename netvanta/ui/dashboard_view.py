"""Dashboard: real, current facts only. Unknown values are shown as Unknown."""

from __future__ import annotations

import threading

import customtkinter as ctk

from ..models.results import Status, to_local
from ..services import adapter_service, internet_check_service, ping_service
from ..services.monitor_service import DOWN, UP
from . import theme
from .bridge import BackgroundTask
from .context import AppContext
from .widgets.common import StatusChip, card, primary_button, secondary_button, title_block


class DashboardView(ctk.CTkFrame):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.task: BackgroundTask | None = None
        self.net_task: BackgroundTask | None = None
        self.columnconfigure((0, 1), weight=1, uniform="col")
        title_block(self, "Dashboard", "A quick, truthful overview of this PC's network. Nothing here is estimated or made up.").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        # connection card
        self.conn = card(self)
        self.conn.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12))
        self._header(self.conn, "Connection")
        self.conn_labels = self._rows(self.conn, ["Adapter", "IPv4 address", "Subnet", "Default gateway", "DNS servers"])

        # connectivity card
        self.conn2 = card(self)
        self.conn2.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(0, 12))
        self._header(self.conn2, "Connectivity")
        row = ctk.CTkFrame(self.conn2, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(8, 2))
        ctk.CTkLabel(row, text="Gateway (ping)", width=140, anchor="w", text_color=theme.MUTED, font=theme.font(13)).pack(side="left")
        self.gw_chip = StatusChip(row)
        self.gw_chip.pack(side="left")
        self.gw_text = ctk.CTkLabel(row, text="", anchor="w", font=theme.font(12), text_color=theme.MUTED)
        self.gw_text.pack(side="left", padx=8)
        row = ctk.CTkFrame(self.conn2, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(6, 2))
        ctk.CTkLabel(row, text="Internet (HTTPS)", width=140, anchor="w", text_color=theme.MUTED, font=theme.font(13)).pack(side="left")
        self.net_chip = StatusChip(row)
        self.net_chip.pack(side="left")
        self.net_text = ctk.CTkLabel(row, text="Not checked yet", anchor="w", font=theme.font(12), text_color=theme.MUTED)
        self.net_text.pack(side="left", padx=8)
        ctk.CTkLabel(self.conn2, text="Gateway ping stays on your local network. The internet check contacts external servers only when you press the button.",
                     wraplength=420, justify="left", font=theme.font(11), text_color=theme.MUTED).pack(anchor="w", padx=16, pady=(8, 4))
        self.net_btn = secondary_button(self.conn2, "Check internet now", self.check_internet, width=170)
        self.net_btn.pack(anchor="w", padx=16, pady=(4, 14))

        # monitor card
        self.mon = card(self)
        self.mon.grid(row=2, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12))
        self._header(self.mon, "Monitored targets")
        self.mon_labels = self._rows(self.mon, ["Configured", "Reachable", "No reply", "Not checked / stopped"])

        # events card
        self.ev = card(self)
        self.ev.grid(row=2, column=1, sticky="nsew", padx=(8, 0), pady=(0, 12))
        self._header(self.ev, "Recent connectivity events")
        self.ev_box = ctk.CTkLabel(self.ev, text="", justify="left", anchor="w", wraplength=440, font=theme.font(12), text_color=theme.TEXT)
        self.ev_box.pack(fill="x", padx=16, pady=(6, 14))

        # quick actions
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=0, columnspan=2, sticky="w")
        primary_button(actions, "Run Quick Diagnosis", lambda: ctx.open_tool("Quick Diagnosis", True), width=190).pack(side="left")
        secondary_button(actions, "IP Configuration", lambda: ctx.open_tool("IP Configuration", True), width=160).pack(side="left", padx=8)
        secondary_button(actions, "Ping…", lambda: ctx.open_tool("Ping", False), width=100).pack(side="left")
        secondary_button(actions, "Refresh", self.refresh, width=100).pack(side="left", padx=8)
        self.status_line = ctk.CTkLabel(actions, text="", font=theme.font(12), text_color=theme.MUTED)
        self.status_line.pack(side="left", padx=8)

    @staticmethod
    def _header(parent, text):
        ctk.CTkLabel(parent, text=text, font=theme.font(15, "bold"), text_color=theme.TEXT).pack(anchor="w", padx=16, pady=(12, 0))

    @staticmethod
    def _rows(parent, names):
        labels = {}
        for name in names:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(row, text=name, width=140, anchor="w", text_color=theme.MUTED, font=theme.font(13)).pack(side="left")
            value = ctk.CTkLabel(row, text="Unknown", anchor="w", text_color=theme.TEXT, font=theme.font(13, "bold"))
            value.pack(side="left")
            labels[name] = value
        ctk.CTkFrame(parent, fg_color="transparent", height=10).pack()
        return labels

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self._refresh_local_cards()
        if self.task:
            return
        self.status_line.configure(text="Refreshing…")

        def work(cancel: threading.Event, emit):
            adapters, error = adapter_service.get_adapters(cancel)
            primary = adapter_service.pick_primary(adapters)
            sample = None
            if primary:
                sample = ping_service.ping_once(primary.gateway_v4, 1500)
            return adapters, error, primary, sample

        self.task = BackgroundTask(self.ctx.bridge, work, self._loaded, self._load_failed).start()

    def _load_failed(self, _exc) -> None:
        self.task = None
        self.status_line.configure(text="Could not refresh.")

    def _loaded(self, data) -> None:
        self.task = None
        adapters, error, primary, sample = data
        L = self.conn_labels
        if primary:
            ip, prefix = primary.usable_ipv4[0]
            mask = ""
            try:
                import ipaddress
                mask = str(ipaddress.IPv4Network(f"0.0.0.0/{prefix}").netmask)
            except ValueError:
                pass
            L["Adapter"].configure(text=f"{primary.name} ({primary.kind})")
            L["IPv4 address"].configure(text=ip)
            L["Subnet"].configure(text=f"{mask} (/{prefix})" if mask else f"/{prefix}")
            L["Default gateway"].configure(text=primary.gateway_v4)
            L["DNS servers"].configure(text=", ".join(primary.dns) or "None")
            if sample and sample.success:
                self.gw_chip.set_status(Status.PASS, "✔ REPLIES")
                self.gw_text.configure(text=f"{sample.rtt_ms:g} ms")
            else:
                self.gw_chip.set_status(Status.WARNING, "⚠ NO REPLY")
                self.gw_text.configure(text="ICMP may be filtered")
            self.status_line.configure(text="Updated.")
        else:
            for label in L.values():
                label.configure(text="Unknown")
            self.gw_chip.set_status(Status.UNKNOWN)
            self.gw_text.configure(text="")
            L["Adapter"].configure(text=error or "No connected adapter with a gateway")
            self.status_line.configure(text="Updated.")

    def _refresh_local_cards(self) -> None:
        runtimes = self.ctx.monitor.runtimes()
        up = sum(1 for r in runtimes if r.running and r.state == UP)
        down = sum(1 for r in runtimes if r.running and r.state == DOWN)
        other = len(runtimes) - up - down
        self.mon_labels["Configured"].configure(text=str(len(runtimes)))
        self.mon_labels["Reachable"].configure(text=str(up))
        self.mon_labels["No reply"].configure(text=str(down))
        self.mon_labels["Not checked / stopped"].configure(text=str(other))
        events = self.ctx.history.recent_events(5)
        if events:
            self.ev_box.configure(text="\n".join(f"{to_local(e['ts'])}  {'✔' if e['status'] == 'PASS' else '✖'}  {e['summary']}" for e in events))
        else:
            self.ev_box.configure(text="No events yet. Events appear when a monitored target changes state.")

    def check_internet(self) -> None:
        if self.net_task:
            return
        self.net_chip.set_busy("CHECKING…")
        self.net_btn.configure(state="disabled")
        endpoints = list(self.ctx.settings.get("internet_endpoints"))

        def work(cancel, emit):
            return internet_check_service.run_internet_check(endpoints)

        self.net_task = BackgroundTask(self.ctx.bridge, work, self._net_done, self._net_failed).start()

    def _net_failed(self, _e) -> None:
        self.net_task = None
        self.net_btn.configure(state="normal")
        self.net_chip.set_status(Status.UNKNOWN)

    def _net_done(self, result) -> None:
        self.net_task = None
        self.net_btn.configure(state="normal")
        self.net_chip.set_status(result.status)
        self.net_text.configure(text=result.summary[:70])
        try:
            self.ctx.history.add_result(result)
        except Exception:
            pass

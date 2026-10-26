"""Live Monitor: configure targets and watch their reachability."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from ..data.repositories import Target
from ..data.database import DatabaseError
from ..defaults import LIMITS, MAX_MONITOR_TARGETS
from ..services.monitor_service import DOWN, UNKNOWN, UP, format_time
from ..utils.validation import ValidationError, validate_host, validate_number
from . import theme
from .context import AppContext
from .widgets.common import danger_button, primary_button, secondary_button, title_block
from .widgets.table import SortableTree

COLUMNS = [
    ("name", "Name", 140), ("host", "Target", 170), ("state", "State", 130), ("latency", "Latency", 80),
    ("checked", "Last checked", 90), ("recent", "Recent latency (ms)", 220), ("fails", "Recent failures", 100),
    ("every", "Every", 60),
]


class TargetDialog(ctk.CTkToplevel):
    def __init__(self, master, ctx: AppContext, target: Target | None, on_save):
        super().__init__(master)
        self.ctx, self.target, self.on_save = ctx, target, on_save
        self.title("Edit target" if target else "Add monitoring target")
        self.geometry("420x400")
        self.resizable(False, False)
        self.transient(master)
        s = ctx.settings
        self.entries = {}
        for label, key, default in (
            ("Name", "name", target.name if target else ""),
            ("Hostname or IP address", "host", target.host if target else ""),
            ("Check interval (seconds)", "interval", target.interval_s if target else s.get("monitor_interval_s")),
            ("Timeout (ms)", "timeout", target.timeout_ms if target else s.get("monitor_timeout_ms")),
        ):
            ctk.CTkLabel(self, text=label, anchor="w", font=theme.font(12)).pack(fill="x", padx=24, pady=(14, 0))
            entry = ctk.CTkEntry(self, height=34)
            entry.pack(fill="x", padx=24)
            entry.insert(0, str(default))
            self.entries[key] = entry
        self.error = ctk.CTkLabel(self, text="", text_color="#ef4444", wraplength=370, justify="left", font=theme.font(12))
        self.error.pack(fill="x", padx=24, pady=(10, 0))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=14)
        primary_button(row, "Save", self.save, width=100).pack(side="left", padx=6)
        secondary_button(row, "Cancel", self.destroy, width=100).pack(side="left", padx=6)
        self.bind("<Return>", lambda _e: self.save())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(150, self.grab_set)
        self.after(150, lambda: self.entries["name"].focus_set())

    def save(self) -> None:
        try:
            host = validate_host(self.entries["host"].get())
            name = self.entries["name"].get().strip() or host
            lo, hi = LIMITS["monitor_interval_s"]
            interval = validate_number(self.entries["interval"].get(), "Interval", lo, hi)
            lo, hi = LIMITS["monitor_timeout_ms"]
            timeout = validate_number(self.entries["timeout"].get(), "Timeout", lo, hi)
            if len(name) > 60:
                raise ValidationError("Name must be 60 characters or fewer.")
        except ValidationError as exc:
            self.error.configure(text=str(exc))
            return
        enabled = self.target.enabled if self.target else True
        target = Target(name, host, interval, timeout, enabled, self.target.id if self.target else None)
        try:
            self.on_save(target)
        except DatabaseError as exc:
            self.error.configure(text=str(exc))
            return
        self.destroy()


class MonitorView(ctk.CTkFrame):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        title_block(self, "Live Monitor",
                    "Watch hosts continuously with ping. Only state changes are recorded, so one outage is one event. "
                    "'No reply' is not proof of a service outage - ICMP can be blocked.").grid(row=0, column=0, sticky="w", pady=(0, 10))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        primary_button(bar, "Start All", self.start_all, width=100).pack(side="left")
        secondary_button(bar, "Stop All", self.stop_all, width=100).pack(side="left", padx=6)
        secondary_button(bar, "Start / Stop selected", self.toggle_selected, width=160).pack(side="left")
        ctk.CTkFrame(bar, fg_color="transparent", width=20, height=1).pack(side="left")
        secondary_button(bar, "Add target", self.add_target, width=100).pack(side="left")
        secondary_button(bar, "Edit", self.edit_target, width=70).pack(side="left", padx=6)
        secondary_button(bar, "Enable / Disable", self.toggle_enabled, width=130).pack(side="left")
        danger_button(bar, "Remove", self.remove_target, width=90).pack(side="left", padx=6)

        self.info = ctk.CTkLabel(self, text="", anchor="w", font=theme.font(12), text_color=theme.MUTED)
        self.info.grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.table = SortableTree(self, COLUMNS, height=12, selectmode="browse")
        self.table.grid(row=3, column=0, sticky="nsew")
        self.table.tree.tag_configure("up", foreground="#22c55e")
        self.table.tree.tag_configure("down", foreground="#ef4444")
        self.table.tree.tag_configure("off", foreground="#94a3b8")
        self._dirty = True
        ctx.monitor.on_change = lambda: ctx.bridge.post(self._mark_dirty)
        self._tick()

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _tick(self) -> None:
        if self._dirty or self.ctx.monitor.is_running():
            self._dirty = False
            if self.winfo_ismapped():
                self.refresh()
        self.after(1000, self._tick)

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        selected = self.table.selected()
        self.table.clear()
        runtimes = self.ctx.monitor.runtimes()
        for rt in runtimes:
            t = rt.target
            if not t.enabled:
                state, tag = "Disabled", "off"
            elif not rt.running:
                state, tag = ("Stopped", "off") if rt.state == UNKNOWN else (f"Stopped (last: {'reachable' if rt.state == UP else 'no reply'})", "off")
            elif rt.state == UP:
                state, tag = "● Reachable", "up"
            elif rt.state == DOWN:
                state, tag = "✖ No reply", "down"
            else:
                state, tag = "Checking…", "off"
            recent = " · ".join("–" if v is None else f"{v:g}" for v in list(rt.recent)[-8:])
            self.table.insert(str(t.id), (
                t.name, t.host, state, f"{rt.latency_ms:g} ms" if rt.latency_ms is not None else "-",
                format_time(rt.last_checked) or "-", recent or "-", f"{rt.recent_failures} / {len(rt.recent)}", f"{t.interval_s}s"), (tag,))
        for iid in selected:
            if self.table.tree.exists(iid):
                self.table.tree.selection_add(iid)
        if not runtimes:
            self.info.configure(text="No targets yet. Click 'Add target' - for example your router or a server you care about.")
        else:
            self.info.configure(text=f"{len(runtimes)} target(s). Monitoring only runs while you have started it; it stops when you close NetVanta.")

    def _selected_id(self) -> int | None:
        sel = self.table.selected()
        if not sel:
            self.info.configure(text="Select a target in the table first.")
            return None
        return int(sel[0])

    def _find(self, target_id: int):
        return next((r for r in self.ctx.monitor.runtimes() if r.target.id == target_id), None)

    def add_target(self) -> None:
        if len(self.ctx.monitor.runtimes()) >= MAX_MONITOR_TARGETS:
            messagebox.showinfo("NetVanta", f"You can monitor at most {MAX_MONITOR_TARGETS} targets.")
            return
        TargetDialog(self.winfo_toplevel(), self.ctx, None, lambda t: (self.ctx.monitor.add(t), self.refresh()))

    def edit_target(self) -> None:
        tid = self._selected_id()
        rt = self._find(tid) if tid else None
        if rt:
            TargetDialog(self.winfo_toplevel(), self.ctx, rt.target, lambda t: (self.ctx.monitor.update(t), self.refresh()))

    def remove_target(self) -> None:
        tid = self._selected_id()
        rt = self._find(tid) if tid else None
        if rt and messagebox.askyesno("Remove target", f"Remove '{rt.target.name}' from monitoring?\nIts past events stay in History."):
            self.ctx.monitor.remove(tid)
            self.refresh()

    def toggle_enabled(self) -> None:
        tid = self._selected_id()
        rt = self._find(tid) if tid else None
        if rt:
            self.ctx.monitor.set_enabled(tid, not rt.target.enabled)
            self.refresh()

    def toggle_selected(self) -> None:
        tid = self._selected_id()
        rt = self._find(tid) if tid else None
        if not rt:
            return
        if not rt.target.enabled:
            self.info.configure(text="This target is disabled. Use 'Enable / Disable' first.")
        elif rt.running:
            self.ctx.monitor.stop(tid)
        else:
            self.ctx.monitor.start(tid)
        self.refresh()

    def start_all(self) -> None:
        self.ctx.monitor.start_all()
        self.refresh()

    def stop_all(self) -> None:
        self.ctx.monitor.stop_all()
        self.refresh()

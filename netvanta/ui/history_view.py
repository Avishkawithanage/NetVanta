"""History & Reports: browse, filter, export and delete stored results."""

from __future__ import annotations

from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..data.database import DatabaseError
from ..models.results import to_local
from ..utils.export import ExportError, export_rows
from . import theme
from .context import AppContext
from .widgets.common import danger_button, output_box, primary_button, secondary_button, set_text, title_block
from .widgets.table import SortableTree

RANGES = {"Last hour": 1, "Last 24 hours": 24, "Last 7 days": 24 * 7, "Last 30 days": 24 * 30, "All time": None}
COLUMNS = [("time", "Time (local)", 150), ("tool", "Tool", 120), ("target", "Target", 170), ("status", "Status", 80), ("summary", "Summary", 520)]


class HistoryView(ctk.CTkFrame):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.rows: dict[str, dict] = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        title_block(self, "History & Reports", "Results of tests you ran and Live Monitor state changes, stored only on this PC.").grid(
            row=0, column=0, sticky="w", pady=(0, 10))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.range = ctk.CTkComboBox(bar, values=list(RANGES), width=140, height=34, state="readonly", command=lambda _v: self.refresh())
        self.range.set("Last 24 hours")
        self.range.pack(side="left")
        self.tool = ctk.CTkComboBox(bar, values=["All tools"], width=160, height=34, state="readonly", command=lambda _v: self.refresh())
        self.tool.set("All tools")
        self.tool.pack(side="left", padx=8)
        self.search = ctk.CTkEntry(bar, width=220, height=34, placeholder_text="Search target or summary…")
        self.search.pack(side="left")
        self.search.bind("<Return>", lambda _e: self.refresh())
        primary_button(bar, "Search", self.refresh, width=90).pack(side="left", padx=8)
        self.count = ctk.CTkLabel(bar, text="", font=theme.font(12), text_color=theme.MUTED)
        self.count.pack(side="left", padx=8)

        bar2 = ctk.CTkFrame(self, fg_color="transparent")
        bar2.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        secondary_button(bar2, "Export selected…", lambda: self.export(True), width=150).pack(side="left")
        secondary_button(bar2, "Export all shown…", lambda: self.export(False), width=150).pack(side="left", padx=8)
        danger_button(bar2, "Delete selected", self.delete_selected, width=130).pack(side="left")
        danger_button(bar2, "Clear all history", self.clear_all, width=140).pack(side="left", padx=8)

        self.table = SortableTree(self, COLUMNS, height=10)
        self.table.grid(row=3, column=0, sticky="nsew")
        self.table.tree.tag_configure("FAIL", foreground="#ef4444")
        self.table.tree.tag_configure("WARNING", foreground="#f59e0b")
        self.table.tree.bind("<<TreeviewSelect>>", lambda _e: self.show_detail())
        self.detail = output_box(self)
        self.detail.configure(height=170)
        self.detail.grid(row=4, column=0, sticky="ew", pady=(10, 0))

    def on_show(self) -> None:
        try:
            tools = self.ctx.history.tools()
            self.tool.configure(values=["All tools"] + tools)
        except DatabaseError as exc:
            messagebox.showerror("NetVanta", str(exc))
        self.refresh()

    def refresh(self) -> None:
        tool = self.tool.get()
        try:
            rows = self.ctx.history.search(RANGES[self.range.get()], "" if tool == "All tools" else tool, self.search.get().strip())
        except DatabaseError as exc:
            messagebox.showerror("NetVanta", str(exc))
            return
        self.table.clear()
        self.rows = {str(r["id"]): r for r in rows}
        for r in rows:
            self.table.insert(str(r["id"]), (to_local(r["ts"]), r["tool"], r["target"], r["status"], r["summary"]), (r["status"],))
        self.count.configure(text=f"{len(rows)} record(s)")
        set_text(self.detail, "Select a row to see its details.")

    def show_detail(self) -> None:
        sel = self.table.selected()
        if sel:
            r = self.rows.get(sel[0])
            if r:
                set_text(self.detail, f"{to_local(r['ts'])}  |  {r['tool']}  |  {r['target']}  |  {r['status']}\n\n{r['details'] or r['summary']}")

    def _chosen(self, selected_only: bool) -> list[dict]:
        if selected_only:
            return [self.rows[i] for i in self.table.selected() if i in self.rows]
        return list(self.rows.values())

    def export(self, selected_only: bool) -> None:
        rows = self._chosen(selected_only)
        if not rows:
            messagebox.showinfo("NetVanta", "There is nothing to export. " + ("Select one or more rows first." if selected_only else ""))
            return
        path = filedialog.asksaveasfilename(
            title="Export history", defaultextension=".csv", initialdir=self.ctx.settings.get("export_dir") or None,
            initialfile="netvanta_history", filetypes=[("CSV", "*.csv"), ("JSON", "*.json")])
        if not path:
            return
        out = [{"timestamp_utc": r["ts"], "timestamp_local": to_local(r["ts"]), "tool": r["tool"], "target": r["target"],
                "status": r["status"], "summary": r["summary"], "duration_ms": round(r["duration_ms"], 1)} for r in rows]
        try:
            export_rows(path, out)
            messagebox.showinfo("NetVanta", f"Exported {len(out)} record(s) to:\n{path}")
        except ExportError as exc:
            messagebox.showerror("NetVanta", str(exc))

    def delete_selected(self) -> None:
        ids = [int(i) for i in self.table.selected()]
        if not ids:
            messagebox.showinfo("NetVanta", "Select one or more rows first.")
            return
        if messagebox.askyesno("Delete history", f"Permanently delete {len(ids)} selected record(s)?"):
            try:
                self.ctx.history.delete(ids)
            except DatabaseError as exc:
                messagebox.showerror("NetVanta", str(exc))
            self.refresh()

    def clear_all(self) -> None:
        if messagebox.askyesno("Clear history", "Permanently delete ALL history records? This cannot be undone."):
            try:
                self.ctx.history.clear()
            except DatabaseError as exc:
                messagebox.showerror("NetVanta", str(exc))
            self.refresh()

"""Base class giving every troubleshooting tool the same layout and behaviour."""

from __future__ import annotations

import threading
from tkinter import filedialog, messagebox
from typing import Any, Callable

import customtkinter as ctk

from ...models.results import CheckResult, Status
from ...utils.export import ExportError, export_result
from ...utils.validation import ValidationError
from .. import theme
from ..bridge import BackgroundTask
from ..context import AppContext
from .common import (StatusChip, append_text, card, copy_to_clipboard, output_box, primary_button,
                     secondary_button, set_text, title_block)


class ToolPanel(ctk.CTkFrame):
    name = "Tool"
    description = ""
    run_label = "Run"
    streaming = False  # append live lines while running
    filterable = False
    save_history = True
    has_stop = True

    def __init__(self, master, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.task: BackgroundTask | None = None
        self.result: CheckResult | None = None
        self._showing_raw = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        title_block(self, self.name, self.description).grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.inputs = card(self)
        self.inputs.grid(row=1, column=0, sticky="ew")
        self.build_inputs(self.inputs)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=10)
        self.run_btn = primary_button(actions, self.run_label, self.run, width=170)
        self.run_btn.pack(side="left")
        self.stop_btn = secondary_button(actions, "Stop", self.stop, width=80)
        if self.has_stop:
            self.stop_btn.pack(side="left", padx=8)
            self.stop_btn.configure(state="disabled")
        secondary_button(actions, "Clear", self.clear, width=80).pack(side="left")
        self.chip = StatusChip(actions)
        self.chip.pack(side="left", padx=(16, 8))
        self.summary = ctk.CTkLabel(actions, text="", font=theme.font(13), text_color=theme.TEXT,
                                    anchor="w", justify="left", wraplength=520)
        self.summary.pack(side="left", fill="x", expand=True)

        self.output = output_box(self)
        self.output.grid(row=3, column=0, sticky="nsew")

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.copy_btn = secondary_button(bottom, "Copy summary", self.copy_summary, width=130)
        self.copy_btn.pack(side="left")
        self.export_btn = secondary_button(bottom, "Export CSV / JSON…", self.export, width=160)
        self.export_btn.pack(side="left", padx=8)
        self.raw_btn = secondary_button(bottom, "Show raw output", self.toggle_raw, width=140)
        self.raw_btn.pack(side="left")
        self.raw_btn.configure(state="disabled")
        self.filter_var = ctk.StringVar()
        if self.filterable:
            self.filter_entry = ctk.CTkEntry(bottom, textvariable=self.filter_var, width=240, height=34,
                                             placeholder_text="Filter results…")
            self.filter_entry.pack(side="right")
            self.filter_var.trace_add("write", lambda *_: self.refresh_view())
        self._update_buttons()

    # ---- to be provided by tools -------------------------------------------------
    def build_inputs(self, parent) -> None:
        ctk.CTkLabel(parent, text="No options - just press the button.", text_color=theme.MUTED,
                     font=theme.font(12)).pack(padx=16, pady=14, anchor="w")

    def read_params(self) -> Any:
        return None

    def work(self, params: Any, cancel: threading.Event, emit: Callable[[str], None]) -> CheckResult:
        raise NotImplementedError

    # ---- helpers for subclasses --------------------------------------------------
    def field(self, parent, label: str, default: str = "", width: int = 160, column: int = 0, row: int = 0,
              placeholder: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, font=theme.font(12), text_color=theme.MUTED).grid(
            row=row * 2, column=column, sticky="w", padx=(16, 6), pady=(10, 0))
        entry = ctk.CTkEntry(parent, width=width, height=34, placeholder_text=placeholder)
        entry.grid(row=row * 2 + 1, column=column, sticky="w", padx=(16, 6), pady=(2, 12))
        if default:
            entry.insert(0, str(default))
        entry.bind("<Return>", lambda _e: self.run())
        return entry

    # ---- lifecycle -----------------------------------------------------------------
    def on_show(self) -> None:
        pass

    def run(self) -> None:
        if self.task is not None:  # ignore repeated clicks while running
            return
        try:
            params = self.read_params()
        except ValidationError as exc:
            self.chip.set_status(Status.FAIL, "INPUT")
            self.summary.configure(text=str(exc))
            return
        self.result, self._showing_raw = None, False
        set_text(self.output, "")
        self.chip.set_busy()
        self.summary.configure(text="Working… you can keep using the app.")
        self.task = BackgroundTask(
            self.ctx.bridge,
            lambda cancel, emit: self.work(params, cancel, emit),
            self._done,
            self._failed,
            self._on_emit,
        ).start()
        self._update_buttons()

    def stop(self) -> None:
        if self.task:
            self.task.cancel()
            self.summary.configure(text="Stopping…")
            self.stop_btn.configure(state="disabled")

    def clear(self) -> None:
        if self.task:
            return
        self.result = None
        set_text(self.output, "")
        self.chip.set_status(None)
        self.summary.configure(text="")
        self._update_buttons()

    def _on_emit(self, item: Any) -> None:
        if self.streaming and isinstance(item, str):
            append_text(self.output, item)

    def _failed(self, exc: Exception) -> None:
        self.task = None
        self.chip.set_status(Status.FAIL, "ERROR")
        self.summary.configure(text="Something went wrong. Details were written to the log file.")
        self._update_buttons()

    def _done(self, result: CheckResult) -> None:
        self.task = None
        self.result = result
        self.chip.set_status(Status.UNKNOWN, "STOPPED") if result.cancelled else self.chip.set_status(result.status)
        self.summary.configure(text=result.summary)
        if self.streaming and self.output.get("1.0", "end").strip():
            append_text(self.output, "\n" + "-" * 60 + "\n" + self.footer(result))
        else:
            self.refresh_view()
        if self.save_history:
            try:
                self.ctx.history.add_result(result)
            except Exception:
                import logging
                logging.getLogger("netvanta.ui").exception("could not save history")
        self._update_buttons()

    # ---- output ----------------------------------------------------------------------
    def render_body(self, result: CheckResult, filter_text: str) -> str:
        text = result.render()
        if filter_text:
            needle = filter_text.lower()
            text = "\n".join(line for line in text.splitlines() if needle in line.lower())
        return text

    def footer(self, result: CheckResult) -> str:
        """Text appended after live output when a streaming tool finishes."""
        return result.render()

    def refresh_view(self) -> None:
        if not self.result or (self.streaming and self.task):
            return
        if self._showing_raw:
            set_text(self.output, self.result.raw)
        else:
            set_text(self.output, self.render_body(self.result, self.filter_var.get().strip()))

    def toggle_raw(self) -> None:
        if not self.result:
            return
        self._showing_raw = not self._showing_raw
        self.raw_btn.configure(text="Show summary" if self._showing_raw else "Show raw output")
        self.refresh_view()

    def _update_buttons(self) -> None:
        busy = self.task is not None
        self.run_btn.configure(state="disabled" if busy else "normal")
        if self.has_stop:
            self.stop_btn.configure(state="normal" if busy else "disabled")
        has = self.result is not None and not busy
        self.copy_btn.configure(state="normal" if has else "disabled")
        self.export_btn.configure(state="normal" if has else "disabled")
        self.raw_btn.configure(state="normal" if has and self.result.raw else "disabled")

    def copy_summary(self) -> None:
        if self.result and copy_to_clipboard(self.winfo_toplevel(), self.result.clipboard_summary()):
            self.summary.configure(text="Copied to clipboard.")

    def export(self) -> None:
        if not self.result:
            return
        path = filedialog.asksaveasfilename(
            title="Export results", defaultextension=".csv",
            initialdir=self.ctx.settings.get("export_dir") or None,
            initialfile=f"netvanta_{self.name.lower().replace(' ', '_')}",
            filetypes=[("CSV (table)", "*.csv"), ("JSON (full result)", "*.json")],
        )
        if not path:
            return
        try:
            export_result(path, self.result)
            messagebox.showinfo("NetVanta", f"Exported to:\n{path}")
        except ExportError as exc:
            messagebox.showerror("NetVanta", str(exc))

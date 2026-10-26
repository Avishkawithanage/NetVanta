"""Ping tool: finite or continuous, with a live 'lost / timed out' log next to the replies."""

from __future__ import annotations

import time

import customtkinter as ctk

from ..defaults import LIMITS
from ..services import ping_service
from ..services.ping_service import PingSample, find_outages, format_outage, local_time
from ..utils.validation import validate_host, validate_number
from . import theme
from .widgets.common import append_text, output_box, set_text
from .widgets.tool_panel import ToolPanel

MAX_LINES = 3000  # keep the live boxes light during very long runs
NO_LOSS = "No lost or timed-out packets so far."


class PingPanel(ToolPanel):
    name = "Ping"
    description = ("Send ICMP echo requests and watch each reply live. Tick 'Continuous' to keep pinging until you press Stop - "
                   "every lost packet is listed with its time on the right. No reply does not always mean a host is down.")
    run_label = "Start Ping"
    streaming = True

    def build_inputs(self, parent):
        s = self.ctx.settings
        self.target = self.field(parent, "Hostname or IP address", "", 260, 0, placeholder="e.g. 8.8.8.8 or example.com")
        self.count = self.field(parent, "Packets", s.get("ping_count"), 80, 1)
        self.timeout = self.field(parent, "Timeout (ms)", s.get("ping_timeout_ms"), 100, 2)
        self.interval = self.field(parent, "Interval (s)", s.get("ping_interval_s"), 90, 3)
        self.continuous = ctk.CTkCheckBox(parent, text="Continuous (until Stop)", command=self._toggle_continuous)
        self.continuous.grid(row=1, column=4, padx=16, pady=(2, 12), sticky="w")

    def _toggle_continuous(self) -> None:
        self.count.configure(state="disabled" if self.continuous.get() else "normal")

    def build_output(self):
        holder = ctk.CTkFrame(self, fg_color="transparent")
        holder.columnconfigure((0, 1), weight=1, uniform="half")
        holder.rowconfigure(2, weight=1)
        self.counters = ctk.CTkLabel(holder, text="", anchor="w", font=theme.font(13, "bold"), text_color=theme.TEXT)
        self.counters.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ctk.CTkLabel(holder, text="All replies", anchor="w", font=theme.font(12), text_color=theme.MUTED).grid(row=1, column=0, sticky="w")
        ctk.CTkLabel(holder, text="Lost / timed out (with time)", anchor="w", font=theme.font(12), text_color="#f59e0b").grid(
            row=1, column=1, sticky="w", padx=(10, 0))
        self.output = output_box(holder)
        self.output.grid(row=2, column=0, sticky="nsew")
        self.problems = output_box(holder)
        self.problems.grid(row=2, column=1, sticky="nsew", padx=(10, 0))
        self._samples: list[PingSample] = []
        self._reset_counters()
        set_text(self.problems, NO_LOSS)
        return holder

    # ---- state --------------------------------------------------------------------
    def _reset_counters(self) -> None:
        self._samples = []
        self._sent = self._received = 0
        self._rtt_sum = 0.0
        self._rtt_min = self._rtt_max = None
        self._started = time.monotonic()
        self._lost_run = 0
        self._has_problems = False
        self._show_counters()

    def reset_view(self) -> None:
        self._reset_counters()
        set_text(self.problems, NO_LOSS)
        self.counters.configure(text="")

    def _show_counters(self) -> None:
        if not self._sent:
            self.counters.configure(text="")
            return
        lost = self._sent - self._received
        loss = lost / self._sent * 100
        avg = f"{self._rtt_sum / self._received:.1f}" if self._received else "-"
        mn = f"{self._rtt_min:g}" if self._received else "-"
        mx = f"{self._rtt_max:g}" if self._received else "-"
        elapsed = int(time.monotonic() - self._started)
        self.counters.configure(
            text=(f"Sent {self._sent}    Received {self._received}    Lost {lost} ({loss:.1f}%)    "
                  f"Latency min/avg/max {mn}/{avg}/{mx} ms    Running {elapsed // 60:02d}:{elapsed % 60:02d}"))

    # ---- live updates ---------------------------------------------------------------
    def _on_emit(self, item):
        if isinstance(item, str):
            append_text(self.output, item, MAX_LINES)
            return
        s: PingSample = item
        self._samples.append(s)
        self._sent += 1
        stamp = local_time(s.ts)
        if s.success:
            self._received += 1
            self._rtt_sum += s.rtt_ms or 0
            self._rtt_min = s.rtt_ms if self._rtt_min is None else min(self._rtt_min, s.rtt_ms)
            self._rtt_max = s.rtt_ms if self._rtt_max is None else max(self._rtt_max, s.rtt_ms)
            append_text(self.output, f"{stamp}  #{s.seq:<5} reply   {s.rtt_ms:g} ms", MAX_LINES)
            if self._lost_run:
                append_text(self.problems, f"{stamp}      replies are back after {self._lost_run} lost packet(s)", MAX_LINES)
                self._lost_run = 0
        else:
            append_text(self.output, f"{stamp}  #{s.seq:<5} NO REPLY", MAX_LINES)
            if not self._has_problems:
                set_text(self.problems, "")
                self._has_problems = True
            self._lost_run += 1
            append_text(self.problems, f"{stamp}  #{s.seq:<5} lost - {s.message}", MAX_LINES)
        self._show_counters()

    def _done(self, result):
        super()._done(result)
        outages = find_outages(self._samples)
        if outages:
            append_text(self.problems, "")
            append_text(self.problems, f"SUMMARY - {len(outages)} loss event(s):")
            for o in outages[:200]:
                append_text(self.problems, "  " + format_outage(o))
        self._show_counters()

    # ---- run ------------------------------------------------------------------------------
    def read_params(self):
        if self.continuous.get():
            count = 0
        else:
            lo, hi = LIMITS["ping_count"]
            count = validate_number(self.count.get(), "Packets", lo, hi)
        lo, hi = LIMITS["ping_timeout_ms"]
        timeout = validate_number(self.timeout.get(), "Timeout", lo, hi)
        lo, hi = LIMITS["ping_interval_s"]
        interval = validate_number(self.interval.get(), "Interval", lo, hi, integer=False)
        return validate_host(self.target.get()), count, timeout, interval

    def work(self, params, cancel, emit):
        target, count, timeout, interval = params
        emit(f"Pinging {target}" + (" continuously - press Stop to finish ..." if count == 0 else " ..."))
        return ping_service.run_ping(target, count, timeout, interval, cancel, on_sample=emit)

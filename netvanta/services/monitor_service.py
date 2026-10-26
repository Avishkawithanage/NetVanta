"""Live Monitor: bounded background polling with state-transition (not per-check) events."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from ..data.repositories import MONITOR_TOOL, HistoryRepository, Target, TargetRepository
from ..models.results import utc_now_iso
from . import ping_service

log = logging.getLogger("netvanta.monitor")

DOWN_AFTER_FAILURES = 2  # consecutive failures before a target is reported as "no reply"
MAX_WORKERS = 8

UNKNOWN, UP, DOWN = "unknown", "up", "down"


@dataclass
class Runtime:
    target: Target
    state: str = UNKNOWN
    running: bool = False
    latency_ms: float | None = None
    last_checked: str = ""
    consecutive_failures: int = 0
    inflight: bool = False
    next_due: float = 0.0
    recent: deque = field(default_factory=lambda: deque(maxlen=20))  # latency or None per check
    last_message: str = ""

    @property
    def recent_failures(self) -> int:
        return sum(1 for v in self.recent if v is None)

    def record(self, ok: bool, latency: float | None, message: str = "") -> tuple[str, str] | None:
        """Record one check. Returns (old_state, new_state) only when the state changes."""
        self.last_checked = utc_now_iso()
        self.last_message = message
        self.recent.append(latency if ok else None)
        old = self.state
        if ok:
            self.consecutive_failures = 0
            self.latency_ms = latency
            self.state = UP
        else:
            self.consecutive_failures += 1
            self.latency_ms = None
            if self.consecutive_failures >= DOWN_AFTER_FAILURES:
                self.state = DOWN
        if self.state != old and not (old == UNKNOWN and self.state == UP):
            return old, self.state
        return None


Probe = Callable[[str, int], tuple[bool, float | None, str]]


class MonitorManager:
    def __init__(
        self,
        targets: TargetRepository,
        history: HistoryRepository,
        probe: Probe = ping_service.probe_target,
        on_change: Callable[[], None] | None = None,
    ):
        self.targets_repo = targets
        self.history = history
        self.probe = probe
        self.on_change = on_change or (lambda: None)
        self._lock = threading.RLock()
        self._runtimes: dict[int, Runtime] = {}
        self._pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="monitor")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.reload()

    # ---- target management -------------------------------------------------
    def reload(self) -> None:
        with self._lock:
            old = self._runtimes
            self._runtimes = {}
            for target in self.targets_repo.list():
                rt = old.get(target.id) or Runtime(target)
                rt.target = target
                self._runtimes[target.id] = rt

    def runtimes(self) -> list[Runtime]:
        with self._lock:
            return sorted(self._runtimes.values(), key=lambda r: r.target.name.lower())

    def add(self, target: Target) -> Target:
        self.targets_repo.add(target)
        self.reload()
        return target

    def update(self, target: Target) -> None:
        self.targets_repo.update(target)
        self.reload()

    def remove(self, target_id: int) -> None:
        with self._lock:
            self._runtimes.pop(target_id, None)
        self.targets_repo.delete(target_id)
        self.on_change()

    def set_enabled(self, target_id: int, enabled: bool) -> None:
        with self._lock:
            rt = self._runtimes.get(target_id)
            if not rt:
                return
            rt.target.enabled = enabled
            if not enabled:
                rt.running = False
        self.targets_repo.update(rt.target)
        self.on_change()

    # ---- running -----------------------------------------------------------
    def start(self, target_id: int) -> None:
        with self._lock:
            rt = self._runtimes.get(target_id)
            if rt and rt.target.enabled and not rt.running:
                rt.running, rt.next_due = True, 0.0
        self._ensure_thread()
        self.on_change()

    def stop(self, target_id: int) -> None:
        with self._lock:
            rt = self._runtimes.get(target_id)
            if rt:
                rt.running = False
        self.on_change()

    def start_all(self) -> None:
        for rt in self.runtimes():
            self.start(rt.target.id)

    def stop_all(self) -> None:
        with self._lock:
            for rt in self._runtimes.values():
                rt.running = False
        self.on_change()

    def is_running(self) -> bool:
        with self._lock:
            return any(rt.running for rt in self._runtimes.values())

    def shutdown(self) -> None:
        self._stop.set()
        self.stop_all()
        self._pool.shutdown(wait=False, cancel_futures=True)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    # ---- internals ---------------------------------------------------------
    def _ensure_thread(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="monitor-scheduler", daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            now = time.monotonic()
            due: list[Runtime] = []
            with self._lock:
                for rt in self._runtimes.values():
                    if rt.running and not rt.inflight and now >= rt.next_due:
                        rt.inflight = True
                        due.append(rt)
            for rt in due:
                try:
                    self._pool.submit(self._check, rt)
                except RuntimeError:  # pool shut down
                    return
            if self._stop.wait(0.25):
                return

    def _check(self, rt: Runtime) -> None:
        try:
            ok, latency, message = self.probe(rt.target.host, rt.target.timeout_ms)
        except Exception as exc:  # a probe must never kill the worker
            log.exception("probe failed")
            ok, latency, message = False, None, str(exc)
        transition = None
        with self._lock:
            if not rt.running:  # stopped while the check was in flight: discard
                rt.inflight = False
                return
            transition = rt.record(ok, latency, message)
            rt.inflight = False
            rt.next_due = time.monotonic() + rt.target.interval_s
        if transition:
            self._record_event(rt, *transition)
        self.on_change()

    def _record_event(self, rt: Runtime, old: str, new: str) -> None:
        name = rt.target.name
        if new == DOWN:
            status, summary = "FAIL", f"{name} ({rt.target.host}): no ping reply after {DOWN_AFTER_FAILURES} consecutive checks."
        else:
            status, summary = "PASS", f"{name} ({rt.target.host}): reachable again."
        try:
            self.history.add(utc_now_iso(), MONITOR_TOOL, rt.target.host, status, summary,
                             f"{summary}\nState change: {old} -> {new}\nA missing ping reply is not proof of a service outage.")
        except Exception:
            log.exception("could not record monitor event")


def format_time(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).astimezone().strftime("%H:%M:%S")
    except ValueError:
        return ""

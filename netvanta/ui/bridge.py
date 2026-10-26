"""Thread-safe hand-off from background workers to the Tk main thread."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Callable

log = logging.getLogger("netvanta.ui")


class UiBridge:
    """Workers call post(); the Tk thread drains the queue on a timer."""

    def __init__(self, root):
        self.root = root
        self._queue: queue.Queue = queue.Queue()
        self._closed = False
        self._poll()

    def post(self, fn: Callable, *args) -> None:
        if not self._closed:
            self._queue.put((fn, args))

    def _poll(self) -> None:
        if self._closed:
            return
        for _ in range(300):
            try:
                fn, args = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args)
            except Exception:
                log.exception("UI callback failed")
        try:
            self.root.after(40, self._poll)
        except Exception:
            self._closed = True

    def close(self) -> None:
        self._closed = True


class BackgroundTask:
    """Runs work(cancel, emit) on a daemon thread; callbacks run on the UI thread."""

    def __init__(
        self,
        bridge: UiBridge,
        work: Callable[[threading.Event, Callable[[Any], None]], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[Exception], None] | None = None,
        on_emit: Callable[[Any], None] | None = None,
    ):
        self.bridge = bridge
        self.work, self.on_done, self.on_error, self.on_emit = work, on_done, on_error, on_emit
        self.cancel_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="netvanta-task", daemon=True)

    def start(self) -> "BackgroundTask":
        self._thread.start()
        return self

    def cancel(self) -> None:
        self.cancel_event.set()

    def _emit(self, item: Any) -> None:
        if self.on_emit:
            self.bridge.post(self.on_emit, item)

    def _run(self) -> None:
        try:
            result = self.work(self.cancel_event, self._emit)
        except Exception as exc:
            log.exception("Background task failed")
            if self.on_error:
                self.bridge.post(self.on_error, exc)
            return
        self.bridge.post(self.on_done, result)

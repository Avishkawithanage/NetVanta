"""Safe subprocess execution: argument lists only, timeouts, cancellation, no console window."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger("netvanta.subprocess")

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


@dataclass
class CommandResult:
    args: list[str]
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    cancelled: bool = False
    error: str = ""  # set when the command could not be started

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.cancelled and not self.error


def _decode(data: bytes, encoding: str) -> str:
    for enc in (encoding, "utf-8"):
        try:
            return data.decode(enc, errors="replace")
        except LookupError:
            continue
    return data.decode("latin-1", errors="replace")


def _kill(proc: subprocess.Popen) -> None:
    try:
        proc.kill()
    except OSError:
        pass


def run_command(
    args: list[str],
    timeout: float = 10.0,
    cancel: threading.Event | None = None,
    encoding: str = "oem",
) -> CommandResult:
    """Run a command to completion. Never uses a shell."""
    result = CommandResult(args=list(args))
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            creationflags=_NO_WINDOW,
        )
    except FileNotFoundError:
        result.error = f"Command not found: {args[0]}"
        return result
    except OSError as exc:
        result.error = f"Could not start {args[0]}: {exc}"
        return result

    deadline = time.monotonic() + timeout
    out = err = b""
    while True:
        try:
            out, err = proc.communicate(timeout=0.2)
            break
        except subprocess.TimeoutExpired:
            if cancel is not None and cancel.is_set():
                result.cancelled = True
            elif time.monotonic() >= deadline:
                result.timed_out = True
            else:
                continue
            _kill(proc)
            out, err = proc.communicate()
            break
    result.returncode = proc.returncode
    result.stdout = _decode(out or b"", encoding)
    result.stderr = _decode(err or b"", encoding)
    return result


def stream_command(
    args: list[str],
    on_line: Callable[[str], None],
    timeout: float = 60.0,
    cancel: threading.Event | None = None,
    encoding: str = "oem",
) -> CommandResult:
    """Run a command and report each output line as it arrives (stderr merged)."""
    result = CommandResult(args=list(args))
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=_NO_WINDOW,
        )
    except FileNotFoundError:
        result.error = f"Command not found: {args[0]}"
        return result
    except OSError as exc:
        result.error = f"Could not start {args[0]}: {exc}"
        return result

    lines: list[str] = []

    def reader() -> None:
        assert proc.stdout is not None
        for chunk in iter(proc.stdout.readline, b""):
            line = _decode(chunk, encoding).rstrip("\r\n")
            lines.append(line)
            try:
                on_line(line)
            except Exception:  # a UI callback must never break the reader
                log.exception("on_line callback failed")

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    deadline = time.monotonic() + timeout
    while thread.is_alive():
        thread.join(0.2)
        if cancel is not None and cancel.is_set():
            result.cancelled = True
        elif time.monotonic() >= deadline:
            result.timed_out = True
        else:
            continue
        _kill(proc)
        thread.join(2.0)
        break
    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        _kill(proc)
    result.returncode = proc.returncode
    result.stdout = "\n".join(lines)
    return result


_PS_PREFIX = (
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    "$ProgressPreference='SilentlyContinue';$ErrorActionPreference='SilentlyContinue';"
)


def run_powershell(script: str, timeout: float = 25.0, cancel: threading.Event | None = None) -> CommandResult:
    args = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        _PS_PREFIX + script,
    ]
    return run_command(args, timeout=timeout, cancel=cancel, encoding="utf-8-sig")


def as_list(value: Any) -> list:
    """PowerShell's ConvertTo-Json collapses 1-item arrays; normalise to a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def run_powershell_json(
    script: str, timeout: float = 25.0, cancel: threading.Event | None = None
) -> tuple[Any, CommandResult]:
    """Run a PowerShell script that prints JSON. Returns (data or None, CommandResult)."""
    res = run_powershell(script, timeout=timeout, cancel=cancel)
    text = res.stdout.strip().lstrip("﻿")
    if not text or res.error or res.timed_out or res.cancelled:
        return None, res
    try:
        return json.loads(text), res
    except json.JSONDecodeError:
        log.warning("PowerShell returned non-JSON output: %.200s", text)
        return None, res

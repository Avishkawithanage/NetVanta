"""TCP port connectivity test. Bounded, for systems you own or are authorised to test."""

from __future__ import annotations

import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..models.results import CheckResult, Status

MAX_WORKERS = 6
NOTE = "A timeout does not prove a port is closed: firewalls and routing problems also cause timeouts."


@dataclass
class PortResult:
    port: int
    outcome: str  # connected | refused | timeout | dns_error | error
    ms: float | None = None
    message: str = ""


def check_port(host: str, port: int, timeout: float = 3.0) -> PortResult:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return PortResult(port, "connected", (time.monotonic() - started) * 1000)
    except socket.gaierror as exc:
        return PortResult(port, "dns_error", None, exc.strerror or str(exc))
    except ConnectionRefusedError:
        return PortResult(port, "refused", (time.monotonic() - started) * 1000, "Host answered but nothing listens on this port")
    except (TimeoutError, socket.timeout):
        return PortResult(port, "timeout", None, f"No answer within {timeout:g}s")
    except OSError as exc:
        return PortResult(port, "error", None, exc.strerror or str(exc))


def run_port_check(host: str, ports: list[int], timeout: float = 3.0, cancel: threading.Event | None = None) -> CheckResult:
    started = time.monotonic()
    cancel = cancel or threading.Event()

    def task(port: int) -> PortResult:
        if cancel.is_set():
            return PortResult(port, "error", None, "Cancelled")
        return check_port(host, port, timeout)

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(ports))) as pool:
        results = list(pool.map(task, ports))

    labels = {"connected": "CONNECTED", "refused": "REFUSED", "timeout": "TIMED OUT", "dns_error": "DNS ERROR", "error": "ERROR"}
    result = CheckResult(tool="TCP Port Test", target=f"{host}:{','.join(map(str, ports))}")
    result.duration_ms = (time.monotonic() - started) * 1000
    result.rows = [
        {"host": host, "port": r.port, "outcome": r.outcome, "connect_ms": round(r.ms, 1) if r.ms is not None else "", "message": r.message}
        for r in results
    ]
    result.details = "\n".join(
        f"Port {r.port:<6} {labels[r.outcome]:<10}" + (f" {r.ms:.0f} ms" if r.ms is not None and r.outcome == "connected" else "") + (f"  {r.message}" if r.message else "")
        for r in results
    )
    opened = sum(1 for r in results if r.outcome == "connected")
    if cancel.is_set():
        result.cancelled, result.status, result.summary = True, Status.UNKNOWN, "Stopped by user - results are partial."
    elif any(r.outcome == "dns_error" for r in results):
        result.status, result.summary = Status.FAIL, f"The name '{host}' could not be resolved."
        result.recommendation = "Check the spelling or test DNS with the DNS Lookup tool."
    elif opened == len(results):
        result.status, result.summary = Status.PASS, f"{opened} of {len(results)} port(s) accepted a connection."
    elif opened:
        result.status, result.summary = Status.WARNING, f"{opened} of {len(results)} port(s) accepted a connection."
        result.recommendation = NOTE
    else:
        result.status, result.summary = Status.FAIL, "No tested port accepted a connection."
        result.recommendation = NOTE
    return result

"""ICMP ping via the Windows ping.exe, parsed in a locale-tolerant way."""

from __future__ import annotations

import ipaddress
import re
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable

from ..models.results import CheckResult, Status
from ..utils.subprocess_runner import run_command

ICMP_NOTE = "No reply does not prove a host is down: ICMP can be blocked or deprioritised by firewalls and routers."

_REPLY_MS = re.compile(r"[=<]\s*(\d+)\s*ms", re.I)


@dataclass
class PingSample:
    seq: int
    success: bool
    rtt_ms: float | None = None
    address: str = ""
    message: str = ""


@dataclass
class PingSummary:
    sent: int
    received: int
    lost: int
    loss_pct: float
    min_ms: float | None
    avg_ms: float | None
    max_ms: float | None


def summarize(samples: list[PingSample]) -> PingSummary:
    sent = len(samples)
    rtts = [s.rtt_ms for s in samples if s.success and s.rtt_ms is not None]
    received = sum(1 for s in samples if s.success)
    loss = (sent - received) / sent * 100 if sent else 0.0
    return PingSummary(
        sent=sent,
        received=received,
        lost=sent - received,
        loss_pct=round(loss, 1),
        min_ms=min(rtts) if rtts else None,
        avg_ms=round(sum(rtts) / len(rtts), 1) if rtts else None,
        max_ms=max(rtts) if rtts else None,
    )


def parse_ping_output(text: str, seq: int = 1, address: str = "") -> PingSample:
    """Interpret one ping.exe run (one probe).

    A reply line has no comma and carries 'time=Xms' / 'time<1ms'. The statistics
    footer ('Minimum = 0ms, ...') contains commas and is ignored, so "Destination
    host unreachable" replies are not mistaken for successes.
    """
    for line in text.splitlines():
        if "," in line or ":" not in line:
            continue
        match = _REPLY_MS.search(line)
        if match:
            value = float(match.group(1))
            if "<" in line[: match.end()] and value <= 1:
                value = 0.5
            return PingSample(seq, True, value, address, line.strip())
    cleaned = [ln.strip() for ln in text.splitlines() if ln.strip() and "," not in ln and "=" not in ln]
    message = cleaned[-1] if cleaned else "No reply"
    return PingSample(seq, False, None, address, message)


def resolve_target(target: str) -> tuple[str, str]:
    """Return (ip address, error message)."""
    try:
        ipaddress.ip_address(target.strip("[]"))
        return target.strip("[]"), ""
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(target, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        return "", f"DNS resolution failed for '{target}': {exc.strerror or exc}"
    except UnicodeError:
        return "", f"'{target}' is not a valid hostname."
    ordered = sorted(infos, key=lambda i: i[0] != socket.AF_INET)  # prefer IPv4
    return ordered[0][4][0], ""


def ping_once(
    address: str, timeout_ms: int = 2000, seq: int = 1, cancel: threading.Event | None = None
) -> PingSample:
    """One ICMP echo to an already-resolved IP address."""
    args = ["ping", "-n", "1", "-w", str(int(timeout_ms))]
    if ":" in address:
        args.append("-6")
    args.append(address)
    res = run_command(args, timeout=timeout_ms / 1000 + 4, cancel=cancel)
    if res.error:
        return PingSample(seq, False, None, address, res.error)
    if res.cancelled:
        return PingSample(seq, False, None, address, "Cancelled")
    if res.timed_out:
        return PingSample(seq, False, None, address, "ping.exe did not finish in time")
    return parse_ping_output(res.stdout, seq, address)


def probe_target(host: str, timeout_ms: int = 2000) -> tuple[bool, float | None, str]:
    """Resolve + ping one probe. Used by the monitor. Returns (ok, rtt, message)."""
    address, error = resolve_target(host)
    if error:
        return False, None, error
    sample = ping_once(address, timeout_ms)
    return sample.success, sample.rtt_ms, sample.message


def format_sample(sample: PingSample, target: str) -> str:
    if sample.success:
        return f"Reply from {sample.address}: time={sample.rtt_ms:g} ms  (#{sample.seq})"
    return f"Request #{sample.seq}: no reply ({sample.message})"


def run_ping(
    target: str,
    count: int,
    timeout_ms: int,
    interval_s: float,
    cancel: threading.Event | None = None,
    on_sample: Callable[[PingSample], None] | None = None,
) -> CheckResult:
    started = time.monotonic()
    cancel = cancel or threading.Event()
    result = CheckResult(tool="Ping", target=target)
    address, error = resolve_target(target)
    if error:
        result.status = Status.FAIL
        result.summary = "The name could not be resolved."
        result.error = error
        result.recommendation = "Check the spelling, or test the DNS server with the DNS Lookup tool."
        result.duration_ms = (time.monotonic() - started) * 1000
        return result

    samples: list[PingSample] = []
    for seq in range(1, count + 1):
        if cancel.is_set():
            break
        sample = ping_once(address, timeout_ms, seq, cancel)
        if sample.message == "Cancelled":
            break
        samples.append(sample)
        if on_sample:
            on_sample(sample)
        if seq < count and cancel.wait(interval_s):
            break

    stats = summarize(samples)
    result.duration_ms = (time.monotonic() - started) * 1000
    result.rows = [
        {"seq": s.seq, "address": s.address, "success": s.success, "rtt_ms": s.rtt_ms if s.rtt_ms is not None else ""}
        for s in samples
    ]
    lines = [f"Target: {target}" + (f" ({address})" if address != target else "")]
    lines.append(f"Sent {stats.sent}, received {stats.received}, lost {stats.lost} ({stats.loss_pct:g}% loss)")
    if stats.avg_ms is not None:
        lines.append(f"Latency: min {stats.min_ms:g} ms, avg {stats.avg_ms:g} ms, max {stats.max_ms:g} ms")
    result.details = "\n".join(lines)

    if cancel.is_set():
        result.cancelled = True
        result.status = Status.UNKNOWN
        result.summary = f"Stopped by user after {stats.sent} packet(s) - results are partial."
    elif stats.sent == 0:
        result.status = Status.UNKNOWN
        result.summary = "No packets were sent."
    elif stats.received == 0:
        result.status = Status.FAIL
        result.summary = f"No reply from {target}."
        result.recommendation = ICMP_NOTE + " Try a TCP port test to the service you care about."
    elif stats.lost:
        result.status = Status.WARNING
        result.summary = f"{stats.loss_pct:g}% packet loss to {target}."
        result.recommendation = "Some packets were lost; repeat the test with more packets to see if it is consistent."
    else:
        result.status = Status.PASS
        result.summary = f"{target} replied to all {stats.sent} packet(s), average {stats.avg_ms:g} ms."
    return result

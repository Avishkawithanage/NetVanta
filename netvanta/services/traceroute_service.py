"""Traceroute via tracert.exe with live, partial-result friendly parsing."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

from ..models.results import CheckResult, Status
from ..utils.subprocess_runner import stream_command

_HOP = re.compile(r"^\s*(\d{1,2})\s+(.*\S)\s*$")
_TIME = re.compile(r"(<?\d+)\s*ms", re.I)
_ADDR = re.compile(r"(?:\[([0-9a-fA-F:.]+)\]|([0-9]{1,3}(?:\.[0-9]{1,3}){3}|[0-9a-fA-F]*:[0-9a-fA-F:]+))\s*$")

NOTE = "A '*' or missing hop usually means a router filters or rate-limits probes - it does not necessarily mean a broken route."


@dataclass
class Hop:
    number: int
    address: str
    host: str
    times: list[str]

    @property
    def responded(self) -> bool:
        return bool(self.address)


def parse_hop(line: str) -> Hop | None:
    match = _HOP.match(line)
    if not match:
        return None
    number, rest = int(match.group(1)), match.group(2)
    times = _TIME.findall(rest)
    stars = rest.count("*")
    if not times and stars and not _ADDR.search(rest):
        return Hop(number, "", "", ["*"] * min(stars, 3))
    addr_match = _ADDR.search(rest)
    address = (addr_match.group(1) or addr_match.group(2)) if addr_match else ""
    host = ""
    if addr_match:
        before = _TIME.sub("", rest[: addr_match.start()]).replace("*", "").strip()
        host = before if before and before != address else ""
    elif not times:
        return None
    shown = [t + "" if t.startswith("<") else t for t in times]
    return Hop(number, address, host, [f"{t} ms" for t in shown] + ["*"] * stars)


def run_traceroute(
    target: str,
    max_hops: int = 30,
    per_hop_timeout_ms: int = 2000,
    resolve_names: bool = False,
    cancel: threading.Event | None = None,
    on_line: Callable[[str], None] | None = None,
) -> CheckResult:
    started = time.monotonic()
    args = ["tracert", "-h", str(max_hops), "-w", str(per_hop_timeout_ms)]
    if not resolve_names:
        args.append("-d")
    args.append(target)
    budget = max_hops * (per_hop_timeout_ms / 1000 * 3 + 1) + 10
    hops: list[Hop] = []

    def handle(line: str) -> None:
        hop = parse_hop(line)
        if hop:
            hops.append(hop)
        if on_line and line.strip():
            on_line(line)

    cmd = stream_command(args, handle, timeout=min(budget, 240), cancel=cancel)
    result = CheckResult(tool="Traceroute", target=target, raw=cmd.stdout)
    result.duration_ms = (time.monotonic() - started) * 1000
    result.rows = [
        {"hop": h.number, "address": h.address or "*", "host": h.host, "times": " ".join(h.times)} for h in hops
    ]
    responded = sum(1 for h in hops if h.responded)
    if cmd.error:
        result.status, result.summary, result.error = Status.FAIL, "Traceroute could not run.", cmd.error
    elif cmd.cancelled:
        result.cancelled = True
        result.status = Status.UNKNOWN
        result.summary = f"Stopped by user - partial result with {len(hops)} hop(s)."
    elif cmd.timed_out:
        result.status = Status.WARNING
        result.summary = f"Traceroute timed out - partial result with {len(hops)} hop(s)."
    elif "could not find host" in cmd.stdout.lower() or (not hops and cmd.returncode not in (0, None)):
        result.status = Status.FAIL
        result.summary = "The target could not be resolved or traced."
        result.recommendation = "Check the spelling of the name or the IP address."
    elif hops and hops[-1].responded:
        result.status = Status.PASS
        result.summary = f"Trace reached {hops[-1].address} in {len(hops)} hop(s)."
    else:
        result.status = Status.WARNING
        result.summary = f"Trace finished with {responded} responding hop(s) of {len(hops)}; the destination did not answer."
    result.recommendation = result.recommendation or NOTE
    result.details = (
        "\n".join(f"{h.number:>3}  {(h.address or '*'):<40} {' '.join(h.times)}" for h in hops) if hops else ""
    )
    return result

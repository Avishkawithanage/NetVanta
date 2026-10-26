"""ARP / neighbour table viewer (read-only) using 'arp -a'."""

from __future__ import annotations

import re
import time

from ..models.results import CheckResult, Status
from ..utils.subprocess_runner import run_command

_IFACE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})\s+---")
_ENTRY = re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})\s+(\S+)\s*$")

NOTE = "The ARP table only lists devices this PC talked to recently. It can be stale or incomplete and is not a full device scan."


def parse_arp(text: str) -> list[dict]:
    rows: list[dict] = []
    interface = ""
    for line in text.splitlines():
        iface = _IFACE.search(line)
        if iface:
            interface = iface.group(1)
            continue
        entry = _ENTRY.match(line)
        if entry:
            rows.append(
                {
                    "ip": entry.group(1),
                    "mac": entry.group(2).replace("-", ":").upper(),
                    "type": entry.group(3),
                    "interface": interface,
                }
            )
    return rows


def read_arp_table() -> CheckResult:
    started = time.monotonic()
    res = run_command(["arp", "-a"], timeout=10)
    result = CheckResult(tool="ARP Table", raw=res.stdout, duration_ms=(time.monotonic() - started) * 1000)
    if res.error or res.timed_out:
        result.status, result.summary = Status.FAIL, "Could not read the ARP table."
        result.error = res.error or "arp.exe timed out"
        return result
    rows = parse_arp(res.stdout)
    result.rows = rows
    result.recommendation = NOTE
    if rows:
        result.status = Status.PASS
        result.summary = f"{len(rows)} neighbour entr{'y' if len(rows) == 1 else 'ies'} found."
        width = max(len(r["ip"]) for r in rows)
        result.details = "\n".join(
            f"{r['ip']:<{width + 2}}{r['mac']:<20}{r['type']:<9}via {r['interface']}" for r in rows
        )
    else:
        result.status = Status.WARNING
        result.summary = "The ARP table has no entries."
    return result

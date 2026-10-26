"""DNS resolver cache viewer (read-only) using Get-DnsClientCache."""

from __future__ import annotations

import threading
import time

from ..models.results import CheckResult, Status
from ..utils.subprocess_runner import as_list, run_powershell_json

_SCRIPT = r"""
@(Get-DnsClientCache | ForEach-Object { @{ name=[string]$_.Entry; type=[string]$_.Type; ttl=[int]$_.TimeToLive; data=[string]$_.Data; status=[string]$_.Status } }) | ConvertTo-Json -Depth 3 -Compress
"""

_TYPES = {"1": "A", "2": "NS", "5": "CNAME", "6": "SOA", "12": "PTR", "15": "MX", "16": "TXT", "28": "AAAA", "33": "SRV"}


def parse_cache(data) -> list[dict]:
    rows = []
    for item in as_list(data):
        if isinstance(item, dict):
            kind = str(item.get("type", ""))
            rows.append(
                {
                    "name": item.get("name", ""),
                    "type": _TYPES.get(kind, kind),
                    "ttl": item.get("ttl", 0),
                    "data": item.get("data", ""),
                }
            )
    rows.sort(key=lambda r: (r["name"].lower(), r["type"]))
    return rows


def filter_rows(rows: list[dict], text: str) -> list[dict]:
    needle = text.strip().lower()
    if not needle:
        return rows
    return [r for r in rows if needle in r["name"].lower() or needle in str(r["data"]).lower()]


def read_dns_cache(cancel: threading.Event | None = None) -> CheckResult:
    started = time.monotonic()
    data, res = run_powershell_json(_SCRIPT, timeout=25, cancel=cancel)
    result = CheckResult(tool="DNS Cache", duration_ms=(time.monotonic() - started) * 1000)
    if data is None:
        if res.cancelled:
            result.cancelled, result.status, result.summary = True, Status.UNKNOWN, "Cancelled."
            return result
        if not res.error and not res.timed_out and res.returncode == 0:
            result.status = Status.WARNING  # empty cache prints nothing
            result.summary = "The DNS cache is empty."
            return result
        result.status = Status.FAIL
        result.summary = "Could not read the DNS cache."
        result.error = res.error or ("Timed out." if res.timed_out else "Windows refused or does not support Get-DnsClientCache.")
        result.recommendation = "Try running NetVanta again; this read-only feature needs the DNS Client service running."
        return result
    rows = parse_cache(data)
    result.rows = rows
    result.status = Status.PASS if rows else Status.WARNING
    result.summary = f"{len(rows)} cached record(s). Use the filter box to narrow them."
    result.recommendation = "Read-only view. NetVanta never flushes or alters the DNS cache."
    return result


def format_rows(rows: list[dict]) -> str:
    if not rows:
        return "No matching records."
    header = f"{'Name':<52}{'Type':<8}{'TTL':<8}Data"
    return header + "\n" + "\n".join(f"{r['name']:<52}{r['type']:<8}{r['ttl']:<8}{r['data']}" for r in rows)

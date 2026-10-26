"""Routing table viewer (read-only) using Get-NetRoute."""

from __future__ import annotations

import ipaddress
import threading
import time

from ..models.results import CheckResult, Status
from ..utils.subprocess_runner import as_list, run_powershell_json

_SCRIPT = r"""
$names = @{}; Get-NetAdapter | ForEach-Object { $names[[int]$_.ifIndex] = [string]$_.Name }
@(Get-NetRoute | ForEach-Object { @{ prefix=[string]$_.DestinationPrefix; nexthop=[string]$_.NextHop; index=[int]$_.InterfaceIndex; alias=[string]$_.InterfaceAlias; metric=[int]$_.RouteMetric; ifmetric=[int]$_.InterfaceMetric; family=[string]$_.AddressFamily } }) | ConvertTo-Json -Depth 4 -Compress
"""


def parse_routes(data) -> list[dict]:
    rows = []
    for item in as_list(data):
        if not isinstance(item, dict):
            continue
        prefix = item.get("prefix", "")
        netmask = ""
        try:
            net = ipaddress.ip_network(prefix, strict=False)
            if net.version == 4:
                netmask = str(net.netmask)
        except ValueError:
            pass
        rows.append(
            {
                "destination": prefix,
                "netmask": netmask,
                "next_hop": item.get("nexthop", ""),
                "interface": item.get("alias") or item.get("index"),
                "metric": int(item.get("metric") or 0) + int(item.get("ifmetric") or 0),
                "family": "IPv6" if ":" in prefix else "IPv4",
            }
        )
    rows.sort(key=lambda r: (r["family"], r["destination"] != "0.0.0.0/0", r["metric"], r["destination"]))
    return rows


def read_routes(cancel: threading.Event | None = None) -> CheckResult:
    started = time.monotonic()
    data, res = run_powershell_json(_SCRIPT, timeout=25, cancel=cancel)
    result = CheckResult(tool="Routing Table", duration_ms=(time.monotonic() - started) * 1000)
    if data is None:
        result.status = Status.UNKNOWN if res.cancelled else Status.FAIL
        result.cancelled = res.cancelled
        result.summary = "Could not read the routing table."
        result.error = res.error or ("Timed out." if res.timed_out else "Windows did not return route data.")
        return result
    rows = parse_routes(data)
    result.rows = rows
    result.status = Status.PASS if rows else Status.WARNING
    result.summary = f"{len(rows)} route(s) found." if rows else "No routes were returned."
    result.recommendation = "Read-only view. NetVanta never adds, deletes or changes routes."
    result.details = "\n".join(
        f"{r['destination']:<44}{r['netmask']:<17}{r['next_hop']:<40}{str(r['interface']):<22}{r['metric']}" for r in rows
    )
    defaults = [r for r in rows if r["destination"] in ("0.0.0.0/0", "::/0")]
    result.simple = (
        "Traffic that has no more specific route goes through the default route(s):\n\n"
        + "\n".join(f"  {r['destination']:<10} via {r['next_hop']:<40} on {r['interface']}  (cost {r['metric']})" for r in defaults)
        + f"\n\n({len(rows)} routes in total - press 'Show details' for the whole table.)"
    ) if defaults else ""
    if rows:
        header = f"{'Destination':<44}{'Netmask':<17}{'Next hop':<40}{'Interface':<22}Metric"
        result.details = header + "\n" + result.details
    return result

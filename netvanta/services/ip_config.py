"""IP Configuration view over the shared adapter service."""

from __future__ import annotations

import ipaddress
import threading
import time

from ..models.results import CheckResult, Status
from .adapter_service import AdapterInfo, adapter_row, format_adapter, get_adapters, pick_primary


def _mask(prefix: int) -> str:
    try:
        return str(ipaddress.IPv4Network(f"0.0.0.0/{prefix}").netmask)
    except ValueError:
        return ""


def format_primary(a: AdapterInfo) -> str:
    ip, prefix = a.usable_ipv4[0]
    mask = _mask(prefix)
    has_global_v6 = any(not addr.lower().startswith("fe80") for addr, _p in a.ipv6)
    rows = [
        ("Adapter", f"{a.name}  ({a.kind}, {a.status})"),
        ("IP address", ip),
        ("Subnet mask", f"{mask}  (/{prefix})" if mask else f"/{prefix}"),
        ("Default gateway", a.gateway_v4 or "None"),
        ("DNS servers", ", ".join(d for d in a.dns if ":" not in d) or "None"),
        ("MAC address", a.mac or "Not provided"),
        ("Link speed", a.speed or "Not provided"),
    ]
    if has_global_v6:
        rows.append(("IPv6", "yes (global address present)"))
    text = "\n".join(f"  {label:<18}{value}" for label, value in rows)
    if a.has_link_local_only:
        text += "\n  Note: only a 169.254.x.x address - DHCP may have failed."
    return text


def format_table(adapters: list[AdapterInfo]) -> str:
    header = f"  {'Adapter':<36}{'Type':<11}{'Status':<14}{'IPv4 address':<18}{'Gateway'}"
    lines = [header, "  " + "-" * (len(header) - 2)]
    for a in adapters:
        ip = a.ipv4[0][0] if a.ipv4 else "-"
        gw = a.gateway_v4 or "-"
        lines.append(f"  {a.name[:34]:<36}{a.kind:<11}{a.status[:12]:<14}{ip:<18}{gw}")
    return "\n".join(lines)


def check_ip_configuration(cancel: threading.Event | None = None) -> CheckResult:
    """Simple view = the main connection. Details = every adapter plus IPv6 and traffic."""
    started = time.monotonic()
    adapters, error = get_adapters(cancel)
    result = CheckResult(tool="IP Configuration", duration_ms=(time.monotonic() - started) * 1000)
    if error:
        result.status = Status.FAIL if error != "Cancelled." else Status.UNKNOWN
        result.cancelled = error == "Cancelled."
        result.summary = "Could not read network configuration."
        result.error = error
        return result

    primary = pick_primary(adapters)
    others = [a for a in adapters if a is not primary]
    others.sort(key=lambda a: (not a.is_up, a.kind == "Virtual", a.name.lower()))
    up = sum(1 for a in adapters if a.is_up)
    if primary:
        result.status = Status.PASS
        result.summary = (f"Connected via {primary.name} ({primary.kind}) - IP {primary.usable_ipv4[0][0]}, "
                          f"gateway {primary.gateway_v4}.")
    elif up:
        result.status = Status.WARNING
        result.summary = f"{up} adapter(s) up, but none has a usable IPv4 address with a default gateway."
        result.recommendation = "Check DHCP / static IP settings, or whether the connection is VPN-only."
    else:
        result.status = Status.FAIL
        result.summary = "No network adapter is connected."
        result.recommendation = "Check the cable, Wi-Fi switch and that the adapter is enabled."

    if primary:
        main = "MAIN CONNECTION\n" + format_primary(primary)
    else:
        real = [a for a in others if a.is_up and a.kind != "Virtual"] or others[:3]
        main = "NO WORKING CONNECTION FOUND\n" + format_table(real) if real else "NO NETWORK ADAPTERS FOUND"
    if result.recommendation:
        main += "\n\nWhat to do: " + result.recommendation
    hidden = len(others)
    result.simple = main + (f"\n\n({hidden} other adapter(s), mostly virtual or disconnected - press 'Show details' to see them.)" if hidden and primary else "")

    parts = [main]
    if others:
        parts.append("ALL OTHER ADAPTERS\n" + format_table(others))
    parts.append("FULL DETAILS (IPv6 addresses, traffic counters)\n\n" + "\n\n".join(format_adapter(a) for a in ([primary] if primary else []) + others))
    result.details = "\n\n".join(parts)
    result.rows = [adapter_row(a) for a in ([primary] if primary else []) + others]
    return result

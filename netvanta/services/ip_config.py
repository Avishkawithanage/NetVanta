"""IP Configuration and Adapter Information views over the shared adapter service."""

from __future__ import annotations

import threading
import time

from ..models.results import CheckResult, Status
from .adapter_service import adapter_row, format_adapter, get_adapters, pick_primary


def check_ip_configuration(cancel: threading.Event | None = None, include_inactive: bool = True) -> CheckResult:
    started = time.monotonic()
    adapters, error = get_adapters(cancel)
    result = CheckResult(tool="IP Configuration", duration_ms=(time.monotonic() - started) * 1000)
    if error:
        result.status = Status.FAIL if error != "Cancelled." else Status.UNKNOWN
        result.cancelled = error == "Cancelled."
        result.summary = "Could not read network configuration."
        result.error = error
        return result
    shown = [a for a in adapters if include_inactive or a.is_up]
    primary = pick_primary(adapters)
    shown.sort(key=lambda a: (a is not primary, not a.is_up, a.name.lower()))
    up = sum(1 for a in adapters if a.is_up)
    if primary:
        ip = primary.usable_ipv4[0][0]
        result.status = Status.PASS
        result.summary = f"{up} adapter(s) up. Primary connection: {primary.name} ({primary.kind}), {ip}, gateway {primary.gateway_v4}."
    elif up:
        result.status = Status.WARNING
        result.summary = f"{up} adapter(s) up, but none has a usable IPv4 address with a default gateway."
        result.recommendation = "Check DHCP / static IP settings, or whether the connection is VPN-only."
    else:
        result.status = Status.FAIL
        result.summary = "No network adapter is connected."
        result.recommendation = "Check the cable, Wi-Fi switch and that the adapter is enabled."
    result.details = "\n\n".join(("* PRIMARY\n" if a is primary else "") + format_adapter(a) for a in shown)
    result.rows = [adapter_row(a) for a in shown]
    return result

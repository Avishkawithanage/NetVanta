"""Full Analysis: cable/link health + Quick Diagnosis, combined into a "where is the problem" verdict."""

from __future__ import annotations

import threading
import time

from ..models.results import CheckResult, Status
from . import link_health_service
from .diagnosis_service import run_quick_diagnosis

P, F, W, S, U = Status.PASS, Status.FAIL, Status.WARNING, Status.SKIPPED, Status.UNKNOWN

LAYERS = [
    ("cable", "1  Cable / physical link"),
    ("address", "2  Addressing (IP, DHCP, gateway set)"),
    ("local", "3  Local network (gateway reachable)"),
    ("dns", "4  Name resolution (DNS)"),
    ("internet", "5  Internet path"),
    ("target", "6  Selected target"),
]

WHY = {
    "cable": "Look at the cable, connectors, switch port and the device at the other end first (swap cable and port to see if the fault follows).",
    "address": "The PC is not getting a usable address or gateway: check the DHCP server/router, the switch port's VLAN, or a wrong static IP.",
    "local": "The gateway/router is not reachable on the local network: check the router, switch, VLAN or cable between them.",
    "dns": "Names do not resolve but the connection works: the DNS server is down, unreachable or wrong - try another DNS server.",
    "internet": "The local network is fine but nothing reaches the internet: check the router's WAN/modem, ISP outage or a firewall rule.",
    "target": "General connectivity is fine but the selected target does not answer: the target may be down or filtering ICMP.",
}


def _worst(*statuses: Status | None) -> Status:
    present = [s for s in statuses if s is not None and s not in (S, U)]
    if not present:
        return S
    for level in (F, W):
        if level in present:
            return level
    return P


def build_layers(link: Status, steps: dict[str, Status]) -> dict[str, Status]:
    g = steps.get
    internet_ok = g("internet_ip") == P or g("https") == P
    gateway_ping = g("gateway_ping")
    if gateway_ping in (F, W) and internet_ok:
        gateway_ping = P  # router just filters ICMP; traffic clearly flows
    return {
        "cable": link,
        "address": _worst(g("adapter"), g("ip"), g("gateway")),
        "local": gateway_ping if gateway_ping is not None else S,
        "dns": g("dns") or S,
        "internet": P if internet_ok and g("internet_ip") != F else _worst(g("internet_ip"), g("https")),
        "target": g("target") or S,
    }


def locate(layers: dict[str, Status]) -> tuple[str, Status, str]:
    """Return (layer key or '', level, explanation) - the first failing layer, else the first weak one."""
    for level in (F, W):
        for key, label in LAYERS:
            if layers.get(key) == level:
                word = "Most likely problem area" if level == F else "Possible weak spot"
                return key, level, f"{word}: {label.strip()}. {WHY[key]}"
    return "", P, ("No problem was found in any tested layer. If one user still has trouble while this laptop works, "
                   "the problem is probably in that user's PC (its settings, proxy, firewall or software) rather than the cable or network.")


def run_full_analysis(settings: dict, target: str = "", cancel: threading.Event | None = None, emit=None) -> CheckResult:
    started = time.monotonic()
    cancel = cancel or threading.Event()

    def say(text: str) -> None:
        if emit:
            emit(text)

    say("STEP A - cable and link health (about 10 seconds) ...")
    link = link_health_service.run_link_health(cancel, on_line=say)
    say(f"   -> {link.status.value}: {link.summary}\n")
    result = CheckResult(tool="Full Analysis", target=target)
    if cancel.is_set():
        result.cancelled, result.status = True, U
        result.summary = "Stopped by user - partial result, not a complete analysis."
        return result

    say("STEP B - connectivity checks (about 15 seconds) ...")
    diag = run_quick_diagnosis(settings, target, cancel, on_step=lambda step: say(step.line() + "\n"))
    if diag.cancelled:
        result.cancelled, result.status = True, U
        result.summary = "Stopped by user - partial result, not a complete analysis."
        return result

    steps = {row["key"]: Status(row["status"]) for row in diag.rows}
    wired_connected = any(r.get("connected") for r in link.rows)
    other_connection_works = steps.get("ip") == P and steps.get("gateway") == P
    note = ""
    if not link.rows or (not wired_connected and other_connection_works):
        cable_level = S  # no cable in use (e.g. Wi-Fi is the active connection): the cable layer does not apply
        note = "\n\nNote: no wired link is in use (the active connection is not Ethernet), so the cable layer was not counted."
    else:
        cable_level = link.status
    layers = build_layers(cable_level, steps)
    key, level, verdict = locate(layers)
    table = "\n".join(f"  {label:<42}[{layers[k].value}]" for k, label in LAYERS)
    result.status = level
    result.summary = verdict.split(". ")[0] + "." if key else "No problem found in any tested layer."
    result.recommendation = ""
    result.details = (
        "PROBLEM LOCATION\n\n" + table + "\n\n" + verdict + note +
        "\n\nEVIDENCE - CABLE AND LINK\n\n" + link.details + "\n\nEVIDENCE - CONNECTIVITY\n\n" + diag.details
    )
    result.rows = [{"layer": label.strip(), "status": layers[k].value} for k, label in LAYERS]
    result.duration_ms = (time.monotonic() - started) * 1000
    return result

"""Quick Network Diagnosis: independent real checks + deterministic, evidence-based rules."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from ..models.results import CheckResult, Status
from . import adapter_service, dns_service, internet_check_service, ping_service, tcp_check_service

IP_PROBE = ("1.1.1.1", 443)


@dataclass
class Step:
    key: str
    title: str
    status: Status
    evidence: str
    explanation: str = ""
    advice: str = ""
    external: bool = False

    def line(self) -> str:
        tag = " (external)" if self.external else ""
        text = f"[{self.status.value}] {self.title}{tag}\n    Evidence: {self.evidence}"
        if self.explanation:
            text += f"\n    {self.explanation}"
        if self.advice:
            text += f"\n    Next step: {self.advice}"
        return text


def interpret(s: dict[str, Status]) -> list[tuple[Status, str, str]]:
    """Map step statuses to (level, finding, advice). Pure function, easy to test."""
    P, F, W = Status.PASS, Status.FAIL, Status.WARNING
    get = s.get
    out: list[tuple[Status, str, str]] = []
    if get("adapter") == F:
        out.append((F, "No active network adapter was found - likely a disconnected cable, Wi-Fi turned off or a disabled adapter.",
                    "Check the cable or Wi-Fi switch and enable the adapter in Network Connections."))
    elif get("ip") == F:
        out.append((F, "The active adapter has no usable IPv4 address - possible DHCP problem (a 169.254.x.x address means no DHCP answer).",
                    "Reconnect, restart the router, or check for a static IP typo."))
    elif get("gateway") == F:
        out.append((F, "No default gateway is configured - the PC cannot leave the local network.",
                    "Check the router/DHCP settings or the static gateway entry."))
    else:
        gw, inet, dns, https = get("gateway_ping"), get("internet_ip"), get("dns"), get("https")
        reachable_externally = inet == P or https == P
        if gw in (F, W) and reachable_externally:
            out.append((W, "The gateway does not answer ping, but internet traffic works - the router most likely filters ICMP. This is usually harmless.",
                        "No action needed unless you specifically need ping to the router."))
        elif gw == F and inet == F and https != P:
            out.append((F, "Possible local network or router problem: the gateway is silent and no external connection works (ICMP could be filtered, so this is not certain).",
                        "Restart the router/modem and check the cable or Wi-Fi signal."))
        if dns == F and inet == P:
            out.append((F, "Possible DNS issue: connecting by IP address works but names cannot be resolved.",
                        "Try another DNS server (for example 1.1.1.1 or 8.8.8.8) in the adapter settings or the DNS Lookup tool."))
        elif dns == F and inet == F and gw != F:
            out.append((F, "The gateway answers but neither DNS nor external connections work - possible ISP outage, upstream problem or a firewall.",
                        "Check the router's internet/WAN status and contact the ISP if it persists."))
        if dns == P and inet == F:
            out.append((W, "Names resolve but a direct connection to an external IP fails - possible firewall rule blocking outbound traffic (or the probe address is blocked).",
                        "Check firewall/proxy policy; compare with the HTTPS result."))
        if dns == P and inet == P and https == F:
            out.append((W, "Basic connectivity works but HTTPS requests fail - possible proxy, TLS/certificate or wrong system clock problem.",
                        "Check the system date/time, proxy settings and security software."))
        if get("target") == F and not [o for o in out if o[0] == F]:
            out.append((W, "General connectivity looks fine but the selected target did not reply - the target may be down or may filter ICMP.",
                        "Try a TCP port test against the service you need."))
    if not out:
        out.append((P, "No problem detected by these checks.", "If something still fails, test the specific target with Ping, DNS Lookup or TCP Port Test."))
    return out


def run_quick_diagnosis(
    settings: dict,
    extra_target: str = "",
    cancel: threading.Event | None = None,
    on_step: Callable[[Step], None] | None = None,
) -> CheckResult:
    started = time.monotonic()
    cancel = cancel or threading.Event()
    steps: list[Step] = []

    def add(step: Step) -> Step:
        steps.append(step)
        if on_step:
            on_step(step)
        return step

    def stopped() -> bool:
        return cancel.is_set()

    adapters, error = adapter_service.get_adapters(cancel)
    primary = adapter_service.pick_primary(adapters)
    up = [a for a in adapters if a.is_up]

    if error:
        add(Step("adapter", "Network adapter status", Status.UNKNOWN, error, "Adapter data was unavailable, so dependent checks are skipped.", external=False))
    elif up:
        add(Step("adapter", "Network adapter status", Status.PASS, ", ".join(f"{a.name} ({a.kind})" for a in up)))
    else:
        add(Step("adapter", "Network adapter status", Status.FAIL, "No adapter reports status 'Up'.", advice="Connect a cable or enable Wi-Fi."))

    if not stopped():
        if primary:
            ip, prefix = primary.usable_ipv4[0]
            add(Step("ip", "Local IP configuration", Status.PASS, f"{primary.name}: {ip}/{prefix}, DNS {', '.join(primary.dns) or 'none'}"))
        elif any(a.has_link_local_only for a in up):
            add(Step("ip", "Local IP configuration", Status.FAIL, "Only a 169.254.x.x (link-local) address was found.", "DHCP probably did not answer.", "Reconnect or restart the router."))
        elif up:
            first = next((a for a in up if a.usable_ipv4), None)
            if first:
                add(Step("ip", "Local IP configuration", Status.PASS, f"{first.name}: {first.usable_ipv4[0][0]}/{first.usable_ipv4[0][1]} (no default gateway)"))
            else:
                add(Step("ip", "Local IP configuration", Status.FAIL, "No usable IPv4 address on the active adapters."))
        else:
            add(Step("ip", "Local IP configuration", Status.SKIPPED, "No active adapter.", "Skipped because no adapter is up."))

    gateway = primary.gateway_v4 if primary else ""
    if not stopped():
        if primary and gateway:
            add(Step("gateway", "Default gateway present", Status.PASS, gateway))
        elif primary is None and (not up or error):
            add(Step("gateway", "Default gateway present", Status.SKIPPED, "No usable connection.", "Skipped because there is no active configured adapter."))
        else:
            add(Step("gateway", "Default gateway present", Status.FAIL, "No IPv4 default route on a connected adapter."))

    if not stopped():
        if gateway:
            samples = []
            for i in range(3):
                samples.append(ping_service.ping_once(gateway, 1500, i + 1, cancel))
                if stopped():
                    break
            ok = [s for s in samples if s.success]
            if len(ok) == len(samples) and samples:
                avg = sum(s.rtt_ms or 0 for s in ok) / len(ok)
                add(Step("gateway_ping", "Gateway reachability (ping)", Status.PASS, f"{len(ok)}/{len(samples)} replies, avg {avg:.0f} ms"))
            elif ok:
                add(Step("gateway_ping", "Gateway reachability (ping)", Status.WARNING, f"{len(ok)}/{len(samples)} replies", "Some packets were lost - possible weak Wi-Fi or congestion."))
            else:
                add(Step("gateway_ping", "Gateway reachability (ping)", Status.FAIL, f"0/{len(samples)} replies", ping_service.ICMP_NOTE))
        else:
            add(Step("gateway_ping", "Gateway reachability (ping)", Status.SKIPPED, "No gateway to test."))

    if not stopped():
        host = settings.get("dns_test_host") or "www.microsoft.com"
        res = dns_service.lookup(host, "A", settings.get("dns_resolver", ""), timeout=4)
        status = Status.PASS if res.status == Status.PASS else (Status.FAIL if res.status == Status.FAIL else Status.WARNING)
        add(Step("dns", "DNS resolution", status, f"{host}: {res.summary}", advice=res.recommendation if status != Status.PASS else ""))

    if not stopped():
        r = tcp_check_service.check_port(*IP_PROBE, timeout=3)
        if r.outcome == "connected":
            add(Step("internet_ip", "External connection by IP (TCP 1.1.1.1:443)", Status.PASS, f"Connected in {r.ms:.0f} ms", external=True))
        else:
            add(Step("internet_ip", "External connection by IP (TCP 1.1.1.1:443)", Status.FAIL, f"{r.outcome}: {r.message}", "No answer from a public address - this separates 'no internet' from 'DNS problem'.", external=True))

    if not stopped():
        endpoints = settings.get("internet_endpoints") or []
        res = internet_check_service.run_internet_check(endpoints[:2], timeout=5)
        status = {Status.PASS: Status.PASS, Status.WARNING: Status.WARNING, Status.SKIPPED: Status.SKIPPED}.get(res.status, Status.FAIL)
        add(Step("https", "External HTTPS check", status, res.summary, external=True))

    if not stopped():
        if extra_target:
            address, err = ping_service.resolve_target(extra_target)
            if err:
                add(Step("target", f"Selected target: {extra_target}", Status.FAIL, err))
            else:
                s = ping_service.ping_once(address, 2000)
                if s.success:
                    add(Step("target", f"Selected target: {extra_target}", Status.PASS, f"Replied in {s.rtt_ms:g} ms"))
                else:
                    add(Step("target", f"Selected target: {extra_target}", Status.FAIL, "No ping reply", ping_service.ICMP_NOTE))
        else:
            add(Step("target", "Selected target", Status.SKIPPED, "No target entered.", "Optional - enter a target to include it."))

    result = CheckResult(tool="Quick Diagnosis", target=extra_target)
    result.duration_ms = (time.monotonic() - started) * 1000
    result.rows = [{"key": s.key, "step": s.title, "status": s.status.value, "evidence": s.evidence, "external": s.external} for s in steps]
    body = "\n\n".join(s.line() for s in steps)
    if cancel.is_set():
        result.cancelled, result.status = True, Status.UNKNOWN
        result.summary = f"Diagnosis cancelled after {len(steps)} step(s) - not a complete result."
        result.details = body
        return result

    findings = interpret({s.key: s.status for s in steps})
    worst = (
        Status.FAIL if any(f[0] == Status.FAIL for f in findings)
        else Status.WARNING if any(f[0] == Status.WARNING for f in findings)
        else Status.PASS
    )
    result.status = worst
    result.summary = findings[0][1] if len(findings) == 1 else f"{len(findings)} findings: " + findings[0][1]
    result.details = "CHECKS\n\n" + body + "\n\nFINDINGS (based on the evidence above, not certain proof)\n\n" + "\n".join(
        f"- [{lvl.value}] {msg}\n    Next step: {adv}" for lvl, msg, adv in findings
    )
    return result

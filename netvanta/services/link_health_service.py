"""Cable & Link Health: indirect evidence about a wired link.

A laptop cannot measure cable length or find a short/open (that needs a hardware tester, TDR).
What it can read is the negotiated speed/duplex, error counters, link-drop events and packet loss on
a burst of large pings. This module turns those into cautious findings, never a definite verdict.
"""

from __future__ import annotations

import re
import statistics
import threading
import time
from dataclasses import dataclass, field

from ..models.results import STATUS_ICON, CheckResult, Status
from ..utils.subprocess_runner import as_list, run_powershell_json
from . import adapter_service, ping_service

DISCLAIMER = (
    "Limits: NetVanta cannot measure cable length or detect a short/open circuit, and cannot see which switch port you are on. "
    "These are indirect signs; use a hardware cable tester for a definite answer."
)

_LINK_SCRIPT = r"""
$ad = @(Get-NetAdapter -Physical | ForEach-Object { @{ name=[string]$_.Name; desc=[string]$_.InterfaceDescription; status=[string]$_.Status; media=[string]$_.PhysicalMediaType; virtual=[bool]$_.Virtual; conn=[string]$_.MediaConnectionState; speed=[int64]$_.ReceiveLinkSpeed; duplex=[string]$_.FullDuplex } })
$sd = @(Get-NetAdapterAdvancedProperty -RegistryKeyword '*SpeedDuplex' | ForEach-Object { @{ name=[string]$_.Name; value=[string]$_.DisplayValue; valid=@($_.ValidDisplayValues) } })
@{adapters=$ad; speedduplex=$sd} | ConvertTo-Json -Depth 5 -Compress
"""

_STATS_SCRIPT = r"""
@(Get-NetAdapterStatistics | ForEach-Object { @{ name=[string]$_.Name; rx=[int64]$_.ReceivedUnicastPackets; tx=[int64]$_.SentUnicastPackets; rxerr=[int64]$_.ReceivedPacketErrors; txerr=[int64]$_.OutboundPacketErrors; rxdrop=[int64]$_.ReceivedDiscardedPackets; txdrop=[int64]$_.OutboundDiscardedPackets } }) | ConvertTo-Json -Compress
"""

_EVENT_SCRIPT = r"""
$start = (Get-Date).AddHours(-24)
@(Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=$start} -MaxEvents 4000 -ErrorAction SilentlyContinue |
  Where-Object { ($_.Message -match 'network link is disconnected|link (is )?(down|disconnected)|media disconnect|cable') -and ($_.ProviderName -match 'e1|Rt|b57|NDIS|Netwtw|ndis|Tcpip|Intel|Realtek|Broadcom|Marvell') -or ($_.ProviderName -eq 'Microsoft-Windows-NDIS' -and $_.Id -in 10400,10401) } |
  ForEach-Object { @{ time=$_.TimeCreated.ToString('s'); provider=[string]$_.ProviderName; id=[int]$_.Id; msg=($_.Message -split "`n")[0] } }) | ConvertTo-Json -Compress
"""


@dataclass
class LinkInfo:
    name: str
    description: str = ""
    status: str = ""
    connected: bool = False
    speed_mbps: float | None = None
    full_duplex: bool | None = None
    max_mbps: float | None = None
    setting: str = ""  # speed & duplex setting, e.g. "Auto Negotiation"


@dataclass
class Counters:
    rx: int = 0
    tx: int = 0
    errors: int = 0
    drops: int = 0


@dataclass
class Burst:
    sent: int = 0
    received: int = 0
    avg_ms: float | None = None
    jitter_ms: float | None = None
    max_ms: float | None = None

    @property
    def loss_pct(self) -> float:
        return round((self.sent - self.received) / self.sent * 100, 1) if self.sent else 0.0


@dataclass
class LinkReport:
    link: LinkInfo
    errors: Counters = field(default_factory=Counters)
    flaps: int | None = None  # None = could not read the event log
    burst: Burst | None = None


def _max_from_values(valid: list[str], description: str) -> float | None:
    best = 0.0
    for value in valid:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(Gbps|Mbps)", value, re.I)
        if match:
            speed = float(match.group(1)) * (1000 if match.group(2).lower() == "gbps" else 1)
            best = max(best, speed)
    if best:
        return best
    if re.search(r"gigabit|gbe|1000base|2\.5g", description, re.I):
        return 1000.0
    return None


def parse_links(data) -> list[LinkInfo]:
    if not isinstance(data, dict):
        return []
    settings = {s.get("name"): s for s in as_list(data.get("speedduplex")) if isinstance(s, dict)}
    links = []
    for raw in as_list(data.get("adapters")):
        if not isinstance(raw, dict):
            continue
        kind = adapter_service.classify(raw.get("name", ""), raw.get("desc", ""), str(raw.get("media", "")), bool(raw.get("virtual")))
        if kind != "Ethernet":
            continue  # real wired adapters only: no Wi-Fi, VPN, VMware/Hyper-V virtual adapters
        setting = settings.get(raw.get("name"), {})
        speed = raw.get("speed") or 0
        duplex = str(raw.get("duplex", "")).lower()
        links.append(LinkInfo(
            name=raw.get("name", ""),
            description=raw.get("desc", ""),
            status=raw.get("status", ""),
            connected=str(raw.get("conn", "")).lower() == "connected" and str(raw.get("status", "")).lower() == "up",
            speed_mbps=speed / 1_000_000 if speed else None,
            full_duplex=True if duplex == "true" else False if duplex == "false" else None,
            max_mbps=_max_from_values(as_list(setting.get("valid")), raw.get("desc", "")),
            setting=setting.get("value", ""),
        ))
    return links


def parse_counters(data) -> dict[str, Counters]:
    out = {}
    for item in as_list(data):
        if isinstance(item, dict):
            out[item.get("name", "")] = Counters(
                rx=int(item.get("rx") or 0), tx=int(item.get("tx") or 0),
                errors=int(item.get("rxerr") or 0) + int(item.get("txerr") or 0),
                drops=int(item.get("rxdrop") or 0) + int(item.get("txdrop") or 0))
    return out


def burst_ping(address: str, count: int = 60, size: int = 1400, timeout_ms: int = 1000,
               cancel: threading.Event | None = None) -> Burst:
    rtts: list[float] = []
    sent = 0
    for i in range(count):
        if cancel is not None and cancel.is_set():
            break
        sample = ping_service.ping_once(address, timeout_ms, i + 1, cancel, size=size)
        if sample.message == "Cancelled":
            break
        sent += 1
        if sample.success and sample.rtt_ms is not None:
            rtts.append(sample.rtt_ms)
    return Burst(
        sent=sent, received=len(rtts),
        avg_ms=round(statistics.fmean(rtts), 2) if rtts else None,
        jitter_ms=round(statistics.pstdev(rtts), 2) if len(rtts) > 1 else (0.0 if rtts else None),
        max_ms=max(rtts) if rtts else None)


def assess(report: LinkReport) -> list[tuple[Status, str, str]]:
    """Pure rules: LinkReport -> [(level, finding, advice)]. Wording stays cautious on purpose."""
    link, out = report.link, []
    P, F, W = Status.PASS, Status.FAIL, Status.WARNING
    if not link.connected:
        out.append((F, f"{link.name}: no link. Possible unplugged or damaged cable, a switch port that is off or faulty, or a powered-off device on the other end.",
                    "Reseat both ends, try another cable and another switch port."))
        return out
    if link.speed_mbps and link.max_mbps and link.speed_mbps < link.max_mbps and "auto" in (link.setting or "auto").lower():
        out.append((W, f"Linked at {link.speed_mbps:g} Mbps although the adapter supports {link.max_mbps:g} Mbps. Possible damaged/poorly terminated cable "
                       "(Gigabit needs all 4 pairs), a very long run, or a switch port limited to the lower speed.",
                    "Try a known-good short cable and a different port; if it then links faster, replace the original cable."))
    elif link.setting and "auto" not in link.setting.lower():
        out.append((W, f"The adapter is forced to '{link.setting}' instead of Auto Negotiation, which can cause duplex mismatch.",
                    "Set Speed & Duplex to Auto Negotiation unless the switch port is forced too."))
    if link.full_duplex is False:
        out.append((W, "The link is running half duplex - possible duplex mismatch or a bad cable.", "Use Auto Negotiation on both ends; try another cable."))
    if report.errors.errors > 0:
        out.append((W, f"{report.errors.errors} packet error(s) were counted during the test (CRC/framing errors are typical of a bad cable or connector).",
                    "Replace the patch cable and check the wall/patch-panel termination."))
    elif report.errors.drops > 20:
        out.append((W, f"{report.errors.drops} packets were discarded during the test - possible congestion or a failing link.", "Repeat the test; try another cable."))
    if report.flaps is not None and report.flaps >= 3:
        out.append((W, f"The link dropped and reconnected about {report.flaps} time(s) in the last 24 hours (best-effort event-log reading). Possible loose connector or failing cable/port.",
                    "Wiggle-test the connector, replace the cable, try another port."))
    b = report.burst
    if b and b.sent:
        if b.received == 0:
            out.append((F, "The gateway did not answer any of the large test packets (it may filter ICMP, or the link is not passing traffic).",
                        "Check the internet/gateway tests; try another cable."))
        elif b.loss_pct >= 2:
            out.append((W, f"{b.loss_pct:g}% packet loss on a local-network burst of {b.sent} large packets - a healthy wired LAN normally shows none. Possible bad cable or port.",
                        "Swap the cable and port and repeat the test to see if the loss follows the cable."))
        elif b.jitter_ms is not None and b.avg_ms is not None and b.jitter_ms > max(5.0, b.avg_ms * 2):
            out.append((W, f"Latency is unstable on the local link (average {b.avg_ms:g} ms, jitter {b.jitter_ms:g} ms).", "Repeat the test; check for a busy switch or a failing cable."))
    if not out:
        out.append((P, "No sign of a cable or link problem was found in these indirect checks.", "If a problem remains, test the next layers (addressing, DNS, internet) with Full Analysis."))
    return out


def run_link_health(cancel: threading.Event | None = None, on_line=None, burst_count: int = 60) -> CheckResult:
    started = time.monotonic()
    cancel = cancel or threading.Event()

    def say(text: str) -> None:
        if on_line:
            on_line(text)

    result = CheckResult(tool="Cable & Link Health")
    say("Reading adapter link information ...")
    data, res = run_powershell_json(_LINK_SCRIPT, 30, cancel)
    links = parse_links(data)
    if data is None or not links:
        result.status = Status.SKIPPED if data is not None else Status.FAIL
        result.summary = "No wired (Ethernet) adapter was found." if data is not None else "Could not read adapter link information."
        result.error = "" if data is not None else (res.error or "Windows did not return data.")
        result.recommendation = "Connect an Ethernet cable and try again." if data is not None else "Check that Windows PowerShell is available."
        result.details = DISCLAIMER
        result.duration_ms = (time.monotonic() - started) * 1000
        return result

    if any(link.connected for link in links):
        links = [link for link in links if link.connected]  # an unplugged spare port must not mask the one in use
    before_data, _ = run_powershell_json(_STATS_SCRIPT, 20, cancel)
    before = parse_counters(before_data)
    adapters, _err = adapter_service.get_adapters(cancel)
    by_name = {a.name: a for a in adapters}
    flap_data, flap_res = run_powershell_json(_EVENT_SCRIPT, 30, cancel)
    if flap_data is not None:
        flaps = len(as_list(flap_data))
    elif flap_res.ok:  # PowerShell printed nothing: no matching events
        flaps = 0
    else:
        flaps = None

    reports: list[LinkReport] = []
    for link in links:
        report = LinkReport(link, flaps=flaps)
        adapter = by_name.get(link.name)
        gateway = adapter.gateway_v4 if adapter else ""
        if link.connected and gateway and not cancel.is_set():
            say(f"{link.name}: sending {burst_count} large test packets to the gateway {gateway} ...")
            report.burst = burst_ping(gateway, burst_count, cancel=cancel)
        reports.append(report)

    after_data, _ = run_powershell_json(_STATS_SCRIPT, 20, cancel)
    after = parse_counters(after_data)
    for report in reports:
        a, b = after.get(report.link.name), before.get(report.link.name)
        if a and b:
            report.errors = Counters(a.rx - b.rx, a.tx - b.tx, max(0, a.errors - b.errors), max(0, a.drops - b.drops))

    result.duration_ms = (time.monotonic() - started) * 1000
    if cancel.is_set():
        result.cancelled, result.status = True, Status.UNKNOWN
        result.summary = "Stopped by user - partial result, not a complete test."
        return result

    blocks, simple_blocks, worst, rows = [], [], Status.PASS, []
    for report in reports:
        findings = assess(report)
        level = (Status.FAIL if any(f[0] == Status.FAIL for f in findings)
                 else Status.WARNING if any(f[0] == Status.WARNING for f in findings) else Status.PASS)
        if level == Status.FAIL or (level == Status.WARNING and worst == Status.PASS):
            worst = level
        link = report.link
        speed = f"{link.speed_mbps:g} Mbps" if link.speed_mbps else "n/a"
        lines = [f"{link.name}  ({link.description})",
                 f"  Link        : {'connected' if link.connected else 'NOT connected'}, {speed}"
                 + (f" (adapter supports up to {link.max_mbps:g} Mbps)" if link.max_mbps else ""),
                 f"  Duplex      : {'full' if link.full_duplex else 'half' if link.full_duplex is False else 'n/a'}   Setting: {link.setting or 'n/a'}",
                 f"  Errors      : {report.errors.errors} packet errors, {report.errors.drops} discards during the test",
                 f"  Link drops  : {report.flaps if report.flaps is not None else 'could not read'} in the last 24 h (best effort)"]
        if report.burst and report.burst.sent:
            b = report.burst
            lines.append(f"  Burst ping  : {b.received}/{b.sent} replies ({b.loss_pct:g}% loss), avg {b.avg_ms if b.avg_ms is not None else 'n/a'} ms, "
                         f"jitter {b.jitter_ms if b.jitter_ms is not None else 'n/a'} ms")
        else:
            lines.append("  Burst ping  : skipped (no link or no gateway)")
        lines.append("  Findings:")
        lines += [f"   - [{lvl.value}] {msg}\n       Next step: {adv}" for lvl, msg, adv in findings]
        blocks.append("\n".join(lines))
        facts = f"{'connected' if link.connected else 'not connected'}" + (f", {link.speed_mbps:g} Mbps" if link.speed_mbps else "")
        if report.burst and report.burst.sent:
            facts += f", {report.burst.loss_pct:g}% packet loss on the test"
        simple_blocks.append(f"  {STATUS_ICON[level]}  {link.name}: {facts}\n" + "\n".join(f"       - {msg}\n         What to do: {adv}" for _l, msg, adv in findings))
        rows.append({"adapter": link.name, "connected": link.connected, "speed_mbps": link.speed_mbps or "", "max_mbps": link.max_mbps or "",
                     "errors": report.errors.errors, "flaps_24h": report.flaps if report.flaps is not None else "",
                     "burst_loss_pct": report.burst.loss_pct if report.burst and report.burst.sent else "", "level": level.value})
    result.status = worst
    result.rows = rows
    result.details = "\n\n".join(blocks) + "\n\n" + DISCLAIMER
    result.simple = ("CABLE AND LINK RESULT\n\n" + "\n\n".join(simple_blocks)
                     + "\n\n(A laptop cannot measure cable length or find a short circuit - these are hints, not proof. "
                     "Press 'Show details' for speed, errors and test numbers.)")
    severity = {Status.FAIL: 0, Status.WARNING: 1, Status.PASS: 2}
    findings_all = [f for r in reports for f in assess(r)]
    worst_finding = min(findings_all, key=lambda f: severity.get(f[0], 3))
    result.summary = worst_finding[1] if len(reports) == 1 else f"{len(reports)} wired adapters checked. " + worst_finding[1]
    return result


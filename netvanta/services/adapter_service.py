"""Single source of truth for network adapter information (read-only)."""

from __future__ import annotations

import ipaddress
import re
import threading
from dataclasses import dataclass, field

from ..utils.subprocess_runner import as_list, run_powershell_json

_SCRIPT = r"""
$ad = @(Get-NetAdapter | ForEach-Object { @{ name=[string]$_.Name; description=[string]$_.InterfaceDescription; index=[int]$_.ifIndex; status=[string]$_.Status; mac=[string]$_.MacAddress; speed=[string]$_.LinkSpeed; media=[string]$_.PhysicalMediaType; virtual=[bool]$_.Virtual } })
$ip = @(Get-NetIPAddress | ForEach-Object { @{ index=[int]$_.InterfaceIndex; address=[string]$_.IPAddress; prefix=[int]$_.PrefixLength; family=[string]$_.AddressFamily } })
$gw = @(Get-NetRoute -DestinationPrefix '0.0.0.0/0','::/0' | ForEach-Object { @{ index=[int]$_.InterfaceIndex; nexthop=[string]$_.NextHop; metric=[int]$_.RouteMetric; ifmetric=[int]$_.InterfaceMetric } })
$dns = @(Get-DnsClientServerAddress | ForEach-Object { @{ index=[int]$_.InterfaceIndex; family=[string]$_.AddressFamily; servers=@($_.ServerAddresses) } })
$st = @(Get-NetAdapterStatistics | ForEach-Object { @{ name=[string]$_.Name; rx=[int64]$_.ReceivedBytes; tx=[int64]$_.SentBytes } })
@{adapters=$ad; ips=$ip; gateways=$gw; dns=$dns; stats=$st} | ConvertTo-Json -Depth 6 -Compress
"""

_VPN = re.compile(r"vpn|tap-windows|tun\b|wireguard|openvpn|anyconnect|nordlynx|tailscale|zerotier|wan miniport|ppp", re.I)
_VIRTUAL = re.compile(r"hyper-v|vmware|virtualbox|vethernet|loopback|virtual|vbox|docker|wsl|npcap", re.I)


@dataclass
class AdapterInfo:
    name: str
    description: str = ""
    index: int = 0
    status: str = "Unknown"
    mac: str = ""
    speed: str = ""
    kind: str = "Other"  # Wi-Fi | Ethernet | VPN | Virtual | Bluetooth | Other
    ipv4: list[tuple[str, int]] = field(default_factory=list)
    ipv6: list[tuple[str, int]] = field(default_factory=list)
    gateways: list[str] = field(default_factory=list)
    dns: list[str] = field(default_factory=list)
    metric: int = 9999
    rx_bytes: int | None = None
    tx_bytes: int | None = None

    @property
    def is_up(self) -> bool:
        return self.status.lower() == "up"

    @property
    def usable_ipv4(self) -> list[tuple[str, int]]:
        return [(a, p) for a, p in self.ipv4 if not a.startswith("169.254.") and not a.startswith("127.")]

    @property
    def has_link_local_only(self) -> bool:
        return bool(self.ipv4) and not self.usable_ipv4

    @property
    def gateway_v4(self) -> str:
        for gw in self.gateways:
            try:
                if isinstance(ipaddress.ip_address(gw), ipaddress.IPv4Address) and gw != "0.0.0.0":
                    return gw
            except ValueError:
                continue
        return ""


def classify(name: str, description: str, media: str, virtual: bool) -> str:
    blob = f"{name} {description}"
    if "802.11" in media or re.search(r"wi-?fi|wireless|wlan", blob, re.I):
        return "Wi-Fi"
    if _VPN.search(blob):
        return "VPN"
    if virtual or _VIRTUAL.search(blob):
        return "Virtual"
    if "bluetooth" in blob.lower():
        return "Bluetooth"
    if "802.3" in media or re.search(r"ethernet|gigabit|realtek|intel.*(lan|pci)", blob, re.I):
        return "Ethernet"
    return "Other"


def format_mac(mac: str) -> str:
    return mac.replace("-", ":").upper() if mac else ""


def parse_adapters(data: dict) -> list[AdapterInfo]:
    """Turn the PowerShell JSON document into AdapterInfo objects."""
    if not isinstance(data, dict):
        return []
    ips = as_list(data.get("ips"))
    gws = as_list(data.get("gateways"))
    dnss = as_list(data.get("dns"))
    stats = {s.get("name"): s for s in as_list(data.get("stats")) if isinstance(s, dict)}
    adapters: list[AdapterInfo] = []
    for raw in as_list(data.get("adapters")):
        if not isinstance(raw, dict):
            continue
        idx = int(raw.get("index") or 0)
        info = AdapterInfo(
            name=raw.get("name") or f"Interface {idx}",
            description=raw.get("description") or "",
            index=idx,
            status=raw.get("status") or "Unknown",
            mac=format_mac(raw.get("mac") or ""),
            speed=raw.get("speed") or "",
            kind=classify(raw.get("name") or "", raw.get("description") or "", raw.get("media") or "", bool(raw.get("virtual"))),
        )
        for entry in ips:
            if entry.get("index") != idx:
                continue
            addr, prefix = entry.get("address", ""), int(entry.get("prefix") or 0)
            if "IPv4" in str(entry.get("family")):
                info.ipv4.append((addr, prefix))
            else:
                info.ipv6.append((addr.split("%")[0], prefix))
        best = None
        for entry in gws:
            if entry.get("index") != idx:
                continue
            info.gateways.append(entry.get("nexthop", ""))
            total = int(entry.get("metric") or 0) + int(entry.get("ifmetric") or 0)
            best = total if best is None else min(best, total)
        if best is not None:
            info.metric = best
        for entry in dnss:
            if entry.get("index") == idx:
                for server in as_list(entry.get("servers")):
                    if server and server not in info.dns:
                        info.dns.append(server)
        stat = stats.get(info.name)
        if stat:
            info.rx_bytes, info.tx_bytes = stat.get("rx"), stat.get("tx")
        adapters.append(info)
    return adapters


def pick_primary(adapters: list[AdapterInfo]) -> AdapterInfo | None:
    """The adapter most likely carrying internet traffic (never assume the first)."""
    candidates = [a for a in adapters if a.is_up and a.usable_ipv4 and a.gateway_v4]
    if not candidates:
        return None
    penalty = {"VPN": 1, "Virtual": 2}
    return min(candidates, key=lambda a: (penalty.get(a.kind, 0), a.metric))


def get_adapters(cancel: threading.Event | None = None) -> tuple[list[AdapterInfo], str]:
    """Return (adapters, error message). Error is empty on success."""
    data, res = run_powershell_json(_SCRIPT, timeout=30, cancel=cancel)
    if res.error:
        return [], res.error
    if res.cancelled:
        return [], "Cancelled."
    if res.timed_out:
        return [], "Reading adapter information timed out."
    if data is None:
        return [], "Windows did not return adapter information (PowerShell networking cmdlets unavailable?)."
    return parse_adapters(data), ""


def format_adapter(a: AdapterInfo) -> str:
    def addrs(items: list[tuple[str, int]]) -> str:
        return ", ".join(f"{ip}/{pfx}" for ip, pfx in items) or "None"

    mask = ""
    if a.ipv4:
        try:
            mask = str(ipaddress.IPv4Network(f"0.0.0.0/{a.ipv4[0][1]}").netmask)
        except ValueError:
            mask = ""
    lines = [
        f"{a.name}  [{a.kind}]  - {a.status}",
        f"  Description : {a.description or 'Not provided'}",
        f"  MAC address : {a.mac or 'Not provided'}",
        f"  Link speed  : {a.speed or 'Not provided'}",
        f"  IPv4        : {addrs(a.ipv4)}" + (f"  (mask {mask})" if mask else ""),
        f"  IPv6        : {addrs(a.ipv6)}",
        f"  Gateway     : {', '.join(g for g in a.gateways if g and g != '0.0.0.0') or 'None'}",
        f"  DNS servers : {', '.join(a.dns) or 'None'}",
    ]
    if a.rx_bytes is not None:
        lines.append(f"  Traffic     : received {a.rx_bytes:,} bytes, sent {a.tx_bytes:,} bytes")
    if a.has_link_local_only:
        lines.append("  Note        : only a link-local (169.254.x.x) address - DHCP may have failed.")
    return "\n".join(lines)


def adapter_row(a: AdapterInfo) -> dict:
    return {
        "adapter": a.name,
        "type": a.kind,
        "status": a.status,
        "ipv4": "; ".join(f"{ip}/{p}" for ip, p in a.ipv4),
        "ipv6": "; ".join(f"{ip}/{p}" for ip, p in a.ipv6),
        "mac": a.mac,
        "gateway": "; ".join(g for g in a.gateways if g and g != "0.0.0.0"),
        "dns": "; ".join(a.dns),
        "rx_bytes": a.rx_bytes if a.rx_bytes is not None else "",
        "tx_bytes": a.tx_bytes if a.tx_bytes is not None else "",
    }

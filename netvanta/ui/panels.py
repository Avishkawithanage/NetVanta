"""The individual troubleshooting tools. Each one is a thin shell over a service."""

from __future__ import annotations


import customtkinter as ctk

from ..defaults import MAX_TRACE_HOPS
from ..models.results import STATUS_ICON, CheckResult, Status
from ..services import (full_analysis_service, link_health_service, adapter_service, arp_service, dns_cache_service, dns_service, internet_check_service,
                        ip_config, route_service, tcp_check_service, traceroute_service)
from ..services.diagnosis_service import run_quick_diagnosis
from ..utils.validation import (parse_ports, validate_host, validate_number, validate_resolver,
                                validate_url)
from . import theme
from .ping_panel import PingPanel
from .widgets.tool_panel import ToolPanel


class IPConfigPanel(ToolPanel):
    name = "IP Configuration"
    description = "Shows your main connection first (IP, mask, gateway, DNS), then a short list of the other adapters. Read-only."
    run_label = "Check IP Configuration"
    save_history = True

    def build_inputs(self, parent):
        ctk.CTkLabel(parent, text="Press the button to read your current network settings. Use 'Show details' afterwards for every adapter and IPv6.",
                     text_color=theme.MUTED, font=theme.font(12)).pack(padx=16, pady=14, anchor="w")

    def work(self, params, cancel, emit):
        return ip_config.check_ip_configuration(cancel)


class QuickDiagnosisPanel(ToolPanel):
    name = "Quick Diagnosis"
    description = ("Runs a sequence of real checks (adapter, IP, gateway, DNS, internet) and explains what the evidence "
                   "suggests. Steps marked 'external' contact the internet.")
    run_label = "Run Quick Diagnosis"
    streaming = True
    wrap_output = True
    replace_on_done = True

    def build_inputs(self, parent):
        self.target = self.field(parent, "Optional target to include", "", 300, 0, placeholder="e.g. a server or website")

    def read_params(self):
        text = self.target.get().strip()
        return validate_host(text) if text else ""

    def work(self, params, cancel, emit):
        emit("Checking your connection - this usually takes 10 to 25 seconds ...\n")
        return run_quick_diagnosis(self.ctx.settings.values, params, cancel,
                                   on_step=lambda step: emit(f"  {STATUS_ICON[step.status]}  {step.title}"))


class DNSPanel(ToolPanel):
    name = "DNS Lookup"
    description = "Query DNS records. Leave the resolver empty to use the system default."
    run_label = "Look Up"

    def build_inputs(self, parent):
        self.host = self.field(parent, "Domain name", "", 260, 0, placeholder="e.g. example.com")
        ctk.CTkLabel(parent, text="Record type", font=theme.font(12), text_color=theme.MUTED).grid(
            row=0, column=1, sticky="w", padx=(16, 6), pady=(10, 0))
        self.rtype = ctk.CTkComboBox(parent, values=list(dns_service.RECORD_TYPES), width=100, height=34, state="readonly")
        self.rtype.set("A")
        self.rtype.grid(row=1, column=1, sticky="w", padx=(16, 6), pady=(2, 12))
        self.resolver = self.field(parent, "DNS server (optional)", self.ctx.settings.get("dns_resolver"), 180, 2,
                                   placeholder="system default")

    def read_params(self):
        return validate_host(self.host.get()), self.rtype.get(), validate_resolver(self.resolver.get())

    def work(self, params, cancel, emit):
        return dns_service.lookup(params[0], params[1], params[2])


class TraceroutePanel(ToolPanel):
    name = "Traceroute"
    description = "Shows the routers between this PC and a target. Missing hops (*) are common and not always a fault."
    run_label = "Start Trace"
    streaming = True

    def build_inputs(self, parent):
        self.target = self.field(parent, "Hostname or IP address", "", 260, 0, placeholder="e.g. 8.8.8.8")
        self.hops = self.field(parent, "Max hops", 20, 80, 1)
        self.timeout = self.field(parent, "Per-hop timeout (ms)", 1500, 120, 2)
        self.names = ctk.CTkCheckBox(parent, text="Resolve host names (slower)")
        self.names.grid(row=1, column=3, padx=16, pady=(2, 12), sticky="w")

    def read_params(self):
        hops = validate_number(self.hops.get(), "Max hops", 1, MAX_TRACE_HOPS)
        timeout = validate_number(self.timeout.get(), "Timeout", 200, 10000)
        return validate_host(self.target.get()), hops, timeout, bool(self.names.get())

    def work(self, params, cancel, emit):
        target, hops, timeout, names = params
        emit(f"Tracing route to {target} ...")
        return traceroute_service.run_traceroute(target, hops, timeout, names, cancel, on_line=emit)

    def footer(self, result):
        return "\n\n".join(p for p in (result.summary, result.recommendation) if p)


class ARPPanel(ToolPanel):
    name = "ARP Table"
    description = "Devices this PC has recently talked to on the local network (IP and MAC address)."
    run_label = "Read ARP Table"
    filterable = True
    save_history = False
    has_stop = False

    def work(self, params, cancel, emit):
        return arp_service.read_arp_table()


class RoutePanel(ToolPanel):
    name = "Routing Table"
    description = "How this PC decides where to send traffic. Read-only: NetVanta never changes routes."
    run_label = "Read Routing Table"
    filterable = True
    save_history = False

    def work(self, params, cancel, emit):
        return route_service.read_routes(cancel)


class DNSCachePanel(ToolPanel):
    name = "DNS Cache"
    description = "Names Windows has recently resolved. Read-only: NetVanta never flushes the cache."
    run_label = "Read DNS Cache"
    filterable = True
    save_history = False

    def work(self, params, cancel, emit):
        return dns_cache_service.read_dns_cache(cancel)

    def render_body(self, result, filter_text):
        if not result.rows:
            return result.render()
        rows = dns_cache_service.filter_rows(result.rows, filter_text)
        return result.summary + f"  (showing {len(rows)})\n\n" + dns_cache_service.format_rows(rows) + (
            f"\n\nNote: {result.recommendation}" if result.recommendation else "")


class TCPPanel(ToolPanel):
    name = "TCP Port Test"
    description = ("Checks whether a TCP port accepts connections. Only test systems you own or are authorised to test. "
                   "A timeout does not prove a port is closed.")
    run_label = "Test Ports"

    def build_inputs(self, parent):
        self.host = self.field(parent, "Hostname or IP address", "", 260, 0, placeholder="e.g. 192.168.1.10")
        self.ports = self.field(parent, "Port(s)", "443", 200, 1, placeholder="80, 443 or 8000-8005")
        self.timeout = self.field(parent, "Timeout (s)", 3, 80, 2)

    def read_params(self):
        return (validate_host(self.host.get()), parse_ports(self.ports.get()),
                validate_number(self.timeout.get(), "Timeout", 1, 30, integer=False))

    def work(self, params, cancel, emit):
        return tcp_check_service.run_port_check(params[0], params[1], params[2], cancel)


class AdapterPanel(ToolPanel):
    name = "Adapter Information"
    description = "Compact overview of interfaces: type, status, speed and traffic counters. Uses the same data as IP Configuration."
    run_label = "Refresh Adapters"
    filterable = True
    save_history = False
    has_stop = False

    def work(self, params, cancel, emit):
        adapters, error = adapter_service.get_adapters(cancel)
        result = CheckResult(tool="Adapter Information")
        if error:
            result.status, result.summary, result.error = Status.FAIL, "Could not read adapters.", error
            return result
        result.status = Status.PASS if adapters else Status.WARNING
        result.summary = f"{len(adapters)} interface(s); {sum(a.is_up for a in adapters)} up."
        result.rows = [adapter_service.adapter_row(a) for a in adapters]
        result.details = f"{'Adapter':<28}{'Type':<11}{'Status':<14}{'Speed':<12}{'MAC':<19}{'Received':>16}{'Sent':>16}\n" + "\n".join(
            f"{a.name[:26]:<28}{a.kind:<11}{a.status:<14}{(a.speed or 'n/a')[:11]:<12}{(a.mac or 'n/a'):<19}"
            f"{(format(a.rx_bytes, ',') if a.rx_bytes is not None else 'n/a'):>16}"
            f"{(format(a.tx_bytes, ',') if a.tx_bytes is not None else 'n/a'):>16}"
            for a in adapters)
        result.recommendation = "'n/a' means Windows did not provide that field."
        return result


class InternetPanel(ToolPanel):
    name = "Internet Check"
    description = "Tests HTTPS connectivity to several endpoints. This contacts the internet. Separate from ping."
    run_label = "Check Internet"

    def build_inputs(self, parent):
        self.extra = self.field(parent, "Extra HTTPS endpoint (optional)", "", 380, 0, placeholder="https://example.com")

    def read_params(self):
        endpoints = list(self.ctx.settings.get("internet_endpoints"))
        text = self.extra.get().strip()
        if text:
            endpoints.append(validate_url(text))
        return endpoints

    def work(self, params, cancel, emit):
        return internet_check_service.run_internet_check(params)


class PublicIPPanel(ToolPanel):
    name = "Public IP"
    description = "Asks an external service which public address your connection uses. Only runs when you press the button."
    run_label = "Look Up Public IP"
    has_stop = False

    def build_inputs(self, parent):
        endpoint = self.ctx.settings.get("public_ip_endpoint")
        ctk.CTkLabel(parent, text=f"Privacy: pressing the button sends a request to {endpoint}. Nothing is stored except in your local history.",
                     font=theme.font(12), text_color=theme.MUTED, wraplength=900, justify="left").pack(padx=16, pady=14, anchor="w")

    def work(self, params, cancel, emit):
        return internet_check_service.get_public_ip(self.ctx.settings.get("public_ip_endpoint"))


class LinkHealthPanel(ToolPanel):
    name = "Cable & Link Health"
    description = ("Checks a wired connection for signs of a bad cable or port: negotiated speed and duplex, error counters, link drops "
                   "and loss on a burst of large pings to the gateway. It cannot measure cable length or find a short/open - use a hardware tester for that.")
    run_label = "Check Cable & Link"
    streaming = True
    wrap_output = True
    replace_on_done = True

    def work(self, params, cancel, emit):
        return link_health_service.run_link_health(cancel, on_line=emit)


class FullAnalysisPanel(ToolPanel):
    name = "Full Analysis"
    description = ("Runs the cable/link check and the connectivity checks together (about 30 seconds) and tells you which layer - cable, addressing, "
                   "local network, DNS, internet or the target - is the most likely problem area. Contains external steps.")
    run_label = "Run Full Analysis"
    streaming = True
    wrap_output = True
    replace_on_done = True

    def build_inputs(self, parent):
        self.target = self.field(parent, "Optional target to include", "", 300, 0, placeholder="e.g. a server or website")

    def read_params(self):
        text = self.target.get().strip()
        return validate_host(text) if text else ""

    def work(self, params, cancel, emit):
        return full_analysis_service.run_full_analysis(self.ctx.settings.values, params, cancel, emit)


PANELS: list[tuple[str, type[ToolPanel]]] = [
    ("IP Configuration", IPConfigPanel),
    ("Ping", PingPanel),
    ("Full Analysis", FullAnalysisPanel),
    ("Quick Diagnosis", QuickDiagnosisPanel),
    ("Cable & Link Health", LinkHealthPanel),
    ("DNS Lookup", DNSPanel),
    ("Traceroute", TraceroutePanel),
    ("TCP Port Test", TCPPanel),
    ("Internet Check", InternetPanel),
    ("Public IP", PublicIPPanel),
    ("ARP Table", ARPPanel),
    ("Routing Table", RoutePanel),
    ("DNS Cache", DNSCachePanel),
    ("Adapter Information", AdapterPanel),
]

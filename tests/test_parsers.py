import socket
import ssl
import sys
import threading
import urllib.error
from unittest import mock

from netvanta.models.results import Status
from netvanta.services import (adapter_service, arp_service, dns_cache_service, route_service)
from netvanta.services import internet_check_service as ics
from netvanta.services import traceroute_service as tr
from netvanta.utils.subprocess_runner import CommandResult, as_list, run_command, stream_command

ARP = """
Interface: 192.168.1.5 --- 0x6
  Internet Address      Physical Address      Type
  192.168.1.1           aa-bb-cc-dd-ee-ff     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     static

Interface: 10.0.0.2 --- 0x9
  10.0.0.1              00-11-22-33-44-55     dynamic
"""


def test_arp_parse():
    rows = arp_service.parse_arp(ARP)
    assert len(rows) == 3 and rows[0]["mac"] == "AA:BB:CC:DD:EE:FF" and rows[2]["interface"] == "10.0.0.2"


def test_arp_malformed_empty_and_missing_command():
    assert arp_service.parse_arp("garbage\n\n???") == []
    with mock.patch.object(arp_service, "run_command", return_value=CommandResult(["arp"], 0, "")):
        assert arp_service.read_arp_table().status == Status.WARNING
    with mock.patch.object(arp_service, "run_command", return_value=CommandResult(["arp"], error="Command not found")):
        assert arp_service.read_arp_table().status == Status.FAIL


def test_traceroute_hops():
    h = tr.parse_hop("  1    <1 ms    <1 ms    <1 ms  192.168.1.1")
    assert h.number == 1 and h.address == "192.168.1.1" and h.responded
    h = tr.parse_hop("  2     *        *        *     Request timed out.")
    assert h.number == 2 and not h.responded
    h = tr.parse_hop("  5    12 ms    13 ms    11 ms  dns.google [8.8.8.8]")
    assert h.address == "8.8.8.8" and h.host == "dns.google"
    assert tr.parse_hop("Tracing route to 8.8.8.8 over a maximum of 20 hops") is None
    assert tr.parse_hop("Trace complete.") is None


def _stream(lines, **kw):
    def fake(args, on_line, **k):
        for ln in lines:
            on_line(ln)
        return CommandResult(args, 0, "\n".join(lines), **kw)

    return fake


def test_traceroute_complete_partial_and_cancelled():
    lines = ["  1    <1 ms    <1 ms    <1 ms  192.168.1.1", "  2    10 ms    9 ms    11 ms  8.8.8.8"]
    with mock.patch.object(tr, "stream_command", _stream(lines)):
        assert tr.run_traceroute("8.8.8.8").status == Status.PASS
    with mock.patch.object(tr, "stream_command", _stream(lines[:1], timed_out=True)):
        r = tr.run_traceroute("8.8.8.8")
        assert r.status == Status.WARNING and "partial" in r.summary and len(r.rows) == 1
    with mock.patch.object(tr, "stream_command", _stream(lines[:1], cancelled=True)):
        assert tr.run_traceroute("8.8.8.8").cancelled


def test_adapter_parse_and_primary():
    data = {
        "adapters": [
            {"name": "Wi-Fi", "description": "Intel Wireless", "index": 5, "status": "Up", "mac": "AA-BB-CC-DD-EE-FF",
             "media": "Native 802.11", "virtual": False},
            {"name": "vEthernet", "description": "Hyper-V Virtual Ethernet", "index": 9, "status": "Up", "mac": "",
             "media": "", "virtual": True},
            {"name": "Ethernet", "description": "Realtek", "index": 2, "status": "Disconnected", "media": "802.3",
             "virtual": False},
        ],
        "ips": [
            {"index": 5, "address": "192.168.1.20", "prefix": 24, "family": "IPv4"},
            {"index": 5, "address": "fe80::1%5", "prefix": 64, "family": "IPv6"},
            {"index": 9, "address": "172.20.0.1", "prefix": 20, "family": "IPv4"},
            {"index": 2, "address": "169.254.3.4", "prefix": 16, "family": "IPv4"},
        ],
        "gateways": {"index": 5, "nexthop": "192.168.1.1", "metric": 0, "ifmetric": 25},
        "dns": [{"index": 5, "family": "IPv4", "servers": "192.168.1.1"}],
        "stats": [],
    }
    adapters = adapter_service.parse_adapters(data)
    kinds = {a.name: a.kind for a in adapters}
    assert kinds == {"Wi-Fi": "Wi-Fi", "vEthernet": "Virtual", "Ethernet": "Ethernet"}
    primary = adapter_service.pick_primary(adapters)
    assert primary.name == "Wi-Fi" and primary.dns == ["192.168.1.1"] and primary.gateway_v4 == "192.168.1.1"
    assert adapters[0].mac == "AA:BB:CC:DD:EE:FF" and adapters[0].ipv6[0][0] == "fe80::1"
    assert adapters[2].has_link_local_only and not adapters[2].usable_ipv4


def test_primary_none_when_no_gateway_and_bad_data():
    lonely = adapter_service.AdapterInfo("x", status="Up", ipv4=[("10.0.0.2", 24)])
    assert adapter_service.pick_primary([lonely]) is None
    assert adapter_service.parse_adapters(None) == [] and adapter_service.parse_adapters({}) == []


def test_routes_parse():
    rows = route_service.parse_routes([
        {"prefix": "0.0.0.0/0", "nexthop": "192.168.1.1", "alias": "Wi-Fi", "metric": 0, "ifmetric": 25},
        {"prefix": "192.168.1.0/24", "nexthop": "0.0.0.0", "alias": "Wi-Fi", "metric": 256, "ifmetric": 25},
        {"prefix": "::/0", "nexthop": "fe80::1", "alias": "Wi-Fi", "metric": 256, "ifmetric": 25},
    ])
    assert rows[0]["destination"] == "0.0.0.0/0" and rows[1]["netmask"] == "255.255.255.0" and rows[2]["family"] == "IPv6"
    assert route_service.parse_routes(None) == []


def test_dns_cache_parse_and_filter():
    rows = dns_cache_service.parse_cache({"name": "Example.com", "type": "1", "ttl": 20, "data": "1.2.3.4"})
    assert rows[0]["type"] == "A"
    assert dns_cache_service.filter_rows(rows, "EXAMPLE") == rows and dns_cache_service.filter_rows(rows, "zzz") == []
    assert dns_cache_service.filter_rows(rows, "") == rows


def test_dns_cache_restricted_gives_actionable_message():
    failure = (None, CommandResult([], error="PowerShell missing"))
    with mock.patch.object(dns_cache_service, "run_powershell_json", return_value=failure):
        r = dns_cache_service.read_dns_cache()
    assert r.status == Status.FAIL and r.recommendation


def test_internet_classification():
    assert ics.classify_error(urllib.error.URLError(socket.gaierror()))[0] == "dns"
    assert ics.classify_error(urllib.error.URLError(TimeoutError()))[0] == "timeout"
    assert ics.classify_error(urllib.error.URLError(ssl.SSLCertVerificationError()))[0] == "tls"
    assert ics.classify_error(urllib.error.URLError(ConnectionRefusedError()))[0] == "connect"


def test_internet_aggregation_never_declares_all_down_from_one_endpoint():
    ok = ics.EndpointResult("https://a", True, "ok", "HTTP 200", 10, 200)
    bad = ics.EndpointResult("https://b", False, "dns", "DNS resolution failed")
    with mock.patch.object(ics, "check_endpoint", side_effect=[ok, bad]):
        assert ics.run_internet_check(["https://a", "https://b"]).status == Status.WARNING
    with mock.patch.object(ics, "check_endpoint", side_effect=[bad, bad]):
        r = ics.run_internet_check(["https://b", "https://b"])
        assert r.status == Status.FAIL and "DNS" in r.summary
    assert ics.run_internet_check([]).status == Status.SKIPPED


class _Resp:
    def __init__(self, body):
        self.body = body

    def read(self, n):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_public_ip_validation():
    with mock.patch.object(ics.urllib.request, "urlopen", return_value=_Resp(b"203.0.113.9")):
        assert ics.get_public_ip().status == Status.PASS
    with mock.patch.object(ics.urllib.request, "urlopen", return_value=_Resp(b"<html>nope</html>")):
        assert ics.get_public_ip().status == Status.FAIL


def test_as_list():
    assert as_list(None) == [] and as_list({"a": 1}) == [{"a": 1}] and as_list([1]) == [1]


def test_subprocess_missing_command():
    assert "not found" in run_command(["definitely_not_a_command_xyz"]).error


def test_subprocess_timeout_and_cancel():
    slow = [sys.executable, "-c", "import time; time.sleep(30)"]
    r = run_command(slow, timeout=0.6)
    assert r.timed_out and not r.ok
    ev = threading.Event()
    threading.Timer(0.5, ev.set).start()
    assert run_command(slow, timeout=20, cancel=ev).cancelled


def test_stream_command_lines_and_cancel():
    got = []
    r = stream_command([sys.executable, "-u", "-c", "print('a');print('b')"], got.append, timeout=10, encoding="utf-8")
    assert got == ["a", "b"] and r.ok
    ev = threading.Event()
    threading.Timer(0.5, ev.set).start()
    r = stream_command([sys.executable, "-c", "import time; time.sleep(30)"], lambda line: None, timeout=20, cancel=ev)
    assert r.cancelled

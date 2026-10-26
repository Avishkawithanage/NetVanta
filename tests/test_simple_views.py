from unittest import mock

from netvanta.models.results import CheckResult, Status
from netvanta.services import adapter_service as ads
from netvanta.services import diagnosis_service as ds
from netvanta.services import ip_config


def _adapters():
    wifi = ads.AdapterInfo("Wi-Fi", "Intel", 5, "Up", "AA:BB:CC:DD:EE:FF", "300 Mbps", "Wi-Fi",
                           [("192.168.1.20", 24)], [("fe80::1", 64), ("2001:db8::5", 64)], ["192.168.1.1"], ["192.168.1.1"], 25)
    virt = ads.AdapterInfo("VMnet1", "VMware", 9, "Up", "", "100 Mbps", "Virtual", [("192.168.5.1", 24)])
    down = ads.AdapterInfo("Ethernet", "Realtek", 2, "Disconnected", "", "", "Ethernet", [("169.254.1.2", 16)])
    return [virt, down, wifi]


def test_ip_config_simple_shows_only_main_connection():
    with mock.patch.object(ip_config, "get_adapters", return_value=(_adapters(), "")):
        r = ip_config.check_ip_configuration()
    assert r.status == Status.PASS
    assert "192.168.1.20" in r.simple and "255.255.255.0" in r.simple and "Show details" in r.simple
    assert "VMnet1" not in r.simple and "fe80" not in r.simple
    assert "VMnet1" in r.details and "ALL OTHER ADAPTERS" in r.details and "FULL DETAILS" in r.details
    assert len(r.rows) == 3


def test_ip_config_no_connection_still_gives_simple_text():
    adapters = [a for a in _adapters() if a.name == "Ethernet"]
    with mock.patch.object(ip_config, "get_adapters", return_value=(adapters, "")):
        r = ip_config.check_ip_configuration()
    assert r.status == Status.FAIL and "NO WORKING CONNECTION" in r.simple and "What to do" in r.simple


def test_diagnosis_checklist_is_one_line_per_step():
    steps = [ds.Step("adapter", "Network adapter status", Status.PASS, "x"),
             ds.Step("https", "External HTTPS check", Status.FAIL, "y", external=True),
             ds.Step("target", "Selected target", Status.SKIPPED, "z")]
    lines = ds.checklist(steps).splitlines()
    assert len(lines) == 3
    assert "OK" in lines[0] and "Problem" in lines[1] and "(online)" in lines[1] and "Skipped" in lines[2]


def test_clipboard_uses_simple_view_when_present():
    r = CheckResult(tool="T", summary="sum", simple="friendly text", details="deep detail")
    text = r.clipboard_summary()
    assert "friendly text" in text and "deep detail" not in text
    plain = CheckResult(tool="T", summary="sum", details="deep detail").clipboard_summary()
    assert "deep detail" in plain

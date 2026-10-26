from unittest import mock

from netvanta.models.results import Status as S
from netvanta.services import full_analysis_service as fa
from netvanta.services import link_health_service as lh

DATA = {
    "adapters": [
        {"name": "Ethernet", "desc": "Realtek PCIe GbE Family Controller", "status": "Up", "media": "802.3",
         "conn": "Connected", "speed": 100_000_000, "duplex": "True"},
        {"name": "Wi-Fi", "desc": "Intel Wireless", "status": "Up", "media": "Native 802.11", "conn": "Connected", "speed": 866_000_000, "duplex": "False"},
        {"name": "Ethernet 2", "desc": "USB LAN", "status": "Disconnected", "media": "802.3", "conn": "Disconnected", "speed": 0, "duplex": ""},
    ],
    "speedduplex": [{"name": "Ethernet", "value": "Auto Negotiation",
                     "valid": ["Auto Negotiation", "10 Mbps Half Duplex", "100 Mbps Full Duplex", "1.0 Gbps Full Duplex"]}],
}


def link(**kw):
    base = dict(name="Ethernet", connected=True, speed_mbps=1000, max_mbps=1000, full_duplex=True, setting="Auto Negotiation")
    base.update(kw)
    return lh.LinkInfo(**base)


def report(burst=None, errors=0, flaps=0, **kw):
    return lh.LinkReport(link(**kw), lh.Counters(0, 0, errors, 0), flaps, burst)


def first(findings):
    return findings[0]


def test_parse_links_wired_only_and_max_speed():
    links = lh.parse_links(DATA)
    assert [x.name for x in links] == ["Ethernet", "Ethernet 2"]
    eth = links[0]
    assert eth.connected and eth.speed_mbps == 100 and eth.max_mbps == 1000 and eth.full_duplex is True
    assert not links[1].connected
    assert lh.parse_links(None) == [] and lh.parse_links({}) == []


def test_healthy_link_passes_but_states_limits():
    f = lh.assess(report(burst=lh.Burst(60, 60, 1.0, 0.2, 2.0)))
    assert f[0][0] == S.PASS and "No sign" in f[0][1]


def test_no_link_is_fail_with_cautious_wording():
    f = lh.assess(report(connected=False))
    assert f[0][0] == S.FAIL and "Possible" in f[0][1]


def test_downshift_to_100mbps_warns_about_damaged_pairs():
    f = lh.assess(report(speed_mbps=100))
    assert f[0][0] == S.WARNING and "4 pairs" in f[0][1]


def test_forced_speed_is_flagged():
    f = lh.assess(report(speed_mbps=100, setting="100 Mbps Full Duplex"))
    assert "forced" in f[0][1]


def test_half_duplex_errors_flaps_and_loss():
    assert any("half duplex" in m for _, m, _ in lh.assess(report(full_duplex=False)))
    assert any("packet error" in m for _, m, _ in lh.assess(report(errors=5)))
    assert any("dropped and reconnected" in m for _, m, _ in lh.assess(report(flaps=4)))
    assert not any("dropped" in m for _, m, _ in lh.assess(report(flaps=None)))
    loss = lh.assess(report(burst=lh.Burst(60, 50, 1.0, 0.1, 3.0)))
    assert loss[0][0] == S.WARNING and "16.7% packet loss" in loss[0][1]


def test_burst_no_replies_is_not_called_a_dead_cable():
    f = lh.assess(report(burst=lh.Burst(60, 0)))
    assert f[0][0] == S.FAIL and "may filter ICMP" in f[0][1]


def test_burst_math():
    ok = lh.Burst(60, 60)
    assert ok.loss_pct == 0 and lh.Burst().loss_pct == 0
    with mock.patch.object(lh.ping_service, "ping_once", side_effect=[
            mock.Mock(success=True, rtt_ms=1.0, message=""), mock.Mock(success=False, rtt_ms=None, message="x"),
            mock.Mock(success=True, rtt_ms=3.0, message="")]):
        b = lh.burst_ping("10.0.0.1", count=3)
    assert (b.sent, b.received, b.avg_ms, b.max_ms) == (3, 2, 2.0, 3.0)


def test_parse_counters():
    c = lh.parse_counters([{"name": "E", "rx": 10, "tx": 5, "rxerr": 1, "txerr": 2, "rxdrop": 3, "txdrop": 4}])
    assert c["E"] == lh.Counters(10, 5, 3, 7)


def test_no_wired_adapter_is_skipped_not_failed():
    with mock.patch.object(lh, "run_powershell_json", return_value=({"adapters": [], "speedduplex": []}, mock.Mock())):
        r = lh.run_link_health()
    assert r.status == S.SKIPPED


ALL_OK = dict(adapter=S.PASS, ip=S.PASS, gateway=S.PASS, gateway_ping=S.PASS, dns=S.PASS, internet_ip=S.PASS, https=S.PASS, target=S.SKIPPED)


def locate(link_level=S.PASS, **changes):
    layers = fa.build_layers(link_level, {**ALL_OK, **changes})
    return fa.locate(layers)


def test_everything_fine_blames_the_users_pc():
    key, level, text = locate()
    assert key == "" and level == S.PASS and "that user's PC" in text


def test_cable_layer_wins_when_link_is_bad():
    assert locate(S.FAIL)[0] == "cable"
    assert locate(S.WARNING)[0] == "cable" and locate(S.WARNING)[1] == S.WARNING


def test_each_layer_is_located():
    assert locate(ip=S.FAIL)[0] == "address"
    assert locate(gateway_ping=S.FAIL, internet_ip=S.FAIL, https=S.FAIL, dns=S.FAIL)[0] == "local"
    assert locate(dns=S.FAIL)[0] == "dns"
    assert locate(internet_ip=S.FAIL, https=S.FAIL)[0] == "internet"
    assert locate(target=S.FAIL)[0] == "target"


def test_icmp_filtered_gateway_is_not_blamed_when_internet_works():
    assert locate(gateway_ping=S.FAIL)[0] == ""


def test_skipped_cable_layer_never_blamed():
    assert locate(S.SKIPPED)[0] == ""

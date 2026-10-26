from netvanta.models.results import Status as S
from netvanta.services.diagnosis_service import interpret

OK = dict(adapter=S.PASS, ip=S.PASS, gateway=S.PASS, gateway_ping=S.PASS, dns=S.PASS, internet_ip=S.PASS,
          https=S.PASS, target=S.SKIPPED)


def top(**changes):
    return interpret({**OK, **changes})


def test_all_good():
    f = top()
    assert len(f) == 1 and f[0][0] == S.PASS


def test_no_adapter():
    f = top(adapter=S.FAIL)
    assert f[0][0] == S.FAIL and "adapter" in f[0][1]


def test_dhcp_problem():
    assert "DHCP" in top(ip=S.FAIL)[0][1]


def test_no_gateway():
    assert "gateway" in top(gateway=S.FAIL)[0][1]


def test_gateway_ping_fails_but_internet_works_is_only_a_warning():
    f = top(gateway_ping=S.FAIL)
    assert f[0][0] == S.WARNING and "ICMP" in f[0][1]


def test_gateway_and_internet_down_uses_uncertain_wording():
    f = top(gateway_ping=S.FAIL, internet_ip=S.FAIL, https=S.FAIL, dns=S.FAIL)
    assert f[0][0] == S.FAIL and "Possible" in f[0][1] and "not certain" in f[0][1]


def test_dns_only_failure():
    f = top(dns=S.FAIL, https=S.FAIL)
    assert any("DNS issue" in m for _, m, _ in f)


def test_https_only_failure():
    f = top(https=S.FAIL)
    assert f[0][0] == S.WARNING and "HTTPS" in f[0][1]


def test_ip_probe_blocked_but_https_ok():
    assert any("firewall" in m for _, m, _ in top(internet_ip=S.FAIL, https=S.PASS))


def test_target_down_only():
    f = top(target=S.FAIL)
    assert f[0][0] == S.WARNING and "target" in f[0][1]


def test_every_single_failure_gives_a_finding():
    for key in ("gateway_ping", "dns", "internet_ip", "https", "target"):
        assert interpret({**OK, key: S.FAIL})

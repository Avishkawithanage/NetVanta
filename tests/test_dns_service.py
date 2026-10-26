from unittest import mock

import dns.resolver

from netvanta.models.results import Status
from netvanta.services import dns_service


def _run(exc=None, answer=None):
    resolver = mock.MagicMock()
    resolver.nameservers = ["1.1.1.1"]
    if exc:
        resolver.resolve.side_effect = exc
    else:
        resolver.resolve.return_value = answer
    with mock.patch.object(dns_service.dns.resolver, "Resolver", return_value=resolver):
        return dns_service.lookup("example.com", "A", "1.1.1.1")


def test_success():
    rdata = mock.MagicMock()
    rdata.to_text.return_value = "93.184.216.34"
    answer = mock.MagicMock()
    answer.__iter__.return_value = iter([rdata])
    answer.rrset.ttl = 300
    r = _run(answer=answer)
    assert r.status == Status.PASS and r.rows[0]["value"] == "93.184.216.34"


def test_nxdomain_is_reported_separately():
    r = _run(exc=dns.resolver.NXDOMAIN())
    assert r.status == Status.FAIL and "NXDOMAIN" in r.summary


def test_no_answer_is_warning_not_nonexistence():
    r = _run(exc=dns.resolver.NoAnswer())
    assert r.status == Status.WARNING and "no A records" in r.summary


def test_timeout_does_not_claim_no_records():
    r = _run(exc=dns.resolver.LifetimeTimeout(timeout=1, errors=[]))
    assert r.status == Status.FAIL and "does not mean" in r.recommendation


def test_resolver_failure():
    r = _run(exc=dns.resolver.NoNameservers())
    assert r.status == Status.FAIL and "refused" in r.summary

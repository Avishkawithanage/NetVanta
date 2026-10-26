"""DNS record lookup using dnspython."""

from __future__ import annotations

import time

import dns.exception
import dns.resolver

from ..models.results import CheckResult, Status

RECORD_TYPES = ("A", "AAAA", "MX", "NS", "TXT", "CNAME")


def _format_rdata(rtype: str, rdata) -> str:
    if rtype == "MX":
        return f"{rdata.preference} {rdata.exchange}"
    if rtype == "TXT":
        return " ".join(part.decode("utf-8", "replace") for part in rdata.strings)
    return rdata.to_text()


def lookup(name: str, rtype: str = "A", resolver_ip: str = "", timeout: float = 5.0) -> CheckResult:
    started = time.monotonic()
    rtype = rtype.upper()
    result = CheckResult(tool="DNS Lookup", target=f"{name} ({rtype})")
    try:
        resolver = dns.resolver.Resolver(configure=not resolver_ip)
        if resolver_ip:
            resolver.nameservers = [resolver_ip]
        resolver.lifetime = timeout
        resolver.timeout = min(timeout, 3.0)
        used = ", ".join(resolver.nameservers) if resolver.nameservers else "system default"
    except Exception as exc:  # no system resolver configured etc.
        result.status = Status.FAIL
        result.summary = "No DNS resolver is configured."
        result.error = str(exc)
        return result

    try:
        answer = resolver.resolve(name, rtype)
        records = [_format_rdata(rtype, r) for r in answer]
        result.status = Status.PASS
        result.summary = f"{len(records)} {rtype} record(s) for {name}."
        result.details = f"Resolver: {used}\nTTL: {answer.rrset.ttl}s\n\n" + "\n".join(records)
        result.simple = f"{name} has {len(records)} {rtype} record(s):\n\n" + "\n".join(f"  {r}" for r in records) + "\n\n(Press 'Show details' for the resolver, TTL and timing.)"
        result.rows = [{"name": name, "type": rtype, "value": r, "ttl": answer.rrset.ttl, "resolver": used} for r in records]
    except dns.resolver.NXDOMAIN:
        result.status = Status.FAIL
        result.summary = f"{name} does not exist (NXDOMAIN)."
        result.details = f"Resolver: {used}"
        result.recommendation = "Check the spelling of the name. The resolver answered, so DNS itself is working."
    except dns.resolver.NoAnswer:
        result.status = Status.WARNING
        result.summary = f"{name} exists but has no {rtype} records."
        result.details = f"Resolver: {used}"
    except (dns.resolver.LifetimeTimeout, dns.exception.Timeout):
        result.status = Status.FAIL
        result.summary = "The DNS server did not answer in time."
        result.details = f"Resolver: {used}"
        result.error = "Timeout"
        result.recommendation = (
            "This does not mean the domain has no records. Try another resolver (for example 1.1.1.1) "
            "or check your connection."
        )
    except dns.resolver.NoNameservers as exc:
        result.status = Status.FAIL
        result.summary = "The DNS server(s) refused or failed the query."
        result.details = f"Resolver: {used}"
        result.error = str(exc)[:300]
        result.recommendation = "Try a different resolver."
    except (dns.exception.DNSException, OSError) as exc:
        result.status = Status.FAIL
        result.summary = "DNS query failed."
        result.error = str(exc)[:300]
    result.duration_ms = (time.monotonic() - started) * 1000
    if result.status != Status.UNKNOWN:
        result.details += f"\n\nQuery time: {result.duration_ms:.0f} ms"
    return result

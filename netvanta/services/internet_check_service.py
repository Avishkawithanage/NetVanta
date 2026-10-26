"""External HTTPS connectivity check and optional public IP lookup.

These are the only features that contact the internet, and only when the user asks.
"""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from ..models.results import CheckResult, Status

USER_AGENT = "NetVanta-ConnectivityCheck/1.0"


def _context() -> ssl.SSLContext:
    """Default verification, minus the strict X.509 profile that rejects some valid public certificates."""
    ctx = ssl.create_default_context()
    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


@dataclass
class EndpointResult:
    url: str
    ok: bool
    stage: str  # dns | connect | tls | http | timeout | ok
    message: str
    ms: float | None = None
    http_status: int | None = None


def classify_error(exc: BaseException) -> tuple[str, str]:
    """Map an exception to (stage, human message)."""
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, socket.gaierror):
        return "dns", "DNS resolution failed"
    if isinstance(reason, ssl.SSLCertVerificationError):
        return "tls", "TLS certificate could not be verified (wrong system clock, proxy or interception?)"
    if isinstance(reason, ssl.SSLError):
        return "tls", f"TLS handshake failed: {reason}"
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "timeout", "Timed out"
    if isinstance(reason, ConnectionRefusedError):
        return "connect", "Connection refused"
    if isinstance(reason, (ConnectionError, OSError)):
        return "connect", getattr(reason, "strerror", None) or str(reason)
    if isinstance(reason, http.client.HTTPException):
        return "http", f"HTTP protocol error: {reason}"
    return "http", str(reason)


def check_endpoint(url: str, timeout: float = 6.0) -> EndpointResult:
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_context()) as response:
            response.read(512)
            code = response.status
        ms = (time.monotonic() - started) * 1000
        ok = 200 <= code < 400
        return EndpointResult(url, ok, "ok" if ok else "http", f"HTTP {code}", ms, code)
    except urllib.error.HTTPError as exc:  # server reached, but it answered with an error status
        return EndpointResult(url, False, "http", f"Server reached, answered HTTP {exc.code}", (time.monotonic() - started) * 1000, exc.code)
    except Exception as exc:
        stage, message = classify_error(exc)
        return EndpointResult(url, False, stage, message)


def run_internet_check(endpoints: list[str], timeout: float = 6.0) -> CheckResult:
    started = time.monotonic()
    results = [check_endpoint(url, timeout) for url in endpoints]
    result = CheckResult(tool="Internet Check", target=", ".join(endpoints))
    result.duration_ms = (time.monotonic() - started) * 1000
    result.rows = [
        {"endpoint": r.url, "ok": r.ok, "stage": r.stage, "message": r.message, "ms": round(r.ms, 1) if r.ms else ""}
        for r in results
    ]
    result.details = "EXTERNAL CHECK - these requests contacted the internet.\n\n" + "\n".join(
        f"{'OK  ' if r.ok else 'FAIL'} {r.url}\n       {r.message}" + (f" ({r.ms:.0f} ms)" if r.ms else "") for r in results
    )
    ok = sum(1 for r in results if r.ok)
    if not results:
        result.status, result.summary = Status.SKIPPED, "No endpoints configured."
    elif ok == len(results):
        result.status, result.summary = Status.PASS, f"HTTPS connectivity works ({ok}/{len(results)} endpoints)."
    elif ok:
        result.status, result.summary = Status.WARNING, f"{ok} of {len(results)} endpoints reachable - the internet works, some endpoints are blocked or down."
    else:
        result.status = Status.FAIL
        stages = {r.stage for r in results}
        hint = {
            "dns": "Possible DNS issue.",
            "timeout": "Possible blocked or very slow connection.",
            "tls": "Possible TLS/certificate or proxy problem.",
            "connect": "Possible firewall or routing problem.",
        }
        result.summary = f"None of {len(results)} endpoint(s) reachable. " + " ".join(hint[s] for s in sorted(stages) if s in hint)
        result.recommendation = "One or more endpoints may be blocked by policy; try the DNS and TCP tools to narrow it down."
    return result


def get_public_ip(endpoint: str = "https://api.ipify.org", timeout: float = 6.0) -> CheckResult:
    started = time.monotonic()
    result = CheckResult(tool="Public IP", target=endpoint)
    request = urllib.request.Request(endpoint, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_context()) as response:
            text = response.read(256).decode("ascii", "replace").strip()
        address = str(ipaddress.ip_address(text))
        result.status = Status.PASS
        result.summary = f"Public IP address: {address}"
        result.details = (
            "EXTERNAL CHECK - this contacted " + endpoint + ".\n"
            "If you use a VPN, proxy or several internet connections, the address shown is the one the service saw."
        )
        result.rows = [{"public_ip": address, "endpoint": endpoint}]
    except ValueError:
        result.status, result.summary = Status.FAIL, "The service did not return a valid IP address."
    except Exception as exc:
        stage, message = classify_error(exc)
        result.status, result.summary, result.error = Status.FAIL, "Could not determine the public IP.", f"{stage}: {message}"
    result.duration_ms = (time.monotonic() - started) * 1000
    return result

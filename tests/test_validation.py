import pytest

from netvanta.utils.validation import (ValidationError, parse_ports, validate_host, validate_number, validate_port,
                                       validate_resolver, validate_url)


@pytest.mark.parametrize("value,expected", [
    ("8.8.8.8", "8.8.8.8"), ("  example.com ", "example.com"), ("::1", "::1"), ("[2001:db8::1]", "2001:db8::1"),
    ("localhost", "localhost"), ("my-host_1.local", "my-host_1.local"), ("example.com.", "example.com"),
    ("bücher.de", "xn--bcher-kva.de"),
])
def test_valid_hosts(value, expected):
    assert validate_host(value) == expected


@pytest.mark.parametrize("value", ["", "   ", "999.1.1.1", "1.2.3", "-t", "-n 5", "a b", "bad;rm", "host|x", "-bad.com",
                                   "a" * 64 + ".com", "exa mple.com", "http://x.com", "x" * 260])
def test_invalid_hosts(value):
    with pytest.raises(ValidationError):
        validate_host(value)


@pytest.mark.parametrize("value", ["0", "65536", "-1", "abc", "", "1.5"])
def test_invalid_ports(value):
    with pytest.raises(ValidationError):
        validate_port(value)


def test_valid_ports_edges():
    assert validate_port("1") == 1 and validate_port(" 65535 ") == 65535


def test_parse_ports():
    assert parse_ports("443, 80 8000-8002,80") == [80, 443, 8000, 8001, 8002]
    for bad in ("", "80-70", "0", "1-100"):
        with pytest.raises(ValidationError):
            parse_ports(bad)


def test_validate_number():
    assert validate_number("4", "x", 1, 10) == 4
    assert validate_number("1.5", "x", 0.2, 10, integer=False) == 1.5
    for bad in ("0", "11", "abc", "2.5"):
        with pytest.raises(ValidationError):
            validate_number(bad, "x", 1, 10)


def test_resolver_and_url():
    assert validate_resolver("") == "" and validate_resolver("1.1.1.1") == "1.1.1.1"
    with pytest.raises(ValidationError):
        validate_resolver("dns.google")
    assert validate_url("https://a.com/x") == "https://a.com/x"
    for bad in ("http://a.com", "ftp://a", "https://", "a.com"):
        with pytest.raises(ValidationError):
            validate_url(bad)

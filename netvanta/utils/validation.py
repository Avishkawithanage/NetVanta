"""Input validation. Everything typed by a user passes through here first."""

from __future__ import annotations

import ipaddress
import re

from ..defaults import MAX_PORTS_PER_TEST


class ValidationError(ValueError):
    """Raised with a message that is safe to show to the user."""


_LABEL = re.compile(r"^(?!-)[A-Za-z0-9_-]{1,63}(?<!-)$")


def validate_host(value: str) -> str:
    """Return a normalised hostname or IP address, or raise ValidationError."""
    text = (value or "").strip()
    if not text:
        raise ValidationError("Enter a hostname or an IP address.")
    if any(ch.isspace() for ch in text) or any(ch in text for ch in "\"'`;&|<>^%/\\"):
        raise ValidationError("The target contains characters that are not allowed.")
    bare = text[1:-1] if text.startswith("[") and text.endswith("]") else text
    try:
        return str(ipaddress.ip_address(bare))
    except ValueError:
        pass
    try:
        ascii_name = text.rstrip(".").encode("idna").decode("ascii")
    except UnicodeError:
        raise ValidationError("That is not a valid hostname.") from None
    if not ascii_name or len(ascii_name) > 253:
        raise ValidationError("That is not a valid hostname.")
    labels = ascii_name.split(".")
    if all(label.isdigit() for label in labels):
        raise ValidationError("That looks like an IP address but it is not valid.")
    if not all(_LABEL.match(label) for label in labels):
        raise ValidationError("That is not a valid hostname.")
    return ascii_name


def validate_port(value) -> int:
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError("A port must be a whole number from 1 to 65535.") from None
    if not 1 <= port <= 65535:
        raise ValidationError("A port must be between 1 and 65535.")
    return port


def parse_ports(text: str, limit: int = MAX_PORTS_PER_TEST) -> list[int]:
    """Parse '80, 443, 8000-8003' into a sorted, de-duplicated port list."""
    ports: set[int] = set()
    for part in re.split(r"[,\s]+", (text or "").strip()):
        if not part:
            continue
        if "-" in part:
            lo, _, hi = part.partition("-")
            first, last = validate_port(lo), validate_port(hi)
            if first > last:
                raise ValidationError(f"Invalid port range '{part}'.")
            ports.update(range(first, last + 1))
        else:
            ports.add(validate_port(part))
        if len(ports) > limit:
            raise ValidationError(f"Test at most {limit} ports at a time.")
    if not ports:
        raise ValidationError("Enter at least one port.")
    return sorted(ports)


def validate_number(value, name: str, low: float, high: float, integer: bool = True):
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a number.") from None
    if integer:
        if number != int(number):
            raise ValidationError(f"{name} must be a whole number.")
        number = int(number)
    if not low <= number <= high:
        shown_low, shown_high = (int(low), int(high)) if integer else (low, high)
        raise ValidationError(f"{name} must be between {shown_low} and {shown_high}.")
    return number


def validate_resolver(value: str) -> str:
    """A DNS resolver must be an IP address; empty means system default."""
    text = (value or "").strip()
    if not text:
        return ""
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        raise ValidationError("The DNS server must be an IP address (or empty for system default).") from None


def validate_url(value: str) -> str:
    text = (value or "").strip()
    if not re.match(r"^https://[^\s/]+(/\S*)?$", text):
        raise ValidationError("Endpoints must be https:// URLs.")
    return text

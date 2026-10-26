"""Typed result models shared by every service and view."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"
    UNKNOWN = "UNKNOWN"


STATUS_ICON = {Status.PASS: "✔", Status.FAIL: "✖", Status.WARNING: "⚠", Status.SKIPPED: "–", Status.UNKNOWN: "?"}
STATUS_WORD = {Status.PASS: "OK", Status.FAIL: "Problem", Status.WARNING: "Check this", Status.SKIPPED: "Skipped", Status.UNKNOWN: "Unknown"}


def utc_now_iso() -> str:
    """Canonical timestamp used for storage: UTC, ISO-8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_local(ts: str) -> str:
    """Convert a stored UTC timestamp to a local, human readable string."""
    try:
        dt = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return ts or ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class CheckResult:
    tool: str
    target: str = ""
    status: Status = Status.UNKNOWN
    summary: str = ""
    simple: str = ""  # short, friendly view shown by default; empty = the tool has nothing simpler than `details`
    details: str = ""  # NetVanta's readable body / interpretation
    raw: str = ""  # raw command output, kept separate from interpretation
    error: str = ""
    recommendation: str = ""
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=utc_now_iso)
    rows: list[dict] = field(default_factory=list)
    cancelled: bool = False

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    def render(self) -> str:
        """Plain text suitable for the output box and the clipboard."""
        parts = [self.summary] if self.summary else []
        if self.details:
            parts.append(self.details)
        if self.recommendation:
            parts.append(f"Next step: {self.recommendation}")
        if self.error:
            parts.append(f"Error: {self.error}")
        return "\n\n".join(parts)

    def clipboard_summary(self) -> str:
        head = f"[{self.timestamp}] {self.tool}"
        if self.target:
            head += f" -> {self.target}"
        body = (self.simple + (f"\n\nError: {self.error}" if self.error else "")) if self.simple else self.render()
        return f"{head}\nStatus: {self.status.value}\n{self.summary}\n\n{body}" if self.simple else f"{head}\nStatus: {self.status.value}\n{body}"

"""Data access for history and monitor targets. All SQL is parameterised."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..models.results import CheckResult, utc_now_iso
from .database import Database, DatabaseError

MONITOR_TOOL = "Live Monitor"


class HistoryRepository:
    def __init__(self, db: Database):
        self.db = db

    def add_result(self, result: CheckResult) -> int:
        return self.add(result.timestamp, result.tool, result.target, result.status.value,
                        result.summary, result.render(), result.duration_ms)

    def add(self, ts: str, tool: str, target: str, status: str, summary: str, details: str = "", duration_ms: float = 0) -> int:
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO history(ts, tool, target, status, summary, details, duration_ms) VALUES (?,?,?,?,?,?,?)",
                (ts, tool, target, status, summary, details[:20000], duration_ms),
            )
            return int(cur.lastrowid)

    def search(self, hours: float | None = None, tool: str = "", text: str = "", limit: int = 2000) -> list[dict]:
        sql = "SELECT * FROM history WHERE 1=1"
        params: list = []
        if hours:
            since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
            sql += " AND ts >= ?"
            params.append(since)
        if tool:
            sql += " AND tool = ?"
            params.append(tool)
        if text:
            like = f"%{text}%"
            sql += " AND (target LIKE ? OR summary LIKE ? OR tool LIKE ?)"
            params += [like, like, like]
        sql += " ORDER BY ts DESC, id DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.db.query(sql, tuple(params))]

    def tools(self) -> list[str]:
        return [r[0] for r in self.db.query("SELECT DISTINCT tool FROM history ORDER BY tool")]

    def recent_events(self, limit: int = 6) -> list[dict]:
        rows = self.db.query("SELECT * FROM history WHERE tool = ? ORDER BY ts DESC, id DESC LIMIT ?", (MONITOR_TOOL, limit))
        return [dict(r) for r in rows]

    def delete(self, ids: list[int]) -> int:
        if not ids:
            return 0
        with self.db.transaction() as conn:
            marks = ",".join("?" * len(ids))
            return conn.execute(f"DELETE FROM history WHERE id IN ({marks})", tuple(ids)).rowcount

    def clear(self) -> int:
        with self.db.transaction() as conn:
            return conn.execute("DELETE FROM history").rowcount

    def count(self) -> int:
        return int(self.db.query("SELECT COUNT(*) FROM history")[0][0])


@dataclass
class Target:
    name: str
    host: str
    interval_s: int = 5
    timeout_ms: int = 2000
    enabled: bool = True
    id: int | None = None


class DuplicateTargetError(DatabaseError):
    pass


class TargetRepository:
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _from_row(row) -> Target:
        return Target(row["name"], row["host"], row["interval_s"], row["timeout_ms"], bool(row["enabled"]), row["id"])

    def list(self) -> list[Target]:
        return [self._from_row(r) for r in self.db.query("SELECT * FROM targets ORDER BY name COLLATE NOCASE")]

    def add(self, target: Target) -> Target:
        try:
            with self.db.transaction() as conn:
                cur = conn.execute(
                    "INSERT INTO targets(name, host, interval_s, timeout_ms, enabled, created) VALUES (?,?,?,?,?,?)",
                    (target.name, target.host, target.interval_s, target.timeout_ms, int(target.enabled), utc_now_iso()),
                )
                target.id = int(cur.lastrowid)
        except sqlite3.IntegrityError:
            raise DuplicateTargetError(f"'{target.host}' is already being monitored.") from None
        return target

    def update(self, target: Target) -> None:
        try:
            with self.db.transaction() as conn:
                conn.execute(
                    "UPDATE targets SET name=?, host=?, interval_s=?, timeout_ms=?, enabled=? WHERE id=?",
                    (target.name, target.host, target.interval_s, target.timeout_ms, int(target.enabled), target.id),
                )
        except sqlite3.IntegrityError:
            raise DuplicateTargetError(f"'{target.host}' is already being monitored.") from None

    def delete(self, target_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM targets WHERE id=?", (target_id,))

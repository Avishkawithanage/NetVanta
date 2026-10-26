"""CSV / JSON export and clipboard helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ..models.results import CheckResult


class ExportError(Exception):
    """Raised with a user-presentable message when a file cannot be written."""


def result_rows(result: CheckResult) -> list[dict]:
    """Rows for CSV: the tool's own table if it has one, else one summary row."""
    base = {
        "timestamp": result.timestamp,
        "tool": result.tool,
        "target": result.target,
        "status": result.status.value,
    }
    if result.rows:
        return [{**base, **row} for row in result.rows]
    return [{**base, "summary": result.summary, "error": result.error, "duration_ms": round(result.duration_ms, 1)}]


def write_csv(path: str | Path, rows: list[dict]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    except OSError as exc:
        raise ExportError(f"Could not write the file: {exc.strerror or exc}") from exc


def write_json(path: str | Path, payload) -> None:
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
    except OSError as exc:
        raise ExportError(f"Could not write the file: {exc.strerror or exc}") from exc


def export_result(path: str | Path, result: CheckResult) -> None:
    """Export by file extension: .csv (table) or .json (full structured result)."""
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        write_csv(path, result_rows(result))
    elif suffix == ".json":
        write_json(path, result.to_dict())
    else:
        raise ExportError("Choose a .csv or .json file name.")


def export_rows(path: str | Path, rows: list[dict]) -> None:
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        write_csv(path, rows)
    elif suffix == ".json":
        write_json(path, rows)
    else:
        raise ExportError("Choose a .csv or .json file name.")

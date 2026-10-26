import csv
import json

import pytest

from netvanta.models.results import CheckResult, Status
from netvanta.utils.export import ExportError, export_result, export_rows


def sample():
    return CheckResult(tool="Ping", target="a.com", status=Status.PASS, summary="ok",
                       rows=[{"seq": 1, "rtt_ms": 12}, {"seq": 2, "rtt_ms": 14}])


def test_csv_rows(tmp_path):
    p = tmp_path / "o.csv"
    export_result(p, sample())
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    assert len(rows) == 2 and rows[0]["tool"] == "Ping" and rows[1]["rtt_ms"] == "14" and rows[0]["status"] == "PASS"


def test_csv_summary_row_when_no_table(tmp_path):
    p = tmp_path / "o.csv"
    export_result(p, CheckResult(tool="DNS", summary="s", status=Status.FAIL))
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    assert rows[0]["summary"] == "s" and rows[0]["status"] == "FAIL"


def test_json_full_result(tmp_path):
    p = tmp_path / "o.json"
    export_result(p, sample())
    data = json.load(open(p, encoding="utf-8"))
    assert data["status"] == "PASS" and len(data["rows"]) == 2 and data["tool"] == "Ping"


def test_unicode_and_spaces_in_path(tmp_path):
    folder = tmp_path / "my folder"
    folder.mkdir()
    p = folder / "résumé.json"
    export_rows(p, [{"a": "ü"}])
    assert json.load(open(p, encoding="utf-8"))[0]["a"] == "ü"


def test_bad_extension_and_write_failure(tmp_path):
    with pytest.raises(ExportError):
        export_result(tmp_path / "o.txt", sample())
    with pytest.raises(ExportError):
        export_result(tmp_path / "nope" / "o.csv", sample())
    with pytest.raises(ExportError):
        export_rows(tmp_path / "nope" / "o.json", [{"a": 1}])

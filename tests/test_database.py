import pytest

from netvanta.data.database import Database, DatabaseError
from netvanta.data.repositories import DuplicateTargetError, HistoryRepository, Target, TargetRepository
from netvanta.data.settings_store import SettingsStore
from netvanta.models.results import CheckResult, Status


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    yield d
    d.close()


def test_history_crud(db):
    h = HistoryRepository(db)
    rid = h.add_result(CheckResult(tool="Ping", target="a.com", status=Status.PASS, summary="ok"))
    h.add_result(CheckResult(tool="DNS Lookup", target="b.com", status=Status.FAIL, summary="bad"))
    assert h.count() == 2 and h.tools() == ["DNS Lookup", "Ping"]
    assert [r["target"] for r in h.search(tool="Ping")] == ["a.com"]
    assert len(h.search(text="b.com")) == 1
    assert len(h.search(hours=1)) == 2
    assert h.delete([rid]) == 1 and h.count() == 1
    assert h.delete([]) == 0
    assert h.clear() == 1 and h.count() == 0


def test_sql_injection_is_inert(db):
    h = HistoryRepository(db)
    h.add_result(CheckResult(tool="Ping", target="x", summary="s"))
    assert h.search(text="'; DROP TABLE history;--") == []
    assert h.count() == 1


def test_target_crud_and_duplicates(db):
    t = TargetRepository(db)
    a = t.add(Target("Router", "192.168.1.1"))
    assert a.id and len(t.list()) == 1
    with pytest.raises(DuplicateTargetError):
        t.add(Target("Again", "192.168.1.1"))
    a.name, a.enabled = "GW", False
    t.update(a)
    got = t.list()[0]
    assert got.name == "GW" and got.enabled is False
    t.delete(a.id)
    assert t.list() == []


def test_closed_database_raises_friendly_error(tmp_path):
    d = Database(tmp_path / "c.db")
    d.close()
    with pytest.raises(DatabaseError):
        HistoryRepository(d).count()


def test_bad_path():
    with pytest.raises(DatabaseError):
        Database("Z:/definitely/not/here/x.db")


def test_settings_persistence_and_limits(tmp_path):
    p = tmp_path / "s.json"
    s = SettingsStore(p)
    s.set("ping_count", 9999)
    s.set("theme", "light")
    assert s.get("ping_count") == 100
    assert s.save() == ""
    again = SettingsStore(p)
    assert again.get("theme") == "light" and again.get("ping_count") == 100
    again.reset()
    assert SettingsStore(p).get("theme") == "dark"


def test_settings_corrupt_file_falls_back(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{not json", encoding="utf-8")
    assert SettingsStore(p).get("ping_count") == 4


def test_settings_bad_values_are_coerced(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"ping_count": "abc", "theme": "neon", "unknown": 1}', encoding="utf-8")
    s = SettingsStore(p)
    assert s.get("ping_count") == 4 and s.get("theme") == "dark" and "unknown" not in s.values


def test_settings_save_failure_reports(tmp_path):
    s = SettingsStore(tmp_path / "missing_dir" / "s.json")
    assert "Could not save" in s.save()

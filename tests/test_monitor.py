import time

import pytest

from netvanta.data.database import Database
from netvanta.data.repositories import HistoryRepository, Target, TargetRepository
from netvanta.services.monitor_service import DOWN, UNKNOWN, UP, MonitorManager, Runtime


def test_state_transitions_no_duplicates():
    rt = Runtime(Target("a", "1.1.1.1", id=1))
    assert rt.record(True, 10) is None  # unknown -> up is not an outage event
    assert rt.state == UP
    assert rt.record(False, None) is None  # a single failure is not an outage yet
    assert rt.record(False, None) == (UP, DOWN)
    for _ in range(10):  # one continuous outage = one event
        assert rt.record(False, None) is None
    assert rt.record(True, 5) == (DOWN, UP)
    assert rt.record(True, 5) is None


def test_initial_failures_report_down_once():
    rt = Runtime(Target("a", "x", id=1))
    assert rt.record(False, None) is None
    assert rt.record(False, None) == (UNKNOWN, DOWN)
    assert rt.record(False, None) is None


def test_recent_history_bounded():
    rt = Runtime(Target("a", "x", id=1))
    for i in range(50):
        rt.record(i % 2 == 0, 1.0)
    assert len(rt.recent) == 20 and rt.recent_failures == 10


@pytest.fixture
def mgr(tmp_path):
    db = Database(tmp_path / "m.db")
    results = {"ok": True}

    def probe(host, timeout):
        return (True, 3.0, "") if results["ok"] else (False, None, "no reply")

    m = MonitorManager(TargetRepository(db), HistoryRepository(db), probe=probe)
    m.results = results
    yield m
    m.shutdown()
    db.close()


def wait_for(cond, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_monitor_end_to_end_records_only_transitions(mgr):
    t = mgr.add(Target("r", "192.168.1.1", interval_s=2))
    mgr.start(t.id)
    assert wait_for(lambda: mgr.runtimes()[0].state == UP)
    mgr.results["ok"] = False
    assert wait_for(lambda: mgr.runtimes()[0].state == DOWN, 15)
    time.sleep(2.5)  # further failing checks must not add events
    events = mgr.history.recent_events(50)
    assert len(events) == 1 and events[0]["status"] == "FAIL"
    mgr.stop(t.id)


def test_stop_prevents_further_checks(mgr):
    t = mgr.add(Target("r", "x.local", interval_s=2))
    mgr.start(t.id)
    assert wait_for(lambda: mgr.runtimes()[0].last_checked)
    mgr.stop_all()
    time.sleep(0.5)  # let an in-flight check settle
    before = mgr.runtimes()[0].last_checked
    time.sleep(2.6)
    assert mgr.runtimes()[0].last_checked == before


def test_rapid_start_stop_and_persistence(mgr, tmp_path):
    t = mgr.add(Target("r", "y.local", interval_s=2))
    for _ in range(20):
        mgr.start(t.id)
        mgr.stop(t.id)
    mgr.start_all()
    mgr.shutdown()
    again = TargetRepository(Database(tmp_path / "m.db")).list()
    assert [x.host for x in again] == ["y.local"]


def test_disabled_target_does_not_start(mgr):
    t = mgr.add(Target("r", "z.local", enabled=False))
    mgr.start(t.id)
    assert not mgr.runtimes()[0].running


def test_probe_exception_does_not_kill_worker(tmp_path):
    db = Database(tmp_path / "e.db")

    def bad(host, timeout):
        raise RuntimeError("boom")

    m = MonitorManager(TargetRepository(db), HistoryRepository(db), probe=bad)
    t = m.add(Target("r", "q.local", interval_s=2))
    m.start(t.id)
    assert wait_for(lambda: m.runtimes()[0].last_checked)
    assert m.runtimes()[0].recent_failures >= 1
    m.shutdown()

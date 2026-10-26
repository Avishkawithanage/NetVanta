import socket
import threading
from unittest import mock

from netvanta.models.results import Status
from netvanta.services import ping_service as ps
from netvanta.utils.subprocess_runner import CommandResult

REPLY = (
    "Pinging 8.8.8.8 with 32 bytes of data:\nReply from 8.8.8.8: bytes=32 time=12ms TTL=117\n\n"
    "Ping statistics for 8.8.8.8:\n    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),\n"
    "Approximate round trip times in milli-seconds:\n    Minimum = 12ms, Maximum = 12ms, Average = 12ms\n"
)
FAST = "Reply from 127.0.0.1: bytes=32 time<1ms TTL=128\n"
TIMEOUT = (
    "Pinging 8.8.8.8 with 32 bytes of data:\nRequest timed out.\n\nPing statistics for 8.8.8.8:\n"
    "    Packets: Sent = 1, Received = 0, Lost = 1 (100% loss),\n"
)
UNREACH = (
    "Pinging 10.0.0.9 with 32 bytes of data:\nReply from 10.0.0.1: Destination host unreachable.\n\n"
    "Ping statistics for 10.0.0.9:\n    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),\n"
    "Approximate round trip times in milli-seconds:\n    Minimum = 0ms, Maximum = 0ms, Average = 0ms\n"
)
V6 = "Reply from ::1: time<1ms\n"


def test_parse_success():
    s = ps.parse_ping_output(REPLY)
    assert s.success and s.rtt_ms == 12


def test_parse_sub_millisecond():
    assert ps.parse_ping_output(FAST).rtt_ms == 0.5
    assert ps.parse_ping_output(V6).success


def test_parse_timeout_is_failure():
    s = ps.parse_ping_output(TIMEOUT)
    assert not s.success and s.rtt_ms is None


def test_parse_unreachable_is_not_success():
    assert not ps.parse_ping_output(UNREACH).success


def test_parse_garbage():
    assert not ps.parse_ping_output("").success
    assert not ps.parse_ping_output("\x00\x01 weird").success


def test_summary_empty_no_divide_by_zero():
    s = ps.summarize([])
    assert (s.sent, s.received, s.loss_pct, s.min_ms, s.avg_ms, s.max_ms) == (0, 0, 0.0, None, None, None)


def test_summary_values():
    samples = [ps.PingSample(1, True, 10), ps.PingSample(2, False), ps.PingSample(3, True, 30), ps.PingSample(4, False)]
    s = ps.summarize(samples)
    assert (s.sent, s.received, s.lost, s.loss_pct) == (4, 2, 2, 50.0)
    assert (s.min_ms, s.avg_ms, s.max_ms) == (10, 20, 30)


def test_all_lost_has_no_latency():
    s = ps.summarize([ps.PingSample(1, False)] * 3)
    assert s.loss_pct == 100 and s.avg_ms is None


def _cmd(out):
    return CommandResult(args=["ping"], returncode=0, stdout=out)


def test_run_ping_success():
    with mock.patch.object(ps, "run_command", return_value=_cmd(REPLY)):
        r = ps.run_ping("8.8.8.8", 3, 1000, 0)
    assert r.status == Status.PASS and len(r.rows) == 3


def test_run_ping_no_reply_wording():
    with mock.patch.object(ps, "run_command", return_value=_cmd(TIMEOUT)):
        r = ps.run_ping("8.8.8.8", 2, 1000, 0)
    assert r.status == Status.FAIL and "ICMP" in r.recommendation


def test_run_ping_partial_loss():
    outs = iter([_cmd(REPLY), _cmd(TIMEOUT)])
    with mock.patch.object(ps, "run_command", side_effect=lambda *a, **k: next(outs)):
        r = ps.run_ping("8.8.8.8", 2, 1000, 0)
    assert r.status == Status.WARNING


def test_run_ping_dns_failure():
    with mock.patch.object(ps.socket, "getaddrinfo", side_effect=socket.gaierror(11001, "no such host")):
        r = ps.run_ping("nope.invalid", 2, 1000, 0)
    assert r.status == Status.FAIL and "resolution" in r.error


def test_run_ping_command_missing():
    with mock.patch.object(ps, "run_command", return_value=CommandResult(args=["ping"], error="Command not found: ping")):
        r = ps.run_ping("8.8.8.8", 1, 1000, 0)
    assert r.status == Status.FAIL


def test_run_ping_process_timeout():
    with mock.patch.object(ps, "run_command", return_value=CommandResult(args=["ping"], timed_out=True)):
        r = ps.run_ping("8.8.8.8", 1, 1000, 0)
    assert r.status == Status.FAIL


def test_run_ping_cancel_is_partial_not_complete():
    cancel = threading.Event()

    def fake(*a, **k):
        cancel.set()
        return _cmd(REPLY)

    with mock.patch.object(ps, "run_command", side_effect=fake):
        r = ps.run_ping("8.8.8.8", 5, 1000, 0, cancel)
    assert r.cancelled and r.status == Status.UNKNOWN and "partial" in r.summary


def test_resolve_target_ip_passthrough():
    assert ps.resolve_target("1.2.3.4") == ("1.2.3.4", "")


def _sample(seq, ok, ts):
    return ps.PingSample(seq, ok, 1.0 if ok else None, "1.1.1.1", "" if ok else "Request timed out.", ts)


def test_find_outages_groups_consecutive_losses():
    s = [_sample(1, True, "2026-01-01T10:00:00+00:00"), _sample(2, False, "2026-01-01T10:00:01+00:00"),
         _sample(3, False, "2026-01-01T10:00:02+00:00"), _sample(4, True, "2026-01-01T10:00:05+00:00"),
         _sample(5, False, "2026-01-01T10:00:06+00:00")]
    out = ps.find_outages(s)
    assert len(out) == 2
    assert (out[0].lost, out[0].first_seq, out[0].last_seq, out[0].recovered) == (2, 2, 3, True)
    assert out[0].seconds == 4
    assert out[1].recovered is False and out[1].lost == 1
    assert "lost" in ps.format_outage(out[0]) and "no reply until you stopped" in ps.format_outage(out[1])
    assert ps.find_outages([_sample(1, True, "2026-01-01T10:00:00+00:00")]) == []


def test_continuous_ping_runs_until_stopped_and_reports_loss_events():
    cancel = threading.Event()
    outs = iter([_cmd(REPLY), _cmd(TIMEOUT), _cmd(TIMEOUT), _cmd(REPLY), _cmd(REPLY)])
    seen = []

    def on_sample(sample):
        seen.append(sample)
        if len(seen) == 5:
            cancel.set()

    with mock.patch.object(ps, "run_command", side_effect=lambda *a, **k: next(outs)):
        r = ps.run_ping("8.8.8.8", 0, 1000, 0, cancel, on_sample)
    assert len(seen) == 5 and all(s.ts for s in seen)
    assert not r.cancelled and r.status == Status.WARNING
    assert "Stopped after 5 packets" in r.summary and "1 loss event" in r.summary
    assert "LOSS EVENTS (1)" in r.details
    assert [row["success"] for row in r.rows] == [True, False, False, True, True]
    assert r.rows[1]["note"] and r.rows[1]["time_utc"]


def test_failure_message_is_the_reason_not_the_statistics_header():
    assert ps.parse_ping_output(TIMEOUT).message == "Request timed out."
    assert ps.parse_ping_output(UNREACH).message.startswith("Reply from 10.0.0.1")

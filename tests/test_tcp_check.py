import socket
import threading

from netvanta.models.results import Status
from netvanta.services import tcp_check_service as tcp


def _server():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    return srv, srv.getsockname()[1]


def test_connected():
    srv, port = _server()
    try:
        r = tcp.check_port("127.0.0.1", port, 2)
        assert r.outcome == "connected" and r.ms is not None
    finally:
        srv.close()


def test_refused():
    srv, port = _server()
    srv.close()
    assert tcp.check_port("127.0.0.1", port, 6).outcome == "refused"


def test_dns_error():
    assert tcp.check_port("nonexistent.invalid", 80, 2).outcome == "dns_error"


def test_timeout_is_not_called_closed(monkeypatch):
    def boom(*a, **k):
        raise TimeoutError()

    monkeypatch.setattr(tcp.socket, "create_connection", boom)
    r = tcp.run_port_check("example.com", [81], 1)
    assert r.rows[0]["outcome"] == "timeout" and "does not prove" in r.recommendation


def test_mixed_results():
    srv, port = _server()
    closed, cport = _server()
    closed.close()
    try:
        r = tcp.run_port_check("127.0.0.1", [port, cport], 2)
        assert r.status == Status.WARNING and len(r.rows) == 2
    finally:
        srv.close()


def test_cancelled_is_partial():
    ev = threading.Event()
    ev.set()
    r = tcp.run_port_check("127.0.0.1", [80], 1, ev)
    assert r.cancelled and r.status == Status.UNKNOWN

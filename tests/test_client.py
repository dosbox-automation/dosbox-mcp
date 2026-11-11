# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import logging
import math
import types

import httpx
import pytest

from dosbox_mcp.client import MAX_PAUSE_S, MIN_PAUSE_S, DosboxClient, EngineBusy


def make_client(handler):
    transport = httpx.MockTransport(handler)
    return DosboxClient(
        base_url="http://127.0.0.1:8386",
        token="0" * 64,
        transport=transport,
    )


def test_get_sends_bearer_token():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        seen["client"] = request.headers.get("x-client")
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler)
    body = client.get("/api/v1/status")
    assert body == {"ok": True}
    assert seen["auth"] == "Bearer " + "0" * 64
    assert seen["client"] == "mcp"


def test_post_sends_json_body():
    seen = {}

    def handler(request):
        seen["body"] = request.content
        seen["ctype"] = request.headers.get("content-type")
        return httpx.Response(200, json={"status": "ok"})

    client = make_client(handler)
    result = client.post("/api/v1/input/type", json={"text": "hi"})
    assert result == {"status": "ok"}
    assert b'"text"' in seen["body"]


def test_error_status_raises():
    def handler(request):
        return httpx.Response(400, json={"error": "bad"})

    client = make_client(handler)
    with pytest.raises(RuntimeError, match="bad"):
        client.get("/api/v1/status")


def test_binary_response_returned_as_bytes():
    def handler(request):
        return httpx.Response(
            200,
            content=b"\x89PNG",
            headers={"content-type": "image/png"},
        )

    client = make_client(handler)
    data = client.get("/api/v1/video/frame")
    assert data == b"\x89PNG"


@pytest.fixture
def clock(monkeypatch):
    fake = types.SimpleNamespace(now=1000.0, sleeps=[])

    def sleep(seconds):
        fake.sleeps.append(seconds)
        fake.now += seconds

    fake.monotonic = lambda: fake.now
    fake.sleep = sleep
    monkeypatch.setattr("dosbox_mcp.client.time", fake)
    return fake


def busy_then(answers, retry_after="0"):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) <= answers:
            return httpx.Response(503, json={"error": "Emulation busy, retry later"},
                                  headers={"Retry-After": retry_after})
        return httpx.Response(200, json={"ok": True})

    return handler, calls


def test_a_busy_answer_is_sent_again():
    handler, calls = busy_then(2)
    client = make_client(handler)
    assert client.post("/api/v1/input/type", json={"text": "hi"}) == {"ok": True}
    assert len(calls) == 3
    assert calls[0].content == calls[2].content


def test_a_503_without_retry_after_raises_at_once():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, json={"error": "No frame available yet"})

    client = make_client(handler)
    with pytest.raises(RuntimeError, match="No frame available yet") as raised:
        client.get("/api/v1/video/frame")
    assert len(calls) == 1
    assert not isinstance(raised.value, EngineBusy)


def test_busy_past_the_deadline_raises(clock):
    handler, calls = busy_then(10_000)
    client = make_client(handler)
    client.busy_deadline_s = 0.175
    with pytest.raises(EngineBusy, match="503: Emulation busy"):
        client.get("/api/v1/mixer")
    assert len(calls) == 4
    assert clock.sleeps == [MIN_PAUSE_S] * 3


def test_a_retry_after_of_zero_still_pauses(clock):
    handler, calls = busy_then(10_000)
    client = make_client(handler)
    client.busy_deadline_s = 0.3
    with pytest.raises(RuntimeError):
        client.get("/api/v1/mixer")
    assert clock.sleeps
    assert all(pause == MIN_PAUSE_S for pause in clock.sleeps)


def test_no_resend_when_the_pause_would_pass_the_deadline(clock):
    handler, calls = busy_then(10_000, retry_after="1")
    client = make_client(handler)
    client.busy_deadline_s = 0.3
    with pytest.raises(RuntimeError, match="503"):
        client.get("/api/v1/mixer")
    assert len(calls) == 1
    assert clock.sleeps == []


@pytest.mark.parametrize("retry_after", ["nan", "-1", "Wed, 21 Oct 2026 07:28:00 GMT"])
def test_an_odd_retry_after_is_a_pause_of_a_second(clock, retry_after):
    handler, calls = busy_then(2, retry_after=retry_after)
    client = make_client(handler)
    assert client.get("/api/v1/mixer") == {"ok": True}
    assert len(calls) == 3
    assert clock.sleeps == [MAX_PAUSE_S, MAX_PAUSE_S]


def test_a_long_retry_after_waits_at_most_a_second(clock):
    handler, calls = busy_then(1, retry_after="5")
    client = make_client(handler)
    assert client.get("/api/v1/mixer") == {"ok": True}
    assert clock.sleeps == [MAX_PAUSE_S]
    assert not any(math.isnan(pause) for pause in clock.sleeps)


def test_resends_are_logged_and_giving_up_warns(clock, caplog):
    handler, calls = busy_then(10_000)
    client = make_client(handler)
    client.busy_deadline_s = 0.175
    with caplog.at_level(logging.DEBUG, logger="dosbox_mcp.client"):
        with pytest.raises(RuntimeError):
            client.get("/api/v1/mixer")
    resends = [r for r in caplog.records if r.levelno == logging.DEBUG]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(resends) == 3
    assert len(warnings) == 1
    assert "/api/v1/mixer" in warnings[0].getMessage()


@pytest.mark.parametrize("send", [
    lambda c: c.put("/api/v1/cpu/cycles", json={"cycles": 3000}),
    lambda c: c.delete("/api/v1/memory/freeze", json={}),
    lambda c: c.post_text("/api/v1/script/load", "dosbox.log('x')"),
])
def test_every_method_is_sent_again_unchanged(send):
    handler, calls = busy_then(1)
    client = make_client(handler)
    assert send(client) == {"ok": True}
    assert len(calls) == 2
    assert calls[0].method == calls[1].method
    assert calls[0].content == calls[1].content
    assert calls[0].headers.get("content-type") == calls[1].headers.get("content-type")


def _listener(handler_cls=None):
    """A loopback server on a free port: an HTTP server, or a bare socket that counts connections."""
    import http.server
    import socket
    import threading
    if handler_cls is None:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(4)
        hits = []

        def accept():
            while True:
                try:
                    conn, _ = sock.accept()
                except OSError:
                    return
                hits.append(1)
                conn.close()
        threading.Thread(target=accept, daemon=True).start()
        return sock.getsockname()[1], hits, sock.close
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def stop():
        server.shutdown()
        server.server_close()
    return server.server_address[1], None, stop


def test_an_http_proxy_in_the_environment_never_sees_the_token(monkeypatch):
    # The bridge talks to loopback only; a proxy variable must not reroute it.
    import http.server
    import json as _json

    class Engine(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    proxy_port, proxy_hits, stop_proxy = _listener()
    engine_port, _, stop_engine = _listener(Engine)
    try:
        for var in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
            monkeypatch.setenv(var, f"http://127.0.0.1:{proxy_port}")
        for var in ("NO_PROXY", "no_proxy"):
            monkeypatch.delenv(var, raising=False)
        client = DosboxClient(f"http://127.0.0.1:{engine_port}", "a" * 64)
        assert client.get("/api/v1/status") == {"ok": True}
        assert proxy_hits == []
    finally:
        stop_proxy()
        stop_engine()


def test_the_hello_probe_ignores_an_http_proxy_too(monkeypatch):
    from dosbox_mcp.config import Config
    from dosbox_mcp.connection import Connection

    proxy_port, proxy_hits, stop_proxy = _listener()
    try:
        for var in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
            monkeypatch.setenv(var, f"http://127.0.0.1:{proxy_port}")
        for var in ("NO_PROXY", "no_proxy"):
            monkeypatch.delenv(var, raising=False)
        Connection(Config(base_url="http://127.0.0.1:9", token=None)).probe_hello()
        assert proxy_hits == []
    finally:
        stop_proxy()

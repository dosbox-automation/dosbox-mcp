# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import httpx
import mcp.types as types
import pytest

from dosbox_mcp.client import DosboxClient
from dosbox_mcp.config import Config
from dosbox_mcp.connection import Connection, NotConnected, guard


TOKEN = "0" * 64


def _refused(request):
    raise httpx.ConnectError("connection refused")


def _make_conn(token=None, features=None):
    config = Config(base_url="http://127.0.0.1:8386", token=token)
    # Unit tests never touch the network: even the hello probe runs
    # against a transport that simulates "nothing is listening".
    conn = Connection(config, transport=httpx.MockTransport(_refused))
    if features is not None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json={"ok": True})
        )
        conn._client = DosboxClient(
            config.base_url, token or TOKEN, transport=transport
        )
        conn._features = features
    return conn


def _routes(info=None, hello=None, require_token=TOKEN):
    """MockTransport standing in for a running engine: /info behind the
    bearer token, /hello unauthenticated (404 when the engine predates
    the route)."""
    def handler(request):
        if request.url.path == "/api/v1/hello":
            if hello is None:
                return httpx.Response(404, json={"error": "not found"})
            return httpx.Response(200, json=hello)
        if request.url.path == "/api/v1/dosbox/info":
            if request.headers.get("authorization") != f"Bearer {require_token}":
                return httpx.Response(401, json={"error": "unauthorized"})
            return httpx.Response(200, json=info)
        return httpx.Response(404, json={"error": "not found"})
    return httpx.MockTransport(handler)


def _connectable(info, token=TOKEN, hello=None, protocol_pin=None):
    config = Config(base_url="http://127.0.0.1:8386", token=token,
                    protocol=protocol_pin)
    return Connection(config, transport=_routes(info=info, hello=hello))


def test_starts_disconnected():
    conn = _make_conn()
    assert not conn.connected
    assert conn.features == {}


def test_no_token_raises_not_connected():
    conn = _make_conn(token=None)
    with pytest.raises(NotConnected, match="No API token"):
        conn.ensure_connected()


def test_connected_with_features():
    conn = _make_conn(token="0" * 64, features={"memory": True, "freeze": True})
    assert conn.connected
    assert conn.features["memory"] is True


def test_detach_clears_state():
    conn = _make_conn(token="0" * 64, features={"memory": True})
    assert conn.connected
    conn.detach()
    assert not conn.connected
    assert conn.features == {}


def test_guard_returns_error_when_not_connected():
    conn = _make_conn()

    def handler(args):
        return [types.TextContent(type="text", text="ok")]

    guarded = guard(conn, handler)
    result = guarded({})
    assert len(result) == 1
    assert "No API token" in result[0].text


def test_guard_returns_error_when_feature_disabled():
    conn = _make_conn(token="0" * 64, features={"memory": True, "freeze": False})

    def handler(args):
        return [types.TextContent(type="text", text="ok")]

    guarded = guard(conn, handler, feature="freeze")
    result = guarded({})
    assert len(result) == 1
    assert "not enabled" in result[0].text


def test_guard_passes_through_when_feature_enabled():
    conn = _make_conn(token="0" * 64, features={"memory": True})

    def handler(args):
        return [types.TextContent(type="text", text="ok")]

    guarded = guard(conn, handler, feature="memory")
    result = guarded({})
    assert result[0].text == "ok"


def test_guard_passes_through_when_no_feature_gate():
    conn = _make_conn(token="0" * 64, features={})

    def handler(args):
        return [types.TextContent(type="text", text="ok")]

    guarded = guard(conn, handler, feature=None)
    result = guarded({})
    assert result[0].text == "ok"


class TestVersionNegotiation:
    def test_connect_computes_effective_version(self):
        conn = _connectable({"version": "0.84-da3", "features": {"memory": True},
                             "mcp_protocol": "1.0"})
        conn.ensure_connected()
        assert conn.effective_protocol == "1.0"
        assert conn.engine_info["version"] == "0.84-da3"

    def test_legacy_info_without_advertisement_is_implicit_1_0(self):
        conn = _connectable({"version": "0.84-da2", "features": {"memory": True}})
        conn.ensure_connected()
        assert conn.effective_protocol == "1.0"

    def test_non_peer_rejected(self):
        conn = _connectable({"version": "not ours"})
        with pytest.raises(NotConnected, match="protocol peer"):
            conn.ensure_connected()

    def test_major_mismatch_rejected(self):
        conn = _connectable({"features": {}, "mcp_protocol": "99.0"})
        with pytest.raises(NotConnected, match="major"):
            conn.ensure_connected()

    def test_bad_pin_reported(self):
        conn = _connectable({"features": {}, "mcp_protocol": "1.0"},
                            protocol_pin="99.9")
        with pytest.raises(NotConnected, match="pin"):
            conn.ensure_connected()


class TestNoTokenDiagnostics:
    def test_hello_makes_the_error_precise(self):
        conn = _connectable(
            {"features": {}},
            token=None,
            hello={"name": "dosbox-automation", "version": "0.84-da3",
                   "mcp_protocol": "1.0"},
        )
        with pytest.raises(NotConnected, match="0.84-da3") as exc:
            conn.ensure_connected()
        assert "token" in str(exc.value).lower()

    def test_listener_without_hello_still_mentions_token(self):
        conn = _connectable({"features": {}}, token=None)
        with pytest.raises(NotConnected, match="token"):
            conn.ensure_connected()

    def test_nothing_listening_keeps_the_generic_message(self):
        conn = _make_conn(token=None)
        with pytest.raises(NotConnected, match="No API token"):
            conn.ensure_connected()


class TestStatus:
    def test_status_when_connected(self):
        conn = _connectable({"version": "0.84-da3", "features": {"memory": True},
                             "mcp_protocol": "1.0"})
        conn.ensure_connected()
        status = conn.status()
        assert status["connected"] is True
        assert status["engine_version"] == "0.84-da3"
        assert status["protocol"] == "1.0"
        assert status["features"] == {"memory": True}
        assert status["token"] == "present"

    def test_status_when_disconnected(self):
        conn = _make_conn()
        status = conn.status()
        assert status["connected"] is False
        assert status["token"] == "absent"

    def test_status_never_contains_the_token_value(self):
        conn = _connectable({"features": {}, "mcp_protocol": "1.0"})
        conn.ensure_connected()
        assert TOKEN not in repr(conn.status())


def test_script_run_loads_the_source_through_a_real_connection():
    from dosbox_mcp.tools.script import _script_run

    seen = []

    def engine(request):
        seen.append((request.method, request.url.path,
                     request.headers.get("content-type"), request.content))
        return httpx.Response(200, json={"status": "ok"})

    conn = _make_conn(token=TOKEN, features={})
    conn._client = DosboxClient("http://127.0.0.1:8386", TOKEN,
                                transport=httpx.MockTransport(engine))
    _script_run(conn, {"script": "dosbox.output.v = 1"})
    assert seen[0][:3] == ("POST", "/api/v1/script/load", "text/plain")
    assert seen[0][3] == b"dosbox.output.v = 1"
    assert seen[1][:2] == ("POST", "/api/v1/script/start")

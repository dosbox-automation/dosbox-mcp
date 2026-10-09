# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import asyncio
import types

import pytest

from dosbox_mcp.connection import Connection
from dosbox_mcp.config import Config
from dosbox_mcp.server import build_server
from dosbox_mcp.tools.memory import _mem_read, _mem_write


def _make_conn():
    config = Config(base_url="http://127.0.0.1:8386", token=None)
    return Connection(config)


def _build(mode="full"):
    return build_server(_make_conn(), mode=mode)


def test_always_on_tools_present():
    server = _build()
    names = server.registered_tool_names()
    assert "dosbox_status" in names
    assert "screen_text" in names
    assert "script_run" in names
    assert "video_capture_status" in names


def test_all_tools_registered_regardless_of_features():
    server = _build()
    names = server.registered_tool_names()
    assert "mem_read" in names
    assert "mem_write" in names
    assert "input_type" in names
    assert "input_key" in names
    assert "mem_search" in names
    assert "dos_memory_map" in names
    assert "freeze_set" in names
    assert "freeze_list" in names
    assert "freeze_clear" in names
    assert "port_read" in names
    assert "port_write" in names
    assert "cpu_write_register" in names
    for t in ("debug_status", "debug_pause", "debug_continue", "debug_step"):
        assert t in names


class TestCapabilityModes:
    """The mode is the operator's constraint on the agent, gated at
    registration: a tool outside the mode does not exist for the client."""

    def test_observe_registers_only_read_only_tools(self):
        names = _build(mode="observe").registered_tool_names()
        assert "screen_text" in names
        assert "mem_read" in names
        assert "dosbox_status" in names
        assert "mem_write" not in names
        assert "input_key" not in names
        assert "script_run" not in names
        assert "drive_swap" not in names
        assert "port_write" not in names

    def test_interact_adds_input_media_script_but_not_surgery(self):
        names = _build(mode="interact").registered_tool_names()
        assert "input_key" in names
        assert "input_type" in names
        assert "script_run" in names
        assert "video_capture_start" in names
        assert "mem_write" not in names
        assert "freeze_set" not in names
        assert "port_write" not in names
        assert "cpu_write_register" not in names

    def test_full_registers_everything(self):
        names = _build(mode="full").registered_tool_names()
        assert "mem_write" in names
        assert "port_write" in names
        assert "freeze_set" in names

    def test_unknown_mode_rejected(self):
        import pytest
        with pytest.raises(ValueError, match="mode"):
            _build(mode="root")


# ---------------------------------------------------------------------------
# Tool handlers must build the right REST calls. The registration tests
# above cannot catch a wrong route or missing Accept header; these do
# (aug-df86: mem_read hit the wrong route and got binary back).
# ---------------------------------------------------------------------------


class _FakeClient:
    def __init__(self):
        self.calls = []

    def get(self, path, params=None, headers=None):
        self.calls.append(("get", path, params, headers))
        return {"memory": {"data": "3q2+7w==", "addr": 4660}, "registers": {}}

    def put(self, path, json=None):
        self.calls.append(("put", path, json))
        return {"status": "ok"}


def test_mem_read_uses_linear_offset_route_and_json_accept():
    client = _FakeClient()
    result = _mem_read(client, {"offset": 0x1234, "length": 100})

    method, path, params, headers = client.calls[0]
    assert method == "get"
    # Linear offset and length in the path, nothing split into segments
    assert path == "/api/v1/memory/4660/100"
    # JSON (base64 payload) is selected by the Accept header
    assert headers == {"accept": "application/json"}
    # The base64 data must survive into the tool output
    assert "3q2+7w==" in result[0].text


def test_mem_write_uses_single_offset_route():
    client = _FakeClient()
    _mem_write(client, {"offset": 0x1234, "data": "AAECAw=="})

    method, path, body = client.calls[0]
    assert method == "put"
    assert path == "/api/v1/memory/4660"
    assert body == {"data": "AAECAw=="}


def test_session_info_registered():
    server = _build()
    assert "session_info" in server.registered_tool_names()


def test_session_info_never_reveals_the_token_value(monkeypatch, tmp_path):
    # Self-audit 2026-07-17: the bearer token must not enter transcripts.
    # session_info reports presence and where a human finds it, nothing more.
    from dosbox_mcp.tools.session import _session_info

    monkeypatch.setenv("DOSBOX_API_TOKEN", "a" * 64)

    class _FakeConn:
        base_url = "http://127.0.0.1:8386"

    result = _session_info(_FakeConn())
    import json as _json
    info = _json.loads(result[0].text)
    assert info["base_url"] == "http://127.0.0.1:8386"
    assert info["token"] == "present"
    assert "a" * 64 not in result[0].text


def test_session_info_without_token(monkeypatch, tmp_path):
    from dosbox_mcp.tools.session import _session_info

    monkeypatch.delenv("DOSBOX_API_TOKEN", raising=False)
    # Point the token file lookup at an empty directory
    monkeypatch.setenv("DOSBOX_TOKEN_FILE", str(tmp_path / "no_token"))

    class _FakeConn:
        base_url = "http://127.0.0.1:8386"

    result = _session_info(_FakeConn())
    import json as _json
    info = _json.loads(result[0].text)
    assert info["token"] == "absent"
    assert "note" in info


def test_script_run_sends_lua_as_text_not_json():
    # aug-bt7n: script/load wants a text/plain body; the old JSON post
    # 415'd. Verify the handler uses post_text with the raw source.
    from dosbox_mcp.tools.script import _script_run

    class _FakeClient:
        def __init__(self):
            self.text_calls = []
            self.json_calls = []

        def post_text(self, path, text, content_type="text/plain", params=None):
            self.text_calls.append((path, text, content_type))
            return {"status": "loaded"}

        def post(self, path, json=None):
            self.json_calls.append((path, json))
            return {"status": "running"}

    client = _FakeClient()
    _script_run(client, {"script": "dosbox.log('hi')"})

    # The script goes through post_text as raw source, not post(json=)
    assert len(client.text_calls) == 1
    path, text, ctype = client.text_calls[0]
    assert path == "/api/v1/script/load"
    assert text == "dosbox.log('hi')"
    assert ctype == "text/plain"
    # start is a plain POST with no body
    assert client.json_calls == [("/api/v1/script/start", None)]


class _StatusClient:
    def get(self, path, params=None, headers=None):
        if path == "/api/v1/status":
            return {"running": True, "archive": {
                "activity": "materializing", "archive": "doom",
                "bytes_done": 4096, "bytes_total": 12408292}}
        return {}


def _status_tool():
    from dosbox_mcp.tools import session
    tools = {}

    def add_tool(name, description, schema, handler, read_only=False, **kwargs):
        tools[name] = (description, handler)

    session.register(None, _StatusClient(), add_tool)
    return tools["dosbox_status"]


def test_status_names_and_passes_the_archive_preparation():
    import json
    description, handler = _status_tool()
    assert "status.archive" in description
    out = json.loads(handler({})[0].text)
    assert out["status"]["archive"] == {
        "activity": "materializing", "archive": "doom",
        "bytes_done": 4096, "bytes_total": 12408292}


# ---------------------------------------------------------------------------
# What an agent sees on the wire, through an in-process client (issue #1:
# mcp 2.x moved handler registration and dropped the tool-call wrapper).
# ---------------------------------------------------------------------------


class _FakeManager:
    running = False
    pid = None

    def __init__(self, logs_error=None):
        self._logs_error = logs_error

    def logs(self, n):
        if self._logs_error:
            raise self._logs_error
        return ["line one", "line two"]


def _over_the_wire(server, request, mode):
    from mcp import Client

    async def run():
        async with Client(server, mode=mode) as client:
            return await request(client)
    return asyncio.run(run())


def _wire_server(mode="full", logs_error=None):
    return build_server(_make_conn(), mode=mode,
                        manager=_FakeManager(logs_error=logs_error))


# stdio clients take the legacy handshake; the in-process default is the
# 2026-07-28 era, which skips initialize and the JSON-RPC framing.
@pytest.fixture(params=["legacy", "auto"])
def wire_mode(request):
    return request.param


def _inject_tool(monkeypatch, schema, handler):
    def register(server, conn, add):
        add(name="injected", description="Injected.", schema=schema,
            handler=handler, needs_connection=False)
    monkeypatch.setattr("dosbox_mcp.server.script",
                        types.SimpleNamespace(register=register))


def test_tools_list_serves_exactly_the_registered_tools(wire_mode):
    server = _wire_server(mode="observe")
    result = _over_the_wire(server, lambda c: c.list_tools(), wire_mode)
    assert {t.name for t in result.tools} == server.registered_tool_names()


def test_tools_call_returns_the_handler_content(wire_mode):
    result = _over_the_wire(_wire_server(),
                            lambda c: c.call_tool("bridge_logs", {"n": 2}),
                            wire_mode)
    assert result.is_error is False
    assert "line one\nline two" in result.content[0].text


def test_tools_call_without_arguments_reaches_the_handler(wire_mode):
    result = _over_the_wire(_wire_server(),
                            lambda c: c.call_tool("bridge_logs"), wire_mode)
    assert result.is_error is False
    assert "line one\nline two" in result.content[0].text


def test_tools_call_rejects_arguments_that_break_the_schema(wire_mode):
    server = _wire_server(logs_error=AssertionError("handler reached"))
    result = _over_the_wire(server,
                            lambda c: c.call_tool("bridge_logs", {"n": "ten"}),
                            wire_mode)
    assert result.is_error is True
    assert result.content[0].text.startswith("Input validation error")


def test_tools_call_reports_a_failing_handler_as_a_tool_error(wire_mode):
    server = _wire_server(logs_error=RuntimeError("pipe closed"))
    result = _over_the_wire(server, lambda c: c.call_tool("bridge_logs", {}),
                            wire_mode)
    assert result.is_error is True
    assert result.content[0].text == "pipe closed"


def test_tools_call_reports_a_malformed_handler_result_as_a_tool_error(
        monkeypatch, wire_mode):
    _inject_tool(monkeypatch, {"type": "object", "properties": {}},
                 lambda args: ["not a content block"])
    result = _over_the_wire(_wire_server(),
                            lambda c: c.call_tool("injected", {}), wire_mode)
    assert result.is_error is True


def test_tools_call_reports_an_unknown_tool_as_a_tool_error(wire_mode):
    result = _over_the_wire(_wire_server(),
                            lambda c: c.call_tool("no_such_tool", {}),
                            wire_mode)
    assert result.is_error is True
    assert result.content[0].text == "unknown tool: no_such_tool"


def test_tools_call_cannot_reach_a_tool_outside_the_mode(wire_mode):
    result = _over_the_wire(_wire_server(mode="observe"),
                            lambda c: c.call_tool("mem_write", {"offset": 0, "data": "AA=="}),
                            wire_mode)
    assert result.is_error is True
    assert result.content[0].text == "unknown tool: mem_write"


def test_build_refuses_a_tool_with_an_invalid_schema(monkeypatch):
    _inject_tool(monkeypatch, {"type": "integer!"}, lambda args: [])
    with pytest.raises(ValueError, match="injected"):
        _wire_server()


def test_server_reports_its_own_version(wire_mode):
    from importlib.metadata import version

    async def server_info(client):
        return client.server_info
    info = _over_the_wire(_wire_server(), server_info, wire_mode)
    assert info.version == version("dosbox-mcp")

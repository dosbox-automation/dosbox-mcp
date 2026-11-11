# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import json

import pytest

from dosbox_mcp.config import Config
from dosbox_mcp.connection import Connection, NotConnected
from dosbox_mcp.lifecycle import LifecycleError, SpawnError
from dosbox_mcp.protocol import BRIDGE_PROTOCOL
from dosbox_mcp.server import build_server
from dosbox_mcp.tools.bridge import (
    _connect,
    _help,
    _logs,
    _setup,
    _start,
    _status,
    _stop,
    _swagger,
    _version,
)
from tests.wire import over_the_wire, wire_server


class FakeConn:
    def __init__(self, connected=True, fail_with=None):
        self._connected = connected
        self._fail_with = fail_with
        self.detached = 0
        self.spec = {"paths": {}}

    def status(self):
        return {"connected": self._connected, "base_url": "http://127.0.0.1:8386",
                "protocol": "1.0" if self._connected else None,
                "token": "present"}

    def ensure_connected(self):
        if self._fail_with:
            raise NotConnected(self._fail_with)
        self._connected = True

    def detach(self):
        self.detached += 1
        self._connected = False

    def get(self, path, **kwargs):
        assert path == "/openapi.json"
        return self.spec


class FakeManager:
    def __init__(self, running=False):
        self._running = running
        self.calls = []
        self._logs = ["fake engine started", "MOUNT_POLICY: x"]

    @property
    def running(self):
        return self._running

    @property
    def pid(self):
        return 4242 if self._running else None

    def start(self, token_deadline=30.0):
        self.calls.append("start")
        if self._running:
            raise LifecycleError("an instance is already managed")
        self._running = True
        return {"version": "0.84-test", "features": {}}

    def stop(self):
        self.calls.append("stop")
        if not self._running:
            raise LifecycleError("no managed instance to stop")
        self._running = False

    def logs(self, n=None):
        if not self.calls:
            raise LifecycleError("no output captured")
        return self._logs if n is None else self._logs[-n:]


def _text(result):
    assert len(result) == 1
    return result[0].text


class TestVersionStatusHelp:
    def test_version_reports_bridge_and_protocol(self):
        payload = json.loads(_text(_version()))
        assert payload["protocol"] == BRIDGE_PROTOCOL
        assert "version" in payload

    def test_status_works_while_disconnected(self):
        conn = FakeConn(connected=False)
        manager = FakeManager()
        payload = json.loads(_text(_status(conn, manager, "observe")))
        assert payload["connected"] is False
        assert payload["mode"] == "observe"
        assert payload["managed_instance"] == {"running": False, "pid": None}

    def test_status_shows_managed_pid(self):
        payload = json.loads(_text(_status(FakeConn(), FakeManager(running=True),
                                           "full")))
        assert payload["managed_instance"] == {"running": True, "pid": 4242}

    def test_help_lists_tools_with_one_liners(self):
        tools = [("bridge_status", "Bridge and connection state."),
                 ("screen_text", "Read the text screen.")]
        text = _text(_help(FakeConn(), FakeManager(), "full", lambda: tools))
        assert "bridge_status" in text
        assert "Bridge and connection state." in text
        assert "screen_text" in text
        assert BRIDGE_PROTOCOL in text


class TestConnectDisconnect:
    def test_connect_returns_status_on_success(self):
        conn = FakeConn(connected=False)
        payload = json.loads(_text(_connect(conn, FakeManager(), "full")))
        assert payload["connected"] is True
        assert conn.detached == 1

    def test_connect_reports_precise_failure(self):
        conn = FakeConn(fail_with="Instance found at X but no usable token")
        text = _text(_connect(conn, FakeManager(), "full"))
        assert "no usable token" in text


class TestStartStop:
    def test_start_spawns_and_reports(self):
        manager = FakeManager()
        text = _text(_start(FakeConn(), manager))
        assert manager.calls == ["start"]
        assert "0.84-test" in text

    def test_start_error_text_when_already_running(self):
        manager = FakeManager(running=True)
        text = _text(_start(FakeConn(), manager))
        assert "already managed" in text

    def test_start_reports_spawn_failure(self):
        manager = FakeManager()

        def boom(token_deadline=30.0):
            raise SpawnError("engine produced no token within 30.0s")
        manager.start = boom
        text = _text(_start(FakeConn(), manager))
        assert "no token within" in text

    def test_stop_stops_and_detaches(self):
        conn = FakeConn()
        manager = FakeManager(running=True)
        manager.calls.append("start")
        text = _text(_stop(conn, manager))
        assert "stop" in manager.calls
        assert conn.detached == 1
        assert "stopped" in text.lower()

    def test_stop_refusal_passes_through(self):
        text = _text(_stop(FakeConn(), FakeManager(running=False)))
        assert "no managed instance" in text


class TestLogs:
    def test_logs_framed_as_untrusted(self):
        manager = FakeManager(running=True)
        manager.calls.append("start")
        text = _text(_logs(manager, {}))
        assert "fake engine started" in text
        assert "untrusted" in text.lower()

    def test_logs_error_passes_through(self):
        text = _text(_logs(FakeManager(), {}))
        assert "no output captured" in text


class TestSetup:
    def test_setup_writes_safe_keys(self, tmp_path, monkeypatch):
        path = tmp_path / "config.toml"
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(path))
        text = _text(_setup({"headless": True, "protocol": "1.0"}))
        assert "saved" in text.lower()
        content = path.read_text(encoding="utf-8")
        assert 'protocol = "1.0"' in content
        assert "headless = true" in content

    @pytest.mark.parametrize("args", [
        {"binary": "/some/other/binary"},
        {"mode": "full"},
        {"port": 6000},
    ])
    def test_setup_rejects_protected_keys(self, args, tmp_path, monkeypatch):
        path = tmp_path / "config.toml"
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(path))
        text = _text(_setup(args))
        assert "human-edited" in text
        assert not path.exists()

    def test_setup_rejects_bad_values(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(tmp_path / "c.toml"))
        text = _text(_setup({"protocol": "one"}))
        assert "major.minor" in text

    def test_setup_refuses_the_token_file(self, tmp_path, monkeypatch):
        path = tmp_path / "config.toml"
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(path))
        text = _text(_setup({"token_file": "~/.git-credentials"}))
        assert "human-edited" in text
        assert not path.exists()

    def test_setup_schema_refuses_keys_beyond_the_safe_two(self, tmp_path,
                                                            monkeypatch, wire_mode):
        path = tmp_path / "config.toml"
        monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(path))
        result = over_the_wire(
            wire_server(),
            lambda c: c.call_tool("bridge_setup", {"token_file": "~/.git-credentials",
                                                   "port": 22}),
            wire_mode)
        assert result.is_error is True
        assert result.content[0].text.startswith("Input validation error")
        assert not path.exists()


class TestSwagger:
    def test_digest_counts_and_flags_unknown_routes(self):
        conn = FakeConn()
        conn.spec = {"paths": {
            "/api/v1/status": {},
            "/api/v1/memory/{offset}/{length}": {},
            "/api/v1/teleporter/engage": {},
        }}
        payload = json.loads(_text(_swagger(conn)))
        assert payload["routes"] == 3
        assert "/api/v1/teleporter/engage" in payload["unknown_to_protocol"]
        assert "/api/v1/status" not in payload["unknown_to_protocol"]


class TestRegistration:
    def _names(self, mode):
        config = Config(base_url="http://127.0.0.1:8386", token=None)
        return build_server(Connection(config), mode=mode).registered_tool_names()

    def test_full_registers_all_bridge_tools(self):
        names = self._names("full")
        for tool in ("bridge_version", "bridge_status", "bridge_help",
                     "bridge_connect", "bridge_disconnect", "bridge_start",
                     "bridge_stop", "bridge_logs", "bridge_setup",
                     "bridge_swagger"):
            assert tool in names, tool

    def test_observe_gets_read_only_bridge_tools_only(self):
        names = self._names("observe")
        for tool in ("bridge_version", "bridge_status", "bridge_help",
                     "bridge_logs", "bridge_swagger"):
            assert tool in names, tool
        for tool in ("bridge_start", "bridge_stop", "bridge_setup"):
            assert tool not in names, tool

    def test_interact_includes_lifecycle(self):
        names = self._names("interact")
        for tool in ("bridge_start", "bridge_stop", "bridge_connect",
                     "bridge_setup"):
            assert tool in names, tool

    def test_no_bridge_token_tool_exists(self):
        # Design rule: the token never enters a transcript.
        assert "bridge_token" not in self._names("full")

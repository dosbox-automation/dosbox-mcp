# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import json

import pytest

from dosbox_mcp.client import EngineBusy
from dosbox_mcp.tools.media import (
    _audio_capture_start,
    _capture_start,
    _capture_stop,
    _compression_get,
    _compression_set,
)
from dosbox_mcp.tools.screen import _screen_capture
from tests.wire import over_the_wire, wire_server


class _FakeClient:
    def __init__(self, status=None, status_error=None, stop_error=None, start_answer=None):
        self.calls = []
        self.status = status or {}
        self.status_error = status_error
        self.stop_error = stop_error
        self.start_answer = start_answer

    def get(self, path, params=None, headers=None):
        self.calls.append(("get", path, params))
        if path.endswith("/frame"):
            return b"\x89PNG"
        if path.endswith("/compression"):
            return {"raw": 9, "rendered": 6}
        if self.status_error:
            raise self.status_error
        return self.status

    def post(self, path, json=None):
        self.calls.append(("post", path, json))
        if path.endswith("/stop"):
            if self.stop_error:
                raise self.stop_error
            return {"status": "stopped"}
        if self.start_answer is not None:
            return self.start_answer
        return {"status": "recording", "mode": (json or {}).get("mode", "raw")}

    def put(self, path, json=None):
        self.calls.append(("put", path, json))
        return {"raw": 9, **(json or {})}


def _schema(name):
    result = over_the_wire(wire_server(), lambda c: c.list_tools(), "auto")
    return next(t.input_schema for t in result.tools if t.name == name)


def test_video_start_without_mode_sends_no_body():
    client = _FakeClient()
    _capture_start(client, {})
    assert client.calls == [("post", "/api/v1/capture/video/start", None)]


def test_video_start_rendered_sends_the_mode():
    client = _FakeClient()
    result = _capture_start(client, {"mode": "rendered"})
    assert client.calls == [("post", "/api/v1/capture/video/start", {"mode": "rendered"})]
    assert json.loads(result[0].text)["mode"] == "rendered"


def test_video_start_schema_offers_raw_and_rendered():
    assert _schema("video_capture_start")["properties"]["mode"]["enum"] == ["raw", "rendered"]


def test_video_start_rejects_an_unknown_mode_before_the_engine(wire_mode):
    result = over_the_wire(
        wire_server(),
        lambda c: c.call_tool("video_capture_start", {"mode": "crt"}),
        wire_mode)
    assert result.is_error is True
    assert result.content[0].text.startswith("Input validation error")


def test_video_stop_reports_the_mode_and_why_it_ended():
    client = _FakeClient(status={"capturing": False, "mode": "rendered",
                                 "last_stop_reason": "clean"})
    result = json.loads(_capture_stop(client, {})[0].text)
    assert client.calls == [("post", "/api/v1/capture/video/stop", None),
                            ("get", "/api/v1/capture/video/status", None)]
    assert result == {"status": "stopped", "mode": "rendered",
                      "last_stop_reason": "clean"}


def test_video_stop_survives_a_failed_status_read():
    client = _FakeClient(status_error=RuntimeError("503: Emulation busy, retry later"))
    result = json.loads(_capture_stop(client, {})[0].text)
    assert result == {"status": "stopped", "mode": "unknown", "last_stop_reason": "unknown"}


def test_a_failed_stop_carries_the_last_stop_reason():
    client = _FakeClient(status={"capturing": False, "mode": "raw",
                                 "last_stop_reason": "disk_space_low"},
                         stop_error=RuntimeError("500: write failed"))
    with pytest.raises(RuntimeError, match="disk_space_low"):
        _capture_stop(client, {})


def test_video_start_refuses_an_engine_that_ignores_the_mode():
    client = _FakeClient(start_answer={"status": "recording"})
    with pytest.raises(RuntimeError, match="raw recording, not rendered.*does not know capture modes"):
        _capture_start(client, {"mode": "rendered"})


def test_video_start_names_another_mode_the_engine_chose():
    client = _FakeClient(start_answer={"status": "recording", "mode": "raw"})
    with pytest.raises(RuntimeError, match="raw recording, not rendered") as raised:
        _capture_start(client, {"mode": "rendered"})
    assert "does not know capture modes" not in str(raised.value)


def test_a_stop_on_a_busy_engine_does_not_wait_again_for_the_status():
    client = _FakeClient(stop_error=EngineBusy("503: Emulation busy, retry later"))
    with pytest.raises(RuntimeError, match="last_stop_reason: unknown"):
        _capture_stop(client, {})
    assert client.calls == [("post", "/api/v1/capture/video/stop", None)]


def test_a_stop_answered_503_without_busy_still_reads_the_reason():
    client = _FakeClient(status={"capturing": False, "mode": "raw", "last_stop_reason": "clean"},
                         stop_error=RuntimeError("503: Service unavailable"))
    with pytest.raises(RuntimeError, match="last_stop_reason: clean"):
        _capture_stop(client, {})


def test_audio_start_offers_no_host_path():
    # The engine writes a given path wherever the client says and truncates
    # what is there; recordings from an agent go to the capture folder.
    schema = _schema("audio_capture_start")
    assert "path" not in schema.get("properties", {})
    assert schema.get("additionalProperties") is False


def test_audio_start_with_a_path_is_refused_before_the_engine(wire_mode):
    result = over_the_wire(
        wire_server(),
        lambda c: c.call_tool("audio_capture_start", {"path": "/home/x/.bashrc"}),
        wire_mode)
    assert result.is_error is True
    assert result.content[0].text.startswith("Input validation error")


def test_audio_start_never_sends_a_path():
    client = _FakeClient()
    _audio_capture_start(client, {"path": "/home/x/.bashrc"})
    assert client.calls == [("post", "/api/v1/capture/audio/start", None)]


def test_screen_capture_defaults_to_the_raw_frame():
    client = _FakeClient()
    _screen_capture(client, {})
    assert client.calls == [("get", "/api/v1/video/frame", {"format": "png"})]


def test_screen_capture_rendered_passes_the_mode():
    client = _FakeClient()
    _screen_capture(client, {"mode": "rendered"})
    assert client.calls == [("get", "/api/v1/video/frame",
                             {"format": "png", "mode": "rendered"})]


def test_screen_capture_schema_offers_raw_and_rendered():
    assert _schema("screen_capture")["properties"]["mode"]["enum"] == ["raw", "rendered"]


def test_compression_get_reads_both_levels():
    client = _FakeClient()
    result = json.loads(_compression_get(client, {})[0].text)
    assert client.calls == [("get", "/api/v1/capture/video/compression", None)]
    assert result == {"raw": 9, "rendered": 6}


def test_compression_set_sends_only_the_given_levels():
    client = _FakeClient()
    _compression_set(client, {"rendered": 5})
    assert client.calls == [("put", "/api/v1/capture/video/compression", {"rendered": 5})]


def test_compression_set_refuses_no_level_and_out_of_range(wire_mode):
    server = wire_server()
    for args in ({}, {"raw": 10}, {"rendered": -1}):
        result = over_the_wire(
            server, lambda c, a=args: c.call_tool("video_capture_compression_set", a),
            wire_mode)
        assert result.is_error is True, args
        assert result.content[0].text.startswith("Input validation error"), args

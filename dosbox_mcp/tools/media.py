# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import json

import httpx

from dosbox_mcp.client import EngineBusy
from dosbox_mcp.connection import NotConnected

_CALL_ERRORS = (RuntimeError, NotConnected, httpx.HTTPError)


def register(server, client, add_tool, feature=None):
    add_tool(
        name="video_capture_start",
        description=(
            "Start ZMBV video recording (AVI with sound) into the engine's capture "
            "directory. mode raw (default): the video adapter's frames at their "
            "own size, no window needed. mode rendered: what the window shows, "
            "after shader and scaling. A start while one runs is an error."
        ),
        read_only=False,
        schema={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["raw", "rendered"],
                    "description": "raw (default) or rendered",
                },
            },
        },
        handler=lambda args: _capture_start(client, args),
    )

    add_tool(
        name="video_capture_stop",
        description="Stop ZMBV video recording; reports the mode and why it ended.",
        read_only=False,
        schema={"type": "object", "properties": {}},
        handler=lambda args: _capture_stop(client, args),
    )

    add_tool(
        name="video_capture_compression",
        description="Zlib levels (0-9) for raw and rendered video capture.",
        read_only=True,
        schema={"type": "object", "properties": {}},
        handler=lambda args: _compression_get(client, args),
    )

    add_tool(
        name="video_capture_compression_set",
        description=(
            "Set the zlib level (0-9) for raw and/or rendered video capture. "
            "Applies to the next start; refused while recording."
        ),
        read_only=False,
        schema={
            "type": "object",
            "properties": {
                "raw": {"type": "integer", "minimum": 0, "maximum": 9},
                "rendered": {"type": "integer", "minimum": 0, "maximum": 9},
            },
            "minProperties": 1,
            "additionalProperties": False,
        },
        handler=lambda args: _compression_set(client, args),
    )

    add_tool(
        name="video_capture_status",
        description="Check whether a video capture is in progress.",
        read_only=True,
        schema={"type": "object", "properties": {}},
        handler=lambda args: _capture_status(client),
    )

    add_tool(
        name="audio_capture_start",
        description="Start WAV audio capture of the mixer output.",
        read_only=False,
        schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Output file path (optional, auto-numbered if omitted)",
                },
            },
        },
        handler=lambda args: _audio_capture_start(client, args),
    )

    add_tool(
        name="audio_capture_stop",
        description="Stop WAV audio capture.",
        read_only=False,
        schema={"type": "object", "properties": {}},
        handler=lambda args: _audio_capture_stop(client),
    )

    add_tool(
        name="audio_capture_status",
        description="Check whether an audio capture is in progress.",
        read_only=True,
        schema={"type": "object", "properties": {}},
        handler=lambda args: _audio_capture_status(client),
    )


def _capture_start(client, args):
    import mcp.types as types
    wanted = args.get("mode")
    body = {"mode": wanted} if wanted else None
    result = client.post("/api/v1/capture/video/start", json=body)
    # An engine older than capture modes ignores the body and answers without one.
    started = result.get("mode", "raw")
    if wanted and started != wanted:
        cause = ("it does not know capture modes" if "mode" not in result
                 else "it chose that mode")
        raise RuntimeError(f"the engine started a {started} recording, not {wanted}; "
                           f"{cause}. The recording runs: stop it with video_capture_stop")
    return [types.TextContent(type="text", text=json.dumps(result))]


def _capture_status_or_none(client):
    try:
        return client.get("/api/v1/capture/video/status")
    except _CALL_ERRORS:
        return None


def _capture_stop(client, args):
    import mcp.types as types
    try:
        result = client.post("/api/v1/capture/video/stop")
    except _CALL_ERRORS as stop_error:
        # A busy engine already cost the whole busy deadline; asking it again waits as long.
        busy = isinstance(stop_error, EngineBusy)
        status = {} if busy else (_capture_status_or_none(client) or {})
        reason = status.get("last_stop_reason", "unknown")
        raise RuntimeError(f"{stop_error}; last_stop_reason: {reason}") from stop_error
    status = _capture_status_or_none(client) or {}
    result["mode"] = status.get("mode", "unknown")
    result["last_stop_reason"] = status.get("last_stop_reason", "unknown")
    return [types.TextContent(type="text", text=json.dumps(result))]


def _compression_get(client, args):
    import mcp.types as types
    result = client.get("/api/v1/capture/video/compression")
    return [types.TextContent(type="text", text=json.dumps(result))]


def _compression_set(client, args):
    import mcp.types as types
    body = {k: args[k] for k in ("raw", "rendered") if k in args}
    result = client.put("/api/v1/capture/video/compression", json=body)
    return [types.TextContent(type="text", text=json.dumps(result))]


def _capture_status(client):
    import mcp.types as types
    result = client.get("/api/v1/capture/video/status")
    return [types.TextContent(type="text", text=json.dumps(result))]


def _audio_capture_start(client, args):
    import mcp.types as types
    body = {}
    if args.get("path"):
        body["path"] = args["path"]
    result = client.post("/api/v1/capture/audio/start", json=body if body else None)
    return [types.TextContent(type="text", text=json.dumps(result))]


def _audio_capture_stop(client):
    import mcp.types as types
    result = client.post("/api/v1/capture/audio/stop")
    return [types.TextContent(type="text", text=json.dumps(result))]


def _audio_capture_status(client):
    import mcp.types as types
    result = client.get("/api/v1/capture/audio/status")
    return [types.TextContent(type="text", text=json.dumps(result))]

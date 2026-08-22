# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import json


def register(server, client, add_tool, feature=None):
    add_tool(
        name="video_capture_start",
        description="Start ZMBV video recording of the emulator screen.",
        read_only=False,
        schema={"type": "object", "properties": {}},
        handler=lambda args: _capture_start(client),
    )

    add_tool(
        name="video_capture_stop",
        description="Stop ZMBV video recording.",
        read_only=False,
        schema={"type": "object", "properties": {}},
        handler=lambda args: _capture_stop(client),
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


def _capture_start(client):
    import mcp.types as types
    result = client.post("/api/v1/capture/video/start")
    return [types.TextContent(type="text", text=json.dumps(result))]


def _capture_stop(client):
    import mcp.types as types
    result = client.post("/api/v1/capture/video/stop")
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

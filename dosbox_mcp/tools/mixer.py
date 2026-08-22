# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import json


def register(server, client, add_tool, feature=None):
    add_tool(
        name="mixer_status",
        description="Get mixer state: master volume, mute, all channels with volumes and sample rates.",
        read_only=True,
        schema={"type": "object", "properties": {}},
        handler=lambda args: _mixer_status(client),
    )

    add_tool(
        name="mixer_volume",
        description="Set the master mixer volume.",
        read_only=False,
        schema={
            "type": "object",
            "properties": {
                "left": {"type": "number", "description": "Left channel volume (0.0+)"},
                "right": {"type": "number", "description": "Right channel volume (0.0+)"},
            },
            "required": ["left", "right"],
        },
        handler=lambda args: _mixer_volume(client, args),
    )

    add_tool(
        name="mixer_mute",
        description="Mute the master mixer output.",
        read_only=False,
        schema={"type": "object", "properties": {}},
        handler=lambda args: _mixer_mute(client),
    )

    add_tool(
        name="mixer_unmute",
        description="Unmute the master mixer output.",
        read_only=False,
        schema={"type": "object", "properties": {}},
        handler=lambda args: _mixer_unmute(client),
    )

    add_tool(
        name="mixer_channel_volume",
        description="Set a mixer channel's user volume by name (SB, GUS, CDAUDIO, SPKR, etc.).",
        read_only=False,
        schema={
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel name"},
                "left": {"type": "number", "description": "Left volume (0.0+)"},
                "right": {"type": "number", "description": "Right volume (0.0+)"},
            },
            "required": ["channel", "left", "right"],
        },
        handler=lambda args: _mixer_channel_volume(client, args),
    )


def _mixer_status(client):
    import mcp.types as types
    result = client.get("/api/v1/mixer")
    return [types.TextContent(type="text", text=json.dumps(result))]


def _mixer_volume(client, args):
    import mcp.types as types
    body = {"left": args["left"], "right": args["right"]}
    result = client.put("/api/v1/mixer/volume", json=body)
    return [types.TextContent(type="text", text=json.dumps(result))]


def _mixer_mute(client):
    import mcp.types as types
    result = client.post("/api/v1/mixer/mute")
    return [types.TextContent(type="text", text=json.dumps(result))]


def _mixer_unmute(client):
    import mcp.types as types
    result = client.post("/api/v1/mixer/unmute")
    return [types.TextContent(type="text", text=json.dumps(result))]


def _mixer_channel_volume(client, args):
    import mcp.types as types
    channel = args["channel"]
    body = {"left": args["left"], "right": args["right"]}
    result = client.put(f"/api/v1/mixer/channel/{channel}", json=body)
    return [types.TextContent(type="text", text=json.dumps(result))]

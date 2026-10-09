# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import asyncio
import logging

import jsonschema
import mcp.server.stdio
from mcp.server.lowlevel import Server
import mcp.types as types

from .config import MODES, Config
from .connection import Connection, guard
from .lifecycle import InstanceManager
from .protocol import bridge_version
from .tools import bridge, session, screen, input as input_tools, memory, freeze, io, cpu, debug, media, mixer, script

logger = logging.getLogger(__name__)

# Groups whose non-read-only tools register under "interact" mode.
# Everything else non-read-only (memory surgery, port IO, cpu control,
# debugger, shutdown) needs "full".
_INTERACT_GROUPS = {"input", "media", "mixer", "script", "bridge"}


def _mode_allows(mode: str, read_only: bool, group: str) -> bool:
    if mode == "full":
        return True
    if read_only:
        return True
    if mode == "interact":
        return group in _INTERACT_GROUPS
    return False


def _make_attach(conn):
    """The spawn-identity check for bridge_start: authenticate against
    the child with the token from the config dir the manager created.
    A port squatter cannot pass this (self-audit 2026-07-17)."""
    def attach(base_url, token):
        conn.detach()
        conn.config.token = token
        conn.ensure_connected()
        return conn.engine_info
    return attach


def _tool_error(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)],
        is_error=True,
    )


def build_server(conn, mode: str = "full", manager=None):
    """Build the MCP server. `mode` is the operator's capability mode
    (observe / interact / full): tools outside the mode are not
    registered, so the client never sees them."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if manager is None:
        manager = InstanceManager(conn.config, attach=_make_attach(conn))

    registry = {}
    validators = {}

    async def list_tools(_ctx, _params):
        return types.ListToolsResult(tools=[tool for tool, _ in registry.values()])

    # mcp 1.x wrapped tool calls in schema validation and turned exceptions
    # into isError results; 2.x leaves both to the server.
    async def call_tool(_ctx, params):
        name = params.name
        arguments = params.arguments or {}
        if name not in registry:
            return _tool_error(f"unknown tool: {name}")
        _, handler = registry[name]
        error = jsonschema.exceptions.best_match(
            validators[name].iter_errors(arguments))
        if error is not None:
            return _tool_error(f"Input validation error: {error.message}")
        try:
            return types.CallToolResult(content=list(handler(arguments)))
        except Exception as e:
            logger.warning("tool %s failed: %s", name, e, exc_info=True)
            return _tool_error(str(e))

    server = Server("dosbox-mcp", version=bridge_version(),
                    on_list_tools=list_tools, on_call_tool=call_tool)

    def add_tool(name, description, schema, handler, read_only=False,
                 feature=None, group="session", needs_connection=True):
        if not _mode_allows(mode, read_only, group):
            return
        # Checked once here so a call can only fail validation, never on
        # the schema itself.
        validator_class = jsonschema.validators.validator_for(schema)
        try:
            validator_class.check_schema(schema)
        except jsonschema.SchemaError as e:
            raise ValueError(f"tool {name}: invalid input schema: {e.message}") from e
        validators[name] = validator_class(schema)
        # Bridge-internal tools skip the connection guard: most of them
        # must work while disconnected - that is their point.
        wrapped = (guard(conn, handler, feature=feature)
                   if needs_connection else handler)
        annotations = types.ToolAnnotations(readOnlyHint=read_only)
        registry[name] = (
            types.Tool(
                name=name,
                description=description,
                inputSchema=schema,
                annotations=annotations,
            ),
            wrapped,
        )

    def add_tool_for(group):
        def add(name, description, schema, handler, read_only=False,
                feature=None, needs_connection=True):
            add_tool(name, description, schema, handler,
                     read_only=read_only, feature=feature, group=group,
                     needs_connection=needs_connection)
        return add

    def get_tools():
        return [(name, tool.description.split(". ")[0].rstrip(".") + ".")
                for name, (tool, _) in registry.items()]

    for mod, group in ((session, "session"), (screen, "screen"),
                       (media, "media"), (mixer, "mixer"),
                       (script, "script")):
        mod.register(server, conn, add_tool_for(group))

    input_tools.register(server, conn, add_tool_for("input"), feature="input")
    memory.register(server, conn, add_tool_for("memory"), feature="memory")
    memory.register_search(server, conn, add_tool_for("memory"), feature="memory")
    freeze.register(server, conn, add_tool_for("freeze"), feature="freeze")
    io.register(server, conn, add_tool_for("port_io"), feature="port_io")
    cpu.register(server, conn, add_tool_for("cpu"), feature="cpu_control")
    debug.register(server, conn, add_tool_for("debug"), feature="debugger")
    bridge.register(server, conn, add_tool_for("bridge"),
                    manager=manager, mode=mode, get_tools=get_tools)

    def _registered_tool_names():
        return set(registry.keys())

    server.registered_tool_names = _registered_tool_names
    return server


async def _run():
    config = Config.load()
    conn = Connection(config)
    server = build_server(conn, mode=config.mode)
    async with mcp.server.stdio.stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    asyncio.run(_run())

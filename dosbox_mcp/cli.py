# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

"""Command line entry point.

`dosbox-mcp` with no arguments serves MCP over stdio (what an MCP client
spawns). `setup` and `probe` are the human-facing configuration
commands; there is deliberately no interactive dialog - the commented
config template plays that role.
"""

import argparse
import json
import sys


from .client import DosboxClient
from .config import (
    Config,
    default_config_path,
    update_config_file,
    write_config_template,
)
from .connection import Connection, NotConnected
from .lifecycle import InstanceManager, LifecycleError
from .protocol import BRIDGE_PROTOCOL


def _serve() -> int:
    # Local import: the MCP server pulls in asyncio machinery the other
    # subcommands never need.
    from .server import main as serve_main
    serve_main()
    return 0


def _connection_factory(config: Config) -> Connection:
    return Connection(config)


def _cmd_setup(args) -> int:
    path = default_config_path()
    if args.init:
        try:
            write_config_template(path)
        except FileExistsError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(f"wrote {path} - edit it to suit; commented lines show defaults")
        return 0

    changes = {}
    for key in ("binary", "port", "protocol", "mode", "token_file"):
        value = getattr(args, key)
        if value is not None:
            changes[key] = value
    if args.headless is not None:
        changes["headless"] = args.headless

    if not changes:
        try:
            config = Config.load()
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        current = {
            "config_file": str(path),
            "binary": str(config.binary) if config.binary else None,
            "port": config.port,
            "headless": config.headless,
            "protocol": config.protocol,
            "mode": config.mode,
            "token_file": str(config.token_file) if config.token_file else None,
        }
        print(json.dumps(current, indent=2))
        return 0

    try:
        update_config_file(path, changes)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(f"saved to {path}")
    return 0


def _cmd_probe(args) -> int:
    try:
        config = Config.load()
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    print(f"bridge protocol: {BRIDGE_PROTOCOL}")
    print(f"config file:     {default_config_path()}")
    print(f"target:          {config.base_url} (mode {config.mode})")

    if config.binary is not None:
        return _probe_binary(config)
    print("no binary configured - trying to attach to a running instance")
    return _probe_attach(config)


def _probe_binary(config: Config) -> int:
    def attach(base_url, token):
        client = DosboxClient(base_url, token)
        return client.get("/api/v1/dosbox/info")

    manager = InstanceManager(config, attach=attach)
    try:
        info = manager.start()
    except LifecycleError as e:
        print(str(e), file=sys.stderr)
        return 1
    try:
        print(f"binary:          {config.binary}")
        print(f"engine version:  {info.get('version', '?')}")
        print(f"engine protocol: {info.get('mcp_protocol', 'implicit 1.0')}")
    finally:
        manager.stop()
    return 0


def _probe_attach(config: Config) -> int:
    conn = _connection_factory(config)
    try:
        conn.ensure_connected()
    except NotConnected as e:
        print(f"not connected: {e}")
        return 1
    status = conn.status()
    print(f"engine version:  {status['engine_version']}")
    print(f"protocol:        {status['protocol']}")
    print(f"features:        {json.dumps(status['features'])}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dosbox-mcp",
        description="MCP bridge for dosbox. Without a subcommand, serves "
                    "MCP over stdio.",
    )
    sub = parser.add_subparsers(dest="command")

    setup = sub.add_parser(
        "setup",
        help="write config values; --init writes a commented template; "
             "no flags prints the current configuration",
    )
    setup.add_argument("--init", action="store_true",
                       help="write the commented default config")
    setup.add_argument("--binary", help="dosbox binary that bridge_start spawns")
    setup.add_argument("--port", type=int, help="webserver port on 127.0.0.1")
    setup.add_argument("--headless", action=argparse.BooleanOptionalAction,
                       default=None, help="spawn without a window")
    setup.add_argument("--protocol", help='protocol pin, "major.minor"')
    setup.add_argument("--mode", help="capability mode: observe/interact/full")
    setup.add_argument("--token-file", dest="token_file",
                       help="token file of an already-running instance")

    sub.add_parser(
        "probe",
        help="validate the config and probe the binary (or a running "
             "instance) for version and protocol",
    )
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "setup":
        return _cmd_setup(args)
    if args.command == "probe":
        return _cmd_probe(args)
    return _serve()


if __name__ == "__main__":
    sys.exit(main())

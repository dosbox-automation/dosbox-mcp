# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import asyncio

from dosbox_mcp.config import Config
from dosbox_mcp.connection import Connection
from dosbox_mcp.server import build_server


def make_conn():
    config = Config(base_url="http://127.0.0.1:8386", token=None)
    return Connection(config)


class FakeManager:
    running = False
    pid = None

    def __init__(self, logs_error=None):
        self._logs_error = logs_error

    def logs(self, n):
        if self._logs_error:
            raise self._logs_error
        return ["line one", "line two"]


def over_the_wire(server, request, mode):
    from mcp import Client

    async def run():
        async with Client(server, mode=mode) as client:
            return await request(client)
    return asyncio.run(run())


def wire_server(mode="full", logs_error=None):
    return build_server(make_conn(), mode=mode,
                        manager=FakeManager(logs_error=logs_error))

# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import logging

import httpx
import mcp.types as types

from .client import DosboxClient
from .config import Config, default_token_path, read_token
from .protocol import IncompatiblePeer, effective_version

log = logging.getLogger(__name__)

HELLO_PATH = "/api/v1/hello"
INFO_PATH = "/api/v1/dosbox/info"


class Connection:
    """Lazy connector to a running dosbox instance.

    Starts disconnected. On the first tool call (or an explicit
    bridge_connect), reads the token, probes the instance, and
    negotiates the effective protocol version. Reconnects automatically
    if the instance restarts (new token) or comes back after going away.

    `transport` is an httpx transport injection point so tests never
    touch the network.
    """

    def __init__(self, config: Config, transport=None):
        self._config = config
        self._transport = transport
        self._client: DosboxClient | None = None
        self._features: dict = {}
        self._engine_info: dict = {}
        self._effective: tuple[int, int] | None = None

    @property
    def config(self) -> Config:
        return self._config

    @property
    def connected(self) -> bool:
        return self._client is not None

    @property
    def base_url(self) -> str:
        return self._config.base_url

    @property
    def features(self) -> dict:
        return self._features

    @property
    def engine_info(self) -> dict:
        return self._engine_info

    @property
    def effective_protocol(self) -> str | None:
        if self._effective is None:
            return None
        return f"{self._effective[0]}.{self._effective[1]}"

    def status(self) -> dict:
        """Connection state for bridge_status. Reports token presence,
        never the token value (design rule: tokens stay out of
        transcripts)."""
        token = self._config.token or read_token(self._config.token_file)
        return {
            "connected": self.connected,
            "base_url": self.base_url,
            "engine_name": self._engine_info.get("name"),
            "engine_version": self._engine_info.get("version"),
            "protocol": self.effective_protocol,
            "features": dict(self._features),
            "token": "present" if token else "absent",
        }

    def probe_hello(self) -> tuple[bool, dict | None]:
        """Unauthenticated hello probe: (something listens, hello payload
        or None when the engine predates the route)."""
        try:
            with httpx.Client(transport=self._transport, timeout=5.0) as probe:
                resp = probe.get(self._config.base_url.rstrip("/") + HELLO_PATH)
        except httpx.HTTPError:
            return False, None
        if resp.status_code == 200:
            try:
                return True, resp.json()
            except ValueError:
                return True, None
        return True, None

    def _no_token_message(self) -> str:
        looked_in = (
            "looked in DOSBOX_API_TOKEN and "
            f"{self._config.token_file or default_token_path()}"
        )
        listening, hello = self.probe_hello()
        if hello is not None:
            return (
                f"Instance found at {self.base_url} "
                f"(version {hello.get('version', '?')}, "
                f"protocol {hello.get('mcp_protocol', '?')}) "
                f"but no usable token - {looked_in}."
            )
        if listening:
            return (
                f"Something answers at {self.base_url} but no usable "
                f"token - {looked_in}."
            )
        return f"No API token available and nothing answers at {self.base_url} - is dosbox running?"

    def _try_connect(self):
        token = self._config.token or read_token(self._config.token_file)
        if token is None:
            raise NotConnected(self._no_token_message())

        client = DosboxClient(self._config.base_url, token,
                              transport=self._transport)
        try:
            info = client.get(INFO_PATH)
        except httpx.ConnectError:
            raise NotConnected(
                f"Cannot reach dosbox at {self._config.base_url}"
            ) from None
        except RuntimeError as e:
            if "401" in str(e) and self._config.token:
                # A remembered token (e.g. from a stopped spawned
                # instance) went stale: drop it and retry once via the
                # normal token lookup.
                self._config.token = None
                return self._try_connect()
            raise NotConnected(f"attach to {self._config.base_url} failed: {e}") from e

        try:
            effective = effective_version(info, pin=self._config.protocol)
        except (IncompatiblePeer, ValueError) as e:
            raise NotConnected(str(e)) from e

        self._client = client
        self._engine_info = info
        self._features = info.get("features", {})
        self._effective = effective
        log.info("attached to %s (%s, protocol %s)", self._config.base_url,
                 info.get("version", "?"), self.effective_protocol)

    def ensure_connected(self):
        if self._client is None:
            self._try_connect()

    def detach(self):
        self._client = None
        self._features = {}
        self._engine_info = {}
        self._effective = None
        log.info("detached from dosbox")

    def call(self, method, path, **kwargs):
        """Execute an HTTP call, reconnecting once on failure."""
        self.ensure_connected()
        fn = getattr(self._client, method)
        try:
            return fn(path, **kwargs)
        except (httpx.ConnectError, httpx.RemoteProtocolError):
            self.detach()
            raise NotConnected("dosbox went away during the call")
        except RuntimeError as e:
            if "401" in str(e):
                self.detach()
                self._try_connect()
                fn = getattr(self._client, method)
                return fn(path, **kwargs)
            raise

    def get(self, path, **kwargs):
        return self.call("get", path, **kwargs)

    def post(self, path, **kwargs):
        return self.call("post", path, **kwargs)

    def post_text(self, path, text, **kwargs):
        return self.call("post_text", path, text=text, **kwargs)

    def put(self, path, **kwargs):
        return self.call("put", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.call("delete", path, **kwargs)


class NotConnected(Exception):
    pass


def guard(connection: Connection, handler, feature=None):
    """Wrap a tool handler with connection and feature checks."""
    def guarded(args):
        try:
            connection.ensure_connected()
            if feature and not connection.features.get(feature):
                return [types.TextContent(
                    type="text",
                    text=f"Feature '{feature}' is not enabled in the running instance.",
                )]
            return handler(args)
        except NotConnected as e:
            return [types.TextContent(type="text", text=str(e))]
    return guarded

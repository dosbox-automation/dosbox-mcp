# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import ipaddress
import logging
import os
import re
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import tomlkit
from platformdirs import user_config_dir

from .protocol import BRIDGE_PROTOCOL, parse_version

logger = logging.getLogger(__name__)

_LOOPBACK_NAMES = {"localhost"}

# The engine accepts exactly this (webserver/private/auth.h IsValidHexToken).
_TOKEN_RE = re.compile(r"[0-9A-Fa-f]{64}")

MODES = ("observe", "interact", "full")

# Protocol pins are "major.minor"; the patch grade is spec-document-only
# and never appears on the wire (design doc, protocol levels).
_PROTOCOL_RE = re.compile(r"^\d+\.\d+$")

DEFAULT_PORT = 8386


def validate_base_url(url: str) -> str:
    """Accept only http(s) URLs pointing at a loopback address."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"scheme must be http or https, got {parsed.scheme!r}")
    host = parsed.hostname
    if host is None:
        raise ValueError(f"no host in URL {url!r}")
    if host in _LOOPBACK_NAMES:
        return url
    try:
        if ipaddress.ip_address(host).is_loopback:
            return url
    except ValueError:
        pass
    raise ValueError(f"host {host!r} is not a loopback address")


def default_config_path() -> Path:
    """The bridge's own config file. DOSBOX_MCP_CONFIG overrides for
    tests and unusual setups."""
    env = os.environ.get("DOSBOX_MCP_CONFIG")
    if env:
        return Path(env)
    return Path(user_config_dir("dosbox-mcp")) / "config.toml"


def default_token_path() -> Path:
    """Where the engine's launcher writes the API token by default."""
    return Path.home() / ".config" / "dosbox-automation" / "webserver" / "api_token"


def read_token(token_file: Path | None = None) -> str | None:
    """Token from DOSBOX_API_TOKEN, else the given file, else the default
    token file. Returns None if no token is available (dosbox not
    running yet)."""
    env = os.environ.get("DOSBOX_API_TOKEN")
    if env:
        return env
    path = token_file if token_file is not None else default_token_path()
    if not path.is_file():
        return None
    try:
        token = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as e:
        logger.warning("cannot read the token file %s, not using it: %s",
                       path, type(e).__name__)
        return None
    if _TOKEN_RE.fullmatch(token):
        return token
    logger.warning("%s holds no dosbox-automation API token, not using it", path)
    return None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_port(value: object) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool),
             f"port must be an integer, got {value!r}")
    _require(1 <= value <= 65535, f"port out of range: {value}")
    return value


def _validate_mode(value: object) -> str:
    _require(isinstance(value, str) and value in MODES,
             f"mode must be one of {MODES}, got {value!r}")
    return value


def _validate_protocol(value: object) -> str:
    _require(isinstance(value, str) and bool(_PROTOCOL_RE.match(value)),
             f'protocol pin must be "major.minor" (e.g. "1.0"), got {value!r}')
    return value


def _validate_bool(key: str):
    def check(value: object) -> bool:
        _require(isinstance(value, bool), f"{key} must be true or false, got {value!r}")
        return value
    return check


def _expanded_path(key: str, value: str) -> Path:
    try:
        return Path(value).expanduser()
    except RuntimeError as e:
        raise ValueError(f"{key}: cannot expand {value!r}: {e}") from e


def _validate_path(key: str):
    def check(value: object) -> Path:
        _require(isinstance(value, str) and value != "",
                 f"{key} must be a non-empty string path, got {value!r}")
        return _expanded_path(key, value)
    return check


_TOML_KEYS = {
    "binary": _validate_path("binary"),
    "port": _validate_port,
    "headless": _validate_bool("headless"),
    "protocol": _validate_protocol,
    "mode": _validate_mode,
    "token_file": _validate_path("token_file"),
}


def _read_toml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"malformed config {path}: {e}") from e
    unknown = sorted(set(raw) - set(_TOML_KEYS))
    if unknown:
        raise ValueError(
            f"unknown key(s) in {path}: {', '.join(unknown)} "
            f"(known: {', '.join(sorted(_TOML_KEYS))})"
        )
    return {key: _TOML_KEYS[key](value) for key, value in raw.items()}


@dataclass
class Config:
    base_url: str
    token: str | None = None
    binary: Path | None = None
    port: int = DEFAULT_PORT
    headless: bool = False
    protocol: str | None = None
    mode: str = "full"
    token_file: Path | None = None

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Resolve configuration with precedence env > toml > defaults."""
        data = _read_toml(path if path is not None else default_config_path())

        port = data.get("port", DEFAULT_PORT)
        base = os.environ.get("DOSBOX_API_URL") or f"http://127.0.0.1:{port}"

        env_token_file = os.environ.get("DOSBOX_TOKEN_FILE")
        token_file = (_expanded_path("DOSBOX_TOKEN_FILE", env_token_file) if env_token_file
                      else data.get("token_file"))

        cfg = cls(
            base_url=validate_base_url(base),
            binary=data.get("binary"),
            port=port,
            headless=data.get("headless", False),
            protocol=data.get("protocol"),
            mode=data.get("mode", "full"),
            token_file=token_file,
        )
        cfg.token = read_token(cfg.token_file)
        return cfg


class ToolProtectedKey(ValueError):
    """Raised when a model-facing caller tries to write a key reserved
    for the human-edited config."""


# Binary decides what code runs, mode sets the agent's own privileges, and
# token_file and port decide where the bridge sends its token, so tools may
# write only the keys named here.
_TOOL_WRITABLE_KEYS = frozenset({"headless", "protocol"})

_CONFIG_TEMPLATE = """\
# dosbox-mcp configuration
# Read at bridge startup. Precedence: environment > this file > defaults.
# Uncomment a line to set it; commented lines show the defaults.

# Path to the dosbox binary that bridge_start spawns.
# Deliberately not settable through any MCP tool.
#binary = "/usr/local/bin/dosbox"

# Port of the instance's webserver on 127.0.0.1 (used to connect, and
# passed to a spawned instance).
#port = 8386

# Spawn without a window (SDL dummy video driver).
#headless = false

# Pin the bridge to a lower protocol version, "major.minor" form.
#protocol = "1.0"

# Capability mode: what a connected agent may do.
#   observe  - read-only tools only
#   interact - adds input, video capture, script, instance lifecycle
#   full     - everything (memory writes, port IO, cpu control, debugger)
# Human-edited only: no tool can change this.
#mode = "full"

# Token file of an already-running instance to attach to. Leave unset
# to use the engine's default location.
#token_file = "~/.config/dosbox-automation/webserver/api_token"
"""


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     delete=False) as tmp:
        tmp.write(text)
        tmp.flush()
        os.fsync(tmp.fileno())
    if path.exists():
        os.chmod(tmp.name, path.stat().st_mode)
    os.replace(tmp.name, path)


def _pin_within_bridge(pin: str) -> bool:
    pinned = parse_version(pin)
    bridge = parse_version(BRIDGE_PROTOCOL)
    return pinned[0] == bridge[0] and pinned[1] <= bridge[1]


def update_config_file(path: Path, changes: dict,
                       tool_facing: bool = False) -> None:
    """Apply validated changes to the config file, preserving the
    human's comments and layout (tomlkit round-trip, atomic replace).

    tool_facing=True enforces the model-side boundary: protected keys
    are rejected loudly instead of written.
    """
    if not changes:
        raise ValueError("no changes given")
    unknown = sorted(set(changes) - set(_TOML_KEYS))
    if unknown:
        raise ValueError(f"unknown key(s): {', '.join(unknown)}")
    if tool_facing:
        protected = sorted(set(changes) - _TOOL_WRITABLE_KEYS)
        if protected:
            raise ToolProtectedKey(
                f"key(s) {', '.join(protected)} are set in the human-edited "
                "config file only - not writable through a tool"
            )
        if "protocol" in changes:
            _validate_protocol(changes["protocol"])
            _require(_pin_within_bridge(changes["protocol"]),
                     f"protocol pin {changes['protocol']!r} exceeds what this "
                     f"bridge implements ({BRIDGE_PROTOCOL})")
    for key, value in changes.items():
        _TOML_KEYS[key](value)

    if path.is_file():
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    else:
        doc = tomlkit.document()
    for key, value in changes.items():
        doc[key] = value
    _atomic_write(path, tomlkit.dumps(doc))


def write_config_template(path: Path) -> None:
    """Write the commented default config (`dosbox-mcp setup --init`).
    Refuses to clobber an existing file."""
    if path.exists():
        raise FileExistsError(f"{path} already exists - edit it instead")
    _atomic_write(path, _CONFIG_TEMPLATE)

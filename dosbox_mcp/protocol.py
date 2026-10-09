# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

"""Protocol version negotiation.

The spec (PROTOCOL.md) is versioned MAJOR.MINOR.PATCH; only
"major.minor" travels on the wire. Peers are compatible when the major
matches; the effective contract is the smaller minor. Engines that ship
a features block but predate the mcp_protocol field (da1, da2) are
implicit 1.0, because 1.0 is defined as the surface those releases ship.
"""

import re
from importlib import metadata

# Highest protocol version this bridge implements.
BRIDGE_PROTOCOL = "1.0"

# Route groups the 1.0 contract knows (first path segment after
# /api/v1/). bridge_swagger reports anything else as unknown to the
# protocol - informational, never fatal.
KNOWN_ROUTE_PREFIXES = frozenset({
    "status", "program", "dosbox", "video", "capture", "input", "memory",
    "dos", "cpu", "io", "script", "drive", "mount", "hello",
    "openapi.json",
})

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")


class IncompatiblePeer(Exception):
    pass


def parse_version(value: object) -> tuple[int, int]:
    """Parse a "major.minor" wire version into a comparable tuple."""
    if not isinstance(value, str):
        raise ValueError(f"protocol version must be a string, got {value!r}")
    match = _VERSION_RE.match(value)
    if match is None:
        raise ValueError(f'protocol version must be "major.minor", got {value!r}')
    return int(match.group(1)), int(match.group(2))


def negotiate(bridge: tuple[int, int], engine: tuple[int, int]) -> tuple[int, int]:
    """Effective contract between two peers: major must match, minor is
    the smaller of the two."""
    if bridge[0] != engine[0]:
        raise IncompatiblePeer(
            f"protocol major mismatch: bridge speaks {bridge[0]}.x, "
            f"engine speaks {engine[0]}.x"
        )
    return bridge[0], min(bridge[1], engine[1])


def effective_version(info: dict, pin: str | None = None) -> tuple[int, int]:
    """Determine the effective protocol version from an /info payload.

    pin (config `protocol`) lowers the bridge's own side for testing and
    compatibility; it can never exceed what the bridge implements.
    """
    bridge = parse_version(BRIDGE_PROTOCOL)
    if pin is not None:
        pinned = parse_version(pin)
        if pinned[0] != bridge[0] or pinned[1] > bridge[1]:
            raise ValueError(
                f"protocol pin {pin!r} exceeds what this bridge implements "
                f"({BRIDGE_PROTOCOL})"
            )
        bridge = pinned

    advertised = info.get("mcp_protocol")
    if advertised is not None:
        try:
            engine = parse_version(advertised)
        except ValueError as e:
            raise IncompatiblePeer(f"engine advertises {advertised!r}: {e}") from e
    elif "features" in info:
        engine = (1, 0)
    else:
        raise IncompatiblePeer(
            "peer advertises no protocol version and no features block - "
            "not a dosbox-mcp protocol peer"
        )
    return negotiate(bridge, engine)


def bridge_version() -> str:
    try:
        return metadata.version("dosbox-mcp")
    except metadata.PackageNotFoundError:
        return "unknown"

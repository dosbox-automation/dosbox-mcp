# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import pytest


@pytest.fixture(autouse=True)
def isolate_token(monkeypatch, tmp_path):
    """Keep the token lookup off the developer's real config.

    read_token() reads DOSBOX_API_TOKEN, then falls back to a token
    file. Without isolation a token file left on the machine (or the
    env var from a shell session) leaks into tests that assert 'no
    token available', making them pass or fail by environment. House
    rule: unit tests never touch live user configuration.
    """
    monkeypatch.delenv("DOSBOX_API_TOKEN", raising=False)
    monkeypatch.setenv("DOSBOX_TOKEN_FILE", str(tmp_path / "no_such_token"))


@pytest.fixture(autouse=True)
def isolate_config(monkeypatch, tmp_path):
    """Point the toml lookup at a nonexistent file so a developer's real
    ~/.config/dosbox-mcp/config.toml never leaks into test results."""
    monkeypatch.setenv("DOSBOX_MCP_CONFIG", str(tmp_path / "no_such_config.toml"))
    monkeypatch.delenv("DOSBOX_API_URL", raising=False)


# stdio clients take the legacy handshake; the in-process default is the
# 2026-07-28 era, which skips initialize and the JSON-RPC framing.
@pytest.fixture(params=["legacy", "auto"])
def wire_mode(request):
    return request.param

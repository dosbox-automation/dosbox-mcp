<!--
This file is part of the dosbox-mcp Project.
License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
-->

# Privacy policy of the dosbox-mcp plugin

Last changed on 2026-11-11. This policy covers the dosbox-mcp plugin for
Claude and the dosbox-mcp bridge that the plugin runs. The
dosbox-automation project publishes both. You can reach us at
dosbox-mcp@trinity2k.net.

## What we collect

We collect nothing. The plugin and the bridge send no data to the
dosbox-automation project or to anyone else; their only network access is
the downloads described under Network access. They have no telemetry, no
analytics, no crash reports and no accounts.

## What happens on your computer

The bridge runs on your computer and talks only to the dosbox-automation
emulator over a loopback address such as 127.0.0.1. It reads the emulator's
API token file, its own config file, and the environment variables
DOSBOX_API_TOKEN, DOSBOX_TOKEN_FILE, DOSBOX_API_URL and DOSBOX_MCP_CONFIG
when they are set. It sends the token only to the emulator's loopback
address in its config.

The bridge writes its own config file when you run its `setup` command or
when Claude changes the window setting or the protocol pin. If you name an
emulator program in that config, Claude can start the emulator through the
bridge. The bridge then creates a temporary config folder for it, where that
emulator keeps its API token and its recordings. The `bridge_stop` tool
deletes that folder with everything in it. If the emulator ends any other
way, for example through `dosbox_shutdown`, or the session ends while it
runs, the folder and its token file stay in your temporary folder until you
delete them. The emulator's own output from that start becomes part of your
conversation when Claude asks for it.

Recordings go into the emulator's capture folder, or to a path that a Lua
script or a REST call names, as the plugin's README describes. Everything
the plugin writes stays on your computer.

## What goes into your conversation

The screen text, screenshots, memory contents, emulator output and other
tool results that Claude asks for become part of your conversation with
Claude, the same way any tool result does. Anthropic handles your
conversation under its own privacy policy. The dosbox-automation project
never sees it.

## Network access

When the plugin starts the bridge, the `uvx` tool installs it from the wheel
inside the plugin and checks PyPI for the bridge's Python dependencies; the
first start downloads them. If your computer has no Python 3.11 or newer,
`uvx` also downloads a Python interpreter from GitHub (the
python-build-standalone releases). The `setup` command, which you run
yourself, fetches dosbox-mcp from PyPI in the same way. PyPI, which the
Python Software Foundation runs, and GitHub see these download requests
under their own privacy policies. The plugin and the bridge send nothing
else over the network.

## Children

The plugin is a tool for developers and is not intended for people under 18.
It drives whatever DOS software you run in the emulator, and some DOS games
were made for adults.

## Changes to this policy

When this policy changes, the new text replaces this file, and the
repository's history keeps every earlier version.

<!--
This file is part of the dosbox-mcp Project.
License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
-->

# dosbox-mcp for Claude

Lets Claude drive a DOS machine: type at the prompt and press keys, read
the screen, take screenshots, record video and audio, run Lua scripts
inside the emulator, and read and write its memory. It is the MCP bridge
of the [dosbox-automation](https://dosbox-automation.org) project,
packaged as a Claude plugin together with a skill that tells Claude how to
use it.

dosbox-automation is a DOS emulator of its own. It began as a fork of
dosbox-staging, which descends from DOSBox, and has been developed
independently since version 0.85.0. This plugin is published by the
dosbox-automation project and is not affiliated with the DOSBox project.

The bridge runs on your computer, so the plugin works in Claude Code and
in Cowork sessions on your own machine. Chat on claude.ai does not start
local servers.

## What you need

- **dosbox-automation**, the emulator, must be installed and running.
  This plugin does not bring it; get it from the
  [releases page](https://github.com/dosbox-automation/dosbox-automation/releases).
- **uv** must be on your PATH, because the plugin starts the bridge with
  `uvx`. The bridge itself comes with the plugin, in
  `vendor/dosbox_mcp-0.2.3-py3-none-any.whl`, the same file as dosbox-mcp
  0.2.3 on PyPI.
- The emulator's primary config needs these lines in its `[webserver]`
  section:

  ```ini
  webserver_enabled = true
  webserver_token_file = true
  mount_allowed_bases = /home/you/dos
  ```

  The last line names the folders DOS may mount; the emulator refuses
  everything else.

On Linux, with the usual config folder, the bridge finds the API token by
itself. On Windows and macOS, or with `XDG_CONFIG_HOME` set, tell it once
where the emulator keeps it:

```
uvx dosbox-mcp==0.2.3 setup --token-file <emulator config folder>/webserver/api_token
```

This writes the path into the bridge's own config file, so it works
however Claude starts the bridge.

## Use it

Start the emulator, then ask Claude to run a program, type a command,
read what is on the screen, record a session or find a value in a game's
memory. The skill tells Claude which tools to use and in what order.

## What it does on your machine

- **Network:** When the plugin starts the bridge, `uvx` installs it from the
  wheel in the plugin's `vendor/` folder and checks PyPI for the bridge's
  Python dependencies; the first start downloads them, later starts use uv's
  cache. If `uvx` finds no Python 3.11 or newer, it downloads an interpreter
  as well. The `setup` command above, which you run yourself, fetches the
  same dosbox-mcp 0.2.3 from PyPI. The bridge process itself talks only to
  the emulator, on loopback addresses.
- **Files it reads:** The bridge reads the emulator's API token file and its
  own config file; `uvx dosbox-mcp==0.2.3 setup` without options prints
  where the config file is. The bridge uses the token file only when it
  holds an API token of 64 hex digits, and it sends that token only to the
  emulator address in its config.
- **Environment:** When they are set, the bridge reads `DOSBOX_API_TOKEN`
  (the token itself), `DOSBOX_TOKEN_FILE`, `DOSBOX_API_URL` (which must be a
  loopback address) and `DOSBOX_MCP_CONFIG` (the path of its config file).
- **Files it writes:** The bridge writes its config file when you run
  `setup` or when Claude calls the `bridge_setup` tool. That tool can change
  only the window setting and the protocol pin; you set the emulator binary,
  the capability mode, the token file and the port yourself. `bridge_start`
  writes a temporary config folder for the emulator it starts.
- **Processes:** The bridge runs while Claude uses it. It starts an emulator
  only when you named one in its config (`setup --binary`). That emulator
  runs on its own empty config, so MOUNT finds no allowed folder there; for
  real work, start the emulator yourself.
- **What Claude can reach:** Claude can reach everything inside the emulated
  DOS machine. It reaches host files through MOUNT, only below
  `mount_allowed_bases`, and through the audio path described under
  Recordings. The emulator's API listens on loopback only and asks for the
  token on every request except its version probe.
  The `session_info` tool tells Claude where the token file is and gives it
  a curl command for the emulator's REST API. With a shell, as in Claude
  Code, Claude can use that command for any route of the API, the audio path
  included, beyond what the capability mode lets its tools do.
- **Your conversation:** The screen text, screenshots, memory contents and
  other tool results that Claude asks for become part of your conversation,
  like any other tool result.
- **Recordings:** The capture tools write numbered files into the emulator's
  capture folder. A Lua script that Claude runs through `script_run`, or a
  REST call made with the `session_info` command, can give an audio
  recording a file path of its own. The emulator refuses system folders
  there, but writes anywhere else your user account can write and replaces a
  file that already exists.
- **Accounts:** The plugin sends no telemetry, needs no account and stores
  no credentials.

## Links

- Bridge source and documentation:
  https://github.com/dosbox-automation/dosbox-mcp
- Project website: https://www.dosbox-automation.org
- Guide for agents: `AGENTS.md` and `docs/agents/` in the emulator's
  release package.
- License: GPL-2.0-or-later.

---
dosbox-mcp has been written with the help of tooled assistance, but has
been designed, reviewed and thoroughly tested and signed off by its
developer.

<!--
This file is part of the dosbox-mcp Project.
License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
-->

# dosbox-mcp for Hermes

Lets a Hermes agent drive a DOS machine: type at the prompt and press
keys, read the screen, take screenshots, record video and audio, run Lua
scripts inside the emulator, and read and write its memory. It is the MCP
bridge of the [dosbox-automation](https://dosbox-automation.org) project,
packaged for Hermes.

## What you need

- **dosbox-automation**, the emulator, installed and running. This plugin
  does not bring it; get it from the
  [releases page](https://github.com/dosbox-automation/dosbox-automation/releases).
- **uv** on your PATH: the plugin starts the bridge with
  `uvx dosbox-mcp==0.2.2`.
- In the emulator's primary config, section `[webserver]`:

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
uvx dosbox-mcp==0.2.2 setup --token-file <emulator config folder>/webserver/api_token
```

This writes the path into the bridge's own config file, so it works
however Hermes starts the bridge.

## What it does on your machine

- **Network:** on first start `uvx` downloads `dosbox-mcp` 0.2.2 and its
  Python dependencies from PyPI, and a Python interpreter when it finds
  none of version 3.11 or newer. After that the bridge talks only to the
  emulator, on loopback addresses.
- **Files read:** the emulator's API token file and the bridge's own
  config file (`dosbox-mcp/config.toml` in your config folder).
- **Files written:** the bridge's config file, by `setup` or by the
  agent's `bridge_setup` tool. `bridge_start` writes a temporary config
  folder for the emulator it starts.
- **Processes:** the bridge runs while Hermes uses it. It starts an
  emulator only when you named one in its config (`setup --binary`).
  That emulator runs on its own empty config, so MOUNT finds no allowed
  folder there; for real work start the emulator yourself.
- **What the agent can reach:** everything inside the emulated DOS
  machine. Host files only through MOUNT, and only below
  `mount_allowed_bases`. The emulator's API listens on loopback only and
  wants the token on every request except its version probe.
- **Recordings** go to the emulator's capture folder.
- No telemetry, no accounts, no stored credentials.

## Links

- Bridge source and documentation:
  https://github.com/dosbox-automation/dosbox-mcp
- Guide for agents: `AGENTS.md` and `docs/agents/` in the emulator's
  release package.
- License: GPL-2.0-or-later.

---
dosbox-mcp has been written with the help of tooled assistance, but has
been designed, reviewed and thoroughly tested and signed off by its
developer.

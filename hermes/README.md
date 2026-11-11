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

- **dosbox-automation**, the emulator, must be installed and running.
  This plugin does not bring it; get it from the
  [releases page](https://github.com/dosbox-automation/dosbox-automation/releases).
- **uv** must be on your PATH, because the plugin starts the bridge with
  `uvx dosbox-mcp==0.2.4`.
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
uvx dosbox-mcp==0.2.4 setup --token-file <emulator config folder>/webserver/api_token
```

This writes the path into the bridge's own config file, so it works
however Hermes starts the bridge.

## Use it

Start the emulator, then ask the agent to run a program, type a command,
read what is on the screen, record a session or find a value in a game's
memory. The skill tells the agent which tools to use and in what order.

These three requests need no other software: they run at the emulator's
own Z:\> prompt, so they also serve as a test setup.

- "Run DIR Z: and tell me which programs are on drive Z:."
- "Record a short video while you type VER at the DOS prompt, then stop the
  recording and tell me whether it ended cleanly."
- "Read the BIOS keyboard flags at 0040:0017 and tell me whether Num Lock
  is on."

The agent reads the screen as text whenever the program runs in a text mode,
which costs far fewer tokens than a screenshot. Video and audio capture
records the emulator's own output, what the DOS program draws and plays;
dosbox-mcp contains no generative model and creates no media of its own.

If something does not work, the troubleshooting sheet is at
https://github.com/dosbox-automation/dosbox-mcp/blob/main/feelies/TECH-SUPPORT.md.

## What it does on your machine

- **Network:** The first time the plugin starts, `uvx` downloads
  `dosbox-mcp` 0.2.4 and its Python dependencies from PyPI. If it finds no
  Python 3.11 or newer, it downloads an interpreter as well. After that the
  bridge talks only to the emulator, on loopback addresses.
- **Files it reads:** The bridge reads the emulator's API token file and its
  own config file; `uvx dosbox-mcp==0.2.4 setup` without options prints
  where the config file is. The bridge uses the token file only when it
  holds an API token of 64 hex digits, and it sends that token only to the
  emulator address in its config.
- **Environment:** When they are set, the bridge reads `DOSBOX_API_TOKEN`
  (the token itself), `DOSBOX_TOKEN_FILE`, `DOSBOX_API_URL` (which must be a
  loopback address) and `DOSBOX_MCP_CONFIG` (the path of its config file).
- **Files it writes:** The bridge writes its config file when you run
  `setup` or when the agent calls the `bridge_setup` tool. That tool can
  change only the window setting and the protocol pin; you set the emulator
  binary, the capability mode, the token file and the port yourself.
  `bridge_start` writes a temporary config folder for the emulator it
  starts; that emulator keeps its API token and its recordings there.
  `bridge_stop` deletes the folder with everything in it, so copy recordings
  out first. If the emulator ends any other way, the folder stays in your
  temporary folder until you delete it.
- **Processes:** The bridge runs while Hermes uses it. It starts an emulator
  only when you named one in its config (`setup --binary`). That emulator
  runs on its own empty config, so MOUNT finds no allowed folder there; for
  real work, start the emulator yourself.
- **What the agent can reach:** The agent can reach everything inside the
  emulated DOS machine. It reaches host files through MOUNT, only below
  `mount_allowed_bases`, and through the audio path described under
  Recordings. The emulator's API listens on loopback only and asks for the
  token on every request except its version probe.
  The `session_info` tool tells the agent where the token file is and gives
  it a curl command for the emulator's REST API. An agent with a shell can
  use that command for any route of the API, the audio path included, beyond
  what the capability mode lets its tools do.
- **Your conversation:** The screen text, screenshots, memory contents and
  other tool results that the agent asks for become part of the agent's
  conversation, like any other tool result.
- **Recordings:** The capture tools write numbered files into the emulator's
  capture folder. A Lua script that the agent runs through `script_run`, or
  a REST call made with the `session_info` command, can give an audio
  recording a file path of its own. The emulator refuses system folders
  there, but writes anywhere else your user account can write and replaces a
  file that already exists.
- **Accounts:** The plugin sends no telemetry, needs no account and stores
  no credentials.

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

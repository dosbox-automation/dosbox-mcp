<!--
This file is part of the dosbox-mcp Project.
License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
-->

# Installing dosbox-mcp: notes for an AI agent

These steps are for an agent, such as Cline, that sets up dosbox-mcp for a
user. dosbox-mcp is the MCP server for the dosbox-automation emulator. It
runs on the user's computer and talks only to an emulator on 127.0.0.1.

## 1. The emulator

The user installs dosbox-automation themselves, from
https://github.com/dosbox-automation/dosbox-automation/releases (Linux and
Windows builds; on macOS it is built from source). Do not download or run
it on the user's behalf. Ask whether it is installed, and if not, point
the user to that page.

## 2. The emulator's config

The emulator needs three lines in the `[webserver]` section of its primary
config file. Add the section if the file has none.

```ini
[webserver]
webserver_enabled = true
webserver_token_file = true
mount_allowed_bases = /home/you/dos
```

The file is `~/.config/dosbox-automation/dosbox-automation.conf` on Linux,
`%LOCALAPPDATA%\dosbox-automation\dosbox-automation.conf` on Windows and
`~/Library/Preferences/dosbox-automation/dosbox-automation.conf` on macOS.
Ask the user which folder DOS may mount and use their answer for
`mount_allowed_bases`; do not pick one yourself. The emulator refuses to
mount anything outside the folders listed there.

## 3. uv

The server starts through `uvx`. Check with `uv --version`. If uv is
missing, ask the user to install it from https://docs.astral.sh/uv/.

## 4. The MCP server entry

Add this server to the MCP settings:

```json
{
  "mcpServers": {
    "dosbox": {
      "command": "uvx",
      "args": ["dosbox-mcp"]
    }
  }
}
```

The server needs no API key and no account. It reads the emulator's own
API token from the token file the emulator writes.

## 5. The token file on Windows and macOS

On Linux the server finds the token file by itself. On Windows and macOS,
or when `XDG_CONFIG_HOME` is set, tell it once where the file is:

```
uvx dosbox-mcp setup --token-file <emulator config folder>/webserver/api_token
```

The emulator config folder is the folder from step 2 that holds
`dosbox-automation.conf`.

## 6. Check

Ask the user to start the emulator. Then call the `bridge_connect` tool: it
attaches to the emulator and, when it cannot, says why: nothing answers on
the port, or something answers but there is no usable token.
`dosbox_status` shows what the emulated machine is doing, and
`bridge_help` lists every tool. A simple first request is to run `DIR Z:`
at the DOS prompt and read the result with `screen_text`.

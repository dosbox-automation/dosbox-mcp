---
name: dosbox-automation
description: Drive DOS programs and games in dosbox-automation through the dosbox MCP tools. Use when the user wants to run, install, test, record or inspect a DOS program, type into the DOS prompt, read the DOS screen, or find values in a game's memory.
license: GPL-2.0-or-later
---
<!--
This file is part of the dosbox-mcp Project.
License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
-->

# Driving DOS with dosbox-automation

## Before the first call

- The emulator is a separate install: dosbox-automation from
  https://github.com/dosbox-automation/dosbox-automation/releases. These
  tools only talk to it.
- Its primary config needs, in `[webserver]`: `webserver_enabled = true`,
  `webserver_token_file = true`, and `mount_allowed_bases = <folder>` for
  the folders DOS may mount. Without the last line MOUNT refuses every path.
- The emulator must be running. `bridge_status` says whether the tools
  reach it. On Windows and macOS, or with `XDG_CONFIG_HOME` set, the user
  points the bridge at the token once: `uvx dosbox-mcp==0.2.3 setup
  --token-file <emulator config folder>/webserver/api_token`.
- The API listens on loopback only; every call except the version probe
  needs the token.
- An emulator started with `bridge_start` runs on an empty config: MOUNT
  finds no allowed folder there. Prefer the emulator the user started.

## Working

| Need | Tools |
|---|---|
| State of the machine | `dosbox_status`, `bridge_status` |
| Type a line, press keys | `input_type` (text, `\n` is Enter), `input_key`, `input_sequence` (names like `KBD_enter`, `KBD_esc`, `KBD_f1`) |
| Read the screen | `screen_text` (text modes only), `screen_capture` (any mode, PNG; `mode`: `raw` or `rendered`), `screen_info` |
| Record | `video_capture_start` (`mode`: `raw` or `rendered`), `video_capture_stop`/`_status`, `video_capture_compression`/`_set`, `audio_capture_start`/`_stop`/`_status` |
| Lua inside the emulator | `script_run`, `script_status`, `script_stop` |
| Memory | `mem_read`, `mem_write`, `mem_search`, `freeze_set`/`_list`/`_clear`, `dos_memory_map` |
| Stop | `dosbox_shutdown` |

- After each input, read the screen before the next step. DOS programs
  react to timing; check the result, do not assume it.
- In graphics modes `screen_text` has nothing: use `screen_capture`.
- Mount folders with `MOUNT C <folder>` typed at the prompt; only folders
  under `mount_allowed_bases` work.
- Never kill the emulator by name: other sessions on the machine may run
  one. `dosbox_shutdown` ends it cleanly.

The full guide for agents ships with the emulator: `AGENTS.md` and
`docs/agents/` in the release package.

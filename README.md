# dosbox-mcp

MCP server for [dosbox-automation](https://dosbox-automation.org):
drive a DOS machine from an AI agent.

[dosbox-automation](https://github.com/dosbox-automation/dosbox-automation)
is a DOSBox fork with a built-in REST API for automation. This bridge
connects any MCP-capable agent (Claude Code, Claude Desktop, or anything
that speaks the Model Context Protocol) to a running emulator. The agent
can type into DOS programs, read the screen, capture frames and video,
run sandboxed Lua scripts, and inspect memory.

## Getting started

You need the emulator, this bridge, and an MCP client such as Claude
Code or Claude Desktop. The bridge runs on Python 3.11 or newer.

### 1. Get dosbox-automation

Download from the [releases page](https://github.com/dosbox-automation/dosbox-automation/releases)
or build from source. Linux and Windows builds are on the releases page;
on macOS you build from source. The [manual](https://dosbox-automation.org)
has the platform-specific setup.

### 2. Enable the API

Open the primary config file. It lives at
`~/.config/dosbox-automation/dosbox-automation.conf` on Linux,
`%LOCALAPPDATA%\dosbox-automation\` on Windows and
`~/Library/Preferences/dosbox-automation/` on macOS. In its
`[webserver]` section (add the section if the file has none), set:

```ini
[webserver]
webserver_enabled = true
webserver_token_file = true
mount_allowed_bases = /home/you/dos
```

The last line names the folder your DOS programs live in. The emulator
refuses to mount anything outside the folders listed there, so without
it the agent can type MOUNT all day and get nothing. On Windows write
the path as `C:\Users\you\dos`.

Start dosbox-automation. The DOS prompt appears in its window. To check
the API is up, open http://localhost:8386/ in a browser: the API's
documentation page answers.

### 3. Install the bridge

Pick one:

```
pipx install dosbox-mcp
```

```
uvx dosbox-mcp
```

`pip install dosbox-mcp` inside a virtual environment works too, but
then the `dosbox-mcp` command lives in that environment's `bin`
folder, and step 4 needs its full path.

You never start the bridge by hand. Your MCP client launches it when a
conversation begins and stops it afterwards. Run in a terminal, it
waits silently for a client that never comes.

### 4. Register with your MCP client

Claude Code, available in every project directory:

```
claude mcp add --scope user dosbox -- dosbox-mcp
```

With `uvx` instead of an install:

```
claude mcp add --scope user dosbox -- uvx dosbox-mcp
```

Claude Desktop: open Settings, then Developer, then Edit Config, and
add the server to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dosbox": { "command": "/home/you/.local/bin/dosbox-mcp" }
  }
}
```

Use the full path (`which dosbox-mcp`, or `where dosbox-mcp` on
Windows): a desktop app does not see your shell's PATH. For `uvx`, use
`"command": "uvx", "args": ["dosbox-mcp"]`. Restart Claude Desktop
afterwards; it reads the file only at start.

The bridge reads the emulator's API token from
`~/.config/dosbox-automation/webserver/api_token`. On Windows and macOS
the emulator writes the token under its own config folder from step 2,
in a `webserver` subfolder; point the bridge at that file with the
`DOSBOX_TOKEN_FILE` environment variable or the `token_file` setting
(see Configuration).

### 5. Hello world

Start a new conversation with your agent and ask it something like:

> Type DIR in the DOS prompt and tell me what files you see.

The agent calls the bridge tools to type the command, reads the screen
text, and reports back what DOS printed. From here you can mount the
folders you listed in step 2, run and install programs, capture
screenshots, search memory for values, or write Lua scripts that
automate entire workflows. The `bridge_status` tool confirms the
connection if you want to check first.

## Configuration

Optional. Write a commented config file to tune the port, spawn an
emulator on demand, or limit what an agent may do:

```
dosbox-mcp setup --init
```

The comments in the generated file explain each setting. Environment
variables `DOSBOX_API_URL`, `DOSBOX_API_TOKEN` and `DOSBOX_TOKEN_FILE`
override it. The bridge talks to loopback addresses only; it will not
reach out to a remote machine.

## What the agent gets

Tools for session control, screen text and captures, video recording,
Lua scripting, keyboard and mouse input, and memory access. You choose
how much reach an agent has, from read-only observation to full
control.

## An open protocol

The contract between this bridge and the emulator is written down in
[PROTOCOL.md](PROTOCOL.md) and versioned independently. dosbox-automation
is the reference implementation; any DOSBox variant that speaks the
protocol works with this bridge.

## In the box

Like the games it drives, this one ships with its paper. The `feelies/`
folder holds the manual, a reference card for every tool, an install
sheet, and a tech-support page.

## Requirements

- Python 3.11 or newer
- A running dosbox-automation (0.84-da2 or newer) on the same machine

## License

GPL-2.0-or-later. See LICENSE. The protocol specification
(PROTOCOL.md) is licensed CC-BY-SA-4.0.

---
This project is developed with tooled assistance, but tested, reviewed and
signed off by a human developer.

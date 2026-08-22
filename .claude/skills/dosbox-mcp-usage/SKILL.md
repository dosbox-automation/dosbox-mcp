---
name: dosbox-mcp-usage
description: "Setup and usage patterns for dosbox-mcp: installing the MCP bridge, configuring Claude Code, token authentication, mount policy, and common pitfalls. Use before connecting to a dosbox-automation instance or when debugging MCP/API issues."
---

# dosbox-mcp usage

How to install the dosbox-mcp bridge, connect it to Claude Code, and
drive a dosbox-automation instance without hitting the silent failures
that make this setup frustrating.


## Installing dosbox-mcp

Pick one:

```bash
# From PyPI (recommended)
pip install dosbox-mcp

# Or with pipx (isolated environment)
pipx install dosbox-mcp

# Or run without installing
uvx dosbox-mcp
```

The installed command is `dosbox-mcp`. Verify with `dosbox-mcp --help`.


## Adding to Claude Code

### Option A: CLI (one command)

```bash
claude mcp add dosbox -- dosbox-mcp
```

Or with uvx (no install needed):

```bash
claude mcp add dosbox -- uvx dosbox-mcp
```

### Option B: JSON configuration

Add to your project's `.mcp.json` or `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "dosbox": {
      "command": "dosbox-mcp",
      "args": []
    }
  }
}
```

With uvx:

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

After adding, restart Claude Code. The bridge registers its tools on
startup. Ask for `bridge_status` to confirm the connection.


## Starting dosbox-automation

The emulator must be running with its API enabled before the bridge
can connect. The API is off by default.

### Minimal config file

Create a file (e.g. `run.conf`):

```ini
[webserver]
webserver_enabled = true
webserver_token_file = true
```

Without `webserver_enabled = true`, no HTTP server starts and the
bridge has nothing to connect to. This is the most common setup
mistake.

### Starting the emulator

```bash
dosbox-automation -conf run.conf
```

For headless operation (no window):

```bash
SDL_VIDEODRIVER=offscreen dosbox-automation -conf run.conf 2>dosbox.log &
```

Wait 2-3 seconds after start before using MCP tools. The webserver
needs time to initialize and write the token file.

### Using -noprimaryconf

If you pass `-noprimaryconf -nolocalconf` to suppress loading the
user config from disk, you MUST provide everything via `-conf`,
including mount policy settings. These flags are useful for clean
automation but mean nothing loads from `~/.config/dosbox-automation/`.


## Token authentication

Every API request requires a bearer token. The bridge handles this
automatically via one of two channels:

### Channel A: environment variable

Set `DOSBOX_API_TOKEN` before starting both the emulator and the MCP
server process. Good for scripts and CI:

```bash
export DOSBOX_API_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
dosbox-automation -conf run.conf &
curl -H "Authorization: Bearer $DOSBOX_API_TOKEN" http://localhost:8386/api/v1/status
```

### Channel B: token file (recommended for Claude Code)

Set `webserver_token_file = true` in your config. The emulator writes
the token to `~/.config/dosbox-automation/webserver/api_token` at
startup. The bridge reads it from there.

This is the recommended path for Claude Code sessions because the MCP
server process starts at session init - before any emulator exists -
so the environment variable is not available.

### "No API token available"

This error means one of:
- `webserver_enabled` is false or was never set (no config loaded)
- `webserver_token_file` is false (token not written to disk)
- The emulator has not finished starting (wait longer)
- Using `-noprimaryconf` without a `-conf` that enables the webserver


## Mount policy

dosbox-automation restricts which host directories the guest can
access. This is a security boundary, not a bug. Two settings control
it, both read from the PRIMARY config file only:

- `mount_allowed_bases` - host directories for the MOUNT command
- `mount_allowed_image_roots` - host directories for image-based
  mounts and disk swaps

Both are semicolon-separated path lists in the `[webserver]` section
of the primary config at `~/.config/dosbox-automation/dosbox-automation.conf`.

Example:

```ini
[webserver]
mount_allowed_bases = /home/user/games;/home/user/dos
mount_allowed_image_roots = /home/user/games;/home/user/diskimages
```

### Why mounts fail silently

- Using `-noprimaryconf` means the allowed bases DO NOT LOAD. The
  emulator has no idea which host paths are permitted. The guest
  MOUNT command prints nothing, but the mounted drive is empty or
  the mount is refused.
- Check the `MOUNT_POLICY` lines in stderr (or your log file) to
  see which bases are active.

### The conf anchor

The directory holding the last `-conf` file you passed counts as an
allowed root for API image operations (disk swaps). This means a
multi-disk game whose images sit next to the conf file can swap
disks without configuring `mount_allowed_image_roots`.

### Mount lock

`POST /api/v1/mount/lock` (or Lua `dosbox.mount_lock()`) freezes the
mount configuration permanently until restart. No further mounts or
swaps are allowed from any source. Use it after setup is complete.


## Disk swapping

For multi-disk games, swap images over the API:

```
POST /api/v1/drive/swap
{"drive": "a", "image": "/path/to/disk2.img"}
```

Or from Lua: `dosbox.drive_swap("A", "disk2.img")`

The image path must be inside `mount_allowed_image_roots` or under
the conf anchor. Relative paths resolve against the policy roots
(conf anchor first, then each configured image root).


## Keyboard input

### Typing text

```
POST /api/v1/input/type
{"text": "cd game\n"}
```

The `\n` maps to Enter. The type endpoint paces key injection through
the keyboard buffer automatically.

### Individual keys

```
POST /api/v1/input/sequence
{"events": [
  {"type": "key", "key": "enter", "pressed": true},
  {"type": "key", "key": "enter", "pressed": false}
]}
```

Key names carry the `KBD_` prefix: `KBD_enter`, `KBD_esc`, `KBD_space`,
`KBD_up`, `KBD_down`, `KBD_f1` through `KBD_f12`, `KBD_leftshift`,
`KBD_leftctrl`, `KBD_leftalt`, `KBD_a` through `KBD_z`, etc.

Passing a bare name (e.g. "enter" instead of "KBD_enter") returns
`Unknown key` with no hint about the prefix.


## Screen reading

### Text mode

`GET /api/v1/video/text` returns the screen buffer as plain text.
Works in CGA/VGA/Hercules/Tandy text modes only.

### Frame capture

`GET /api/v1/video/frame?format=png&mode=rendered` grabs the current
frame as an image. Works in any video mode.


## Video recording

```
POST /api/v1/capture/video/start          # raw mode (default)
POST /api/v1/capture/video/start {"mode": "rendered"}  # post-shader
POST /api/v1/capture/video/stop
```

Output is AVI with ZMBV codec. VLC plays it natively.


## Audio capture

Record the mixer output as a WAV file:

```
POST /api/v1/capture/audio/start                    # auto-numbered in capture dir
POST /api/v1/capture/audio/start {"path": "/tmp/out.wav"}  # caller-specified path
POST /api/v1/capture/audio/stop
GET  /api/v1/capture/audio/status
```

The path parameter is validated against the system path denylist
(writing to `/etc/`, `/bin/`, etc. is rejected). Omit it to use the
default capture directory.

In Lua:
```lua
dosbox.audio_capture_start()           -- auto-numbered
dosbox.audio_capture_start("/tmp/out.wav")  -- specific path
dosbox.audio_capture_stop()
```

Headless capture works with `SDL_AUDIODRIVER=dummy` - the mixer
produces real PCM data even without audio hardware.


## Mixer control

Read and control the audio mixer:

```
GET  /api/v1/mixer                         # full state: master, mute, all channels
PUT  /api/v1/mixer/volume {"left": 0.8, "right": 0.8}   # set master volume
POST /api/v1/mixer/mute
POST /api/v1/mixer/unmute
PUT  /api/v1/mixer/channel/SB {"left": 0.5, "right": 0.5}  # set channel volume
```

Channel names come from the mixer itself (SB, GUS, CDAUDIO, SPKR,
etc.). `GET /api/v1/mixer` lists all active channels with their names,
user volumes, app volumes, enabled state, and sample rates.

In Lua:
```lua
local info = dosbox.mixer_info()     -- table with master_volume, muted, channels
dosbox.mixer_volume(0.8, 0.8)        -- set master
dosbox.mixer_channel_volume("SB", 0.5, 0.5)  -- set channel
dosbox.mixer_mute()
dosbox.mixer_unmute()
```


## Verifying the setup

After starting the emulator and Claude Code with the bridge
configured:

1. Ask for `bridge_status` - confirms the bridge sees the emulator
2. Ask for `dosbox_status` - confirms the API responds
3. Try `screen_text` - confirms screen reading works
4. Try typing something with `input_type` - confirms input injection

If step 1 fails, the token or connection is wrong. If step 2 fails,
the emulator is not running or the port is wrong. Steps 3 and 4 test
the actual automation path.


## Common errors

| Symptom | Cause |
|---|---|
| "No API token available" | Webserver not enabled, or token file not written |
| Mount fails silently | Path outside allowed bases; check MOUNT_POLICY in the log |
| "Unknown key: enter" | Missing KBD_ prefix; use "KBD_enter" |
| Connection refused | Emulator not running, or wrong port (default 8386) |
| "Blocked by mount policy" on disk swap | Image not in allowed roots or conf anchor |
| screen_text returns empty | Emulator is in graphics mode, not text mode |


## API reference

The full OpenAPI spec is served at `/openapi.json` on the running
instance. Open `http://localhost:8386/` in a browser for the
interactive Swagger UI. The `feelies/REFCARD.md` in the dosbox-mcp
package has a tool-by-tool reference card.

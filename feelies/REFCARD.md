# REFERENCE CARD - dosbox-mcp tools

Keep this by the keyboard. Every tool, one block, with an example call
in the arguments an MCP client passes. Tools marked (read-only) are
safe to auto-approve. A tool's feature flag (if any) must be enabled in
the engine build, and the tool must be within your capability mode.

## Bridge tools (about the bridge itself)

These work whether or not an engine is connected.

- **bridge_version** (read-only) - bridge version and protocol level.
  `{}`
- **bridge_status** (read-only) - connection state, engine version,
  effective protocol, features, mode, managed instance, token presence.
  `{}`
- **bridge_help** (read-only) - one-call orientation: version, state,
  and every available tool with a one-line description. `{}`
- **bridge_connect** - attach to the running engine explicitly; reports
  a precise reason on failure. `{}`
- **bridge_disconnect** - detach; the engine keeps running. `{}`
- **bridge_start** - spawn the engine binary from the config file (with
  an isolated config dir) and attach. `{}`
- **bridge_stop** - stop the instance this bridge spawned (never one it
  only attached to). `{}`
- **bridge_logs** (read-only) - tail the spawned instance's output.
  `{"n": 50}`
- **bridge_setup** - change safe settings (port, headless, protocol).
  Binary path and mode are human-edited only.
  `{"port": 8386, "headless": true}`
- **bridge_swagger** (read-only) - digest of the engine's OpenAPI
  surface: route counts and anything unknown to the protocol. `{}`

## Session and screen

- **dosbox_status** (read-only) - machine and program state in one call.
  `{}`
- **dosbox_shutdown** - shut the emulator down. Irreversible. `{}`
- **session_info** (read-only) - base URL and token location for
  driving the REST API directly (never the token value). `{}`
- **screen_text** (read-only) - read the text-mode screen. `{}`
- **screen_capture** (read-only) - capture a frame as an image. `{}`
- **screen_info** (read-only) - current video mode and geometry. `{}`

## Input (feature: input)

- **input_key** - press one named key.
  `{"key": "KBD_enter"}`
- **input_sequence** - a timed sequence of key and mouse events on one
  timeline (each event has a `type`, its data, and an optional
  `delay_ms`).
  `{"events": [{"key": "KBD_up"}, {"key": "KBD_enter", "delay_ms": 100}]}`
- **input_type** - type a string, paced so the keyboard buffer keeps
  up. `{"text": "dir *.exe"}`

## Memory (feature: memory)

- **mem_read** (read-only) - read guest physical memory; returns base64
  plus register state. `{"offset": 4660, "length": 64}`
- **mem_write** - write bytes to guest memory.
  `{"offset": 4660, "data": "AAECAw=="}`
- **mem_search** (read-only) - scan a range for a value (width 1/2/4).
  `{"start": 0, "end": 655360, "value": 100, "width": 2}`
- **dos_memory_map** (read-only) - walk the DOS MCB chain: which PSP
  owns which block. `{}`

## Freeze (feature: freeze)

- **freeze_set** - lock an address to a value each frame (the trainer
  primitive). `{"address": 4660, "value": 999, "width": 2}`
- **freeze_list** (read-only) - list active freezes. `{}`
- **freeze_clear** - clear one freeze or all.
  `{"address": 4660}`

## CPU and ports

- **cpu_write_register** - write a CPU register (feature: cpu_control).
  `{"register": "eax", "value": 0}`
- **port_read** (read-only) - read an x86 I/O port (feature: port_io).
  `{"port": 968, "width": 1}`
- **port_write** - write an x86 I/O port (feature: port_io).
  `{"port": 968, "value": 1, "width": 1}`

## Scripts (the escape hatch)

- **script_run** - load and run sandboxed Lua in the engine. Anything
  without a dedicated tool can usually be done here.
  `{"script": "dosbox.type('hello')"}`
- **script_status** (read-only) - script state and its output table.
  `{}`
- **script_stop** - stop the running script. `{}`

## Media and recording

- **video_capture_start** - start ZMBV video recording.
  `{}` or `{"mode": "rendered"}`
- **video_capture_stop** - stop video recording. `{}`
- **video_capture_status** (read-only) - video recording state. `{}`

## Audio

- **audio_capture_start** - start WAV audio capture.
  `{}` or `{"path": "/tmp/out.wav"}`
- **audio_capture_stop** - stop audio capture. `{}`
- **audio_capture_status** (read-only) - audio capture state. `{}`

## Mixer

- **mixer_status** (read-only) - master volume, mute state, all
  channels with volumes and sample rates. `{}`
- **mixer_volume** - set master volume.
  `{"left": 0.8, "right": 0.8}`
- **mixer_mute** - mute master output. `{}`
- **mixer_unmute** - unmute master output. `{}`
- **mixer_channel_volume** - set a channel's user volume.
  `{"channel": "SB", "left": 0.5, "right": 0.5}`

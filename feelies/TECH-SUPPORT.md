# TECHNICAL SUPPORT

Having trouble? Before you call the hotline (there is no hotline), work
through the sheet. Most problems are one of five things.

## "No API token available"

The bridge cannot find a token, which almost always means the engine is
not running the way it needs to be.

1. Is the engine actually running? Try `bridge_status`. If nothing
   answers on the port, start dosbox first.
2. Did you enable the webserver? The engine needs, in its config:
   `webserver_enabled = true`. It defaults to off.
3. Did you enable the token file? `webserver_token_file = true`. Without
   it the engine holds the token only in memory and the bridge cannot
   read it.
4. Are you looking in the right place? The bridge reads
   `~/.config/dosbox-automation/webserver/api_token` unless you set
   `token_file` in the bridge config or the `DOSBOX_API_TOKEN` env var.
5. Does the file hold a token? The bridge uses the token file only when
   it holds 64 hex digits; otherwise it logs a warning that names the
   file. You see this when the bridge points at the wrong file or a
   stale copy, or when an editor saved the file with a byte order mark.

If the engine has the hello route, `bridge_connect` tells you which of
these it is: it can see the engine is there and report that only the
token is missing.

## "Cannot reach dosbox at ..."

Nothing is listening on the address. Check the port matches on both
sides (engine `webserver_port`, bridge `port`), and that you did not
point the bridge at a different port through `DOSBOX_API_URL`.

## "host ... is not a loopback address"

The bridge refuses to talk to anything but 127.0.0.1 or ::1, on
purpose. If you set `DOSBOX_API_URL` to a LAN address or a hostname, it
will be rejected. Network operation is not part of this version.

## "Feature '...' is not enabled in the running instance"

The tool exists in the protocol, but this engine build has that
capability switched off (or was compiled without it). `bridge_status`
lists the features the running build reports. This is not a bug in the
bridge; it is the engine telling you the truth about itself.

## The agent cannot see a tool at all

Two possibilities:

- **Capability mode.** If your config has `mode = "observe"`, only
  read-only tools are registered; `mode = "interact"` leaves out the
  memory-surgery tools. Check `bridge_status` - it reports the mode.
  Widen it by editing the config file (not through a tool - by design).
- **Protocol level.** A newer tool group may be above the effective
  protocol negotiated with an older engine. `bridge_status` shows the
  effective version.

## bridge_start spawns nothing / fails

- No `binary` set in the config file. The bridge will not spawn a path
  handed to it by a tool - only one you wrote in the config. Set it
  with `dosbox-mcp setup --binary /path/to/dosbox`.
- The engine started but never wrote a token in time: the error carries
  the engine's own output, which usually says why (bad config, port in
  use). `bridge_logs` shows more.
- Something else is already on the port: the bridge authenticates
  against the instance it spawned, so a stranger on the port is
  rejected rather than mistaken for your engine.

## Something typed wrong / the screen shows garbage

Read the actual screen with `screen_text` or grab a frame with
`screen_capture` before assuming a timing bug. Nine times out of ten
the characters that landed tell you what went wrong. The screen is
ground truth.

## Still stuck

Everything the bridge knows about its own state is in `bridge_status`
and `bridge_help`. Everything the engine exposes is in its OpenAPI
document, digestible via `bridge_swagger`. Between the two, the honest
answer is usually already on screen.

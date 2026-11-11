# Changelog

## 0.2.4 (2026-11-11)

- Every tool carries a title, readOnlyHint, destructiveHint and
  openWorldHint.
- The bundled skill points to no outside guide and prefers screen text
  over screenshots.
- The bridge ignores HTTP proxy settings from the environment.
- `port_read` is no longer offered as read-only.
- `session_info` describes itself for users who want the REST API directly.

## 0.2.3 (2026-11-11)

- `bridge_setup` changes only headless and protocol.
- The bridge uses a token file only when it holds 64 hex digits.
- `audio_capture_start` takes no path; its recordings go to the
  capture folder.
- claude-plugin/ holds a plugin package for Claude.

## 0.2.2 (2026-11-11)

- `video_capture_start` and `screen_capture` take `mode`: `raw` (default) or
  `rendered`. `video_capture_stop` reports the mode and why the recording
  ended. New tools `video_capture_compression` and
  `video_capture_compression_set` read and set the zlib levels.
- LICENSE holds the GPL-2.0 text; which part carries which license is in NOTICE.
- `script_run` loads Lua scripts; no earlier release could.
- `session_info` reads the token file the bridge is configured with.
  Its curl example quotes the path.
- `~` at the start of a path in the config file or in `DOSBOX_TOKEN_FILE`
  means the home folder.
- The client sends a request again while dosbox-automation answers that it
  is busy.

## 0.2.1 (2026-10-12)

- The README walks through getting started, from the download to the
  first prompt you give the agent. No code changes.

## 0.2.0 (2026-10-09)

- Runs on the mcp 2.x SDK and requires it (mcp >= 2, < 3). Fixes the crash
  on start with `'Server' object has no attribute 'list_tools'` (#1).
- `dosbox_status` describes the archive preparation field of the status
  reply.

## 0.1.2 (2026-08-22)

- Audio capture and mixer tools.

## 0.1.1 (2026-07-19)

- PyPI discovery classifiers.

## 0.1.0 (2026-07-19)

- First release.

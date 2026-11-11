# This file is part of the dosbox-mcp Project.
# License: GPL-2.0-or-later. Contact: dosbox-mcp@trinity2k.net
#

import logging
import math
import time

import httpx

logger = logging.getLogger(__name__)

MIN_PAUSE_S = 0.05
MAX_PAUSE_S = 1.0


class EngineBusy(RuntimeError):
    """The engine still answered busy when the busy deadline ran out."""


def _pause_for(retry_after):
    """Seconds as the engine sends them; an HTTP date or a value that is not
    a finite, non-negative number waits the longest pause."""
    try:
        pause_s = float(retry_after)
    except ValueError:
        return MAX_PAUSE_S
    if not math.isfinite(pause_s) or pause_s < 0:
        return MAX_PAUSE_S
    return min(max(pause_s, MIN_PAUSE_S), MAX_PAUSE_S)


class DosboxClient:
    """Thin authenticated HTTP wrapper. Every request carries the bearer
    token and the X-Client: mcp header that drives the OSD activity signal."""

    def __init__(self, base_url, token, transport=None):
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "X-Client": "mcp",
            },
            transport=transport,
            timeout=30.0,
        )
        # The pauses block the calling thread; the stdio server answers nothing meanwhile.
        self.busy_deadline_s = 30.0

    def _send(self, method, path, **kwargs):
        """Busy is 503 with Retry-After: the emulation thread never ran the
        request, so it goes again. Any other 503 is an answer."""
        deadline = time.monotonic() + self.busy_deadline_s
        while True:
            resp = self._client.request(method, self._base + path, **kwargs)
            retry_after = resp.headers.get("retry-after")
            if resp.status_code != 503 or retry_after is None:
                return resp
            pause_s = _pause_for(retry_after)
            if time.monotonic() + pause_s >= deadline:
                logger.warning("engine still busy after %.0f s: %s %s",
                               self.busy_deadline_s, method, path)
                return resp
            logger.debug("engine busy, sending %s %s again in %.2f s", method, path, pause_s)
            time.sleep(pause_s)

    def _handle(self, resp):
        if resp.status_code >= 400:
            try:
                msg = resp.json().get("error", resp.text)
            except Exception:
                msg = resp.text
            if resp.status_code == 503 and resp.headers.get("retry-after") is not None:
                raise EngineBusy(f"{resp.status_code}: {msg}")
            raise RuntimeError(f"{resp.status_code}: {msg}")
        ctype = resp.headers.get("content-type", "")
        if ctype.startswith("application/json"):
            return resp.json()
        return resp.content

    def get(self, path, params=None, headers=None):
        return self._handle(self._send("GET", path, params=params, headers=headers))

    def post(self, path, json=None):
        return self._handle(self._send("POST", path, json=json))

    def post_text(self, path, text, content_type="text/plain", params=None):
        # Some endpoints (script/load) take a raw body, not JSON. httpx
        # sets Content-Type from the content= kwarg's type, so pin it.
        return self._handle(
            self._send(
                "POST",
                path,
                content=text.encode("utf-8"),
                headers={"Content-Type": content_type},
                params=params,
            )
        )

    def put(self, path, json=None):
        return self._handle(self._send("PUT", path, json=json))

    def delete(self, path, json=None):
        return self._handle(self._send("DELETE", path, json=json))

"""One HTTPS call with retries, shared by the Search Console and Bing clients.

`call(request, opener, sleep)` returns the answer's JSON. It tries again on
a 429, a 5xx or a dropped connection, waiting 1, 2, 4 then 8 seconds (or
what a Retry-After header asks, up to 60), at most RETRIES more times. A
4xx other than 429 is not retried: a wrong key or a missing permission does
not fix itself. Every failure is raised as Failed with the HTTP code and a
reason in plain words that never holds a key or token (`hide`).

The opener is `urllib.request.urlopen` unless a test hands in its own; the
tests also hand in `sleep`, so no test waits.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

RETRIES = 4
TIMEOUT = 60
MAX_BYTES = 50_000_000
AGENT = "skald-search/1"


class Failed(RuntimeError):
    """A call that did not give an answer. `code` is the HTTP status (0: no
    answer at all), `detail` the engine's own message when it gave one."""

    def __init__(self, code: int, words: str, detail: str = "") -> None:
        super().__init__(words)
        self.code, self.detail = code, detail


def scrub(text: str, hide) -> str:
    for secret in hide or ():
        if secret:
            text = text.replace(secret, "***")
    return text


def _detail(body: bytes) -> str:
    """The engine's own error message, if its answer has one."""
    try:
        got = json.loads(body.decode("utf-8", "replace") or "{}")
    except ValueError:
        return ""
    if not isinstance(got, dict):
        return ""
    error = got.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("status") or "")[:300]
    if isinstance(error, str):
        return str(got.get("error_description") or error)[:300]
    return str(got.get("Message") or got.get("message") or "")[:300]


def _wait(attempt: int, headers) -> float:
    try:
        asked = float((headers or {}).get("Retry-After") or 0)
    except (TypeError, ValueError):
        asked = 0
    return min(60.0, asked) if asked > 0 else float(2 ** attempt)


def call(request: urllib.request.Request, opener=None, sleep=time.sleep, hide=(),
         retries: int = RETRIES) -> dict:
    opener = opener or urllib.request.urlopen
    if not request.has_header("User-agent"):
        request.add_header("User-Agent", AGENT)
    last = Failed(0, "no answer")
    for attempt in range(retries + 1):
        headers = None
        try:
            with opener(request, timeout=TIMEOUT) as answer:
                body = answer.read(MAX_BYTES)
            try:
                got = json.loads(body.decode("utf-8", "replace") or "{}")
            except ValueError:
                raise Failed(200, "the answer was not JSON") from None
            return got if isinstance(got, dict) else {"d": got}
        except urllib.error.HTTPError as why:
            try:
                body = why.read(200_000)
            except OSError:
                body = b""
            headers = why.headers
            detail = scrub(_detail(body), hide)
            last = Failed(why.code, f"HTTP {why.code}" + (f": {detail}" if detail else ""),
                          detail)
            if why.code != 429 and why.code < 500:
                break
        except (urllib.error.URLError, OSError, TimeoutError) as why:
            reason = getattr(why, "reason", why)
            last = Failed(0, scrub(f"could not reach the server ({reason})", hide)[:300])
        if attempt < retries:
            sleep(_wait(attempt, headers))
    raise last

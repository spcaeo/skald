"""Asking one question of one provider, through its documented HTTP API.

Each provider: the request (with the profile's place and language), the
answer's text, and the URLs it cited, in the order the answer gives them.
Checked against the providers' documents on 2026-10-18:

  openai      POST https://api.openai.com/v1/responses, Bearer key;
              tools [{"type": "web_search", "user_location": {"type":
              "approximate", city, region, country, timezone}}]. Text: the
              `message` output item's `output_text` parts; cited: their
              `annotations` of type `url_citation` (url, title).
  perplexity  POST https://api.perplexity.ai/v1/agent (the Agent API, which
              replaces Sonar chat completions), Bearer key; `preset` (or a
              `provider/model` name), tools [{"type": "web_search",
              "user_location": {city, region, country, latitude, longitude}}],
              `language_preference` (ISO 639-1). Text: the `message` item's
              `output_text`; cited: the `search_results` item's `results`
              ({id, url, title}) that the text's [n] or [web:n] markers name,
              in the order named (all results when the text names none). An
              older Sonar answer (choices, citations, search_results) is read
              too.
  gemini      POST https://generativelanguage.googleapis.com/v1beta/models/
              <model>:generateContent, header x-goog-api-key; tools
              [{"google_search": {}}]. Text: candidates[0].content.parts[].text;
              cited: groundingMetadata.groundingChunks[].web {uri, title}. The
              API has no location field, so the place and the language are
              written into the question. A uri on Google's grounding redirect
              host is resolved by asking for its Location header (no page is
              fetched); when that fails the title (the source's domain) is kept
              as the citation's domain and its page stays unknown.
  anthropic   POST https://api.anthropic.com/v1/messages, x-api-key,
              anthropic-version 2023-06-01; tools [{"type":
              "web_search_20250305", "name": "web_search", "max_uses": 3,
              "user_location": {"type": "approximate", city, region, country,
              timezone}}]. Text: the `text` blocks; cited: their `citations`
              of type `web_search_result_location` (url, title). A
              `pause_turn` answer is sent back to finish, at most twice.

Where no language field exists (all but Perplexity) a language other than
English is asked for in a last line of the question ("Answer in fr-CA.").

`transport(method, url, headers, body, timeout) -> (status, headers, bytes)`
is injected by tests; the default uses urllib. Rate limits (429) and server
errors (5xx, timeouts) are tried again with backoff (Retry-After honoured, at
most 60 s), RETRIES times; 400, 401, 403 and 404 are not. A reason never
holds the key.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from . import LOCATION, IN_QUESTION, TEXT_MAX

TIMEOUT = 90
RETRIES = 3
BACKOFF = 4.0
MAX_WAIT = 60.0
REDIRECT_HOST = "vertexaisearch.cloud.google.com"
RESOLVE_MAX = 10
URLS = {"openai": "https://api.openai.com/v1/responses",
        "perplexity": "https://api.perplexity.ai/v1/agent",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "anthropic": "https://api.anthropic.com/v1/messages"}


class Failed(RuntimeError):
    """The provider gave no answer: the reason, in words without the key."""


# ------------------------------------------------------------- transport

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):     # noqa: D401 - keep the 3xx
        return None


def urllib_transport(method: str, url: str, headers: dict, body: bytes | None,
                     timeout: float):
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as answer:
            return answer.status, dict(answer.headers), answer.read(10_000_000)
    except urllib.error.HTTPError as why:
        return why.code, dict(why.headers or {}), why.read(200_000) if why.fp else b""


def _scrub(text: str, key: str | None) -> str:
    text = str(text)
    return text.replace(key, "***") if key else text


def _post(transport, url: str, headers: dict, payload: dict, key: str | None,
          timeout: float, retries: int, sleep) -> dict:
    body = json.dumps(payload).encode()
    last = "no answer"
    for attempt in range(retries + 1):
        wait = BACKOFF * (2 ** attempt)
        try:
            status, got_headers, raw = transport("POST", url, headers, body, timeout)
        except (OSError, ValueError) as why:        # timeouts, refused connections
            status, got_headers, raw = None, {}, b""
            last = f"{type(why).__name__}: {why}"
        if status is not None and 200 <= status < 300:
            try:
                return json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                raise Failed("the answer is not JSON") from None
        if status is not None:
            last = f"HTTP {status}" + _error_words(raw)
            if status not in (408, 409, 425, 429) and status < 500:
                break                               # a wrong key or request: no retry
            after = {k.lower(): v for k, v in (got_headers or {}).items()}.get("retry-after")
            try:
                wait = max(wait, float(after)) if after else wait
            except ValueError:
                pass
        if attempt < retries:
            sleep(min(wait, MAX_WAIT))
    raise Failed(_scrub(last, key)[:300])


def _error_words(raw: bytes) -> str:
    try:
        got = json.loads(raw.decode("utf-8", "replace"))
    except (ValueError, AttributeError):
        return ""
    err = got.get("error") if isinstance(got, dict) else None
    if isinstance(err, dict):
        err = err.get("message") or err.get("type")
    return f": {str(err)[:200]}" if err else ""


# --------------------------------------------------------------- the ask

def _language_line(lang: str | None) -> str:
    lang = (lang or "").strip()
    return "" if not lang or lang.lower() == "en" or lang.lower().startswith("en-") \
        else f"\n\nAnswer in {lang}."


def question_text(provider: str, question: str, where: dict) -> str:
    """The question as sent: with the place written in when the provider has
    no location field, and the language asked for when it has no language
    field."""
    text = question.strip()
    if LOCATION[provider] == IN_QUESTION:
        place = ", ".join(x for x in (where.get("city"), where.get("region"),
                                      where.get("country")) if x)
        if place:
            text += f"\n\nI am in {place}."
    if provider != "perplexity":
        text += _language_line(where.get("language"))
    return text


def _location(where: dict, *, kind: bool, zone: bool, coords: bool) -> dict | None:
    got = {k: where[k] for k in ("city", "region", "country") if where.get(k)}
    if zone and where.get("timezone"):
        got["timezone"] = where["timezone"]
    if coords and where.get("lat") is not None and where.get("lon") is not None:
        got.update(latitude=where["lat"], longitude=where["lon"])
    if not got:
        return None
    return {"type": "approximate", **got} if kind else got


def request(provider: str, model: str, question: str, where: dict, key: str) -> tuple:
    """(url, headers, payload) for one question."""
    text = question_text(provider, question, where)
    if provider == "openai":
        tool = {"type": "web_search"}
        loc = _location(where, kind=True, zone=True, coords=False)
        if loc:
            tool["user_location"] = loc
        return (URLS[provider], {"Authorization": f"Bearer {key}"},
                {"model": model, "input": text, "tools": [tool]})
    if provider == "perplexity":
        tool = {"type": "web_search"}
        loc = _location(where, kind=False, zone=False, coords=True)
        if loc:
            tool["user_location"] = loc
        payload = {"input": text, "tools": [tool]}
        payload["model" if "/" in model else "preset"] = model
        lang = (where.get("language") or "").split("-")[0].lower()
        if re.fullmatch(r"[a-z]{2}", lang):
            payload["language_preference"] = lang
        return URLS[provider], {"Authorization": f"Bearer {key}"}, payload
    if provider == "gemini":
        return (URLS[provider].format(model=urllib.parse.quote(model, safe="-._")),
                {"x-goog-api-key": key},
                {"contents": [{"role": "user", "parts": [{"text": text}]}],
                 "tools": [{"google_search": {}}]})
    if provider == "anthropic":
        tool = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}
        loc = _location(where, kind=True, zone=True, coords=False)
        if loc:
            tool["user_location"] = loc
        return (URLS[provider], {"x-api-key": key, "anthropic-version": "2023-06-01"},
                {"model": model, "max_tokens": 1500, "tools": [tool],
                 "messages": [{"role": "user", "content": text}]})
    raise ValueError(f"not a provider: {provider!r}")


def ask(provider: str, key: str, model: str, question: str, where: dict, transport=None,
        timeout: float = TIMEOUT, retries: int = RETRIES, sleep=time.sleep) -> dict:
    """{"text", "citations": [{"url", "title"[, "domain"]}], "sent"}: one
    answer. Raises Failed."""
    transport = transport or urllib_transport
    url, headers, payload = request(provider, model, question, where, key)
    headers = {**headers, "Content-Type": "application/json", "User-Agent": "skald-ai-answers/1"}
    raw = _post(transport, url, headers, payload, key, timeout, retries, sleep)
    if provider == "anthropic":
        for _ in range(2):              # a long search turn: send it back to finish
            if raw.get("stop_reason") != "pause_turn":
                break
            payload = {**payload, "messages": payload["messages"]
                       + [{"role": "assistant", "content": raw.get("content") or []}]}
            raw = _post(transport, url, headers, payload, key, timeout, retries, sleep)
    got = parse(provider, raw)
    if provider == "gemini":
        got["citations"] = resolve(got["citations"], transport, timeout)
    if not got["text"] and not got["citations"]:
        raise Failed("the answer holds no text")
    got["sent"] = payload_question(provider, payload)
    return got


def payload_question(provider: str, payload: dict) -> str:
    if provider == "openai" or provider == "perplexity":
        return str(payload.get("input"))
    if provider == "gemini":
        return str(payload["contents"][0]["parts"][0]["text"])
    return str(payload["messages"][0]["content"])


# ------------------------------------------------------------- answers

def _dedupe(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for c in items:
        url = str(c.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        item = {"url": url[:2000], "title": str(c.get("title") or "")[:300]}
        if c.get("domain"):
            item["domain"] = str(c["domain"])[:253]
        out.append(item)
    return out


def _trim(text: str) -> str:
    return text.strip()[:TEXT_MAX]


def parse(provider: str, raw: dict) -> dict:
    """{"text", "citations"} from a provider's answer."""
    raw = raw if isinstance(raw, dict) else {}
    if provider == "openai" or (provider == "perplexity" and "output" in raw):
        texts, cited, results = [], [], []
        for item in raw.get("output") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message":
                for part in item.get("content") or []:
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        texts.append(str(part.get("text") or ""))
                        cited += [a for a in part.get("annotations") or []
                                  if isinstance(a, dict) and a.get("type") == "url_citation"]
            elif item.get("type") == "search_results":
                results += [r for r in item.get("results") or [] if isinstance(r, dict)]
        text = "\n".join(t for t in texts if t) or str(raw.get("output_text") or "")
        if provider == "perplexity" and not cited:
            cited = _marked(text, results)
        return {"text": _trim(text), "citations": _dedupe(cited)}
    if provider == "perplexity":                    # an older Sonar answer
        choice = ((raw.get("choices") or [{}])[0] or {}).get("message") or {}
        results = raw.get("search_results") or [{"url": u} for u in raw.get("citations") or []]
        return {"text": _trim(str(choice.get("content") or "")),
                "citations": _dedupe([r for r in results if isinstance(r, dict)])}
    if provider == "gemini":
        cand = (raw.get("candidates") or [{}])[0] or {}
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict))
        chunks = (cand.get("groundingMetadata") or {}).get("groundingChunks") or []
        cited = [{"url": (c.get("web") or {}).get("uri"), "title": (c.get("web") or {}).get("title")}
                 for c in chunks if isinstance(c, dict)]
        return {"text": _trim(text), "citations": _dedupe(cited)}
    if provider == "anthropic":
        texts, cited = [], []
        for block in raw.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(str(block.get("text") or ""))
                cited += [c for c in block.get("citations") or []
                          if isinstance(c, dict) and c.get("type") == "web_search_result_location"]
        return {"text": _trim("".join(texts)), "citations": _dedupe(cited)}
    raise ValueError(f"not a provider: {provider!r}")


MARK = re.compile(r"\[(?:web:)?(\d{1,3})\]")


def _marked(text: str, results: list[dict]) -> list[dict]:
    """Perplexity's results in the order the text's [n] / [web:n] markers name
    them; every result when it names none."""
    by_id = {str(r.get("id")): r for r in results}
    order = []
    for m in MARK.finditer(text):
        r = by_id.get(m.group(1))
        if r is not None and r not in order:
            order.append(r)
    return order or results


def resolve(citations: list[dict], transport, timeout: float) -> list[dict]:
    """Gemini's grounding redirects: the real address from the Location
    header (no page fetched); the title as the domain when that fails."""
    out = []
    for i, c in enumerate(citations):
        host = (urllib.parse.urlsplit(c["url"]).hostname or "").lower()
        if host != REDIRECT_HOST:
            out.append(c)
            continue
        real = None
        if i < RESOLVE_MAX:
            try:
                status, headers, _ = transport("HEAD", c["url"], {"User-Agent": "skald-ai-answers/1"},
                                               None, min(timeout, 15))
                where = {k.lower(): v for k, v in (headers or {}).items()}.get("location")
                if 300 <= int(status) < 400 and where and where.startswith(("http://", "https://")):
                    real = where
            except (OSError, ValueError, TypeError):
                real = None
        if real:
            out.append({"url": real[:2000], "title": c.get("title", "")})
        else:
            domain = str(c.get("title") or "").strip().lower()
            item = {"url": c["url"], "title": c.get("title", "")}
            if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain):
                item["domain"] = domain
            out.append(item)
    return _dedupe(out)

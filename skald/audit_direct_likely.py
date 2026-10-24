"""The second count of "Direct, likely <reason>" (day kind `direct_likely`).

Registered in audit_more.RECOUNTS. It sees every line the audit judged
(`judged`) and every people visit (`visit`), and rebuilds the figure from
them with its own code, written apart from direct_likely.py. It shares only
the name lists in direct_names.py:

  a preview     a line the audit's judge put in bots as a link preview
                (its info names the app); its minute is the line's epoch
                seconds // 60; its page is the path cut at "?" or "#", to 70
                characters, a trailing "/" taken off ("/" stays "/")
  a Direct      a visit that read a page whose source (the audit's own
  visit         label, audit_labels.source_of) is "Direct or unknown"
  its address   the first page line's URL, its query split here by hand on
                "&" and "=" (pairs with no value left out, the first 40
                kept, the last of a repeated name winning, names lower case)
  checkout      a provider parameter whose value starts with its prefix; or
                a path segment (lower case, "_" as "-", a final .html, .htm,
                .php or .aspx off) that is a checkout end page, or a done
                word after a checkout section
  in_app        the audit's own browser label is an in-app browser
  shared        a share parameter or a share word in a ref-like value; else a
                preview of the landing page in the visit's first minute or up
                to the window before it (two apps or more: "(more than one)")

The window is the one the stored day says it used, so a later change of
`attribution.share_window_minutes` never makes an old day disagree.
"""
from __future__ import annotations

from collections import Counter
from urllib.parse import unquote_plus

from .direct_names import (CHECKOUT_DONE, CHECKOUT_PAGES, CHECKOUT_PARAMS, CHECKOUT_SECTIONS,
                           IN_APP_BROWSERS, MANY, PAGE_ENDINGS, REASONS, RETURN_PAGE,
                           SHARE_KEYS, SHARE_PARAMS, SHARE_TAG, SHARE_WORDS)

NO_SOURCE = "Direct or unknown"


def _bare_page(path: str) -> str:
    cut = len(path or "")
    for mark in ("?", "#"):
        at = (path or "").find(mark)
        if at != -1:
            cut = min(cut, at)
    got = (path or "")[:cut][:70]
    while len(got) > 1 and got.endswith("/"):
        got = got[:-1]
    return got or "/"


def _pairs(url: str) -> dict:
    """The landing address's query, by hand: {lower-case name: value}."""
    if "?" not in url:
        return {}
    kept = []
    for part in url.split("?", 1)[1].split("&"):
        name, eq, value = part.partition("=")
        if not eq or not value:
            continue
        kept.append((unquote_plus(name).lower(), unquote_plus(value)))
        if len(kept) == 40:
            break
    return dict(kept)


def _path_words(url: str) -> list[str]:
    words = []
    for raw in url.split("?", 1)[0].split("#", 1)[0].split("/"):
        seg = raw.lower().replace("_", "-")
        ending = next((e for e in PAGE_ENDINGS if seg.endswith(e)), "")
        if ending:
            seg = seg[: len(seg) - len(ending)]
        if seg != "":
            words.append(seg)
    return words


def _paid_return(url: str) -> str:
    query = _pairs(url)
    for name, prefix, provider in CHECKOUT_PARAMS:
        value = query.get(name) or ""
        if value.strip() != "" and value[: len(prefix)] == prefix:
            return provider
    words = _path_words(url)
    seen_section = False
    for word in words:
        if word in CHECKOUT_PAGES:
            return RETURN_PAGE
    for word in words:
        if seen_section and word in CHECKOUT_DONE:
            return RETURN_PAGE
        if word in CHECKOUT_SECTIONS:
            seen_section = True
    return ""


def _split_words(value: str) -> list[str]:
    out, word = [], ""
    for ch in value:
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            word += ch
        elif word:
            out.append(word)
            word = ""
    if word:
        out.append(word)
    return out


def _share_tag(url: str) -> str:
    query = _pairs(url)
    for name in SHARE_PARAMS:
        if (query.get(name) or "").strip():
            return SHARE_PARAMS[name]
    for key in SHARE_KEYS:
        value = (query.get(key) or "").strip().lower()
        if value == "":
            continue
        words = _split_words(value)
        for word in [*words, "".join(words)]:
            if word in SHARE_WORDS:
                return SHARE_WORDS[word] if SHARE_WORDS[word] else SHARE_TAG
    return ""


class Recount:
    def __init__(self, config, day, tz, own) -> None:
        self.previews: list[tuple[int, str, str]] = []      # (minute, page, app)
        self.visits = 0
        self.direct: list[tuple[int, str, str, str]] = []   # (minute, page, url, browser)

    def judged(self, line, group, info) -> None:
        app = (info or {}).get("preview")
        if group == "bots" and app:
            self.previews.append((int(line.when.timestamp()) // 60, _bare_page(line.path), app))

    def visit(self, lines, is_page, labels) -> None:
        if labels is None:
            return
        self.visits += 1
        if labels["source"] != NO_SOURCE:
            return
        first = next((x for x in lines if is_page(x)), None)
        if first is None:
            return
        start = int(min(x.when for x in lines).timestamp()) // 60
        self.direct.append((start, _bare_page(labels["landing"]), first.url, labels["browser"]))

    def _count(self, window: int) -> tuple[Counter, dict]:
        reasons: Counter = Counter()
        details = {r: Counter() for r in REASONS}
        for start, page, url, browser in self.direct:
            why = detail = ""
            provider = _paid_return(url)
            if provider:
                why, detail = "checkout", provider
            elif browser in IN_APP_BROWSERS:
                why, detail = "in_app", browser
            else:
                tag = _share_tag(url)
                if tag:
                    why, detail = "shared", tag
                else:
                    apps = {a for m, p, a in self.previews
                            if p == page and m <= start <= m + window}
                    if apps:
                        why, detail = "shared", (apps.pop() if len(apps) == 1 else MANY)
            if why:
                reasons[why] += 1
                details[why][detail] += 1
        return reasons, details

    def compare(self, stored, same, problems) -> None:
        blob = stored.get("direct_likely")
        if blob is None:
            return
        reasons, details = self._count(int(blob.get("share_window_minutes", 0)))
        likely = sum(reasons.values())
        same("direct_likely: visits", int(blob.get("visits", 0)), self.visits)
        same("direct_likely: direct visits", int(blob.get("direct", 0)), len(self.direct))
        same("direct_likely: likely visits", int(blob.get("likely", 0)), likely)
        same("direct_likely: plain direct visits", int(blob.get("plain", 0)),
             len(self.direct) - likely)
        kept = blob.get("reasons") or {}
        for why in REASONS:
            same(f"direct_likely: {why}", int(kept.get(why, 0)), reasons[why])
            mine = {k: int(v) for k, v in ((blob.get("details") or {}).get(why) or {}).items()}
            for name in sorted(set(mine) | set(details[why])):
                same(f"direct_likely: {why}, {name}", mine.get(name, 0), details[why][name])
        for extra in sorted(set(kept) - set(REASONS)):
            problems.append(f"direct_likely: a reason the recount does not know: {extra}")

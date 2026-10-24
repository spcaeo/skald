"""Direct, likely <reason>: the day kind `direct_likely` (an inferred split of
the Direct visits, never part of the real counts).

A visit with no referrer and no campaign tag is Direct. Some of them say
more in their own request or in the log around them, and those are split
out as *likely* a reason, never as fact. Each Direct visit (source "Direct
or unknown") gets at most one reason, tested in this order (the name lists
are in direct_names.py):

  checkout  its landing address carries a payment provider's return
            parameter (Stripe's session_id=cs_..., PayPal's PayerID=, ...:
            detail the provider), or its path is a checkout's end
            (/checkout/order-received/, /order/thank-you: detail
            "(return page)")
  in_app    its browser label is an app's own browser (Instagram app,
            Facebook app, ...: detail the label)
  shared    its landing address carries a share marker (igshid=,
            ref=whatsapp, ...: detail the app, or "(share tag)"), or an app
            fetched a link preview of the same page in the same minute as the
            visit's first request or up to `attribution.share_window_minutes`
            (default 30) before (detail the app, or "(more than one)")

Everything else stays plain Direct. Like "likely sent by an AI assistant"
(ai_likely.py), it moves no visit and changes no count: the Direct row keeps
every one of these visits. The two estimates are apart: a visit can be both.

The blob (kind `direct_likely`; None when `attribution.direct_likely` is
false or the visits were not counted - "not recorded", never 0):

  share_window_minutes  the window the day was counted with
  visits      the day's visits (journeys)
  direct      of which Direct: equals the readers whose source is Direct
  likely      of which given a reason
  plain       of which not: direct - likely
  reasons     {"checkout", "in_app", "shared": visits}: always all three,
              adds up to likely
  details     {reason: {detail: visits}}: each adds up to its reason

Each likely visit's journey carries `likely_direct`: {"reason", "detail"}
and, for a preview, "minutes" (from the nearest preview to the visit). Only
names and counts are kept: never the landing address's query values.

Second count: audit_direct_likely.py, from the raw lines with its own code;
it shares only direct_names.py's lists.
"""
from __future__ import annotations

import re
from collections import Counter

from . import dimensions as dim
from .ai_likely import minute, page_key
from .classify import LINK_PREVIEW, Group
from .direct_names import (CHECKOUT_DONE, CHECKOUT_PAGES, CHECKOUT_PARAMS, CHECKOUT_SECTIONS,
                           IN_APP_BROWSERS, MANY, PAGE_ENDINGS, REASON_WORDS, REASONS,
                           RETURN_PAGE, SHARE_KEYS, SHARE_PARAMS, SHARE_TAG, SHARE_WINDOW,
                           SHARE_WORDS)

DIRECT = "Direct or unknown"
METHOD = ("Inferred, not counted: a Direct visit (no referrer, no campaign tag) is shown as "
          "likely from a checkout or payment return when its landing address carries a payment "
          "provider's return parameter or is a checkout's end page; else as likely from an "
          "in-app browser when its browser is an app's own (Instagram, Facebook, LinkedIn, "
          "TikTok, ...); else as likely a shared link when its address carries a share marker "
          "or an app fetched a link preview of that page in the same minute or up to {w} minutes "
          "before. One reason a visit at most. Likely, never certain.")
_WORD = re.compile(r"[^a-z0-9]+")
_IN_APP = frozenset(IN_APP_BROWSERS)


def settings(config: dict | None) -> dict:
    """{"on", "window"} from `attribution.direct_likely` (default true) and
    `attribution.share_window_minutes` (default 30, at least 0)."""
    got = (config or {}).get("attribution") or {}
    on = got.get("direct_likely", True) not in (False, "false", "no", "off", 0)
    try:
        window = max(0, int(got.get("share_window_minutes", SHARE_WINDOW)))
    except (TypeError, ValueError):
        window = SHARE_WINDOW
    return {"on": on, "window": window}


def note(config: dict | None) -> dict:
    """What a page says beside the figure: on or off, the window, the method."""
    got = settings(config)
    return {"on": got["on"], "share_window_minutes": got["window"],
            "method": METHOD.format(w=got["window"]), "reasons": dict(REASON_WORDS)}


class Previews:
    """The tally pass's link-preview fetches (extras.Extras offers it every hit)."""

    def __init__(self) -> None:
        self.rows: list[tuple[int, str, str]] = []      # (minute, page, app)

    def add(self, hit, verdict) -> None:
        if verdict.group is Group.BOTS and (verdict.engine or "").startswith(LINK_PREVIEW):
            self.rows.append((minute(hit.when), page_key(hit.path),
                              verdict.engine[len(LINK_PREVIEW):]))


# ------------------------------------------------------------- the rules

def _segments(url: str) -> list[str]:
    path = url.split("?", 1)[0].split("#", 1)[0]
    out = []
    for seg in path.lower().replace("_", "-").split("/"):
        for end in PAGE_ENDINGS:
            if seg.endswith(end):
                seg = seg[: -len(end)]
                break
        if seg:
            out.append(seg)
    return out


def checkout(url: str) -> str:
    """The provider of a payment return, RETURN_PAGE for a checkout's end
    page, or ""."""
    tags = dim.query(url)
    for name, prefix, provider in CHECKOUT_PARAMS:
        value = tags.get(name, "")
        if value.strip() and value.startswith(prefix):
            return provider
    segs = _segments(url)
    if any(s in CHECKOUT_PAGES for s in segs):
        return RETURN_PAGE
    for i, seg in enumerate(segs):
        if seg in CHECKOUT_DONE and any(s in CHECKOUT_SECTIONS for s in segs[:i]):
            return RETURN_PAGE
    return ""


def share_marker(url: str) -> str:
    """The app a share marker on the landing address names, SHARE_TAG, or ""."""
    tags = dim.query(url)
    for name, app in SHARE_PARAMS.items():
        if tags.get(name, "").strip():
            return app
    for key in SHARE_KEYS:
        value = tags.get(key, "").strip().lower()
        if not value:
            continue
        words = [w for w in _WORD.split(value) if w]
        for word in words + ["".join(words)]:
            if word in SHARE_WORDS:
                return SHARE_WORDS[word] or SHARE_TAG
    return ""


def reason(j: dict, url: str, at_minute: int, previews: dict, window: int) -> dict | None:
    """The likely reason of one Direct visit, or None (plain Direct)."""
    got = checkout(url)
    if got:
        return {"reason": "checkout", "detail": got}
    if j.get("browser") in _IN_APP:
        return {"reason": "in_app", "detail": j["browser"]}
    got = share_marker(url)
    if got:
        return {"reason": "shared", "detail": got}
    near: dict[str, int] = {}
    for m, app in previews.get(page_key(j.get("landing") or ""), ()):
        gap = at_minute - m
        if 0 <= gap <= window:
            near[app] = min(near.get(app, gap), gap)
    if near:
        name = next(iter(near)) if len(near) == 1 else MANY
        return {"reason": "shared", "detail": name, "minutes": min(near.values())}
    return None


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    conf = getattr(extras, "direct_likely", None) or {}
    on, window = conf.get("on", True), int(conf.get("window", SHARE_WINDOW))
    firsts = getattr(extras, "visit_firsts", None)
    landings = getattr(extras, "visit_landings", None)
    seen = getattr(extras, "link_previews", None)
    if not on or journeys is None or firsts is None or landings is None or seen is None \
            or not len(firsts) == len(landings) == len(journeys):
        return None
    previews: dict[str, list] = {}
    for m, page, app in seen.rows:
        previews.setdefault(page, []).append((m, app))
    direct = 0
    reasons: Counter = Counter({r: 0 for r in REASONS})
    details: dict[str, Counter] = {r: Counter() for r in REASONS}
    for j, first, url in zip(journeys, firsts, landings):
        if j.get("source") != DIRECT:
            continue
        direct += 1
        got = reason(j, url or "", minute(first), previews, window)
        if got is None:
            continue
        reasons[got["reason"]] += 1
        details[got["reason"]][got["detail"]] += 1
        j["likely_direct"] = got
    likely = int(sum(reasons.values()))
    return {"share_window_minutes": window, "visits": len(journeys), "direct": direct,
            "likely": likely, "plain": direct - likely,
            "reasons": {r: int(reasons[r]) for r in REASONS},
            "details": {r: dict(sorted(details[r].items())) for r in REASONS}}


def check(totals, blob, differs, problems) -> None:
    from .verify import Problem
    likely = int(blob.get("likely", 0))
    reasons = blob.get("reasons") or {}
    differs("direct_likely: likely visits by reason",
            sum(int(v) for v in reasons.values()), likely, "likely visits")
    differs("direct_likely: likely and plain visits", likely + int(blob.get("plain", 0)),
            int(blob.get("direct", 0)), "direct visits")
    for r in REASONS:
        differs(f"direct_likely: {r} by detail",
                sum(int(v) for v in ((blob.get("details") or {}).get(r) or {}).values()),
                int(reasons.get(r, 0)), f"{r} visits")
    if set(reasons) != set(REASONS):
        problems.append(Problem("direct_likely", "the reasons are not the three known ones"))
    stats = getattr(totals, "visits", None)
    if stats is not None:
        differs("direct_likely: visits", int(blob.get("visits", 0)), int(stats.visits), "visits")
        # The visits by source (the Sources tab's rows): only on a tally that
        # labelled them (visits.check holds them equal to the readers').
        if sum(stats.source.values()) == stats.visits:
            differs("direct_likely: direct visits", int(blob.get("direct", 0)),
                    int(stats.source.get(DIRECT, 0)), "visits whose source is Direct")
    if not 0 <= likely <= int(blob.get("direct", 0)) <= int(blob.get("visits", 0)):
        problems.append(Problem("direct_likely", "likely visits are not within the direct "
                                                 "visits, or the direct within the visits"))
    journeys = getattr(totals, "journeys", None)
    if journeys is not None:
        marked = Counter(j["likely_direct"]["reason"] for j in journeys if j.get("likely_direct"))
        for r in REASONS:
            differs(f"direct_likely: journeys marked {r}", int(marked.get(r, 0)),
                    int(reasons.get(r, 0)), f"{r} visits")

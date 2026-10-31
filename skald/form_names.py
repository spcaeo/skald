"""A POST that is no form: the name lists both roads share (form rule 2).

A visit "sent a form" when it made a POST (visits.py, parse.Hit.is_form_post).
A page's own script posts too, from every page view, with nobody doing
anything: on one live site (2026-10-30) each page view sent POST /api/events
four seconds after it loaded, answered 204 with no body, and 29 of 34 visits
on 24 Oct read "sent a form". A POST is no form when it is one of these, on
both roads (the audit, audit_visits.NotForm, matches them by its own code):

  skald     Skald's own endpoints: the script tag's events, signed hooks,
            shipped logs (parse.OWN_ENDPOINT), as before
  204       answered 204 with no body (0 bytes, or no size logged): a beacon
            by definition. A form's submit gets a page or a redirect back
  list      a path on SCRIPT_POSTS below: analytics and event beacons and
            error reports that pages send by themselves
  site      a path on the site's own list (site.script_posts, Settings ›
            Data › What counts › Not forms). Only a person adds one; Skald
            suggests (suggest() below), it never adds one by itself

A POST the site refused is no form either (rule 3, 2026-10-30): answered
REFUSED below, nothing at that address took it. On the same live site, after
rule 2, 18 of 34 visits on 24 Oct still read "sent a form": every one was a
scanner posting to /, /api, /app, /graphql or /xmlrpc.php and getting 301,
404, 405 or 444 back. A form that was taken answers 2xx or sends the browser
on (302, 303); one that failed on the server (5xx) or said what was wrong
(400, 403, 422, 429) still counts, as a person sent it.

WordPress's admin-ajax.php stays a form: its heartbeat cannot be told from a
real form's call in the log, unless it was answered 204 (rule 2).

The request still counts as a request of its group. Only "sent a form" (a
visit's posted flag, the POST times kept with a visit, the Form posts table,
the pages' "posts from") leaves it out.

Entries, on the list and the site's own, are matched the same way:

  /path      that path exactly, any case (ASCII letters), trailing slashes ignored
  /prefix*   every path that starts with /prefix, any case

The same log lines always give the same answer: nothing here learns by itself.
"""
from __future__ import annotations

import re
import string

# Paths pages post to by themselves. Each is a well-known beacon, analytics
# collector or error reporter, or a site's own event endpoint seen live.
SCRIPT_POSTS: tuple[str, ...] = (
    "/api/events",              # a site's own event script (seen live)
    "/api/event",               # Plausible's proxied event
    "/api/analytics",
    "/api/collect",
    "/api/track",
    "/api/sentry*",             # Sentry's tunnel, proxied
    "/monitoring",              # Sentry's Next.js tunnel route
    "/_vercel/insights/*",      # Vercel Web Analytics
    "/_vercel/speed-insights/*",
    "/cdn-cgi/rum",             # Cloudflare's browser insights
    "/ingest/*",                # PostHog's proxy
)

BEACON_STATUS = "204"
SKALD, NO_BODY, LISTED, OWN = "skald", "204", "list", "site"

# Answers that say nothing at that address takes a POST: moved (301: the
# browser sends a GET after it, what was typed is lost; 307 and 308 send the
# POST again, and that request is the one counted), not found or gone (404,
# 410), no POSTs there (405, 501), the connection closed (nginx's 444).
REFUSED: frozenset[str] = frozenset({"301", "307", "308", "404", "405", "410", "444", "501"})

# The site's own list (site.script_posts).
MAX_OWN = 20
ENTRY_LIMIT = 100

# The counting rule a day was stored with: a `counts` row (RULE_KIND,
# RULE_NAME, FORMS_RULE) beside each day stored with this rule. A day without it
# was counted when every POST but Skald's own was a form, a day with rule 2
# when a refused POST was one; its raw log is all that can recount it
# (backfill --force), and it says so where it is shown.
FORMS_RULE = 3
RULE_KIND = "visit_rule"
RULE_NAME = "forms"

# Suggestions: a POST path sent, answered 2xx, by at least half the people
# visits that sent any POST still counted as a form, and by at least a fifth
# of all the day's people visits (a site whose only form is a contact form
# is not "sent by most page views"), on SUGGEST_MIN_DAYS of the last
# SUGGEST_DAYS stored days. Read from the stored visit_post and visit_flag rows.
SUGGEST_DAYS = 14
SUGGEST_MIN_DAYS = 3
SHARE_OF_POSTING = (1, 2)       # at least 1/2 of the visits that sent a POST
SHARE_OF_VISITS = (1, 5)        # and at least 1/5 of all the visits


def clean(value) -> list[str]:
    """site.script_posts: at most MAX_OWN entries, each /path or /prefix*,
    each once. ValueError in plain words otherwise."""
    items = value.replace(",", " ").split() if isinstance(value, str) else value
    if not isinstance(items, (list, tuple)):
        raise ValueError("A list of paths: /path or /prefix*.")
    out = []
    for item in items:
        raw = item.strip() if isinstance(item, str) else ""
        if (not raw or len(raw) > ENTRY_LIMIT or ".." in raw or "#" in raw or "?" in raw
                or any(ord(c) <= 0x20 or ord(c) >= 0x7f for c in raw)):
            raise ValueError(f"An entry is /path or /prefix*, with no spaces and no ?: "
                             f"{str(item)[:40]!r}.")
        if not raw.startswith("/"):
            raise ValueError(f"An entry starts with /: {raw[:40]!r}.")
        body = raw[:-1] if raw.endswith("*") else raw
        if "*" in body:
            raise ValueError(f"A * may only end a path: {raw[:40]!r}.")
        if body.strip("/") == "":
            raise ValueError("/ alone would make every form on the site no form.")
        if raw not in out:
            out.append(raw)
    if len(out) > MAX_OWN:
        raise ValueError(f"At most {MAX_OWN} entries of your own.")
    return out


def from_config(config: dict | None) -> list[str]:
    """The site's own list from config["site"]["script_posts"] (settings_store.apply
    writes the Settings row there); an unreadable value is none, never a guess."""
    try:
        return clean(((config or {}).get("site") or {}).get("script_posts") or [])
    except ValueError:
        return []


class Paths:
    """The list and a site's own entries, compiled: entry(path) is
    "list: <entry>", "site: <entry>" or ""."""

    def __init__(self, own=()) -> None:
        self.own = tuple(own)
        each = [(f"{LISTED}: {e}", _pattern(e)) for e in SCRIPT_POSTS]
        each += [(f"{OWN}: {e}", _pattern(e)) for e in self.own]
        self._each = tuple((name, re.compile(p, re.I | re.A)) for name, p in each)
        self._any = re.compile("|".join(p for _, p in each), re.I | re.A)

    def entry(self, path: str) -> str:
        if not self._any.search(path):
            return ""
        return next((name for name, p in self._each if p.search(path)), "")


def _pattern(entry: str) -> str:
    if entry.endswith("*"):
        return "^" + re.escape(entry[:-1])
    return "^" + re.escape(entry.rstrip("/")) + "/*$"


_MADE: dict[tuple, Paths] = {}


def paths(own=()) -> Paths:
    """The compiled list for these entries, made once per distinct value."""
    key = tuple(own or ())
    got = _MADE.get(key)
    if got is None:
        got = _MADE[key] = Paths(key)
    return got


def why_not_a_form(method: str, path: str, status: str, size, listed: Paths,
                   own_endpoint) -> str:
    """The main road's answer for one request: "" for a form (or no POST),
    else the reason (SKALD, NO_BODY, "list: ...", "site: ...").
    `own_endpoint(path)` is parse.OWN_ENDPOINT's match."""
    if method != "POST":
        return ""
    if own_endpoint(path):
        return SKALD
    if status == BEACON_STATUS and not size:
        return NO_BODY
    return listed.entry(path)


def covered(path: str, own=()) -> bool:
    """Whether a path is already no form by the list or the site's entries."""
    return bool(paths(own).entry(path))


_LOW = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


def suggest(history_db, site: str, last, own=(), days: int = SUGGEST_DAYS) -> list[dict]:
    """The POST paths that look like the site's own script, newest evidence
    first: [{"path", "days", "visits", "of_posting", "of_all", "day"}], the
    figures of its busiest qualifying day. From the stored days only (counts
    kinds visit_post, visit_flag, visit_pages). A path already on the list or
    the site's own is not suggested again."""
    from datetime import timedelta
    first = last - timedelta(days=days - 1)
    rows = history_db.execute(
        "SELECT c.day, c.kind, c.name, c.n FROM counts c JOIN days d "
        "ON d.site = c.site AND d.day = c.day AND d.verified = 1 "
        "WHERE c.site = ? AND c.day BETWEEN ? AND ? "
        "AND c.kind IN ('visit_post', 'visit_flag', 'visit_pages')",
        (site, first.isoformat(), last.isoformat())).fetchall()
    per_day: dict[str, dict] = {}
    for day, kind, name, n in rows:
        got = per_day.setdefault(day, {"posting": 0, "visits": 0, "paths": {}})
        if kind == "visit_flag" and name == "posted":
            got["posting"] = int(n)
        elif kind == "visit_pages":
            got["visits"] += int(n)
        elif kind == "visit_post" and name.startswith("/"):
            got["paths"][name] = int(n)
    found: dict[str, dict] = {}
    for day in sorted(per_day):
        got = per_day[day]
        posting, visits = got["posting"], got["visits"]
        for path, n in got["paths"].items():
            if not posting or not visits or covered(path, own):
                continue
            if n * SHARE_OF_POSTING[1] < posting * SHARE_OF_POSTING[0] or \
                    n * SHARE_OF_VISITS[1] < visits * SHARE_OF_VISITS[0]:
                continue
            row = found.setdefault(path, {"path": path, "days": 0, "visits": 0,
                                          "of_posting": 0, "of_all": 0, "day": ""})
            row["days"] += 1
            if n >= row["visits"]:
                row.update(visits=n, of_posting=posting, of_all=visits, day=day)
    out = [r for r in found.values() if r["days"] >= SUGGEST_MIN_DAYS]
    return sorted(out, key=lambda r: (-r["days"], r["path"].translate(_LOW), r["path"]))

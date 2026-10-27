"""Calendly history: Calendly's own bookings over a window, by status and by event
type, read with a personal access token through the Calendly API v2 (docs/TOOLS.md).

Skald already receives each new booking by Calendly's webhook
(conversions/adapters/calendly.py), as a lead. This tool is apart from that: it
shows Calendly's own history and figures, never makes a lead, never changes or
duplicates a webhook row. The admins' drawer says how many of the bookings it lists
the webhook also sent ("matched on the event URI": a webhook row's reference is the
invitee's URI, which starts with its meeting's URI), counted twice: here in Python,
and by recount.webhook_match's own SQL; when they differ the line is withheld.

The calls (GET only, https://api.calendly.com):
  /users/me                        the token's user, its URI and organisation
  /scheduled_events?user=...       (or organization=..., option scope) every meeting
                                   whose start is CALENDLY_PAST days back to
                                   CALENDLY_AHEAD days ahead, 100 a page, at most
                                   MAX_PAGES pages; more: the counts are NULL
  <meeting URI>/invitees           for the past active meetings (no-shows; at most
                                   MAX_INVITEE_READS) and the RECENT newest bookings

Kept from each record only what Skald reads: a meeting's URI, name, status, start,
end, event type, creation and cancellation time; an invitee's URI, meeting, status,
times, no-show time, and name and email only as the site's People settings keep a
lead's (conversions.identity, privacy.keep_days: scrub). The counts are names.py's
CALENDLY_* rules; recount._calendly counts the same again by its own code.

The key: a personal access token with the scopes users:read and scheduled_events:read
only (Calendly's read scopes). A token made before Calendly had scopes can do what its
account can; Skald only reads with it.
"""
from __future__ import annotations

import copy
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import timedelta, timezone
from pathlib import Path

from ..search import http
from .base import Adapter, Answer, BadKey, Figure, Option, Unreachable, kept_person, \
    plain_key_words, pointer, when
from .names import CALENDLY_ACTIVE, CALENDLY_AHEAD, CALENDLY_CANCELED, CALENDLY_COUNTS, \
    CALENDLY_LABELS, CALENDLY_PAST, NONE_DIM

API = "https://api.calendly.com"
MAX_PAGES = 20                      # of 100 meetings each
MAX_INVITEE_READS = 150             # past meetings whose invitees are read (no-shows)
INVITEE_PAGES = 3
RECENT = 10                         # the newest bookings the drawer lists
EVENT = re.compile(r"/scheduled_events/[A-Za-z0-9-]{1,80}")
TOKEN = re.compile(r"[A-Za-z0-9._-]{20,4000}")
EVENT_KEEP = ("uri", "name", "status", "start_time", "end_time", "event_type", "created_at",
              "updated_at")
INVITEE_KEEP = ("uri", "event", "status", "created_at", "updated_at", "rescheduled",
                "name", "email")


def _event(e: dict) -> dict:
    out = {k: e.get(k) for k in EVENT_KEEP}
    cancel = e.get("cancellation") if isinstance(e.get("cancellation"), dict) else None
    out["cancellation"] = ({"canceler_type": cancel.get("canceler_type"),
                            "created_at": cancel.get("created_at")} if cancel else None)
    return out


def _invitee(i: dict) -> dict:
    out = {k: i.get(k) for k in INVITEE_KEEP}
    show = i.get("no_show") if isinstance(i.get("no_show"), dict) else None
    out["no_show"] = {"created_at": show.get("created_at")} if show else None
    return out


def counts(body: dict) -> tuple[dict, list]:
    """({count name: value or None}, [(event type name, meetings, first index)])."""
    events = body.get("events") or []
    asked = when(body.get("asked_at"))
    if not body.get("complete") or asked is None:
        return {n: None for n in CALENDLY_COUNTS}, []
    day0 = asked.replace(hour=0, minute=0, second=0, microsecond=0)
    active = [e for e in events if e.get("status") == CALENDLY_ACTIVE]
    past = {e["uri"] for e in active if (when(e.get("start_time")) or asked) < asked}

    def made(lo: int, hi: int) -> int:
        a, b = day0 - timedelta(days=lo), day0 - timedelta(days=hi)
        return sum(1 for e in events if (t := when(e.get("created_at"))) and a <= t < b)

    read = set(body.get("invitees_read") or [])
    no_shows = None
    if body.get("no_shows_complete") and past <= read:
        no_shows = sum(1 for i in body.get("invitees") or []
                       if i.get("event") in past and i.get("no_show"))
    out = {"bookings": len(events), "upcoming": len(active) - len(past), "past": len(past),
           "canceled": sum(1 for e in events if e.get("status") == CALENDLY_CANCELED),
           "no_shows": no_shows, "booked_7d": made(7, 0), "booked_prev_7d": made(14, 7)}
    first: dict = {}
    per: Counter = Counter()
    for i, e in enumerate(events):
        name = e.get("name") or NONE_DIM
        per[name] += 1
        first.setdefault(name, i)
    rows = [(name, n, first[name]) for name, n in sorted(per.items(), key=lambda x: (-x[1], x[0]))]
    return out, rows


class Calendly(Adapter):
    id = "calendly"
    name = "Calendly"
    key_words = "a Calendly personal access token"
    permission = ("the read scopes users:read and scheduled_events:read only. A token made "
                  "before Calendly had scopes can do everything its account can; Skald only "
                  "reads with it")
    make_key = ("Calendly > Integrations & apps > API and webhooks > Personal access tokens > "
                "Generate new token, with only users:read and scheduled_events:read "
                "(https://calendly.com/integrations/api_webhooks)")
    env_names = ("CALENDLY_TOKEN", "CALENDLY_API_KEY", "CALENDLY_PAT", "CALENDLY_ACCESS_TOKEN",
                 "CALENDLY_PERSONAL_ACCESS_TOKEN")
    options = {"scope": Option(
        "Whose bookings", r"me|organization",
        "me: the token's own bookings (the default). organization: every member's; the "
        "token's owner must be an owner or admin of the Calendly organisation.",
        required=False, example="me")}
    key_most = 4096
    latest_only = True
    notes = ("Calendly's own history and figures. New bookings also reach Skald by the "
             "Calendly webhook, as leads; this tool never makes a lead and never changes one.",
             "Names and emails follow this site's People settings, as a lead's do.")

    def __init__(self, api: str = API) -> None:
        self.api = api.rstrip("/")

    def check_key(self, text: str) -> dict:
        got = plain_key_words(text, self.key_most)
        if not TOKEN.fullmatch(got):
            raise BadKey("That is not a Calendly personal access token: one line of letters, "
                         "digits, dots and dashes, with no spaces.")
        return {"who": f"a Calendly token ending ...{got[-4:]}"}

    def _get(self, path: str, params: dict, key: str, opener, sleep) -> dict:
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        request = urllib.request.Request(f"{self.api}{path}{query}", method="GET", headers={
            "Authorization": f"Bearer {key}", "Accept": "application/json"})
        try:
            return http.call(request, opener, sleep, hide=(key,))
        except http.Failed as why:
            raise Unreachable(_words(why), why.code) from None

    def _invitees(self, uri: str, key: str, opener, sleep) -> list[dict]:
        path = urllib.parse.urlsplit(str(uri))
        if f"{path.scheme}://{path.netloc}" != self.api or not EVENT.fullmatch(path.path):
            raise Unreachable("Calendly named a meeting Skald cannot read (not on its API).", 200)
        out, token = [], None
        for _ in range(INVITEE_PAGES):
            got = self._get(f"{path.path}/invitees", {"count": 100, **(
                {"page_token": token} if token else {})}, key, opener, sleep)
            out += [_invitee(i) for i in got.get("collection") or [] if isinstance(i, dict)]
            token = (got.get("pagination") or {}).get("next_page_token")
            if not token:
                break
        return out

    def fetch(self, key, options, now, opener=None, sleep=None) -> list[Answer]:
        sleep = sleep or time.sleep
        asked = now.astimezone(timezone.utc).replace(microsecond=0)
        start = asked.date() - timedelta(days=CALENDLY_PAST)
        end = asked.date() + timedelta(days=CALENDLY_AHEAD)
        res = self._get("/users/me", {}, key, opener, sleep).get("resource") or {}
        user = {k: res.get(k) for k in ("uri", "current_organization", "timezone")}
        scope = (options or {}).get("scope") or "me"
        owner = user["current_organization"] if scope == "organization" else user["uri"]
        if not owner:
            raise Unreachable("Calendly did not name the token's user or organisation.", 200)
        params = {"count": 100, "sort": "start_time:asc",
                  "min_start_time": f"{start}T00:00:00.000000Z",
                  "max_start_time": f"{end + timedelta(days=1)}T00:00:00.000000Z",
                  "organization" if scope == "organization" else "user": owner}
        events, token, seen, complete = [], None, set(), False
        for _ in range(MAX_PAGES):
            got = self._get("/scheduled_events", {**params, **(
                {"page_token": token} if token else {})}, key, opener, sleep)
            page = got.get("collection")
            if not isinstance(page, list):
                raise Unreachable("Calendly's answer had no list of meetings.", 200)
            events += [_event(e) for e in page if isinstance(e, dict) and e.get("uri")]
            token = (got.get("pagination") or {}).get("next_page_token")
            if not token:
                complete = True
                break
            if token in seen:
                raise Unreachable("Calendly's pages did not move on.", 200)
            seen.add(token)
        past = sorted((e for e in events if e.get("status") == CALENDLY_ACTIVE
                       and (when(e.get("start_time")) or asked) < asked),
                      key=lambda e: e.get("start_time") or "", reverse=True)
        recent = sorted(events, key=lambda e: e.get("created_at") or "", reverse=True)[:RECENT]
        wanted = [e["uri"] for e in past[:MAX_INVITEE_READS]]
        wanted += [e["uri"] for e in recent if e["uri"] not in wanted]
        invitees = []
        for uri in wanted:
            invitees += self._invitees(uri, key, opener, sleep)
        body = {"asked_at": asked.isoformat(), "scope": scope, "user": user, "events": events,
                "complete": complete, "invitees": invitees, "invitees_read": wanted,
                "no_shows_complete": len(past) <= MAX_INVITEE_READS}
        return [Answer(report="totals", period=f"{start}..{end}", start=start.isoformat(),
                       end=end.isoformat(),
                       request={"scope": scope, "min_start_time": params["min_start_time"],
                                "max_start_time": params["max_start_time"]},
                       body=body, flags={"incomplete": not complete,
                                         "no_shows_partial": not body["no_shows_complete"]},
                       note=f"meetings by their start, {CALENDLY_PAST} days back to "
                            f"{CALENDLY_AHEAD} ahead, UTC")]

    def scrub(self, answer: Answer, policy: dict) -> Answer:
        body = copy.deepcopy(answer.body)
        for i in body.get("invitees") or []:
            if not kept_person(i.get("created_at"), policy):
                i.pop("name", None)
                i.pop("email", None)
        answer.body = body
        return answer

    def figures(self, answer: Answer) -> list[Figure]:
        got, rows = counts(answer.body)
        out = [Figure(name=n, value=got[n], label=CALENDLY_LABELS[n]) for n in CALENDLY_COUNTS]
        for rank, (name, n, i) in enumerate(rows):
            out.append(Figure(name="bookings", value=n, label=CALENDLY_LABELS["bookings"],
                              dim=name, rank=rank,
                              dim_src=pointer("events", i, "name") if name != NONE_DIM else None))
        return out

    def headline(self, figures: list[Figure]) -> list[Figure]:
        by = {f.name: f for f in figures if f.dim is None}
        return [by[n] for n in ("booked_7d", "upcoming", "canceled") if n in by]

    def more(self, ctx: dict) -> dict:
        body = next((a["body"] for a in ctx["answers"] if a["report"] == "totals"), None) or {}
        events = body.get("events") or []
        lines = [webhook_line(ctx, [e["uri"] for e in events])] if events else []
        by_event: dict = {}
        for i in body.get("invitees") or []:
            by_event.setdefault(i.get("event"), []).append(i)
        people = []
        for e in sorted(events, key=lambda e: e.get("created_at") or "", reverse=True)[:RECENT]:
            for i in by_event.get(e["uri"]) or [{}]:
                state = "no-show" if i.get("no_show") else (i.get("status") or e.get("status"))
                people.append({"when": i.get("created_at") or e.get("created_at"),
                               "what": e.get("name"), "start": e.get("start_time"),
                               "state": state, "name": i.get("name"), "email": i.get("email")})
        if people and not any(p["name"] or p["email"] for p in people):
            lines.append("No names or emails are kept: this site's People settings keep none "
                         "for these bookings.")
        return {"lines": lines, "people": people[:RECENT]}


def webhook_refs(config: dict, folder, site: str) -> set | None:
    """The meetings the Calendly webhook sent Skald: each reference's meeting URI
    (the invitee's URI up to /invitees/). None without a conversions file."""
    from ..conversions import store
    path = store.path_for(config, Path(folder))
    if path is None or not Path(path).is_file():
        return None
    import sqlite3
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    try:
        refs = [r[0] for r in db.execute("SELECT DISTINCT external_ref FROM conversions WHERE "
                                         "site = ? AND tool = 'calendly'", (site,))]
    finally:
        db.close()
    return {str(r).split("/invitees/", 1)[0] for r in refs if "/invitees/" in str(r)}


def webhook_line(ctx: dict, uris: list[str]) -> str:
    """"N of the bookings ... the webhook also has; M it does not", counted twice."""
    from . import recount
    from ..conversions import store
    refs = webhook_refs(ctx["config"], ctx["folder"], ctx["site"])
    total = len(uris)
    if not refs:
        return (f"The Calendly webhook has sent Skald none of these {total} bookings (it may "
                "not be set up, or it started later): they are in Calendly's figures only.")
    mine = sum(1 for u in uris if u in refs)
    path = store.path_for(ctx["config"], Path(ctx["folder"]))
    if recount.webhook_match(path, ctx["site"], uris) != mine:
        return ("The bookings the webhook also has are withheld: Skald's two counts of them "
                "differ.")
    return (f"Of these {total} bookings, {mine} reached Skald by the webhook too (matched on "
            f"the meeting's address); {total - mine} did not (the webhook was off or started "
            "later, or its event type is not kept).")


def _words(why: http.Failed) -> str:
    detail = f" (Calendly said: {why.detail})" if why.detail else ""
    if why.code == 401:
        return ("Calendly refused the token: it was revoked or has expired. Make a new one "
                "and paste it again." + detail)
    if why.code == 403:
        return ("Calendly refused: the token lacks a read scope (users:read, "
                "scheduled_events:read), or reading the organisation's bookings needs an "
                "organisation admin's token." + detail)
    if why.code == 404:
        return "Calendly has no such user or organisation for this token." + detail
    if why.code == 429:
        return "Calendly's rate limit is reached for now; the next sync tries again." + detail
    if why.code == 0:
        return f"Could not reach Calendly: {why}"
    return f"Calendly answered {why.code}." + detail


ADAPTER = Calendly()

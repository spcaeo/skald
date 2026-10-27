"""Resend: contacts (subscribed or not), contacts per segment, and the delivery
states of the most recent emails, read with the site's Resend API key (GET only,
https://api.resend.com; docs/TOOLS.md).

  totals    GET /contacts?limit=100, page after page (`after`, while `has_more`), at
            most MAX_PAGES: contacts, subscribed (`unsubscribed` false), unsubscribed
  segments  GET /segments, then GET /contacts?segment_id=... for each of the first
            MAX_SEGMENTS: each segment's contacts. Resend's segments were its
            "audiences" before late 2025
  emails    GET /emails?limit=100: Resend's newest RESEND_EMAILS emails sent, by
            each one's `last_event` (delivered, bounced, opened...)

Not every page read: that count is NULL ("Not given"), never a short count. Resend
allows two requests a second; Skald waits GAP seconds between calls.

Kept from each record only what Skald reads: a contact's id, time and
unsubscribed; a segment's id, name and its contacts' ids; an email's id, time
and last event. Addresses only for the RECENT newest contacts and emails, and only
as the site's People settings keep a lead's (conversions.identity,
privacy.keep_days: scrub). A delivery state is Resend's own last event: delivered
means the receiving server took it, not that anyone read it.

The key: Resend's keys are full access or sending only; a sending-only key cannot
read contacts or emails, so Skald needs a full-access key. Skald only reads with it.
"""
from __future__ import annotations

import copy
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import timezone

from ..search import http
from .base import Adapter, Answer, BadKey, Figure, Unreachable, kept_person, \
    plain_key_words, pointer
from .names import NONE_DIM, RESEND_EMAILS, RESEND_LABELS, RESEND_TOTALS

API = "https://api.resend.com"
MAX_PAGES = 50                  # of 100 contacts: 5,000 a list at most
MAX_SEGMENTS = 20
RECENT = 10
GAP = 0.6                       # seconds between calls: Resend allows two a second
KEY = re.compile(r"re_[A-Za-z0-9_-]{8,200}")


def counts(body: dict) -> dict:
    contacts = body.get("contacts") or []
    if not body.get("complete"):
        return {n: None for n in RESEND_TOTALS}
    return {"contacts": len(contacts),
            "subscribed": sum(1 for c in contacts if c.get("unsubscribed") is False),
            "unsubscribed": sum(1 for c in contacts if c.get("unsubscribed") is True)}


class Resend(Adapter):
    id = "resend"
    name = "Resend"
    key_words = "a Resend API key (re_...)"
    permission = ("Full access. Resend's keys are full access or sending only, and a "
                  "sending-only key cannot read contacts or emails. Skald only reads with it "
                  "(GET): it never sends, changes or deletes anything")
    make_key = ("Resend > API Keys > Create API key, permission Full access "
                "(https://resend.com/api-keys)")
    env_names = ("RESEND_API_KEY", "RESEND_KEY", "RESEND_TOKEN")
    key_most = 400
    latest_only = True
    notes = ("Resend's own contacts and emails, apart from Skald's leads.",
             "A delivery state is Resend's last event for an email: delivered means the "
             "receiving server took it, not that anyone read it.",
             "Email addresses follow this site's People settings, as a lead's do.")

    def __init__(self, api: str = API) -> None:
        self.api = api.rstrip("/")

    def check_key(self, text: str) -> dict:
        got = plain_key_words(text, self.key_most)
        if not KEY.fullmatch(got):
            raise BadKey("That is not a Resend API key: it starts with re_ and has no spaces.")
        return {"who": f"a Resend key ending ...{got[-4:]}"}

    def _get(self, path: str, params: dict, key: str, opener, sleep) -> dict:
        sleep(GAP)
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        request = urllib.request.Request(f"{self.api}{path}{query}", method="GET", headers={
            "Authorization": f"Bearer {key}", "Accept": "application/json"})
        try:
            return http.call(request, opener, sleep, hide=(key,))
        except http.Failed as why:
            raise Unreachable(_words(why), why.code) from None

    def _list(self, path: str, params: dict, key, opener, sleep, pages=MAX_PAGES):
        """(every row, read to the end) of a Resend list, page after page."""
        rows, after, seen = [], None, set()
        for _ in range(pages):
            got = self._get(path, {**params, **({"after": after} if after else {})}, key,
                            opener, sleep)
            data = got.get("data")
            if not isinstance(data, list):
                raise Unreachable("Resend's answer had no list (data).", 200)
            rows += [r for r in data if isinstance(r, dict)]
            if not got.get("has_more") or not data:
                return rows, True
            after = str(data[-1].get("id") or "")
            if not after or after in seen:
                raise Unreachable("Resend's pages did not move on.", 200)
            seen.add(after)
        return rows, False

    def fetch(self, key, options, now, opener=None, sleep=None) -> list[Answer]:
        sleep = sleep or time.sleep
        asked = now.astimezone(timezone.utc).replace(microsecond=0)
        day = asked.date().isoformat()
        rows, complete = self._list("/contacts", {"limit": 100}, key, opener, sleep)
        newest = {c.get("id") for c in sorted(rows, key=lambda c: str(c.get("created_at") or ""),
                                              reverse=True)[:RECENT]}
        contacts = [{"id": c.get("id"), "created_at": c.get("created_at"),
                     "unsubscribed": c.get("unsubscribed"),
                     **({"email": c.get("email")} if c.get("id") in newest else {})}
                    for c in rows]
        segs, segs_whole = self._list("/segments", {"limit": 100}, key, opener, sleep, pages=5)
        segments = []
        for n, s in enumerate(segs):
            one = {"id": s.get("id"), "name": s.get("name"), "created_at": s.get("created_at"),
                   "contacts": None, "complete": False}
            if n < MAX_SEGMENTS and s.get("id"):
                got, whole = self._list("/contacts", {"limit": 100, "segment_id": s["id"]},
                                        key, opener, sleep)
                one.update(contacts=[c.get("id") for c in got], complete=whole)
            segments.append(one)
        got = self._get("/emails", {"limit": RESEND_EMAILS}, key, opener, sleep)
        data = got.get("data")
        if not isinstance(data, list):
            raise Unreachable("Resend's answer had no list of emails (data).", 200)
        emails = [{"id": e.get("id"), "created_at": e.get("created_at"),
                   "last_event": e.get("last_event"),
                   **({"to": e.get("to")} if i < RECENT else {})}
                  for i, e in enumerate(r for r in data if isinstance(r, dict))]
        times = sorted(str(e["created_at"])[:10] for e in emails if e.get("created_at"))
        note = "as Resend had them when Skald asked (UTC)"
        return [
            Answer("totals", day, day, day, {"path": "/contacts"},
                   {"asked_at": asked.isoformat(), "contacts": contacts, "complete": complete},
                   flags={"incomplete": not complete}, note=note),
            Answer("segments", day, day, day, {"path": "/segments"},
                   {"segments": segments, "complete": segs_whole},
                   flags={"incomplete": not segs_whole or not all(
                       s["complete"] for s in segments)}, note=note),
            Answer("emails", day, times[0] if times else None, times[-1] if times else None,
                   {"path": "/emails", "limit": str(RESEND_EMAILS)},
                   {"emails": emails, "has_more": bool(got.get("has_more"))},
                   flags={"recent_only": bool(got.get("has_more"))},
                   note=f"the newest {len(emails)} emails Resend lists")]

    def scrub(self, answer: Answer, policy: dict) -> Answer:
        body = copy.deepcopy(answer.body)
        for c in body.get("contacts") or []:
            if "email" in c and not kept_person(c.get("created_at"), policy):
                c.pop("email")
        for e in body.get("emails") or []:
            if "to" in e and not kept_person(e.get("created_at"), policy):
                e.pop("to")
        answer.body = body
        return answer

    def figures(self, answer: Answer) -> list[Figure]:
        body = answer.body
        if answer.report == "totals":
            got = counts(body)
            return [Figure(name=n, value=got[n], label=RESEND_LABELS[n]) for n in RESEND_TOTALS]
        if answer.report == "segments":
            out = []
            for i, s in enumerate(body.get("segments") or []):
                ok = s.get("complete") and isinstance(s.get("contacts"), list)
                out.append(Figure(name="contacts", label=RESEND_LABELS["contacts"], rank=i,
                                  value=len(s["contacts"]) if ok else None,
                                  dim=str(s.get("name") or NONE_DIM),
                                  dim_src=pointer("segments", i, "name") if s.get("name")
                                  else None))
            return out
        emails = body.get("emails") or []
        out = [Figure(name="emails", value=len(emails), label=RESEND_LABELS["emails"])]
        per = Counter(str(e.get("last_event") or NONE_DIM) for e in emails)
        first = {}
        for i, e in enumerate(emails):
            first.setdefault(str(e.get("last_event") or NONE_DIM), i)
        for rank, (state, n) in enumerate(sorted(per.items(), key=lambda x: (-x[1], x[0]))):
            out.append(Figure(name="emails", value=n, label=RESEND_LABELS["emails"], dim=state,
                              rank=rank, dim_src=pointer("emails", first[state], "last_event")
                              if state != NONE_DIM else None))
        return out

    def headline(self, figures: list[Figure]) -> list[Figure]:
        by = {f.name: f for f in figures if f.dim is None}
        return [by[n] for n in RESEND_TOTALS if n in by]

    def more(self, ctx: dict) -> dict:
        bodies = {a["report"]: a["body"] for a in ctx["answers"]}
        people = []
        for e in ((bodies.get("emails") or {}).get("emails") or [])[:RECENT]:
            to = e.get("to")
            people.append({"when": e.get("created_at"), "what": "Email",
                           "state": e.get("last_event"),
                           "email": ", ".join(to) if isinstance(to, list) else to})
        contacts = sorted((bodies.get("totals") or {}).get("contacts") or [],
                          key=lambda c: str(c.get("created_at") or ""), reverse=True)[:RECENT]
        for c in contacts:
            people.append({"when": c.get("created_at"), "what": "New contact",
                           "state": "unsubscribed" if c.get("unsubscribed") else "subscribed",
                           "email": c.get("email")})
        return {"people": people}


def _words(why: http.Failed) -> str:
    detail = f" (Resend said: {why.detail})" if why.detail else ""
    if why.code in (401, 403) and "restrict" in (why.detail or "").lower() + str(why).lower():
        return ("This Resend key can only send emails. Skald needs a full-access key to read "
                "contacts and emails; it only reads with it." + detail)
    if why.code in (401, 403):
        return ("Resend refused the key: it was deleted, or it can only send emails (Skald "
                "needs full access to read contacts and emails)." + detail)
    if why.code == 404:
        return "Resend has no such list for this key." + detail
    if why.code == 429:
        return "Resend's rate limit is reached for now; the next sync tries again." + detail
    if why.code == 0:
        return f"Could not reach Resend: {why}"
    return f"Resend answered {why.code}." + detail


ADAPTER = Resend()

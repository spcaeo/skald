#!/usr/bin/env python3
"""Build the public demo dashboard: sample data through the real pipeline, as static files.

    python3 tools/demo.py OUT [--now 2026-10-12T15:00:00Z] [--days 62] [--keep DIR]
                              [--repo-url https://github.com/<owner>/<repo>]

OUT is wiped and written again (only a folder this tool wrote, or an empty
one). It is served as it is, from any path, e.g. GitHub Pages at /<repo>/:

    OUT/index.html                     sends the reader to traffic/example.com/
    OUT/traffic/                       the dashboard folder (dashboard.out), as nginx serves it
    OUT/traffic/example.com/data/demo/ the helper's compare and page-story answers, worked
                                       out here for the periods and pages the demo offers

The data: a small fictional SaaS on example.com (tools/demo_traffic.py), with
RFC 5737 addresses and made-up names. It goes in through the same roads a real
install uses: an nginx access log, the beacon spool (and what the beacon helper
records for journeys and conversions), signed Calendly and Stripe webhooks through
the hook receiver, and the site's lead store. Then `backfill` day by day, the
in-page events, and `live`, in a temporary install that is removed afterwards
(--keep DIR keeps it in DIR).

Seeded: the same --now and --days give the same traffic. --now defaults to a few
minutes ago, so the demo's "today" is the day it was built.

--keep DIR is a whole install: `python3 bin/skald --config DIR/config.yml audit --day D`
recounts any stored day. Its made-up visitor key is in DIR/visitor.env
(report.env_file), so the visitor hashes are recounted too (a key set in the shell
wins over it). As on a real install the hashes are kept 30 days: a day older than
that says its visitor hashes, and a day whose 30-day window reaches past that its
returning readers, are "not checkable (inputs expired)"; so is the first touch of a
day counted while visitor IDs' page views (kept 30 days unless the ID converted) now
pruned were still kept: every day but the last few. Everything else matches.

app.json gets "demo": {...}: the page then works without a helper. What needs a
running install (refresh, saving, settings, team, integrations, the person
search) says so politely; compare, page story and the lists of what the figures
leave out (spam, duplicate and test leads; cancelled, removed and test
conversions) read the files in data/demo/ (DATA-CONTRACT.md, the compare and
page answers; DATA-CONTRACT-PEOPLE.md, the lists).

Standard library only (the tiny MaxMind writer and the hook test double come from tests/).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT), str(ROOT / "tests")]
# A fixed, made-up key for the 30-day visitor codes, set only while the demo builds:
# its codes are the same every build.
KEY_VAR, DEMO_KEY = "SKALD_VISITOR_KEY", "ab" * 32

import demo_answers as da  # noqa: E402
import demo_traffic as dt  # noqa: E402

MARKER = ".skald-demo"
REPO_URL = "https://github.com/spcaeo/skald"
UTC = timezone.utc
DEMO_LEAD_DAYS = 120   # the Leads list's answer covers every period the demo offers

# ------------------------------------------------------------- the install


def config_text(root: Path) -> str:
    return f"""site:
  name: example.com
  hosts: [example.com, www.example.com]
  require_rendering: false
  logo_color: "#1d4ed8"     # the letter tile on blue (the page has no helper to serve an image)
logs:
  dir: {root / 'logs'}
  base: access.log
  days: 2
  format: auto
  city_db: {root / 'city.mmdb'}
ours:
  addresses:
    - {{ip: {dt.OFFICE}, label: office}}
report:
  session_gap_minutes: 30
  timezone: {dt.TZ_NAME}
  coverage_gap_minutes: 1440
  env_file: {root / 'visitor.env'}     # the demo's made-up visitor key, for runs after the build
history:
  db: history.sqlite
dashboard:
  out: www
  url: https://analytics.example.com/traffic/example.com/
  app: true
  refresh_button: true
  views:
    - {{name: Blog, path_prefix: /blog/}}
leads:
  db: {root / 'leads.db'}
beacon:
  enabled: true
  origins:
    - https://example.com
  visitor_ids: true
  goals: [signup_start, form_start, calendly_time_selected]
conversions:
  abandon_hours: 24
  country_db: {root / 'country.mmdb'}
bots:
  ranges_dir: {root / 'ranges'}
hooks:
  public_url: https://analytics.example.com
"""


def ranges(root: Path, now: datetime) -> None:
    folder = root / "ranges"
    folder.mkdir()
    stamp = now.isoformat(timespec="seconds")
    for name, nets in dt.RANGES.items():
        (folder / f"{name}.json").write_text(json.dumps({"source": "demo", "fetched": stamp, "networks": nets,
                                                         "error": None, "tried": stamp}) + "\n")


def robots(root: Path, now: datetime) -> None:
    """The site's robots.txt, as if fetched a minute ago (so no run fetches it)."""
    (root / "robots.txt").write_text("User-agent: *\nDisallow: /signup/thanks\n\nUser-agent: CCBot\nDisallow: /\n\n"
                                     "User-agent: Bytespider\nDisallow: /\n\nSitemap: https://example.com/sitemap.xml\n")
    stamp = now.isoformat(timespec="seconds")
    (root / "robots-state.json").write_text(json.dumps({"ok": True, "error": None, "url": "https://www.example.com/robots.txt",
                                                        "fetched_at": stamp, "tried_at": stamp}, sort_keys=True) + "\n")


def sitemaps(root: Path, traffic: dt.Traffic) -> None:
    """The site's sitemap as the live run keeps it (sitemap.py), one list per day, as if
    each had been fetched that morning (so no run fetches it). It lists pages no crawler
    asks for, a guide that is gone (404) and, from ten days ago, a changelog; it leaves
    out one guide the crawlers do fetch."""
    from skald import sitemap
    pages = sorted({p for p, _ in dt._PAGES} - {dt.GUIDES[-1]}
                   | {"/customers/", "/about/", "/contact/", "/blog/", "/book-a-demo/", "/guides/api-v1"})
    d = traffic.first
    while d <= traffic.today:
        listed = pages + (["/changelog/"] if (traffic.today - d).days < 10 else [])
        got = {"paths": sorted(listed), "sources": ["https://example.com/sitemap.xml",
                                                    "https://example.com/sitemap-blog.xml"],
               "skipped": 0, "truncated": False}
        sitemap.keep(root, d, got, datetime(d.year, d.month, d.day, 11, tzinfo=UTC).isoformat())
        d += timedelta(days=1)
    stamp = traffic.now.isoformat(timespec="seconds")
    (root / sitemap.STATE).write_text(json.dumps({"ok": True, "error": None, "tried_at": stamp, "fetched_at": stamp,
                                                  "urls": ["https://example.com/sitemap.xml", "https://example.com/sitemap-blog.xml"]},
                                                 sort_keys=True) + "\n")


LEADS_SCHEMA = """
CREATE TABLE `submissions` (
  `id` integer PRIMARY KEY NOT NULL, `type` text NOT NULL, `email` text,
  `fields` text NOT NULL, `consent` integer DEFAULT false, `ip_hash` text, `locale` text,
  `updated_at` text NOT NULL, `created_at` text NOT NULL,
  `status` text DEFAULT 'new' NOT NULL, `notes` text, `duplicate_of_id` integer,
  `name` text, `company` text, `source` text, `ai_source` text, `page` text,
  `first_touch` text, `last_touch` text, `session_id` text, `pages_viewed` numeric,
  `visits` numeric, `flags` text, `fill_seconds` numeric, `browser` text,
  `ip_country` text, `external_ref` text, `delivery_team` text, `delivery_sender` text);
"""


# Made-up names for the demo's leads (Leads & sales > Leads shows them to admins). Picked
# by the lead's number, not drawn from the seeded random source, so the traffic stays as it was.
FIRST_NAMES = ("Avery", "Jordan", "Riley", "Morgan", "Casey", "Quinn", "Rowan", "Sasha", "Taylor", "Emerson", "Hayden", "Parker", "Reese")
LAST_NAMES = ("Lane", "Pike", "Okafor", "Lindqvist", "Moreau", "Tanaka", "Haddad", "Novak", "Silva", "Brennan", "Kowalski")


def demo_name(i: int) -> str:
    return f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[(i * 7) % len(LAST_NAMES)]}"


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def leads_db(path: Path, traffic: dt.Traffic, rnd) -> None:
    """The site's own lead store (docs/LEADS.md): the form rows, a few of them spam."""
    db = sqlite3.connect(path)
    db.executescript(LEADS_SCHEMA)
    statuses = [("new", 34), ("contacted", 22), ("qualified", 16), ("won", 10), ("lost", 8)]
    rows = list(traffic.leads)
    span = max(2, int((traffic.now - datetime.combine(traffic.first, datetime.min.time(), UTC)).total_seconds() // 3600))
    for _ in range(max(2, (traffic.today - traffic.first).days // 7)):
        rows.append({"at": traffic.now - timedelta(hours=rnd.randrange(2, span)), "type": "contact", "vid": None,
                     "first": None, "last": None, "visits": None, "cc": "", "spam": True})
    rows.sort(key=lambda r: r["at"])

    def touch(t):
        if not t:
            return None
        return json.dumps({"at": _iso(t["at"]), "landingPath": t.get("landingPath", "/"),
                           "referrerHost": t.get("referrerHost", ""), "utmSource": t.get("utmSource", ""),
                           "utmMedium": t.get("utmMedium", ""), "utmCampaign": t.get("utmCampaign", ""),
                           "utmTerm": "", "utmContent": "", "gclid": t.get("gclid", ""), "msclkid": "",
                           "fbclid": "", "aiSource": t.get("aiSource", ""), "locale": "en-us"})
    for i, r in enumerate(rows, 1):
        made = _iso(r["at"])
        status = "spam" if r.get("spam") else ("new" if (traffic.now - r["at"]).days < 3 else _pick(rnd, statuses))
        first = r["first"] if r["first"] is not None and "referrerHost" in r["first"] else None
        db.execute("INSERT INTO submissions (id, type, email, name, fields, locale, updated_at, created_at, status, page, "
                   "first_touch, last_touch, visits, session_id, ip_country) "
                   "VALUES (?, ?, ?, ?, '{}', 'en-us', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (i, r["type"], f"lead{i}@example.com", demo_name(i), made, made, status,
                    "/signup/" if r["type"] == "signup" else "/contact/",
                    touch(first or r["last"]), touch(r["last"]), r["visits"], r["vid"], r["cc"] or None))
    # Left out of the figures and listed (Leads > "Left out"): a few forms sent
    # twice, the second marked duplicate, and the team's own test lead.
    # No draw from `rnd`: the rest of the demo stays as it was.
    extra = db.execute("SELECT MAX(id) FROM submissions").fetchone()[0]
    twice = db.execute("SELECT type, email, created_at, page, first_touch, last_touch, visits, session_id, ip_country "
                       "FROM submissions WHERE status != 'spam' ORDER BY id").fetchall()[5::30]
    for kind, email, made, page, first, last, visits, vid, cc in twice:
        extra += 1
        again = _iso(datetime.fromisoformat(made.replace("Z", "+00:00")) + timedelta(minutes=4))
        db.execute("INSERT INTO submissions (id, type, email, fields, locale, updated_at, created_at, status, page, "
                   "first_touch, last_touch, visits, session_id, ip_country, duplicate_of_id) "
                   "VALUES (?, ?, ?, '{}', 'en-us', ?, ?, 'duplicate', ?, ?, ?, ?, ?, ?, NULL)",
                   (extra, kind, email, again, again, page, first, last, visits, vid, cc))
    made = _iso(traffic.now - timedelta(hours=30))
    db.execute("INSERT INTO submissions (id, type, email, fields, locale, updated_at, created_at, status, page) "
               "VALUES (?, 'contact', 'test@example.com', '{}', 'en-us', ?, ?, 'test', '/contact/')",
               (extra + 1, made, made))
    db.commit()
    db.close()


def later_changes(root: Path, cfgp: Path, traffic: dt.Traffic) -> None:
    """What a team does after the fact, for the lists that show it: three
    leads marked duplicate or spam in the lead store days later (the next
    sync moves their conversions to the removed list, with when and why),
    and the team's own test payment marked test (listed, never counted)."""
    from skald.config import load_config
    from skald.conversions import from_leads, store
    from_leads.run(load_config(cfgp), root, dt.SITE)        # the leads so far, as a run would have synced them
    leads = sqlite3.connect(root / "leads.db")
    for days, status in ((7, "duplicate"), (12, "spam"), (20, "duplicate")):
        before = _iso(traffic.now - timedelta(days=days))
        row = leads.execute("SELECT id FROM submissions WHERE status NOT IN ('spam', 'duplicate', 'test') "
                            "AND created_at < ? ORDER BY created_at DESC LIMIT 1", (before,)).fetchone()
        if row:
            leads.execute("UPDATE submissions SET status = ?, updated_at = ? WHERE id = ?",
                          (status, _iso(traffic.now), row[0]))
    leads.commit()
    leads.close()
    db = sqlite3.connect(store.path_for({}, root))
    paid = db.execute("SELECT id FROM conversions WHERE tool = 'stripe' AND at < ? ORDER BY at DESC LIMIT 1",
                      (store.stamp(traffic.now - timedelta(hours=6)),)).fetchone()
    db.close()
    if paid:
        code, err = run(cfgp, "--today", traffic.today.isoformat(), "conversions", "mark-test", dt.SITE, str(paid[0]))
        if code:
            raise SystemExit(f"demo: mark-test failed ({code}): {err[-800:]}")


def _pick(rnd, pairs):
    x = rnd.uniform(0, sum(w for _, w in pairs))
    for v, w in pairs:
        x -= w
        if x <= 0:
            return v
    return pairs[-1][0]


def funnels(root: Path, now: datetime) -> None:
    saved = (now - timedelta(days=45)).isoformat()
    f = {"name": "Visit to sign-up", "source": None, "saved_by": "owner@example.com", "saved_at": saved,
         "steps": [{"label": "Landed", "kind": "any"},
                   {"label": "Pricing", "kind": "path", "match": "segment", "paths": ["pricing"]},
                   {"label": "Sign-up page", "kind": "path", "match": "segment", "paths": ["signup"]}]}
    g = {**f, "name": "Blog to pricing",
         "steps": [{"label": "Blog post", "kind": "path", "match": "prefix", "paths": ["/blog/"]},
                   {"label": "Pricing", "kind": "path", "match": "segment", "paths": ["pricing"]},
                   {"label": "Book a demo", "kind": "path", "match": "segment", "paths": ["book-a-demo"]}]}
    (root / "funnels.json").write_text(json.dumps({"funnels": {f["name"]: f, g["name"]: g}}))


def spool_beacon(root: Path, cfg: dict, traffic: dt.Traffic) -> None:
    """What the beacon helper does with each accepted event: the day's spool
    line, and the journey and conversion it means (beacon_server.py)."""
    from skald import beacon
    from skald.conversions import from_beacon, store
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(dt.TZ_NAME)
    spool = root / "beacon"
    spool.mkdir(exist_ok=True)
    db = store.connect(store.path_for(cfg, root))
    for when, ip, ua, e in traffic.beacon:
        local = when.astimezone(tz)
        source, ai = beacon.source_of(e["r"], e["u"], dt.HOSTS)
        with open(beacon.day_file(spool, local.date()), "a") as fh:
            fh.write(beacon.line_for(e, local, "people", source, ai) + "\n")
        from_beacon.record(db, dt.SITE, e, local, source, dt.HOSTS, str(root / "country.mmdb"), ip, ua)
    db.close()


def post_hooks(root: Path, cfgp: Path, cfg: dict, traffic: dt.Traffic, rnd) -> dict:
    """Calendly and Stripe webhooks, signed with the site's secrets and posted
    to the hook receiver with its clock set to each event's time."""
    from conversions_support import FakeHandler
    from skald.conversions import secrets_store
    from skald.conversions.adapters import adapter
    from skald.conversions.hooks import Receiver
    path = secrets_store.path_for(cfg, root)
    secret = {}
    for tool in ("calendly", "stripe"):
        secret[tool] = "demo-" + "".join(rnd.choice("abcdef0123456789") for _ in range(32))   # made up, local
        secrets_store.put(path, secrets_store.key(dt.SITE, tool), secret[tool])
    rcfg = json.loads(json.dumps(cfg, default=str))
    rcfg.setdefault("hooks", {}).update(per_minute=100000, burst=100000, all_per_second=100000)
    clock = {"t": 0.0}
    rx = Receiver(rcfg, root, cfgp, clock=lambda: clock["t"])
    tally = {"ok": 0, "refused": 0}
    events = []
    stamp = "%Y-%m-%dT%H:%M:%S.000000Z"
    for i, (when, tool, d) in enumerate(traffic.hooks):
        if tool == "calendly":
            uri = f"https://api.calendly.com/scheduled_events/EV{i:04d}/invitees/IN{i:04d}"
            pl = {"uri": uri, "tracking": {"utm_content": d["vid"], "utm_source": d.get("utm") or None}}
            events.append((when, tool, {"event": "invitee.created", "created_at": when.strftime(stamp), "payload": pl}))
            x = rnd.random()
            if x < 0.09:
                w2 = when + timedelta(hours=rnd.randrange(3, 60))
                events.append((w2, tool, {"event": "invitee.canceled", "created_at": w2.strftime(stamp), "payload": pl}))
            elif x < 0.16:
                w2 = when + timedelta(hours=rnd.randrange(3, 40))
                events.append((w2, tool, {"event": "invitee.canceled", "created_at": w2.strftime(stamp),
                                          "payload": {**pl, "rescheduled": True}}))
            elif x < 0.22:
                w2 = when + timedelta(days=rnd.randrange(2, 6))
                events.append((w2, tool, {"event": "invitee_no_show.created", "created_at": w2.strftime(stamp),
                                          "payload": {"uri": f"https://api.calendly.com/invitee_no_shows/NS{i:04d}",
                                                      "invitee": uri}}))
        else:
            events.append((when, tool, {"object": "event", "type": "checkout.session.completed", "created": int(when.timestamp()),
                                        "data": {"object": {"id": f"cs_demo_{i:05d}", "payment_status": "paid",
                                                            "client_reference_id": d["vid"]}}}))
    for when, tool, payload in sorted(events, key=lambda x: x[0]):
        if when > traffic.now:
            continue
        clock["t"] = when.timestamp()
        body = json.dumps(payload).encode()
        p = f"/traffic-hooks/{dt.SITE}/{tool}"
        headers = {"Host": "analytics.example.com", "X-Forwarded-Proto": "https",
                   **adapter(tool).sign(body, secret[tool], clock["t"], "POST", "https://analytics.example.com" + p)}
        status, _ = rx.http(FakeHandler(p, body, headers))
        tally["ok" if status == 200 else "refused"] += 1
    return tally


def run(cfgp: Path, *argv: str) -> tuple[int, str]:
    from skald import cli
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(["--config", str(cfgp), *argv])
    return code, err.getvalue()


# The demo's city file (logs.city_db): a few made-up placements of its RFC 5737
# addresses in real cities of their country, at each city's own point. Not
# DB-IP's data (so no DB-IP credit); every eleventh address has no city, so
# "Not recorded" shows too. Kept apart from demo_traffic's seeded draws.
CITIES = {
    "US": [("New York", "New York", 40.713, -74.006), ("San Francisco", "California", 37.775, -122.419),
           ("Austin", "Texas", 30.267, -97.743), ("Chicago", "Illinois", 41.878, -87.630),
           ("Seattle", "Washington", 47.606, -122.332)],
    "GB": [("London", "England", 51.507, -0.128), ("Manchester", "England", 53.481, -2.243),
           ("Edinburgh", "Scotland", 55.953, -3.188)],
    "CA": [("Toronto", "Ontario", 43.653, -79.383), ("Vancouver", "British Columbia", 49.283, -123.121),
           ("Montreal", "Quebec", 45.502, -73.567)],
    "DE": [("Berlin", "Land Berlin", 52.520, 13.405), ("Munich", "Bavaria", 48.137, 11.575)],
    "IN": [("Bengaluru", "Karnataka", 12.972, 77.594), ("Mumbai", "Maharashtra", 19.076, 72.878)],
    "AU": [("Sydney", "New South Wales", -33.869, 151.209), ("Melbourne", "Victoria", -37.814, 144.963)],
    "FR": [("Paris", "Île-de-France", 48.857, 2.352), ("Lyon", "Auvergne-Rhône-Alpes", 45.764, 4.836)],
    "NL": [("Amsterdam", "North Holland", 52.368, 4.904)],
    "ES": [("Madrid", "Madrid", 40.417, -3.704), ("Barcelona", "Catalonia", 41.385, 2.173)],
    "BR": [("São Paulo", "São Paulo", -23.551, -46.633)],
    "SE": [("Stockholm", "Stockholm", 59.329, 18.069)],
    "IE": [("Dublin", "Leinster", 53.350, -6.260)],
    "SG": [("Singapore", "Singapore", 1.290, 103.852)],
}


def city_file(country_of: dict) -> bytes:
    """The demo's city .mmdb: most of a country's addresses in its first city."""
    from conversions_support import city_record, mmdb
    nets = {}
    for ip, cc in sorted(country_of.items()):
        n = int(ip.rsplit(".", 1)[1])
        if n % 11 == 0 or cc not in CITIES:
            continue
        roll = (n * 37) % 10
        place = CITIES[cc][min(len(CITIES[cc]) - 1, 0 if roll < 5 else 1 if roll < 8 else 2 + roll % 3)]
        nets[f"{ip}/32"] = city_record(place[0], place[1], cc, place[2], place[3])
    return mmdb(nets, kind="Demo-City")


def install(root: Path, traffic: dt.Traffic, say=print) -> Path:
    """A whole install in `root`, its history built from `traffic`. Returns dashboard.out."""
    import random
    from conversions_support import mmdb
    from skald import events
    from skald.config import load_config
    from skald.store import History
    from zoneinfo import ZoneInfo
    rnd = random.Random(dt.SEED + 1)
    (root / "logs").mkdir(parents=True)
    (root / "logs" / "access.log").write_text("".join(traffic.lines))
    cfgp = root / "config.yml"
    cfgp.write_text(config_text(root))
    (root / "visitor.env").write_text(f"{KEY_VAR}={DEMO_KEY}\n")
    cfg = load_config(cfgp)
    ranges(root, traffic.now)
    robots(root, traffic.now)
    sitemaps(root, traffic)
    (root / "country.mmdb").write_bytes(mmdb({f"{ip}/32": cc for ip, cc in sorted(traffic.country_of.items())}))
    (root / "city.mmdb").write_bytes(city_file(traffic.country_of))
    leads_db(root / "leads.db", traffic, rnd)
    funnels(root, traffic.now)
    spool_beacon(root, cfg, traffic)
    hooks = post_hooks(root, cfgp, cfg, traffic, rnd)
    say(f"demo: {len(traffic.lines):,} log lines, {len(traffic.beacon):,} beacon events, "
        f"{hooks['ok']} webhooks, {len(traffic.leads)} leads, {traffic.first} to {traffic.today}")
    days = (traffic.today - traffic.first).days
    for k in range(days - 1, -1, -1):           # each day as the morning run would collect it
        d = traffic.today - timedelta(days=k)
        code, err = run(cfgp, "--today", d.isoformat(), "backfill", "--days", "1")
        if code:
            raise SystemExit(f"demo: backfill for {d} failed ({code}): {err[-800:]}")
    tz = ZoneInfo(dt.TZ_NAME)
    with History(root / "history.sqlite") as history:      # the in-page events, day by day
        d = traffic.first
        while d < traffic.today:
            events.collect(history, cfg, dt.SITE, root / "beacon", d)
            events.audit(history, cfg, dt.SITE, root / "beacon", d, tz)
            d += timedelta(days=1)
    later_changes(root, cfgp, traffic)
    # AI & bots > AI answers: made-up answers asked through the real road (demo_answers.py).
    da.seed(root, load_config(cfgp), dt.SITE, dt.TZ_NAME, traffic.first, traffic.today, say)
    code, err = run(cfgp, "--today", traffic.today.isoformat(), "backfill", "--days", "3")
    if code:
        raise SystemExit(f"demo: backfill failed ({code}): {err[-1500:]}")
    # The morning run's recount of the retention cohorts (audit_retention.py, run-daily's
    # recounts step): every cohort the page shows is checked, and says so.
    from skald import audit_retention
    with History(root / "history.sqlite") as history:
        cdb = sqlite3.connect(root / "conversions.sqlite")
        try:
            got = audit_retention.check(history.db, cdb, dt.SITE, traffic.today,
                                        (traffic.today - timedelta(days=1)).isoformat())
        finally:
            cdb.close()
    if got["problems"]:
        raise SystemExit(f"demo: the retention recount does not match: {got['problems'][:3]}")
    # The live run at the demo's own clock, not at --today's noon: today so far ends
    # where the traffic does, and Real time's last 30 minutes are the traffic's.
    from unittest import mock
    from skald import cli
    with mock.patch.object(cli, "_now", lambda _args, zone: traffic.now.astimezone(zone)):
        code, err = run(cfgp, "live")
    if code:
        raise SystemExit(f"demo: live failed ({code}): {err[-1500:]}")
    return root / "www"

# ------------------------------------------------------- the static output

# The compare tab's presets (webapp/js/tabs/versuspick.js), for A; B is the
# period just before A, or the same weeks a year earlier.


def _month_end(y: int, m: int) -> date:
    return (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))


def compare_ranges(anchor: date) -> list[tuple[tuple[date, date], tuple[date, date]]]:
    y, mo = anchor.year, anchor.month
    lm_y, lm = (y - 1, 12) if mo == 1 else (y, mo - 1)
    q_first = (mo - 1) // 3 * 3 + 1
    lq_y, lq_first = (y - 1, 10) if q_first == 1 else (y, q_first - 3)
    a_list = [(anchor - timedelta(days=6), anchor), (anchor - timedelta(days=29), anchor),
              (anchor - timedelta(days=89), anchor), (date(y, mo, 1), anchor),
              (date(lm_y, lm, 1), _month_end(lm_y, lm)), (date(y, q_first, 1), anchor),
              (date(lq_y, lq_first, 1), _month_end(lq_y, lq_first + 2)), (anchor - timedelta(days=182), anchor)]
    out = []
    for first, last in a_list:
        length = (last - first).days + 1
        before = (first - timedelta(days=length), first - timedelta(days=1))
        year = (first - timedelta(days=364), last - timedelta(days=364))
        for b in (before, year):
            if (first, last, b) not in [(x[0][0], x[0][1], x[1]) for x in out]:
                out.append(((first, last), b))
    return out


def _span(r: tuple[date, date]) -> str:
    return f"{r[0].isoformat()}..{r[1].isoformat()}"


def helper_answers(root: Path, site_dir: Path) -> dict:
    """The helper's compare and page-story answers for what the demo offers,
    as files in data/demo/; returns the map app.json carries."""
    from skald import compare, lifecycle
    from skald.config import load_config
    from skald.store import History
    from zoneinfo import ZoneInfo
    cfg = load_config(root / "config.yml")
    tz = ZoneInfo(dt.TZ_NAME)
    app = json.loads((site_dir / "data" / "app.json").read_text())
    anchor, today = date.fromisoformat(app["anchor"]), date.fromisoformat(app["today"])
    folder = site_dir / "data" / "demo"
    folder.mkdir(parents=True, exist_ok=True)
    answers = {"compare": {}, "page": {}, "people": {}}
    index = json.loads((site_dir / "data" / "page_index.json").read_text())
    with History(root / "history.sqlite") as history:
        for a, b in compare_ranges(anchor):
            got = compare.compare(history, dt.SITE, None, _span(a), _span(b), {}, cfg, tz)
            name = f"compare-{a[0]}-{a[1]}-vs-{b[0]}-{b[1]}.json"
            (folder / name).write_text(json.dumps(got, separators=(",", ":")))
            answers["compare"][f"{_span(a)}|{_span(b)}"] = f"data/demo/{name}"
        for i, row in enumerate(index.get("pages") or []):
            got = lifecycle.story(history, dt.SITE, row["path"], cfg, tz, today)
            if not got.get("ok"):
                continue
            name = f"page-{i:03d}-{re.sub(r'[^a-z0-9]+', '-', row['path'].lower()).strip('-') or 'home'}.json"
            (folder / name).write_text(json.dumps(got, separators=(",", ":")))
            answers["page"][row["path"]] = f"data/demo/{name}"
    # The lists of what the figures leave out (Leads > "Left out", the Conversions
    # page's cancelled, removed and test rows), as a member who is not an admin
    # sees them: no email, name or visitor ID.
    from skald.people import lookup
    answers["people"] = {}
    lists = [("people/left-out", "left-out", lambda: lookup.left_out(cfg, root, dt.SITE, False))]
    lists += [(f"people/conversions?kind={k}", f"conversions-{k}",
               lambda k=k: lookup.conversions_listing(cfg, root, dt.SITE, k, False)) for k in ("cancelled", "removed", "test")]
    for url, stem, ask in lists:
        got = {**ask(), "private": False}
        for row in [*got.get("leads", []), *got.get("rows", []), *got.get("conversions", [])]:
            row.pop("vid", None)           # a lead's visitor ID too: the demo shows what a viewer may see
        if got.get("ok"):
            (folder / f"{stem}.json").write_text(json.dumps(got, separators=(",", ":")))
            answers["people"][url] = f"data/demo/{stem}.json"
    # Leads & sales > Leads (people/leads): every lead of the demo's days, as a member who
    # is not an admin sees them: no name or email (an admin on an install that keeps them
    # sees both). One answer for every period: the page keeps the rows of the period it shows.
    from skald.people import leadlist
    got = leadlist.rows(cfg, root, dt.SITE, today - timedelta(days=DEMO_LEAD_DAYS), today, names=False)
    if got.get("ok"):
        (folder / "leads.json").write_text(json.dumps(got, separators=(",", ":")))
        answers["people"]["people/leads"] = "data/demo/leads.json"
    # The visitor drawer's timeline (people/visitor, admins and owners on an
    # install): for each visit the page holds whose visitor came before, and
    # every visit of today. Labels, times and pages: no address, no visitor ID.
    from skald.people.timeline import visitor
    for j in app.get("journeys") or []:
        ft = j.get("first_touch") or {}
        if j.get("seq") is None or (ft.get("by") not in ("vid", "address", "hash") and j.get("day") != app["today"]):
            continue
        url = f"people/visitor?day={j['day']}&seq={j['seq']}"
        got = visitor(cfg, root, dt.SITE, j["day"], int(j["seq"]))
        if got.get("found"):
            name = f"visitor-{j['day']}-{int(j['seq']):04d}.json"
            (folder / name).write_text(json.dumps(got, separators=(",", ":")))
            answers["people"][url] = f"data/demo/{name}"
    retention_answers(cfg, root, folder, answers, today, visitor)
    return answers


def retention_answers(cfg: dict, root: Path, folder: Path, answers: dict, today: date, visitor) -> None:
    """Traffic > Retention: the visitors behind each weekly cell (people/cohort, everyone,
    came back and read 2+ pages), and the visitor drawer's timeline for those that came
    back. Labels, times and pages: no address."""
    from skald.retention_page import visitors
    from skald.store import History
    data = json.loads((folder.parent / "retention.json").read_text())
    timelines = 0
    with History(root / "history.sqlite") as history:
        for c in data.get("grains", {}).get("week", {}).get("cohorts", []):
            if c.get("state") != "ok":
                continue
            ks = [0] + [int(k) for k, st in (c.get("status") or {}).items() if st == "ok"]
            for k in ks:
                for deep in ((False, True) if k else (False,)):
                    got = visitors(cfg, root, history.db, dt.SITE, "week", c["start"], k, deep=deep, today=today)
                    if not got.get("ok"):
                        continue
                    url = f"people/cohort?grain=week&start={c['start']}&k={k}" + ("&deep=1" if deep else "")
                    name = f"cohort-week-{c['start']}-{k}{'-deep' if deep else ''}.json"
                    (folder / name).write_text(json.dumps(got, separators=(",", ":")))
                    answers["people"][url] = f"data/demo/{name}"
                    for r in got.get("rows", []) if k else []:
                        vurl = f"people/visitor?day={r['day']}&seq={r['seq']}"
                        if vurl in answers["people"] or timelines >= 600:
                            continue
                        tl = visitor(cfg, root, dt.SITE, r["day"], int(r["seq"]))
                        if tl.get("found"):
                            vname = f"visitor-{r['day']}-{int(r['seq']):04d}.json"
                            (folder / vname).write_text(json.dumps(tl, separators=(",", ":")))
                            answers["people"][vurl] = f"data/demo/{vname}"
                            timelines += 1


def mark_demo(www: Path, answers: dict, repo_url: str) -> None:
    """Every app.json says "demo" (the site's and each view's); a request log
    names no helper address to poll."""
    readme = repo_url.rstrip("/") + "#quick-start-in-60-seconds"
    demo = {"text": "Demo with sample data", "install": "install Skald for your site",
            "links": [{"text": "Quick start", "url": readme}, {"text": "Source on GitHub", "url": repo_url}],
            "api": answers}
    for path in sorted(www.rglob("data/app.json")):
        app = json.loads(path.read_text())
        app["demo"] = demo
        app["canRefresh"] = True          # the button is there; in the demo it says why it does nothing
        path.write_text(json.dumps(app, separators=(",", ":")))
    for path in sorted(www.rglob("data/requests.json")):
        body = json.loads(path.read_text())
        if body.pop("api", None) is not None:
            path.write_text(json.dumps(body, separators=(",", ":")))


def build_file(now: datetime) -> dict:
    def text(name: str, default: str = "") -> str:
        try:
            return (ROOT / name).read_text().strip()
        except OSError:
            return default
    try:
        commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True, timeout=10).stdout.strip() or "demo"
    except (OSError, subprocess.SubprocessError):
        commit = "demo"
    return {"schema_version": 1, "name": text("NAME", "Skald"), "version": text("VERSION", "0"),
            "tagline": text("TAGLINE"), "release": "demo", "commit": commit,
            "deployed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}


REDIRECT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Skald demo</title>
<meta http-equiv="refresh" content="0;url=traffic/example.com/">
<link rel="canonical" href="traffic/example.com/">
</head>
<body>
<p>The demo dashboard is at <a href="traffic/example.com/">traffic/example.com/</a>.</p>
</body>
</html>
"""


def prepare(out: Path) -> Path:
    out = out.expanduser().resolve()
    if out == ROOT or out in ROOT.parents or out in (Path("/"), Path.home().resolve()):
        raise SystemExit(f"demo: refusing to wipe {out}")
    if out.exists():
        if any(out.iterdir()) and not (out / MARKER).is_file():
            raise SystemExit(f"demo: {out} is not empty and was not written by this tool")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    return out


def static(out: Path, www: Path, root: Path, now: datetime, repo_url: str) -> None:
    site_dir = www / dt.SITE
    mark_demo(www, helper_answers(root, site_dir), repo_url)
    (www / "build.json").write_text(json.dumps(build_file(now)) + "\n")
    shutil.copytree(www, out / "traffic")
    (out / "index.html").write_text(REDIRECT)
    (out / ".nojekyll").write_text("")
    (out / MARKER).write_text("Written by tools/demo.py, which wipes and rewrites this folder.\n")
    marks = {str(root), str(root.resolve())}
    leaked = [p for p in out.rglob("*") if p.is_file() and any(m in p.read_text(errors="ignore") for m in marks)]
    if leaked:
        raise SystemExit(f"demo: the temporary install's path is in {leaked[0].relative_to(out)}")


def parse_now(text: str | None) -> datetime:
    if not text:
        return (datetime.now(UTC) - timedelta(minutes=3)).replace(second=0, microsecond=0)
    got = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return (got if got.tzinfo else got.replace(tzinfo=UTC)).astimezone(UTC)


def build(out: Path, now: datetime, days: int = 62, keep: Path | None = None, repo_url: str = REPO_URL,
          say=print) -> Path:
    out = prepare(out)
    traffic = dt.generate(now, days)
    was = os.environ.get(KEY_VAR)
    os.environ[KEY_VAR] = DEMO_KEY
    try:
        with tempfile.TemporaryDirectory(prefix="skald-demo-") as tmp, da.made_up_keys():
            root = Path(keep).resolve() if keep else Path(tmp) / "install"
            if root.exists():
                shutil.rmtree(root)
            www = install(root, traffic, say)
            static(out, www, root, traffic.now, repo_url)
    finally:
        if was is None:
            os.environ.pop(KEY_VAR, None)
        else:
            os.environ[KEY_VAR] = was
    say(f"demo: written to {out}; open traffic/{dt.SITE}/")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", type=Path, help="the folder to write (wiped first)")
    ap.add_argument("--now", help="the demo's clock, ISO 8601 (default: a few minutes ago)")
    ap.add_argument("--days", type=int, default=62, help="whole days of history before today (default 62)")
    ap.add_argument("--keep", type=Path, help="keep the temporary install in this folder")
    ap.add_argument("--repo-url", default=REPO_URL, help="where the banner's links point")
    a = ap.parse_args(argv)
    if a.days < 2:
        ap.error("--days must be at least 2")
    build(a.out, parse_now(a.now), a.days, a.keep, a.repo_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())

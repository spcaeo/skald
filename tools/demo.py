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

app.json gets "demo": {...}: the page then works without a helper. What needs a
running install (refresh, saving, settings, team, integrations) says so politely,
and compare and page story read the files in data/demo/ (DATA-CONTRACT.md, the
compare and page answers).

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

import demo_traffic as dt  # noqa: E402

MARKER = ".skald-demo"
REPO_URL = "https://github.com/spcaeo/skald"
UTC = timezone.utc

# ------------------------------------------------------------- the install


def config_text(root: Path) -> str:
    return f"""site:
  name: example.com
  hosts: [example.com, www.example.com]
  require_rendering: false
logs:
  dir: {root / 'logs'}
  base: access.log
  days: 2
  format: auto
ours:
  addresses:
    - {{ip: {dt.OFFICE}, label: office}}
report:
  session_gap_minutes: 30
  timezone: {dt.TZ_NAME}
  coverage_gap_minutes: 1440
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
        db.execute("INSERT INTO submissions (id, type, email, fields, locale, updated_at, created_at, status, page, "
                   "first_touch, last_touch, visits, session_id, ip_country) "
                   "VALUES (?, ?, ?, '{}', 'en-us', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (i, r["type"], f"lead{i}@example.com", made, made, status,
                    "/signup/" if r["type"] == "signup" else "/contact/",
                    touch(first or r["last"]), touch(r["last"]), r["visits"], r["vid"], r["cc"] or None))
    db.commit()
    db.close()


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
    cfg = load_config(cfgp)
    ranges(root, traffic.now)
    robots(root, traffic.now)
    (root / "country.mmdb").write_bytes(mmdb({f"{ip}/32": cc for ip, cc in sorted(traffic.country_of.items())}))
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
    for argv in (("backfill", "--days", "3"), ("live",)):
        code, err = run(cfgp, "--today", traffic.today.isoformat(), *argv)
        if code:
            raise SystemExit(f"demo: {argv[0]} failed ({code}): {err[-1500:]}")
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
    answers = {"compare": {}, "page": {}}
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
    return answers


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
        with tempfile.TemporaryDirectory(prefix="skald-demo-") as tmp:
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

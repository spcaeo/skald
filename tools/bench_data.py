"""Synthetic traffic for tools/bench.py: log lines, a history, accounts and
conversions that look like a real small site, built from documentation
addresses only (RFC 5737) and example.com hosts.

A day of log is made by `day_lines`: people's visits that render (a page,
then the site's /_next/static/ script a second later), scrapers with a
browser's user agent that do not, AI crawlers and assistants, search
crawlers, monitors, scanner probes, our own heartbeat and a sibling host.
The mix is fixed by a seed, so two runs build the same files.

`clone_days` copies the rows of days that the real pipeline collected onto
other dates (and other site names), table by table, with the schema's own
columns: older days of a long history cost a copy, not a parse. The copies'
figures are the templates' figures; they are for timing, never for reading.
"""
from __future__ import annotations

import random
import sqlite3
from datetime import date, datetime, time, timedelta, timezone

CHROME = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
SAFARI_IOS = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1")
FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0"
EDGE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0")
ANDROID = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/129.0.0.0 Mobile Safari/537.36")
BROWSERS = (CHROME, SAFARI_IOS, FIREFOX, EDGE, ANDROID)

TRAINING = ("Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)",
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0)",
            "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)")
ASKED = ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; "
         "+https://openai.com/bot",
         "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; "
         "+https://perplexity.ai/perplexity-user)")
SEARCH = ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
          "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)")
BOTS = ("Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
        "Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)",
        "Mozilla/5.0+(compatible; UptimeRobot/2.0; http://www.uptimerobot.com/)")
SCANNER = "curl/8.7.1"
HEARTBEAT = "skald heartbeat"

REFERRERS = ("-", "-", "-", "https://www.google.com/", "https://www.google.com/",
             "https://www.bing.com/", "https://chatgpt.com/", "https://www.perplexity.ai/",
             "https://www.linkedin.com/", "https://news.example.com/story")
CAMPAIGNS = ("", "", "", "", "?utm_source=newsletter&utm_medium=email&utm_campaign=launch",
             "?utm_source=linkedin&utm_medium=social&utm_campaign=autumn")
COUNTRIES = ("US", "US", "US", "CA", "CA", "GB", "IN", "DE", "FR", "AU")
PROBES = ("/.env", "/wp-login.php", "/xmlrpc.php", "/.git/config", "/admin/config.php")
NETS = ("203.0.113", "198.51.100", "192.0.2")


def pages(n: int) -> list[str]:
    """`n` page paths: a home page, a few fixed ones, guides and Canadian
    English and French pages (so the three views have figures)."""
    fixed = ["/", "/pricing/", "/about/", "/contact/", "/ca/", "/ca/fr/"]
    out = list(fixed)
    i = 0
    while len(out) < n:
        out.append(("/guides/topic-{0}/", "/blog/post-{0}/", "/ca/guides/topic-{0}/",
                    "/ca/fr/guides/sujet-{0}/")[i % 4].format(i))
        i += 1
    return out[:n]


def address(rng: random.Random) -> str:
    return f"{rng.choice(NETS)}.{rng.randint(1, 254)}"


def log_line(when: datetime, ip: str, path: str, agent: str, referrer: str = "-",
         status: int = 200, host: str = "example.com", country: str = "US",
         method: str = "GET", seconds: float = 0.004) -> str:
    """One nginx_extended line (the format tests/support.py writes)."""
    return (f'{when.isoformat()} {ip} {host} "{method} {path} HTTP/2.0" {status} 512 '
            f'"{referrer}" "{agent}" {seconds:.3f} cc={country} ray=0000000000000000-LHR\n')


# The share of events that are each kind, after people's visits (`people`):
# scrapers, AI, search, monitors, probes, heartbeat, a sibling host. A small
# site's log is mostly machines: on the first live install about one browser
# visit in fifty rendered (rendering.py).
MACHINES = ((0.12, "scraper"), (0.08, "training"), (0.02, "asked"), (0.20, "search"),
            (0.16, "bot"), (0.32, "probe"), (0.06, "ours"), (0.04, "other"))


def day_lines(day: date, tz, n: int, paths: list[str], seed: int,
              until: datetime | None = None, people: float = 0.02,
              host: str = "example.com") -> list[str]:
    """About `n` lines for local `day`, sorted by time; only those before
    `until` when given (today so far). `people`: the share of events that
    are a person's visit (each two to twelve lines). `host`: the site's."""
    rng = random.Random(seed)
    start = datetime.combine(day, time(0), tzinfo=tz)

    def line(*args, **kw) -> str:
        kw.setdefault("host", host)
        return log_line(*args, **kw)

    out: list[tuple[datetime, str]] = []

    def at() -> datetime:
        return start + timedelta(seconds=rng.randint(0, 86399))

    weights = [1.0 / (i + 1) ** 0.8 for i in range(len(paths))]

    def page() -> str:
        return rng.choices(paths, weights)[0]

    made = 0
    while made < n:
        if rng.random() < people:                # a person's visit that renders
            ip, agent, cc = address(rng), rng.choice(BROWSERS), rng.choice(COUNTRIES)
            when = at()
            ref = rng.choice(REFERRERS)
            camp = rng.choice(CAMPAIGNS)
            for k in range(rng.choice((1, 1, 1, 2, 2, 3, 4, 6))):
                p = page()
                seconds = rng.choice((0.004, 0.02, 0.2, 1.4))
                out.append((when, line(when, ip, p + (camp if k == 0 else ""), agent,
                                       ref if k == 0 else f"https://{host}" + p, country=cc,
                                       seconds=seconds)))
                out.append((when + timedelta(seconds=1),
                            line(when + timedelta(seconds=1), ip,
                                 f"/_next/static/chunks/app-{k % 3}.js", agent,
                                 f"https://{host}" + p, country=cc)))
                made += 2
                if rng.random() < 0.03:
                    out.append((when + timedelta(seconds=5),
                                line(when + timedelta(seconds=5), ip, "/missing-page/", agent,
                                     status=404, country=cc)))
                    made += 1
                if rng.random() < 0.01:
                    out.append((when + timedelta(seconds=9),
                                line(when + timedelta(seconds=9), ip, "/api/contact", agent,
                                     method="POST", country=cc)))
                    made += 1
                when += timedelta(seconds=rng.randint(20, 400))
            continue
        kind = rng.choices([k for _, k in MACHINES], [w for w, _ in MACHINES])[0]
        when, ip = at(), address(rng)
        if kind == "scraper":                    # a browser's agent, never renders
            text = line(when, ip, page(), rng.choice(BROWSERS), country=rng.choice(COUNTRIES))
        elif kind == "training":
            text = line(when, ip, page(), rng.choice(TRAINING))
        elif kind == "asked":
            text = line(when, ip, page(), rng.choice(ASKED))
        elif kind == "search":
            text = line(when, ip, page(), rng.choice(SEARCH))
        elif kind == "bot":
            text = line(when, ip, page(), rng.choice(BOTS), country="DE")
        elif kind == "probe":
            text = line(when, ip, rng.choice(PROBES), SCANNER, status=404, country="NL")
        elif kind == "ours":
            text = line(when, "192.0.2.250", "/", HEARTBEAT)
        else:
            text = line(when, ip, "/v1/items", CHROME, host="api.example.com",
                        status=502 if rng.random() < 0.05 else 200)
        out.append((when, text))
        made += 1
    out.sort(key=lambda x: x[0])
    if until is not None:
        out = [x for x in out if x[0] < until]
    return [text for _, text in out]


# ----------------------------------------------------------- cloning days

def _tables(db) -> list[tuple[str, list[str]]]:
    """(table, columns) for every table filed by (site, day)."""
    out = []
    for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                              "ORDER BY name"):
        cols = [r[1] for r in db.execute(f'PRAGMA table_info("{name}")')]
        if "site" in cols and "day" in cols:
            out.append((name, cols))
    return out


def clone_days(db_path, site: str, plan: list[tuple[str, str, str]]) -> int:
    """Copy each stored (template site, template day) onto (new site, new day),
    for the site and its views. `plan`: [(template_day, new_site, new_day)].
    Rows written."""
    db = sqlite3.connect(str(db_path))
    written = 0
    try:
        tables = _tables(db)
        with db:
            for src_day, dst_site, dst_day in plan:
                for table, cols in tables:
                    picks = []
                    for c in cols:
                        if c == "site":
                            picks.append("? || substr(site, ?)")
                        elif c == "day":
                            picks.append("?")
                        else:
                            picks.append(f'"{c}"')
                    sql = (f'INSERT OR REPLACE INTO "{table}" ({", ".join(cols)}) '
                           f'SELECT {", ".join(picks)} FROM "{table}" '
                           f"WHERE day = ? AND (site = ? OR substr(site, 1, ?) = ?)")
                    args = []
                    for c in cols:
                        if c == "site":
                            args += [dst_site, len(site) + 1]
                        elif c == "day":
                            args.append(dst_day)
                    args += [src_day, site, len(site) + 2, site + "::"]
                    written += db.execute(sql, args).rowcount
    finally:
        db.close()
    return written


def copy_milestones(db_path, site: str, others: list[str]) -> None:
    db = sqlite3.connect(str(db_path))
    try:
        with db:
            for other in others:
                db.execute("INSERT OR REPLACE INTO page_milestones (site, path, kind, who, at, "
                           "via) SELECT ?, path, kind, who, at, via FROM page_milestones "
                           "WHERE site = ?", (other, site))
    finally:
        db.close()


# ------------------------------------------------------------- conversions

def fill_conversions(path, sites: list[str], first: date, last: date, per_day: int,
                     seed: int = 7) -> int:
    """Conversions and browser journeys for each site and day (the beacon's
    shapes): page views by visitor ID, some of which sign up later."""
    from skald.conversions import store
    rng = random.Random(seed)
    db = store.connect(path)
    n = 0
    try:
        with store.tx(db):
            day = first
            while day <= last:
                for site in sites:
                    for i in range(per_day):
                        vid = f"v{day.toordinal()}-{i}-{rng.randint(0, 9999)}"
                        t0 = datetime.combine(day, time(9), tzinfo=timezone.utc) + \
                            timedelta(minutes=rng.randint(0, 600))
                        src = rng.choice(("Search engine", "Direct", "AI assistant",
                                          "Social", "Referral"))
                        for k in range(rng.randint(1, 5)):
                            db.execute("INSERT INTO journeys (vid, site, at, path, source_type) "
                                       "VALUES (?, ?, ?, ?, ?)",
                                       (vid, site, store.stamp(t0 + timedelta(minutes=k)),
                                        rng.choice(("/", "/pricing/", "/guides/topic-1/",
                                                    "/contact/")), src))
                        if rng.random() < 0.3:
                            stage = rng.choice(("started", "completed", "completed"))
                            db.execute(
                                "INSERT OR IGNORE INTO conversions (site, action, stage, at, "
                                "vid, external_ref, tool, source_type, first_source, landing, "
                                "country, device, first_touch_at, visits_before, received_at) "
                                "VALUES (?, 'signup', ?, ?, ?, ?, 'beacon', ?, ?, '/', 'US', "
                                "'Desktop', ?, ?, ?)",
                                (site, stage, store.stamp(t0 + timedelta(minutes=8)), vid,
                                 f"ref-{vid}", src, src, store.stamp(t0),
                                 rng.randint(0, 4), store.stamp(t0 + timedelta(minutes=8))))
                            n += 1
                day += timedelta(days=1)
    finally:
        db.close()
    return n

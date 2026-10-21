"""Shared fixtures for Security's tests (test_security*.py): a day of scanners shaped like
the ones found on a real site, with documentation addresses and example.com hosts only.

  * a single-page app (app.example.com) answering every path it does not have with its 392-byte
    shell (626 bytes raw, gzipped by the CDN)
  * the bare IP of the server (192.0.2.10) answering with nginx's 404-byte default page
  * one fake leak: /.env.production on example.com answered 200 with 1,873 bytes, by a
    scanner with a forged referrer of the site's own wp. subdomain
  * path traversal and Log4Shell in the query, login hammering (25 POSTs in 2 minutes),
    a burst (320 requests in 40 seconds) and a person who renders the page
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from support import CHROME, Sandbox

UTC = timezone.utc
DAY = "2026-10-05"
T = datetime(2026, 10, 5, 8, tzinfo=UTC)
SPA = ["/.env", "/phpinfo.php", "/config/auth.php", "/storage/logs/laravel.log", "/admin"]


def ln(when, address, path, agent=CHROME, status=200, size=512, host="example.com",
       referrer="-", method="GET", country="US") -> str:
    """One nginx_extended line; size None writes "-" (a log without bytes)."""
    return (f'{when.isoformat()} {address} {host} "{method} {path} HTTP/2.0" '
            f'{status} {"-" if size is None else size} "{referrer}" "{agent}" 0.004 '
            f'cc={country} ray=0000000000000000-LHR\n')


def day_lines() -> list[str]:
    out = []
    for i, p in enumerate(SPA):
        out.append(ln(T + timedelta(seconds=i), "198.51.100.7", p, "curl/8.7.1", 200, 392,
                      host="app.example.com", country="SG"))
    out.append(ln(T + timedelta(minutes=1), "198.51.100.8", "/.env.production", CHROME, 200, 1873,
                  referrer="https://wp.example.com/", country="HK"))
    out.append(ln(T + timedelta(minutes=1, seconds=2), "198.51.100.8", "/terraform.tfstate", CHROME,
                  404, 150, referrer="https://wp.example.com/", country="HK"))
    for i, p in enumerate(["/.env", "/wp-login.php", "/.aws/credentials"]):
        out.append(ln(T + timedelta(minutes=2, seconds=i), "203.0.113.200", p, "Go-http-client/1.1",
                      200, 404, host="192.0.2.10", country="NL"))
    out.append(ln(T + timedelta(minutes=3), "198.51.100.9", "/search?q=../../etc/passwd", CHROME,
                  400, 0, country="DE"))
    out.append(ln(T + timedelta(minutes=3, seconds=1), "198.51.100.9", "/?x=${jndi:ldap://x}", CHROME,
                  400, 0, country="DE"))
    for i in range(25):
        out.append(ln(T + timedelta(minutes=10, seconds=5 * i), "198.51.100.10", "/login",
                      "python-requests/2.31", 401, 60, method="POST"))
    for i in range(320):
        out.append(ln(T + timedelta(minutes=30, milliseconds=125 * i), "198.51.100.11",
                      f"/blog/{i % 7}", "Scrapy/2.11", 200, 9000))
    # a person who renders the page, from a page of the site
    out.append(ln(T + timedelta(hours=1), "203.0.113.5", "/"))
    out.append(ln(T + timedelta(hours=1, seconds=1), "203.0.113.5", "/assets/site.css",
                  referrer="https://example.com/"))
    return sorted(out)


def box(lines=None, extra: str = "") -> Sandbox:
    b = Sandbox(mail=False)
    text = b.config.read_text().replace("hosts: [example.com]",
                                        "hosts: [example.com, app.example.com]")
    b.config.write_text(text + extra)
    b.log(day_lines() if lines is None else lines)
    return b


def stored(b: Sandbox, day: str = DAY) -> dict:
    with sqlite3.connect(b.db) as db:
        got = db.execute("SELECT data FROM day_extras WHERE kind = 'security' AND day = ?",
                         (day,)).fetchone()
    return json.loads(got[0]) if got else None


def put(b: Sandbox, blob: dict, day: str = DAY) -> None:
    with sqlite3.connect(b.db) as db:
        db.execute("UPDATE day_extras SET data = ? WHERE kind = 'security' AND day = ?",
                   (json.dumps(blob), day))

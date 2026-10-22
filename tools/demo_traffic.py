"""The public demo's traffic: a small fictional SaaS on example.com (tools/demo.py).

Every address is from the RFC 5737 documentation ranges (192.0.2.0/24,
198.51.100.0/24, 203.0.113.0/24); every host is example.com, example.org or
example.net, or a real search engine, social site or AI assistant as a
referrer. Names and e-mail addresses are made up.

`generate(now, days)` is seeded: the same `now` and `days` give the same
traffic, line for line. Nothing here writes a file or touches the network.

What it makes, for the days up to `now`:
  lines   nginx_extended access-log lines: people (pages and assets, a few
          404s, the form posts that make the leads), AI crawlers and
          assistants (training, user fetches), search engines, a fake
          GPTBot, scanners, the team's own office visits; and Security's scanners,
          a leak, login hammering and a burst (demo_security.py)
  beacon  in-page events from the site's script: page views, CTA clicks,
          scrolls, forms started, a booking widget
  hooks   Calendly bookings and Stripe payments, as the tools would post them
  leads   sign-up and contact form rows for the site's lead store
A user fetch by ChatGPT-User or Perplexity-User followed minutes later by a
direct, untagged visit to the same page makes the "likely sent by an AI
assistant" figure; a few of those visitors become leads. Before many visits
cited by ChatGPT, Perplexity or Claude, that assistant's user fetcher read the
landing page and a few others minutes earlier ("what the AI read").

Crawlers ask for what real ones ask for: pages, robots.txt, sitemaps, and the
AI crawlers and user fetchers llms.txt, llms-full.txt and Markdown copies of
the blog. Every line has a body size and a response time that fit what it
asked for (a crawler on a big page is slower than a cached page for a person),
and crawlers meet the odd 404 and 5xx. Those draws come from a second seeded
generator, so the people, leads and bookings are the same as without them.

Standard library only.
"""
from __future__ import annotations

import random
import zlib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
SITE = "example.com"
HOSTS = {"example.com", "www.example.com"}
TZ_NAME = "America/New_York"
SEED = 20261011
OFFICE = "192.0.2.50"          # the team's own address: "our own" traffic

# ------------------------------------------------------------- browsers
UAS = [   # (user agent, weight, viewport)
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36", 20, "lg"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36", 18, "lg"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", 16, "xs"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15", 9, "xl"),
    ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36", 9, "xs"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0", 8, "lg"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0", 4, "lg"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0", 2, "lg"),
    ("Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", 2, "md"),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36", 3, "lg"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/129.0.6668.69 Mobile/15E148 Safari/604.1", 4, "xs"),
    ("Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/26.0 Chrome/122.0.0.0 Mobile Safari/537.36", 3, "xs"),
]
COUNTRIES = [("US", 44), ("GB", 11), ("CA", 8), ("DE", 7), ("IN", 6), ("AU", 5), ("FR", 4), ("NL", 4),
             ("ES", 3), ("BR", 3), ("SE", 2), ("IE", 2), ("SG", 1)]

# ------------------------------------------------------- crawlers, bots
GPTBOT = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)"
CHATGPT_USER = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot"
PERPLEXITY_USER = ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; "
                   "+https://perplexity.ai/perplexity-user)")
CLAUDE_USER = ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; "
               "+Claude-User@anthropic.com)")
FETCHERS = [(CHATGPT_USER, "198.51.100.3", 3), (PERPLEXITY_USER, "198.51.100.35", 1)]
# The user fetcher of each assistant a cited visit can come from (its referrer host).
FETCHER_OF = {"chatgpt.com": (CHATGPT_USER, "198.51.100.3"), "perplexity.ai": (PERPLEXITY_USER, "198.51.100.35"),
              "claude.ai": (CLAUDE_USER, "198.51.100.19")}
BOTS = [  # (user agent, address, (fewest, most) requests a day)
    (GPTBOT, "198.51.100.2", (4, 14)),
    (CHATGPT_USER, "198.51.100.3", (3, 11)),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot",
     "198.51.100.4", (1, 5)),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0)", "198.51.100.18", (3, 12)),
    (CLAUDE_USER, "198.51.100.19", (1, 5)),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
     "198.51.100.34", (2, 8)),
    (PERPLEXITY_USER, "198.51.100.35", (1, 6)),
    ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "198.51.100.50", (8, 22)),
    ("Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)", "198.51.100.66", (3, 10)),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 "
     "Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)", "198.51.100.82", (1, 4)),
    ("meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)", "198.51.100.98", (1, 6)),
    ("Mozilla/5.0 (compatible; Bytespider; spider-feedback@bytedance.com)", "198.51.100.120", (0, 5)),
    ("CCBot/2.0 (https://commoncrawl.org/faq/)", "198.51.100.130", (0, 3)),
]
# The published address lists the demo's bot check reads (bots.ranges_dir).
RANGES = {"openai-gptbot": ["198.51.100.0/28"], "openai-searchbot": ["198.51.100.0/28"],
          "openai-chatgpt-user": ["198.51.100.0/28"], "anthropic": ["198.51.100.16/28"],
          "perplexity-bot": ["198.51.100.32/28"], "perplexity-user": ["198.51.100.32/28"],
          "google-common": ["198.51.100.48/28"], "google-special": ["198.51.100.48/28"],
          "google-user": ["198.51.100.48/28"], "google-user-google": ["198.51.100.48/28"],
          "bing": ["198.51.100.64/28"], "apple": ["198.51.100.80/28"], "meta": ["198.51.100.96/28"],
          "duckduckgo": ["198.51.100.112/29"], "hosting": ["198.51.100.192/26"]}

# ------------------------------------------------------------- the site
BLOG = ["/blog/server-logs-vs-tags", "/blog/ai-crawlers-explained", "/blog/fall-launch", "/blog/pricing-for-small-teams"]
GUIDES = ["/guides/getting-started", "/guides/webhooks", "/guides/team-roles"]
NEXT = {
    "/": [("/features/", 30), ("/pricing/", 30), ("/blog/", 12), ("/customers/", 12), ("/about/", 8), ("/contact/", 4)],
    "/features/": [("/pricing/", 45), ("/customers/", 20), ("/signup/", 15), ("/book-a-demo/", 8), ("/guides/getting-started", 8)],
    "/pricing/": [("/signup/", 22), ("/book-a-demo/", 12), ("/features/", 20), ("/contact/", 9), ("/customers/", 15)],
    "/customers/": [("/pricing/", 60), ("/book-a-demo/", 20), ("/features/", 15)],
    "/about/": [("/contact/", 45), ("/customers/", 35), ("/pricing/", 20)],
    "/blog/": [(b, 25) for b in BLOG],
    "/signup/": [("/pricing/", 60), ("/guides/getting-started", 40)],
    "/contact/": [("/", 100)],
    "/book-a-demo/": [("/pricing/", 100)],
}
for _b in BLOG:
    NEXT[_b] = [("/pricing/", 30), ("/", 20), ("/features/", 20)] + [(o, 10) for o in BLOG if o != _b]
for _g in GUIDES:
    NEXT[_g] = [("/pricing/", 35), ("/signup/", 30)] + [(o, 18) for o in GUIDES if o != _g]
STAY = {"/signup/": 0.18, "/contact/": 0.1, "/book-a-demo/": 0.15}
DWELL = {"/blog/": (40, 220), "/guides/": (60, 300), "/pricing/": (30, 180)}
ASSETS = ["/assets/site.css", "/assets/site.js", "/assets/logo.svg"]

SOURCES = [("search", 34), ("direct", 21), ("social", 10), ("ai", 8), ("referral", 9),
           ("email", 6), ("paid", 8), ("social_paid", 4)]
SEARCH = [("https://www.google.com/", 80), ("https://www.bing.com/", 12), ("https://duckduckgo.com/", 8)]
SOCIAL = [("https://www.linkedin.com/", 55), ("https://t.co/", 15), ("https://www.reddit.com/", 18),
          ("https://news.ycombinator.com/", 12)]
AI = [("https://chatgpt.com/", 52), ("https://www.perplexity.ai/", 20), ("https://claude.ai/", 15),
      ("https://gemini.google.com/", 9), ("https://copilot.microsoft.com/", 4)]
REFERRAL = [("https://news.example.org/a/small-team-tools", 45), ("https://blog.example.net/review", 35),
            ("https://partners.example.org/", 20)]
LAND = {
    "search": [(b, 10) for b in BLOG] + [(g, 7) for g in GUIDES] + [("/", 22), ("/pricing/", 10), ("/features/", 7)],
    "ai": [(g, 12) for g in GUIDES] + [(b, 7) for b in BLOG] + [("/pricing/", 18), ("/", 10), ("/features/", 10)],
    "direct": [("/", 62), ("/pricing/", 16), ("/blog/", 8), ("/signup/", 6), ("/features/", 8)],
    "social": [(b, 14) for b in BLOG] + [("/", 30), ("/pricing/", 14)],
    "referral": [("/", 45), ("/features/", 25), ("/pricing/", 20), ("/customers/", 10)],
    "email": [("/blog/fall-launch", 70), ("/pricing/", 30)],
    "paid": [("/pricing/", 60), ("/", 40)],
    "social_paid": [("/features/", 60), ("/", 40)],
}
MD = [b + ".md" for b in BLOG]          # the blog's Markdown copies, for AI readers
_PAGES = [("/", 10), ("/pricing/", 8), ("/features/", 6)] + [(b, 4) for b in BLOG] + [(g, 4) for g in GUIDES]
CRAWL = {   # what each kind of crawler asks for (one draw each: the main sequence stays as it was)
    "search": _PAGES + [("/robots.txt", 4), ("/sitemap.xml", 4), ("/sitemap-blog.xml", 2)],
    "training": _PAGES + [("/robots.txt", 4), ("/llms.txt", 6), ("/llms-full.txt", 3), ("/sitemap.xml", 3),
                          ("/sitemap-blog.xml", 1.5)] + [(m, 2) for m in MD],
    "asked": _PAGES + [("/robots.txt", 2), ("/llms.txt", 4), ("/llms-full.txt", 1), ("/sitemap.xml", 0.5)]
             + [(m, 2) for m in MD],
    "other": _PAGES + [("/robots.txt", 4), ("/sitemap.xml", 2)],
}
TRAINING = ("GPTBot", "ClaudeBot", "PerplexityBot", "OAI-SearchBot", "meta-externalagent")
SEARCHERS = ("Googlebot", "bingbot", "Applebot")
GONE = ["/blog/old-launch-post", "/guides/api-v1", "/blog/2024-roadmap", "/blog/old-launch-post.md"]
SIZES = {"/robots.txt": 168, "/llms.txt": 5_812, "/llms-full.txt": 214_377, "/sitemap.xml": 7_406,
         "/sitemap-blog.xml": 3_118, "/assets/site.css": 38_412, "/assets/site.js": 96_850, "/assets/logo.svg": 3_920}
FETCHED = [("/pricing/", 30), ("/guides/getting-started", 25), ("/features/", 15), ("/guides/webhooks", 10)] + [(b, 5) for b in BLOG]
VIDCH = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


HUMAN = frozenset(ua for ua, _, _ in UAS)


def crawl_kind(agent: str) -> str:
    if "-User/" in agent:
        return "asked"
    if any(name in agent for name in TRAINING):
        return "training"
    return "search" if any(name in agent for name in SEARCHERS) else "other"


def size_of(path: str, status: int = 200, method: str = "GET") -> int:
    """The body size a path is sent with: fixed per path, so a page weighs
    the same every time (a blog post more than a landing page)."""
    bare = path.split("?", 1)[0]
    h = zlib.crc32(bare.encode())
    if method == "POST":
        return 48 + h % 40
    if status >= 500:
        return 150 + h % 400
    if status == 404:
        return 9_400 + h % 600
    if bare in SIZES:
        return SIZES[bare]
    if bare.endswith(".md"):
        return 9_000 + h % 17_000
    if bare.startswith("/blog/") and bare != "/blog/":
        return 58_000 + h % 50_000
    if bare.startswith("/guides/"):
        return 41_000 + h % 38_000
    return 22_000 + h % 26_000


def line(when: datetime, address: str, path: str, agent: str, referrer: str = "-", status: int = 200,
         country: str = "US", method: str = "GET", size: int = 512, secs: float = 0.004) -> str:
    """One nginx_extended line (the format DEPLOY.md sets up), host example.com, with the
    optional request_length= field (INGEST.md), so Security's large-POST sign is recorded."""
    return (f'{when.isoformat()} {address} {SITE} "{method} {path} HTTP/2.0" '
            f'{status} {size} "{referrer}" "{agent}" {secs:.3f} cc={country} '
            f'ray=0000000000000000-LHR request_length={request_length(path, agent, referrer, method)}\n')


def request_length(path: str, agent: str, referrer: str = "-", method: str = "GET") -> int:
    """The request's size as nginx's $request_length counts it (line, headers, body): about
    the request line and headers, a small form body for a POST. No random draw."""
    return 260 + len(path) + len(agent) + (len(referrer) if referrer != "-" else 0) + (640 if method == "POST" else 0)


@dataclass
class Traffic:
    now: datetime                     # UTC, the last moment with traffic
    today: date                       # the site's day of `now`
    first: date                       # the first day with traffic
    lines: list[str] = field(default_factory=list)
    beacon: list[tuple] = field(default_factory=list)    # (when UTC, address, agent, event dict)
    hooks: list[tuple] = field(default_factory=list)     # (when UTC, tool, {"vid", "utm"})
    leads: list[dict] = field(default_factory=list)
    country_of: dict[str, str] = field(default_factory=dict)


class _Maker:
    def __init__(self, now: datetime, days: int, seed: int) -> None:
        self.rnd = random.Random(seed)
        self.tz = ZoneInfo(TZ_NAME)
        self.now = now.astimezone(UTC).replace(microsecond=0)
        today = self.now.astimezone(self.tz).date()
        self.days = days
        self.t = Traffic(self.now, today, today - timedelta(days=days))
        addresses = [f"192.0.2.{i}" for i in range(1, 255) if f"192.0.2.{i}" != OFFICE] + \
                    [f"203.0.113.{i}" for i in range(1, 250)]
        self.t.country_of = {ip: self.pick(COUNTRIES) for ip in addresses}
        self.pools = {ua: self.rnd.sample(addresses, len(addresses)) for ua, _, _ in UAS}
        self.uaw = [((ua, vw), w) for ua, w, vw in UAS]
        self.vid_of: dict[tuple, str | None] = {}
        self.seen: list[tuple] = []
        self.info: dict[tuple, dict] = {}
        self.cur = ("", "")
        self.xr = random.Random(seed + 2)      # sizes, times, errors, pre-fetches: never the main draws
        self.cited: list[tuple] = []           # (when, assistant host, landing page) of each AI-cited visit

    def line(self, when, address, path, agent, referrer="-", status=200, country="US", method="GET") -> str:
        """line() with a body size and a response time drawn for what was asked:
        static files fast, a person's page from the cache, a crawler's page
        slower the bigger it is, a 5xx slowest."""
        x = self.xr
        size = size_of(path, status, method)
        if status >= 500:
            secs = x.uniform(0.25, 0.9)
        elif method == "POST":
            secs = x.uniform(0.08, 0.35)
        elif status == 404 or path in SIZES or path.endswith((".txt", ".xml", ".md")):
            secs = x.uniform(0.001, 0.006) + size / 2_000_000 * x.uniform(0.5, 1.5)
        elif agent in HUMAN:
            secs = x.lognormvariate(-3.6 + size / 400_000, 0.55)
            size = int(size * x.uniform(0.98, 1.02))          # compression varies a little
        else:
            secs = x.lognormvariate(-2.4 + size / 120_000, 0.45)
        return line(when, address, path, agent, referrer, status, country, method, size, min(0.9, max(0.004, secs)))

    def pick(self, pairs):
        total = sum(w for _, w in pairs)
        x = self.rnd.uniform(0, total)
        for v, w in pairs:
            x -= w
            if x <= 0:
                return v
        return pairs[-1][0]

    def vid(self) -> str:
        return "skv_" + "".join(self.rnd.choice(VIDCH) for _ in range(22))

    def new_identity(self, tracked: float = 0.86) -> tuple:
        while True:
            ua, vw = self.pick(self.uaw)
            if self.pools[ua]:
                identity = (self.pools[ua].pop(), ua, vw)
                break
        self.vid_of[identity] = self.vid() if self.rnd.random() < tracked else None
        self.seen.append(identity)
        self.info[identity] = {"visits": 1, "first": None}
        return identity

    def ev(self, t, e, p, vid, host, utm, vw, id="", tt=5):
        self.t.beacon.append((t, self.cur[0], self.cur[1],
                              {"e": e, "p": p, "id": id, "r": host, "u": utm, "vw": vw, "t": tt, "v": vid}))

    def source(self, returning: bool, force=None):
        kind = force or ("direct" if returning and self.rnd.random() < 0.45 else self.pick(SOURCES))
        ref, q, touch = "-", "", {}
        if kind == "search":
            ref = self.pick(SEARCH)
        elif kind == "social":
            ref = self.pick(SOCIAL)
        elif kind == "ai":
            ref = self.pick(AI)
        elif kind == "referral":
            ref = self.pick(REFERRAL)
        elif kind == "email":
            q = "?utm_source=newsletter&utm_medium=email&utm_campaign=october-update"
            touch = {"utmSource": "newsletter", "utmMedium": "email", "utmCampaign": "october-update"}
        elif kind == "paid":
            ref = "https://www.google.com/"
            q = "?utm_source=google&utm_medium=cpc&utm_campaign=fall-launch&gclid=EAIaIQdemo"
            touch = {"utmSource": "google", "utmMedium": "cpc", "utmCampaign": "fall-launch", "gclid": "EAIaIQdemo"}
        elif kind == "social_paid":
            ref = "https://www.linkedin.com/"
            q = "?utm_source=linkedin&utm_medium=paid-social&utm_campaign=fall-launch"
            touch = {"utmSource": "linkedin", "utmMedium": "paid-social", "utmCampaign": "fall-launch"}
        host = "" if ref == "-" else ref.split("/")[2].removeprefix("www.")
        touch["referrerHost"] = host
        if kind == "ai":
            touch["aiSource"] = host
        return kind, ref, q, host, touch

    def visit(self, t, identity, returning, first_touch, nvisits, force=None, force_path=None, keen=False):
        """One visit: pages through the site, its assets, its in-page events,
        and the leads and bookings it ends in. keen: a visitor reading on now (right_now),
        who stays for more pages and moves on sooner."""
        rnd, T = self.rnd, self.t
        ip, ua, vw = identity
        self.cur = (ip, ua)
        kind, ref, q, host, touch = self.source(returning, force)
        utm = touch.get("utmSource") or ""
        cc = T.country_of[ip]
        vid = self.vid_of[identity]
        path = force_path or self.pick(LAND[kind])
        if kind == "ai":
            self.cited.append((t, host, path))
        pages, cur, prev_url, url, stay = [], path, ref, path + q, 0.62
        while True:
            T.lines.append(self.line(t, ip, url, ua, prev_url, country=cc))
            if rnd.random() < 0.7:
                for a in ASSETS[: rnd.randrange(1, 4)]:
                    T.lines.append(self.line(t + timedelta(seconds=1), ip, a, ua, "https://example.com" + cur, country=cc))
            pages.append((t, cur))
            if vid is not None:
                self.events(t, cur, vid, host, utm, vw, nvisits, first_touch, touch, path, cc)
            if rnd.random() > STAY.get(cur, 0.82 if keen else stay):
                break
            stay = 0.5
            lo, hi = (15, 70) if keen else next((v for k, v in DWELL.items() if cur.startswith(k)), (12, 120))
            t += timedelta(seconds=rnd.randrange(lo, hi))
            nxt = self.pick(NEXT.get(cur, [("/", 1)]))
            prev_url, cur, url = "https://example.com" + cur, nxt, nxt
            if rnd.random() < 0.012:
                T.lines.append(self.line(t, ip, "/blog/old-launch-post", ua, prev_url, status=404, country=cc))
        return pages, touch

    def form_sent(self, at, kind, page, cc):
        """The form's POST to the site's own endpoint, a second before the lead
        is stored: what lets a person search tie a lead to its visit by time."""
        ip, ua = self.cur
        self.t.lines.append(self.line(at - timedelta(seconds=1), ip, f"/api/forms/{kind}", ua,
                                 "https://example.com" + page, country=cc, method="POST"))

    def events(self, t, cur, vid, host, utm, vw, nvisits, first_touch, touch, path, cc):
        rnd, T = self.rnd, self.t
        s = timedelta(seconds=1)
        self.ev(t + s, "page_view", cur, vid, host, utm, vw)
        if cur in ("/pricing/", "/features/") and rnd.random() < 0.15:
            self.ev(t + 12 * s, "cta_click", cur, vid, host, utm, vw, id="pricing_cta" if cur == "/pricing/" else "hero_cta")
        if cur.startswith("/blog/") and cur != "/blog/" and rnd.random() < 0.45:
            self.ev(t + 70 * s, "scroll_75", cur, vid, host, utm, vw)
        last = {**touch, "landingPath": path, "at": t}
        if cur == "/signup/" and rnd.random() < 0.5:
            self.ev(t + 6 * s, "signup_start", cur, vid, host, utm, vw, id="signup_form")
            if rnd.random() < (0.55 if nvisits > 1 else 0.2):
                if rnd.random() < 0.25:
                    T.hooks.append((t + timedelta(hours=rnd.choice([1, 5, 30, 70, 150])), "stripe", {"vid": vid}))
                at = t + timedelta(seconds=rnd.randrange(40, 160))
                self.form_sent(at, "signup", cur, cc)
                T.leads.append({"at": at, "type": "signup", "vid": vid,
                                "first": first_touch, "last": last, "visits": nvisits, "cc": cc})
        if cur == "/contact/" and rnd.random() < 0.5:
            self.ev(t + 8 * s, "form_start", cur, vid, host, utm, vw, id="contact_form")
            if rnd.random() < (0.75 if nvisits > 1 else 0.3):
                at = t + timedelta(seconds=rnd.randrange(50, 200))
                self.form_sent(at, "contact", cur, cc)
                T.leads.append({"at": at, "type": "contact", "vid": vid,
                                "first": first_touch, "last": last, "visits": nvisits, "cc": cc})
            if rnd.random() < 0.12:
                self.ev(t + 20 * s, "mailto_click", cur, vid, host, utm, vw, id="sales_email")
        if cur == "/book-a-demo/" and rnd.random() < 0.8:
            self.ev(t + 4 * s, "calendly_open", cur, vid, host, utm, vw, id="demo_widget")
            if rnd.random() < 0.45:
                self.ev(t + 45 * s, "calendly_time_selected", cur, vid, host, utm, vw, id="demo_widget")
                if rnd.random() < 0.7:
                    T.hooks.append((t + timedelta(seconds=rnd.randrange(70, 140)), "calendly", {"vid": vid, "utm": utm}))

    # ---------------------------------------------------------- one day
    def day(self, day: date) -> None:
        rnd, T = self.rnd, self.t
        start = datetime(day.year, day.month, day.day, tzinfo=self.tz)
        k = (day - T.first).days
        frac = 1.0
        if day == T.today:
            frac = max(0.01, (self.now.astimezone(self.tz) - start).total_seconds() / 86400)
        span = max(60, int(86400 * frac))
        base = (40 if day.weekday() >= 5 else 72) * (1 + 0.3 * k / self.days) * rnd.uniform(0.86, 1.14)
        if k in (self.days - 19, self.days - 18):          # a launch post did well
            base *= 1.55
        for t in sorted(start + timedelta(seconds=int(rnd.betavariate(2.3, 2.0) * span)) for _ in range(int(base * frac))):
            t = t.astimezone(UTC)
            if self.seen and rnd.random() < 0.24:
                identity = self.seen[rnd.randrange(max(0, len(self.seen) - 1200), len(self.seen))]
                self.info[identity]["visits"] += 1
                returning = True
            else:
                identity, returning = self.new_identity(), False
            it = self.info[identity]
            pages, touch = self.visit(t, identity, returning, it["first"], it["visits"])
            if it["first"] is None:
                it["first"] = {**touch, "at": t, "landingPath": pages[0][1]}
        self.likely_ai(day, start, span, k)
        for agent, ip, (lo, hi) in BOTS:
            for _ in range(rnd.randrange(lo, hi + 1)):
                t = (start + timedelta(seconds=rnd.randrange(0, span))).astimezone(UTC)
                path, status = self.pick(CRAWL[crawl_kind(agent)]), 200
                e = self.xr.random()
                if e < 0.03:                    # an old link, or a Markdown copy that was never made
                    path, status = self.xr.choice(GONE), 404
                elif e < 0.04:
                    status = self.xr.choice([500, 502, 503, 504])
                T.lines.append(self.line(t, ip, path, agent, status=status))
        if rnd.random() < 0.25:     # someone claims to be GPTBot from a home address
            T.lines.append(self.line((start + timedelta(hours=9)).astimezone(UTC), "203.0.113.251", "/pricing/", GPTBOT))
        for _ in range(rnd.randrange(1, 4)):       # scanners
            t = (start + timedelta(seconds=rnd.randrange(0, span))).astimezone(UTC)
            T.lines.append(self.line(t, "198.51.100.200", rnd.choice(["/.env", "/wp-login.php", "/.git/config", "/xmlrpc.php"]),
                                rnd.choice(["curl/8.7.1", "python-requests/2.31", "Go-http-client/1.1"]), status=404))
        if day.weekday() < 5:                       # the team's own visits, from the office
            for _ in range(rnd.randrange(3, 9)):
                t = (start + timedelta(hours=9, seconds=rnd.randrange(0, 30000))).astimezone(UTC)
                T.lines.append(self.line(t, OFFICE, rnd.choice(["/", "/pricing/", "/blog/fall-launch"]), UAS[0][0]))

    def likely_ai(self, day, start, span, k) -> None:
        """An assistant fetches a page for someone; minutes later a browser
        lands on it directly, with no referrer: likely sent by that assistant."""
        rnd, T = self.rnd, self.t
        recent = k >= self.days - 9
        for j in range(rnd.randrange(3, 7) if recent else rnd.randrange(0, 3)):
            tf = (start + timedelta(seconds=rnd.randrange(600, max(1200, span - 60)))).astimezone(UTC)
            if tf > self.now - timedelta(minutes=12):
                continue
            page = self.pick(FETCHED)
            fua, fip = self.pick([((ua, ip), w) for ua, ip, w in FETCHERS])
            T.lines.append(self.line(tf, fip, page, fua))
            if j == 0 and k % 3 == 0:     # both assistants fetched it: "more than one"
                other = FETCHERS[1] if fip == FETCHERS[0][1] else FETCHERS[0]
                T.lines.append(self.line(tf + timedelta(seconds=40), other[1], page, other[0]))
            tv = tf + timedelta(seconds=rnd.randrange(60, 600))
            identity = self.new_identity(tracked=1.0)
            pages, touch = self.visit(tv, identity, False, None, 1, force="direct", force_path=page)
            self.info[identity]["first"] = {**touch, "at": tv, "landingPath": page}
            if recent and k in (self.days - 4, self.days - 6) and j < 2:   # became a lead, minutes later
                ip, ua, vw = identity
                vid = self.vid_of[identity]
                self.cur = (ip, ua)
                ts = tv + timedelta(minutes=4)
                T.lines.append(self.line(ts, ip, "/signup/", ua, "https://example.com" + page, country=T.country_of[ip]))
                self.ev(ts + timedelta(seconds=1), "page_view", "/signup/", vid, "", "", vw)
                self.ev(ts + timedelta(seconds=6), "signup_start", "/signup/", vid, "", "", vw, id="signup_form")
                self.form_sent(ts + timedelta(seconds=90), "signup", "/signup/", T.country_of[ip])
                T.leads.append({"at": ts + timedelta(seconds=90), "type": "signup", "vid": vid,
                                "first": self.info[identity]["first"], "last": {**touch, "landingPath": page, "at": tv},
                                "visits": 1, "cc": T.country_of[ip]})


    # ------------------------------------------------- today's leads
    TODAY_LEADS = [   # (share of the day so far, source, landing page, what they send)
        (0.35, "search", "/pricing/", "contact"),
        (0.6, "ai", "/blog/ai-crawlers-explained", "signup"),
        (0.85, "email", "/customers/", "demo"),
    ]

    def today_leads(self) -> None:
        """A few leads and a booking earlier today, so Live's "Leads and
        bookings today" has rows at any hour after the first. Drawn after
        every day is made: the days before stay as they were."""
        T, s = self.t, timedelta(seconds=1)
        start = datetime(T.today.year, T.today.month, T.today.day, tzinfo=self.tz)
        elapsed = self.now - start
        if elapsed < timedelta(hours=1):
            return
        for share, kind, landing, sends in self.TODAY_LEADS:
            t = (start + elapsed * share).astimezone(UTC).replace(microsecond=0)
            if t > self.now - timedelta(minutes=8):
                continue
            identity = self.new_identity(tracked=1.0)
            ip, ua, vw = identity
            self.cur = (ip, ua)
            _, ref, q, host, touch = self.source(False, kind)
            if kind == "ai":
                self.cited.append((t, host, landing))
            utm, cc, vid = touch.get("utmSource") or "", T.country_of[ip], self.vid_of[identity]
            page = {"contact": "/contact/", "signup": "/signup/", "demo": "/book-a-demo/"}[sends]
            T.lines.append(self.line(t, ip, landing + q, ua, ref, country=cc))
            self.ev(t + s, "page_view", landing, vid, host, utm, vw)
            t2 = t + timedelta(seconds=self.rnd.randrange(40, 150))
            T.lines.append(self.line(t2, ip, page, ua, "https://example.com" + landing, country=cc))
            self.ev(t2 + s, "page_view", page, vid, host, utm, vw)
            first = {**touch, "landingPath": landing, "at": t}
            self.info[identity]["first"] = first
            if sends == "demo":
                self.ev(t2 + 4 * s, "calendly_open", page, vid, host, utm, vw, id="demo_widget")
                self.ev(t2 + 45 * s, "calendly_time_selected", page, vid, host, utm, vw, id="demo_widget")
                T.hooks.append((t2 + timedelta(seconds=100), "calendly", {"vid": vid, "utm": utm}))
                continue
            started = "signup_start" if sends == "signup" else "form_start"
            self.ev(t2 + 6 * s, started, page, vid, host, utm, vw, id=f"{sends}_form")
            at = t2 + timedelta(seconds=self.rnd.randrange(50, 140))
            self.form_sent(at, sends, page, cc)
            T.leads.append({"at": at, "type": sends, "vid": vid, "first": first, "last": first,
                            "visits": 1, "cc": cc})


    # ------------------------------------------------- the last half hour
    NOW_VISITS = (28, 23, 19, 15, 12, 9, 7, 5, 4, 3, 2, 1, 1)   # minutes before `now`
    NOW_MACHINES = ((GPTBOT, "198.51.100.2", "training"), (CHATGPT_USER, "198.51.100.3", "asked"),
                    (CHATGPT_USER, "198.51.100.3", "asked"), (CLAUDE_USER, "198.51.100.19", "asked"))

    def right_now(self) -> None:
        """Visits and a few AI fetches in the last half hour, so Overview >
        Real time has someone on the site whenever the demo is built. Drawn
        after every day is made: the days before stay as they were."""
        T, rnd = self.t, self.rnd
        start = datetime(T.today.year, T.today.month, T.today.day, tzinfo=self.tz)
        if self.now - start < timedelta(minutes=40):
            return
        for ago in self.NOW_VISITS:
            # Started a few minutes earlier and still reading, so "What visitors are doing now"
            # shows a path of pages, not one page each.
            t = (self.now - timedelta(minutes=ago, seconds=rnd.randrange(0, 50) + rnd.randrange(60, 300))).replace(microsecond=0)
            identity = self.new_identity()
            pages, touch = self.visit(t, identity, False, None, 1, keen=True)
            if self.info[identity]["first"] is None:
                self.info[identity]["first"] = {**touch, "at": t, "landingPath": pages[0][1]}
        for agent, ip, kind in self.NOW_MACHINES:
            t = (self.now - timedelta(seconds=rnd.randrange(60, 1700))).replace(microsecond=0)
            T.lines.append(self.line(t, ip, self.pick(CRAWL[kind]), agent))

    def prefetch(self) -> None:
        """Before many visits cited by ChatGPT, Perplexity or Claude, that
        assistant's user fetcher read pages minutes earlier: usually the page
        the visit landed on and one to three others, now and then only others."""
        x, T = self.xr, self.t
        others = [p for p, _ in FETCHED] + ["/", "/customers/", "/llms.txt"] + MD
        for tv, host, landing in self.cited:
            if host not in FETCHER_OF or x.random() > 0.62:
                continue
            agent, ip = FETCHER_OF[host]
            read = [] if x.random() < 0.15 else [landing]
            read += x.sample([p for p in others if p != landing], x.choice([1, 1, 2, 2, 3]))
            for i, path in enumerate(read):
                ago = x.randrange(60, 420) if i == 0 else x.randrange(70, 840)
                T.lines.append(self.line(tv - timedelta(seconds=ago), ip, path, agent))


def generate(now: datetime, days: int = 62, seed: int = SEED) -> Traffic:
    """`days` whole days of traffic before `now`'s day, and that day up to `now`."""
    if days < 2:
        raise ValueError("days must be at least 2")
    m = _Maker(now, days, seed)
    d = m.t.first
    while d <= m.t.today:
        m.day(d)
        d += timedelta(days=1)
    m.today_leads()
    m.right_now()
    m.prefetch()
    # Security's scanners and attack attempts, from a generator of their own (demo_security.py).
    import demo_security
    demo_security.add(m.t.lines, m.t.first, m.t.today, m.tz, m.now, seed)
    heartbeat(m.t.lines, m.t.first, m.now, m.tz)
    T, cut = m.t, m.now
    T.lines = sorted((x for x in T.lines if x.split(" ", 1)[0] <= cut.isoformat()), key=lambda x: x.split(" ", 1)[0])
    T.beacon = sorted((b for b in T.beacon if b[0] <= cut), key=lambda b: b[0])
    T.hooks = sorted((h for h in T.hooks if h[0] <= cut), key=lambda h: h[0])
    T.leads = [x for x in T.leads if x["at"] <= cut]
    return T


HEARTBEAT = "example-heartbeat/1.0"     # ours.user_agents labels it "heartbeat" (demo.py's config)
SERVER = "192.0.2.10"


def heartbeat(lines: list, first: date, now: datetime, tz) -> None:
    """The 5-minute heartbeat the server sends itself (Site > Health's uptime), with one
    15-minute outage five days before today (three beats answered 502). No random draw."""
    t = datetime(first.year, first.month, first.day, tzinfo=tz).astimezone(UTC)
    down = datetime.combine(now.astimezone(tz).date() - timedelta(days=5), datetime.min.time(), tz) \
        + timedelta(hours=3, minutes=10)
    while t <= now:
        failed = down <= t.astimezone(tz) < down + timedelta(minutes=15)
        lines.append(line(t, SERVER, "/", HEARTBEAT, status=502 if failed else 200,
                          size=166 if failed else 512, secs=0.9 if failed else 0.012))
        t += timedelta(minutes=5)


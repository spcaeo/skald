"""What a log line can say about a reader, beyond who they are.

Each function here turns one field of one request into one label: a browser
family, an operating system, a device type, a kind of traffic source, a
campaign, an hour, a response-time bucket, a status class. aggregate.Tally
counts readers (visits that read a page) under each label once, at the
visit's first page view, so every breakdown adds up to the readers exactly -
verify.py checks it.

What these labels honestly are:

  * Browser, system and device come from the user agent, which is
    self-reported. Brave sends Chrome's agent and is counted as Chrome; an
    iPad asking for the desktop site sends a Mac's and is counted as a Mac.
  * The source is the referrer of the first page read, often stripped:
    "Direct" includes every visitor whose referrer was withheld.
  * A campaign is what the landing URL's utm_ tags (or an ad click id) say,
    nothing more.

Only labels are kept. The user agent and the referrer URL themselves are
never stored, so a breakdown can be shared like any other total.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import tzinfo
from urllib.parse import parse_qsl, urlsplit

# ------------------------------------------------------------ user agents

# In-app browsers first: they carry a full browser's agent plus a marker, and
# the marker is the more useful answer ("came from the LinkedIn app").
IN_APP = [
    ("Facebook app", re.compile(r"FBAN/|FBAV/|FB_IAB|FBIOS", re.I)),
    ("Instagram app", re.compile(r"\bInstagram\b", re.I)),
    ("LinkedIn app", re.compile(r"LinkedInApp", re.I)),
    ("Gmail app", re.compile(r"\bGmail\b|GmailWebView", re.I)),
    ("Google app", re.compile(r"\bGSA/", re.I)),
    ("X (Twitter) app", re.compile(r"Twitter for|TwitterAndroid", re.I)),
    ("TikTok app", re.compile(r"musical_ly|BytedanceWebview|TikTok", re.I)),
    ("Snapchat app", re.compile(r"Snapchat", re.I)),
    ("Pinterest app", re.compile(r"\[Pinterest/", re.I)),
    ("WeChat", re.compile(r"MicroMessenger", re.I)),
    ("Line app", re.compile(r"\bLine/\d", re.I)),
]

BROWSERS = [
    ("Samsung Internet", re.compile(r"SamsungBrowser/", re.I)),
    ("Opera", re.compile(r"\bOPR/|\bOPT/|Opera[/ ]|OPiOS/", re.I)),
    ("Edge", re.compile(r"\bEdg(?:e|A|iOS)?/", re.I)),
    ("Yandex Browser", re.compile(r"YaBrowser/", re.I)),
    ("Firefox", re.compile(r"Firefox/|FxiOS/", re.I)),
    ("Chrome", re.compile(r"Chrome/|CriOS/|Chromium/", re.I)),
    # Safari names its version as Version/N; a WebView on iOS does not.
    ("Safari", re.compile(r"Version/[\d.]+.*Safari/", re.I)),
]
IOS_WEBVIEW = re.compile(r"(?:iPhone|iPad|iPod).*AppleWebKit(?!.*Safari/)", re.I)
ANDROID_WEBVIEW = re.compile(r"; wv\)", re.I)

SYSTEMS = [
    ("iOS", re.compile(r"iPhone|iPad|iPod", re.I)),
    ("Android", re.compile(r"Android", re.I)),
    ("ChromeOS", re.compile(r"\bCrOS\b", re.I)),
    ("Windows", re.compile(r"Windows", re.I)),
    ("macOS", re.compile(r"Macintosh|Mac OS X", re.I)),
    ("Linux", re.compile(r"Linux|X11", re.I)),
]

BROWSER_NAMES = [name for name, _ in IN_APP] + [name for name, _ in BROWSERS] + [
    "In-app browser (iOS)", "In-app browser (Android)", "Other"]
SYSTEM_NAMES = [name for name, _ in SYSTEMS] + ["Other"]
DEVICES = ["Desktop", "Mobile", "Tablet"]


def browser(agent: str) -> str:
    for name, pattern in IN_APP:
        if pattern.search(agent):
            return name
    if ANDROID_WEBVIEW.search(agent):
        return "In-app browser (Android)"
    for name, pattern in BROWSERS:
        if pattern.search(agent):
            return name
    if IOS_WEBVIEW.search(agent):
        return "In-app browser (iOS)"
    return "Other"


def system(agent: str) -> str:
    for name, pattern in SYSTEMS:
        if pattern.search(agent):
            return name
    return "Other"


def device(agent: str) -> str:
    """Desktop, mobile or tablet. Only ever asked about readers, so bots are
    never in it. An Android device without "Mobile" is a tablet - that is
    how Android browsers say so."""
    if re.search(r"iPad|Tablet|Kindle|Silk/|PlayBook", agent, re.I):
        return "Tablet"
    if re.search(r"Android", agent, re.I) and not re.search(r"Mobile", agent, re.I):
        return "Tablet"
    if re.search(r"Mobi|iPhone|iPod|Android|Windows Phone", agent, re.I):
        return "Mobile"
    return "Desktop"


_AGENTS: dict[str, tuple[str, str, str]] = {}


def agent_labels(agent: str) -> tuple[str, str, str]:
    """(browser, system, device), worked out once per distinct agent."""
    got = _AGENTS.get(agent)
    if got is None:
        if len(_AGENTS) > 50_000:
            _AGENTS.clear()
        got = _AGENTS[agent] = (browser(agent), system(agent), device(agent))
    return got


# --------------------------------------------------------------- sources

SOURCE_TYPES = ["AI assistant", "Search engine", "Social media", "Email",
                "Other website", "This site", "Tagged link", "Direct or unknown"]

# Google's web search by its real domains (google.com, google.de,
# google.co.uk, google.com.au), never by the word: com.google.android.<app>
# is an Android app's id, and only the search app among them is a search.
_SEARCH = re.compile(
    r"(?:^|\.)(?:google\.(?:com(?:\.[a-z]{2})?|co\.[a-z]{2}|[a-z]{2,3})"
    r"|bing\.com|duckduckgo\.com|yahoo\.com|yandex\.[a-z.]+"
    r"|baidu\.com|ecosia\.org|search\.brave\.com|startpage\.com|qwant\.com"
    r"|naver\.com|seznam\.cz|kagi\.com|yep\.com|aol\.com)$"
    r"|^com\.google\.android\.googlequicksearchbox$")
_SOCIAL = re.compile(
    r"(?:^|\.)(?:facebook\.com|fb\.com|instagram\.com|linkedin\.com|lnkd\.in|t\.co"
    r"|twitter\.com|x\.com|reddit\.com|youtube\.com|youtu\.be|pinterest\.[a-z.]+"
    r"|tiktok\.com|threads\.net|ycombinator\.com|quora\.com|t\.me|whatsapp\.com"
    r"|slack\.com|discord\.com|bsky\.app|mastodon\.social)$"
    r"|^com\.(?:linkedin|facebook|instagram|twitter|reddit|slack)[a-z.]*$"
    r"|^(?:com\.google\.android\.youtube|com\.whatsapp|org\.telegram\.messenger)"
    r"(?:\.[a-z0-9.]*)?$")
_EMAIL = re.compile(
    r"^(?:mail\.google\.com|outlook\.(?:live|office|office365)\.com|mail\.yahoo\.com"
    r"|mail\.proton\.me|com\.google\.android\.gm|com\.microsoft\.office\.outlook)$")
_UTM_WORDS = (("Search engine", ("google", "bing", "duckduckgo", "yahoo", "cpc", "ppc")),
              ("Social media", ("linkedin", "facebook", "instagram", "twitter", "x",
                                "reddit", "youtube", "tiktok", "social")),
              ("Email", ("email", "newsletter", "mailchimp", "hubspot", "gmail")))
# An ad click id with no utm_ tag: the source type and the campaign it says,
# for every id in classify.CLICK_ID_PARAMS (campaigns.CLICK_IDS names their
# networks), first match wins.
_CLICK_IDS = (("gclid", "Search engine", "google / cpc / (gclid)"),
              ("gbraid", "Search engine", "google / cpc / (gbraid)"),
              ("wbraid", "Search engine", "google / cpc / (wbraid)"),
              ("msclkid", "Search engine", "bing / cpc / (msclkid)"),
              ("fbclid", "Social media", "facebook / (fbclid) / -"),
              ("li_fat_id", "Social media", "linkedin / (li_fat_id) / -"),
              ("ttclid", "Social media", "tiktok / (ttclid) / -"),
              ("twclid", "Social media", "x / (twclid) / -"))


def _utm_kind(value: str) -> str:
    """The source type one utm_ tag's words name, or ""."""
    words = set(re.split(r"[^a-z0-9]+", value.lower()))
    for kind, keys in _UTM_WORDS:
        if words & set(keys):
            return kind
    return ""


def referrer_host(referrer: str) -> str:
    """The referrer's host, without "www.". An app referrer
    (android-app://com.linkedin.android/) gives the app's id."""
    if not referrer:
        return ""
    parts = urlsplit(referrer if "//" in referrer else "//" + referrer)
    host = (parts.hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def source_type(referrer: str, url: str, cited: bool, own_hosts: set[str]) -> str:
    """Where a reader came from, as one of SOURCE_TYPES."""
    if cited:
        return "AI assistant"
    host = referrer_host(referrer)
    if host:
        if host in own_hosts or "www." + host in own_hosts:
            return "This site"
        # Webmail before search: mail.google.com is not a Google search.
        if _EMAIL.search(host):
            return "Email"
        if _SEARCH.search(host):
            return "Search engine"
        if _SOCIAL.search(host):
            return "Social media"
        return "Other website"
    tags = query(url)
    if tags.get("utm_source") or tags.get("utm_medium"):
        # The source names the place; the medium only says how (cpc is paid
        # search or paid social), so it decides only when the source can't.
        return (_utm_kind(tags.get("utm_source", ""))
                or _utm_kind(tags.get("utm_medium", "")) or "Tagged link")
    for key, kind, _ in _CLICK_IDS:
        if tags.get(key):
            return kind
    return "Direct or unknown"


# Sources that continue a visit: a page reached from the site itself, or with
# no referrer and no tag (a reload, a typed address, an app). Any other
# source - an assistant, a website, a search engine, social, email, a tagged
# link - is an outside arrival.
INSIDE_SOURCES = ("This site", "Direct or unknown")


def page_origin(referrer: str, url: str, cited: bool, own_hosts: set[str]) -> tuple | None:
    """Where one page view came from: (source, referrer, campaign) labels,
    as a reader is labelled. Two page views come from the same place when
    these are equal. None when the site's own hosts are not known (no
    site.hosts and a line without a host): a link from the site itself
    cannot then be told from one from outside, so it never splits a visit."""
    if not own_hosts:
        return None
    return (source_type(referrer, url, cited, own_hosts),
            referrer_label(referrer, own_hosts), campaign(url))


def new_source(origin: tuple | None, visit_origin: tuple | None) -> bool:
    """The session rule's second half (the first is the gap): a page that
    arrives from outside, from somewhere other than where the open visit's
    first page came from, starts a new visit. `origin` is None for a request
    that is not a page view; `visit_origin` is None while the visit has read
    no page yet (the page then becomes its first)."""
    return (origin is not None and visit_origin is not None
            and origin[0] not in INSIDE_SOURCES and origin != visit_origin)


def referrer_label(referrer: str, own_hosts: set[str]) -> str:
    host = referrer_host(referrer)
    if not host:
        return "(none)"
    if host in own_hosts or "www." + host in own_hosts:
        return "(this site)"
    return host[:60]


def query(url: str) -> dict[str, str]:
    if "?" not in url:
        return {}
    try:
        return {k.lower(): v for k, v in parse_qsl(url.split("?", 1)[1])[:40]}
    except ValueError:
        return {}


NO_CAMPAIGN = "(no campaign tag)"


def campaign(url: str) -> str:
    """'source / medium / campaign' from utm_ tags, or the ad click id that
    says the same. Lower case, so 'LinkedIn' and 'linkedin' are one row."""
    tags = query(url)
    src, med, name = (tags.get("utm_source", ""), tags.get("utm_medium", ""),
                      tags.get("utm_campaign", ""))
    if not (src or med or name):
        for key, _, said in _CLICK_IDS:
            if tags.get(key):
                return said
        return NO_CAMPAIGN
    return " / ".join((v or "-").strip().lower()[:30] for v in (src, med, name))


# ------------------------------------------------------- time and status

def hour(when, tz: tzinfo | None) -> str:
    """'00' to '23', in the report's own time zone."""
    if tz is not None and when.tzinfo is not None:
        when = when.astimezone(tz)
    return f"{when.hour:02d}"


HOURS = [f"{h:02d}" for h in range(24)]

SPEEDS = ["under 0.2 s", "0.2 to 0.5 s", "0.5 to 1 s", "1 to 3 s", "3 s or more",
          "not logged"]
SLOW = ("1 to 3 s", "3 s or more")


def speed(seconds: float | None) -> str:
    """The server's time to answer ($request_time), as a bucket."""
    if seconds is None:
        return "not logged"
    for limit, name in ((0.2, SPEEDS[0]), (0.5, SPEEDS[1]), (1, SPEEDS[2]),
                        (3, SPEEDS[3])):
        if seconds < limit:
            return name
    return SPEEDS[4]


STATUSES = ["2xx", "3xx", "404", "4xx", "5xx", "other"]


def status_class(status: str) -> str:
    if status == "404":
        return "404"
    head = status[:1]
    return {"2": "2xx", "3": "3xx", "4": "4xx", "5": "5xx"}.get(head, "other")


# ------------------------------------------------------------- top lists

OTHER = "(all others)"


def fold(counter: Counter, top: int) -> Counter:
    """The top entries, and everything else summed into one OTHER row.

    Cutting a list to its top N loses the tail; folding it keeps the total,
    so a breakdown still adds up to the readers it was taken from.
    """
    if len(counter) <= top:
        return Counter(dict(counter.most_common()))
    kept = counter.most_common(top - 1)
    rest = sum(counter.values()) - sum(n for _, n in kept)
    out = Counter(dict(kept))
    if rest:
        out[OTHER] += rest
    return out

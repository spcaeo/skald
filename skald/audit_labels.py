"""The audit's own labels for a reader: browser, system, device, source,
referrer, campaign and status class. Part of audit.py's second road.

Written apart from dimensions.py and campaigns.py on purpose: nothing here
calls the package's label code, so when the recount and history disagree
one of two separately written rule sets is wrong. Phase 4 recounts
(audit_more.py) label visits with these, never with dimensions.py.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlsplit

if TYPE_CHECKING:                       # the type only, never the code
    from .audit import Line


def _host_of(url: str) -> str:
    try:
        return (urlsplit(url if "//" in url else "//" + url).hostname or "").lower()
    except ValueError:
        return ""


def browser_of(agent: str) -> str:
    a = agent
    apps = (("FBAN/", "Facebook app"), ("FBAV/", "Facebook app"),
            ("FB_IAB", "Facebook app"), ("FBIOS", "Facebook app"),
            ("Instagram", "Instagram app"), ("LinkedInApp", "LinkedIn app"),
            ("GmailWebView", "Gmail app"), ("GSA/", "Google app"),
            ("Twitter for", "X (Twitter) app"), ("TwitterAndroid", "X (Twitter) app"),
            ("musical_ly", "TikTok app"), ("BytedanceWebview", "TikTok app"),
            ("TikTok", "TikTok app"), ("Snapchat", "Snapchat app"),
            ("[Pinterest/", "Pinterest app"), ("MicroMessenger", "WeChat"))
    low = a.lower()
    for token, name in apps:
        if token.lower() in low:
            # Instagram and Gmail are words: require them as whole words.
            if token in ("Instagram",) and not re.search(r"\bInstagram\b", a, re.I):
                continue
            return name
    if re.search(r"\bGmail\b", a, re.I):
        return "Gmail app"
    if re.search(r"\bLine/\d", a, re.I):
        return "Line app"
    if "; wv)" in low:
        return "In-app browser (Android)"
    for tokens, name in ((("samsungbrowser/",), "Samsung Internet"),
                         (("opr/", "opt/", "opera/", "opera ", "opios/"), "Opera"),
                         (("edg/", "edge/", "edga/", "edgios/"), "Edge"),
                         (("yabrowser/",), "Yandex Browser"),
                         (("firefox/", "fxios/"), "Firefox"),
                         (("chrome/", "crios/", "chromium/"), "Chrome")):
        if any(t in low for t in tokens):
            if name == "Opera" and not re.search(r"\bOP(?:R|T|iOS)/|Opera[/ ]", a, re.I):
                continue
            if name == "Edge" and not re.search(r"\bEdg(?:e|A|iOS)?/", a, re.I):
                continue
            return name
    if re.search(r"Version/[\d.]+.*Safari/", a, re.I):
        return "Safari"
    if re.search(r"iPhone|iPad|iPod", a, re.I) and "applewebkit" in low and \
            "safari/" not in low.split("applewebkit", 1)[1]:
        return "In-app browser (iOS)"
    return "Other"


def system_of(agent: str) -> str:
    low = agent.lower()
    for tokens, name in ((("iphone", "ipad", "ipod"), "iOS"), (("android",), "Android"),
                         (("cros",), "ChromeOS"), (("windows",), "Windows"),
                         (("macintosh", "mac os x"), "macOS"), (("linux", "x11"), "Linux")):
        if any(t in low for t in tokens):
            if name == "ChromeOS" and not re.search(r"\bCrOS\b", agent):
                continue
            return name
    return "Other"


def device_of(agent: str) -> str:
    low = agent.lower()
    if any(t in low for t in ("ipad", "tablet", "kindle", "silk/", "playbook")):
        return "Tablet"
    if "android" in low and "mobile" not in low:
        return "Tablet"
    if any(t in low for t in ("mobi", "iphone", "ipod", "android", "windows phone")):
        return "Mobile"
    return "Desktop"


_SEARCH_SITES = ("bing.com", "duckduckgo.com", "yahoo.com", "baidu.com", "ecosia.org",
                 "search.brave.com", "startpage.com", "qwant.com", "naver.com",
                 "seznam.cz", "kagi.com", "yep.com", "aol.com")
_SOCIAL_SITES = ("facebook.com", "fb.com", "instagram.com", "linkedin.com", "lnkd.in",
                 "t.co", "twitter.com", "x.com", "reddit.com", "youtube.com", "youtu.be",
                 "tiktok.com", "threads.net", "ycombinator.com", "quora.com", "t.me",
                 "whatsapp.com", "slack.com", "discord.com", "bsky.app",
                 "mastodon.social")
# Android app ids (android-app://<id>/) that are social: the id itself, or
# the id followed by more of its own (com.whatsapp.w4b).
_SOCIAL_APPS = ("com.google.android.youtube", "com.whatsapp", "org.telegram.messenger")
# Google's web search country domains: google.<cc>, google.com, google.com.<cc>,
# google.co.<cc>. Any other google.* name (com.google.android.<app>) is not.
_GOOGLE_SEARCH = re.compile(r"(?:^|\.)google\.(?:com|com\.[a-z]{2}|co\.[a-z]{2}|[a-z]{2,3})$")
_MAIL_HOSTS = {"mail.google.com", "outlook.live.com", "outlook.office.com",
               "outlook.office365.com", "mail.yahoo.com", "mail.proton.me",
               "com.google.android.gm", "com.microsoft.office.outlook"}


def _under(host: str, sites) -> bool:
    return any(host == s or host.endswith("." + s) for s in sites)


def _bare(referrer: str) -> str:
    host = _host_of(referrer).rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _tags(url: str) -> dict:
    if "?" not in url:
        return {}
    try:
        return {k.lower(): v for k, v in parse_qsl(url.split("?", 1)[1])[:40]}
    except ValueError:
        return {}


def source_of(line: Line, cited: bool, own: set) -> str:
    if cited:
        return "AI assistant"
    host = _bare(line.referrer) if line.referrer else ""
    if host:
        if host in own or "www." + host in own:
            return "This site"
        if host in _MAIL_HOSTS:
            return "Email"
        if _GOOGLE_SEARCH.search(host) or re.search(
                r"(?:^|\.)yandex\.[a-z.]+$", host) or _under(host, _SEARCH_SITES) or \
                host == "com.google.android.googlequicksearchbox":
            return "Search engine"
        if _under(host, _SOCIAL_SITES) or re.search(r"(?:^|\.)pinterest\.[a-z.]+$", host) \
                or re.match(r"com\.(?:linkedin|facebook|instagram|twitter|reddit|slack)", host) \
                or any(host == a or host.startswith(a + ".") for a in _SOCIAL_APPS):
            return "Social media"
        return "Other website"
    tags = _tags(line.url)
    if tags.get("utm_source") or tags.get("utm_medium"):
        # utm_source first; utm_medium only when the source names no kind.
        for key in ("utm_source", "utm_medium"):
            kind = _utm_kind(tags.get(key, ""))
            if kind:
                return kind
        return "Tagged link"
    for key, kind, _ in _CLICKS:
        if tags.get(key):
            return kind
    return "Direct or unknown"


def _utm_kind(value: str) -> str:
    words = set(re.split(r"[^a-z0-9]+", value.lower()))
    if words & {"google", "bing", "duckduckgo", "yahoo", "cpc", "ppc"}:
        return "Search engine"
    if words & {"linkedin", "facebook", "instagram", "twitter", "x", "reddit",
                "youtube", "tiktok", "social"}:
        return "Social media"
    if words & {"email", "newsletter", "mailchimp", "hubspot", "gmail"}:
        return "Email"
    return ""


# Ad click ids with no utm_ tag, in order: (id, source type, campaign).
_CLICKS = (("gclid", "Search engine", "google / cpc / (gclid)"),
           ("gbraid", "Search engine", "google / cpc / (gbraid)"),
           ("wbraid", "Search engine", "google / cpc / (wbraid)"),
           ("msclkid", "Search engine", "bing / cpc / (msclkid)"),
           ("fbclid", "Social media", "facebook / (fbclid) / -"),
           ("li_fat_id", "Social media", "linkedin / (li_fat_id) / -"),
           ("ttclid", "Social media", "tiktok / (ttclid) / -"),
           ("twclid", "Social media", "x / (twclid) / -"))


def referrer_of(line: Line, own: set) -> str:
    host = _bare(line.referrer) if line.referrer else ""
    if not host:
        return "(none)"
    if host in own or "www." + host in own:
        return "(this site)"
    return host[:60]


def campaign_of(url: str) -> str:
    tags = _tags(url)
    parts = [tags.get(k, "") for k in ("utm_source", "utm_medium", "utm_campaign")]
    if any(parts):
        return " / ".join((v or "-").strip().lower()[:30] for v in parts)
    for key, _, said in _CLICKS:
        if tags.get(key):
            return said
    return "(no campaign tag)"


def status_of(status: str) -> str:
    if status == "404":
        return "404"
    return {"2": "2xx", "3": "3xx", "4": "4xx", "5": "5xx"}.get(status[:1], "other")

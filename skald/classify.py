"""Decide who made each request, and in which of five groups it belongs.

The one rule this package is built around: **every hit lands in exactly one
group, and the groups add up to the total.** Not "roughly" - exactly. A report
whose categories do not sum is a report the reader stops trusting, and they are
right to, because a gap means something is being counted twice or not at all.

verify.py enforces that. It is not decoration: the system this was extracted
from shipped a daily email whose three visitor categories summed to 51,763
against a stated total of 55,539, and whose three answer-engine tiers summed to
34,495 against a stated 34,357. Both went out for days. Nobody noticed, because
nothing checked.

The five groups, in the order a reader cares about them:

  PEOPLE          a human with a browser
  ANSWER_ENGINE   an assistant: fetching to train, fetching because someone
                  just asked, or a person who followed its citation
  SEARCH_ENGINE   classic indexing - wanted traffic, so never filed under "bots"
  BOTS            everything else automated, including credential scanners
  OURS            our own crawler and tests, which are not traffic at all

What this cannot do, stated plainly so no report implies otherwise:

  * A user agent is self-reported. Anything here can be forged, so "people" is
    an upper bound on humans, never a count of them.
  * Google AI Overview clicks are indistinguishable from ordinary Google
    clicks: both arrive with a bare google.com referrer and no marker. The
    click side is not visible at all, and neither is the crawl: Google trains
    on what Googlebot fetches, and Google-Extended is a robots.txt token,
    never a user agent.
  * A referrer is often stripped, so citations undercount.
"""
from __future__ import annotations

import ipaddress
import re
from datetime import timedelta
from urllib.parse import urlsplit
from enum import Enum

from .config import ours_entries
from .parse import ASSET, RSC_PAYLOAD, Hit


class Group(str, Enum):
    PEOPLE = "people"
    ANSWER_ENGINE = "answer_engines"
    SEARCH_ENGINE = "search_engines"
    BOTS = "bots"
    OURS = "ours"


class Tier(str, Enum):
    """Why an answer engine fetched something. Three very different things.

    TRAINING is a crawl: nobody is waiting on it.
    ASKED means a person put a question to an assistant seconds ago and it went
    to fetch us to answer them - a reader exists, at the other end.
    CITED means a person saw us in an answer and clicked through. That is the
    tier that turns into customers, and the only one measured from the
    referrer rather than the user agent.
    """

    TRAINING = "training"
    ASKED = "asked"
    CITED = "cited"


# ---------------------------------------------------------------- identities

# Fetching to train or to build an index. Nobody is waiting. The assistants'
# search indexes belong here too: OAI-SearchBot and PerplexityBot crawl ahead
# of any question, like Googlebot. Google-Extended is not here: it is a
# robots.txt token, and no request ever carries it as a user agent.
AI_TRAINING = re.compile(
    r"GPTBot|ClaudeBot|Claude-SearchBot|CCBot|anthropic-ai|OAI-SearchBot"
    r"|PerplexityBot|meta-externalagent|FacebookBot|Bytespider|Amazonbot|Applebot-Extended"
    r"|cohere-ai|Diffbot|omgili|AI2Bot|Timpibot|ImagesiftBot|YouBot"
    r"|PanguBot|Kangaroo Bot|DuckAssistBot",
    re.I,
)

# Fetching right now because a person asked the assistant something.
AI_ASKED = re.compile(
    r"ChatGPT-User|Claude-User|Perplexity-User|meta-externalfetcher"
    r"|Gemini-User|BingPreview|MistralAI-User",
    re.I,
)

# Whose assistant each user fetcher (AI_ASKED) is, by the name its citations
# carry (assistant_name). "Likely sent by an AI assistant" (ai_likely.py, its
# recount audit_ai_likely.py, and the leads and conversions built on it)
# credits a direct visit to the owner of the fetch before it. BingPreview is
# filed as Microsoft's assistant, as AI_ASKED files it. Keys lower case.
AI_FETCHER_OWNERS = {
    "chatgpt-user": "chatgpt.com", "claude-user": "claude.ai",
    "perplexity-user": "perplexity.ai", "gemini-user": "gemini.google.com",
    "bingpreview": "copilot.microsoft.com", "mistralai-user": "mistral.ai",
    "meta-externalfetcher": "meta.ai",
}
# A likely-referred visit whose page two or more assistants fetched in the
# window: counted once, under this name, never under each.
AI_LIKELY_MANY = "(more than one)"

# Skald's own fetchers: always our own traffic, never a bot in the counts,
# whatever the `ours` lists say. robots.py fetches the site's robots.txt
# hourly as "site-version-check/1"; it used to land in bots on every site.
OWN_AGENTS = (("site-version-check/", "Skald (robots.txt check)"),)

# A person who followed a citation. Identified by where they came FROM, since
# their user agent is an ordinary browser's.
#
# Matched against the referrer's HOST: the domain itself or a subdomain of it.
# A substring match counted thank-you.com as you.com, and would have counted
# notperplexity.ai or a ?ref=chatgpt.com query too. Most specific first, so
# chat.openai.com is reported as itself rather than as openai.com.
#
# An assistant's Android app sends its package id as the referrer's host
# (android-app://com.openai.chatgpt/); those ids count as the assistant
# (ASSISTANT_ALIASES names them). Only the assistants' own published app ids.
AI_REFERRER_HOSTS = (
    "chatgpt.com", "chat.openai.com", "openai.com", "perplexity.ai", "claude.ai",
    "gemini.google.com", "copilot.microsoft.com", "you.com", "phind.com",
    "poe.com", "mistral.ai",
    "com.openai.chatgpt", "ai.perplexity.app.android", "com.anthropic.claude",
    "com.google.android.apps.bard", "com.microsoft.copilot",
)
# Bing's assistant shares its host with Bing search; only its path tells.
AI_REFERRER_PATHS = {"bing.com": "/chat"}


# One name per assistant, whichever signal found it: a referrer from its
# current or old host, or a UTM tag. Its main domain is the name, so a filter
# written as "chatgpt.com" or "perplexity.ai" means the assistant, however
# the visitor arrived. Without this one assistant was split into rows called
# "chatgpt", "chatgpt.com" and "chat.openai.com".
ASSISTANT_ALIASES = {
    "chat.openai.com": "chatgpt.com", "openai.com": "chatgpt.com",
    "chatgpt": "chatgpt.com", "openai": "chatgpt.com",
    "perplexity": "perplexity.ai", "claude": "claude.ai",
    "gemini": "gemini.google.com", "copilot": "copilot.microsoft.com",
    "bing.com/chat": "copilot.microsoft.com", "mistral": "mistral.ai",
    # Android apps, by package id.
    "com.openai.chatgpt": "chatgpt.com", "ai.perplexity.app.android": "perplexity.ai",
    "com.anthropic.claude": "claude.ai", "com.google.android.apps.bard": "gemini.google.com",
    "com.microsoft.copilot": "copilot.microsoft.com",
}


def assistant_name(raw: str) -> str:
    """The canonical name for an assistant, from any name it was seen by."""
    name = (raw or "").strip().lower()
    return ASSISTANT_ALIASES.get(name, name)


def cited_by(referrer: str) -> str:
    """The assistant whose citation this referrer is, or "" if none."""
    if not referrer:
        return ""
    parts = urlsplit(referrer if "//" in referrer else "//" + referrer)
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        return ""
    for domain in AI_REFERRER_HOSTS:
        if host == domain or host.endswith("." + domain):
            return assistant_name(domain)
    for domain, prefix in AI_REFERRER_PATHS.items():
        if (host == domain or host.endswith("." + domain)) and \
                parts.path.startswith(prefix):
            return assistant_name(domain + prefix)
    return ""
# Some assistants tag the link instead of sending a referrer.
AI_UTM = re.compile(
    r"utm_source=(chatgpt|openai|perplexity|claude|gemini|copilot|mistral)", re.I
)

# Campaign tag hygiene (utm_hygiene.py, its recount audit_utm.py): the ad
# click ids a landing address may carry (campaigns.CLICK_IDS names their
# networks), and the utm_medium values analytics tools know - the channel
# names in common use. A medium outside this list still counts; it is only
# reported as one no channel grouping will recognise.
CLICK_ID_PARAMS = ("gclid", "gbraid", "wbraid", "msclkid", "fbclid", "li_fat_id",
                   "ttclid", "twclid")
UTM_MEDIUMS = frozenset((
    "cpc", "ppc", "paid", "paidsearch", "paid_search", "paid-search", "paidsocial",
    "paid_social", "paid-social", "retargeting", "display", "banner", "cpm", "cpv", "cpa",
    "interstitial", "native", "email", "e-mail", "e_mail", "newsletter", "social",
    "social-network", "social_network", "social-media", "social_media", "sm", "organic",
    "referral", "affiliate", "affiliates", "partner", "partners", "app", "link", "audio",
    "podcast", "sms", "push", "notification", "mobile", "video", "print", "qr", "offline",
    "influencer"))

# Leads (leads.py, its recount audit_leads.py). "Paid": an ad click id, or a
# medium that says paid. fbclid is not one: Facebook adds it to every link out.
PAID_CLICK_IDS = ("gclid", "msclkid")
PAID_MEDIUMS = ("cpc", "ppc", "paid", "paidsearch", "paid_search", "paid-search",
                "paidsocial", "paid_social", "paid-social", "display", "cpm")
# The funnel's pages by their last path segment, in English, French, German and
# Spanish (config leads.pricing_paths / form_paths override them).
PRICING_PAGES = ("pricing", "tarifs", "preise", "precios")
FORM_PAGES = ("signup", "inscription", "registrieren", "registro",
              "contact", "kontakt", "contacto",
              "join", "adhesion", "beitreten", "alta")

# Google's ad systems checking the landing pages of ads. They belong to the
# search company and are wanted, so they stay in the search group, but they
# are not indexing: reports show them on their own line, "ads quality
# checks", and leave them out of the search-engine indexing figure.
ADS_CHECK = re.compile(r"^(?:AdsBot-Google|Google-Adwords-Instant)", re.I)


def ads_checks(engines) -> int:
    """How many of a search group's fetches, by name, were ads checks."""
    return sum(n for name, n in engines.items() if ADS_CHECK.match(name))


SEARCH_ENGINE = re.compile(
    r"Googlebot|Google-InspectionTool|GoogleOther|APIs-Google|AdsBot-Google"
    r"|Google-Adwords-Instant"
    r"|bingbot|Slurp|DuckDuckBot|Baiduspider|YandexBot|Sogou|Exabot"
    r"|Applebot(?!-Extended)",
    re.I,
)

# Link previews: an app fetching a page because someone pasted its link in a
# chat or a post. Not indexing (facebookexternalhit, Twitterbot and
# LinkedInBot sat in the search group until 2026-10-07) and not a reader, so
# bots - on their own line, because a preview means a person shared the
# link. Most specific first: iMessage sends a Safari agent carrying both
# Facebook's and Twitter's tokens.
LINK_PREVIEWS = (
    (re.compile(r"facebookexternalhit.*Twitterbot|Twitterbot.*facebookexternalhit", re.I),
     "iMessage"),
    (re.compile(r"Slackbot|Slack-ImgProxy", re.I), "Slack"),
    (re.compile(r"SkypeUriPreview|MicrosoftPreview", re.I), "Microsoft Teams"),
    (re.compile(r"WhatsApp", re.I), "WhatsApp"),
    (re.compile(r"LinkedInBot", re.I), "LinkedIn"),
    (re.compile(r"Discordbot", re.I), "Discord"),
    (re.compile(r"TelegramBot", re.I), "Telegram"),
    (re.compile(r"Twitterbot", re.I), "X (Twitter)"),
    (re.compile(r"facebookexternalhit|Facebot", re.I), "Facebook"),
    (re.compile(r"Pinterestbot", re.I), "Pinterest"),
    (re.compile(r"redditbot", re.I), "Reddit"),
    (re.compile(r"Embedly", re.I), "Embedly"),
    (re.compile(r"Iframely", re.I), "Iframely"),
    (re.compile(r"Snap URL Preview", re.I), "Snapchat"),
    (re.compile(r"vkShare", re.I), "VK"),
    (re.compile(r"Bluesky Cardyb|Cardyb/", re.I), "Bluesky"),
    (re.compile(r"Mastodon/", re.I), "Mastodon"),
)
LINK_PREVIEW = "link preview: "


def link_preview(agent: str) -> str:
    """The app a link-preview fetch came from, or ""."""
    for pattern, app in LINK_PREVIEWS:
        if pattern.search(agent):
            return app
    return ""

# Automated, not an engine. Monitors, SEO suites, link unfurlers, libraries.
#
# "bot" counts as a word only when no letter comes before it: CUBOT is a phone
# maker, and "CUBOT X30" in a browser's user agent is a person. Crawler names
# that end in -bot are caught by their version ("FooBot/2.1") or by the
# "+https://..." info link crawlers put in their agent and browsers never do.
OTHER_BOT = re.compile(
    r"(?<![a-z])bot\b|bot/\d|\+https?://"
    r"|crawler|spider|scraper|curl|wget|python-requests|httpx|aiohttp|Go-http"
    r"|java/|okhttp|axios|node-fetch|libwww|Scrapy|HeadlessChrome|PhantomJS"
    r"|AhrefsBot|SemrushBot|MJ12bot|DotBot|BLEXBot|DataForSeoBot|PetalBot"
    r"|UptimeRobot|Pingdom|StatusCake|NewRelic|Site24x7|monitoring|Nagios"
    r"|WhatsApp|TelegramBot|Discordbot|Slackbot|vkShare|Embedly|SkypeUriPreview"
    r"|Let's Encrypt validation"
    # Page-speed testers render pages fully, assets and all.
    r"|Chrome-Lighthouse|PTST/|GTmetrix|Google-PageRenderer"
    # Found in a real log, filed as people.
    r"|ctwatch|jSystem3-metadata-indexer"
    # Googlebot's smartphone template with "Googlebot" taken out: a tool or a
    # spoof copying the crawler, never a person - no phone has run Android 6
    # on a Nexus 5X with this year's Chrome.
    r"|Nexus 5X Build/MMB29P",
    re.I,
)

# Paths only machines ask for on a healthy site: certificate validation. Found in a real log being counted
# as people, because the validators send a Mozilla user agent.
MACHINE_PATH = re.compile(r"^/\.well-known/acme-challenge/")

# Files only a crawler asks for. A browser never fetches robots.txt, a sitemap,
# ads.txt or security.txt on its own; a session (address and user agent) that
# does is a crawler, whatever browser it claims to be, and every request it
# made in that visit is filed under bots (Classifier.crawler_visits). On the
# audited day, 7
# such sessions sending Chrome user agents made 111 of 182 "people" page
# views.
CRAWLER_PATH = re.compile(
    r"^/(?:robots\.txt|ads\.txt|app-ads\.txt|security\.txt"
    r"|\.well-known/security\.txt)$"
    r"|sitemap[^/]*\.(?:xml|txt)(?:\.gz)?$",
    re.I,
)
CRAWLER_SESSION = "browser-like crawler (fetched robots.txt or a sitemap)"
# A browser-like visit that never loaded the page's own scripts and styles
# (rendering.py): a scraper in a browser's clothes. Its requests are bots.
NOT_RENDERED = "browser-like, never rendered the page"


def crawler_visits(hits, gap_minutes: int = 30,
                   hosts: list[str] | None = None,
                   also=None) -> dict[tuple[str, str], list]:
    """The crawler visits in these hits: {(address, agent): [(first, last), ...]}.

    Narrow on purpose, because a wrong call turns a person's reading into
    bots:

      * one visit, not the session all window long: the same address and
        agent, no gap longer than the session gap. A reader who opens
        /robots.txt by hand hours later is a new visit.
      * the site's own hosts only (and lines with no host): robots.txt on
        the API host says nothing about who reads the site.
      * a visit that loaded the site's own scripts, styles or payloads - with
        one of the site's pages as referrer - at least once per page it read
        is a browser rendering pages, and is left alone, whatever else it
        fetched: an SEO extension reading robots.txt, or two people behind
        one office address with the same browser. A crawler does not render.
        The audited day's largest crawler session read 99 pages and loaded
        2 assets, so "at least once per page" and not "at all".
    """
    wanted = {h.lower() for h in (hosts or [])}
    gap = timedelta(minutes=gap_minutes)
    events: dict[tuple[str, str], list] = {}
    marked: set[tuple[str, str]] = set()
    for hit in hits:
        host = hit.host.lower()
        if wanted and host and host not in wanted:
            continue
        if also is not None:
            also(hit)       # another first-pass collector (FanOut)
        key = (hit.address, hit.user_agent)
        crawler_file = bool(CRAWLER_PATH.search(hit.path))
        if crawler_file:
            marked.add(key)
        own_asset = False
        if ASSET.search(hit.path) or RSC_PAYLOAD.search(hit.url):
            ref = (urlsplit(hit.referrer).hostname or "").lower() if hit.referrer else ""
            own_asset = bool(ref) and (ref in wanted if wanted else ref == host or not host)
        events.setdefault(key, []).append((hit.when, crawler_file, own_asset, hit.is_page))

    found: dict[tuple[str, str], list] = {}
    for key in marked:
        visits, current = [], []
        for event in sorted(events[key], key=lambda e: e[0]):
            if current and event[0] - current[-1][0] > gap:
                visits.append(current)
                current = []
            current.append(event)
        visits.append(current)
        for visit in visits:
            if not any(e[1] for e in visit):
                continue
            pages = sum(1 for e in visit if e[3])
            assets = sum(1 for e in visit if e[2])
            if assets and assets >= pages:
                continue            # rendered its pages: a browser
            found.setdefault(key, []).append((visit[0][0], visit[-1][0]))
    return found


# Paths no real site serves. A request for one is somebody trying credentials,
# whatever its user agent claims - so it is never a page view, and the agent is
# not to be believed about anything else either.
#
# Every pattern is anchored to the SHAPE of the thing being hunted - a file
# name, an extension, a directory segment - never a bare word. The first
# version matched "backup" anywhere, and a real site's page with "backup" in
# its name became a scanner, with every person who read it.
# tests/fixtures/site_paths.txt is a made-up sitemap of the same shape (475
# pages, many named with scanners' words); none may match. Tested on the path only: a query string is a
# page's own business (an image URL inside one mentioned "backup" too).
_SEG = r"(?:^|/)"          # starts a path segment
_END = r"(?:[/.]|$)"       # ends one: a slash, an extension, or the end
PROBE = re.compile(
    # Dotfiles and version control: no site serves these on purpose.
    _SEG + r"\.(?:env|git|svn|hg|bzr|aws|ssh|docker|vscode|idea|npmrc|htpasswd"
    r"|htaccess|bash_history|ds_store|config)(?:[._/-]|$)"
    # Server-side scripts that a static or Node site never runs.
    r"|\.(?:php\d?|phtml|asp|aspx|jsp|jspa|cgi|pl|cfm)(?:/|$)"
    # WordPress and its kin.
    r"|" + _SEG + r"(?:wp-admin|wp-login|wp-content|wp-includes|wp-json|wp-config"
    r"|xmlrpc|wordpress|wp)" + _END +
    # Dumps and backups, shaped like files.
    r"|" + _SEG + r"(?:backups?|bak|db|database|dump|site|www|web|html|public_html"
    r"|wwwroot|data|old|test)\.(?:zip|tar|tar\.gz|tgz|gz|rar|7z|sql|bak)$"
    r"|\.(?:sql|sql\.gz|sqlite3?|bak|swp)$|" + _SEG + r"backups?/?$"
    # Keys and credentials, shaped like files.
    r"|" + _SEG + r"id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?$|\.(?:pem|key|p12|pfx|tfstate)$"
    r"|" + _SEG + r"(?:credentials?|secrets?|service-account[^/]*|firebase[^/]*|config"
    r"|settings|appsettings|parameters|key)\.(?:json|ya?ml|xml|ini|env|txt)$"
    r"|" + _SEG + r"docker-compose[^/]*\.ya?ml$|" + _SEG + r"env\.js$"
    # Admin panels, app-server consoles and framework debug routes (several
    # are remote-code-execution endpoints that send a Chrome user agent).
    r"|" + _SEG + r"(?:admin|administrator|phpmyadmin|pma|myadmin|adminer|cpanel"
    r"|cgi-bin|boaform|hudson|jenkins|solr|struts|actuator|telescope|_ignition"
    r"|_debugbar|_profiler|laravel|druid|geoserver|HNAP1|owa|autodiscover"
    r"|vendor/phpunit|containers/json|api/config|sdk)" + _END +
    r"|phpinfo|eval-stdin|invokefunction|" + _SEG + r"\.well-known/ALFA",
    re.I,
)

# Attack strings that arrive in the query string instead of the path.
PROBE_QUERY = re.compile(
    r"\.\./|%2e%2e|/etc/passwd|\$\{jndi:|<script|union(?:\s|%20|\+)+select"
    r"|XDEBUG_SESSION|allow_url_include|auto_prepend_file",
    re.I,
)

# "Mozilla/5.0 (compatible; Name)" is how crawlers write a browser-shaped
# agent. A real browser that says "compatible;" - Internet Explorer - names
# its engine as well. So "compatible;" with no engine in the agent is a bot,
# even with no version and no info link to give it away.
COMPATIBLE = re.compile(r"\(compatible;", re.I)
ENGINE = re.compile(r"AppleWebKit|Gecko|Trident|Presto|Chrome/|Safari/|Firefox/", re.I)

# Looks like a browser. Checked last, and only as a fallback.
BROWSER = re.compile(r"Mozilla/|Opera/|Safari/|Chrome/|Firefox/", re.I)


def _aware(when):
    from datetime import timezone
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


class Verdict:
    """What a hit is, and why. The reason is kept so a report can show it."""

    __slots__ = ("group", "tier", "engine", "probe", "verified", "claim", "flags", "legacy")

    def __init__(
        self,
        group: Group,
        tier: Tier | None = None,
        engine: str = "",
        probe: bool = False,
        verified: str | None = None,
        claim: str = "",
        flags: tuple = (),
        legacy: bool = False,
    ) -> None:
        self.group = group
        self.tier = tier
        self.engine = engine
        self.probe = probe
        # A named crawler's claim checked (bot_verify): "verified",
        # "unverified", "spoofed"; None for everyone else. `claim` is the
        # name a spoofed request gave.
        self.verified = verified
        self.claim = claim
        # Warning signs on a browser counted as people (FAKE_BROWSER_FLAGS).
        self.flags = flags
        # A path of the site's old version, kept out of the probes.
        self.legacy = legacy


class Classifier:
    """Applies the rules. Built once from config, then called per hit.

    Order matters and is deliberate:

      1. ours      - never traffic, and would otherwise look like a bot
      2. engines   - named agents, the most specific signal there is
      3. search    - also named, and wanted
      4. probe     - a scanner, whatever it claims to be
      5. bots      - automated by any other sign
      6. people    - a browser, and nothing above matched

    Putting `probe` above `people` is what stops a scanner that sends a Chrome
    user agent from being counted as a reader. Putting it BELOW the engines is
    deliberate too: an engine that happens to request a silly path is still
    that engine, and filing it under scanners would quietly remove it from the
    engine totals - which is how a tier sum ends up 82 higher than its own
    group total.
    """

    def __init__(self, our_agents: list | None = None,
                 our_referrers: list | None = None,
                 our_addresses: list | None = None,
                 file_addresses: list[dict] | None = None) -> None:
        # Each list holds plain strings or labelled entries (config.ours_entries).
        # The label is what an OURS verdict carries as its engine, so the
        # dashboard can say which rule a request matched without ever
        # showing the address behind it.
        self.ours_agents = [(v.lower(), l) for v, l in ours_entries(our_agents, "user_agents")]
        self.ours_agents += [(v.lower(), l) for v, l in OWN_AGENTS]
        self.ours_referrers = [(v.lower(), l) for v, l in ours_entries(our_referrers, "referrers")]
        self.ours_agent = self._any_of([v for v, _ in self.ours_agents])
        self.ours_referrer = self._any_of([v for v, _ in self.ours_referrers])
        # Addresses or CIDR ranges you browse from (an office, your own laptop): your own visits
        # look exactly like a reader's, and are not traffic.
        # (network, label, since): config entries apply always; an entry added
        # on the page (ours_store) only from the moment it was added.
        self.ours_networks = [(ipaddress.ip_network(v, strict=False), l, None)
                              for v, l in ours_entries(our_addresses, "addresses")]
        from .ours_store import since
        self.ours_networks += [(ipaddress.ip_network(e["ip"], strict=False), e["label"], since(e))
                               for e in file_addresses or []]
        self._agents: dict[str, tuple] = {}
        # Crawler visits found by a first pass (crawler_visits). Set by the
        # caller that can read the window twice; empty: the rule is off.
        self.crawler_visits: dict[tuple[str, str], list] = {}
        # Release 2. Paths of the site's old version (site.legacy_paths):
        # a request under one is not a scanner probe, whatever PROBE says.
        self.legacy: tuple[str, ...] = ()
        # Checks crawler claims and hosting networks (bot_verify.Verifier);
        # None: nothing is checked, every claim stands.
        self.verifier = None
        # (address, agent) pairs in a fan-out burst (fan_out), from the
        # first pass like crawler_visits.
        self.fan_out: set[tuple[str, str]] = set()
        # Browser-like visits that never rendered a page (rendering.py), from
        # the same first pass: {(address, agent): [(first, last), ...]}.
        # Empty: the rule is off.
        self.unrendered: dict[tuple[str, str], list] = {}

    # A user agent repeats across thousands of hits, and the case-insensitive
    # alternations below were nine-tenths of the time spent per hit. What
    # they say about an agent never changes, so it is worked out once per
    # distinct agent. The rules and their order are untouched: __call__ asks
    # the same questions in the same order, it just remembers the answers.
    AGENT_CACHE_LIMIT = 50_000

    def _agent(self, agent: str) -> tuple:
        """(ours label or "", asked, training, search, other_bot, browser)."""
        facts = self._agents.get(agent)
        if facts is None:
            if len(self._agents) >= self.AGENT_CACHE_LIMIT:
                self._agents.clear()   # a log of random agents: stay bounded
            asked = AI_ASKED.search(agent)
            training = AI_TRAINING.search(agent)
            search = SEARCH_ENGINE.search(agent)
            facts = (
                self._agent_label(agent) if self.ours_agent and self.ours_agent.search(agent)
                else "",
                asked.group(0) if asked else None,
                training.group(0) if training else None,
                search.group(0) if search else None,
                bool(OTHER_BOT.search(agent))
                or bool(COMPATIBLE.search(agent) and not ENGINE.search(agent)),
                bool(BROWSER.search(agent)),
            )
            self._agents[agent] = facts
        return facts

    @classmethod
    def from_config(cls, config: dict) -> "Classifier":
        """The one way to build a classifier from config.yml.

        Every entry point - report.py in either mode, skald, the library's
        analyse() - goes through here, so a rule added to `ours` cannot be
        honoured by one and silently ignored by another. That happened:
        report.py's --days mode dropped ours.addresses, and counted the
        owner's own visits, including a citation click, as readers.
        """
        from .ours_store import load, path_of
        from .bot_verify import from_config
        ours = (config or {}).get("ours") or {}
        made = cls(ours.get("user_agents") or None, ours.get("referrers") or None,
                   ours.get("addresses") or None, load(path_of(config)))
        made.legacy = legacy_paths(config)
        made.verifier = from_config(config)
        return made

    def _agent_label(self, agent: str) -> str:
        low = agent.lower()
        return next((l for v, l in self.ours_agents if v in low), "ours")

    def _ours_address(self, address: str, when=None) -> str:
        """The label of the first listed range holding this address (and, for
        one added on the page, added before this request), or ""."""
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return ""
        for net, label, start in self.ours_networks:
            if ip in net and (start is None or when is None or _aware(when) >= start):
                return label
        return ""

    def _in_crawler_visit(self, hit: Hit) -> bool:
        spans = self.crawler_visits.get((hit.address, hit.user_agent))
        return bool(spans) and any(first <= hit.when <= last for first, last in spans)

    def _never_rendered(self, hit: Hit) -> bool:
        spans = self.unrendered.get((hit.address, hit.user_agent))
        if not spans:
            return False
        when = _aware(hit.when)
        return any(first <= when <= last for first, last in spans)

    @staticmethod
    def _any_of(patterns: list[str] | None) -> re.Pattern | None:
        cleaned = [re.escape(p) for p in (patterns or []) if p]
        return re.compile("|".join(cleaned), re.I) if cleaned else None

    def _checked(self, name: str, hit: Hit) -> str | None:
        return self.verifier.status(name, hit.address, hit.user_agent) \
            if self.verifier is not None else None

    def __call__(self, hit: Hit) -> Verdict:
        agent, referrer = hit.user_agent, hit.referrer
        probing = bool(PROBE.search(hit.path) or PROBE_QUERY.search(hit.url))
        legacy = False
        if probing and self.legacy and any(hit.path.startswith(p) for p in self.legacy):
            probing, legacy = False, True
        ours, asked, training, search, other_bot, browser = self._agent(agent)

        # An OURS verdict carries the matching rule's label as its engine.
        if ours:
            return Verdict(Group.OURS, engine=ours, probe=probing)
        if self.ours_referrer and referrer and self.ours_referrer.search(referrer):
            low = referrer.lower()
            label = next((l for v, l in self.ours_referrers if v in low), "ours")
            return Verdict(Group.OURS, engine=label, probe=probing)
        if self.ours_networks:
            label = self._ours_address(hit.address, hit.when)
            if label:
                return Verdict(Group.OURS, engine=label, probe=probing)

        # A named crawler is checked against its owner's addresses
        # (bot_verify). One that is proven not to be what it says is a bot
        # that lied: never counted in the engine's figures.
        named = asked or training
        if named:
            checked = self._checked(named, hit)
            if checked == "spoofed":
                return Verdict(Group.BOTS, engine=f"claims to be {named}", probe=probing,
                               verified=checked, claim=named, legacy=legacy)
            tier = Tier.ASKED if asked else Tier.TRAINING
            return Verdict(Group.ANSWER_ENGINE, tier, named, probing, checked, legacy=legacy)

        preview = link_preview(agent)
        if preview:
            return Verdict(Group.BOTS, engine=LINK_PREVIEW + preview, probe=probing,
                           legacy=legacy)

        if search:
            checked = self._checked(search, hit)
            if checked == "spoofed":
                return Verdict(Group.BOTS, engine=f"claims to be {search}", probe=probing,
                               verified=checked, claim=search, legacy=legacy)
            return Verdict(Group.SEARCH_ENGINE, engine=search, probe=probing,
                           verified=checked, legacy=legacy)

        if probing:
            return Verdict(Group.BOTS, probe=True)

        if other_bot or not agent or MACHINE_PATH.search(hit.path):
            return Verdict(Group.BOTS, legacy=legacy)

        if browser and self._in_crawler_visit(hit):
            # A browser user agent that fetched robots.txt or a sitemap in the
            # same session: a crawler in a browser's clothes. All of its
            # requests are bots, so the groups still partition the log.
            return Verdict(Group.BOTS, engine=CRAWLER_SESSION, legacy=legacy)

        if browser and self._never_rendered(hit):
            # Took the page and never drew it: no script, no style, no
            # beacon, and not a browser we saw render before. A scraper.
            return Verdict(Group.BOTS, engine=NOT_RENDERED, legacy=legacy)

        if browser:
            # A browser that arrived from an assistant is a person who followed
            # a citation. They stay in PEOPLE - they ARE a person - and the
            # citation is recorded as a property of that visit. Adding them to
            # the answer-engine group as well is double counting, and is
            # exactly how the old report's tiers over-summed.
            source = cited_by(referrer)
            if not source:
                tagged = AI_UTM.search(hit.url)
                source = assistant_name(tagged.group(1)) if tagged else ""
            flags = self._flags(hit)
            if source:
                return Verdict(Group.PEOPLE, Tier.CITED, source, flags=flags, legacy=legacy)
            return Verdict(Group.PEOPLE, flags=flags, legacy=legacy)

        return Verdict(Group.BOTS, legacy=legacy)

    def _flags(self, hit: Hit) -> tuple:
        """Fake-browser warning signs on a request counted as people."""
        flags = []
        if self.verifier is not None and self.verifier.hosting(hit.address):
            flags.append("hosting_network")
        if (hit.address, hit.user_agent) in self.fan_out:
            flags.append("fan_out")
        if BARE_MOZILLA.match(hit.user_agent):
            flags.append("bare_mozilla")
        return tuple(flags)


# A browser agent with nothing after the product token: no browser sends it.
BARE_MOZILLA = re.compile(r"^\s*Mozilla/5\.0\s*$")
FAKE_BROWSER_FLAGS = ("hosting_network", "fan_out", "bare_mozilla")

# Fan-out: one browser agent from this many addresses within this many
# seconds. A flag only (EDGE A16): a link shared in a busy chat can look
# the same.
FAN_OUT_ADDRESSES = 10
FAN_OUT_SECONDS = 10


class FanOut:
    """Collects (when, address) per browser agent in a first pass, then
    says which (address, agent) pairs were part of a burst."""

    def __init__(self) -> None:
        self.seen: dict[str, list] = {}

    def __call__(self, hit: Hit) -> None:
        agent = hit.user_agent
        if agent and BROWSER.search(agent) and not OTHER_BOT.search(agent):
            self.seen.setdefault(agent, []).append((hit.when, hit.address))

    def pairs(self) -> set[tuple[str, str]]:
        out: set[tuple[str, str]] = set()
        span = timedelta(seconds=FAN_OUT_SECONDS)
        for agent, events in self.seen.items():
            if len({a for _, a in events}) < FAN_OUT_ADDRESSES:
                continue
            events.sort(key=lambda e: e[0])
            start, inside = 0, {}
            for end, (when, address) in enumerate(events):
                inside[address] = inside.get(address, 0) + 1
                while when - events[start][0] > span:
                    old = events[start][1]
                    inside[old] -= 1
                    if not inside[old]:
                        del inside[old]
                    start += 1
                if len(inside) >= FAN_OUT_ADDRESSES:
                    out.update((a, agent) for a in inside)
        return out


def legacy_paths(config: dict) -> tuple[str, ...]:
    """`site.legacy_paths`: path prefixes of the site's old version."""
    raw = ((config or {}).get("site") or {}).get("legacy_paths") or []
    if isinstance(raw, str):
        raw = raw.split()
    return tuple(str(p) for p in raw if str(p).startswith("/"))

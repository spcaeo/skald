"""Machine and utility addresses that are not pages (2.35, owner: "not really
traffic in any sense").

parse.ASSET and parse.BEACON already keep files and a page's own calls out of
the page views. This is the next list: addresses a person never reads,
shaped like a page (a 200 for a GET of a path with no file extension). A
survey of the eight live sites (2026-10-25) found them counted as people's
page views: WordPress's REST API asked by query (?rest_route=), feeds by
query (?feed=), user-number lookups (?author=2), and Markdown copies of
pages that AI agents fetch (/docs/index.md).

A request on the list is not a page view. Nothing else about it changes: it
stays in the log's request counts, in the same group (people, bots, ...),
so the five groups still add up to the log. Only page views, readers,
landings, exits and journey steps leave it out, the way they leave out a
stylesheet.

Every site gets DEFAULT. A site can count any entry as pages again
(site.not_pages_off, Settings > Data > What counts) and add its own
addresses (site.not_pages_extra). Things a person does open stay pages:
search results, a cart, a sign-in page, an app's dashboard, a thank-you
page. A site that wants one of them out adds it as its own address.

2.36 added the HTML sitemap page (owner: "a user never looks at
/sitemap/"). On one site in a day, its visits were Googlebot, PetalBot,
Amazonbot, Ahrefs' site audit, a "research-check" tool and four browser
signatures with no referrer: the last were counted as people and put
/sitemap/ in the people's pages.

The lists below are data. The audit (audit_not_pages.py) shares them and
nothing else: it matches them by its own code. Matching, on both roads:

  ends      the path, without trailing slashes, ends with this (any case)
  tails     the path's last segments are these (any case)
  segments  one of the path's segments is this (any case)
  keys      the query string has this key, with or without a value (any case)
  numbers   the query string has this key with a value of digits 0-9 only

Upper and lower case are the ASCII letters only, on both roads. The query
is everything after the first "?" up to a "#"; its keys are the text before
"=" in each "&"-separated part, as written (not decoded).

A site's own entries (site.not_pages_extra), each one of:

  /path      that path exactly, any case, trailing slashes ignored
  /prefix*   every path that starts with /prefix, any case
  ?key       every address whose query string has that key
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import form_names

# name -> (reason, shapes). The order is the order a match is reported in.
RULES: dict[str, tuple[str, dict]] = {
    "markdown": (
        "A Markdown copy of a page (.md), fetched by AI agents and tools; "
        "people read the page itself.",
        {"ends": (".md", ".mdx", ".markdown")}),
    "wp_rest": (
        "WordPress's REST API (/wp-json/, ?rest_route=): data for scripts and "
        "apps, not a page.",
        {"segments": ("wp-json",), "keys": ("rest_route",)}),
    "wp_files": (
        "WordPress's machine files: remote posting (xmlrpc.php), its scheduler "
        "(wp-cron.php) and script calls (admin-ajax.php).",
        {"tails": (("xmlrpc.php",), ("wp-cron.php",), ("admin-ajax.php",))}),
    "feeds": (
        "A feed for feed readers (/feed/, /comments/feed/, /feed/atom/, ?feed=), "
        "not a page.",
        {"tails": (("feed",), ("feed", "rss"), ("feed", "rss2"), ("feed", "atom"),
                   ("feed", "rdf")),
         "keys": ("feed",)}),
    "oembed": (
        "oEmbed (/oembed/): what another site asks for to embed a link.",
        {"segments": ("oembed",)}),
    "trackback": (
        "Trackbacks (/trackback/, wp-trackback.php): notices one blog's software "
        "sends another.",
        {"tails": (("trackback",), ("wp-trackback.php",))}),
    "author_number": (
        "?author=2: a lookup that lists a WordPress site's user names; people "
        "follow /author/name/ links.",
        {"numbers": ("author",)}),
    "reply_to_comment": (
        "?replytocom=: WordPress's reply link for browsers without scripts, "
        "followed by crawlers; the same post without it is the page.",
        {"keys": ("replytocom",)}),
    "sitemap_page": (
        "An HTML sitemap page (/sitemap/, /site-map/, /sitemap.html): crawlers, "
        "link checkers and test browsers walk it; people use the menu and search.",
        {"tails": (("sitemap",), ("site-map",), ("html-sitemap",), ("sitemap.html",),
                   ("sitemap.htm",))}),
}
DEFAULT: tuple[str, ...] = tuple(RULES)

# A site's own entries (site.not_pages_extra).
MAX_EXTRA = 20
EXTRA_LIMIT = 100
OWN = "own"             # the rule name an own entry is reported under: "own: /docs/*"
_KEY = re.compile(r"^[A-Za-z0-9_.\-\[\]]{1,60}$")


def reason(name: str) -> str:
    return RULES[name][0] if name in RULES else "This site's own entry (Settings > Data > What counts)."


def clean_off(value) -> list[str]:
    """site.not_pages_off: names from DEFAULT, each once, in DEFAULT's order.
    ValueError in plain words otherwise."""
    items = value.replace(",", " ").split() if isinstance(value, str) else value
    if not isinstance(items, (list, tuple)):
        raise ValueError("A list of entry names from the not-a-page list.")
    out = []
    for item in items:
        name = item.strip() if isinstance(item, str) else ""
        if name not in RULES:
            raise ValueError(f"Not an entry of the not-a-page list: {str(item)[:40]!r}. "
                             f"The entries: {', '.join(DEFAULT)}.")
        if name not in out:
            out.append(name)
    return [n for n in DEFAULT if n in out]


def clean_extra(value) -> list[str]:
    """site.not_pages_extra: at most MAX_EXTRA entries, each /path, /prefix*
    or ?key (module doc), each once. ValueError in plain words otherwise."""
    items = value.replace(",", " ").split() if isinstance(value, str) else value
    if not isinstance(items, (list, tuple)):
        raise ValueError("A list of addresses: /path, /prefix* or ?key.")
    out = []
    for item in items:
        raw = item.strip() if isinstance(item, str) else ""
        if (not raw or len(raw) > EXTRA_LIMIT or ".." in raw or "#" in raw
                or any(ord(c) <= 0x20 or ord(c) >= 0x7f for c in raw)):
            raise ValueError(f"An entry is /path, /prefix* or ?key, with no spaces: "
                             f"{str(item)[:40]!r}.")
        if raw.startswith("?"):
            if not _KEY.match(raw[1:]):
                raise ValueError(f"A query key is letters, digits and _ . - only: {raw[:40]!r}.")
        elif raw.startswith("/"):
            body = raw[:-1] if raw.endswith("*") else raw
            if "*" in body or "?" in body:
                raise ValueError(f"A * may only end a path, and a path has no ?: {raw[:40]!r}.")
            if body.strip("/") == "":
                raise ValueError("/ alone would take every page out of the counts.")
        else:
            raise ValueError(f"An entry starts with / (a path) or ? (a query key): {raw[:40]!r}.")
        if raw not in out:
            out.append(raw)
    if len(out) > MAX_EXTRA:
        raise ValueError(f"At most {MAX_EXTRA} entries of your own.")
    return out


def _alt(words) -> str:
    return "|".join(re.escape(w) for w in words)


@dataclass(frozen=True)
class Rules:
    """One site's list, compiled: match(path, url) is the name of the first
    entry that matches, or "". Shared by every hit read for the site. It
    carries the site's POST paths that are no form too (`posts`, its
    site.script_posts; form_names.py), so every road that reads a site's
    not-a-page list reads that one with it."""

    names: tuple[str, ...]
    extra: tuple[str, ...]
    script_posts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        flags = re.I | re.A
        object.__setattr__(self, "posts", form_names.paths(self.script_posts))
        each, paths, queries = [], [], []
        for name in self.names:
            shapes = RULES[name][1]
            p = []
            if shapes.get("ends"):
                p.append(f"(?:{_alt(shapes['ends'])})/*$")
            for tail in shapes.get("tails", ()):
                p.append("(?:^|/)" + "/+".join(re.escape(s) for s in tail) + "/*$")
            if shapes.get("segments"):
                p.append(f"(?:^|/)(?:{_alt(shapes['segments'])})(?:/|$)")
            q = []
            if shapes.get("keys"):
                q.append(f"(?:^|&)(?:{_alt(shapes['keys'])})(?:[=&]|$)")
            if shapes.get("numbers"):
                q.append(f"(?:^|&)(?:{_alt(shapes['numbers'])})=[0-9]+(?:&|$)")
            paths += p
            queries += q
            each.append((name, re.compile("|".join(p), flags) if p else None,
                         re.compile("|".join(q), flags) if q else None))
        for entry in self.extra:
            if entry.startswith("?"):
                q = f"(?:^|&){re.escape(entry[1:])}(?:[=&]|$)"
                queries.append(q)
                each.append((f"{OWN}: {entry}", None, re.compile(q, flags)))
            else:
                p = ("^" + re.escape(entry[:-1]) if entry.endswith("*")
                     else "^" + re.escape(entry.rstrip("/")) + "/*$")
                paths.append(p)
                each.append((f"{OWN}: {entry}", re.compile(p, flags), None))
        # One search each for the path and the query decides "none" (nearly
        # every request); only a match looks for which entry, in list order.
        object.__setattr__(self, "_each", tuple(each))
        object.__setattr__(self, "_paths", re.compile("|".join(paths), flags) if paths else None)
        object.__setattr__(self, "_queries", re.compile("|".join(queries), flags)
                           if queries else None)

    def match(self, path: str, url: str) -> str:
        """The first entry, in list order (DEFAULT's, then the site's own),
        that `path` (no query) or `url`'s query matches: an entry name,
        "own: <entry>", or ""."""
        query = url.partition("?")[2].partition("#")[0] if "?" in url else ""
        if not ((self._paths is not None and self._paths.search(path))
                or (query and self._queries is not None and self._queries.search(query))):
            return ""
        for name, on_path, on_query in self._each:
            if (on_path is not None and on_path.search(path)) or \
                    (query and on_query is not None and on_query.search(query)):
                return name
        return ""


_MADE: dict[tuple, Rules] = {}


def rules(off=(), extra=(), posts=()) -> Rules:
    """The compiled list for these settings, made once per distinct value."""
    names = tuple(n for n in DEFAULT if n not in set(off or ()))
    key = (names, tuple(extra or ()), tuple(posts or ()))
    got = _MADE.get(key)
    if got is None:
        got = _MADE[key] = Rules(*key)
    return got


STANDARD = rules()


def from_config(config: dict | None) -> Rules:
    """The site's list from config["site"] (not_pages_off, not_pages_extra,
    and script_posts, form_names.py; settings_store.apply writes the
    Settings rows there). An unreadable value counts as unset: the default
    applies, never a guess."""
    site = (config or {}).get("site") or {}
    try:
        off = clean_off(site.get("not_pages_off") or [])
    except ValueError:
        off = []
    try:
        extra = clean_extra(site.get("not_pages_extra") or [])
    except ValueError:
        extra = []
    return rules(off, extra, form_names.from_config(config))

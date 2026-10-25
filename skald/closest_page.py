"""The closest live page for an old address (Site > Not found, lost pages, 2.35).

An old page that now answers 404 or 410 is often the same page at a new address:
moved to another section, renamed, written with a slip (a capital, a missing
slash, a WordPress copy suffix), or a broken link to a live page. `closest()`
looks for it among the live pages and says how close it is, in one word:

  exact    the same page: the same path but for case or the trailing slash, a
           malformed link whose clean part is live (a pasted Markdown link, a
           session id, a stray bracket), a copy suffix (-2) or index.html left
           over, the home page by another name (/home/), or the same last segment
           (slug, three words or more) under one other section only
  likely   most of the address's words (Dice's coefficient over 0.6, over the
           words of every segment) are one live page's, two at least, and that
           page's slug shares one of them: the same topic, renamed; or a later
           page of a live list (/blog/page/3/)
  guess    a live page of the same section: the nearest live parent, never the
           home page alone (one word in common with some page is not enough)
  None     nothing close: "410 gone" is the honest answer

The live pages are what the caller gives: the sitemap's paths and the pages
served with a 2xx or 304 in the window (lost_pages.py). Nothing here names a
site; it reads paths only. Standard library only, no network.

`rules()` writes the server lines for the choice, as text to copy: nginx
`location = /old/ { return 301 /new/; }` (or `return 410;`), Apache
`Redirect 301 /old/ /new/` (or `Redirect gone /old/`). Skald never changes a
web server itself. A path with characters a rule would need escaped gets no
line (None): it is written by hand.
"""
from __future__ import annotations

import re
from urllib.parse import unquote

EXACT, LIKELY, GUESS = "exact", "likely", "guess"
WORDS = {EXACT: "Same page", LIKELY: "Same topic", GUESS: "Loose", None: "No good match"}

# Where a malformed link's clean part ends: a pasted Markdown link "](https:...",
# an encoded bracket or quote, a session id or a tracking tail glued onto the path.
_BROKEN = re.compile(r"(\]\(|%5[bBdD]|\[|\]|%22|%27|\"|'|&|%26|%20|\s|\)|%29|\\|%5[cC]|tel:)")
_COPY = re.compile(r"-\d{1,2}$")                 # a WordPress copy: /page-2/
_PAGED = re.compile(r"/page/\d+/?$")             # /blog/page/3/
_INDEX = re.compile(r"/(?:index|default)\.(?:html?|php)$", re.I)
_HTML = re.compile(r"\.html?$", re.I)
_SPLIT = re.compile(r"[^a-z0-9]+")
STOP = frozenset("a an and are as at be by can do for from how in into is it its of on or "
                 "our the their this to vs what when where which who why with you your "
                 "page html htm www amp".split())
MOVED_WORDS = 3
LIKELY_DICE = 0.62               # more than 0.6: three words of five on each side is not enough
HOME = frozenset(("home", "index", "index.html", "index.php", "default.aspx", "start"))
_SAFE = re.compile(r"^/[A-Za-z0-9._~/-]*$")      # a path a server rule takes as it is


def _slash(path: str) -> list[str]:
    """The path, and the same with or without its trailing slash."""
    if path == "/":
        return ["/"]
    return [path, path.rstrip("/")] if path.endswith("/") else [path, path + "/"]


def _stem(w: str) -> str:
    """A plural made singular, roughly: wearables -> wearable (not "access" or "news")."""
    return w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith(("ss", "us", "is")) else w


def words(text: str) -> list[str]:
    """The meaningful words of a slug or a section: lower case, no numbers, no stop words."""
    return [_stem(w) for w in _SPLIT.split(unquote(text).lower()) if len(w) > 1 and not w.isdigit()
            and w not in STOP]


def _parts(path: str) -> tuple[str, str]:
    """(the parent section, the slug): "/blog/a-b/" -> ("/blog/", "a-b")."""
    trimmed = path.rstrip("/")
    head, _, slug = trimmed.rpartition("/")
    return (head + "/" if head else "/"), slug


class Live:
    """The live pages, indexed for the look-up: by exact path, by lower-cased path, by
    slug, and by slug word."""

    def __init__(self, paths) -> None:
        self.paths = frozenset(p for p in paths if isinstance(p, str) and p.startswith("/"))
        self.lower: dict[str, str] = {}
        self.slugs: dict[str, list[str]] = {}
        self.by_word: dict[str, set[str]] = {}
        for p in sorted(self.paths):
            self.lower.setdefault(p.lower(), p)
            self.lower.setdefault(p.lower().rstrip("/") or "/", p)
            _, slug = _parts(p)
            if slug:
                self.slugs.setdefault(slug.lower(), []).append(p)
                for w in set(words(slug)):
                    self.by_word.setdefault(w, set()).add(p)
        self.all_words = {p: frozenset(words(p)) for p in self.paths}

    def __contains__(self, path: str) -> bool:
        return path in self.paths

    def __len__(self) -> int:
        return len(self.paths)

    def find(self, path: str) -> str | None:
        """The live page this path is, but for case and the trailing slash."""
        for p in _slash(path):
            if p in self.paths:
                return p
        low = path.lower()
        return self.lower.get(low) or self.lower.get(low.rstrip("/") or "/")


def _clean(path: str) -> str:
    """A malformed link's clean part: cut at the first broken character, the query gone."""
    cut = _BROKEN.split(path.split("?", 1)[0], maxsplit=1)[0]
    return cut or "/"


def _same_page(path: str, live: Live) -> tuple[str, str] | None:
    """(target, why) when the path is a live page written another way."""
    got = live.find(path)
    if got and got != path:
        return got, "the same address but for a capital letter or the trailing slash"
    clean = _clean(path)
    if clean != path.split("?", 1)[0]:
        got = live.find(clean)
        if got:
            return got, "a malformed link to a live page"
    for pattern, why in ((_INDEX, "an index file of a live page"), (_HTML, "the .html copy of a live page")):
        if pattern.search(clean):
            got = live.find(pattern.sub("/", clean))
            if got:
                return got, why
    head, slug = _parts(clean)
    if head == "/" and slug.lower() in HOME and "/" in live:
        return "/", "the home page under another name"
    if _COPY.search(slug):
        got = live.find(head + _COPY.sub("", slug) + "/")
        if got:
            return got, "a copy (-2) of a live page"
    # The same slug under one other section: the same page moved, when the slug says enough
    # to be one page's own (three words or more; "/types/" or "/cost/" could be any page's).
    if slug and len(words(slug)) >= MOVED_WORDS:
        moved = [p for p in live.slugs.get(slug.lower(), []) if p.rstrip("/") != clean.rstrip("/")]
        if len(moved) == 1:
            return moved[0], "the same page, moved to another section"
    return None


def _score(old: frozenset, cand: frozenset) -> tuple[int, float]:
    """(words shared, Dice's coefficient) over the whole paths' words: the section's words
    count too, so /ehr/cost/ is closer to /ehr/ehr-cost/ than to /app/cost/."""
    shared = len(old & cand)
    return shared, (2 * shared / (len(old) + len(cand)) if shared else 0.0)


def closest(path: str, live: Live) -> tuple[str | None, str | None, str]:
    """(target, confidence, why) for an old path: confidence EXACT, LIKELY, GUESS or None."""
    if not path or not path.startswith("/"):
        return None, None, "not a site path"
    if path in live:
        return path, EXACT, "this address is live"
    same = _same_page(path, live)
    if same:
        return same[0], EXACT, same[1]
    clean = _clean(path)
    if _PAGED.search(clean):
        clean = _PAGED.sub("/", clean)
        got = live.find(clean)
        if got:
            return got, LIKELY, "a later page of a live list"
    head, slug = _parts(clean)
    old_slug, old_all = words(slug), frozenset(words(clean))
    if old_slug:
        # Only pages whose slug shares a word with this slug are weighed.
        seen: set[str] = set()
        for w in set(old_slug):
            seen |= live.by_word.get(w, set())
        best = None
        for cand in sorted(seen):
            n, score = _score(old_all, live.all_words[cand])
            if best is None or (score, n) > (best[0], best[1]):
                best = (score, n, cand)
        # Most of both addresses' words shared: two at least, or every word of the shorter.
        if best and best[0] >= LIKELY_DICE and (
                best[1] >= 2 or best[1] == min(len(old_all), len(live.all_words[best[2]]))):
            return best[2], LIKELY, f"{best[1]} words in common with this page's address"
    # The nearest live section above it (never the home page alone: too loose). One word in
    # common with some page is not enough for a guess: "/ai-for-retail/" is no AI page's.
    section = _parent(clean, live)
    if section:
        return section, GUESS, "a live page of the same section"
    return None, None, "no live page shares its words or its section"


def _parent(path: str, live: Live) -> str | None:
    head, _ = _parts(path)
    while head and head != "/":
        got = live.find(head)
        if got:
            return got
        head, _ = _parts(head)
    return None


def rules(old: str, target: str | None) -> dict:
    """The server lines for the choice, as text: {"nginx", "apache"} (None: write it by hand).
    A target redirects (301); no target says gone (410). The paths are decoded first: nginx
    and Apache match the decoded address."""
    src = unquote(old.split("?", 1)[0])
    dst = unquote(target.split("?", 1)[0]) if target else None
    if not _SAFE.match(src) or (dst is not None and not _SAFE.match(dst)):
        return {"nginx": None, "apache": None}
    if dst:
        return {"nginx": f"location = {src} {{ return 301 {dst}; }}",
                "apache": f"Redirect 301 {src} {dst}"}
    return {"nginx": f"location = {src} {{ return 410; }}", "apache": f"Redirect gone {src}"}

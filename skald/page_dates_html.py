"""A page's own published and modified dates, read from its HTML (SKALD-64),
and its title (SKALD-70).

page_dates.py fetches the page; this module only reads what came back. Three
places are read, in this order, each date on its own (the first place that
gives a valid value wins for that date):

  jsonld  <script type="application/ld+json">: `datePublished` and
          `dateModified` of an article (Article, BlogPosting, NewsArticle,
          ...) or a web page (WebPage, FAQPage, ...). A node whose url, @id
          or mainEntityOfPage is the page itself comes first (an article
          before a web page among them), then a top-level node (the block
          itself, its list or its @graph). A node nested in another that is
          not the page (a related post in a listing's hasPart, a comment)
          is never read, nor any other type (a review, the organisation):
          their dates are not the page's.
  meta    <meta property="article:published_time"> and
          "article:modified_time" (Open Graph; also og:updated_time for the
          modified date), and any tag with itemprop="datePublished" /
          "dateModified" and a content attribute (microdata)
  time    a <time datetime> tag marked as the page's: itemprop
          "datePublished" / "dateModified", or the hAtom classes "published"
          / "updated". A bare <time> is never taken: on a page it is as often
          a comment's, a related post's or an event's date.

The title (SKALD-70), the first place that gives one: the page's <title>
("html"; a <title> inside an <svg> is an icon's, never read), else its
og:title meta tag ("meta"), else the `headline` of the JSON-LD node chosen as
above ("jsonld"). Entities are read as the characters they stand for, white
space is folded to single spaces, and a title longer than TITLE_MAX characters
is cut at a word and ends with "…". An empty title is none.

A value is valid when it is a W3C date or date-time (normalise): a date
alone, or a date and time with or without a zone, no year before EARLIEST and
nothing later than now (a zone-less value may be up to 14 hours ahead, the
widest zone). A date and time with a zone is kept in UTC
("2026-11-26T05:42:14Z"), one without a zone as written
("2026-11-26T05:42:14"), a date alone as a date ("2024-11-05"). Anything else
is not a date: never guessed.
"""
from __future__ import annotations

import html as htmllib
import json
import re
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit

EARLIEST = 1990
SOURCES = ("jsonld", "meta", "time")
_W3C = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})"
    r"(?:[Tt ](\d{2}):(\d{2})(?::(\d{2})(?:[.,]\d+)?)?\s*(Z|z|[+-]\d{2}(?::?\d{2})?)?)?")
ARTICLE = {"article", "newsarticle", "blogposting", "techarticle", "scholarlyarticle",
           "report", "socialmediaposting", "liveblogposting", "analysisnewsarticle",
           "opinionnewsarticle", "reportagenewsarticle", "reviewnewsarticle",
           "backgroundnewsarticle", "howto", "recipe"}
WEBPAGE = {"webpage", "aboutpage", "faqpage", "itempage", "collectionpage", "profilepage",
           "qapage", "medicalwebpage", "checkoutpage", "contactpage", "searchresultspage"}
META = {"published": ("article:published_time", "og:article:published_time", "datepublished"),
        "modified": ("article:modified_time", "og:article:modified_time", "og:updated_time",
                     "datemodified")}
LD_FIELD = {"published": "datePublished", "modified": "dateModified"}
ITEMPROP = {"datepublished": "published", "datemodified": "modified"}
HATOM = {"published": "published", "updated": "modified"}
MAX_LD = 40                        # JSON-LD blocks read at most
MAX_LD_BYTES = 500_000             # characters of one block
TITLE_MAX = 300                    # characters of a title kept (SKALD-70)
TITLE_SOURCES = ("html", "meta", "jsonld")


_TAG = re.compile(r"<[a-zA-Z/][^<>]*>")
_ZERO = re.compile("[\u200b-\u200d\u2060\ufeff]")


def clean_title(raw, markup: bool = True) -> str | None:
    """A title as kept (module doc), or None when there is none. `markup`: raw is HTML
    as written (a <title>'s text, a JSON-LD headline): tags inside it (the parser keeps
    <title>A <b>B</b></title> as text) are left out first, then entities are decoded, so
    "&lt;video&gt;" stays "<video>". Without it (an attribute, already decoded) nothing
    is taken out. Zero-width characters are left out."""
    if not isinstance(raw, str):
        return None
    text = htmllib.unescape(_TAG.sub(" ", raw)) if markup else raw
    text = " ".join(_ZERO.sub("", text).split())
    if not text:
        return None
    if len(text) > TITLE_MAX:
        cut = text[:TITLE_MAX - 1]
        space = cut.rfind(" ")
        cut = cut[:space] if space > TITLE_MAX // 2 else cut
        text = (cut.rstrip(" ,.;:-") or cut) + "…"
    return text


def normalise(raw, now: datetime) -> str | None:
    """A W3C date or date-time as stored (module doc), or None."""
    found = _W3C.fullmatch(str(raw or "").strip())
    if not found:
        return None
    y, mo, d, hh, mm, ss, zone = found.groups()
    try:
        day = date(int(y), int(mo), int(d))
    except ValueError:
        return None
    now = now.astimezone(timezone.utc)
    if day.year < EARLIEST:
        return None
    if hh is None:
        return day.isoformat() if day <= (now + timedelta(hours=14)).date() else None
    if int(hh) > 23 or int(mm) > 59 or int(ss or 0) > 59:
        return None
    clock = f"{int(hh):02d}:{int(mm):02d}:{int(ss or 0):02d}"
    if zone is None:
        stamp = datetime.fromisoformat(f"{day.isoformat()}T{clock}")
        if stamp > now.replace(tzinfo=None) + timedelta(hours=14):
            return None
        return stamp.isoformat()
    if zone in ("Z", "z"):
        offset = "+00:00"
    else:
        digits = zone[1:].replace(":", "")
        if len(digits) == 2:
            digits += "00"
        if int(digits[:2]) > 23 or int(digits[2:]) > 59:
            return None
        offset = f"{zone[0]}{digits[:2]}:{digits[2:]}"
    try:
        stamp = datetime.fromisoformat(f"{day.isoformat()}T{clock}{offset}")
    except ValueError:
        return None
    stamp = stamp.astimezone(timezone.utc)
    if stamp > now + timedelta(minutes=5) or stamp.year < EARLIEST:
        return None
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def local_day(value: str | None, tz) -> str | None:
    """A stored value's day in the site's zone ("YYYY-MM-DD"): a UTC time is
    moved to the zone; a date, or a time without a zone, is its own day."""
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        try:
            return datetime.fromisoformat(text[:-1] + "+00:00").astimezone(tz).date().isoformat()
        except ValueError:
            return None
    return text[:10]


def order_key(value: str) -> str:
    """A stored value as text that sorts in time order (a date as its midnight)."""
    text = str(value or "")
    return text[:19] if len(text) > 10 else f"{text}T00:00:00"


def _types(node: dict) -> set:
    got = node.get("@type")
    items = got if isinstance(got, list) else [got]
    return {str(t).lower().rsplit("/", 1)[-1] for t in items if isinstance(t, str)}


def _self(node: dict, page_path: str) -> bool:
    for k in ("url", "@id", "mainEntityOfPage"):
        v = node.get(k)
        if isinstance(v, dict):
            v = v.get("@id") or v.get("url")
        if isinstance(v, str) and v:
            try:
                p = urlsplit(v).path or "/"
            except ValueError:
                continue
            if p.rstrip("/") == page_path.rstrip("/"):
                return True
    return False


def _nodes(value, out: list, depth: int = 0) -> None:
    if depth > 12 or len(out) > 500:
        return
    if isinstance(value, dict):
        out.append(value)
        for v in value.values():
            if isinstance(v, (dict, list)):
                _nodes(v, out, depth + 1)
    elif isinstance(value, list):
        for v in value:
            _nodes(v, out, depth + 1)


def from_jsonld(blocks: list[str], page_path: str, now: datetime) -> dict:
    """{"published": value, "modified": value} (either None) from the JSON-LD."""
    nodes: list[dict] = []
    tops: set[int] = set()
    for text in blocks[:MAX_LD]:
        text = text.strip()[:MAX_LD_BYTES]
        for mark in ("<!--", "<![CDATA["):
            if text.startswith(mark):
                text = text[len(mark):]
        for mark in ("-->", "]]>"):
            if text.endswith(mark):
                text = text[:-len(mark)]
        try:
            got = json.loads(text, strict=False)
        except ValueError:
            continue
        for item in (got if isinstance(got, list) else [got]):
            if isinstance(item, dict):
                tops.add(id(item))
                tops.update(id(g) for g in (item.get("@graph") or [])
                            if isinstance(item.get("@graph"), list) and isinstance(g, dict))
        _nodes(got, nodes)
    ranked = []
    for i, node in enumerate(nodes):
        types = _types(node)
        tier = 0 if types & ARTICLE else 1 if types & WEBPAGE else None
        own = _self(node, page_path)
        if tier is not None and (own or id(node) in tops):
            ranked.append((0 if own else 1, tier, i, node))
    ranked.sort(key=lambda r: r[:3])
    out = {"published": None, "modified": None, "title": None}
    for kind, field in LD_FIELD.items():
        for *_, node in ranked:
            value = node.get(field)
            if isinstance(value, list):
                value = value[0] if value else None
            got = normalise(value, now) if isinstance(value, str) else None
            if got:
                out[kind] = got
                break
    for *_, node in ranked:
        got = clean_title(node["headline"]) \
            if isinstance(node.get("headline"), str) else None
        if got:
            out["title"] = got
            break
    return out


class _Reader(HTMLParser):
    def __init__(self) -> None:
        # Entities come one by one (handle_entityref): a title keeps them as written,
        # so clean_title can tell "&lt;b&gt;" (text) from "<b>" (a tag).
        super().__init__(convert_charrefs=False)
        self.blocks: list[str] = []
        self.meta: dict[str, str] = {}
        self.times: dict[str, list[str]] = {"published": [], "modified": []}
        self._ld: list[str] | None = None
        self.title: str | None = None          # the first <title> outside an <svg>
        self._title: list[str] | None = None
        self._svg = 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs if k}
        if tag == "head":
            self._svg = 0                      # no <svg> can hold the head: one left open is closed
        if tag == "svg":
            self._svg += 1
        elif tag == "title" and not self._svg and self.title is None:
            self._title = []
        if tag == "script":
            if "ld+json" in a.get("type", "").lower() and len(self.blocks) < MAX_LD:
                self._ld = []
            return
        prop = a.get("itemprop", "").strip().lower()
        if tag == "meta":
            name = (a.get("property") or a.get("name") or prop).strip().lower()
            if name and a.get("content") and name not in self.meta:
                self.meta[name] = a["content"]
            return
        if prop in ITEMPROP and a.get("content") and prop not in self.meta:
            self.meta[prop] = a["content"]
        if tag == "time" and a.get("datetime"):
            kind = ITEMPROP.get(prop)
            if kind is None:
                classes = set(a.get("class", "").lower().split())
                kind = next((HATOM[c] for c in ("published", "updated") if c in classes), None)
            if kind is not None:
                self.times[kind].append(a["datetime"])

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
        if self._title is not None:
            self._title.append(data)

    def handle_entityref(self, name):
        if self._title is not None:
            self._title.append(f"&{name};")

    def handle_charref(self, name):
        if self._title is not None:
            self._title.append(f"&#{name};")

    def handle_endtag(self, tag):
        if tag == "svg" and self._svg:
            self._svg -= 1
        if tag == "title" and self._title is not None:
            self.title = "".join(self._title)
            self._title = None
        if tag == "script" and self._ld is not None:
            self.blocks.append("".join(self._ld))
            self._ld = None


def parse(html: str, page_path: str, now: datetime) -> dict:
    """{"published", "modified", "title"}: each (value, source) or None."""
    reader = _Reader()
    try:
        reader.feed(html)
        reader.close()
    except Exception:                    # noqa: BLE001 - what was read so far stands
        pass
    ld = from_jsonld(reader.blocks, page_path, now)
    out: dict = {}
    for kind in ("published", "modified"):
        got = None
        if ld[kind]:
            got = (ld[kind], "jsonld")
        if got is None:
            for name in META[kind]:
                value = normalise(reader.meta.get(name), now)
                if value:
                    got = (value, "meta")
                    break
        if got is None:
            for raw in reader.times[kind]:
                value = normalise(raw, now)
                if value:
                    got = (value, "time")
                    break
        out[kind] = got
    out["title"] = None
    for value, source in ((clean_title(reader.title), "html"),
                          (clean_title(reader.meta.get("og:title"), markup=False), "meta"),
                          (ld["title"], "jsonld")):
        if value:
            out["title"] = (value, source)
            break
    return out

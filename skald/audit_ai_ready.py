"""The second count of ai_readiness (ai_ready.json, ai_ready.py): can AI read each page well?

Registered in audit_more.DAILY: run-daily's recounts step works the whole file
out again from what is stored, with its own code. It shares the name lists
only (the main AI crawlers, ai_ready.CRAWLERS; the Markdown endings,
not_pages.RULES); it calls nothing in ai_ready.py, ai_status.py, robots.py,
robots_match.py, sitemap.py or lifecycle.py to count, and asks
ai_ready.figures only for the figures the file shows, to compare them.

  a day         audit_page_trends.states: the `days` table's own reading;
                whole and partial days have figures
  the answers   each day's stored ai_status blob (its own second count is
                audit_ai_status.py, against the raw lines), read here with
                its own SQL
  a page        the address cut at "?" and "#", with "/" added unless it ends
                with one. A Markdown copy (the address without its trailing
                "/" ends .md, .mdx or .markdown, letters A-Z in any case)
                belongs to the address without that ending, without a last
                "index" after a "/" and with the "/" added: /a/b.md,
                /a/b/index.md and /a/b/.md are /a/b/'s. Any other address
                counts only when the audit's own reading of AI fetches calls
                it a "Page" (audit_ai_formats.kind_of), with and without a
                closing "/", no part of it starts with "." and its own reading
                of the not-a-page list names nothing (audit_not_pages.Marker)
  robots.txt    robots.txt and robots-state.json beside the history, read
                here: a group starts at a User-agent line that follows an
                Allow or a Disallow line (with a value or none); a crawler's
                rules are every group naming it (the text before "/", any
                case), else every "*" group's. A rule is turned into a regular
                expression ("*" any characters, a "$" at the end the end);
                the longest matching pattern decides, an Allow on a tie; none
                matching allows. Paths and patterns are compared with %xx of a
                letter, digit or - . _ ~ written out, other %xx in capitals,
                and characters outside printable ASCII as their UTF-8 %xx.
                No copy and the last try answered 4xx (not 429): no
                robots.txt, everything allowed
  the sitemap   sitemaps/days.json's latest day no later than today, its list
                file (which must hash to its name), each path a page; the
                change date by audit_lastmod.expected
  needs         per page: a copy's answers but 2xx and 304 (and of them 404
                and 410), the page's 404 and 410, its 5xx, its other 4xx, the
                crawlers its path shuts out that may fetch "/", its slow
                answers; a page with any of them is listed, worst first (the
                four answer counts together, then the crawlers, the slow
                answers, the redirects, the path); its 3xx but 304 are said
                beside them

A problem is a figure the file shows that the stored data does not give.
Nothing is changed: the run's outcome says the recount does not match.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from .ai_ready import CRAWLERS
from .not_pages import RULES

WINDOW = 30
ROWS = 100
REST = "(all others)"
_ENDS = tuple(RULES["markdown"][1]["ends"])
_SAFE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def set_up(ctx) -> bool:
    """True once a day of what AI got back was stored for the site."""
    try:
        with ctx.history() as history:
            return history.db.execute("SELECT 1 FROM day_extras WHERE site = ? AND kind = "
                                      "'ai_status' LIMIT 1", (ctx.site,)).fetchone() is not None
    except Exception:              # noqa: BLE001 - no history yet: nothing to recount
        return False


def _small(text: str) -> str:
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)


def _page(path) -> str:
    cut = re.split(r"[?#]", str(path or ""), maxsplit=1)[0]
    return cut if cut.endswith("/") else cut + "/"


def page_and_copy(path: str) -> tuple[str, bool]:
    cut = re.split(r"[?#]", str(path or ""), maxsplit=1)[0]
    bare = re.sub(r"/+$", "", cut)
    hit = [e for e in _ENDS if _small(bare).endswith(e)]
    if not hit:
        return _page(cut), False
    bare = bare[:len(bare) - max(len(e) for e in hit)]
    if _small(bare).endswith("/index"):
        bare = bare[:-5]
    return _page(bare or "/"), True


# ------------------------------------------------------------- robots.txt

def _norm(text: str) -> str:
    def one(m):
        ch = chr(int(m.group(1), 16))
        return ch if ch in _SAFE else "%" + m.group(1).upper()
    text = re.sub(r"%([0-9A-Fa-f]{2})", one, text or "")
    return "".join(c if 32 < ord(c) < 127 else "".join(
        f"%{b:02X}" for b in (chr(0xFFFD) if 0xD800 <= ord(c) <= 0xDFFF else c).encode("utf-8"))
        for c in text)


def groups_of(text: str) -> list[dict]:
    groups, cur, closed = [], None, True
    text = text or ""
    if text.startswith("\ufeff"):
        text = text[1:]
    for raw in text.split("\n"):
        line = raw.split("#")[0].strip()
        name, colon, value = line.partition(":")
        if not colon:
            continue
        name, value = name.strip().lower(), value.strip()
        if name == "user-agent":
            if closed:
                cur = {"agents": [], "rules": []}
                groups.append(cur)
                closed = False
            cur["agents"].append(value)
        elif name in ("allow", "disallow") and cur is not None:
            closed = True
            if value:
                cur["rules"].append((name, value))
    return groups


def _agent(value: str) -> str:
    return value.split("/")[0].strip().lower()


def crawler_rules(groups: list[dict], token: str) -> tuple[list, list]:
    """(the User-agent values that apply, the rules) for one crawler."""
    t = token.lower()
    mine = [g for g in groups if t in [_agent(a) for a in g["agents"]]]
    if not mine:
        mine = [g for g in groups if "*" in [_agent(a) for a in g["agents"]]]
    agents = []
    for g in mine:
        for a in g["agents"]:
            if _agent(a) in (t, "*") and a.strip() not in agents:
                agents.append(a.strip())
    return agents, [r for g in mine for r in g["rules"]]


def may(rules: list, path: str) -> bool:
    target = _norm(path or "/")
    best = None
    for kind, pattern in rules:
        p = _norm(pattern)
        if not p:
            continue
        body, end = (p[:-1], True) if p.endswith("$") else (p, False)
        rx = "".join(".*" if c == "*" else re.escape(c) for c in body) + (r"\Z" if end else "")
        if re.match(rx, target, re.S) is None:
            continue
        if best is None or len(p) > best[0] or (len(p) == best[0] and kind == "allow"):
            best = (len(p), kind)
    return best is None or best[1] == "allow"


def robots_of(folder) -> dict:
    """{"ok", "missing", "crawlers": {token: {"agents", "rules", "root"}} or None}."""
    text = state = None
    if folder is not None:
        try:
            text = (Path(folder) / "robots.txt").read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = None
        try:
            state = json.loads((Path(folder) / "robots-state.json").read_text())
        except (OSError, ValueError):
            state = None
    state = state if isinstance(state, dict) else {}
    code = re.search(r"HTTP Error (\d{3})", str(state.get("error") or ""))
    missing = text is None and code is not None and code.group(1).startswith("4") \
        and code.group(1) != "429"
    out = {"ok": text is not None, "missing": missing, "crawlers": None}
    if text is not None:
        groups = groups_of(text.replace("\r\n", "\n").replace("\r", "\n"))
        out["crawlers"] = {}
        for token, _ in CRAWLERS:
            agents, rules = crawler_rules(groups, token)
            out["crawlers"][token] = {"agents": agents, "rules": rules, "root": may(rules, "/")}
    return out


def shut(robots: dict, path: str) -> list:
    if robots["missing"] or robots["crawlers"] is None:
        return []
    return [t for t, _ in CRAWLERS if robots["crawlers"][t]["root"]
            and not may(robots["crawlers"][t]["rules"], path)]


# --------------------------------------------------------------- sitemap

def sitemap_of(config: dict, folder, today: date) -> dict | None:
    """{page: lastmod} of the list kept for today, or None."""
    from .audit_lastmod import _off
    from .audit_page_trends import _dates
    if folder is None or _off(config):
        return None
    try:
        days = json.loads((Path(folder) / "sitemaps" / "days.json").read_text())
    except (OSError, ValueError):
        return None
    kept = sorted(d for d in (days if isinstance(days, dict) else {}) if d <= today.isoformat())
    if not kept:
        return None
    lid = str((days[kept[-1]] or {}).get("list") or "")
    try:
        paths = [str(p) for p in json.loads(
            (Path(folder) / "sitemaps" / f"{lid}.json").read_text()).get("paths") or []]
    except (OSError, ValueError, AttributeError):
        return None
    if hashlib.sha256("\n".join(sorted(paths)).encode("utf-8")).hexdigest()[:16] != lid:
        return None

    class _Ctx:
        pass
    ctx = _Ctx()
    ctx.config, ctx.live_dir = config, folder
    dates = _dates(ctx)
    return {_page(p): (dates.get(_page(p)) or {}).get("lastmod") for p in paths}


# ---------------------------------------------------------------- the days

def answers(db, site: str, last: date, config: dict | None = None) -> tuple[dict, dict]:
    """(window, pages) by the rule above."""
    from .audit_ai_formats import kind_of
    from .audit_not_pages import Marker
    from .audit_page_trends import states
    marker = Marker(config)

    def which(path):
        page, copy = page_and_copy(path)
        if copy:
            return page, True
        bare = re.split(r"[?#]", str(path), maxsplit=1)[0]
        if kind_of(bare, "") != "Page" or kind_of(re.sub(r"/+$", "", bare) or "/", "") != "Page":
            return None
        if re.search(r"(^|/)\.", bare) or marker(bare, bare):
            return None
        return page, False
    first = last - timedelta(days=WINDOW - 1)
    st = states(db, site, first, last)
    blobs = {d: json.loads(data) for d, data in db.execute(
        "SELECT day, data FROM day_extras WHERE site = ? AND kind = 'ai_status' AND day BETWEEN "
        "? AND ?", (site, first.isoformat(), last.isoformat()))}
    pages: dict[str, dict] = {}
    of = recorded = folded = 0
    since = None
    for day in sorted(st):
        if st[day] not in ("ok", "partial"):
            continue
        of += 1
        blob = blobs.get(day)
        if blob is None:
            continue
        recorded += 1
        since = since or day
        if any(int(v or 0) for v in (blob.get("folded") or {}).values()):
            folded += 1
        for path, per in (blob.get("answers") or {}).items():
            got = None if path == REST else which(path)
            if got is None:
                continue
            page, copy = got
            row = pages.setdefault(page, {"self": {}, "slow": Counter(), "copies": {}})
            into = row["copies"].setdefault(path, {}) if copy else row["self"]
            for name, codes in per.items():
                into.setdefault(name, Counter()).update({str(k): int(v) for k, v in codes.items()})
        for path, per in (blob.get("slow") or {}).items():
            got = None if path == REST else which(path)
            if got is None or got[1]:
                continue
            page = got[0]
            row = pages.setdefault(page, {"self": {}, "slow": Counter(), "copies": {}})
            row["slow"].update({k: int(v) for k, v in per.items()})
    window = {"days": WINDOW, "first": first.isoformat(), "last": last.isoformat(), "of": of,
              "recorded": recorded, "since": since, "folded": folded}
    return window, pages


def _count(per: dict, test) -> int:
    return sum(n for codes in per.values() for code, n in codes.items() if test(code))


def need_row(page: str, facts: dict | None, robots: dict, listed) -> dict:
    facts = facts or {"self": {}, "slow": Counter(), "copies": {}}
    own, copies = facts["self"], list(facts["copies"].values())
    ok = lambda c: c.startswith("2") or c == "304"          # noqa: E731
    return {"path": page, "listed": None if listed is None else page in listed,
            "copy_errors": sum(_count(c, lambda x: not ok(x)) for c in copies),
            "copy_404": sum(_count(c, lambda x: x in ("404", "410")) for c in copies),
            "not_found": _count(own, lambda x: x in ("404", "410")),
            "server_errors": _count(own, lambda x: x.startswith("5")),
            "blocked": _count(own, lambda x: x.startswith("4") and x not in ("404", "410")),
            "robots": shut(robots, page),
            "redirects": _count(own, lambda x: x.startswith("3") and x != "304"),
            "slow": sum(facts["slow"].values()),
            "by": sorted({n for per in [own] + copies for n, codes in per.items()
                          if any(not ok(c) for c in codes)}
                         | {n for n, v in facts["slow"].items() if v})}


def recheck(db, site: str, last: date, today: date, config: dict, folder, shown: dict) -> list:
    problems = []
    window, pages = answers(db, site, last, config)
    if shown.get("window") != window:
        problems.append(f"ai readiness: window shown {shown.get('window')!r}, history gives "
                        f"{window!r}")
    plain = {p: {"self": {n: dict(c) for n, c in r["self"].items()}, "slow": dict(r["slow"]),
                 "copies": {cp: {n: dict(c) for n, c in per.items()}
                            for cp, per in r["copies"].items()}} for p, r in pages.items()}
    got = shown.get("pages") or {}
    for page in sorted(set(plain) | set(got)):
        if got.get(page) != plain.get(page):
            problems.append(f"ai readiness {page}: what AI got back shown {got.get(page)!r}, "
                            f"history gives {plain.get(page)!r}")
    robots = robots_of(folder)
    rshown = shown.get("robots") or {}
    if (bool(rshown.get("ok")), bool(rshown.get("missing"))) != (robots["ok"], robots["missing"]):
        problems.append("ai readiness: robots.txt shown as kept or missing, the files say "
                        f"ok={robots['ok']} missing={robots['missing']}")
    mine_c, shown_c = robots["crawlers"], rshown.get("crawlers")
    if (mine_c is None) != (shown_c is None):
        problems.append("ai readiness: robots.txt rules shown without a copy, or none with one")
    elif mine_c is not None:
        for token, c in mine_c.items():
            s = shown_c.get(token) or {}
            if Counter(map(tuple, s.get("rules") or [])) != Counter(c["rules"]) or \
                    s.get("agents") != c["agents"] or s.get("root") != c["root"]:
                problems.append(f"ai readiness: {token}'s robots.txt rules or verdict for / "
                                "do not match the file")
    listed = sitemap_of(config, folder, today)
    sm = (shown.get("sitemap") or {}).get("pages")
    if sm != listed:
        problems.append(f"ai readiness: sitemap pages shown {len(sm or {})}, the stored list "
                        f"gives {None if listed is None else len(listed)} (or their dates differ)")
    rows = []
    for page in sorted(set(pages) | set(listed or {})):
        r = need_row(page, pages.get(page), robots, listed)
        if r["copy_errors"] or r["not_found"] or r["server_errors"] or r["blocked"] \
                or r["robots"] or r["slow"]:
            rows.append(r)
    rows.sort(key=lambda r: (-(r["copy_errors"] + r["not_found"] + r["server_errors"]
                               + r["blocked"]), -len(r["robots"]), -r["slow"], -r["redirects"],
                             r["path"]))
    att = shown.get("attention") or {}
    if att.get("total") != len(rows):
        problems.append(f"ai readiness: {att.get('total')!r} pages need attention, the recount "
                        f"finds {len(rows)}")
    for a, b in zip(att.get("rows") or [], rows[:ROWS]):
        if a != b:
            problems.append(f"ai readiness, needs {b['path']}: shown {a!r}, recount {b!r}")
            break
    if len(att.get("rows") or []) != len(rows[:ROWS]):
        problems.append("ai readiness: the list of pages that need attention is not as long as "
                        "the recount's")
    return problems


def daily(ctx, day) -> list[str] | None:
    """run-daily: the problems found (empty: they match); None when not set up."""
    if not set_up(ctx):
        return None
    from . import ai_ready
    folder = Path(ctx.live_dir) if getattr(ctx, "live_dir", None) else None
    today = day + timedelta(days=1)
    with ctx.history() as history:
        first = day - timedelta(days=WINDOW - 1)
        shown = ai_ready.figures(history, ctx.site, history.daily(ctx.site, first, day), day,
                                 today, ctx.config, folder)
        problems = recheck(history.db, ctx.site, day, today, ctx.config, folder, shown)
    ctx.out(f"ai readiness: {len(shown['pages'])} pages and "
            f"{shown['attention']['total']} that need attention recounted")
    return problems

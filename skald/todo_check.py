"""Overview > Insights' "Check again": re-run one to-do's own check now (2.44).

The owner (27 Oct): "I have made fixes; there is no way to re-run the check. Can that be
built for each case?" A to-do (todos.py) is re-checked on its own on the whole days after
it is marked done. This answers at once, by the kind's own road:

  kind       its rows come from                        Check again
  lost       the day's log: old page addresses that    live: Skald asks each address. Fixed:
             answered 404 or 410 (lost_pages.py)       410 gone, a redirect that ends on a
                                                       live page, or the page live again
  markdown   the day's log: AI asks for .md copies     live: fixed when the .md address answers
             of live pages that answered 404           2xx, or redirects to a page that does
  sitemap    the day's log: crawlers' asks for a       live: fixed when it answers 2xx, or
             *sitemap*.xml that answered 404           redirects to one that does
  errors     the history's counts: 5xx by address      live: fixed when each address answers
                                                       without a 5xx (one ask each; the daily
                                                       re-check counts the log after)
  leave      the stored journeys (visits)              log only: judged on whole days of
                                                       visits after the mark; the page says
                                                       so, and what the last update found

Each live check also reads the newest log lines since the fix (the mark's time, or the
agent's report), at most LOG_HOURS back: "none of these addresses answered 404 since
14:10". That line informs; the verdict is the live answer, because a fix made after the
mark leaves older failures in the log.

How Skald asks, politely: at most CAP addresses a check ("Check the next 50" for more),
one at a time, GAP seconds apart, TIMEOUT seconds each and BUDGET seconds in all (an
address not reached is left for the next page); its own user agent (AGENT, counted as
Skald's own, classify.OWN_AGENTS, never as a visitor or a bot); site_fetch.py's checked
fetch (public addresses only, no cookie); HEAD first (GET for server errors, and when HEAD
is refused), and no body is ever read or kept. A redirect is followed at most HOPS times,
and only on the site's own hosts: never to another host.

The verdict of a sweep (every page of one check, todo_checks.py): fixed (every row),
partly, not_fixed, more (rows left to check), waiting (log only, not enough yet) or error
(the site did not answer at all: nothing is changed). A fixed sweep marks the to-do fixed
(todo_marks.mark_checked); the audit (audit_todo_checks.py) re-derives that mark from the
rows kept.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlsplit

from . import todo_checks, todo_marks

CAP = 50
BUDGET = 20.0
TIMEOUT = 5.0
GAP = 0.1
HOPS = 2
LOG_HOURS = 24
AGENT_TOKEN = "site-todo-check/"
AGENT = f"Mozilla/5.0 (compatible; {AGENT_TOKEN}1; one look at an address a to-do lists, asked for by the site's owner)"
LIVE = ("lost", "markdown", "sitemap", "errors")
LOG_ONLY = ("leave",)
REDIRECTS = (301, 302, 303, 307, 308)
OTHER = "(all others)"
WHAT = {"lost": "addresses", "markdown": "Markdown copies", "sitemap": "sitemap addresses",
        "errors": "addresses"}
FAILS = {"lost": "404", "markdown": "404", "sitemap": "404", "errors": "a server error"}


class Refused(ValueError):
    def __init__(self, status: int, words: str):
        super().__init__(words)
        self.status = status


def mode_of(kind: str) -> str:
    return "live" if kind in LIVE else "log"


# ------------------------------------------------------------------ one address

def _default_fetch(url: str, method: str, deadline: float):
    from . import site_fetch
    return site_fetch.fetch(url, method, deadline, max_bytes=0, headers={"User-Agent": AGENT})


def _ask(fetch, url: str, method: str, deadline: float):
    """(status, location) of one request; HEAD refused (405, 501) asks again with GET."""
    got = fetch(url, method, deadline)
    if method == "HEAD" and got.status in (405, 501):
        got = fetch(url, "GET", deadline)
    loc = (got.headers.get("location") or [""])[0].strip() if got.status in REDIRECTS else ""
    return got.status, loc


def askable(path) -> bool:
    """A real address of the site: never the folded tail, never one whose email or
    address todo_rows.scrub replaced (that is not the address people asked for)."""
    from .todo_rows import REMOVED
    return (isinstance(path, str) and path.startswith("/") and not path.startswith("//")
            and path != OTHER and REMOVED not in path and len(path) <= 2000
            and not any(ord(c) <= 32 or ord(c) == 127 for c in path))


def probe(base: str, hosts: set[str], path: str, kind: str, fetch, deadline: float,
          target: str | None = None) -> dict:
    """What one address answers now: {path, status, end, location, other_host, ok, why}."""
    from . import site_fetch
    row = {"path": path, "status": None, "end": None, "location": None, "other_host": False,
           "ok": False, "why": ""}
    method = "GET" if kind == "errors" else "HEAD"
    url = base + path
    try:
        status, loc = _ask(fetch, url, method, deadline)
        row["status"] = row["end"] = status
        hops = 0
        while status in REDIRECTS and loc and kind != "errors":
            nxt = urljoin(url, loc)
            parts = urlsplit(nxt)
            ours = (parts.hostname or "").lower() in hosts and parts.scheme in ("http", "https")
            if row["location"] is None:          # where the address itself sends people
                row["location"] = (parts.path or "/") + (f"?{parts.query}" if parts.query else "") \
                    if ours else f"{parts.scheme}://{parts.hostname or ''}{parts.path}"
            if not ours:
                row["other_host"], row["end"] = True, None
                break
            if hops >= HOPS:
                row["end"] = status
                break
            hops += 1
            url = nxt
            status, loc = _ask(fetch, url, "HEAD", deadline)
            row["end"] = status
    except site_fetch.Refused as why:
        row["why"] = str(why)
        row["refused"] = True
        return row
    except (site_fetch.Unreachable, OSError) as why:
        row["why"] = f"did not answer: {why}" if str(why) else "did not answer"
        row["unreachable"] = str(why) or "it did not answer"
        return row
    row["ok"], row["why"] = judge(kind, row, target)
    return row


def judge(kind: str, row: dict, target: str | None = None) -> tuple[bool, str]:
    """Is this address fixed, and the words."""
    status, end, loc = row["status"], row["end"], row["location"]
    if kind == "errors":
        return (status < 500, f"answers {status}")
    if status in REDIRECTS:
        if loc is None:
            return False, f"answers {status} with no address to go to"
        if row["other_host"]:
            return True, f"answers {status} to another site (not followed)"
        if end is not None and 200 <= end < 300:
            to = " (the suggested page)" if target and loc and loc.split("?")[0] == target else ""
            return True, f"answers {status} to a live page{to}"
        if end in REDIRECTS:
            return False, f"answers {status}, then redirects more than {HOPS} times"
        return False, f"answers {status} to a page that answers {end}"
    if 200 <= status < 300:
        return True, f"answers {status}" + (": the page is live" if kind == "lost" else "")
    if status == 410 and kind == "lost":
        return True, "answers 410 gone"
    return False, f"still answers {status}" if status in (404, 410) else f"answers {status}"


# ------------------------------------------------------------------ the log since the fix

def read_log(cfg: dict, paths: set[str], since: datetime, now: datetime, bad) -> dict:
    """The site's log lines for `paths` since `since`: {read, lines, failed, newest}.
    Skald's own asks (AGENT) are left out."""
    from .config import setting
    from .parse import sizes
    from .realtime_tail import _parser, tail_lines
    from .window import window_paths
    try:
        files = [p for p in window_paths(cfg, since, now, now) if p.suffix != ".gz"]
    except Exception:                    # noqa: BLE001 - no log folder here (a drain, a test)
        files = []
    out = {"read": bool(files), "lines": 0, "failed": 0, "newest": None, "partial": False}
    if not files:
        return out
    hosts = {str(h).lower() for h in (setting(cfg, "site", "hosts") or [])}
    upto = sizes(files)
    newest = None
    for f in files:
        lines, short = tail_lines(f, since, upto.get(f.name, 0))
        out["partial"] = out["partial"] or short
        parse_one = _parser(cfg, lines[-200:])
        for line in lines:
            hit = parse_one(line)
            if hit is None or AGENT_TOKEN in (hit.user_agent or "").lower():
                continue
            when = hit.when if hit.when.tzinfo else hit.when.replace(tzinfo=timezone.utc)
            if when < since or (hosts and hit.host and hit.host.lower() not in hosts):
                continue
            if hit.url not in paths and hit.url.split("?", 1)[0] not in paths:
                continue
            out["lines"] += 1
            if bad(str(hit.status)):
                out["failed"] += 1
                newest = when if newest is None or when > newest else newest
    out["newest"] = newest.strftime("%Y-%m-%dT%H:%M:%SZ") if newest else None
    return out


def log_part(cfg, kind: str, paths: set[str], since: datetime | None, now: datetime,
             reader=None) -> dict | None:
    if since is None or kind not in LIVE:
        return None
    since = max(since, now - timedelta(hours=LOG_HOURS))
    bad = (lambda s: s.startswith("5")) if kind == "errors" else (lambda s: s == "404")
    got = (reader or read_log)(cfg, paths, since, now, bad)
    return {"since": since.strftime("%Y-%m-%dT%H:%M:%SZ"), **got}


def _clock(iso: str | None, cfg, now: datetime | None = None) -> str:
    if not iso:
        return ""
    from .window import zone
    when = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(zone(cfg))
    today = (now or datetime.now(timezone.utc)).astimezone(zone(cfg)).date()   # the check's own now
    return when.strftime("%H:%M") if today == when.date() else when.strftime("%-d %b %H:%M")


def log_words(log: dict | None, kind: str, cfg, now: datetime | None = None) -> str:
    if not log:
        return ""
    if not log.get("read"):
        return "The log could not be read here, so only the live answer counts."
    since = _clock(log["since"], cfg, now)
    fail = "a server error" if kind == "errors" else "404"
    if not log["failed"]:
        return f"In the log since {since}: none of these addresses answered {fail}" + \
               (f" ({log['lines']:,} asks)." if log["lines"] else " (nobody asked for them yet).")
    return (f"In the log since {since}: {log['failed']:,} answer{'s' if log['failed'] != 1 else ''} of "
            f"{fail} to these addresses, the newest at {_clock(log['newest'], cfg, now)}. A fix made after "
            "that time is judged by the live answer above.")


# ------------------------------------------------------------------ one check

def rows_of(todo: dict) -> list[dict]:
    """The to-do's addresses Skald can ask, in the list's order (most asked first)."""
    seen, out = set(), []
    for r in todo.get("rows") or []:
        p = r.get("path")
        if askable(p) and p not in seen:
            seen.add(p)
            out.append(r)
    return out


def run(cfg: dict, todo: dict, start: int = 0, fetch=None, clock=time.monotonic, sleep=time.sleep) -> dict:
    """One page of a live check: {mode, start, total, checked, ok, rows, host, stopped}."""
    from .llms_txt import base_url
    base = base_url(cfg).rstrip("/")
    hosts = {str(h).lower() for h in (((cfg or {}).get("site") or {}).get("hosts") or [])}
    hosts.add(urlsplit(base).hostname or "")
    rows = rows_of(todo)
    page = rows[start:start + CAP]
    fetch = fetch or _default_fetch
    end = clock() + BUDGET
    out, stopped = [], None
    for i, r in enumerate(page):
        if clock() > end - TIMEOUT:
            stopped = "time"
            break
        got = probe(base, hosts, r["path"], todo["kind"], fetch, min(end, clock() + TIMEOUT),
                    r.get("target") or r.get("page"))
        out.append(got)
        if got.get("refused"):
            stopped = "refused"
            break
        if i + 1 < len(page):
            sleep(GAP)
    return {"mode": "live", "start": start, "total": len(rows), "checked": len(out),
            "ok": sum(1 for r in out if r["ok"]), "rows": out, "host": urlsplit(base).hostname,
            "stopped": stopped}


def short(r: dict) -> str:
    """One address's answer in a few words, to group them: "answer 404"."""
    if r.get("unreachable") or r.get("refused"):
        return "do not answer"
    status, end = r.get("status"), r.get("end")
    if status in REDIRECTS:
        if r.get("location") is None:
            return f"answer {status} with no address to go to"
        if r.get("other_host"):
            return f"answer {status} to another site"
        if end is not None and 200 <= end < 300:
            return f"answer {status} to a live page"
        return f"answer {status} to a page that answers {end}"
    return "answer 410 gone" if status == 410 else f"answer {status}"


def _count(rows: list[dict]) -> str:
    """"2 answer 404, 1 did not answer" from the rows."""
    from collections import Counter
    return ", ".join(f"{n:,} {w}" for w, n in Counter(short(r) for r in rows).most_common())


def conclude(kind: str, sweep: dict, page: dict, cfg) -> tuple[str, str]:
    """(verdict, words) of a live sweep after this page."""
    what = WHAT[kind]
    total, checked, ok = sweep["total"], sweep["checked"], sweep["ok"]
    if page["stopped"] == "refused":
        return "error", f"Could not check: {page['rows'][-1]['why']} Nothing was changed."
    if page["checked"] and all(r.get("unreachable") for r in page["rows"]):
        return "error", (f"Could not check: {page['host']} did not answer ({page['rows'][0]['unreachable']}). "
                         "Nothing was changed. Try again in a few minutes.")
    if not total:
        return "error", "This to-do lists no address Skald can ask. The daily re-check still counts it."
    bad = [r for r in sweep["rows"] if not r["ok"]]
    if sweep["next"] is not None:
        left = min(CAP, total - sweep["next"])
        why = " Skald stopped to stay polite to your server." if page["stopped"] == "time" else ""
        return "more", (f"{checked:,} of {total:,} {what} checked: {ok:,} fixed"
                        + (f", {len(bad):,} not yet ({_count(bad)})" if bad else "")
                        + f".{why} Check the next {left:,} to finish.")
    every = f"the one {ONE[kind]}" if total == 1 else f"all {total:,} {what}"
    verb = _one if total == 1 else (lambda w: w)
    if not bad:
        if kind == "errors":
            return "fixed", (f"Fixed: {every} now {verb('answer')} without a server error "
                             "(Skald asked each once). The daily re-check keeps counting the log.")
        aimed = sum(1 for r in sweep["rows"] if "(the suggested page)" in r.get("why", ""))
        tail = f" ({aimed:,} to the suggested page)" if kind == "lost" and aimed and total > 1 else \
            " (the suggested page)" if kind == "lost" and aimed else ""
        return "fixed", f"Fixed: {every} now {verb(_how(sweep['rows']))}{tail}."
    if len(bad) == total:
        return "not_fixed", f"Not fixed yet: {every} still {verb(_how(bad))}."
    return "partly", f"{len(bad):,} of {total:,} {what} still {_how(bad)}."


ONE = {"lost": "address", "markdown": "Markdown copy", "sitemap": "sitemap address", "errors": "address"}


def _one(words: str) -> str:
    """The words for one address: "answer 404" -> "answers 404"."""
    for many, one in (("answer ", "answers "), ("do not answer", "does not answer"), ("work: ", "works: "),
                      ("fail: ", "fails: ")):
        if words.startswith(many):
            return one + words[len(many):]
    return "answers" if words == "answer" else words


def _how(rows: list[dict]) -> str:
    """"answer 404" when every row answers the same, else "fail: 2 answer 404, 1 ..."."""
    from collections import Counter
    by = Counter(short(r) for r in rows)
    if len(by) == 1:
        return next(iter(by))
    return "work: " + _count(rows) if all(r.get("ok") for r in rows) else "fail: " + _count(rows)


def waiting(todo: dict, cfg) -> tuple[str, str, dict]:
    """A log-only to-do: what the last data update found, or why it cannot be judged yet."""
    from .todos import LIMITS
    rc = todo.get("recheck") or {}
    last = (todo.get("window") or {}).get("last")
    seen = f" The last data update counted up to {last}." if last else ""
    fig = rc.get("figures") or {}
    if rc.get("verdict") in ("fixed", "not_yet") and rc.get("days"):
        verdict = "fixed" if rc["verdict"] == "fixed" else "not_fixed"
        return verdict, f"From the visits: {rc.get('words')}{seen}", fig
    return "waiting", ("Can't check now: this to-do comes from visits, not from an address Skald can ask. "
                       "It is judged on whole days of visits after you mark it done, once at least "
                       f"{LIMITS['leave_min_visits']} visits start on {todo.get('subject') or 'the page'}."
                       f"{seen}"), fig


def since_of(db, site: str, item: str) -> datetime | None:
    """When the fix was said to be made: the newest of the to-do's mark (done or fixed)
    and the agent's report."""
    stamps = []
    mark = todo_marks.current(db, site).get(item) or {}
    if mark.get("state") in ("done", "fixed"):
        stamps.append(mark["at"])
    fix = todo_marks.fixes(db, site).get(item)
    if fix:
        stamps.append(fix["at"])
    if not stamps:
        return None
    return datetime.strptime(max(stamps), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def check(db, cfg: dict, site: str, todo: dict, start: int = 0, by_user=None, by_who: str = "person",
          fetch=None, reader=None, now: datetime | None = None, today: str | None = None,
          clock=time.monotonic, sleep=time.sleep) -> dict:
    """Check one to-do now, keep it, mark it, and answer what the page shows."""
    item, kind = todo["id"], todo["kind"]
    now = now or datetime.now(timezone.utc)
    sweep = todo_checks.current_sweep(db, site, item)
    if start and (sweep is None or sweep["mode"] != "live" or sweep["next"] != start):
        raise Refused(409, "That page of the check is out of date. Press Check again.")
    starting = not start
    why = todo_checks.limited(db, site, item, starting, now)
    if why:
        raise Refused(429, why)
    if kind not in LIVE:
        verdict, words, fig = waiting(todo, cfg)
        got = {"mode": "log", "start": 0, "total": fig.get("visits", 0), "checked": fig.get("visits", 0),
               "ok": 0, "rows": [], "verdict": verdict, "words": words, "log": None}
        todo_checks.keep(db, site, item, got, None, by_user, by_who, now)
        return {**todo_checks.newest(db, site)[item], "marked": None}
    if fetch is None:
        from .llms_txt import base_url
        from .stack import reserved
        host = urlsplit(base_url(cfg)).hostname or ""
        if reserved(host):
            raise Refused(409, f"{host} is a name kept for examples and tests: Skald never asks it.")
    page = run(cfg, todo, start, fetch, clock, sleep)
    prior = todo_checks.sweep_of(todo_checks.rows(db, site, item)) if start else []
    tally = todo_checks.tally(prior + [page])
    verdict, words = conclude(kind, tally, page, cfg)
    from .todo_rows import REMOVED
    hidden = sum(1 for r in todo.get("rows") or [] if REMOVED in str(r.get("path") or ""))
    if hidden and verdict != "error":
        words += (f" {hidden:,} address{'es were' if hidden != 1 else ' was'} not asked: an email or an "
                  "address in it was removed, so it is not the address people asked for.")
    log = None
    if verdict != "error":
        log = log_part(cfg, kind, {r["path"] for r in rows_of(todo)}, since_of(db, site, item), now, reader)
        more = log_words(log, kind, cfg, now)
        words = f"{words} {more}".strip()
    page.update(verdict=verdict, words=words, log=log)
    todo_checks.keep(db, site, item, page, sweep["sweep"] if start else None, by_user, by_who, now)
    marked = None
    if verdict in ("fixed", "partly", "not_fixed"):
        from .window import zone
        day = today or now.astimezone(zone(cfg)).date().isoformat()
        marked = todo_marks.mark_checked(db, site, item, verdict == "fixed", day, by_user, now)
    return {**todo_checks.newest(db, site)[item], "marked": marked,
            "page": {"start": page["start"], "checked": page["checked"], "ok": page["ok"]}}


# ------------------------------------------------------------------ after an agent's report

def _start(fn) -> None:
    threading.Thread(target=fn, name="todo-check", daemon=True).start()


RUNNER = _start          # the tests run it at once


def after_report(config: dict, config_path, folder, site: str, item: str, by_who: str,
                 fetch=None) -> None:
    """An AI agent reported a to-do done: run the same check, in the background, so the
    page shows its answer next to the report. Never raises; a limit skips it."""
    import sys

    def work():
        from . import todo_rows
        from .accounts import auditlog
        from .accounts import db as base
        from .accounts.orgs import org_of_site
        from pathlib import Path
        try:
            todo = todo_rows.one(folder, site, item)
            path = base.path_for(config, Path(folder))
            if todo is None or todo.get("kind") not in LIVE or path is None or not Path(path).is_file():
                return                    # nothing to ask (a visits to-do is judged on whole days)
            cfg = site_cfg(config, config_path, site, folder)
            db = base.connect(path)
            try:
                got = check(db, cfg, site, todo, 0, None, by_who, fetch)
                org = org_of_site(db, site)
                auditlog.record(db, org["id"] if org else None, by_who, "todo.checked", item[:120],
                                f"{site} {got['verdict']} {got['ok']}/{got['checked']} of {got['total']}; "
                                "after the agent's report")
                db.commit()
            finally:
                db.close()
        except Refused:
            return                        # a limit: the person can press Check again
        except Exception as why:          # noqa: BLE001 - the report is kept either way
            print(f"todo check after a report: {site} {item} not checked ({type(why).__name__})",
                  file=sys.stderr)
    RUNNER(work)


def site_cfg(config, config_path, site: str, live_dir) -> dict:
    """The site's config, as the dashboard's routes read it."""
    from . import settings_store as store
    from .settings_api import site_config
    return store.apply(site_config(config, config_path, site), site, live_dir)

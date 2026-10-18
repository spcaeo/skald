"""The second count of AI answers (answers/): every stored figure, again,
from the stored raw answers, with its own code.

It shares nothing with answers/match.py or answers/run.py but the name
lists each run froze in its plan (brand terms, competitors, own hosts). It
reads ai_answers.sqlite's `answers` (the text and the cited URLs as the
provider gave them) and `figures`, and works out:

  named          a term is named when, in the lower-cased text, it occurs with
                 no letter, digit or "_" on either side
  brand rank     1 + the competitors named in the text before the brand's
                 first naming (a competitor only cited, not named, is after)
  a host         the URL's text between "//" and the first "/", "?" or "#",
                 without user, port, trailing dot or a leading "www.",
                 lower-cased; a citation with a `domain` (an unresolved
                 redirect) has that domain as its host and no known page
  own            the host is an own host or ends with "." and one
  a page         the URL's text after the host up to "?" or "#", "/" for none,
                 at most 300 characters
  competitors    named in the text, or, written as a domain, a cited host on it
  per assistant  asked = tries stored; answered = tries with an answer;
                 mentioned, cited (at least one own citation), competitor
                 mentions (distinct per answer, summed), the first own
                 citation's position summed and counted

Every answer's stored reading (mentioned, ranks, own pages, competitors) and
every figure must match, and a done run must hold every planned try. In
audit_more.DAILY: run-daily's recounts step rechecks the done runs of the
last RECHECK_DAYS days; answers/run.py calls `recheck_run` as each run
finishes and withholds its figures when it disagrees.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from pathlib import Path

FILE = "ai_answers.sqlite"
RECHECK_DAYS = 35
UNKNOWN = "(page not known)"


def _word(c: str) -> bool:
    return c.isalnum() or c == "_"


def named_at(text: str, term: str) -> int:
    """The first whole-word position of `term` in `text`, or -1."""
    low, t = (text or "").lower(), (term or "").strip().lower()
    if not t:
        return -1
    start = 0
    while True:
        i = low.find(t, start)
        if i < 0:
            return -1
        before = low[i - 1] if i > 0 else " "
        after = low[i + len(t)] if i + len(t) < len(low) else " "
        if not _word(before) and not _word(after):
            return i
        start = i + 1


def _host_part(url: str) -> tuple[str, str]:
    rest = url.split("://", 1)[1] if "://" in url else ""
    cut = len(rest)
    for ch in "/?#":
        k = rest.find(ch)
        if 0 <= k < cut:
            cut = k
    return rest[:cut], rest[cut:]


def _clean_host(host: str) -> str:
    host = host.rsplit("@", 1)[-1].lower()
    if host.startswith("["):
        host = host.split("]", 1)[0] + "]"
    else:
        host = host.split(":", 1)[0]
    host = host.rstrip(".")
    return host[4:] if host.startswith("www.") else host


def host_and_page(c: dict) -> tuple[str, str]:
    if c.get("domain"):
        return _clean_host(str(c["domain"])), UNKNOWN
    hostpart, tail = _host_part(str(c.get("url") or ""))
    for ch in "?#":
        tail = tail.split(ch, 1)[0]
    return _clean_host(hostpart), (tail or "/")[:300]


def _domainish(name: str) -> bool:
    n = name.strip().lower()
    return "." in n and " " not in n and all(p and all(ch.isalnum() or ch == "-" for ch in p)
                                            for p in n.split("."))


def _on(host: str, hosts) -> bool:
    for h in hosts:
        h = _clean_host(h)
        if h and host and (host == h or host.endswith("." + h)):
            return True
    return False


def reread(text: str, citations: list, plan: dict) -> dict:
    brand_pos = [i for i in (named_at(text, b) for b in plan.get("brands") or []) if i >= 0]
    first = min(brand_pos) if brand_pos else -1
    hosts = [host_and_page(c)[0] for c in citations]
    comps, before = [], 0
    for name in plan.get("competitors") or []:
        if name in comps:
            continue
        at = named_at(text, name)
        if at >= 0:
            comps.append(name)
            before += 1 if first >= 0 and at < first else 0
        elif _domainish(name) and any(_on(h, [name]) for h in hosts):
            comps.append(name)
    own, rank = [], None
    for i, c in enumerate(citations):
        host, page = host_and_page(c)
        if _on(host, plan.get("own_hosts") or []):
            rank = rank if rank is not None else i + 1
            if page not in own:
                own.append(page)
    return {"mentioned": first >= 0, "mention_rank": (1 + before) if first >= 0 else None,
            "own_pages": own, "cite_rank": rank, "competitors": comps}


def _json(raw, default):
    try:
        got = json.loads(raw) if raw else default
    except ValueError:
        return default
    return got


def recheck_run(db, run_id: int) -> list[str]:
    """The problems with one done run's stored answers and figures."""
    run = db.execute("SELECT plan, planned, state FROM runs WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        return [f"run {run_id}: not stored"]
    plan = _json(run[0], {})
    problems, counted = [], {}
    rows = db.execute("SELECT id, provider, ok, text, citations, mentioned, mention_rank, "
                      "cite_rank, own_pages, competitors FROM answers WHERE run_id = ?",
                      (run_id,)).fetchall()
    if run[2] == "done" and len(rows) != int(run[1]):
        problems.append(f"run {run_id}: {len(rows)} tries stored, {run[1]} planned")
    for aid, provider, ok, text, cites, mentioned, mrank, crank, pages, comps in rows:
        c = counted.setdefault(provider, [0, 0, 0, 0, 0, 0, 0])
        c[0] += 1
        if not ok:
            continue
        got = reread(text or "", _json(cites, []), plan)
        stored = {"mentioned": bool(mentioned), "mention_rank": mrank, "cite_rank": crank,
                  "own_pages": _json(pages, []), "competitors": _json(comps, [])}
        for k, v in got.items():
            if stored[k] != v:
                problems.append(f"answer {aid} ({provider}): {k} stored {stored[k]!r}, read {v!r}")
        c[1] += 1
        c[2] += 1 if got["mentioned"] else 0
        c[3] += 1 if got["own_pages"] else 0
        c[4] += len(got["competitors"])
        if got["cite_rank"] is not None:
            c[5] += got["cite_rank"]
            c[6] += 1
    names = ("asked", "answered", "mentioned", "cited", "competitor_mentions", "rank_sum", "rank_n")
    stored = {r[0]: r[1:] for r in db.execute(
        "SELECT provider, " + ", ".join(names) + " FROM figures WHERE run_id = ?", (run_id,))}
    for provider in sorted(set(stored) | set(counted)):
        a, b = stored.get(provider), counted.get(provider)
        if a is None or b is None:
            problems.append(f"run {run_id} {provider}: figures {'missing' if a is None else 'without answers'}")
            continue
        for name, x, y in zip(names, a, b):
            if int(x) != int(y):
                problems.append(f"run {run_id} {provider}: {name} stored {x}, recounted {y}")
    return problems


def set_up(ctx) -> bool:
    return (Path(ctx.db_path).parent / FILE).is_file()


def daily(ctx, day) -> list[str] | None:
    """Problems with the done runs of the last RECHECK_DAYS days; None when
    there is no run to recheck."""
    path = Path(ctx.db_path).parent / FILE
    if not path.is_file():
        return None
    db = sqlite3.connect(str(path))
    try:
        first = (day - timedelta(days=RECHECK_DAYS)).isoformat()
        ids = [r[0] for r in db.execute("SELECT id FROM runs WHERE site = ? AND state = 'done' "
                                        "AND day >= ? ORDER BY id", (ctx.site, first))]
        if not ids:
            return None
        problems = []
        for rid in ids:
            problems += recheck_run(db, rid)
        return problems
    finally:
        db.close()

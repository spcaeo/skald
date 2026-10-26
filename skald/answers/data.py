"""ai_answers.json: AI & bots > AI answers (DATA-CONTRACT.md).

  setup       the keys set (never a key), the profiles, the steps still to do
  providers   each assistant: name, model, how the place is passed, the price
              of an answer the estimate uses
  profiles    each listed profile's settings (not deleted), state, estimate,
              last and next run
  trend       per profile, per done run, per assistant: asked, answered,
              mentioned, cited, competitor mentions, average citation rank -
              only figures the second count verified; a run that did not
              match is listed as withheld, with no figures
  last        per profile, its last done and verified run: per question and
              assistant, the tries, how many named the site, the own pages
              cited, the competitors named, and a line from one answer (its
              id opens the full answer)
  competitors per profile, last COMPETITOR_DAYS days: each competitor's
              answers naming it, by assistant
  chain       last CHAIN_DAYS days ending yesterday, per assistant and own page
              cited: answers that cited it (of that assistant's answers);
              that assistant's user-fetcher reads of the page (ai_fetches);
              visits it sent landing on the page (the cube: source "AI
              assistant", that assistant); visits likely sent by any AI answer
              landing on it (ai_likely, inferred); leads whose first visit came
              from an AI answer and landed on it (conversions.sqlite, any
              assistant, tests left out). Five different counts, never added
              together: answers are a sample; the rest are the log's and the
              lead tools' own figures, each already checked twice.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from pathlib import Path

from . import (ASSISTANT, LOCATION, LOCATION_WORDS, NAMES, PROVIDERS, estimate, keys_set,
               model, price)
from . import profiles as profiles_mod
from . import store
from ..visits import ASSISTANTS as LABELS

CHAIN_DAYS = 30
COMPETITOR_DAYS = 90
TREND_DAYS = 180
EXCERPT = 220
SOURCE = "AI assistant"
# The cube's assistant names ("ChatGPT") back to the log's (chatgpt.com).
BY_LABEL = {label: name for name, label in LABELS.items()}


def folder_of(p) -> Path:
    return Path(p.history.path).parent


def norm(path: str) -> str:
    path = str(path or "").split("?", 1)[0].split("#", 1)[0] or "/"
    return path.rstrip("/") or "/"


def excerpt(text: str, terms) -> dict:
    """A line around the first naming of a brand term: {pre, mark, post}."""
    from .match import first_at
    text = " ".join((text or "").split())
    hits = [(at, t) for t in terms for at in [first_at(text, t)] if at is not None]
    if not hits:
        return {"pre": text[:EXCERPT] + ("…" if len(text) > EXCERPT else ""), "mark": "",
                "post": ""}
    at, term = min(hits)
    start = max(0, at - EXCERPT // 2)
    end = at + len(term)
    return {"pre": ("…" if start else "") + text[start:at], "mark": text[at:end],
            "post": text[end:end + EXCERPT // 2] + ("…" if end + EXCERPT // 2 < len(text) else "")}


def _profile_out(p, db, site, config, keyed, lists, tz) -> dict:
    history = store.runs(db, site, p["id"])
    last = next((r for r in reversed(history) if r["state"] == "done"), None)
    open_run = next((r for r in history if r["state"] == "open"), None)
    asks = profiles_mod.resolved(p, lists)
    paused = bool(p["paused"]) and p["paused"][-1][1] is None
    return {"id": p["id"], "version": p["version"],
            **{k: p.get(k) for k in ("name", "city", "region", "country", "lat", "lon", "timezone",
                                      "language", "use_site_questions", "questions", "brands",
                                      "competitors", "providers", "frequency", "repeats", "cap",
                                      "gbp_location_id")},
            "asks": asks, "state": "paused" if paused else "active",
            "estimate": estimate(p, len(asks["questions"]), config, keyed),
            "last_run": last and {"id": last["id"], "day": last["day"],
                                  "finished_at": last["finished_at"]},
            "open_run": open_run and {"id": open_run["id"], "day": open_run["day"],
                                      "planned": open_run["planned"]},
            "next_run": None if paused else profiles_mod.next_run(
                p, history[-1]["day"] if history else None, config, tz),
            "run_requested": bool(p.get("run_requested_at"))}


def _trend(db, site, first) -> list[dict]:
    out = {}
    for f in store.figures(db, site, first):
        run = out.setdefault(f["run_id"], {"run": f["run_id"], "profile": f["profile_id"],
                                           "day": f["day"], "withheld": False, "providers": {}})
        if f["verified"] != 1:
            run["withheld"] = True
            run["problems"] = f["problems"] or "not checked yet"
            run["providers"] = {}
            continue
        if run["withheld"]:
            continue
        run["providers"][f["provider"]] = {
            k: f[k] for k in ("asked", "answered", "mentioned", "cited", "competitor_mentions")}
        run["providers"][f["provider"]]["avg_rank"] = (
            round(f["rank_sum"] / f["rank_n"], 2) if f["rank_n"] else None)
    return list(out.values())


def _last(db, run: dict, brands) -> list[dict]:
    plan = run["plan"]
    rows = store.answers(db, run["id"])
    out = []
    for qi, question in enumerate(plan["questions"]):
        by = {}
        for pr in plan["providers"]:
            mine = [a for a in rows if a["qi"] == qi and a["provider"] == pr]
            ok = [a for a in mine if a["ok"]]
            pages = Counter(pg for a in ok for pg in a["own_pages"])
            comps = Counter(c for a in ok for c in a["competitors"])
            pick = next((a for a in ok if a["mentioned"]), ok[0] if ok else None)
            by[pr] = {"tries": len(mine), "answered": len(ok),
                      "mentioned": sum(1 for a in ok if a["mentioned"]),
                      "pages": [pg for pg, _ in pages.most_common()],
                      "competitors": [c for c, _ in comps.most_common()],
                      "answer_id": pick["id"] if pick else None,
                      "line": excerpt(pick["text"], brands) if pick else None,
                      "failed": [a["error"] for a in mine if not a["ok"]][:3]}
        out.append({"qi": qi, "question": question, "by": by})
    return out


def _competitors(db, site, pid, first) -> list[dict]:
    got: dict[str, Counter] = {}
    total = Counter()
    for provider, comps in db.execute(
            "SELECT a.provider, a.competitors FROM answers a JOIN figures f ON f.run_id = a.run_id "
            "AND f.provider = a.provider WHERE a.site = ? AND a.profile_id = ? AND a.ok = 1 "
            "AND a.day >= ? AND f.verified = 1", (site, pid, first)):
        total[provider] += 1
        for name in store.loads(comps, []):
            got.setdefault(name, Counter())[provider] += 1
    return [{"name": n, "answers": sum(c.values()), "by": dict(c), "of": dict(total)}
            for n, c in sorted(got.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))]


def _chain(p, db, site, first, last) -> list[dict]:
    cited: dict[tuple, int] = Counter()
    answered = Counter()
    for provider, pages in db.execute(
            "SELECT a.provider, a.own_pages FROM answers a JOIN figures f ON f.run_id = a.run_id "
            "AND f.provider = a.provider WHERE a.site = ? AND a.ok = 1 AND a.day BETWEEN ? AND ? "
            "AND f.verified = 1", (site, first.isoformat(), last.isoformat())):
        answered[provider] += 1
        for page in set(store.loads(pages, [])):
            cited[(provider, page)] += 1
    if not cited:
        return []
    blobs = p.history.extras(site, first, last, ("ai_fetches", "cube", "ai_likely"))
    counted = set(p.counted_days())
    reads, sent, likely = Counter(), Counter(), Counter()
    seen = {"ai_fetches": 0, "cube": 0, "ai_likely": 0}
    for day, kinds in blobs.items():
        if day not in counted:
            continue
        for kind in seen:
            seen[kind] += 1 if kinds.get(kind) is not None else 0
        for _, who, path, n in (kinds.get("ai_fetches") or {}).get("rows") or []:
            reads[(who, norm(path))] += int(n)
        for row in (kinds.get("cube") or {}).get("rows") or []:
            if row[2] == SOURCE:            # the cube names an assistant as people know it
                sent[(BY_LABEL.get(row[3], row[3]), norm(row[1]))] += int(row[-1])
        for page, n in ((kinds.get("ai_likely") or {}).get("pages") or {}).items():
            likely[norm(page)] += int(n)
    leads = _leads(p, site, first, last)
    out = []
    for (provider, page), n in sorted(cited.items(), key=lambda kv: (-kv[1], kv[0])):
        who, key = ASSISTANT[provider], norm(page)
        known = page.startswith("/")
        out.append({"provider": provider, "page": page, "cited": n, "of": answered[provider],
                    "read": reads[(who, key)] if known and seen["ai_fetches"] else None,
                    "sent": sent[(who, key)] if known and seen["cube"] else None,
                    "likely": likely[key] if known and seen["ai_likely"] else None,
                    "leads": leads.get(key, 0) if known and leads is not None else None})
    return out


def _leads(p, site, first, last) -> dict | None:
    """{landing page: completed leads whose first touch was an AI answer}; None
    when there is no conversions file (not recorded, never 0)."""
    import sqlite3
    from ..conversions.store import path_for
    path = path_for(p.config, folder_of(p))
    if path is None or not Path(path).is_file():
        return None
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = db.execute("SELECT landing, at FROM conversions WHERE site = ? AND stage = "
                              "'completed' AND first_source = ? AND COALESCE(test, 0) = 0",
                              (site, SOURCE)).fetchall()
        finally:
            db.close()
    except sqlite3.Error:
        return None
    out = Counter()
    for landing, at in rows:
        if first.isoformat() <= str(at)[:10] <= last.isoformat():
            out[norm(landing)] += 1
    return dict(out)


def setup_steps(keyed: dict, lists: dict, listed: list, done_runs: int) -> list[dict]:
    return [
        {"id": "key", "done": any(keyed.values()), "words": "An install admin adds an API key for "
         "at least one assistant: Settings > AI answers > API keys."},
        {"id": "lists", "done": bool(lists["brands"]) or any(x.get("brands") for x in listed),
         "words": "Write the site's brand terms, "
         "competitors and questions: Settings > AI answers."},
        {"id": "profile", "done": bool(listed), "words": "Make a tracking profile: a place, a "
         "language, the assistants to ask, how often, and a daily cap."},
        {"id": "run", "done": done_runs > 0, "words": "Wait for the first run (from 06:00 in the "
         "site's time zone, or Run now). The figures appear when its answers are all in."},
    ]


def build(p) -> dict:
    site, tz = p.site, p.tz
    keyed = keys_set(p.config, p.live_dir)
    providers = [{"id": x, "name": NAMES[x], "model": model(p.config, x),
                  "location": LOCATION[x], "how": LOCATION_WORDS[x], "price": price(p.config, x),
                  "key": keyed[x], "assistant": ASSISTANT[x]} for x in PROVIDERS]
    path = store.path_for(folder_of(p))
    base = {"providers": providers, "chain_days": CHAIN_DAYS,
            "competitor_days": COMPETITOR_DAYS}
    if not path.is_file():
        lists = {"questions": [], "brands": [], "competitors": [], "keep_days": None}
        return {**base, "state": "not set up", "setup": {
            "keys": keyed, "steps": setup_steps(keyed, lists, [], 0)}, "lists": lists,
            "profiles": [], "trend": [], "last": {}, "competitors": {}, "chain": []}
    db = store.connect(path)
    try:
        lists = store.lists(db, site)
        listed = profiles_mod.listed(db, site)
        profs = [_profile_out(x, db, site, p.config, keyed, lists, tz) for x in listed]
        first = (p.today - timedelta(days=TREND_DAYS)).isoformat()
        trend = _trend(db, site, first)
        verified = {t["run"] for t in trend if not t["withheld"]}
        last = {}
        for x in listed:
            done = [r for r in store.runs(db, site, x["id"]) if r["state"] == "done"
                    and r["id"] in verified]
            if done:
                run = done[-1]
                last[str(x["id"])] = {"run": run["id"], "day": run["day"],
                                      "providers": run["plan"]["providers"],
                                      "repeats": run["plan"]["repeats"],
                                      "questions": _last(db, run, run["plan"]["brands"])}
        comp_first = (p.today - timedelta(days=COMPETITOR_DAYS)).isoformat()
        competitors = {str(x["id"]): _competitors(db, site, x["id"], comp_first) for x in listed}
        chain = _chain(p, db, site, p.anchor - timedelta(days=CHAIN_DAYS - 1), p.anchor)
        done_runs = db.execute("SELECT COUNT(*) FROM runs WHERE site = ? AND state = 'done'",
                               (site,)).fetchone()[0]
    finally:
        db.close()
    steps = setup_steps(keyed, lists, listed, done_runs)
    ready = all(s["done"] for s in steps[:3]) or done_runs > 0
    return {**base, "state": "ok" if ready else "not set up",
            "setup": {"keys": keyed, "steps": steps}, "lists": lists, "profiles": profs,
            "trend": trend, "last": last, "competitors": competitors, "chain": chain,
            "chain_first": (p.anchor - timedelta(days=CHAIN_DAYS - 1)).isoformat(),
            "chain_last": p.anchor.isoformat()}

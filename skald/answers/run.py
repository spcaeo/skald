"""The run: `skald ai-answers [--due] [--profile ID]`, for each site in turn.

For every profile of the site that is due (its frequency, from RUN_HOUR in
the site's zone) or asked to run now, and every open run (one the daily cap
stopped): ask each question of each chosen assistant `repeats` times, one
thread per assistant, and store every answer (store.put_answer) with what
match.py read in it. Before each ask the profile's spending today (the
estimated cost of the answers asked today) plus the ask's must stay under
its cap; past it the run stays open and goes on the next day. An assistant
without a key is left out of the plan, and said.

A run with every answer in is done: its figures are written per assistant
(`figures`) and recounted at once by audit_ai_answers.py; the verdict is
stored with them (verified 1, or 0 with the problems: withheld). Old runs
go after the site's keep_days (400).

One run at a time per install (a lock file beside the history); a run the
lock refuses exits 0. runs.json: "ai-answers" ok, or failed when every ask
failed. Keys are never printed.
"""
from __future__ import annotations

import fcntl
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import (ASSISTANT, KEEP_DAYS, LOCATION, PROVIDERS, key as key_of, model as model_of,
               price as price_of)
from . import match, profiles, store
from .providers import Failed, ask

LOCK = ".ai_answers.lock"


def figures(rows: list[dict]) -> dict:
    """{provider: figures} of one run's answers (the main road)."""
    out = {}
    for a in rows:
        f = out.setdefault(a["provider"], {"asked": 0, "answered": 0, "mentioned": 0, "cited": 0,
                                           "competitor_mentions": 0, "rank_sum": 0, "rank_n": 0})
        f["asked"] += 1
        if not a["ok"]:
            continue
        f["answered"] += 1
        f["mentioned"] += 1 if a["mentioned"] else 0
        f["cited"] += 1 if a["own_pages"] else 0
        f["competitor_mentions"] += len(a["competitors"])
        if a["cite_rank"] is not None:
            f["rank_sum"] += a["cite_rank"]
            f["rank_n"] += 1
    return out


def finish(db, site: str, run: dict, now: datetime) -> list[str]:
    """Write a done run's figures and the second count's verdict. Problems."""
    from .. import audit_ai_answers
    rows = store.answers(db, run["id"], full=False)
    got = figures(rows)
    at = store.now_iso(now)
    with db:
        db.execute("UPDATE runs SET state = 'done', finished_at = ? WHERE id = ?", (at, run["id"]))
        for provider, f in got.items():
            db.execute("INSERT OR REPLACE INTO figures (run_id, provider, site, profile_id, day, "
                       "asked, answered, mentioned, cited, competitor_mentions, rank_sum, rank_n, "
                       "written_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (run["id"], provider, site, run["profile_id"], run["day"], f["asked"],
                        f["answered"], f["mentioned"], f["cited"], f["competitor_mentions"],
                        f["rank_sum"], f["rank_n"], at))
    problems = audit_ai_answers.recheck_run(db, run["id"])
    with db:
        db.execute("UPDATE figures SET verified = ?, problems = ? WHERE run_id = ?",
                   (0 if problems else 1, "; ".join(problems)[:2000] or None, run["id"]))
    return problems


def plan_for(p: dict, lists: dict, config: dict, keyed: dict) -> dict:
    got = profiles.resolved(p, lists)
    return {"questions": got["questions"], "brands": got["brands"],
            "competitors": got["competitors"],
            "own_hosts": match.own_hosts(config, got["brands"]),
            "providers": [x for x in p["providers"] if keyed.get(x)],
            "repeats": int(p["repeats"]), "cap": float(p["cap"]),
            "where": {k: p.get(k) for k in ("city", "region", "country", "lat", "lon",
                                             "timezone", "language")},
            "models": {x: model_of(config, x) for x in p["providers"]},
            "prices": {x: price_of(config, x) for x in p["providers"]}}


def _missing(db, run: dict) -> dict:
    """{provider: [(qi, try), ...]} still to ask."""
    have = {(r["provider"], r["qi"], r["try"]) for r in db.execute(
        "SELECT provider, qi, try FROM answers WHERE run_id = ?", (run["id"],))}
    plan = run["plan"]
    out = {}
    for provider in plan["providers"]:
        todo = [(qi, n) for qi in range(len(plan["questions"]))
                for n in range(1, plan["repeats"] + 1) if (provider, qi, n) not in have]
        if todo:
            out[provider] = todo
    return out


class Asker:
    """One run's asks, a thread per provider, under the cap."""

    def __init__(self, folder: Path, site: str, run: dict, config: dict, live_dir, today,
                 transport=None, sleep=None, out=print, err=print, clock=None):
        self.folder, self.site, self.run, self.config = folder, site, run, config
        self.live_dir, self.today, self.transport = live_dir, today, transport
        self.sleep, self.out, self.err = sleep, out, err
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.lock = threading.Lock()
        self.capped = False
        self.tally = {"asked": 0, "failed": 0}

    def provider(self, provider: str, todo: list) -> None:
        plan = self.run["plan"]
        secret = key_of(self.config, provider, self.live_dir)
        cost = float(plan["prices"].get(provider, 0))
        db = store.connect(store.path_for(self.folder))
        try:
            for qi, n in todo:
                with self.lock:
                    if store.spent(db, self.site, self.run["profile_id"], self.today) + cost \
                            > plan["cap"] + 1e-9:
                        self.capped = True
                        return
                    # Book the cost before asking, so the other threads see it.
                    store.put_answer(db, self.run, self.site, provider,
                                     plan["models"][provider], qi, n, plan["questions"][qi], None,
                                     "asking", cost, LOCATION[provider], None, self.today,
                                     self.clock())
                question = plan["questions"][qi]
                try:
                    if not secret:
                        raise Failed("no API key")
                    extra = {"sleep": self.sleep} if self.sleep else {}
                    got = ask(provider, secret, plan["models"][provider], question,
                              plan["where"], self.transport, **extra)
                    read = match.analyse(got["text"], got["citations"], plan["brands"],
                                         plan["competitors"], plan["own_hosts"])
                    error = None
                except (Failed, ValueError, KeyError, TypeError, OSError) as why:
                    words = str(why) if isinstance(why, Failed) else f"{type(why).__name__}: {why}"
                    got, read, error = None, None, words.replace(secret or "\0", "***")[:300]
                store.put_answer(db, self.run, self.site, provider, plan["models"][provider],
                                 qi, n, question, got, error, cost, LOCATION[provider], read,
                                 self.today, self.clock())
                with self.lock:
                    self.tally["asked"] += 1
                    self.tally["failed"] += 0 if got else 1
                if error:
                    self.err(f"ai-answers {self.site} profile {self.run['profile_id']} "
                             f"{provider} q{qi + 1} try {n}: failed ({error})")
        finally:
            db.close()

    def go(self, todo: dict) -> None:
        with ThreadPoolExecutor(max_workers=max(1, len(todo))) as pool:
            for f in [pool.submit(self.provider, p, items) for p, items in todo.items()]:
                f.result()


def _lock(folder: Path):
    fd = os.open(Path(folder) / LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


def run_site(folder: Path, site: str, config: dict, tz, now: datetime, live_dir=None,
             due_only: bool = True, only=None, transport=None, sleep=None, out=print,
             err=print) -> dict:
    """Ask what is due for one site. {"runs", "asked", "failed", "capped", "done"}."""
    from . import keys_set
    tally = {"runs": 0, "asked": 0, "failed": 0, "capped": 0, "done": 0, "withheld": 0}
    local = now.astimezone(tz)
    today = local.date()
    keyed = keys_set(config, live_dir)
    db = store.connect(store.path_for(folder))
    try:
        lists = store.lists(db, site)
        keep = int(lists.get("keep_days") or KEEP_DAYS)
        store.prune(db, site, today - timedelta(days=keep))
        for p in profiles.listed(db, site):
            if only is not None and p["id"] != int(only):
                continue
            history = store.runs(db, site, p["id"])
            open_runs = [r for r in history if r["state"] == "open"]
            last_day = history[-1]["day"] if history else None
            why = "requested" if only is not None and not due_only else \
                profiles.due(p, last_day, local, config)
            if not open_runs and why:
                plan = plan_for(p, lists, config, keyed)
                skipped = [x for x in p["providers"] if x not in plan["providers"]]
                if skipped:
                    err(f"ai-answers {site} profile {p['id']}: no API key for "
                        + ", ".join(skipped) + "; left out")
                if not plan["questions"] or not plan["providers"]:
                    err(f"ai-answers {site} profile {p['id']}: nothing to ask "
                        f"({'no questions' if not plan['questions'] else 'no assistant with a key'})")
                else:
                    rid = store.start_run(db, site, p, today, why, plan, now)
                    open_runs = [r for r in store.runs(db, site, p["id"]) if r["id"] == rid]
                with db:
                    db.execute("UPDATE profiles SET run_requested_at = NULL WHERE id = ?", (p["id"],))
            if p.get("removed_at") or profiles.is_paused(p, now.astimezone(timezone.utc)):
                continue
            for run in open_runs:
                tally["runs"] += 1
                asker = Asker(folder, site, run, config, live_dir, today, transport, sleep, out, err)
                todo = _missing(db, run)
                asker.go(todo)
                tally["asked"] += asker.tally["asked"]
                tally["failed"] += asker.tally["failed"]
                if _missing(db, run):
                    tally["capped"] += 1
                    out(f"ai-answers {site} profile {p['id']}: the daily cap of "
                        f"${run['plan']['cap']:.2f} is reached; the run goes on tomorrow")
                    continue
                problems = finish(db, site, run, now)
                tally["done"] += 1
                if problems:
                    tally["withheld"] += 1
                    err(f"ai-answers {site} run {run['id']}: THE RECOUNT DOES NOT MATCH; withheld: "
                        + "; ".join(problems[:5]))
    finally:
        db.close()
    return tally


def run(ctx, due_only: bool = True, only=None, transport=None, sleep=None) -> int:
    from .. import runs
    folder = Path(ctx.db_path).parent
    fd = _lock(folder)
    if fd is None:
        ctx.out("ai-answers: another run is going; nothing done")
        return 0
    try:
        tally = run_site(folder, ctx.site, ctx.config, ctx.tz, ctx.now, ctx.live_dir, due_only,
                         only, transport, sleep, ctx.out, ctx.err)
    except Exception as why:            # noqa: BLE001 - noted, never a crash loop
        ctx.err(f"ai-answers: {type(why).__name__}: {why}")
        runs.record(ctx.live_dir, "ai-answers", 1)
        return 1
    finally:
        os.close(fd)
    if tally["runs"]:
        ctx.out("ai-answers " + ctx.site + ": " + ", ".join(f"{k} {v}" for k, v in tally.items()))
    failed = tally["asked"] and tally["failed"] == tally["asked"]
    runs.record(ctx.live_dir, "ai-answers", 1 if failed or tally["withheld"] else 0)
    return 1 if tally["withheld"] else 0


def cmd_ai_answers(ctx) -> int:
    if ctx.args.show:
        return show(ctx, ctx.args.show)
    return run(ctx, due_only=not ctx.args.now, only=ctx.args.profile)


def show(ctx, answer_id) -> int:
    """One stored answer in full: the question as sent, the text, the cited URLs."""
    folder = Path(ctx.db_path).parent
    with store.opened(folder) as db:
        r = db.execute("SELECT * FROM answers WHERE site = ? AND id = ?",
                       (ctx.site, int(answer_id))).fetchone()
        if r is None:
            ctx.err("no such answer for this site")
            return 1
        a = store.answer_row(r)
    ctx.out(f"{a['provider']} ({a['model']}), {a['asked_at']}, try {a['try']}: {a['question']}")
    ctx.out(a["text"] or f"(no answer: {a['error']})")
    for i, c in enumerate(a["citations"], 1):
        ctx.out(f"  [{i}] {c['url']}")
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("ai-answers", help="ask the AI assistants the tracking profiles' questions "
                       "(AI answers); --due asks only what is due")
    p.add_argument("--due", action="store_true", help="only profiles whose time has come (default)")
    p.add_argument("--now", action="store_true", help="with --profile: run it now, due or not")
    p.add_argument("--profile", help="one profile's id")
    p.add_argument("--show", help="print one stored answer in full, by its id")
    p.set_defaults(run=cmd_ai_answers)


assert set(ASSISTANT) == set(PROVIDERS)

"""ai_answers.sqlite beside the history: lists, profiles, runs, answers,
figures. Rows are filed by site.

  lists             a site's own questions, brand terms and competitors (what
                    a profile uses when it has none of its own), and how many
                    days its answers are kept (keep_days)
  profiles          a tracking profile: its settings (body, JSON), its version,
                    its pauses ([[from, to|null], ...]), removed_at when deleted.
                    A profile is never erased: deleted, it leaves the lists,
                    while its runs and answers stay until keep_days passes
  profile_versions  every saved version of every profile, with who and when
  runs              one run of one profile: the version, the plan it asks (the
                    questions, assistants, tries, place, brand terms,
                    competitors and own hosts, frozen when it starts), open
                    until every answer is in (a run the daily cap stops goes
                    on the next day), then done
  answers           one try of one question of one assistant: the text
                    (trimmed), the cited URLs, the estimated cost, and what
                    match.py read from it; a failed try keeps its reason
  figures           per done run and assistant: asked, answered, mentioned,
                    cited, competitor mentions, the citation rank's sum and
                    count, and the second count's verdict (verified 1 or 0,
                    with the problems); data.py shows only verified figures
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

FILE = "ai_answers.sqlite"
SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lists (
  site TEXT PRIMARY KEY, questions TEXT NOT NULL DEFAULT '[]', brands TEXT NOT NULL DEFAULT '[]',
  competitors TEXT NOT NULL DEFAULT '[]', keep_days INTEGER, updated_at TEXT, updated_by TEXT);
CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
  paused TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, created_by TEXT,
  updated_at TEXT NOT NULL, updated_by TEXT, removed_at TEXT, removed_by TEXT,
  run_requested_at TEXT, copied_from INTEGER);
CREATE INDEX IF NOT EXISTS profiles_site ON profiles (site);
CREATE TABLE IF NOT EXISTS profile_versions (
  profile_id INTEGER NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
  saved_at TEXT NOT NULL, saved_by TEXT, PRIMARY KEY (profile_id, version));
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, profile_id INTEGER NOT NULL,
  version INTEGER NOT NULL, day TEXT NOT NULL, started_at TEXT NOT NULL, why TEXT NOT NULL,
  plan TEXT NOT NULL, planned INTEGER NOT NULL, state TEXT NOT NULL CHECK (state IN ('open', 'done')),
  finished_at TEXT);
CREATE INDEX IF NOT EXISTS runs_profile ON runs (site, profile_id, day);
CREATE TABLE IF NOT EXISTS answers (
  id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, site TEXT NOT NULL, profile_id INTEGER NOT NULL,
  provider TEXT NOT NULL, model TEXT NOT NULL, qi INTEGER NOT NULL, try INTEGER NOT NULL,
  question TEXT NOT NULL, sent TEXT, asked_at TEXT NOT NULL, day TEXT NOT NULL,
  ok INTEGER NOT NULL, error TEXT, text TEXT, citations TEXT NOT NULL DEFAULT '[]',
  cost REAL NOT NULL, location TEXT NOT NULL, mentioned INTEGER, mention_rank INTEGER,
  cite_rank INTEGER, own_pages TEXT, competitors TEXT,
  UNIQUE (run_id, provider, qi, try));
CREATE INDEX IF NOT EXISTS answers_day ON answers (site, profile_id, day);
CREATE TABLE IF NOT EXISTS figures (
  run_id INTEGER NOT NULL, provider TEXT NOT NULL, site TEXT NOT NULL, profile_id INTEGER NOT NULL,
  day TEXT NOT NULL, asked INTEGER NOT NULL, answered INTEGER NOT NULL, mentioned INTEGER NOT NULL,
  cited INTEGER NOT NULL, competitor_mentions INTEGER NOT NULL, rank_sum INTEGER NOT NULL,
  rank_n INTEGER NOT NULL, written_at TEXT NOT NULL, verified INTEGER, problems TEXT,
  PRIMARY KEY (run_id, provider));
"""


def path_for(folder) -> Path:
    return Path(folder) / FILE


def connect(path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=30)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    with db:
        db.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('schema', ?)",
                   (str(SCHEMA_VERSION),))
    return db


@contextmanager
def opened(folder):
    db = connect(path_for(folder))
    try:
        yield db
    finally:
        db.close()


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")


def loads(raw, default):
    try:
        got = json.loads(raw) if raw else default
    except (TypeError, ValueError):
        return default
    return got if isinstance(got, type(default)) else default


# ----------------------------------------------------------------- lists

def lists(db, site: str) -> dict:
    row = db.execute("SELECT * FROM lists WHERE site = ?", (site,)).fetchone()
    if row is None:
        return {"questions": [], "brands": [], "competitors": [], "keep_days": None,
                "updated_at": None}
    return {"questions": loads(row["questions"], []), "brands": loads(row["brands"], []),
            "competitors": loads(row["competitors"], []), "keep_days": row["keep_days"],
            "updated_at": row["updated_at"]}


def save_lists(db, site: str, got: dict, who: str, now: datetime | None = None) -> None:
    with db:
        db.execute(
            "INSERT INTO lists (site, questions, brands, competitors, keep_days, updated_at, "
            "updated_by) VALUES (?,?,?,?,?,?,?) ON CONFLICT(site) DO UPDATE SET "
            "questions = excluded.questions, brands = excluded.brands, competitors = "
            "excluded.competitors, keep_days = excluded.keep_days, updated_at = "
            "excluded.updated_at, updated_by = excluded.updated_by",
            (site, json.dumps(got["questions"]), json.dumps(got["brands"]),
             json.dumps(got["competitors"]), got.get("keep_days"), now_iso(now), who))


# ------------------------------------------------------------------ runs

def run_row(r) -> dict:
    return {"id": r["id"], "profile_id": r["profile_id"], "version": r["version"],
            "day": r["day"], "started_at": r["started_at"], "why": r["why"],
            "plan": loads(r["plan"], {}), "planned": r["planned"], "state": r["state"],
            "finished_at": r["finished_at"]}


def runs(db, site: str, profile_id: int | None = None, first: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM runs WHERE site = ?", [site]
    if profile_id is not None:
        sql += " AND profile_id = ?"
        args.append(profile_id)
    if first is not None:
        sql += " AND day >= ?"
        args.append(first)
    return [run_row(r) for r in db.execute(sql + " ORDER BY started_at, id", args)]


def start_run(db, site: str, profile: dict, day: date, why: str, plan: dict,
              now: datetime | None = None) -> int:
    planned = len(plan["questions"]) * len(plan["providers"]) * int(plan["repeats"])
    with db:
        cur = db.execute(
            "INSERT INTO runs (site, profile_id, version, day, started_at, why, plan, planned, state) "
            "VALUES (?,?,?,?,?,?,?,?, 'open')",
            (site, profile["id"], profile["version"], day.isoformat(), now_iso(now), why,
             json.dumps(plan, sort_keys=True), planned))
    return int(cur.lastrowid)


def answer_row(r, full: bool = True) -> dict:
    out = {"id": r["id"], "run_id": r["run_id"], "profile_id": r["profile_id"],
           "provider": r["provider"], "model": r["model"], "qi": r["qi"], "try": r["try"],
           "question": r["question"], "asked_at": r["asked_at"], "day": r["day"],
           "ok": bool(r["ok"]), "error": r["error"], "citations": loads(r["citations"], []),
           "cost": r["cost"], "location": r["location"],
           "mentioned": None if r["mentioned"] is None else bool(r["mentioned"]),
           "mention_rank": r["mention_rank"], "cite_rank": r["cite_rank"],
           "own_pages": loads(r["own_pages"], []), "competitors": loads(r["competitors"], [])}
    if full:
        out.update(text=r["text"], sent=r["sent"])
    return out


def answers(db, run_id: int, full: bool = True) -> list[dict]:
    return [answer_row(r, full) for r in db.execute(
        "SELECT * FROM answers WHERE run_id = ? ORDER BY provider, qi, try", (run_id,))]


def put_answer(db, run: dict, site: str, provider: str, model: str, qi: int, n: int,
               question: str, got: dict | None, error: str | None, cost: float,
               location: str, read: dict | None, day: date, now: datetime | None = None) -> None:
    with db:
        db.execute(
            "INSERT OR REPLACE INTO answers (run_id, site, profile_id, provider, model, qi, try, "
            "question, sent, asked_at, day, ok, error, text, citations, cost, location, "
            "mentioned, mention_rank, cite_rank, own_pages, competitors) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run["id"], site, run["profile_id"], provider, model, qi, n, question,
             (got or {}).get("sent"), now_iso(now), day.isoformat(), 1 if got else 0,
             error, (got or {}).get("text"), json.dumps((got or {}).get("citations") or []),
             float(cost), location,
             None if read is None else int(read["mentioned"]),
             None if read is None else read["mention_rank"],
             None if read is None else read["cite_rank"],
             None if read is None else json.dumps(read["own_pages"]),
             None if read is None else json.dumps(read["competitors"])))


def spent(db, site: str, profile_id: int, day: date) -> float:
    got = db.execute("SELECT COALESCE(SUM(cost), 0) FROM answers WHERE site = ? AND "
                     "profile_id = ? AND day = ?", (site, profile_id, day.isoformat())).fetchone()
    return float(got[0] or 0)


def figures(db, site: str, first: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM figures WHERE site = ?", [site]
    if first:
        sql += " AND day >= ?"
        args.append(first)
    return [dict(r) for r in db.execute(sql + " ORDER BY day, run_id, provider", args)]


def prune(db, site: str, keep_from: date) -> int:
    """Answers, figures and runs of runs started before `keep_from`."""
    gone = [r[0] for r in db.execute("SELECT id FROM runs WHERE site = ? AND day < ? AND "
                                     "state = 'done'", (site, keep_from.isoformat()))]
    if not gone:
        return 0
    marks = ",".join("?" * len(gone))
    with db:
        n = db.execute(f"DELETE FROM answers WHERE run_id IN ({marks})", gone).rowcount
        db.execute(f"DELETE FROM figures WHERE run_id IN ({marks})", gone)
        db.execute(f"DELETE FROM runs WHERE id IN ({marks})", gone)
    return n

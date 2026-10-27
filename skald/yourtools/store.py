"""The raw-answer store: `yourtools.sqlite` beside the history, never inside it,
so nothing a tool says can reach the log's tables or counts.

  answers  one row per site, tool, report and period: the tool's answer exactly
           as it came (`body`, its JSON text, and its sha256), what was asked
           (`request`, never a key), when, and what the tool said about its own
           answer (`flags`: sampled, thresholded...). A newer answer for the same
           window replaces the older one with its figures; other windows stay.
  figures  what the screens show, each read from one answer: its name and value
           (NULL when the tool did not give it, never 0), its row (`dim`), and
           where in the answer each was read (`src`, `name_src`, `dim_src`: JSON
           pointers), for recount.py to read again by its own code.

`latest(db, site, tool)` gives each report's newest answer with its figures.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

FILE = "yourtools.sqlite"
SCHEMA = """
CREATE TABLE IF NOT EXISTS answers (
  id INTEGER PRIMARY KEY,
  site TEXT NOT NULL, tool TEXT NOT NULL, report TEXT NOT NULL, period TEXT NOT NULL,
  start TEXT, end TEXT, fetched_at TEXT NOT NULL,
  request TEXT NOT NULL, body TEXT NOT NULL, sha256 TEXT NOT NULL,
  flags TEXT NOT NULL DEFAULT '{}', note TEXT NOT NULL DEFAULT '',
  UNIQUE (site, tool, report, period));
CREATE TABLE IF NOT EXISTS figures (
  answer_id INTEGER NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
  name TEXT NOT NULL, label TEXT NOT NULL DEFAULT '', dim TEXT, value,
  src TEXT, name_src TEXT, dim_src TEXT, rank INTEGER);
CREATE INDEX IF NOT EXISTS figures_answer ON figures (answer_id);
CREATE INDEX IF NOT EXISTS answers_site ON answers (site, tool, report, end);
"""


def path_for(history_folder) -> Path:
    return Path(history_folder) / FILE


def connect(history_folder) -> sqlite3.Connection:
    """The store, made when missing."""
    where = path_for(history_folder)
    where.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(where), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    return db


def reader(history_folder) -> sqlite3.Connection | None:
    """The store read-only, or None when it was never made."""
    where = path_for(history_folder)
    if not where.is_file():
        return None
    db = sqlite3.connect(f"file:{where}?mode=ro", uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    return db


def body_text(body: dict) -> str:
    """The answer as kept: the tool's JSON, keys sorted, nothing dropped."""
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def keep(db, site: str, tool: str, answer, figures, fetched_at: str) -> int:
    """Store one answer and its figures (replacing the same window's); its id.
    The caller commits."""
    body = body_text(answer.body)
    db.execute("DELETE FROM answers WHERE site = ? AND tool = ? AND report = ? AND period = ?",
               (site, tool, answer.report, answer.period))
    cur = db.execute(
        "INSERT INTO answers (site, tool, report, period, start, end, fetched_at, request, "
        "body, sha256, flags, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (site, tool, answer.report, answer.period, answer.start, answer.end, fetched_at,
         json.dumps(answer.request, sort_keys=True), body,
         hashlib.sha256(body.encode("utf-8")).hexdigest(),
         json.dumps(answer.flags or {}, sort_keys=True), answer.note or ""))
    aid = cur.lastrowid
    db.executemany(
        "INSERT INTO figures (answer_id, name, label, dim, value, src, name_src, dim_src, rank) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(aid, f.name, f.label or "", f.dim, f.value, f.src, f.name_src, f.dim_src, f.rank)
         for f in figures])
    return aid


def latest(db, site: str, tool: str) -> list[dict]:
    """Each report's newest answer (the latest window, then the latest fetch),
    with its figures in the tool's order: [{report, period, start, end,
    fetched_at, flags, note, sha256, id, figures: [...]}]."""
    rows = db.execute(
        "SELECT * FROM answers a WHERE site = ? AND tool = ? AND id = ("
        " SELECT b.id FROM answers b WHERE b.site = a.site AND b.tool = a.tool"
        " AND b.report = a.report ORDER BY COALESCE(b.end, '') DESC, b.fetched_at DESC,"
        " b.id DESC LIMIT 1) ORDER BY report", (site, tool)).fetchall()
    out = []
    for r in rows:
        figs = db.execute("SELECT name, label, dim, value, src, name_src, dim_src, rank "
                          "FROM figures WHERE answer_id = ? ORDER BY rank IS NOT NULL, rank, "
                          "rowid", (r["id"],)).fetchall()
        out.append({"id": r["id"], "report": r["report"], "period": r["period"],
                    "start": r["start"], "end": r["end"], "fetched_at": r["fetched_at"],
                    "flags": json.loads(r["flags"] or "{}"), "note": r["note"],
                    "sha256": r["sha256"], "figures": [dict(f) for f in figs]})
    return out


def body(db, answer_id: int) -> dict | None:
    """One stored answer's body, parsed; None when it is gone or not JSON."""
    row = db.execute("SELECT body FROM answers WHERE id = ?", (answer_id,)).fetchone()
    try:
        got = json.loads(row[0]) if row else None
    except ValueError:
        return None
    return got if isinstance(got, dict) else None


def keep_only(db, site: str, tool: str, ids) -> int:
    """Remove the tool's other answers and their figures (a `latest_only` tool:
    an older answer may name a person the newer one no longer does). The
    caller commits. Rows removed."""
    keep = [int(i) for i in ids]
    marks = ",".join("?" for _ in keep) or "NULL"
    gone = [r[0] for r in db.execute(f"SELECT id FROM answers WHERE site = ? AND tool = ? AND "
                                     f"id NOT IN ({marks})", (site, tool, *keep))]
    for aid in gone:
        db.execute("DELETE FROM figures WHERE answer_id = ?", (aid,))
        db.execute("DELETE FROM answers WHERE id = ?", (aid,))
    return len(gone)


def answer_ids(db, site: str, tool: str) -> list[int]:
    return [r[0] for r in db.execute("SELECT id FROM answers WHERE site = ? AND tool = ? "
                                     "ORDER BY id", (site, tool))]

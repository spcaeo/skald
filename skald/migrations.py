"""Database upgrades made explicit: what each file is at, what the code
expects, what will change, and a record of every change made.

Skald keeps three SQLite files beside each other: the history
(history.sqlite, store.py), the accounts (accounts.sqlite, accounts/db.py)
and the conversions (conversions.sqlite, conversions/store.py). Each one's
own code knows its schema version (SCHEMA_VERSION) and how to bring an older
file up to it (store.ADDED_COLUMNS / ADDED_TABLES, accounts and conversions
UPGRADES), and each one refuses a file newer than it understands. This
module only reads those - it never repeats a schema step - so a change to a
schema stays in its own file:

    skald migrate --check   each file, its version, the code's, the steps pending
    skald migrate           a restore-tested copy of each file first, then each
                            file opened by its own code (which upgrades it),
                            then one line per file in migrations.json

The opening is what upgrades, as it always has: any command would do it.
`migrate` does it on purpose, after a copy, and writes it down. A file newer
than the code is never opened: the command says which, and stops.

skald sends `migrate` here (main) before the rest of the command line is
read, because every other command opens the accounts file as it starts (the
settings in it are laid over config.yml) - and so upgrades it. `migrate
--check` must only look, also when `skald upgrade --dry-run` runs a newer
release's copy of it against this install's files.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

RECORD = "migrations.json"
KEEP = 200
NAMES = ("history", "accounts", "conversions")


# ------------------------------------------------------------ the files

def _module(name: str):
    if name == "history":
        from . import store
        return store
    if name == "accounts":
        from .accounts import db
        return db
    from .conversions import store
    return store


def code_version(name: str) -> int:
    """The schema this code writes, read from the database's own module."""
    return int(_module(name).SCHEMA_VERSION)


def paths(config: dict, history: Path) -> list[tuple[str, Path]]:
    """(name, file) for the three databases of this install, present or not."""
    from .accounts import db as accounts_db
    from .conversions import store as conversions_store
    history = Path(history)
    found = [("history", history),
             ("accounts", accounts_db.path_for(config, history.parent)),
             ("conversions", conversions_store.path_for(config, history.parent))]
    return [(name, Path(p)) for name, p in found if p is not None]


def file_version(path: Path) -> int | None:
    """The schema_version a file says, read-only; None when it has none yet.
    sqlite3.DatabaseError when it is not a database."""
    db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    try:
        have = db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                          "AND name = 'meta'").fetchone()
        if not have:
            return None
        row = db.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        return int(row[0]) if row else None
    finally:
        db.close()


def _short(sql: str, limit: int = 90) -> str:
    text = " ".join(str(sql).split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _history_steps(found: int, code: int) -> list[str]:
    """store.py's own lists: (version, table, column, ...) and (version, name, sql);
    any other ADDED_* list of the same shape is read too."""
    module = _module("history")
    steps: dict[int, list[str]] = {}
    for attr in sorted(a for a in dir(module) if a.startswith("ADDED_")):
        what = attr[len("ADDED_"):].lower().rstrip("s") or "item"
        for item in getattr(module, attr) or []:
            if not (isinstance(item, tuple) and item and isinstance(item[0], int)):
                continue
            if found < item[0] <= code:
                label = ".".join(str(x) for x in item[1:3]) if what == "column" \
                    else str(item[1])
                steps.setdefault(item[0], []).append(f"add {what} {label}")
    return [f"v{v}: {s}" for v in range(found + 1, code + 1)
            for s in steps.get(v) or ["new version stamp"]]


def _upgrade_steps(name: str, found: int, code: int) -> list[str]:
    ups = getattr(_module(name), "UPGRADES", {}) or {}
    return [f"v{v}: {_short(sql)}" for v in range(found + 1, code + 1)
            for sql in (ups.get(v) or ["new version stamp"])]


def steps(name: str, found: int | None, code: int | None = None) -> list[str]:
    """What opening the file will change, from the database's own upgrade code."""
    code = code_version(name) if code is None else code
    if found is None or found >= code:
        return []
    return _history_steps(found, code) if name == "history" else \
        _upgrade_steps(name, found, code)


def inspect(config: dict, history: Path) -> list[dict]:
    """One row per database: name, path, state (absent, current, pending,
    newer, unreadable), found, code, steps."""
    out = []
    for name, path in paths(config, history):
        code = code_version(name)
        row = {"name": name, "path": str(path), "code": code, "found": None, "steps": []}
        if not path.exists():
            out.append({**row, "state": "absent"})
            continue
        try:
            found = file_version(path)
        except (sqlite3.Error, ValueError) as why:
            out.append({**row, "state": "unreadable", "error": str(why)[:200]})
            continue
        row["found"] = found
        if found is not None and found > code:
            row["state"] = "newer"
        elif found is None:             # made before versions were written down
            row.update(state="pending", steps=[f"v{code}: write the schema version"])
        elif found < code:
            row.update(state="pending", steps=steps(name, found, code))
        else:
            row["state"] = "current"
        out.append(row)
    return out


def newer_message(row: dict) -> str:
    return (f"{Path(row['path']).name} is schema {row['found']}, and this code understands "
            f"{row['code']}: a newer Skald wrote it. Upgrade Skald (skald upgrade), or put "
            f"back the copy taken before that upgrade (docs/UPGRADING.md, \"Rolling back\").")


def guard(config: dict, history: Path) -> list[str]:
    """The refusal for each database newer than this code ([] when none)."""
    return [newer_message(r) for r in inspect(config, history) if r["state"] == "newer"]


# ------------------------------------------------------------ copies

def snapshot(config: dict, history: Path, folder: Path) -> tuple[list[dict], list[str]]:
    """A restore-tested copy of each database into `folder`:
    ([{"name","path","copy"|None}], problems). A database not there yet is
    noted with copy None, so a rollback removes what the new code made."""
    from .backup import copy, verify
    from .files import own_like_folder
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(folder, 0o750)
    except OSError:
        pass
    own_like_folder(folder)
    taken, problems = [], []
    for name, path in paths(config, history):
        if not path.exists():
            taken.append({"name": name, "path": str(path), "copy": None})
            continue
        target = folder / f"{name}.sqlite"
        try:
            seen = copy(path, target)
        except (OSError, sqlite3.Error) as why:
            problems.append(f"{name}: the copy FAILED: {why}")
            continue
        own_like_folder(target)
        problems += verify(target, seen)
        taken.append({"name": name, "path": str(path), "copy": str(target)})
    (folder / "snapshot.json").write_text(json.dumps(taken, indent=1) + "\n")
    return taken, problems


def _drop_journal(path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        try:
            Path(str(path) + suffix).unlink()
        except FileNotFoundError:
            pass


def restore(taken: list[dict]) -> list[str]:
    """Put each database back as `snapshot` copied it. [] when all went back."""
    from .files import own_like_folder
    problems = []
    for item in taken:
        path = Path(item["path"])
        try:
            if item.get("copy") is None:
                if path.exists():           # made by the new code: not there before
                    path.unlink()
                _drop_journal(path)
                continue
            tmp = path.with_name(f".{path.name}.restore.tmp")
            shutil.copyfile(item["copy"], tmp)
            os.chmod(tmp, 0o640)
            _drop_journal(path)
            os.replace(tmp, path)
            own_like_folder(path)
        except OSError as why:
            problems.append(f"{item['name']}: could not be put back from {item.get('copy')}: {why}")
    return problems


# ------------------------------------------------------------ applying

def _open(name: str, path: Path) -> None:
    """Open the file with its own code, which upgrades it, and close it."""
    if name == "history":
        from .store import History
        History(path).close()
    else:
        _module(name).connect(path).close()


def record(folder: Path, entries: list[dict]) -> None:
    from .files import own_like_folder, write_atomic
    path = Path(folder) / RECORD
    try:
        old = json.loads(path.read_text())
        old = old if isinstance(old, list) else []
    except (OSError, ValueError):
        old = []
    write_atomic(path, json.dumps((old + entries)[-KEEP:], indent=1) + "\n")
    own_like_folder(path)


def history_of(folder: Path) -> list[dict]:
    try:
        got = json.loads((Path(folder) / RECORD).read_text())
    except (OSError, ValueError):
        return []
    return got if isinstance(got, list) else []


def apply(config: dict, history: Path, now: datetime | None = None,
          version: str = "") -> tuple[list[dict], list[str]]:
    """Upgrade every database with steps pending: (records written, problems).
    Refuses (problems, nothing opened) when any file is newer than the code."""
    rows = inspect(config, history)
    refused = [newer_message(r) for r in rows if r["state"] == "newer"]
    refused += [f"{Path(r['path']).name}: not readable ({r.get('error')})"
                for r in rows if r["state"] == "unreadable"]
    if refused:
        return [], refused
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    done, problems = [], []
    for row in rows:
        if row["state"] != "pending":
            continue
        path = Path(row["path"])
        try:
            _open(row["name"], path)
            after = file_version(path)
        except Exception as why:        # noqa: BLE001 - said, and the rest stops
            problems.append(f"{row['name']}: the upgrade FAILED: {type(why).__name__}: {why}")
            break
        done.append({"at": now.isoformat(timespec="seconds"), "db": row["name"],
                     "file": path.name, "from": row["found"], "to": after,
                     "steps": len(row["steps"]), "code": version})
    if done:
        record(Path(history).parent, done)
    return done, problems


# ------------------------------------------------------------ the command

def table(rows: list[dict]) -> list[str]:
    words = {"absent": "not made yet", "current": "up to date", "pending": "steps pending",
             "newer": "NEWER than this code", "unreadable": "NOT READABLE"}
    out = []
    for r in rows:
        found = "-" if r["found"] is None else r["found"]
        out.append(f"{r['name']:<12} schema {found} (code {r['code']})  "
                   f"{words[r['state']]}  {r['path']}")
        out += [f"    {s}" for s in r["steps"]]
        if r["state"] == "newer":
            out.append(f"    {newer_message(r)}")
        if r["state"] == "unreadable":
            out.append(f"    {r.get('error')}")
    return out


def pre_copy_dir(ctx) -> Path:
    from .backup import backup_dir
    stamp = ctx.now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return backup_dir(ctx) / f"pre-migrate-{stamp}"


def cmd_migrate(ctx) -> int:
    from . import brand
    a = ctx.args
    rows = inspect(ctx.config, ctx.db_path)
    if a.check or a.json:
        if a.json:
            ctx.out(json.dumps({"databases": rows, "record": history_of(ctx.db_path.parent)[-20:]},
                               indent=1))
        else:
            for line in table(rows):
                ctx.out(line)
            if not any(r["state"] == "pending" for r in rows):
                ctx.out("nothing to do")
        return 1 if any(r["state"] in ("newer", "unreadable") for r in rows) else 0
    bad = [r for r in rows if r["state"] in ("newer", "unreadable")]
    if bad:
        for line in table(bad):
            ctx.err(line)
        ctx.err("migrate REFUSED: nothing was changed")
        return 1
    if not any(r["state"] == "pending" for r in rows):
        ctx.out("every database is up to date: nothing to do")
        return 0
    if not a.no_backup:
        folder = pre_copy_dir(ctx)
        _, problems = snapshot(ctx.config, ctx.db_path, folder)
        if problems:
            for p in problems:
                ctx.err(f"  - {p}")
            ctx.err("migrate REFUSED: the copy before it did not pass the restore test")
            return 1
        ctx.out(f"copied and restore-tested every database into {folder}")
    done, problems = apply(ctx.config, ctx.db_path, version=brand.load().get("version") or "")
    for d in done:
        ctx.out(f"{d['db']}: schema {d['from']} -> {d['to']} ({d['steps']} steps)")
    for p in problems:
        ctx.err(p)
    if problems:
        ctx.err("migrate FAILED; the copies taken before it are in the backup folder")
        return 1
    return 0


def _flags(p) -> None:
    p.add_argument("--check", action="store_true",
                   help="list each database, its schema, the code's, and the steps pending")
    p.add_argument("--json", action="store_true", help="--check as JSON, with the record")
    p.add_argument("--no-backup", dest="no_backup", action="store_true",
                   help="skip the copy (`upgrade` has just taken one)")


def add_command(sub) -> None:
    p = sub.add_parser("migrate", help="upgrade the databases to this code's schema, "
                       "after a restore-tested copy (--check: list only)")
    _flags(p)
    p.set_defaults(run=cmd_migrate)


class Plain:
    """What cmd_migrate needs, from config.yml alone: no database is opened."""

    def __init__(self, args) -> None:
        from .config import load_config, setting
        self.args = args
        self.config_path = Path(args.config)
        if not self.config_path.exists():
            raise SystemExit(f"config not found: {self.config_path}")
        self.config = load_config(self.config_path)
        raw = Path(str(setting(self.config, "history", "db", "history.sqlite"))).expanduser()
        self.db_path = raw if raw.is_absolute() else self.config_path.resolve().parent / raw
        self.live_dir = self.db_path.parent
        self.now = datetime.now(timezone.utc)
        self.out = print
        self.err = lambda *a: print(*a, file=sys.stderr)


def command_of(argv: list[str]) -> str | None:
    """The command word of a skald command line (after --config X and the like)."""
    i = 0
    while i < len(argv):
        word = argv[i]
        if word in ("--config", "--today", "--site"):
            i += 2
        elif word.startswith("-"):
            i += 1
        else:
            return word
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="skald", description="skald migrate: " + __doc__.split("\n")[0])
    ap.add_argument("--config", default="config.yml")
    ap.add_argument("--today", help=argparse.SUPPRESS)
    ap.add_argument("--site", dest="only_site", help=argparse.SUPPRESS)
    ap.add_argument("command", choices=["migrate"])
    _flags(ap)
    return cmd_migrate(Plain(ap.parse_args(argv)))

"""Copies of the history, kept on the server, each one tested by restoring it.

The history is the only state that cannot be rebuilt: the web server keeps
its logs 14 days, the totals are kept for good. So `skald backup` (nightly
from cron) does three things:

  1. copies history with SQLite's online backup API into
     history-YYYY-MM-DD.sqlite (the local date in report.timezone), through a
     temporary name and a rename, mode 0640, and keeps the newest --keep;
  2. on Sundays, or when this ISO week has no weekly copy yet, also writes a
     gzip copy history-weekly-YYYY-Www.sqlite.gz, keeping --weekly-keep;
  3. restores what it wrote into a scratch file (gunzipped for the weekly),
     runs PRAGMA integrity_check and compares the row count of every table
     with the counts taken from the source at the moment of the copy.

The counts and the copy come from one read transaction on one connection,
so a collect or a live run writing in between cannot make the two disagree
and fail a good backup. They are written beside the copy as
<copy>.counts.json, which is what `--verify` checks a copy against later -
so the restore test compares two things taken independently: what SQLite
counted in the source, and what a restored file holds.

The accounts and conversions databases, when this install has them, are
copied the same way as accounts-YYYY-MM-DD.sqlite and conversions-YYYY-MM-DD.sqlite
(with their own weekly copies), tested and pruned alike.

What a backup holds: the totals, the 7 days of anonymous journeys and the
30 days of keyed visitor hashes (pseudonymous: HMAC of an address with a
key that lives only in the env file). The env file, the SMTP login and the
visitor key are never copied. Where the copies go off the server is the
owner's decision (README, "Backups"); `--pull` prints the command that
fetches the newest one to another machine.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

from . import runs

DAILY = re.compile(r"^history-(\d{4}-\d{2}-\d{2})\.sqlite$")
WEEKLY = re.compile(r"^history-weekly-(\d{4})-W(\d{2})\.sqlite\.gz$")
# Other databases beside the history, copied the same way under their own name:
# the accounts (people, roles, tokens, settings) and the conversions.
EXTRA = ("accounts", "conversions")


def backup_dir(ctx) -> Path:
    given = getattr(ctx.args, "dir", None)
    if given:
        return Path(given)
    raw = ((ctx.config or {}).get("backup") or {}).get("dir")
    if raw:
        p = Path(str(raw)).expanduser()
        return p if p.is_absolute() else ctx.config_path.resolve().parent / p
    return Path(ctx.db_path).parent / "backups"


def _tables(db) -> list[str]:
    return [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def counts(db) -> dict[str, int]:
    """Rows per table."""
    return {t: int(db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])
            for t in _tables(db)}


def copy(source: Path, target: Path) -> dict[str, int]:
    """Copy `source` to `target` (temp file, then rename; 0640) and return
    the row counts of the source as copied.

    The read transaction is opened first and held through the copy, so the
    counts and the pages copied are the same snapshot, whatever writes
    happen meanwhile (they wait, or - in WAL mode - land after it)."""
    src = sqlite3.connect(f"file:{Path(source).resolve()}?mode=ro", uri=True,
                          isolation_level=None)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    os.close(fd)
    try:
        src.execute("BEGIN")
        seen = counts(src)
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
        src.execute("COMMIT")
        os.chmod(tmp, 0o640)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    finally:
        src.close()
    return seen


def _gzip(plain: Path, target: Path) -> None:
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb") as out, \
                open(plain, "rb") as handle:
            shutil.copyfileobj(handle, out)
        os.chmod(tmp, 0o640)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _manifest(path: Path) -> Path:
    return path.with_name(path.name + ".counts.json")


def _write_manifest(path: Path, seen: dict[str, int]) -> None:
    from .files import write_atomic
    write_atomic(_manifest(path), json.dumps({"tables": seen}, sort_keys=True) + "\n")
    os.chmod(_manifest(path), 0o640)


def verify(path: Path, expected: dict[str, int] | None = None) -> list[str]:
    """Restore `path` into a scratch file and check it. [] when it is good.

    `expected` defaults to the counts written beside it when it was made."""
    path = Path(path)
    if expected is None:
        try:
            expected = json.loads(_manifest(path).read_text())["tables"]
        except (OSError, ValueError, KeyError):
            return [f"{path.name}: no counts file beside it to check against"]
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as scratch:
        restored = Path(scratch) / "restored.sqlite"
        try:
            if path.suffix == ".gz":
                with gzip.open(path, "rb") as handle, open(restored, "wb") as out:
                    shutil.copyfileobj(handle, out)
            else:
                shutil.copyfile(path, restored)
        except (OSError, EOFError, gzip.BadGzipFile) as why:
            return [f"{path.name}: cannot be restored ({why})"]
        try:
            db = sqlite3.connect(str(restored))
            try:
                check = db.execute("PRAGMA integrity_check").fetchone()[0]
                if check != "ok":
                    problems.append(f"{path.name}: integrity check says {check}")
                got = counts(db)
            finally:
                db.close()
        except sqlite3.DatabaseError as why:
            return [f"{path.name}: not a readable database ({why})"]
    for table, n in sorted(expected.items()):
        if got.get(table) != n:
            problems.append(f"{path.name}: table {table} has {got.get(table)} rows, "
                            f"the source had {n}")
    for table in sorted(set(got) - set(expected)):
        problems.append(f"{path.name}: table {table} was not in the source")
    return problems


def _dailies(folder: Path, stem: str = "history") -> list[Path]:
    daily = re.compile(rf"^{stem}-(\d{{4}}-\d{{2}}-\d{{2}})\.sqlite$")
    return sorted((p for p in folder.glob(f"{stem}-*.sqlite") if daily.match(p.name)),
                  key=lambda p: p.name)


def _weeklies(folder: Path, stem: str = "history") -> list[Path]:
    weekly = re.compile(rf"^{stem}-weekly-(\d{{4}})-W(\d{{2}})\.sqlite\.gz$")
    return sorted((p for p in folder.glob(f"{stem}-weekly-*.sqlite.gz")
                   if weekly.match(p.name)), key=lambda p: p.name)


def _prune(files: list[Path], keep: int) -> list[Path]:
    gone = files[:-keep] if keep > 0 else list(files)
    for p in gone:
        for q in (p, _manifest(p)):
            try:
                q.unlink()
            except FileNotFoundError:
                pass
    return gone


def weekly_name(day: date, stem: str = "history") -> str:
    year, week, _ = day.isocalendar()
    return f"{stem}-weekly-{year}-W{week:02d}.sqlite.gz"


def make(source: Path, folder: Path, day: date, keep: int = 14,
         weekly_keep: int = 8, stem: str = "history") -> tuple[list[Path], list[str]]:
    """Back up, prune, and verify what was written: (written, problems)."""
    folder.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(folder, 0o750)
    except OSError:
        pass
    daily = folder / f"{stem}-{day.isoformat()}.sqlite"
    seen = copy(source, daily)
    _write_manifest(daily, seen)
    written = [daily]
    weekly = folder / weekly_name(day, stem)
    if day.weekday() == 6 or not weekly.exists():
        _gzip(daily, weekly)
        _write_manifest(weekly, seen)
        written.append(weekly)
    _prune(_dailies(folder, stem), keep)
    _prune(_weeklies(folder, stem), weekly_keep)
    problems = []
    for path in written:
        problems += verify(path, seen)
    return written, problems


def newest(folder: Path) -> Path | None:
    found = _dailies(folder) or _weeklies(folder)
    return found[-1] if found else None


def pull_command(config: dict, path: Path) -> str:
    host = str(((config or {}).get("backup") or {}).get("ssh_host") or "<server>")
    return f"scp -i ~/.ssh/<your-key> root@{host}:{path} ~/Downloads/"


def kept(config: dict, keep: int | None = None,
         weekly_keep: int | None = None) -> tuple[int, int]:
    """(daily, weekly) copies to keep: --keep / --weekly-keep when given,
    else backup.daily / backup.weekly (config.yml, or Settings > Data
    retention), else 14 and 8."""
    from .config import setting

    def number(name: str, default: int) -> int:
        try:
            return int(setting(config or {}, "backup", name, default))
        except (TypeError, ValueError):
            return default
    return (keep if keep is not None else number("daily", 14),
            weekly_keep if weekly_keep is not None else number("weekly", 8))


def extra_sources(ctx) -> list[tuple[str, Path]]:
    """The accounts and conversions databases this install has: (name, file)."""
    from .accounts import db as accounts_db
    from .conversions import store as conversions_store
    found = [("accounts", accounts_db.path_for(ctx.config, ctx.live_dir)),
             ("conversions", conversions_store.path_for(ctx.config, Path(ctx.db_path).parent))]
    return [(stem, Path(path)) for stem, path in found if path and Path(path).exists()]


def cmd_backup(ctx) -> int:
    folder = backup_dir(ctx)
    a = ctx.args
    if a.pull:
        got = newest(folder)
        if got is None:
            ctx.err(f"no backup in {folder} yet; run `skald backup` first")
            return 1
        ctx.out("Run this on the machine that keeps the copy, to fetch the newest backup:")
        ctx.out("  " + pull_command(ctx.config, got))
        return 0
    if a.verify:
        got = newest(folder)
        if got is None:
            ctx.err(f"no backup in {folder} to verify")
            code = 1
        else:
            problems = verify(got)
            for p in problems:
                ctx.err(f"  - {p}")
            ctx.out(f"verify {got.name}: " + ("FAILED" if problems else
                                               "restored, integrity ok, row counts match"))
            code = 1 if problems else 0
        runs.record(ctx.live_dir, "backup", code)
        return code
    if not Path(ctx.db_path).exists():
        ctx.err(f"no history file at {ctx.db_path}; nothing to back up")
        runs.record(ctx.live_dir, "backup", 1)
        return 1
    keep, weekly_keep = kept(ctx.config, a.keep, a.weekly_keep)
    try:
        written, problems = make(Path(ctx.db_path), folder, ctx.now.date(),
                                 keep, weekly_keep)
    except (OSError, sqlite3.Error) as why:
        ctx.err(f"backup FAILED: {why}")
        runs.record(ctx.live_dir, "backup", 1)
        return 1
    for stem, source in extra_sources(ctx):
        try:
            more, bad = make(source, folder, ctx.now.date(), keep, weekly_keep, stem)
        except (OSError, sqlite3.Error) as why:
            more, bad = [], [f"{stem}: backup FAILED: {why}"]
        written += more
        problems += bad
    for path in written:
        ctx.out(f"wrote {path} ({path.stat().st_size:,} bytes)")
    if problems:
        ctx.err("backup written but the restore test FAILED:")
        for p in problems:
            ctx.err(f"  - {p}")
    else:
        ctx.out("restore test ok: integrity ok, every table's row count matches the source")
    code = 1 if problems else 0
    runs.record(ctx.live_dir, "backup", code)
    return code


def add_command(sub) -> None:
    p = sub.add_parser("backup", help="copy history (daily, plus a weekly gzip) and "
                       "test the copy by restoring it")
    p.add_argument("--dir", help="backup directory (default backup.dir, else "
                   "backups/ beside the history)")
    p.add_argument("--keep", type=int, default=None,
                   help="daily copies kept (default backup.daily, else 14)")
    p.add_argument("--weekly-keep", dest="weekly_keep", type=int, default=None,
                   help="weekly gzip copies kept (default backup.weekly, else 8)")
    which = p.add_mutually_exclusive_group()
    which.add_argument("--verify", action="store_true",
                       help="only restore-test the newest copy")
    which.add_argument("--pull", action="store_true",
                       help="print the scp command that fetches the newest copy")
    p.set_defaults(run=cmd_backup)

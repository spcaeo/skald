"""Every store Skald keeps for one site: written to one archive, then deleted.

"Delete all data" (PURGE) and "Clear data" (CLEAR) in Settings > Sites and
`skald site purge|clear` (site_lifecycle.py) call `archive` and then `delete`
with the same plan, so what is archived is exactly what is deleted. Nothing is
deleted unless the archive was written whole.

The stores, by where they live (the history folder unless the config says
otherwise), and what each action takes:

  history.sqlite       every table with a `site` column: the site's rows and
                       its page groups' (<site>::<view>)                 both
  conversions.sqlite   every table with a `site` column (leads, journeys,
                       kept visits, security rows, deliveries, outbox ...),
                       meta keys ending ":<site>" (the outbox cursor)     both
                       its outgoing webhooks (a setting)            purge only
  ai_answers.sqlite    runs, answers, figures                             both
                       lists, profiles, profile_versions (settings)  purge only
  accounts.sqlite      security_items, security_sends, summary_items      both
                       security_prefs, share_links (set-up links),
                       todo_marks, client_reports, client_report_sends,
                       settings (scope site:<name>), site_setup and the
                       ingest/read tokens: by site_lifecycle.py      purge only
  sites/<slug>/        the site's state folder: live snapshot, alerts, run
                       log, beacon spool, robots and sitemap state ...    both
                       (CLEAR keeps funnels.json, ours.json, markers.log and
                       bot-policy*.json: the site's own settings)
  ingest/<slug>/       the log lines a shipper or a drain sent            both
  ingest-status/<slug>.json  the endpoint's last answer                   both
  <dashboard out>/<slug>/    its dashboard pages and data files           both
                       (CLEAR draws them again at once)
  hooks/*.jsonl        lead-hook spool lines for the site                 both
  search/<site>.*      the Search Console and Bing sync state       purge only
                       (kept on CLEAR, so the sync does not fill the days
                       before the clear again)
  logos/<slug>/        the site's logo                              purge only
  kit-links.json       its set-up links (one-command install, AI agent line)
                                                                    purge only
  secrets.json         hooks/<site>/*, outgoing/<site>/*: deleted, never
                       archived (the archive lists their names)     purge only

The archive is one `site-<name>-<kind>-<UTC stamp>.tar.gz` in the install's
backups folder (where `skald backup` writes: backup.dir, else <history
folder>/backups), mode 0640: a manifest.json, a copy of each database holding
only the site's rows, and the files. `prune` deletes archives older than
KEEP_DAYS (30); it runs after each archive and with every `skald backup`, except on an
install that keeps everything (keep_everything.install_on), which keeps them all.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import sqlite3
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .files import slug

PURGE, CLEAR = "purge", "clear"
KEEP_DAYS = 30
ARCHIVE = re.compile(r"^site-(?P<site>[a-z0-9.-]+)-(?:purge|clear)-"
                     r"(?P<at>\d{8}T\d{6}Z)\.tar\.gz$")
KEEP_ON_CLEAR = ("funnels.json", "ours.json", "markers.log", "bot-policy.json",
                 "bot-policy-applied.json")
ANSWERS_DATA = ("runs", "answers", "figures")
ACCOUNTS_DATA = ("security_items", "security_sends", "summary_items")
ACCOUNTS_PURGE = ("security_prefs", "share_links", "todo_marks", "client_reports",
                  "client_report_sends")


class Install:
    """Where one install keeps things: its config, the history folder, the
    dashboard's folder (or None)."""

    def __init__(self, config: dict, config_path, folder, out=None):
        self.config, self.folder = config or {}, Path(folder)
        self.config_path = Path(config_path) if config_path else None
        self.out = Path(out) if out else None

    def _rel(self, raw) -> Path:
        p = Path(str(raw)).expanduser()
        if p.is_absolute() or self.config_path is None:
            return p
        return self.config_path.resolve().parent / p

    @property
    def history(self) -> Path:
        raw = (self.config.get("history") or {}).get("db")
        return self._rel(raw) if raw else self.folder / "history.sqlite"

    @property
    def conversions(self) -> Path | None:
        from .conversions import store
        return store.path_for(self.config, self.folder)

    @property
    def answers(self) -> Path:
        from .answers import store
        return store.path_for(self.folder)

    @property
    def backups(self) -> Path:
        raw = (self.config.get("backup") or {}).get("dir")
        return self._rel(raw) if raw else self.folder / "backups"

    def ingest(self, name: str) -> Path:
        from . import ingest_log
        return ingest_log.site_folder(ingest_log.root(self.config, self.folder), name)


# ------------------------------------------------------------------ the plan

def _columns(db, table: str) -> list[str]:
    return [c[1] for c in db.execute(f'PRAGMA table_info("{table}")')]


def _tables(db) -> list[str]:
    return [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                     "AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _db_plan(db, kind: str, store: str, name: str) -> list[tuple[str, str, tuple]]:
    """[(table, WHERE, args)] of one database for this action."""
    out = []
    for table in _tables(db):
        cols = _columns(db, table)
        if store == "history" and "site" in cols:
            out.append((table, "site = ? OR substr(site, 1, ?) = ?",
                        (name, len(name) + 2, name + "::")))
        elif store == "conversions":
            if table == "meta":
                out.append((table, "substr(key, -?) = ?", (len(name) + 1, ":" + name)))
            elif "site" in cols and not (kind == CLEAR and table == "webhooks"):
                out.append((table, "site = ?", (name,)))
        elif store == "answers" and "site" in cols and (kind == PURGE or table in ANSWERS_DATA):
            out.append((table, "site = ?", (name,)))
        elif store == "answers" and table == "profile_versions" and kind == PURGE:
            out.append((table, "profile_id IN (SELECT id FROM profiles WHERE site = ?)", (name,)))
        elif store == "accounts" and "site" in cols and (
                table in ACCOUNTS_DATA or (kind == PURGE and table in ACCOUNTS_PURGE)):
            out.append((table, "site = ?", (name,)))
    # profile_versions before profiles: its rows are found through them.
    return sorted(out, key=lambda t: (t[0] != "profile_versions", t[0] != "outbox"))


def _databases(inst: Install, accounts) -> list[tuple[str, Path]]:
    found = [("history", inst.history), ("conversions", inst.conversions),
             ("answers", inst.answers), ("accounts", accounts)]
    return [(k, Path(p)) for k, p in found if p is not None and Path(p).is_file()]


def _state_files(inst: Install, name: str, kind: str) -> list[Path]:
    folder = inst.folder / "sites" / slug(name)
    if not folder.is_dir():
        return []
    if kind == PURGE:
        return [folder]
    return sorted(p for p in folder.iterdir() if p.name not in KEEP_ON_CLEAR)


def _files(inst: Install, name: str, kind: str) -> list[Path]:
    """Files and folders this action deletes (each whole)."""
    from . import ingest_status
    found = _state_files(inst, name, kind)
    ingest = inst.ingest(name)
    if ingest.is_dir():
        found += sorted(ingest.iterdir()) if kind == CLEAR else [ingest]
    found.append(ingest_status.path_for(inst.folder, name))
    if inst.out is not None:
        found.append(inst.out / slug(name))
    if kind == PURGE:
        from .site_logos import folder as logos
        found.append(logos(inst.folder, name))
        found += sorted((inst.folder / "search").glob(f"{name}.*"))
    return [p for p in found if p.exists() or p.is_symlink()]


def _spool_rows(inst: Install, name: str) -> list[dict]:
    from .conversions import spool
    folder = spool.spool_dir(inst.config, inst.folder)
    if not folder.is_dir():
        return []
    return [r for day in spool.days(folder) for r in spool.read(folder, day)
            if r.get("site") == name]


def _secret_names(inst: Install, name: str) -> list[str]:
    from .conversions import secrets_store
    path = secrets_store.path_for(inst.config, inst.folder)
    return sorted(k for k in secrets_store.load(path) if _secret_of(k, name)) \
        if Path(path).exists() else []


def _secret_of(key: str, name: str) -> bool:
    return key.split("/")[:2] in (["hooks", name], ["outgoing", name])


def _kit_links(inst: Install, name: str) -> dict:
    from .kit import link
    return {k: v for k, v in link._load(link.path_for(inst.folder)).items()
            if isinstance(v, dict) and v.get("site") == name}


# ------------------------------------------------------------------- archive

def _stamp(now: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if now is None else now,
                                  timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _subset(source: Path, target: Path, plan) -> dict[str, int]:
    """A copy of `source` with only the planned rows. Rows per table."""
    dst = sqlite3.connect(str(target))
    try:
        dst.execute("ATTACH DATABASE ? AS src", (str(source.resolve()),))
        counts = {}
        for table, where, args in plan:
            sql = dst.execute("SELECT sql FROM src.sqlite_master WHERE type = 'table' "
                              "AND name = ?", (table,)).fetchone()[0]
            dst.execute(sql)
            counts[table] = dst.execute(f'INSERT INTO main."{table}" SELECT * FROM '
                                        f'src."{table}" WHERE {where}', args).rowcount
        dst.commit()
        dst.execute("DETACH DATABASE src")
        return counts
    finally:
        dst.close()


def archive(inst: Install, accounts, name: str, kind: str, actor, extra: dict | None = None,
            now: float | None = None) -> dict:
    """Write the archive; {"path", "name", "counts"}. Raises on any failure,
    leaving no partial file; nothing is deleted here."""
    folder = inst.backups
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"site-{name}-{kind}-{_stamp(now)}.tar.gz"
    counts: dict = {}
    with tempfile.TemporaryDirectory(dir=folder, prefix=".site-") as scratch:
        scratch = Path(scratch)
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=f".{target.name}.", suffix=".tmp")
        os.close(fd)
        try:
            with tarfile.open(tmp, "w:gz") as tar:
                for store, path in _databases(inst, accounts):
                    plan = _plan_of(path, kind, store, name)
                    if not plan:
                        continue
                    part = scratch / f"{store}.sqlite"
                    counts[store] = _subset(path, part, plan)
                    tar.add(part, arcname=f"{store}.sqlite")
                for path in _files(inst, name, kind):
                    tar.add(path, arcname="files/" + _arc(inst, path))
                rows = _spool_rows(inst, name)
                if rows:
                    _add_text(tar, "hooks-spool.jsonl",
                              "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
                counts["hook spool lines"] = len(rows)
                if kind == PURGE:
                    links = _kit_links(inst, name)
                    _add_text(tar, "setup-links.json", json.dumps(
                        [{k: v.get(k) for k in ("site", "kind", "made_at", "expires_at")}
                         for v in links.values()], indent=1))
                    counts["set-up links"] = len(links)
                manifest = {"site": name, "kind": kind, "made_at": _stamp(now), "by": str(actor),
                            "counts": counts, "files": [_arc(inst, p) for p in
                                                        _files(inst, name, kind)],
                            "secrets_deleted_not_archived": _secret_names(inst, name)
                            if kind == PURGE else [], **(extra or {})}
                _add_text(tar, "manifest.json", json.dumps(manifest, indent=1, default=str))
            os.chmod(tmp, 0o640)
            os.replace(tmp, target)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    prune(folder, config=inst.config)
    return {"path": str(target), "name": target.name, "counts": counts}


def _plan_of(path: Path, kind: str, store: str, name: str) -> list:
    db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        return _db_plan(db, kind, store, name)
    finally:
        db.close()


def _arc(inst: Install, path: Path) -> str:
    for label, base in (("history-folder", inst.folder), ("dashboard", inst.out)):
        if base is not None:
            try:
                return f"{label}/{Path(path).relative_to(base)}"
            except ValueError:
                continue
    return "other/" + Path(path).name


def _add_text(tar, arcname: str, text: str) -> None:
    data = text.encode("utf-8")
    info = tarfile.TarInfo(arcname)
    info.size, info.mtime, info.mode = len(data), int(time.time()), 0o640
    tar.addfile(info, io.BytesIO(data))


def prune(folder, keep_days: int = KEEP_DAYS, now: float | None = None,
          config: dict | None = None) -> list[Path]:
    """Delete site archives older than `keep_days` (by the stamp in the name);
    none of a site that keeps everything (keep_everything.Keeper: the install's
    rule, unless the site's organisation is a client)."""
    from .keep_everything import Keeper
    keeper = Keeper(config or {})
    now = time.time() if now is None else now
    gone = []
    for path in Path(folder).glob("site-*.tar.gz"):
        m = ARCHIVE.match(path.name)
        if not m or keeper(m.group("site")):
            continue
        made = datetime.strptime(m.group("at"), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if now - made.timestamp() > keep_days * 86400:
            path.unlink(missing_ok=True)
            gone.append(path)
    return gone


# -------------------------------------------------------------------- delete

def delete(inst: Install, accounts, name: str, kind: str) -> dict:
    """Delete what `archive` wrote, store by store. Counts, and `items`: one line per
    table and per file or folder deleted, for the report."""
    counts: dict = {"rows": 0, "files": 0, "spool": 0, "secrets": 0, "links": 0, "items": []}
    for store, path in _databases(inst, accounts):
        db = sqlite3.connect(str(path), timeout=30, isolation_level=None)
        try:
            db.execute("BEGIN IMMEDIATE")
            try:
                for table, where, args in _db_plan(db, kind, store, name):
                    n = db.execute(f'DELETE FROM "{table}" WHERE {where}', args).rowcount
                    counts["rows"] += n
                    if n:
                        counts["items"].append(f"{path.name} {table}: {n} rows")
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("COMMIT")
        finally:
            db.close()
    for path in _files(inst, name, kind):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        counts["files"] += 1
        counts["items"].append(f"deleted {path}")
    from .conversions import spool
    folder = spool.spool_dir(inst.config, inst.folder)
    if folder.is_dir():
        counts["spool"] = spool.scrub(folder, lambda row, texts: row.get("site") == name)
    from .conversions import held                    # refused deliveries held (2.44.1)
    counts["held"] = held.drop_site(inst.folder, name)
    if kind == PURGE:
        from .conversions import secrets_store
        counts["secrets"] = secrets_store.delete(secrets_store.path_for(inst.config, inst.folder),
                                                 lambda key: _secret_of(key, name))
        counts["links"] = _drop_links(inst, name)
    if kind == CLEAR:
        inst.ingest(name).mkdir(parents=True, exist_ok=True)   # the shipper's lines land here
    return counts


def _drop_links(inst: Install, name: str) -> int:
    from .kit import link
    path = link.path_for(inst.folder)
    if not path.exists():
        return 0
    with link._locked(path):
        links = link._load(path)
        keep = {k: v for k, v in links.items()
                if not (isinstance(v, dict) and v.get("site") == name)}
        if len(keep) != len(links):
            link._save(path, keep, time.time())
    return len(links) - len(keep)

"""Deletion requests: `skald forget --ip X` (and --email, --vid, --lead).

What skald keeps about one address, and what forget does to each:

  * the private page's lists - today's AI events (live-<site>-ai.json and
    every data/ai_activity.json) and the recent requests
    (live-<site>-requests.json and every data/requests.json): each "ip"
    field holding the address becomes "(removed)";
  * history's keyed visitor hashes (visitor_days, 30 days): the hash is
    HMAC(key, address) joined with a family - a reader's browser and system,
    or a crawler's name - so forget computes it for every family the
    package can produce and deletes the rows that match. Without the key no
    hash can be matched, and forget says so;
  * the visits kept with the address (people/visits.py, conversions.sqlite
    `visits`, 2.4.0): every row of the address is deleted, and on a site
    that keeps addresses shortened (`privacy.keep_ips: short`) every row of
    its shortened form, which may hold other people's visits too;
  * from now on: the address goes on a forgotten list (forgotten.json
    beside the history) as its SHA-256 only, with an expiry 15 days ahead -
    past the web server's 14 days of logs - so the next live runs, which
    read the raw log again, keep showing it as "(removed)".

The web server's own access logs are not touched: they are the server's,
rotate away after 14 days, and the README gives the command to scrub them
by hand. Totals and anonymous journeys hold no address and are not changed.
--email, --vid and --lead run `conversions forget` (cli_conversions.py): the
conversions, removed rows, identity, journeys, deliveries and spool lines.
Each forget is logged to privacy.log (time, a hash prefix, the counts),
never the address.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .files import write_atomic

REMOVED = "(removed)"
KEEP_DAYS = 15
FORGOTTEN = "forgotten.json"
LOG = "privacy.log"
DATA_FILES = ("ai_activity.json", "requests.json")


def digest(ip: str) -> str:
    return hashlib.sha256(ip.strip().encode("utf-8", "replace")).hexdigest()


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _load(directory: Path, now: datetime | None = None) -> list[dict]:
    """The forgotten list, expired entries dropped."""
    try:
        got = json.loads((Path(directory) / FORGOTTEN).read_text())
    except (OSError, ValueError):
        return []
    at = _now(now)
    keep = []
    for e in got.get("entries", []) if isinstance(got, dict) else []:
        try:
            if datetime.fromisoformat(e["until"]) > at and len(e["sha256"]) == 64:
                keep.append({"sha256": e["sha256"], "until": e["until"]})
        except (KeyError, TypeError, ValueError):
            continue
    return keep


def _save(directory: Path, entries: list[dict]) -> None:
    path = Path(directory) / FORGOTTEN
    write_atomic(path, json.dumps({"entries": entries}, indent=1, sort_keys=True) + "\n")
    os.chmod(path, 0o640)


def remember(directory: Path, ip: str, now: datetime | None = None) -> None:
    """Put `ip` on the forgotten list (or extend it), pruning expired ones."""
    entries = [e for e in _load(directory, now) if e["sha256"] != digest(ip)]
    until = _now(now) + timedelta(days=KEEP_DAYS)
    entries.append({"sha256": digest(ip), "until": until.isoformat(timespec="seconds")})
    _save(directory, entries)


def forgotten(directory: Path | None, now: datetime | None = None) -> Callable[[str], bool]:
    """A test for "this address was forgotten": loaded once, cheap per call.
    With no directory or no list, nothing is forgotten."""
    wanted = {e["sha256"] for e in _load(directory, now)} if directory is not None else set()
    if not wanted:
        return lambda ip: False
    seen: dict[str, bool] = {}

    def test(ip: str) -> bool:
        got = seen.get(ip)
        if got is None:
            if len(seen) > 100_000:
                seen.clear()
            got = seen[ip] = digest(ip or "") in wanted
        return got
    return test


# ----------------------------------------------------------------- JSON files

def redact(value, ip: str) -> tuple[object, int]:
    """`value` with every "ip" field equal to `ip` replaced; and how many."""
    if isinstance(value, dict):
        n = 0
        out = {}
        for k, v in value.items():
            if k == "ip" and isinstance(v, str) and v == ip:
                out[k] = REMOVED
                n += 1
            else:
                out[k], m = redact(v, ip)
                n += m
        return out, n
    if isinstance(value, list):
        n = 0
        out_list = []
        for v in value:
            got, m = redact(v, ip)
            out_list.append(got)
            n += m
        return out_list, n
    return value, 0


def redact_file(path: Path, ip: str, dry_run: bool = False) -> int:
    """Redact one JSON file in place (atomically, same mode). Fields changed."""
    try:
        text = path.read_text()
        data = json.loads(text)
        mode = path.stat().st_mode & 0o777
    except (OSError, ValueError):
        return 0
    data, n = redact(data, ip)
    if n and not dry_run:
        compact = "\n" not in text.strip()
        body = (json.dumps(data, ensure_ascii=False, separators=(",", ":")) if compact
                else json.dumps(data, indent=1, ensure_ascii=False))
        write_atomic(path, body + "\n")
        os.chmod(path, mode)
    return n


def private_files(live_dir: Path, site: str) -> list[Path]:
    from .live import path_for
    snap = Path(path_for(live_dir, site))
    return [snap.with_name(snap.stem + "-ai.json"),
            snap.with_name(snap.stem + "-requests.json")]


def data_files(out: Path | None) -> list[Path]:
    if out is None or not Path(out).is_dir():
        return []
    return sorted(p for name in DATA_FILES for p in Path(out).rglob(name)
                  if p.parent.name == "data")


# ------------------------------------------------------------- visitor hashes

def families(db) -> set[str]:
    """Every family a visitor hash can have been made with."""
    from . import classify
    from .dimensions import BROWSER_NAMES, SYSTEM_NAMES
    out = {f"{b}/{s}" for b in BROWSER_NAMES for s in SYSTEM_NAMES}
    for pattern in (classify.AI_TRAINING, classify.AI_ASKED, classify.SEARCH_ENGINE):
        for token in pattern.pattern.split("|"):
            token = re.sub(r"\(\?<?[!=][^)]*\)", "", token).strip()
            if token:
                out.update({token, token.lower()})
    try:
        for (name,) in db.execute(
                "SELECT DISTINCT name FROM counts WHERE kind IN "
                "('engine_training', 'engine_asked', 'search_engine', 'bot_agent', 'cited_by')"):
            out.add(name)
    except Exception:
        pass
    return out


def forget_hashes(db, key: bytes, ip: str, dry_run: bool = False) -> int:
    """Delete the visitor_days rows made from `ip`. Rows deleted (or found)."""
    from .visitors import visitor_hash
    wanted = {visitor_hash(key, ip, f) for f in families(db)}
    rows = db.execute("SELECT DISTINCT visitor FROM visitor_days").fetchall()
    hits = [v for (v,) in rows if v in wanted]
    if not hits:
        return 0
    marks = ",".join("?" * len(hits))
    if dry_run:
        return int(db.execute(f"SELECT COUNT(*) FROM visitor_days WHERE visitor IN ({marks})",
                              hits).fetchone()[0])
    with db:
        return db.execute(f"DELETE FROM visitor_days WHERE visitor IN ({marks})", hits).rowcount


# ------------------------------------------------------------------- command

def forget(ctx, ip: str, dry_run: bool = False) -> dict:
    """Do it; return the counts (never another address)."""
    from .cli import _path
    from .visitors import load_key
    report = {"private_fields": 0, "data_fields": 0, "files": 0, "hashes": None,
              "visits": 0}
    for path in private_files(ctx.live_dir, ctx.site):
        n = redact_file(path, ip, dry_run)
        report["private_fields"] += n
        report["files"] += bool(n)
    for path in data_files(_path(ctx.config, ctx.config_path, "dashboard", "out", None)):
        n = redact_file(path, ip, dry_run)
        report["data_fields"] += n
        report["files"] += bool(n)
    key = load_key(ctx.config)
    if key is not None and Path(ctx.db_path).exists():
        import sqlite3
        db = sqlite3.connect(str(ctx.db_path))
        try:
            has = db.execute("SELECT 1 FROM sqlite_master WHERE name = 'visitor_days'").fetchone()
            report["hashes"] = forget_hashes(db, key, ip, dry_run) if has else 0
        finally:
            db.close()
    report["visits"] = _forget_visits(ctx, ip, dry_run)
    if not dry_run:
        remember(ctx.live_dir, ip)
        line = (f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} forget "
                f"sha256:{digest(ip)[:12]} private_fields={report['private_fields']} "
                f"data_fields={report['data_fields']} files={report['files']} "
                f"hashes={report['hashes']} visits={report['visits']}\n")
        log = Path(ctx.live_dir) / LOG
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(line)
        os.chmod(log, 0o640)
    return report


def _forget_visits(ctx, ip: str, dry_run: bool) -> int:
    """The visits kept with `ip` (people/visits.py): deleted, or counted."""
    from .conversions import store
    from .people import policy
    from .people.visits import forget_ip
    folder = Path(ctx.db_path).parent
    path = store.path_for(ctx.config, folder)
    if path is None or not Path(path).is_file():
        return 0
    # A site that keeps addresses shortened: its rows of the shortened form
    # go too (they cannot be told apart from the person's).
    short = (ctx.site,) if policy.ip_mode(ctx.config, folder) == policy.SHORT else ()
    db = store.connect(path)
    try:
        from .security_kept import forget_ip as forget_scanner   # Security's rows (2.21)
        forget_scanner(db, ip, dry_run, short)
        return forget_ip(db, ip, dry_run, short)
    finally:
        db.close()


def cmd_forget(ctx) -> int:
    a = ctx.args
    if not (a.ip or a.email or a.vid or a.lead):
        ctx.err("forget: give --ip, --email, --vid or --lead (any of them)")
        return 2
    code = _forget_ip(ctx) if a.ip else 0
    if code:
        return code
    from .cli_conversions import forget_person
    for kind in ("email", "vid", "lead"):
        value = getattr(a, kind)
        if value:
            forget_person(ctx, **{kind: value}, dry_run=a.dry_run)
    return 0


def _forget_ip(ctx) -> int:
    ip = ctx.args.ip.strip()
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        ctx.err(f"forget: {ip!r} is not an IP address")
        return 2
    dry = ctx.args.dry_run
    got = forget(ctx, ip, dry)
    verb = "would change" if dry else "changed"
    ctx.out(f"forget{' (dry run)' if dry else ''}: {verb} {got['private_fields']} field(s) "
            f"in the private snapshot files and {got['data_fields']} in the dashboard "
            f"data files ({got['files']} file(s))")
    if got["hashes"] is None:
        ctx.out("  visitor hashes: no visitor key configured (or no history), so no hash "
                "can be matched; none were changed")
    else:
        ctx.out(f"  visitor hashes: {got['hashes']} row(s) "
                f"{'found' if dry else 'deleted'} from the 30-day table")
    ctx.out(f"  visits kept with the address: {got['visits']} kept visit(s) "
            f"{'found' if dry else 'deleted'}")
    if not dry:
        ctx.out(f"  the address is on the forgotten list for {KEEP_DAYS} days: live runs "
                "show it as (removed), and visits are kept without it")
    ctx.out("  not changed: the web server's own access logs (rotated away after 14 "
            "days; see README, Privacy, to scrub them sooner)")
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("forget", help="delete a person (deletion requests): an IP address "
                       "everywhere it is kept, and an email, visitor ID or lead's conversions")
    p.add_argument("--ip", help="the address to forget")
    p.add_argument("--email", help="a lead's email: its conversions and identity")
    p.add_argument("--vid", help="a visitor ID (skv_...)")
    p.add_argument("--lead", help="a lead's id or a tool's reference (external_ref)")
    p.add_argument("--dry-run", dest="dry_run", action="store_true",
                   help="count what would change; change nothing")
    p.set_defaults(run=cmd_forget)

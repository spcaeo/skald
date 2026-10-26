"""What an owner or an admin can do to a site, and what the runs make of it.

One set of actions behind Settings > Sites (sites_api.py: sites/pause, resume,
remove, restore, clear, purge) and `skald site pause|resume|remove|restore|
clear|purge` (sites_cli.py), for a site made from the dashboard and a site
from the server's config files alike:

  pause / resume   stop collecting and counting, then start again. Ingest
                   answers 503 with Retry-After (the shipper keeps its lines);
                   live and run-daily skip the site (`skipped`). History,
                   settings, tokens and pages stay. The days paused read Not
                   recorded, never 0; `resume_words` says whether the log can
                   still fill them.                              owner or admin
  remove / restore stop processing and hide the site from the dashboard; its
                   data stays. Restore undoes it.                    owner only
  clear            archive, then delete the collected data (history, the
                   shipped log, leads and conversions, AI answer runs, the
                   state folder); settings and tokens stay. The days before the
                   clear are never collected again (`before_clear`), so they
                   read Not recorded.                                owner only
  purge            "Delete all data": archive, then delete every store of the
                   site (site_data.py), revoke its tokens, drop its settings
                   and set-up links. A dashboard site is gone (its name held
                   30 days); a config-file site keeps its config entry and
                   becomes Removed, with no data.                    owner only

The install's main site (the config file's own `site:`) can be paused, never
removed, cleared or deleted here: its config is the base of every other site's
and its files sit beside the install's own.

Every action writes one audit row (the site, the actor and, for clear and purge,
the archive's file name; never a person's data).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .accounts import auditlog, orgs, site_configs, site_state
from .accounts import db as base
from .config import site_name

MAIN_WORDS = ("{name} is this install's main site: its config is the base of every other "
              "site's, and its files sit beside the install's own. Pause it here; removing "
              "it or deleting its data is done on the server.")
DRAINS = ("vercel_json", "netlify_json", "edge_json")


class Refused(ValueError):
    def __init__(self, code: int, words: str):
        super().__init__(words)
        self.code = code


def config_names(config, config_path) -> list[str]:
    """The sites the config files define, the main site first."""
    from .sites_api import config_sites
    return config_sites(config, config_path)


def find(db, name: str, config, config_path, org_id=None) -> dict:
    """The site as the actions see it. Refused(404) when it is not a site of the
    install (or of `org_id`)."""
    name = str(name or "").strip().lower()
    row = site_configs.get(db, name)
    names = config_names(config, config_path)
    own = orgs.org_of_site(db, name)
    if row is None and name not in names:
        raise Refused(404, "There is no such site here.")
    org = row["org_id"] if row is not None else (own["id"] if own else None)
    if org_id is not None and org != org_id:
        raise Refused(404, "There is no such site in this organisation.")
    state = site_state.get(db, name)
    dashboard = row is not None and name not in names
    removed = (row["removed_at"] if dashboard else None) or state["removed_at"]
    return {"name": name, "source": "dashboard" if dashboard else "config",
            "main": bool(names) and name == names[0], "org_id": org,
            "removed_at": removed, "paused_at": state["paused_at"],
            "cleared_at": state["cleared_at"]}


def state_of(site: dict) -> str:
    return "removed" if site["removed_at"] else "paused" if site["paused_at"] else "active"


# ------------------------------------------------------------- pause/resume

def pause(db, site: dict, actor) -> dict:
    if site["removed_at"]:
        raise Refused(400, f"{site['name']} is removed. Restore it first.")
    try:
        got = site_state.pause(db, site["org_id"], site["name"], actor)
    except ValueError as why:
        raise Refused(400, str(why)) from None
    return {"paused_at": got["paused_at"]}


def resume(db, site: dict, actor, site_config: dict | None, now: datetime | None = None) -> dict:
    try:
        was = site_state.resume(db, site["org_id"], site["name"], actor)
    except ValueError as why:
        raise Refused(400, str(why)) from None
    return resume_words(site_config or {}, was["paused_at"], now)


def _local(stamp: str, tz) -> date:
    return base.parse(stamp).astimezone(tz).date()


def resume_words(config: dict, paused_at: str, now: datetime | None = None) -> dict:
    """{"days", "first", "last", "words"}: the whole days the pause missed
    (from the day it was paused to yesterday) and, in plain words, whether
    the log can still fill them or they stay Not recorded."""
    from .window import zone
    tz = zone(config or {})
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    first, last = _local(paused_at, tz), now.date() - timedelta(days=1)
    days = max(0, (last - first).days + 1)
    out = {"days": days, "first": first.isoformat() if days else None,
           "last": last.isoformat() if days else None}
    if not days:
        out["words"] = "Collecting starts again. No whole day was missed."
        return out
    name, fmt = site_name(config or {}), str(((config or {}).get("logs") or {}).get("format"))
    span = f"{days} day{'s' if days != 1 else ''} ({first.isoformat()} to {last.isoformat()})"
    fill = f"skald --site {name} backfill --days {(now.date() - first).days}"
    head = f"Collecting starts again. The {span} paused read Not recorded, never 0. "
    if config.get("_dashboard_site") and fmt in DRAINS:
        out["words"] = head + ("A log drain does not keep lines it could not send, "
                               "so those days stay Not recorded.")
    elif config.get("_dashboard_site"):
        out["words"] = head + ("The shipper kept its lines and sends them now. Once they "
                               "are in, an install admin can count those days with: " + fill)
    else:
        from .views_fill import reach
        held = reach(config, tz, now)
        if held["first"] and held["first"] <= first.isoformat():
            out["words"] = head + ("The server's log still holds them: an install admin "
                                   "can count them with: " + fill)
        elif held["first"]:
            out["words"] = head + (f"The server's log holds days from {held['first']} only: "
                                   "days before that stay Not recorded; an install admin can "
                                   "count the rest with: " + fill)
        else:
            out["words"] = head + "The server's log no longer holds them, so they stay Not recorded."
    return out


# ------------------------------------------------------------ remove/restore

def remove(db, site: dict, actor) -> dict:
    _not_main(site)
    if site["removed_at"]:
        raise Refused(400, f"{site['name']} is already removed.")
    if site["source"] == "dashboard":
        got = site_configs.remove(db, site["org_id"], site["name"], actor)
        return {"removed_at": got["removed_at"]}
    got = site_state.set_removed(db, site["org_id"], site["name"], actor, True)
    return {"removed_at": got["removed_at"]}


def restore(db, site: dict, actor) -> dict:
    if not site["removed_at"]:
        raise Refused(400, f"{site['name']} is not removed.")
    if site["source"] == "dashboard":
        site_configs.restore(db, site["org_id"], site["name"], actor)
    else:
        site_state.set_removed(db, site["org_id"], site["name"], actor, False)
    return {"status": "paused" if site["paused_at"] else "active"}


def _not_main(site: dict) -> None:
    if site["main"]:
        raise Refused(400, MAIN_WORDS.format(name=site["name"]))


# --------------------------------------------------------------- clear/purge

def install(config, config_path, folder, out=None):
    from .site_data import Install
    return Install(config, config_path, folder, out)


def clear(db, accounts_path, inst, site: dict, actor) -> dict:
    """Archive, then delete the site's collected data; settings and tokens stay."""
    from . import site_data
    _not_main(site)
    got = site_data.archive(inst, accounts_path, site["name"], site_data.CLEAR, actor)
    gone = site_data.delete(inst, accounts_path, site["name"], site_data.CLEAR)
    with base.tx(db):
        site_state.mark_cleared(db, site["name"], actor)
        auditlog.record(db, site["org_id"], actor, "site.clear", site["name"],
                        f"archive {got['name']}; settings and tokens kept")
    return {"archive": got["path"], "archive_name": got["name"], "deleted": gone}


def purge(db, accounts_path, inst, site: dict, actor) -> dict:
    """Delete all data: archive, then every store; tokens revoked."""
    from . import site_data, site_verify
    from .accounts import site_setup
    _not_main(site)
    name = site["name"]
    got = site_data.archive(inst, accounts_path, name, site_data.PURGE, actor)
    gone = site_data.delete(inst, accounts_path, name, site_data.PURGE)
    detail = f"archive {got['name']}"
    if site["source"] == "dashboard":
        done = site_configs.purge(db, name, actor, detail=detail, allow_active=True)
        site_verify.forget(db, name)
        site_state.forget(db, name)
        until = site_verify.reserve(db, name, actor)
        return {"archive": got["path"], "archive_name": got["name"], "deleted": gone,
                "tokens_revoked": done["tokens_revoked"], "status": "deleted",
                "name_held_until": until}
    with base.tx(db):
        revoked = site_configs.revoke_tokens(db, site["org_id"], name) \
            if site["org_id"] is not None else 0
        db.execute("DELETE FROM settings WHERE scope = ?", (f"site:{name}",))
        site_setup.forget(db, name)
        site_verify.forget(db, name)
        site_state.set_removed(db, site["org_id"], name, actor, True, audit=False)
        site_state.mark_cleared(db, name, actor)
        auditlog.record(db, site["org_id"], actor, "site.purge", name,
                        f"{detail}; {revoked} tokens revoked; config entry kept, removed")
    return {"archive": got["path"], "archive_name": got["name"], "deleted": gone,
            "tokens_revoked": revoked, "status": "removed"}


# --------------------------------------------------------------- the runs

def _open(config, folder):
    path = base.path_for(config or {}, folder)
    if path is None or not Path(path).is_file():
        return None
    import sqlite3
    db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def skipped(config, folder) -> dict[str, str]:
    """{site: why} for every paused or removed site: the runs skip them."""
    db = _open(config, folder)
    if db is None:
        return {}
    try:
        try:
            rows = db.execute("SELECT name, paused_at, removed_at FROM site_state").fetchall()
        except Exception:                 # noqa: BLE001 - no table yet: nothing is paused
            return {}
    finally:
        db.close()
    out = {}
    for r in rows:
        if r["removed_at"]:
            out[r["name"]] = f"removed since {r['removed_at'][:10]}"
        elif r["paused_at"]:
            out[r["name"]] = f"paused since {r['paused_at'][:10]}"
    return out


def paused(db, name: str) -> str | None:
    """When the site was paused (ingest's check), or None."""
    return site_state.get(db, name)["paused_at"]


def removed_here(db, name: str) -> bool:
    """A config-file site removed from the dashboard (ingest answers 410)."""
    return bool(site_state.get(db, name)["removed_at"])


def before_clear(config, folder, site: str, day: date) -> bool:
    """True for a day before the site's last clear: it is never collected again."""
    db = _open(config, folder)
    if db is None:
        return False
    try:
        try:
            row = db.execute("SELECT cleared_at FROM site_state WHERE name = ?",
                             (site,)).fetchone()
        except Exception:                 # noqa: BLE001 - no table yet: never cleared
            return False
    finally:
        db.close()
    if row is None or not row["cleared_at"]:
        return False
    from .window import zone
    return day < _local(row["cleared_at"], zone(config or {}))

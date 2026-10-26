"""Settings > Site details > Views: "Fill past days for the new groups" (sessions mode).

Served through settings_api.py (its sign-in, membership, same-origin and
X-Skald-CSRF checks), for every site page:

  GET  settings/views-fill          the fill's state for this site (or only
                                    "busy" when another organisation's site is
                                    filling) and `reach`: the whole days the raw
                                    log holds (views_fill.reach). Admins.
  POST settings/views-fill-start    {views: [slug, ...]} (default: every view of
                                    the site): runs `skald --site S views refresh
                                    --days N --view ...` in the background, N =
                                    the days the raw log holds. Admins and
                                    owners (or an install admin); one fill at a
                                    time per install (409 while one runs);
                                    written to the audit log (views.fill).

A save of sites.views answers `views` (after_save): the views it added or
changed, the ones it removed (their folders are left out of the menu; nothing
to recount), the raw log's reach and the fill's state, so the page offers
the fill.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import settings_store as store
from . import views_fill
from .accounts import auditlog

ROOT = Path(__file__).resolve().parent.parent
QUEUED_GRACE = 120      # seconds a started job has to take the lock


def folder(c) -> Path:
    """Where the state and the lock are: beside the history (one per install)."""
    if c.history_path is not None:
        return Path(c.history_path).parent
    return Path(c.live_dir)


def _site(c) -> tuple[dict, object]:
    """The site's config with its Settings laid over, and its time zone."""
    from .window import zone
    conf = store.apply(c.config, c.site, c.live_dir)
    try:
        tz = zone(conf)
    except Exception:                   # noqa: BLE001 - a bad zone: UTC, as the preview does
        tz = timezone.utc
    return conf, tz


def _views(conf: dict) -> list:
    from .config import views
    try:
        return views(conf)
    except ValueError:
        return []


def reach(c) -> dict:
    conf, tz = _site(c)
    return views_fill.reach(conf, tz)


def current(where: Path, now: datetime | None = None) -> dict:
    """The install's fill state; a running or queued one whose process is
    gone (no lock held, past the grace) reads as failed."""
    got = views_fill.load(where)
    if got.get("state") not in ("queued", "running") or views_fill.busy(where):
        return got
    since = got.get("asked_at") or got.get("started_at") or ""
    try:
        age = ((now or datetime.now(timezone.utc)) - datetime.fromisoformat(since)).total_seconds()
    except ValueError:
        age = QUEUED_GRACE + 1
    if got.get("state") == "queued" and age <= QUEUED_GRACE:
        return got
    return {**got, "state": "failed",
            "error": got.get("error") or "The fill stopped before it finished (the server "
                                         "restarted, or the job could not start). Start it again."}


def for_site(c, state: dict) -> dict | None:
    """The state as this caller may see it: this site's in full; another
    site's only as "busy" while it runs (never its name)."""
    if not state:
        return None
    if state.get("site") == c.site:
        return state
    return {"state": "busy"} if state.get("state") in ("queued", "running") else None


def after_save(c, old, new) -> dict:
    """The `views` part of a save's answer."""
    added, removed = views_fill.changed(old, new)
    out = {"changed": added, "removed": removed,
           "can_fill": bool(c.admin or c.install_admin)}
    if added:
        out["reach"] = reach(c)
        out["fill"] = for_site(c, current(folder(c)))
    return out


def status(c, form):
    return c.ok(fill=for_site(c, current(folder(c))), reach=reach(c),
                views=[{"slug": v.slug, "name": v.name} for v in _views(_site(c)[0])])


def spawn(c, args: list[str], log: Path) -> None:
    """Run `skald --config C --site S <args>` detached. Replaced in tests."""
    if c.config_path is None:
        raise OSError("the helper does not know its config file")
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as out:
        subprocess.Popen([sys.executable, str(ROOT / "bin/skald"), "--config", str(c.config_path),
                          "--site", c.site, *args], cwd=str(ROOT), stdin=subprocess.DEVNULL,
                         stdout=out, stderr=subprocess.STDOUT, start_new_session=True)


def start(c, form):
    if not (c.admin or c.install_admin):
        return c.no(403, "Only an admin can fill past days.", role=c.role)
    conf, _ = _site(c)
    known = {v.slug: v.name for v in _views(conf)}
    asked = form.get("views")
    if asked is None:
        asked = list(known)
    if not isinstance(asked, list) or not asked or len(asked) > 20 \
            or not all(isinstance(s, str) and s in known for s in asked):
        return c.no(400, "Name the groups to fill, from this site's Views.")
    where = folder(c)
    span = reach(c)
    if not span["days"]:
        return c.no(409, "The raw log holds no whole day before today, so there is nothing "
                         "to fill yet. The groups count from the next run.", reach=span)
    with views_fill.guard(where):
        now = current(where)
        if now.get("state") in ("queued", "running"):
            return c.no(409, "A fill is already running on this server. Try again when it "
                             "ends.", fill=for_site(c, now))
        state = views_fill.save(
            where, fresh=True, state="queued", site=c.site,
            views=[{"slug": s, "name": known[s]} for s in asked], days=span["days"],
            done=0, filled=0, withheld=0, empty=0, first=span["first"], last=span["last"],
            before=span["first"], kept_days=span["kept_days"], by=c.session["email"],
            asked_at=views_fill.now_text(), started_at=None, finished_at=None, error=None,
            problems=[])
    args = ["views", "refresh", "--days", str(span["days"]), "--by", c.session["email"]]
    for s in asked:
        args += ["--view", s]
    try:
        spawn(c, args, where / "views-fill.log")
    except OSError as why:
        views_fill.save(where, state="failed", error=f"Could not start: {why}")
        return c.no(503, "The fill could not be started on this server.")
    auditlog.record(c.db, c.org["id"], c.uid, "views.fill", c.site,
                    f"{span['days']} days ({span['first']} to {span['last']}): "
                    + ", ".join(known[s] for s in asked))
    return c.ok(fill=state, reach=span)

"""A set-up's live progress and its Check now (2.43), for Add a site, the Sites
list and Overview's "Set up <site>".

The owner (2026-10-27) added fieldcamp.ai, gave the agent line to its
developer, and the agent did it all: a Vercel log drain, the hooks, the set-up
marked done, 1,300 requests in. His open wizard still said only "Finish
later". Now the wizard shows, ticking by itself, each with its time:

    opened    the agent opened its line        (kit/agent.py opened_at)
    keys      the agent took its keys          (keys_at)
    road      the data road is set up: a Vercel or Netlify drain, the
              Cloudflare Worker, a shipper, the script tag (the first batch's
              drain or shipper, else the agent's report, else the way chosen)
    data      the first data arrived, with the lines of the last 15 minutes
              and the newest time (ingest_status.recent; the tag's events)
    verified  the domain is verified (site_verify.py), or needs no proof here
    done      the set-up is done (site_setup done_at)
    invites   who was invited, once (setup_people.py)

Routes (sites_api.py routes them with its session, role, same-origin and
CSRF checks; all for an owner or admin):

  POST sites/live {site, link_id?}  -> {live: one site's steps, state, counts}
       {all: true}                  -> {sites: {site: {state, lines, newest_at}}}
       Polled by the page every 5 s, then every 30 s; it marks a 2.43 set-up
       done and sends its invites once data arrived (setup_people.tick).
  POST sites/check {site}  Check now: the same checks as the doctor's access
       log line and the set-up checklist (setup_items.answers), at once, in
       plain words -> {check: {verdict: ok | wait | bad, head, says, fix, tech},
       live}. CHECK_PER_HOUR per admin.
  POST sites/sendinvites {site}  send the set-up's invites now, before the
       data (the late mail's button) -> {invites}
  GET  sites/whoopts       the organisations the person may add a site to, and
       this organisation's members (setup_people.options)
  POST sites/whofor {site, people}  change who will use it, before the invites
       went -> {setup}

2.44: live_now, check_now and send_now are the routes' cores, shared with the
MCP tools site_progress, check_site and send_invites (mcp/tools_addsite.py);
Check now's limit is counted per admin here and per token there.

`run(ctx)` is the live run's step (cli._after_live): the same tick for the
run's site, so the invites go out with no page open; 2.44, and one look at Google for a
Search Console property someone asked for (search/auto.py tick), connected once it shows. Nothing here counts a
figure: it reads what the endpoint and the set-up already keep.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import connections_api, ingest, ingest_status, site_verify
from .auth_api import text

CHECK_PER_HOUR = 60
DRAINS = {"vercel": "Vercel log drain", "netlify": "Netlify log drain",
          "edge": "Cloudflare Worker"}
WAYS = {"vercel": "Vercel log drain", "netlify": "Netlify log drain",
        "cloudflare": "Cloudflare Worker", "server": "the shipper on the site's server",
        "docker": "the shipper on the site's server", "systemd": "the shipper on the site's server",
        "script": "the script tag"}
# What to look at when nothing came, by the way the data travels.
NO_DATA = {
    "vercel": ("Usually it starts within 2 minutes after the drain is saved. If not, open "
               "Vercel, Settings, Log Drains: the drain's address ends in /traffic-ingest/{site}"
               "?format=vercel, its status is Active, and it sends the project's Static and "
               "Edge logs."),
    "netlify": ("Usually it starts within 2 minutes after the drain is saved. If not, open "
                "Netlify, Logs & metrics, Log drains: the address ends in "
                "/traffic-ingest/{site}?format=netlify."),
    "cloudflare": ("Usually it starts within 2 minutes after the Worker is deployed. If not, "
                   "check the Worker's route covers {site}, and that its SKALD_TOKEN secret is "
                   "set."),
    "server": ("Usually it starts within 2 minutes after the shipper starts. If not, run "
               "skald-ship-check on the server, or look at journalctl -u skald-ship -n 50."),
    "script": ("Data starts with the first visit to a page that carries the tag. Open {site} in "
               "a browser, then press Check now again. If still nothing, view the page's source "
               "and look for skald.js."),
}
NO_DATA["docker"] = NO_DATA["systemd"] = NO_DATA["server"]


def _now() -> float:
    return time.time()


def _stamp(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- facts

def facts(config, live_dir, config_path, site: str, now: float | None = None) -> dict:
    """What reached Skald for the site: {lines (kept so far), recent (the last
    15 minutes), newest_at, first_at, shipper, events (the tag's newest day),
    arrived}."""
    now = _now() if now is None else now
    base = ingest.history_folder(config, live_dir)
    rec = ingest_status.recent(base, site, now)
    _, summary = connections_api.received(config, live_dir, site)
    tag = connections_api.beacon_status(config, live_dir, config_path, site) or {}
    lines = int((summary or {}).get("accepted") or 0)
    events = int(tag.get("events") or 0)
    return {"lines": lines, "recent": rec["lines"],
            "newest_at": rec["newest_at"] or (summary or {}).get("last_at") or tag.get("updated_at"),
            "first_at": rec["first_at"], "shipper": rec["shipper"], "events": events,
            "arrived": lines > 0 or events > 0}


def line_of(folder, site: str, lid: str = "") -> dict | None:
    """The agent line watched (its link id), else the site's newest set-up line."""
    from .kit import agent
    if lid and agent.LINK_ID.match(lid):
        got = agent.status(folder, site, lid)
        return None if got["state"] == "unknown" else {"link_id": lid, **got}
    return agent.latest(folder, [site]).get(site)


def road_words(setup: dict | None, line: dict | None, f: dict) -> str | None:
    """How the data travels, in a few words; None when not known yet."""
    if f.get("shipper") in DRAINS:
        return DRAINS[f["shipper"]]
    if f.get("lines"):
        return "the shipper on the site's server"
    if f.get("events"):
        return "the script tag"
    hosting = ((line or {}).get("report") or {}).get("hosting")
    if hosting:
        return str(hosting)[:60]
    return WAYS.get((setup or {}).get("method") or "")


def steps(setup: dict | None, verify: dict | None, line: dict | None, f: dict) -> list[dict]:
    """The checklist: [{id, words, done, at, ...}], in order."""
    out = []
    if line and line.get("state") != "cancelled":
        out.append({"id": "opened", "words": "Your agent opened the line",
                    "done": bool(line.get("opened_at")), "at": line.get("opened_at")})
        out.append({"id": "keys", "words": "Keys made and taken by your agent",
                    "done": bool(line.get("keys_at")), "at": line.get("keys_at")})
    report = (line or {}).get("report") or {}
    logs = (report.get("jobs") or {}).get("logs") in ("done", "already")
    road = road_words(setup, line, f)
    out.append({"id": "road", "words": f"Data road set up: {road}" if road and (logs or f["arrived"])
                else "Data road set up", "done": bool(logs or f["arrived"]),
                "at": (line or {}).get("reported_at") if logs else f.get("first_at")})
    out.append({"id": "data", "words": "First data received", "done": f["arrived"],
                "at": f.get("first_at"), "recent": f.get("recent", 0),
                "newest_at": f.get("newest_at"), "lines": f.get("lines", 0)})
    pending = bool(verify) and verify.get("state") == "pending"
    out.append({"id": "verified", "words": "Domain verified" if verify else
                "Domain: no proof needed here", "done": not pending,
                "at": (verify or {}).get("verified_at")})
    out.append({"id": "done", "words": "Set-up done", "done": bool((setup or {}).get("done")),
                "at": (setup or {}).get("done_at")})
    people = (setup or {}).get("people") or []
    if people or (setup or {}).get("invites_at"):
        n = len(people)
        out.append({"id": "invites", "words": (setup or {}).get("invites_words") or
                    f"{n} {'person waits' if n == 1 else 'people wait'} for an invite: "
                    "it goes when the first data arrives",
                    "done": bool((setup or {}).get("invites_at")),
                    "at": (setup or {}).get("invites_at"), "people": n})
    return out


def state_of(setup: dict | None, f: dict) -> str:
    """done, receiving or waiting."""
    if (setup or {}).get("done"):
        return "done"
    return "receiving" if f["arrived"] else "waiting"


def verdict(setup: dict | None, verify: dict | None, line: dict | None, f: dict,
            refusal: dict | None, site: str, logs_line: dict | None = None) -> dict:
    """Check now's answer: {verdict: ok | wait | bad, head, says, fix, tech}."""
    tech = None
    if logs_line:
        tech = f"{logs_line.get('part') or 'Access log'}: {logs_line.get('says')}"
        if logs_line.get("fix") and logs_line.get("state") != "OK":
            tech += f"\nFix: {logs_line['fix']}"
    out = {"tech": tech, "fix": None, "says": None}
    newer = refusal and (not f.get("newest_at") or str(refusal.get("at")) > str(f["newest_at"]))
    if verify and verify.get("state") == "pending":
        return {**out, "verdict": "bad", "head": "The domain is not verified yet.",
                "says": "Nothing is collected for the site until it is: add the DNS TXT record "
                        "or the meta tag, then press Verify."}
    if newer:
        return {**out, "verdict": "bad", "head": "Skald refused what was sent.",
                "says": refusal.get("words") or "Refused.",
                "fix": "Make a new line (or a new token) and set it again, then press Check now."}
    if f.get("recent"):
        return {**out, "verdict": "ok", "head": "Receiving data.",
                "says": f"{f['recent']:,} lines in the last 15 minutes, the newest at "
                        f"{str(f.get('newest_at') or '')[11:16]} UTC."}
    if f.get("arrived"):
        return {**out, "verdict": "wait", "head": "Data arrived before, but none in the last 15 "
                                                 "minutes.",
                "says": "A quiet site can go a while without a visit. If it is not quiet, look "
                        "at the way the data comes in, below."}
    method = (setup or {}).get("method") or ""
    state = (line or {}).get("state")
    if line and state in ("waiting",):
        return {**out, "verdict": "wait", "head": "No data yet.",
                "says": "Your agent has not opened its line yet. Paste the line into your "
                        "agent, in the site's own folder or on its server."}
    if line and state == "opened":
        return {**out, "verdict": "wait", "head": "No data yet.",
                "says": "Your agent read the steps but has not taken its keys yet. It may be "
                        "waiting for your answer in its chat."}
    if line and state == "expired" and not line.get("keys_at"):
        return {**out, "verdict": "bad", "head": "No data yet, and the line expired.",
                "says": "Make a new line and give it to your agent."}
    report = (line or {}).get("report") or {}
    way = method if method in NO_DATA else ""
    host = str(report.get("hosting") or "").lower()
    for name in ("vercel", "netlify", "cloudflare"):
        if name in host:
            way = name
    says = NO_DATA.get(way, "Usually it starts within 2 minutes after the data road is set up. "
                            "If not, open the troubleshooting guide.").format(site=site)
    return {**out, "verdict": "wait", "head": "No data yet.", "says": says}


# ---------------------------------------------------------------- views

def refused(refusal: dict | None, f: dict) -> dict | None:
    """The plain reason Skald refused what was sent, when it is newer than the newest data
    kept (the Test connection's words, shown by the live progress without a press)."""
    if not refusal or (f.get("newest_at") and str(refusal.get("at")) <= str(f["newest_at"])):
        return None
    return {"words": refusal.get("words") or "Refused.", "at": refusal.get("at")}


def view(c, site: str, lid: str = "", now: float | None = None) -> dict:
    """One site's live view (sites/live)."""
    from .accounts import site_setup
    from .kit_api import _folder
    f = facts(c.config, c.live_dir, c.config_path, site, now)
    setup = site_setup.get(c.db, site)
    verify = site_verify.shown(c.db, site)
    line = line_of(_folder(c), site, lid)
    return {"site": site, "state": state_of(setup, f), "steps": steps(setup, verify, line, f),
            "refused": refused(ingest_status.status(ingest.history_folder(c.config, c.live_dir),
                                                    site).get("last_refusal"), f),
            "lines": f["lines"], "recent": f["recent"], "newest_at": f["newest_at"],
            "events": f["events"], "link_id": (line or {}).get("link_id"),
            "line_state": (line or {}).get("state"), "people": len((setup or {}).get("people")
                                                                  or []),
            "invites_words": (setup or {}).get("invites_words"),
            "invites_at": (setup or {}).get("invites_at"),
            "started_at": (setup or {}).get("started_at"),
            "now": _stamp(_now() if now is None else now)}


def _tick(c, site: str) -> None:
    from . import setup_people
    from .auth_api import base_url
    try:
        setup_people.tick(c.db, c.config, site, base_url(c.config, c.allowed),
                          lambda: _heard(c.config, c.live_dir, c.config_path, site),
                          lambda: check_words(c.config, c.live_dir, c.config_path, c.db, site))
    except Exception as why:              # noqa: BLE001 - the view never fails for a mail
        sys.stderr.write(f"setup tick {site}: {type(why).__name__}: {why}\n")


def _heard(config, live_dir, config_path, site):
    f = facts(config, live_dir, config_path, site)
    return f["lines"] or f["events"], f["arrived"]


def check_words(config, live_dir, config_path, db, site: str) -> str:
    """Check now's head and words in one line (the late mail)."""
    got = run_check(config, live_dir, config_path, db, site)
    return " ".join(x for x in (got["head"], got["says"]) if x)


def run_check(config, live_dir, config_path, db, site: str, lid: str = "") -> dict:
    from . import setup_items
    from .accounts import site_setup
    from .conversions import hooks
    folder = Path(live_dir) if live_dir is not None else hooks.history_folder(config, config_path)
    f = facts(config, live_dir, config_path, site)
    got = ingest_status.status(ingest.history_folder(config, live_dir), site)
    try:
        status = setup_items.answers(config, site, live_dir, config_path, accounts_db=db)["status"]
    except Exception:                     # noqa: BLE001 - the answer says what it knows
        status = None
    logs_line = setup_items._doc(status, "logs")
    return verdict(site_setup.get(db, site), site_verify.shown(db, site),
                   line_of(folder, site, lid), f, got.get("last_refusal"), site, logs_line)


# --------------------------------------------------------------- routes

def live_route(c, form):
    from .connections_api import _site
    from .accounts import orgs
    if form.get("all") is True:
        names = orgs.sites_of_org(c.db, c.org["id"])
        from .accounts import site_setup
        rows = site_setup.for_org(c.db, c.org["id"])
        out = {}
        for name in names:
            if rows.get(name) and not rows[name].get("invites_at"):
                _tick(c, name)
            f = facts(c.config, c.live_dir, c.config_path, name)
            row = site_setup.get(c.db, name) if rows.get(name) else None
            out[name] = {"state": state_of(row, f) if row else
                         ("receiving" if f["arrived"] else "none"),
                         "recent": f["recent"], "newest_at": f["newest_at"],
                         "setup": bool(row), "done": bool((row or {}).get("done"))}
        return c.ok(sites=out)
    site = _site(c, text(form, "site", 200))
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    return c.ok(live=live_now(c, site, text(form, "link_id", 40).strip().lower()))


def check_now(c, site: str, key: str, lid: str = "") -> dict | None:
    """Check now for one site (sites/check and the MCP's check_site): {check,
    live}, or None past CHECK_PER_HOUR for `key` (an admin, or a token)."""
    from .accounts import limits
    if limits.too_many(c.db, key, limit=CHECK_PER_HOUR, minutes=60):
        return None
    limits.note_failure(c.db, key)
    _tick(c, site)
    return {"check": run_check(c.config, c.live_dir, c.config_path, c.db, site, lid),
            "live": view(c, site, lid)}


def live_now(c, site: str, lid: str = "") -> dict:
    """One site's live view after its tick (sites/live and the MCP's site_progress)."""
    _tick(c, site)
    return view(c, site, lid)


def send_now(c, site: str) -> dict:
    """Send the set-up's invites now (sites/sendinvites and the MCP's send_invites):
    setup_people.send's answer; ValueError in plain words."""
    from . import setup_people
    from .auth_api import base_url
    f = facts(c.config, c.live_dir, c.config_path, site)
    return setup_people.send(c.db, c.config, site, base_url(c.config, c.allowed), c.uid,
                             requests=f["lines"] or None, by_hand=not f["arrived"])


def check_route(c, form):
    from .connections_api import _site
    site = _site(c, text(form, "site", 200))
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    got = check_now(c, site, f"setup-check:{c.uid}", text(form, "link_id", 40).strip().lower())
    if got is None:
        return c.no(429, "Too many checks. Try again in a few minutes.")
    return c.ok(**got)


def send_route(c, form):
    from .connections_api import _site
    site = _site(c, text(form, "site", 200))
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    try:
        got = send_now(c, site)
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(invites=got)


def options_route(c, form):
    from . import setup_people
    from .saas import enabled
    who = c.session or {}
    return c.ok(org={"id": c.org["id"], "name": c.org["name"]},
                may_make=not enabled(c.config) or bool(who.get("install_admin")),
                **setup_people.options(c.db, c.uid, c.org["id"]))


def people_route(c, form):
    from . import setup_people
    from .accounts import site_setup
    from .connections_api import _site
    site = _site(c, text(form, "site", 200))
    row = site_setup.get(c.db, site) if site else None
    if row is None:
        return c.no(404, "There is no set-up for this site in this organisation.")
    if row.get("invites_at"):
        return c.no(409, "The invites went already. Invite more people in Settings › "
                         "Organisation › People.")
    try:
        people = setup_people.clean(c.db, form.get("people"), c.org["id"],
                                    new_org=row.get("privacy_class") is not None)
        from .site_add import people_allowed
        seats = people_allowed(c.db, c.config, row["org_id"], people)
        if seats:
            raise ValueError(seats)
    except ValueError as why:
        return c.no(400, str(why))
    site_setup.note(c.db, site, people=people)
    from .accounts import auditlog
    auditlog.record(c.db, c.org["id"], c.uid, "setup.people", site,
                    f"{len(people)} to invite once data arrives")
    return c.ok(setup=site_setup.get(c.db, site))


ROUTES = {"sites/live": live_route, "sites/check": check_route, "sites/sendinvites": send_route,
          "sites/whoopts": options_route, "sites/whofor": people_route}
GETS = ("sites/whoopts",)


# ------------------------------------------------------------- live run

def run(ctx) -> None:
    """The live run's step for its site: setup_people.tick. Never fails the run."""
    from .accounts import db as base
    from .auth_api import base_url
    try:
        folder = Path(ctx.db_path).parent
        path = base.path_for(ctx.config, folder)
        if path is None or not Path(path).is_file():
            return
        db = base.connect(path)
        try:
            from . import setup_people
            from .accounts import site_setup
            site_setup.ensure(db)
            did = setup_people.tick(
                db, ctx.config, ctx.site, base_url(ctx.config),
                lambda: _heard(ctx.config, folder, ctx.config_path, ctx.site),
                lambda: check_words(ctx.config, folder, ctx.config_path, db, ctx.site))
            # 2.44: a Search Console property someone asked for: look once, connect once seen.
            from .search import auto
            did = auto.tick(ctx.config, ctx.config_path, folder, db, ctx.site) or did
        finally:
            db.close()
        if did:
            ctx.out(f"set-up {ctx.site}: {did}")
    except Exception as why:              # noqa: BLE001 - never stops a run
        ctx.err(f"set-up {ctx.site}: {type(why).__name__}: {why}")

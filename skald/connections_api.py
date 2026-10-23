"""Settings > Connections and the "Add a site" wizard: the parts the helper
answers beside Settings > Sites (sites_api.py routes them, with its session,
role and CSRF checks; every route here is for an owner or admin):

  GET  sites/status?site=<name>   what has reached Skald for the site
       -> {site, ingest_enabled, send_url, folder, received, last_batch,
           last_contact, today, last_refusal, verify, beacon, setup, now}
  POST sites/kit     {site, method: docker|systemd|server, token?, include_token}
       -> the install kit as a zip (skald/kit); with "server", the one
          bash file instead (skald-install-<site>.sh, kit_api.py). The token
          goes in only when include_token is true, and only a valid sending
          token of that site; it is never logged or kept.
  POST sites/setup   {name, step?, method?, token_id?, done?, found?}: the
       wizard's progress (accounts/site_setup.py), never a token's value; found:
       a site check's facts, kept cleaned (site_detect.clean_found) -> {setup}
  POST sites/detect  {address, name?}: the site check (site_detect.py): how the
       site at `address` is hosted, from outside, with a suggested way and
       why -> {found}. Fetched safely (site_fetch.py); DETECT_PER_ADMIN checks
       an hour per admin, DETECT_PER_TARGET per address in 10 minutes (429).
       With `name`, a site of the organisation with set-up progress, the
       facts are kept in that progress too (no progress row is made).

  POST sites/tagcheck {site}: the script tag's set-up Test, when nothing
       arrived: Skald reads the site's home page (tag_check.py, by site_fetch's
       safe rules) and says what is wrong -> {check: {state, words, fix, facts}}.
       Limited like sites/detect, under its own keys.

They live under sites/ so the nginx route every install already has
(`sites(?:/[a-z]+)?`) reaches them. `extras` adds to the GET sites answer
what the Connections page needs: the kit's availability, the API and MCP
addresses, and each site's set-up progress and "nothing for a day" flag.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from . import ingest, ingest_log, ingest_status, kit, site_verify
from .auth_api import answer, query, text
from .files import slug

QUIET_HOURS = 24
DETECT_PER_ADMIN = 30              # site checks an admin may ask for in an hour
DETECT_PER_TARGET = 6              # checks of one address in 10 minutes, by anyone


def _site(c, name: str) -> str | None:
    """`name` when it is a site of the caller's organisation, else None."""
    from .accounts import orgs
    return name if name in orgs.sites_of_org(c.db, c.org["id"]) else None


def _admin(c) -> bool:
    return c.role in ("owner", "admin")


def send_base(c) -> str:
    from .sites_api import _base
    return _base(c.config, c.allowed)


def _parse(stamp) -> float | None:
    """Unix seconds of an ISO time ("...Z", "...+02:00"; no zone: UTC), or None."""
    if not stamp:
        return None
    try:
        got = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (got if got.tzinfo else got.replace(tzinfo=timezone.utc)).timestamp()


# ---------------------------------------------------------------- beacon

def beacon_on(config) -> bool:
    b = (config or {}).get("beacon") or {}
    return bool(b.get("enabled") or b.get("origins"))


def beacon_status(config, live_dir, config_path, site: str) -> dict | None:
    """The script tag's newest day for the site: events kept and when the
    counters were last written (beacon_server.py's stats-<day>.json), and when
    a page last opened (opens-<day>.jsonl). None with the tag off. The spool
    is found as beacon_server.py finds it."""
    from . import beacon
    from .config import site_name
    if not beacon_on(config):
        return None
    if site == site_name(config or {}):
        spool = beacon.spool_dir(config, Path(config_path)) if config_path is not None \
            else beacon.spool_dir(config, None, live_dir)
    else:
        own = ingest.site_configs(config, config_path).get(site) or {}
        folder = ingest.history_folder(config, live_dir)
        spool = beacon.spool_dir(own, None, Path(folder) / "sites" / slug(site))
    empty = {"events": 0, "day": None, "updated_at": None, "last_open_at": None}
    try:
        stats = sorted(Path(spool).glob("stats-*.json"))
        opens = sorted(Path(spool).glob("opens-*.jsonl"))
        last_open = datetime.fromtimestamp(opens[-1].stat().st_mtime, timezone.utc) \
            .strftime("%Y-%m-%dT%H:%M:%SZ") if opens else None
    except OSError:
        return empty
    got = {}
    if stats:
        try:
            got = beacon.read_stats(spool, datetime.strptime(stats[-1].name[6:16],
                                                             "%Y-%m-%d").date()) or {}
        except ValueError:
            got = {}
    return {"day": got.get("day"), "updated_at": got.get("updated_at"),
            "events": int(got.get("accepted") or 0) + int(got.get("accepted_ours") or 0),
            "last_open_at": last_open}


# ---------------------------------------------------------------- status

def _received(c, site: str) -> tuple[bool, dict | None]:
    return received(c.config, c.live_dir, site)


def received(config, live_dir, site: str) -> tuple[bool, dict | None]:
    """(the site has an ingest folder, what it received: ingest_log.summary)."""
    root = ingest_log.root(config, ingest.history_folder(config, live_dir))
    folder = ingest_log.site_folder(root, site)
    return folder.is_dir(), (ingest_log.summary(folder) if folder.is_dir() else None)


def status(c, form):
    if not _admin(c):
        return c.no(403, "Only an admin can do this.", role=c.role)
    site = _site(c, query(c.h.path).get("site") or c.site)
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    from .accounts import site_setup
    base = ingest.history_folder(c.config, c.live_dir)
    has_folder, summary = _received(c, site)
    got = ingest_status.status(base, site)
    return c.ok(site=site, ingest_enabled=ingest.enabled(c.config),
                send_url=f"{send_base(c)}{ingest.PREFIX}{site}", folder=has_folder,
                received=summary, **got, verify=site_verify.shown(c.db, site),
                beacon=beacon_status(c.config, c.live_dir, c.config_path, site),
                setup=site_setup.get(c.db, site),
                now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


# ------------------------------------------------------------------- kit

def kit_zip(c, form):
    from .accounts import apitokens
    site = _site(c, text(form, "site", 200))
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    method = text(form, "method", 20)
    token = None
    if form.get("include_token") is True:
        token = text(form, "token", 200).strip()
        ok, why, _ = apitokens.check(c.db, f"Bearer {token}", site, "ingest")
        if not ok:
            return c.no(400, f"The token cannot go in the kit: {why}.")
    if method == "server":                        # the one bash file (kit_api.py)
        from . import kit_api
        return kit_api.server_file(c, site, token)
    page = f"{send_base(c)}/traffic/{slug(site)}/"
    try:
        data = kit.build(site, f"{send_base(c)}{ingest.PREFIX}{site}", method, page,
                         f"{page}#help?part=troubleshooting-connections",
                         kit.image(c.config), kit.ship_path(c.config), token)
    except ValueError as why:
        return c.no(400, str(why))
    name = f"skald-ship-{site}.zip"
    c.h.send_response(200)
    for k, v in (("Content-Type", "application/zip"),
                 ("Content-Disposition", f'attachment; filename="{name}"'),
                 ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                 ("Content-Length", str(len(data)))):
        c.h.send_header(k, v)
    c.h.end_headers()
    c.h.wfile.write(data)
    return None


# ----------------------------------------------------------------- setup

def setup(c, form):
    from .accounts import site_configs, site_setup
    name = _site(c, text(form, "name", 200))
    if name is None:
        return c.no(404, "There is no such site in this organisation.")
    method = text(form, "method", 20) or None
    done = form.get("done") if isinstance(form.get("done"), bool) else None
    found = form.get("found") if isinstance(form.get("found"), dict) else None
    try:
        got = site_setup.save(c.db, c.org["id"], name, c.uid, step=form.get("step"),
                              method=method, token_id=text(form, "token_id", 200) or None,
                              done=done, found=found)
    except ValueError as why:
        return c.no(400, str(why))
    fmt = site_setup.FORMAT_FOR.get(method or "", "auto") if method else None
    row = site_configs.get(c.db, name)
    if fmt and row is not None and row["active"] and row["format"] != fmt \
            and not (_received(c, name)[1] or {}).get("batches"):
        site_configs.set_format(c.db, name, fmt, c.uid)    # nothing arrived yet
    return c.ok(setup=got)


# ------------------------------------------------------------ site check

def detect(c, form):
    """The site check: admins only (sites_api.handle refuses the rest), and
    rate-limited per admin and per address before anything is fetched."""
    from . import site_detect
    from .accounts import limits, site_setup
    try:
        host = site_detect.clean_address(text(form, "address", 300))
    except ValueError as why:
        return c.no(400, str(why))
    mine, theirs = f"site-detect:user:{c.uid}", f"site-detect:host:{host}"
    if limits.too_many(c.db, mine, limit=DETECT_PER_ADMIN, minutes=60):
        return c.no(429, "Too many site checks. Try again in an hour, or choose by hand.")
    if limits.too_many(c.db, theirs, limit=DETECT_PER_TARGET, minutes=10):
        return c.no(429, f"{host} was checked many times just now. Try again in a few "
                         "minutes, or choose by hand.")
    limits.note_failure(c.db, mine)
    limits.note_failure(c.db, theirs)
    try:
        found = site_detect.detect(host)
    except ValueError as why:
        return c.no(400, str(why))
    name = _site(c, text(form, "name", 200)) if form.get("name") else None
    row = site_setup.get(c.db, name) if name is not None else None
    if row is not None:                   # never a new row: that would be a set-up badge
        use = (row.get("found") or {}).get("use") is not False
        site_setup.save(c.db, c.org["id"], name, c.uid, found={**found, "use": use})
    return c.ok(found=found)


# -------------------------------------------------------- the tag's page

def beacon_origins(config, config_path, site: str) -> set[str]:
    """The Origins the beacon helper takes for `site`, as beacon_server.Sites
    builds them: the first site's beacon.origins, a dashboard site's
    https://<each host>."""
    from . import beacon, settings_store
    from .config import setting, site_name
    if site == site_name(config or {}):
        got = setting(config, "beacon", "origins") or []
        return {got} if isinstance(got, str) else {str(o) for o in got if o}
    own = ingest.site_configs(config, config_path).get(site)
    if own is None:
        return set()
    return {f"https://{h}" for h in beacon.own_hosts(settings_store.apply(own, site))}


def tag_check(c, form):
    """The set-up Test's look at the site's home page when nothing from the
    tag arrived (tag_check.py). Admins only; rate-limited as the site check."""
    from . import tag_check as tc
    from .accounts import limits
    from .integrations_api import _origin
    site = _site(c, text(form, "site", 200))
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    if not beacon_on(c.config):
        return c.no(409, "The script tag is switched off on this server.")
    mine, theirs = f"tag-check:user:{c.uid}", f"tag-check:host:{site}"
    if limits.too_many(c.db, mine, limit=DETECT_PER_ADMIN, minutes=60):
        return c.no(429, "Too many page checks. Try again in an hour.")
    if limits.too_many(c.db, theirs, limit=DETECT_PER_TARGET, minutes=10):
        return c.no(429, f"{site} was checked many times just now. Try again in a few minutes.")
    limits.note_failure(c.db, mine)
    limits.note_failure(c.db, theirs)
    return c.ok(check=tc.check(site, beacon_origins(c.config, c.config_path, site), _origin(c)))


# ---------------------------------------------------- the GET sites extras

def last_heard(config, live_dir, config_path, site: str) -> float | None:
    """When anything last reached Skald for the site: a batch, or the tag."""
    got = ingest_status.read(ingest.history_folder(config, live_dir), site)
    times = [_parse(got.get("last_contact"))]
    _, had = received(config, live_dir, site)
    if had:
        times.append(_parse(had.get("last_at")))
    tag = beacon_status(config, live_dir, config_path, site)
    if tag and tag.get("events"):
        times.append(_parse(tag.get("updated_at")))
    times = [t for t in times if t]
    return max(times) if times else None


def progress(db, org_id, names, heard) -> dict:
    """{site: {"setup": entry, "quiet": bool}} for the sites with a set-up row.
    quiet: set up, and nothing reached Skald in the last QUIET_HOURS."""
    from .accounts import site_setup
    rows = site_setup.for_org(db, org_id)
    out = {}
    for name in names:
        row = rows.get(name)
        if row is None:
            continue
        last = heard(name) if row["done"] else None
        quiet = row["done"] and (last is None or time.time() - last > QUIET_HOURS * 3600)
        out[name] = {"setup": row, "quiet": bool(quiet)}
    return out


def extras(c, names) -> dict:
    from .auth_api import base_url
    from .mcp.http import enabled as mcp_on
    # The dashboard's own address (ingest.url may name another host for shippers).
    base = str(base_url(c.config, c.allowed) or send_base(c)).rstrip("/")
    return {"kit": kit.available(c.config), "api_base": f"{base}/traffic-api/v1/",
            "mcp_url": f"{base}/traffic-mcp", "mcp_enabled": mcp_on(c.config),
            "beacon_on": beacon_on(c.config),
            "progress": progress(c.db, c.org["id"], names,
                                 lambda n: last_heard(c.config, c.live_dir, c.config_path, n))}


def badges(config, live_dir, config_path, names) -> dict:
    """{site: (words, "setup" | "test")} for the site picker (helper_sessions.py):
    a set-up left unfinished, or one finished that has heard nothing for a day.
    `names`: the sites the caller is an admin of."""
    from .accounts import db as base
    from .accounts import site_configs, site_setup
    path = base.path_for(config, ingest.history_folder(config, live_dir))
    if path is None or not Path(path).is_file() or not names:
        return {}
    db = base.connect(path)
    try:
        site_setup.ensure(db)
        rows = {r["name"]: r for r in db.execute("SELECT name, step, done_at FROM site_setup")
                if r["name"] in set(names)}
        # A removed site collects nothing: no "continue" link for it (setup_page.py).
        removed = {r["name"] for r in site_configs.listing(db) if not r["active"]}
    finally:
        db.close()
    out = {}
    for name, row in rows.items():
        if name in removed:
            continue
        if not row["done_at"]:
            out[name] = (f"Setup: step {row['step']} of {site_setup.STEPS}, continue", "setup")
            continue
        last = last_heard(config, live_dir, config_path, name)
        if last is None or time.time() - last > QUIET_HOURS * 3600:
            out[name] = ("No visits yet: test the connection", "test")
    return out

"""Settings > Sites, a site's row menu: sites/pause, resume, remove, restore,
clear and purge (site_lifecycle.py does the work; sites_api.py checks the
session, CSRF, same origin, the plan and the role before these run).

  POST sites/pause    {name}                                    owner or admin
  POST sites/resume   {name} -> the days paused and, in plain words, whether
                      the log can still fill them               owner or admin
  POST sites/remove   {name, confirm: name}                          owner
  POST sites/restore  {name}                                         owner
  POST sites/clear    {name, confirm: name, understood: true} -> the archive's
                      path; settings and tokens stay                 owner
  POST sites/purge    {name, confirm: name, understood: true} -> the archive's
                      path; every store deleted, tokens revoked      owner

Each is limited per site: ACTS_PER_HOUR changes an hour, WIPES_PER_HOUR
clears and purges an hour for the organisation (each writes an archive).
"""
from __future__ import annotations

from . import site_lifecycle as life
from .auth_api import text

ACTS_PER_HOUR = 20
WIPES_PER_HOUR = 3
TYPED = ("sites/remove", "sites/clear", "sites/purge")
UNDERSTOOD = ("sites/clear", "sites/purge")


def _site(c, form) -> dict:
    return life.find(c.db, text(form, "name", 200), c.config, c.config_path, c.org["id"])


def _checked(c, form, act: str):
    """The site, or None once the refusal is answered."""
    from .accounts import limits
    try:
        site = _site(c, form)
    except life.Refused as why:
        return c.no(why.code, str(why))
    if act in TYPED and text(form, "confirm", 200).strip() != site["name"]:
        return c.no(400, f"Type the site name, {site['name']}, to confirm.")
    if act in UNDERSTOOD and form.get("understood") is not True:
        return c.no(400, "Tick the box that says what is deleted, to confirm.")
    key, most = (f"site-wipe:{c.org['id']}", WIPES_PER_HOUR) if act in UNDERSTOOD \
        else (f"site-act:{site['name']}", ACTS_PER_HOUR)
    if limits.too_many(c.db, key, limit=most, minutes=60):
        return c.no(429, "Too many changes to this site in the last hour. "
                         "Try again later.")
    limits.note_failure(c.db, key)
    return site


def _act(name: str):
    def call(c, form):
        act = f"sites/{name}"
        site = _checked(c, form, act)
        if site is None:
            return None
        try:
            got = RUN[name](c, site)
        except life.Refused as why:
            return c.no(why.code, str(why))
        except ValueError as why:
            return c.no(400, str(why))
        return c.ok(site=site["name"], **got)
    return call


def _resume(c, site):
    from .ingest import site_configs
    own = site_configs(c.config, c.config_path).get(site["name"]) or {}
    return life.resume(c.db, site, c.uid, own)


def _wipe(kind: str):
    def run(c, site):
        from .accounts import db as base
        from .ingest import history_folder
        folder = history_folder(c.config, c.live_dir)
        inst = life.install(c.config, c.config_path, folder, c.out)
        got = (life.clear if kind == "clear" else life.purge)(
            c.db, base.path_for(c.config, folder), inst, site, c.uid)
        if kind == "clear" and c.out is not None:
            # Its pages again, from no data, now: a paused site's live run would not.
            from . import first_page
            first_page.start(c.out, site["name"], c.config_path)
        return got
    return run


RUN = {"pause": lambda c, s: life.pause(c.db, s, c.uid), "resume": _resume,
       "remove": lambda c, s: life.remove(c.db, s, c.uid),
       "restore": lambda c, s: life.restore(c.db, s, c.uid),
       "clear": _wipe("clear"), "purge": _wipe("purge")}
ROUTES = {f"sites/{name}": _act(name) for name in RUN}
OWNER_ONLY = {"sites/remove": "Only an owner can remove a site.",
              "sites/restore": "Only an owner can restore a site.",
              "sites/clear": "Only an owner can clear a site's data.",
              "sites/purge": "Only an owner can delete a site's data."}

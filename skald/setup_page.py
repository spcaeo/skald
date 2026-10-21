"""The page at /traffic/<site>/ for a known site that has no dashboard page.

Owner-reported (21 Oct 2026): a site added in Settings > Add or remove sites,
its wizard at step 3 of 5, still had a card in the site picker with "Setup:
step 3 of 5, continue", but its address answered nginx's bare 404. nginx
serves /traffic/<site>/ from the dashboard's folder, and nothing had drawn a
page there: the runs draw only the active sites, and the dashboard folder
is drawn again from nothing when the container is made again.

So whenever the dashboard is written (`skald dashboard`, every live run),
`write_missing` writes a small page into the folder of every known site that
has no page, saying why there is no dashboard:

  waiting   an active site made from the dashboard with no day stored
            (multisite.waiting, sites.json `waiting`): "<site> is waiting for
            its first log lines", the wizard step it reached, "Continue setup"
            (or, with the setup finished, "Test the connection"), the
            troubleshooting guide, and a reload every RELOAD seconds, since
            its own run draws the real page within minutes
  removed   a site made from the dashboard and removed (site_config.removed_at):
            it was removed on that day, nothing is collected, its data stays
            until an install admin purges it. No setup button: a removed
            site's wizard would collect nothing.

The wizard and the guide open inside the web app, as the site picker's badge
does (helper_sessions.listing): `<site>/#settings/sitesadmin?setup=<name>`
(or `?test=<name>`) and `#help?part=troubleshooting-connections`, on a site
of the same organisation that has a drawn dashboard. With none, the page
links back to all sites only.

The page sits in the dashboard's folder, so nginx serves it behind the same
sign-in and membership check as the dashboard. It holds no figure, no address
and no token: the site's name, its state and the step. It is written only
where there is no page or where the page is this one (MARK), so a real
dashboard is never replaced; the site's own run writes its dashboard over
it, as for any page.
"""
from __future__ import annotations

import sqlite3
from html import escape as esc
from pathlib import Path
from urllib.parse import quote

from .files import slug, write_atomic

RELOAD = 60
MARK = '<meta name="skald-page" content="setup">'
GUIDE = "#help?part=troubleshooting-connections"
WAITING = "is waiting for its first log lines"

CSS = """
:root{color-scheme:light;--page:#edf0f3;--surface:#fbfcfd;--ink:#17212b;--ink-2:#4f5d6b;
--rule:#d8dfe6;--gap:#c3ccd5;--sunk:#e4e9ee;--sans:system-ui,-apple-system,"Segoe UI",Roboto,
"Helvetica Neue",Arial,sans-serif}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--page:#0d1319;--surface:#141c24;
--ink:#e4eaf0;--ink-2:#a9b5c1;--rule:#26313c;--gap:#3a4652;--sunk:#1b252f}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);
font:15px/1.55 var(--sans)}a{color:inherit}
:focus-visible{outline:2px solid var(--ink);outline-offset:2px;border-radius:8px}
.sp-top{display:flex;align-items:center;gap:10px;padding:14px 32px;font-weight:720;
font-size:18px;border-bottom:1px solid var(--rule);background:var(--surface)}
.sp-top svg{display:block}
main{max-width:40rem;margin:10vh auto;padding:0 16px}
.sp-box{padding:26px 28px;border:1px solid var(--rule);border-radius:12px;
background:var(--surface)}
h1{margin:0 0 10px;font-size:24px;font-weight:720;letter-spacing:-.01em;line-height:1.25;
overflow-wrap:anywhere}
p{margin:8px 0;color:var(--ink-2)}
.sp-acts{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;margin-top:18px}
.sp-go{display:inline-block;padding:9px 16px;border-radius:8px;background:var(--ink);
color:var(--surface);font-weight:650;text-decoration:none}
.sp-go:hover{opacity:.9}
@media (max-width:600px){.sp-top{padding:12px 16px}main{margin-top:6vh}.sp-box{padding:20px}}
"""


def _rows(db, sql: str) -> list:
    try:
        return db.execute(sql).fetchall()
    except sqlite3.OperationalError:     # a table not made yet: nothing of that kind
        return []


def states(config: dict, config_path) -> dict:
    """{site: {"org": id, "removed": stamp | None, "step": n | None, "done": bool,
    "made_here": bool}} from accounts.sqlite, or {} when there is none."""
    from . import multisite
    from .accounts import db as base
    path = base.path_for(config, multisite.history_folder(config, config_path)) \
        if config_path is not None else None
    if path is None or not Path(path).is_file():
        return {}
    db = base.connect(path)
    try:
        out = {name: {"org": org, "removed": None, "step": None, "done": False,
                      "made_here": False}
               for name, org in _rows(db, "SELECT name, org_id FROM sites")}
        for name, org, removed in _rows(db, "SELECT name, org_id, removed_at FROM site_config"):
            got = out.setdefault(name, {"org": org, "step": None, "done": False})
            got.update(removed=removed, made_here=True)
        for name, step, done in _rows(db, "SELECT name, step, done_at FROM site_setup"):
            if name in out:
                out[name].update(step=step, done=bool(done))
    finally:
        db.close()
    return out


def _drawn(out: Path, name: str) -> bool:
    """A real dashboard is there: its page and its data folder."""
    folder = Path(out) / slug(name)
    return (folder / "index.html").is_file() and (folder / "data").is_dir() \
        and not _ours(folder / "index.html")


def _ours(page: Path) -> bool:
    try:
        with open(page, encoding="utf-8", errors="replace") as handle:
            return MARK in handle.read(4096)
    except OSError:
        return False


def host_of(name: str, known: dict, order: list[str], out: Path) -> str | None:
    """A site of `name`'s organisation with a drawn dashboard, to open the
    wizard and the guide in; None when there is none."""
    org = (known.get(name) or {}).get("org")
    for other in order:
        if other != name and org is not None and (known.get(other) or {}).get("org") == org \
                and _drawn(out, other):
            return other
    return None


def render(name: str, state: dict, host: str | None) -> str:
    """The page for one site. `state`: its entry of `states` plus `waiting`."""
    from .site_picker import MARK as LOGO
    from .accounts.site_setup import STEPS
    app = f"../{slug(host)}/" if host else None
    step, removed = state.get("step"), state.get("removed")
    links = []
    if removed:
        title = f"{name} was removed"
        lines = [f"It was removed in Settings &gt; Add or remove sites on "
                 f"{esc(str(removed)[:10])} (UTC). Nothing is collected for it any more; "
                 "the data it had stays until an install admin purges it on the server."]
        if step and not state.get("done"):
            lines.append(f"Its setup had reached step {int(step)} of {STEPS}.")
        reload = ""
    else:
        title = f"{name} {WAITING}"
        if step and not state.get("done"):
            lines = [f"Its setup reached step {int(step)} of {STEPS}. Until log lines from "
                     "it arrive there is no dashboard to show, and no figure."]
            if app:
                links.append(f'<a class="sp-go" href="{esc(app)}#settings/sitesadmin?setup='
                             f'{quote(name)}">Continue setup</a>')
        elif step:
            lines = ["Its setup is finished, but nothing from it has reached Skald yet. "
                     "Until log lines arrive there is no dashboard to show, and no figure."]
            if app:
                links.append(f'<a class="sp-go" href="{esc(app)}#settings/sitesadmin?test='
                             f'{quote(name)}">Test the connection</a>')
        else:
            lines = ["Nothing from it has reached Skald yet. Until log lines arrive there "
                     "is no dashboard to show, and no figure."]
        lines.append("This page reloads itself. The dashboard appears here once the next run "
                     "has drawn it, within a few minutes.")
        if app:
            links.append(f'<a href="{esc(app)}{GUIDE}">If a connection does not work</a>')
        if links and app:
            lines.append("Setting up a site is for the organisation's owners and admins.")
        reload = f'<meta http-equiv="refresh" content="{RELOAD}">'
    links.append('<a href="../">All sites</a>')
    body = "".join(f"<p>{line}</p>" for line in lines)
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'{MARK}{reload}<meta name="robots" content="noindex, nofollow, noarchive">'
        '<meta name="referrer" content="no-referrer"><meta name="color-scheme" content="light dark">'
        f"<title>{esc(title)} · Skald</title><style>{CSS}</style></head><body>"
        f'<header class="sp-top">{LOGO}Skald</header><main>'
        f'<div class="sp-box" role="status"><h1>{esc(title)}</h1>{body}'
        f'<p class="sp-acts">{"".join(links)}</p></div></main></body></html>\n')


def write_missing(out, sites: list[dict], config: dict, config_path, err=None) -> list[Path]:
    """Write the page for every waiting or removed site with no page of its
    own. `sites`: sites.json's list (multisite.describe). Never raises: a
    failure is said through `err` and the dashboard is unharmed."""
    if out is None:
        return []
    try:
        return _write(Path(out), sites, config, config_path)
    except Exception as why:            # noqa: BLE001 - never the dashboard's redraw
        if err is not None:
            err(f"setup pages: {type(why).__name__}: {why}")
        return []


def _write(out: Path, sites: list[dict], config: dict, config_path) -> list[Path]:
    known = states(config, config_path)
    listed = {s["name"]: s for s in sites if isinstance(s, dict) and s.get("name")}
    order = list(listed) + sorted(set(known) - set(listed))
    written = []
    for name in order:
        state = dict(known.get(name) or {})
        removed = state.get("removed") and state.get("made_here") and name not in listed
        waiting = bool((listed.get(name) or {}).get("waiting"))
        if not (removed or waiting):
            continue
        page = out / slug(name) / "index.html"
        if page.exists() and not _ours(page):
            continue                    # a real page (or the first-page notice): never replaced
        if not removed:
            state["removed"] = None
        text = render(name, state, host_of(name, known, order, out))
        if page.exists():
            try:
                if page.read_text(encoding="utf-8") == text:
                    continue
            except OSError:
                pass
        write_atomic(page, text)
        written.append(page)
    return written

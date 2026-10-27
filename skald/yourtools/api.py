"""The dashboard's routes for the figures from your tools (sessions mode only).

Served by the refresh helper for every site page, `/traffic/<site>/[<view>/]...`,
with integrations_api.py's rules (signed in; same-origin and the CSRF header on
every POST; each change in the audit log, never a key; an organisation whose plan
is locked reads but cannot change):

  GET  integrations/yourtools/figures  any member of the site: each connected tool's
                                       state, freshness and figures (Overview's
                                       "From your tools" card). No key, no error text.
                                       Under integrations/ so the nginx location that
                                       reaches the helper needs no change
  GET  integrations/yourtools[?site=]  admins: every tool Skald knows, its state, where
                                       its key lives and its robot's address (never
                                       the key), its options, what Skald suggests,
                                       its figures (Settings > Leads & tools)
  POST integrations/yourtools/key      {site, tool, key, options, replace}: the "Me"
                                       road: a pasted key, checked by the tool's
                                       adapter and kept 0600 (keys.py); the tool on.
                                       A key Skald has already: 409 unless replace
  POST integrations/yourtools/set      {site, tool, options}: the options alone (GA4's
                                       property; key "search": the Search Console key)
  POST integrations/yourtools/pause    {site, tool}: off; key, answers, figures stay
  POST integrations/yourtools/remove   {site, tool}: the key taken out, the tool off;
                                       its answers and figures stay
  POST integrations/yourtools/sync     {site, tool}: "Sync now", in the background;
                                       at most once in SYNC_MINUTES per site and tool

`view(config, folder, site, admin)` is the answer's core, for MCP's your_tools too.
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import auth_api, integrations_api as base
from ..auth_api import answer, csrf_ok, read_json, text
from ..conversions import secrets_store
from . import adapters, conn, get, keys, store
from .base import BadKey
from .names import COUNTED_FROM, TOOL_FLAGS

PATH = re.compile(base.PAGE + r"(?P<act>integrations/yourtools"
                              r"(?:/(?:figures|key|set|pause|remove|sync))?)$")
GETS = {"integrations/yourtools/figures", "integrations/yourtools"}
MEMBERS = "integrations/yourtools/figures"
SYNC_MINUTES = 10
MOST = 16 * 1024
ROOT = Path(__file__).resolve().parents[2]


def match(path: str):
    path = path.split("?", 1)[0]
    return None if ".." in path else PATH.match(path)


def is_yourtools(path: str) -> bool:
    return match(path) is not None


def spawn(c, site: str, tool: str) -> None:
    """`skald --site SITE tools sync --tool T` in the background. Replaced in tests."""
    if c.config_path is None:
        raise OSError("the helper does not know its config file")
    log = conn.folder(c.folder) / f"{site}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as out:
        subprocess.Popen([sys.executable, str(ROOT / "bin/skald"), "--config", str(c.config_path),
                          "--site", site, "tools", "sync", tool], cwd=str(ROOT),
                         stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                         start_new_session=True)


def handle(h, write: bool, config, live_dir, allowed: set[str], same_origin,
           config_path=None) -> None:
    if not auth_api.sessions_mode(config):
        return answer(h, 404, {"ok": False, "error": "not found"})
    m = match(h.path)
    act = m.group("act")
    if write == (act in GETS):
        return answer(h, 405, {"ok": False, "error": "wrong method"})
    if write and not same_origin(h.headers, allowed):
        return answer(h, 403, {"ok": False, "error": "same-origin requests only"})
    db = auth_api.open_db(config, live_dir)
    if db is None:
        return answer(h, 503, {"ok": False, "error": "accounts are not set up here"})
    try:
        from ..accounts import sessions, users
        session = sessions.resolve(db, auth_api.cookie_of(h.headers))
        if session is None:
            return answer(h, 401, {"ok": False, "error": "Sign in first."})
        if write and not csrf_ok(session, h.headers):
            return answer(h, 403, {"ok": False, "error": "The page is out of date. "
                                                         "Reload it and try again."})
        role, org = users.site_role(db, session["user_id"], m.group("site"))
        if role is None and not session["install_admin"]:
            return answer(h, 403, {"ok": False, "error": "You are not a member here."})
        c = base.Ctx(h, db, session, m.group("site"), role, org, config, live_dir, config_path)
        if act == MEMBERS:
            return c.ok(**view(base._site_config(c, c.site), c.folder, c.site, admin=False))
        if not (role in base.ADMIN or c.install_admin):
            return c.no(403, "Tools are for admins.", role=role)
        form = {}
        if write:
            form = read_json(h, MOST)
            if form is None:
                return None
        return ROUTES[act](c, form)
    finally:
        db.close()


# ---------------------------------------------------------------- reading

def _flags(flags: dict) -> list[str]:
    """What the tool said about its own answer, in plain words."""
    return [TOOL_FLAGS.get(k, k) for k, v in sorted((flags or {}).items()) if v]


def _figure(f: dict) -> dict:
    return {"name": f["name"], "label": f["label"] or f["name"], "dim": f["dim"],
            "value": f["value"]}


def tool_view(config: dict, folder, site: str, tool: str, part: dict, db, admin: bool,
              now=None) -> dict:
    """One tool's state, freshness and figures."""
    adapter = get(tool)
    key = keys.state(config, folder, site, tool, part.get("options"))
    st = conn.status(part, bool(key.get("set")), now)
    out = {"id": tool, "name": adapter.name, "state": st["state"], "pill": st["pill"],
           "words": st["words"], "last_ok": st["last_ok"], "ago": st["ago"],
           "counted_from": f"{COUNTED_FROM}: {adapter.name}", "reports": {}, "headline": []}
    if admin:
        out.update(error=st.get("error"), last_try=st.get("last_try"),
                   key={k: key.get(k) for k in ("set", "where", "who", "problem")},
                   in_env=keys.in_env(config, site, tool), options=part.get("options") or {},
                   audit=part.get("audit"))
    if st["state"] == "withheld":
        out["withheld"] = ("Withheld: Skald's recheck of the stored answer did not match "
                           "(skald tools audit). Nothing from this tool is shown until it does.")
        return out
    if db is None:
        return out
    got = store.latest(db, site, tool)
    totals = []
    for r in got:
        figs = [_figure(f) for f in r["figures"]]
        out["reports"][r["report"]] = {"start": r["start"], "end": r["end"], "note": r["note"],
                                       "fetched_at": r["fetched_at"],
                                       "flags": _flags(r["flags"]), "figures": figs}
        if r["report"] == "totals":
            totals = r["figures"]
    from .base import Figure
    picked = adapter.headline([Figure(name=f["name"], value=f["value"], label=f["label"],
                                      dim=f["dim"]) for f in totals])
    out["headline"] = [{"name": f.name, "label": f.label or f.name, "value": f.value}
                       for f in picked]
    first = out["reports"].get("totals") or next(iter(out["reports"].values()), None)
    if first:
        out["period"] = {"start": first["start"], "end": first["end"], "note": first["note"]}
    if admin and got:
        out["more"] = more(adapter, config, folder, site, db, got)
    return out


def more(adapter, config: dict, folder, site: str, db, got: list[dict]) -> dict:
    """The admins' extra lines and people of a tool (Adapter.more), from its newest
    answers. A failure is one plain line, never the page's failure."""
    answers = [{**{k: r[k] for k in ("report", "start", "end", "fetched_at")},
                "body": store.body(db, r["id"]) or {}} for r in got]
    try:
        return adapter.more({"config": config, "folder": folder, "site": site,
                             "answers": answers}) or {}
    except Exception as why:            # noqa: BLE001 - a line, never the drawer
        return {"lines": [f"Skald could not work this out ({type(why).__name__})."]}


def view(config: dict, folder, site: str, admin: bool, now=None) -> dict:
    """{"tools": [...], "connected": n, "known": [...]}: every tool switched on
    (admin: every tool Skald knows), each with its state and figures."""
    parts = conn.load(folder, site)
    db = store.reader(folder)
    tools = []
    try:
        for tool in adapters():
            part = parts.get(tool) or {}
            if not admin and not part.get("on"):
                continue
            tools.append(tool_view(config, folder, site, tool, part, db, admin, now))
    finally:
        if db is not None:
            db.close()
    return {"site": site, "tools": tools,
            "connected": sum(1 for t in tools if t["state"] != "off")}


def states(config: dict, folder, site: str, now=None) -> list[dict]:
    """[{tool, name, state, words}] for every tool Skald knows: the set-up
    lines' answer (GET integrations' `yourtools`, setup_items.tool_line)."""
    parts = conn.load(folder, site)
    out = []
    for tool, adapter in adapters().items():
        part = parts.get(tool) or {}
        key = keys.state(config, folder, site, tool, part.get("options"))
        st = conn.status(part, bool(key.get("set")), now)
        out.append({"tool": tool, "name": adapter.name, "state": st["state"],
                    "words": st["words"]})
    return out


def overview(c, form):
    site = base._target(c, form)
    if site is None:
        return None
    conf = base._site_config(c, site)
    got = view(conf, c.folder, site, admin=True)
    from ..accounts import site_setup
    found = (site_setup.get(c.db, site) or {}).get("found")
    for t in got["tools"]:
        adapter = get(t["id"])
        t.update(key_words=adapter.key_words, permission=adapter.permission,
                 make_key=adapter.make_key, suggest=adapter.suggest(found),
                 shares_key=adapter.shares_key, notes=list(adapter.notes),
                 option_specs={k: {"label": o.label, "words": o.words, "required": o.required,
                                   "example": o.example} for k, o in adapter.options.items()})
    return c.ok(**got, sync_minutes=SYNC_MINUTES)


# ---------------------------------------------------------------- changing

def _tool(c, form) -> str | None:
    tool = text(form, "tool", 20)
    if get(tool) is None:
        c.no(400, f"Name one of the tools: {', '.join(adapters())}.")
        return None
    return tool


def _options(form) -> dict:
    got = form.get("options")
    return {str(k)[:40]: str(v)[:200] for k, v in got.items()} if isinstance(got, dict) else {}


def key(c, form):
    site = base._change_target(c, form)
    tool = _tool(c, form) if site else None
    if tool is None:
        return None
    raw = form.get("key")
    if not isinstance(raw, str) or not raw.strip():
        return c.no(400, "Paste the key.")
    from .sync import connect
    try:
        got = connect(base._site_config(c, site), c.folder, site, tool, _options(form),
                      str(c.uid), key=raw, replace=form.get("replace") is True)
    except BadKey as why:
        return c.no(400, str(why))
    except ValueError as why:
        return c.no(409, str(why))
    except secrets_store.Exposed:
        return c.no(500, "Skald's secrets file is not private on its server, so nothing was "
                         "kept. Ask whoever runs Skald to fix it.")
    except OSError:
        return c.no(503, "The server has no secrets file. Ask whoever runs Skald.")
    c.log("tools.key", site, f"{get(tool).name}: key {'replaced' if got['replaced'] else 'kept'}"
                             + (f" ({got['who']})" if got["who"] else "") + " (pasted)")
    return c.ok(**got)


def set_options(c, form):
    site = base._change_target(c, form)
    tool = _tool(c, form) if site else None
    if tool is None:
        return None
    from .sync import connect
    try:
        got = connect(base._site_config(c, site), c.folder, site, tool, _options(form),
                      str(c.uid))
    except ValueError as why:
        return c.no(400, str(why))
    opts = (conn.load(c.folder, site).get(tool) or {}).get("options") or {}
    c.log("tools.set", site, f"{get(tool).name}: on; " +
          ", ".join(f"{k} {v}" for k, v in sorted(opts.items())))
    return c.ok(**got)


def pause(c, form):
    site = base._change_target(c, form)
    tool = _tool(c, form) if site else None
    if tool is None:
        return None
    from .sync import pause as off
    off(c.folder, site, tool)
    c.log("tools.pause", site, f"{get(tool).name}: paused; its key and figures stay")
    return c.ok(tool=tool, paused=True)


def remove(c, form):
    site = base._change_target(c, form)
    tool = _tool(c, form) if site else None
    if tool is None:
        return None
    conf = base._site_config(c, site)
    if keys.in_env(conf, site, tool):
        return c.no(409, "This key is kept in the server's environment; only whoever runs "
                         "Skald can remove it.")
    try:
        gone = keys.remove(conf, c.folder, site, tool)
    except secrets_store.Exposed:
        return c.no(500, "Skald's secrets file is not private on its server. Ask whoever "
                         "runs Skald to fix it.")
    from .sync import pause as off
    off(c.folder, site, tool)
    c.log("tools.remove", site, f"{get(tool).name}: key removed; its figures stay")
    return c.ok(tool=tool, removed=gone)


def sync_now(c, form):
    site = base._change_target(c, form)
    tool = _tool(c, form) if site else None
    if tool is None:
        return None
    part = conn.load(c.folder, site).get(tool) or {}
    if not part.get("on"):
        return c.no(409, "Connect this tool first.")
    now = datetime.now(timezone.utc)
    asked = conn.parse(part.get("asked_at"))
    if asked is not None:
        wait = asked + timedelta(minutes=SYNC_MINUTES) - now
        if wait > timedelta(0):
            return c.no(429, f"Asked a moment ago: try again in "
                             f"{int(wait.total_seconds() // 60) + 1} minutes.",
                        retry_after=int(wait.total_seconds()))
    conn.update(c.folder, site, tool, asked_at=conn.now_text(now))
    try:
        spawn(c, site, tool)
    except OSError as why:
        return c.no(503, f"The sync could not start ({why.strerror or why}).")
    c.log("tools.sync", site, f"{get(tool).name}: sync now")
    return c.ok(started=True)


ROUTES = {"integrations/yourtools": overview, "integrations/yourtools/key": key,
          "integrations/yourtools/set": set_options, "integrations/yourtools/pause": pause,
          "integrations/yourtools/remove": remove, "integrations/yourtools/sync": sync_now}

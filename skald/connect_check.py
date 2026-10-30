"""Has it arrived yet? (2.44): one answer, in plain words, for every "connect" journey where
Skald gives someone something to do: a line for an AI agent, an install command, a snippet,
a page for a developer, a webhook address, a key.

The owner (2026-10-27): "Status does not get updated, and it's very confusing then ...
wherever you have a command, 'copy this and give it to Claude Code', there should be a test
button." Every such line, command, snippet, share page and webhook address now has a pill and
a sentence that update by themselves, and a Test button beside it (js/ui/live.js arrivedBox).
This module answers both.

  POST <page>/sites/arrived {site, what, press?}
       -> {test: {verdict: ok | wait | bad, head, says, fix, steps, tech, at, final}}

`what` names the thing (KINDS):

  logs              the access log (any road): setup_live.facts and its verdict
  agent:<link id>   an agent line: opened, keys taken, reported (kit/agent.py), and the
                    first data when its jobs include the logs
  hook:<tool>       a tool's webhook (lead, json, calendly, calcom, stripe, typeform,
                    hubspot): conversions/roads.hook_states. 2.44.1: good only after a
                    real delivery accepted since the key was saved; a passing Test
                    proves only the address (hook_keys.py)
  tag               the script tag: its events (connections_api.beacon_status)
  search            Search Console and Bing: the saved property and the sync's state
  tool:<id>         one of your own tools (yourtools: ga4, vercel, calendly, resend)
  share:<ref>       a "Share with your developer" page: opened, the secret taken, then
                    what its task brings (logs, the tag, the hook)
  journeys          recorded journeys: sessions received (recorded/status.py)
  token:<id>        an API or MCP token: first and last use (accounts/apitokens.py)

The head says the state; `says` what it means; `fix` the one next thing to do; `tech` the
technical words (behind "Details"); `steps` the agent's or developer's progress where Skald
knows it; `final` true when nothing more can change (a cancelled or expired line) so the page
stops asking. A plain poll is free; `press: true` (the Test button) is counted, at most
setup_live.CHECK_PER_HOUR per admin an hour, and runs the fuller check where one exists.

Routed by sites_api.py with its session, role (owner or admin), same-origin and CSRF checks.
Nothing here counts a figure: it reads what the endpoint, the hooks and the syncs already keep.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from . import setup_live
from .auth_api import text

HOOK_NEXT = {
    "lead": "Send your site's form once: your server tells Skald about it.",
    "json": "Run your Zap, scenario or workflow once.",
    "calendly": "Book a test call on your Calendly page.",
    "calcom": "Book a test call on your Cal.com page.",
    "stripe": "Make a test payment in Stripe (test mode is fine), or wait for the next sale.",
    "typeform": "Send one answer to your form.",
    "hubspot": "Make a test contact in HubSpot.",
}
SHARE_TASK = {"send": "logs", "script": "tag", "hook": "hook", "nextjs": "logs"}


def _stamp(t: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if t is None else t, timezone.utc) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")


def _hm(iso) -> str:
    return f"{str(iso)[11:16]} UTC" if iso else ""


def _out(verdict: str, head: str, says: str | None = None, fix: str | None = None,
         steps: list | None = None, tech: str | None = None, final: bool = False) -> dict:
    return {"verdict": verdict, "head": head, "says": says, "fix": fix, "steps": steps or [],
            "tech": tech, "final": final, "at": _stamp()}


def _folder(c) -> Path:
    from .conversions import hooks
    return Path(c.live_dir) if c.live_dir is not None else \
        hooks.history_folder(c.config, c.config_path)


def _site_config(c, site: str) -> dict:
    from .conversions import hooks
    return hooks.site_configs(c.config, c.config_path).get(site) or c.config


# ------------------------------------------------------------------ the logs

def logs(c, site: str, press: bool = False, lid: str = "") -> dict:
    """The access log, by whatever road: setup_live's own verdict (Check now's)."""
    from .accounts import site_setup
    from . import ingest, ingest_status, site_verify
    if press:
        got = setup_live.run_check(c.config, c.live_dir, c.config_path, c.db, site, lid)
    else:
        f = setup_live.facts(c.config, c.live_dir, c.config_path, site)
        refusal = ingest_status.status(ingest.history_folder(c.config, c.live_dir),
                                       site).get("last_refusal")
        got = setup_live.verdict(site_setup.get(c.db, site), site_verify.shown(c.db, site),
                                 setup_live.line_of(_folder(c), site, lid), f, refusal, site)
    head = got["head"]
    if got["verdict"] == "wait" and head == "No data yet.":
        head = "Waiting: no data has arrived yet."
    return _out(got["verdict"], head, got.get("says"), got.get("fix"), tech=got.get("tech"))


def _data(c, site: str) -> dict:
    return setup_live.facts(c.config, c.live_dir, c.config_path, site)


# ------------------------------------------------------------------ an agent line

AGENT_STEPS = (("opened", "Your agent opened the line"), ("keys", "Your agent took its keys"),
               ("reported", "Your agent reported what it did"))


def agent(c, site: str, lid: str, press: bool = False) -> dict | None:
    from .kit import agent as kit
    if not kit.LINK_ID.match(lid or ""):
        return None
    st = kit.status(_folder(c), site, lid)
    state = st["state"]
    if state == "unknown":
        return _out("bad", "Skald does not know this line.", "It may belong to another site.",
                    "Make a new line and give it to your agent.", final=True)
    jobs = st.get("line_jobs") or []
    f = _data(c, site) if "logs" in jobs else None
    steps = [{"id": "opened", "words": AGENT_STEPS[0][1], "done": bool(st.get("opened_at")),
              "at": st.get("opened_at")},
             {"id": "keys", "words": AGENT_STEPS[1][1], "done": bool(st.get("keys_at")),
              "at": st.get("keys_at")},
             {"id": "reported", "words": AGENT_STEPS[2][1], "done": bool(st.get("reported_at")),
              "at": st.get("reported_at")}]
    if f is not None:
        steps.append({"id": "data", "words": "The first data arrived", "done": f["arrived"],
                      "at": f.get("first_at") or (f.get("newest_at") if f["arrived"] else None)})
    if state == "cancelled":
        return _out("bad", "This line was cancelled.", None,
                    "Make a new line if the work is not done yet.", steps, final=True)
    if state == "expired":
        return _out("bad", "The line ran out before your agent used it.", None,
                    "Make a new line and give it to your agent.", steps, final=True)
    if state == "waiting":
        return _out("wait", "Waiting for your agent: it has not opened the line yet.",
                    "Nothing has happened on this line so far.",
                    "Paste the line into Claude Code or Codex, opened in the site's own folder "
                    "or on its server.", steps)
    if state == "opened":
        return _out("wait", "Your agent read the steps but has not taken its keys yet.",
                    None, "It may be waiting for your answer in its chat.", steps)
    report = st.get("report") or {}
    done = report.get("jobs") or {}
    left = [j for j in jobs if done.get(j) == "left"]
    if not st.get("reported_at"):
        if f and f["arrived"]:
            return _out("ok", "Data is arriving.", _recent(f),
                        "Your agent will report what else it did when it finishes.", steps)
        return _out("wait", "Your agent took its keys and is working.",
                    "It reports here by itself when it finishes.", None, steps)
    if f is not None and not f["arrived"]:
        return _out("wait", "Your agent finished, but no data has arrived yet.",
                    _no_data(c, site), None, steps)
    says = _recent(f) if f else None
    if left:
        return _out("wait", "Your agent finished, with something left for you.", says,
                    "Open its report below: it says what is left and why.", steps)
    return _out("ok", "Done: your agent finished its work.", says, None, steps)


def _recent(f: dict | None) -> str | None:
    if not f:
        return None
    if f.get("recent"):
        return f"{f['recent']:,} lines in the last 15 minutes, the newest at {_hm(f.get('newest_at'))}."
    if f.get("events"):
        return f"The script tag sent {f['events']:,} events, the newest at {_hm(f.get('newest_at'))}."
    if f.get("arrived"):
        return f"Data arrived before; the newest at {_hm(f.get('newest_at'))}."
    return None


def _no_data(c, site: str) -> str:
    from .accounts import site_setup
    method = (site_setup.get(c.db, site) or {}).get("method") or ""
    return setup_live.NO_DATA.get(method, "Usually it starts within 2 minutes after the data "
                                          "road is set up.").format(site=site)


# ------------------------------------------------------------------ a webhook

# What proves a tool's key: a real event of its own (Skald's Test proves only the address).
HOOK_PROVE = {
    "lead": "send your site's form once",
    "json": "run your Zap, scenario or workflow once",
    "calendly": "make a test booking",
    "calcom": "make a test booking",
    "stripe": "make a test payment (test mode is fine)",
    "typeform": "send one answer to your form",
    "hubspot": "make a test contact",
}


def hook(c, site: str, tool: str, press: bool = False) -> dict | None:
    """A tool's webhook. 2.44.1: good only once a real delivery (never a test of
    Skald's own, which is signed with the key Skald has and proves only the
    address) was accepted since the key was saved (hook_keys.facts); refusals
    since then say why, with the fix (roads.refused_words, hook_states' fix)."""
    from .conversions import TOOLS, store
    from .conversions.roads import ACCEPTED, KEY_REFUSALS, hook_states, key_word, last_test
    from .hook_keys import facts
    if tool not in TOOLS:
        return None
    folder = _folder(c)
    path = store.path_for(c.config, folder)
    db = store.connect(path) if path is not None and Path(path).exists() else None
    try:
        states = {s["tool"]: s for s in hook_states(_site_config(c, site), folder, site, db)}
        f = facts(c.db, db, folder, site, tool)
        tested = last_test(db, site, tool)
    finally:
        if db is not None:
            db.close()
    t = states.get(tool) or {}
    name = t.get("name") or tool
    st = t.get("state")
    kw = key_word(tool)
    since, last = f["since_saved"], f["last_real"]
    # The saved time unknown (a key set on the server): the newest real delivery says.
    proven = since["accepted"] > 0 if since is not None else \
        bool(last and last["outcome"] in ACCEPTED)
    refused = (since["refused"] + since["unsigned"]) > 0 if since is not None else \
        bool(last and last["outcome"] in KEY_REFUSALS)
    test_ok = bool(tested and tested["outcome"] == "test" and
                   (not f["saved_at"] or tested["received_at"] >= f["saved_at"]))
    steps = [{"id": "secret", "words": f"The {kw} is saved in Skald",
              "done": bool(t.get("set")), "at": f["saved_at"]},
             {"id": "test", "words": "Skald's own test reached the address", "done": test_ok,
              "at": tested["received_at"] if test_ok else None},
             {"id": "real", "words": f"A real delivery from {name} was accepted with the {kw}",
              "done": proven, "at": last["at"] if proven and last else None}]
    tech = f"{name}: {t.get('words')}" if t.get("words") else None
    if st in ("missing", "exposed"):
        return _out("bad", f"{name} cannot be read yet.", t.get("words"), t.get("fix"), steps, tech)
    if st == "needs_secret":
        return _out("wait", f"Not set up yet: {name}'s {kw} is not saved here.", None,
                    f"Make or paste the {kw}, then add the address in {name}.", steps, tech)
    if last and last["outcome"] in KEY_REFUSALS and refused:
        held = f.get("held") or 0
        says = last["words"][:1].upper() + last["words"][1:] + "."
        if held:
            says += (f" {held} refused deliver{'y is' if held == 1 else 'ies are'} held for "
                     f"24 hours: once the right {kw} is saved, Skald takes "
                     f"{'it' if held == 1 else 'them'} in.")
        return _out("bad", f"{name} is sending, but Skald refuses it.", says, t.get("fix"),
                    steps, tech)
    if proven:
        attention = t.get("attention")
        return _out("wait" if attention else "ok",
                    f"Connected. The last delivery from {name} came at {_hm(last['at'])} "
                    f"on {str(last['at'])[:10]}." if last and last.get("at") else
                    f"Connected: deliveries from {name} arrive.",
                    t.get("fix") if attention else None, None, steps, tech)
    prove = HOOK_PROVE.get(tool, "send one real event")
    if test_ok:
        says = f"Skald's address works. Only a real {name} event proves the {kw}: {prove}."
    elif f["saved_at"] and last:
        says = f"Nothing real has arrived since the {kw} was saved."
    else:
        says = f"Check that the address is saved in {name}."
    return _out("wait", f"Waiting for {name}: nothing real has arrived yet.", says,
                HOOK_NEXT.get(tool), steps, tech)


# ------------------------------------------------------------------ the script tag

def tag(c, site: str, press: bool = False) -> dict:
    from . import connections_api
    got = connections_api.beacon_status(c.config, c.live_dir, c.config_path, site)
    if got is None:
        return _out("bad", "The script tag is switched off on this Skald.", None,
                    "Ask whoever runs Skald to switch the tag on.", final=True)
    steps = [{"id": "open", "words": "A page with the tag opened", "done":
              bool(got.get("last_open_at")), "at": got.get("last_open_at")},
             {"id": "events", "words": "The tag's events arrived", "done": bool(got.get("events")),
              "at": got.get("updated_at")}]
    if got.get("events"):
        return _out("ok", "The script tag is working.",
                    f"{int(got['events']):,} events on {got.get('day')}, the newest at "
                    f"{_hm(got.get('updated_at'))}.", None, steps)
    if got.get("last_open_at"):
        return _out("wait", "A page with the tag opened, but no event arrived yet.",
                    "Events come once someone reads, clicks or sends a form.",
                    f"Open {site}, click a link, then press Test again.", steps)
    return _out("wait", "Waiting: no page with the tag has reached Skald yet.", None,
                f"Open {site} in a browser, then press Test again. If still nothing, view the "
                "page's source and look for skald.js.", steps)


# ------------------------------------------------------------------ search

def search_words(part: dict, engine: str = "google") -> dict:
    """One engine's state in plain words (the page's live-words.js searchState, server side)."""
    tool = {"google": "Search Console", "bing": "Bing Webmaster Tools"}[engine]
    if not part.get("connected"):
        return _out("wait", f"{tool} is not connected yet.", None,
                    "Open Search Console & Bing in Settings › Leads & tools and connect it.")
    st, days = part.get("status") or {}, int((part.get("summary") or {}).get("days") or 0)
    b = st.get("backfill") or {}
    if b.get("state") in ("running", "queued"):
        got = f"{b.get('done') or 0:,} of {b['of']:,} weeks" if b.get("of") else "starting"
        return _out("ok", f"Connected. Getting the history: {got}.",
                    f"{days:,} days are here so far." if days else
                    "The figures appear as each week arrives.")
    if st.get("error"):
        return _out("bad", "Connected, but the last sync failed.",
                    f"The {days:,} days already here stay." if days else None,
                    "Open Search Console & Bing in Settings › Leads & tools.", tech=st["error"])
    if not days:
        return _out("wait", "Connected. Waiting for the first figures.",
                    "They arrive with the first sync, usually within a few minutes." if
                    not st.get("last_sync") else
                    f"Synced, but {tool} has no figures for this site yet. Google starts a new "
                    "property's figures a few days after it is verified.")
    return _out("ok", f"Connected. {days:,} days of {tool}'s figures are here.",
                f"Last synced at {_hm(st.get('last_sync'))}." if st.get("last_sync") else None)


def search(c, site: str, press: bool = False) -> dict:
    from . import settings_store
    from .search import auto, days, state
    from .store import History
    # 2.44: a property someone asked for and Google does not show yet: look again (a press
    # looks now; a poll at most once a minute), and connect it once it shows.
    wanted = (state.load(_folder(c), site).get("auto") or {})
    if wanted.get("state") in ("waiting", "failed", "no_key"):
        got = auto.run(c.config, c.config_path, _folder(c), c.db, site, force=press) or {}
        if got.get("state") != "connected":
            return _out("bad" if got.get("state") == "no_key" else "wait",
                        got.get("words") or "Waiting for Google.",
                        "Skald checks again by itself every minute and connects it as soon as "
                        "Google shows it.", None if got.get("state") == "no_key" else
                        "In Search Console, Settings › Users and permissions: Skald's robot "
                        "address must be there, Restricted, on this site's property.",
                        tech=got.get("tech"))
    conf = _site_config(c, site)
    found = settings_store.explain(conf, site, c.db)
    saved = state.load(_folder(c), site)
    db_path = (c.config.get("_resolved") or {}).get("history_db") or _folder(c) / "history.sqlite"
    parts = {}
    for engine, key in (("google", "search.google_property"), ("bing", "search.bing_site")):
        summary = {}
        if Path(db_path).exists():
            try:
                with History.reader(db_path) as history:
                    summary = days.summary(history.db, site, engine)
            except Exception:           # noqa: BLE001 - an older or busy file
                summary = {}
        parts[engine] = {"connected": (found.get(key) or {}).get("value"),
                         "status": saved.get(engine) or {}, "summary": summary}
    one = parts["google"] if parts["google"]["connected"] or not parts["bing"]["connected"] \
        else parts["bing"]
    got = search_words(one, "google" if one is parts["google"] else "bing")
    if wanted.get("state") == "connected" and wanted.get("note") and one is parts["google"]:
        got["says"] = " ".join(x for x in (wanted["note"], got.get("says")) if x)
    return got


# ------------------------------------------------------------------ your tools

def tool(c, site: str, tid: str, press: bool = False) -> dict | None:
    from .yourtools.api import states
    got = {s["tool"]: s for s in states(_site_config(c, site), _folder(c), site)}
    t = got.get(tid)
    if t is None:
        return None
    name, st = t["name"], t["state"]
    if st == "answering":
        return _out("ok", f"Connected. {name} is answering.", None, None, tech=t["words"])
    if st in ("failing", "stopped", "withheld"):
        return _out("bad", f"{name} is connected but not answering.", t["words"],
                    f"Open {name} in Settings › Leads & tools › Your tools.", tech=t["words"])
    if st == "no_key":
        return _out("wait", f"Waiting for {name}'s key.", None,
                    f"Paste the key {name} gave, or give the line to your agent.")
    if st == "waiting":
        return _out("wait", f"Connected. Waiting for {name}'s first answer.",
                    "Skald asks it every few hours; the first answer usually comes within a few "
                    "minutes.")
    return _out("wait", f"{name} is not connected yet.", None,
                f"Connect it in Settings › Leads & tools › Your tools.")


# ------------------------------------------------------------------ a page for a developer

def share(c, site: str, ref: str, press: bool = False) -> dict | None:
    from . import share_links
    entry = share_links.get_ref(c.db, ref)
    if entry is None or entry.get("site") != site or entry.get("org_id") != c.org["id"]:
        return None
    steps = [{"id": "viewed", "words": "Your developer opened the page",
              "done": bool(entry.get("viewed_at")), "at": entry.get("viewed_at")}]
    if entry["task"] in ("send", "hook"):
        steps.append({"id": "secret", "words": "They took the secret", "done":
                      bool(entry.get("revealed_at")), "at": entry.get("revealed_at")})
    kind = SHARE_TASK.get(entry["task"], "logs")
    then = (hook(c, site, entry.get("method") or "lead") if kind == "hook" else
            tag(c, site) if kind == "tag" else logs(c, site))
    if then is not None:
        steps.append({"id": "arrived", "words": "It works: Skald received it",
                      "done": then["verdict"] == "ok", "at": then["at"] if then["verdict"] == "ok"
                      else None})
    if then is not None and then["verdict"] == "ok":
        return _out("ok", "Done: your developer finished.", then["head"], None, steps)
    if entry["state"] in ("revoked", "expired"):
        return _out("bad", f"This page was {'cancelled' if entry['state'] == 'revoked' else 'closed: it ran out'}.",
                    None, "Make a new link if the work is not done yet.", steps, final=True)
    if not entry.get("viewed_at"):
        return _out("wait", "Waiting for your developer: they have not opened the page yet.",
                    None, "Send them the link again, or ask whether it arrived.", steps)
    if len(steps) > 2 and not entry.get("revealed_at"):
        return _out("wait", "Your developer opened the page but has not taken the secret yet.",
                    None, None, steps)
    return _out("wait", "Your developer is on it: nothing has arrived yet.",
                (then or {}).get("says"), (then or {}).get("fix"), steps)


# ------------------------------------------------------------------ recorded journeys

def journeys(c, site: str, press: bool = False) -> dict:
    import sqlite3
    from .conversions import secrets_store
    from .conversions.store import path_for
    from .recorded import store as rstore
    from .recorded import TOOL
    folder = _folder(c)
    try:
        secret = secrets_store.find(_site_config(c, site), folder, site, TOOL)[0]
    except secrets_store.Exposed:
        return _out("bad", "Recorded journeys cannot be read yet.",
                    "The secrets file on the server is not private (0600).",
                    "Ask whoever runs Skald to fix the file's rights.")
    if not secret:
        return _out("wait", "Recorded journeys are not connected yet.", None,
                    "Connect them in Settings › Leads & tools › Recorded journeys.")
    last, n = None, 0
    path = path_for(c.config, folder)
    if path is not None and Path(path).is_file():
        db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
        try:
            if rstore.present(db):
                last = rstore.last_received(db, site)
                n = int(db.execute("SELECT COUNT(*) FROM recorded_events WHERE site = ?",
                                   (site,)).fetchone()[0])
        finally:
            db.close()
    steps = [{"id": "secret", "words": "The relay's secret is made", "done": True},
             {"id": "first", "words": "The first recorded session arrived", "done": bool(last),
              "at": last}]
    if not last:
        return _out("wait", "Waiting: no recorded session has arrived yet.", None,
                    "Open the site, agree to analytics in its banner, read two pages, then "
                    "press Test again.", steps)
    return _out("ok", "Connected. Recorded sessions arrive.",
                f"{n:,} events kept, the newest at {_hm(last)} on {str(last)[:10]}.", None, steps)


# ------------------------------------------------------------------ a token

def token(c, site: str, tid: str, press: bool = False) -> dict | None:
    from .accounts import apitokens
    row = next((t for t in apitokens.listing(c.db, c.org["id"]) if str(t.get("id")) == tid),
               None)
    if row is None:
        return None
    if row.get("revoked_at"):
        return _out("bad", "This key was revoked.", None, "Make a new one if it is still needed.",
                    final=True)
    if row.get("last_used"):
        return _out("ok", "Connected: your assistant used this key.",
                    f"Last used at {_hm(row['last_used'])} on {str(row['last_used'])[:10]}.")
    return _out("wait", "Waiting: your assistant has not used this key yet.", None,
                "Add it to your assistant, then ask it one question about this site.")


CHECKS = {"logs": lambda c, s, a, p: logs(c, s, p), "tag": lambda c, s, a, p: tag(c, s, p),
          "search": lambda c, s, a, p: search(c, s, p),
          "journeys": lambda c, s, a, p: journeys(c, s, p),
          "agent": lambda c, s, a, p: agent(c, s, a, p), "hook": lambda c, s, a, p: hook(c, s, a, p),
          "tool": lambda c, s, a, p: tool(c, s, a, p), "share": lambda c, s, a, p: share(c, s, a, p),
          "token": lambda c, s, a, p: token(c, s, a, p)}
KINDS = tuple(CHECKS)


def answer(c, site: str, what: str, press: bool = False) -> dict | None:
    """The answer for `what` (KINDS), or None when it names nothing known."""
    kind, _, arg = str(what or "").partition(":")
    fn = CHECKS.get(kind)
    if fn is None or (kind in ("agent", "hook", "tool", "share", "token") and not arg):
        return None
    return fn(c, site, arg.strip().lower(), press)


def route(c, form):
    from .connections_api import _site
    site = _site(c, text(form, "site", 200))
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    what = text(form, "what", 60)
    press = form.get("press") is True
    if press:
        from .accounts import limits
        key = f"arrived-check:{c.uid}"
        if limits.too_many(c.db, key, limit=setup_live.CHECK_PER_HOUR, minutes=60):
            return c.no(429, "Too many checks. Try again in a few minutes.")
        limits.note_failure(c.db, key)
    got = answer(c, site, what, press)
    if got is None:
        return c.no(400, f"Skald cannot check that: name one of {', '.join(KINDS)}.")
    return c.ok(test=got, what=what)


ROUTES = {"sites/arrived": route}

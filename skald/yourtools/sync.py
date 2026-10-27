"""The sync: each connected tool asked for its figures, by itself.

The container's scheduler runs `skald tools sync` every EVERY_HOURS hours, at a
lower CPU priority than its other jobs (docker/scheduler.py, SKALD_TOOLS_HOURS),
one site after another under each site's lock. For each tool that is on:

  1. its key (keys.find); none: the tool says "Needs its key", nothing is asked;
  2. its answers (adapter.fetch), each read into figures (adapter.figures)
     before anything is stored, so an answer Skald cannot read keeps nothing;
  3. the answers and figures kept in one transaction (store.keep);
  4. the recheck (recount.check), kept with the tool (conn.py `audit`);
  5. its freshness: last_ok, or the failure in plain words. A failure keeps the
     last good figures, shown with their age, and sends one mail per run of
     failures to the site's mail recipients.

A sync never touches the log's figures or history.sqlite.

The CLI (`skald tools ...`, per site; `--site` for one):

  status                       each tool's state, where its key lives (never the key)
  sync [--tool T]              ask the tools now
  audit [--tool T]             recheck every stored figure; exit 1 on a mismatch
  connect T [--option k=v] [--key-stdin] [--replace]
                               switch a tool on, with its options; the key from
                               stdin (never an argument), kept as the page keeps it
  pause T                      switch it off; its key, answers and figures stay
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path

from . import adapters, conn, get, keys, recount, store
from .base import BadKey, Unreachable

EVERY_HOURS = conn.EVERY_HOURS


@dataclass
class Job:
    """One site's sync. `opener` and `sleep` are for tests (no network)."""
    config: dict
    site: str
    folder: Path                        # the history's folder
    now: datetime
    out: object = print
    err: object = print
    opener: object = None
    sleep: object = time.sleep
    send: object = None                 # mail sender (failmail.send); tests hand one in


def run(job: Job, tools=None) -> int:
    """Sync every tool that is on (or `tools`), under the site's lock. 0 when
    every one answered (or none is on), 1 when one failed, 3 when busy."""
    wanted = [t for t in (tools or conn.on_tools(job.folder, job.site))]
    if not wanted:
        return 0
    try:
        with conn.lock(job.folder, job.site):
            return max(run_tool(job, tool) for tool in wanted)
    except conn.Busy as why:
        job.err(f"tools {job.site}: {why}")
        return 3


def run_tool(job: Job, tool: str) -> int:
    adapter = get(tool)
    part = conn.load(job.folder, job.site).get(tool) or {}
    if adapter is None:
        job.err(f"tools {job.site}: Skald has no tool {tool!r}")
        return 1
    if not part.get("on"):
        job.out(f"{adapter.name} {job.site}: not connected; skipped")
        return 0
    started = conn.now_text()
    options = dict(part.get("options") or {})
    try:
        key, where = keys.find(job.config, job.folder, job.site, tool, options)
    except keys.secrets_store.Exposed:
        return _failed(job, adapter, "secrets.json can be read by others; it must be 0600.")
    if not key:
        job.out(f"{adapter.name} {job.site}: no key yet; nothing asked")
        return 0
    try:
        answers = adapter.fetch(key, options, job.now, opener=job.opener, sleep=job.sleep)
        policy = people_policy(job)
        answers = [adapter.scrub(a, policy) for a in answers]
        read = [(a, adapter.figures(a)) for a in answers]
    except (Unreachable, BadKey) as why:
        return _failed(job, adapter, str(why))
    except Exception as why:            # noqa: BLE001 - one tool never stops the others
        return _failed(job, adapter, f"Skald could not read {adapter.name}'s answer "
                                     f"({type(why).__name__}). Tell whoever runs Skald.")
    db = store.connect(job.folder)
    try:
        with db:
            kept = [store.keep(db, job.site, tool, answer, figures, started)
                    for answer, figures in read]
            if adapter.latest_only:
                store.keep_only(db, job.site, tool, kept)
    finally:
        db.close()
    audit = recount.check(job.folder, job.site, tool).get(tool) or \
        {"ok": True, "problems": [], "answers": 0, "figures": 0, "checked": ""}
    ended = conn.now_text()
    conn.update(job.folder, job.site, tool, ok=True, last_try=ended, last_ok=ended,
                error=None, error_since=None, error_mailed=None, answers=len(read),
                audit={**audit, "at": ended})
    shown = sum(len(f) for _, f in read)
    job.out(f"{adapter.name} {job.site}: {len(read)} answer{'' if len(read) == 1 else 's'}, "
            f"{shown} figure{'' if shown == 1 else 's'}"
            + ("" if audit.get("ok") else f"; RECHECK FAILED: {audit['problems'][:1]}"))
    return 0 if audit.get("ok") else 1


def people_policy(job: Job) -> dict:
    """What the site keeps about people, for an adapter's scrub: names and emails
    or not (conversions.identity), and for how many days (privacy.keep_days, the
    People days), as the leads keep them (people/policy.py)."""
    from ..people import policy
    return {"identity": policy.identity_full(job.config, job.folder),
            "keep_days": policy.keep_days(job.config), "now": job.now}


def _failed(job: Job, adapter, why: str) -> int:
    job.err(f"{adapter.name} {job.site}: FAILED: {why}")
    before = conn.load(job.folder, job.site).get(adapter.id) or {}
    ended = conn.now_text()
    part = conn.update(job.folder, job.site, adapter.id, ok=False, last_try=ended,
                       error=why[:600], error_since=before.get("error_since") or ended)
    if not part.get("error_mailed") and _mail(job, adapter, why):
        conn.update(job.folder, job.site, adapter.id, error_mailed=conn.now_text())
    return 1


def _mail(job: Job, adapter, why: str) -> bool:
    """One plain mail about a tool that started failing. True when sent."""
    from .. import failmail
    try:
        cfg = failmail.mail_settings(job.config)
    except Exception as refused:        # noqa: BLE001 - no mail set up: the page shows it
        job.err(f"{adapter.name} {job.site}: no failure mail ({refused})")
        return False
    msg = EmailMessage()
    msg["Subject"] = f"{cfg['prefix']} {adapter.name} stopped answering for {job.site}".strip()
    msg["From"] = cfg["from"]
    msg["To"] = ", ".join(cfg["to"])
    msg["Date"] = format_datetime(job.now)
    msg["Message-ID"] = make_msgid(domain=cfg["from"].rsplit("@", 1)[-1].strip("> ") or None)
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content("\n".join([
        f"Skald could not get {job.site}'s figures from {adapter.name} "
        f"({job.now:%Y-%m-%d %H:%M} UTC).", "", f"Why: {why}", "",
        f"The figures it gave before stay, with their age. Skald asks again every "
        f"{EVERY_HOURS} hours; the first good answer clears this.",
        "Status and the fix: Settings > Leads & tools.", "",
        "One mail per run of failures: no more mails until it works again and then fails.",
    ]) + "\n")
    try:
        (job.send or failmail.send)(msg, cfg)
    except Exception as failed:         # noqa: BLE001
        job.err(f"{adapter.name} {job.site}: the failure mail could not be sent "
                f"({type(failed).__name__})")
        return False
    return True


# ---------------------------------------------------------------- connecting

def connect(config: dict, folder, site: str, tool: str, options: dict | None, who: str,
            key: str | None = None, replace: bool = False) -> dict:
    """Switch a tool on for a site, with its options and, when given, its key.
    {"tool", "who", "replaced"}; ValueError in plain words (a bad option, a
    key already kept without `replace`, a key kept in the environment);
    BadKey for a key the tool does not take; OSError without a secrets file."""
    adapter = get(tool)
    if adapter is None:
        raise ValueError(f"Skald has no tool {tool!r}. Tools: {', '.join(adapters())}.")
    before = conn.load(folder, site).get(tool) or {}
    clean = adapter.clean_options(options, before.get("options"))
    info, replaced = {}, False
    if key is not None:
        info = adapter.check_key(key)
        if keys.in_env(config, site, tool):
            raise ValueError(f"{adapter.name}'s key for {site} is kept in the server's "
                             "environment; only whoever runs Skald can change it.")
        have = keys.state(config, folder, site, tool)
        if have.get("set") and have.get("where") == "file" and not replace:
            raise ValueError(f"Skald has a {adapter.name} key for {site} already; it keeps "
                             "that one unless you ask to replace it.")
        replaced = bool(have.get("set") and have.get("where") == "file")
        keys.put(config, folder, site, tool, key)
        if clean.get("key") == keys.SHARED:     # its own key now, not the shared one
            clean.pop("key")
    now = conn.now_text()
    fields = dict(on=True, options=clean, paused_at=None)
    if not before.get("on"):
        fields.update(connected_at=now, connected_by=str(who))
    conn.update(folder, site, tool, **fields)
    return {"tool": tool, "who": info.get("who"), "replaced": replaced}


def pause(folder, site: str, tool: str) -> bool:
    """Switch a tool off; its key, answers and figures stay. True when it was on."""
    was = (conn.load(folder, site).get(tool) or {}).get("on")
    conn.update(folder, site, tool, on=False, paused_at=conn.now_text())
    return bool(was)


# ------------------------------------------------------------------- the CLI

def _job(ctx) -> Job:
    return Job(ctx.config, ctx.site, Path(ctx.db_path).parent,
               ctx.now.astimezone(timezone.utc), ctx.out, ctx.err)


def _status(ctx) -> int:
    folder = Path(ctx.db_path).parent
    parts = conn.load(folder, ctx.site)
    for tool, adapter in adapters().items():
        part = parts.get(tool) or {}
        key = keys.state(ctx.config, folder, ctx.site, tool, part.get("options"))
        st = conn.status(part, bool(key.get("set")))
        opts = ", ".join(f"{k} {v}" for k, v in (part.get("options") or {}).items())
        ctx.out(f"{adapter.name} {ctx.site}: {st['words']}"
                + (f"; {opts}" if opts else "")
                + (f"; key: {key['where']}" + (f" ({key['who']})" if key.get("who") else "")
                   if key.get("set") else "; no key")
                + (f"; last answer {st['last_ok']}" if st.get("last_ok") else "")
                + (f"; {st['error']}" if st.get("error") and st["state"] != "answering" else "")
                + (f"; key problem: {key['problem']}" if key.get("problem") else ""))
    return 0


def _options(given) -> dict:
    out = {}
    for one in given or ():
        name, eq, value = str(one).partition("=")
        if not eq:
            raise SystemExit(f"--option is name=value, not {one!r}")
        out[name.strip()] = value.strip()
    return out


def cmd(ctx) -> int:
    a = ctx.args
    folder = Path(ctx.db_path).parent
    if a.action == "status":
        return _status(ctx)
    if a.action == "audit":
        got = recount.check(folder, ctx.site, a.tool)
        for tool, part in got.items():
            n, f = part["answers"], part["figures"]
            ctx.out(f"{tool} {ctx.site}: {n} answer{'' if n == 1 else 's'}, "
                    f"{f} figure{'' if f == 1 else 's'}: "
                    + ("match" if part["ok"] else "MISMATCH"))
            for line in part["problems"]:
                ctx.out(f"  {line}")
        return 0 if all(p["ok"] for p in got.values()) else 1
    if a.action == "sync":
        return run(_job(ctx), [a.tool] if a.tool else None)
    if not a.tool:
        raise SystemExit(f"{a.action} needs the tool: {', '.join(adapters())}")
    if a.action == "pause":
        pause(folder, ctx.site, a.tool)
        ctx.out(f"{a.tool} {ctx.site}: paused; its key and figures stay")
        return 0
    key = sys.stdin.read() if a.key_stdin else None
    try:
        got = connect(ctx.config, folder, ctx.site, a.tool, _options(a.option), "cli",
                      key=key, replace=a.replace)
    except (ValueError, OSError) as why:
        ctx.err(f"{a.tool} {ctx.site}: not connected: {why}")
        return 1
    ctx.out(f"{a.tool} {ctx.site}: connected" + (f" ({got['who']})" if got["who"] else "")
            + ("; the old key was replaced" if got["replaced"] else ""))
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("tools", help="figures from your own tools (Google Analytics...): "
                                     f"the scheduler runs `tools sync` every {EVERY_HOURS} hours")
    p.add_argument("action", choices=("status", "sync", "audit", "connect", "pause"),
                   help="status; sync: ask the tools now; audit: recheck every stored figure; "
                        "connect TOOL: switch it on; pause TOOL: switch it off")
    p.add_argument("tool", nargs="?", help="the tool's id (ga4)")
    p.add_argument("--option", action="append", metavar="NAME=VALUE",
                   help="a connection's option, e.g. property=123456789")
    p.add_argument("--key-stdin", action="store_true",
                   help="read the key from stdin (never pass a key as an argument)")
    p.add_argument("--replace", action="store_true", help="replace a key Skald has already")
    p.set_defaults(run=cmd)

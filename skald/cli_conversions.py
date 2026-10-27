"""skald commands for incoming hooks and the conversions file.

    skald hooks secret SITE TOOL     make a hook's secret, keep it 0600, print it once
    skald hooks list                 each hook set up: its address, where its
                                     secret lives, its last deliveries
    skald hooks test SITE TOOL       post a signed sample (marked as a test:
                                     checked and read, never kept)
    skald conversions forget --email ADDRESS | --vid ID | --lead REF [--dry-run]
    skald conversions prune          drop what is past its keeping time
    skald conversions mark-test SITE [ID...] [--ref REF...] [--tool T] [--unmark]
                                     mark conversions as test (kept and listed,
                                     never counted), or not; audit-logged
    skald conversions remove SITE --ref REF [--stage S] [--action A] --why TEXT [--dry-run]
                                     soft-remove a ref's rows (kept in `removed`
                                     with when and why, never counted); audited
    skald conversions list SITE [--test]  the latest conversions with their ids

Registered through cli_more.MODULES ("cli_conversions").
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .config import setting, site_name
from .conversions import STAGES, TOOLS, secrets_store, spool, store
from .conversions.adapters import adapter

DEFAULT_URL = "http://127.0.0.1:8766"


def _folder(ctx) -> Path:
    return Path(ctx.db_path).parent


def _sites(ctx) -> dict[str, dict]:
    from .conversions.hooks import site_configs
    found = site_configs(ctx.config, ctx.config_path)
    for c in getattr(ctx, "all_configs", []) or []:
        found.setdefault(site_name(c), c)
    return found


def _check(ctx, site: str, tool: str, tools=TOOLS) -> dict | None:
    sites = _sites(ctx)
    if site not in sites:
        ctx.err(f"hooks: no site named {site!r}; sites: {', '.join(sorted(sites))}")
        return None
    if tool not in tools:
        ctx.err(f"hooks: no tool {tool!r}; tools: {', '.join(tools)}")
        return None
    return sites[site]


# `hooks secret` only: recorded journeys' secret (recorded/, 2.43) is made and kept like a
# tool's, but it is not a conversion tool (no list, no test, no leads).
SECRET_TOOLS = (*TOOLS, "journey")


# ------------------------------------------------------------------- hooks

def cmd_secret(ctx) -> int:
    site, tool = ctx.args.site, ctx.args.tool
    config = _check(ctx, site, tool, SECRET_TOOLS)
    if config is None:
        return 2
    env = secrets_store.env_name(config, site, tool)
    if env:
        ctx.err(f"hooks: this hook's secret is read from the environment variable {env} "
                "(config hooks); set it there, or remove that line to use the file")
        return 2
    path = secrets_store.path_for(ctx.config, _folder(ctx))
    try:
        secrets_store.load(path)
    except secrets_store.Exposed as why:
        ctx.err(f"hooks: {why}; fix it with chmod 600 first")
        return 2
    value = ctx.args.value
    if value == "-":
        import sys
        value = sys.stdin.readline().strip()
    given = bool(value)
    value = value or secrets_store.make()
    secrets_store.put(path, secrets_store.key(site, tool), value)
    if given:
        ctx.out(f"hook {site}/{tool}: the tool's secret kept in {path} (0600)")
    else:
        ctx.out(f"hook {site}/{tool}: secret kept in {path} (0600). It is shown once:")
        ctx.out(f"  {value}")
    from .doctor import base_url
    base = base_url(config) or base_url(ctx.config)
    ctx.out(f"  address: {base or 'https://<your site>'}/traffic-hooks/{site}/{tool}")
    if not base:
        ctx.out("  (set access.base_url, or hooks.public_url, and this prints the real address)")
    if tool == "journey":
        ctx.out("  put both in the site's relay settings as SKALD_JOURNEY_SECRET and "
                "SKALD_JOURNEY_URL (docs/JOURNEYS.md); a new secret replaces the old one at once")
        return 0
    ctx.out("  give both to the tool (docs/INTEGRATIONS.md says where); a new secret "
            "replaces the old one at once")
    return 0


def cmd_list(ctx) -> int:
    folder = _folder(ctx)
    db_path = store.path_for(ctx.config, folder)
    db = store.connect(db_path) if db_path.exists() else None
    shown = 0
    try:
        for site, config in _sites(ctx).items():
            for tool in TOOLS:
                try:
                    value, where = secrets_store.find(config, folder, site, tool)
                except secrets_store.Exposed as why:
                    ctx.err(f"hooks: {why}")
                    return 2
                if not where:
                    continue
                shown += 1
                state = "set" if value else "MISSING (the variable is empty or unset)"
                ctx.out(f"{site}/{tool}: /traffic-hooks/{site}/{tool}  secret: {where}, {state}")
                rows = store.deliveries(db, site, tool, limit=5) if db else []
                for r in rows:
                    ctx.out(f"    {r['received_at']}  {r['http_status']}  {r['outcome']}"
                            + (f"  ({r['error']})" if r["error"] else ""))
                if not rows:
                    ctx.out("    no deliveries yet")
    finally:
        if db is not None:
            db.close()
    if not shown:
        ctx.out("no hooks set up; make one with: skald hooks secret SITE TOOL")
    return 0


def cmd_test(ctx) -> int:
    site, tool = ctx.args.site, ctx.args.tool
    config = _check(ctx, site, tool)
    if config is None:
        return 2
    try:
        secret, _ = secrets_store.find(config, _folder(ctx), site, tool)
    except secrets_store.Exposed as why:
        ctx.err(f"hooks: {why}")
        return 2
    if not secret:
        ctx.err(f"hooks: no secret for {site}/{tool}; make one with: "
                f"skald hooks secret {site} {tool}")
        return 2
    base = (ctx.args.url or setting(ctx.config, "hooks", "test_url") or DEFAULT_URL).rstrip("/")
    path = f"/traffic-hooks/{site}/{tool}"
    public = setting(ctx.config, "hooks", "public_url")
    uri = (str(public).rstrip("/") if public else base) + path
    now = time.time()
    mod = adapter(tool)
    body = json.dumps(mod.sample(site, now)).encode()
    headers = {"Content-Type": "application/json", "X-Skald-Test": "1",
               **mod.sign(body, secret, now, "POST", uri)}
    if not public:
        headers["X-Forwarded-Proto"] = base.split("://", 1)[0]
    request = urllib.request.Request(base + path, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            status, text = answer.status, answer.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as why:
        status, text = why.code, why.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as why:
        ctx.err(f"hooks test: could not reach {base}: {why}")
        return 1
    ctx.out(f"hooks test {site}/{tool}: {status} {text}")
    for line in kept_lines(text):
        ctx.out(line)
    return 0 if status == 200 else 1


def kept_lines(text: str) -> list[str]:
    """What a real delivery would keep, in words, from the test's answer."""
    try:
        got = json.loads(text)
    except ValueError:
        return []
    if not isinstance(got, dict) or not got.get("test") or "would_keep" not in got:
        return []
    out = [f"  a real one would keep {got['would_keep']} of {got.get('records', 0)} "
           f"record(s):"]
    for r in got.get("read") or []:
        facts = ", ".join(f"{k} {r[k]}" for k in ("action", "stage", "at", "source_type",
                                                   "campaign", "country", "device") if r.get(k))
        out.append(f"    {facts}; visitor ID {r['vid'] if r.get('vid') else 'none'}")
    out += [f"  note: {n}" for n in got.get("notes") or []]
    return out


# ------------------------------------------------------------- conversions

def cmd_forget(ctx) -> int:
    a = ctx.args
    return forget_person(ctx, a.email, a.vid, a.lead, a.dry_run)


def forget_person(ctx, email: str | None = None, vid: str | None = None,
                  lead: str | None = None, dry_run: bool = False) -> int:
    """Everything for one email, visitor ID or lead: conversions, removed
    rows, identity, journeys, deliveries, spool lines (`conversions forget`
    and `forget --email/--vid/--lead`)."""
    from types import SimpleNamespace
    from .privacy import LOG, digest
    a = SimpleNamespace(email=email, vid=vid, lead=lead, dry_run=dry_run)
    folder = _folder(ctx)
    db_path = store.path_for(ctx.config, folder)
    site = getattr(ctx.args, "only_site", None)
    what = ("email", a.email) if a.email else ("vid", a.vid) if a.vid else ("lead", a.lead)
    counts = {"conversions": 0, "identities": 0, "journeys": 0, "deliveries": 0,
              "removed": 0, "vids": [], "refs": []}
    if db_path.exists():
        db = store.connect(db_path)
        try:
            counts = store.forget(db, site, email=a.email, vid=a.vid, external_ref=a.lead,
                                  dry_run=a.dry_run)
            # Recorded journeys (2.43): the events sent with that email or visitor ID.
            from .recorded.store import forget as forget_recorded
            recorded = forget_recorded(db, site, email=a.email, vids=[a.vid, *counts["vids"]],
                                       dry_run=a.dry_run)
        finally:
            db.close()
    else:
        recorded = 0
    values = {v.strip().lower() for v in ([a.email, a.vid, a.lead] + counts["vids"]
                                          + counts["refs"]) if v}

    def match(row, texts) -> bool:
        if site and row.get("site") != site:
            return False
        return bool(values & texts)

    lines = spool.scrub(spool.spool_dir(ctx.config, folder), match, a.dry_run)
    # The beacon spool keeps its lines (the event audit counts them); only
    # the visitor ID comes out of them.
    from .beacon import spool_dir as beacon_spool
    from .conversions.from_beacon import scrub_spool
    vids = {v.strip().lower() for v in [a.vid, *counts["vids"]] if v}
    lines += scrub_spool(beacon_spool(ctx.config, getattr(ctx, "config_path", None),
                                      getattr(ctx, "live_dir", None)), vids, a.dry_run)
    verb = "would delete" if a.dry_run else "deleted"
    ctx.out(f"conversions forget{' (dry run)' if a.dry_run else ''}: {verb} "
            f"{counts['conversions']} conversion(s), {counts['journeys']} page view(s) of "
            f"{len(counts['vids'])} visitor ID(s), {counts['identities']} identit"
            f"{'y' if counts['identities'] == 1 else 'ies'}, {counts['deliveries']} delivery "
            f"row(s), {counts['removed']} removed row(s), {lines} spool line(s)")
    if recorded:
        ctx.out(f"  recorded journeys: {verb} {recorded} event(s) sent by the site, with "
                "their whole sessions")
    if not a.dry_run:
        from .audit_conversions import forget_cache
        forget_cache(folder)            # the beacon spool changed: count it again
        line = (f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} conversions "
                f"forget {what[0]} sha256:{digest(what[1].strip().lower())[:12]} "
                f"conversions={counts['conversions']} journeys={counts['journeys']} "
                f"identities={counts['identities']} spool_lines={lines}\n")
        log = _folder(ctx) / LOG
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(line)
        log.chmod(0o640)
    return 0


def _refs(raw) -> list[str]:
    """--ref values, trimmed, in order, once each (as leads/test reads refs)."""
    out: list[str] = []
    for ref in raw or []:
        ref = str(ref).strip()[:120]
        if ref and ref not in out:
            out.append(ref)
    return out


def cmd_mark_test(ctx) -> int:
    """Mark conversions as test (or not): kept and listed, never counted. By
    row id (every stage of the same tool and ref follows), and by --ref (2.26:
    store.mark_refs, the function POST .../leads/test calls)."""
    a = ctx.args
    on = not a.unmark
    refs = _refs(a.ref)
    if not a.ids and not refs:
        ctx.err("conversions mark-test: give row ids (conversions list) or --ref REF")
        return 2
    db_path = store.path_for(ctx.config, _folder(ctx))
    if not db_path.exists():
        ctx.err("conversions mark-test: no conversions file here")
        return 2
    db = store.connect(db_path)
    try:
        changed = store.mark_test(db, a.site, a.ids, on) if a.ids else []
        by_ref = store.mark_refs(db, a.site, a.tool, refs, on) if refs else None
    except ValueError as why:
        ctx.err(f"conversions mark-test: {why}; nothing changed")
        return 2
    finally:
        db.close()
    from .audit_conversions import forget_cache
    forget_cache(_folder(ctx))           # the audit's cached beacon days: count again
    word = "marked" if on else "unmarked"
    action = "conversions.test" if on else "conversions.untest"
    if a.ids:
        for r in changed:
            ctx.out(f"  {r['id']}  {r['tool']}  {r['action']} {r['stage']}  {r['at']}")
        ctx.out(f"conversions mark-test: {len(changed)} row(s) {word} test on {a.site}"
                + ("" if changed else " (they were already)"))
        _audit(ctx, action, a.site, ",".join(str(r["id"]) for r in changed))
    if by_ref is not None:
        missing = by_ref["not_found"]
        ctx.out(f"conversions mark-test --ref: {by_ref['changed']} row(s) {word} test on "
                f"{a.site} ({a.tool}), {by_ref['already']} already"
                + (f"; not found: {', '.join(missing)}" if missing else ""))
        _audit(ctx, action, a.site, f"{by_ref['changed']} row(s) {word}, {by_ref['already']} "
               f"already, {len(missing)} not found; tool={a.tool}; refs={','.join(refs)}",
               key="detail")
    return 0


def cmd_remove(ctx) -> int:
    """Soft-remove the rows of one ref (2.26): each row copied whole into
    `removed` with when and why (store.remove), out of every count, listed
    under Show left out > Removed. Refused without --why; --dry-run lists."""
    a = ctx.args
    why = (a.why or "").strip()
    if not why:
        ctx.err("conversions remove: say why with --why \"...\" (kept with each row)")
        return 2
    ref = str(a.ref or "").strip()[:120]
    if not ref:
        ctx.err("conversions remove: --ref is the lead's external_ref")
        return 2
    db_path = store.path_for(ctx.config, _folder(ctx))
    if not db_path.exists():
        ctx.err("conversions remove: no conversions file here")
        return 2
    sql = ("SELECT id, tool, action, stage, at, test FROM conversions WHERE site = ? AND "
           "tool = ? AND external_ref = ?")
    args: list = [a.site, a.tool, ref]
    for column, value in (("stage", a.stage), ("action", a.action)):
        if value:
            sql += f" AND {column} = ?"
            args.append(value)
    what = " ".join(f"{k} {v}" for k, v in (("stage", a.stage), ("action", a.action)) if v)
    db = store.connect(db_path)
    try:
        rows = db.execute(sql + " ORDER BY at, id", args).fetchall()
        if not rows:
            ctx.err(f"conversions remove: no row of {a.site} ({a.tool}) with ref {ref}"
                    + (f" and {what}" if what else "") + "; nothing changed")
            return 1
        for r in rows:
            ctx.out(f"  {r[0]}  {r[1]}  {r[2]} {r[3]}  {r[4]}" + ("  TEST" if r[5] else ""))
        if a.dry_run:
            ctx.out(f"conversions remove (dry run): would remove {len(rows)} row(s) of {ref} on "
                    f"{a.site}; nothing changed")
            return 0
        gone = sum(store.remove(db, r[0], f"removed by the admin: {why}") for r in rows)
    finally:
        db.close()
    from .audit_conversions import forget_cache
    forget_cache(_folder(ctx))
    ctx.out(f"conversions remove: {gone} row(s) of {ref} removed on {a.site}: kept under Show "
            f"left out > Removed, out of every count")
    _audit(ctx, "conversions.remove", a.site, f"{gone} row(s) removed, ids="
           f"{','.join(str(r[0]) for r in rows)}; tool={a.tool}; ref={ref}; why={why}",
           key="detail")
    return 0


def _audit(ctx, action: str, site: str, detail: str, key: str = "ids") -> None:
    """One row in the accounts audit log (actor "cli"), when there is one,
    else a line in privacy.log (conversions/marks.audit_entry)."""
    from .conversions.marks import audit_entry
    audit_entry(ctx.config, _folder(ctx), action, site, detail, key=key)


def cmd_conversions_list(ctx) -> int:
    """The latest conversions of a site with their ids (for mark-test)."""
    a = ctx.args
    db_path = store.path_for(ctx.config, _folder(ctx))
    if not db_path.exists():
        ctx.out("conversions list: no conversions file here")
        return 0
    db = store.connect(db_path)
    try:
        rows = db.execute("SELECT id, at, tool, action, stage, external_ref, test, label, "
                          "value_minor, currency FROM conversions WHERE site = ?"
                          + (" AND test <> 0" if a.test else "")
                          + " ORDER BY id DESC LIMIT ?", (a.site, a.limit)).fetchall()
    finally:
        db.close()
    from .conversions.money import shown
    for r in rows:
        # 2.32: the money a row carries, in the currency's major units.
        cash = shown(r[8], r[9])
        ctx.out(f"  {r[0]:>6}  {r[1]}  {r[2]:<9} {r[3]} {r[4]}  ref {str(r[5])[:40]}"
                + (f"  {cash} {r[9]}" if cash else "")
                + (f"  [{r[7]}]" if r[7] else "") + ("  TEST" if r[6] else ""))
    ctx.out(f"conversions list: {len(rows)} row(s), newest first")
    return 0


def cmd_prune(ctx, quiet: bool = False) -> int:
    folder = _folder(ctx)
    db_path = store.path_for(ctx.config, folder)
    # Each site by its own days when Settings > Privacy set them
    # (settings_store.prune_plan); conversions.retention_days 0 keeps leads,
    # their pages and the spool for good.
    from .settings_store import prune_plan
    vid_days, own_vid = prune_plan(ctx.config, "journeys.vid_days", store.vid_days(ctx.config))
    keep, own_keep = prune_plan(ctx.config, "conversions.retention_days",
                                store.keep_days(ctx.config))
    today = ctx.now.date()
    from .keep_everything import of
    spare = of(ctx)                   # a keep-everything site loses nothing
    got = {"conversions": 0, "journeys": 0, "identities": 0, "deliveries": 0}
    if db_path.exists():
        db = store.connect(db_path)
        try:
            got = store.prune(db, today, vid_days, keep, own_vid, own_keep, spare)
        finally:
            db.close()
    files = spool.prune(spool.spool_dir(ctx.config, folder), today, keep, own_keep, spare)
    # Names and emails past the site's People days (privacy.keep_days) when
    # that is shorter than the lead's own: cleared, every figure kept
    # (conversions/people_days.py). It says its own counts, per site.
    from .conversions import people_days
    people_days.run(ctx, today)
    # The same promise for the names and emails in your tools' stored answers
    # (Calendly, Resend), even a tool that stopped answering (yourtools/people_days.py).
    from .yourtools import people_days as tools_people_days
    tools_people_days.run(ctx, today)
    # Recorded journeys (2.43): the visitor-page days, their addresses and emails the
    # People days; a keep-everything site loses nothing (recorded/store.py).
    from .recorded.store import run_prune as recorded_prune
    rec = recorded_prune(ctx, folder, today)
    if rec["events"] or rec["cleared"]:
        ctx.out(f"recorded journeys prune: {rec['events']} event(s) removed, "
                f"{rec['cleared']} address(es) or email(s) cleared")
    if quiet and not (files or any(got.values())):
        return 0                      # the daily run says nothing when nothing went
    ctx.out(f"conversions prune: {got['conversions']} conversion(s), {got['journeys']} page "
            f"view(s), {got['identities']} identit{'y' if got['identities'] == 1 else 'ies'}, "
            f"{got['deliveries']} delivery row(s), {files} spool file(s) removed")
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("hooks", help="incoming hooks from the site and its tools "
                       "(Calendly, Stripe, ...): secrets, list, test")
    hs = p.add_subparsers(dest="hooks_command", required=True)
    s = hs.add_parser("secret", help="make a hook's secret (printed once, kept 0600)")
    s.add_argument("site")
    s.add_argument("tool", choices=SECRET_TOOLS)
    s.add_argument("--value", help="keep this secret (one the tool made, such as Stripe's "
                   "whsec_...) instead of a new one; '-' reads it from standard input")
    s.set_defaults(run=cmd_secret)
    s = hs.add_parser("list", help="the hooks set up, where their secrets live, "
                      "their last deliveries")
    s.set_defaults(run=cmd_list)
    s = hs.add_parser("test", help="post a signed sample to the local receiver "
                      "(marked as a test: read, never kept)")
    s.add_argument("site")
    s.add_argument("tool", choices=TOOLS)
    s.add_argument("--url", help=f"the receiver (default hooks.test_url or {DEFAULT_URL})")
    s.set_defaults(run=cmd_test)

    p = sub.add_parser("conversions", help="the conversions file: list, mark test, remove, "
                       "forget a person, prune")
    cs = p.add_subparsers(dest="conversions_command", required=True)
    f = cs.add_parser("forget", help="delete everything for an email, visitor ID or lead")
    which = f.add_mutually_exclusive_group(required=True)
    which.add_argument("--email")
    which.add_argument("--vid", help="a visitor ID (skv_...)")
    which.add_argument("--lead", help="a lead's external reference")
    f.add_argument("--dry-run", dest="dry_run", action="store_true",
                   help="count what would go; change nothing")
    f.set_defaults(run=cmd_forget)
    s = cs.add_parser("prune", help="delete journeys, conversions, deliveries and spool "
                      "files past their keeping time")
    s.set_defaults(run=cmd_prune)
    s = cs.add_parser("mark-test", help="mark conversions as test: kept and listed (Left "
                      "out), never counted; every stage of the same booking or lead too")
    s.add_argument("site")
    s.add_argument("ids", nargs="*", type=int, help="conversion ids (conversions list)")
    s.add_argument("--ref", action="append", metavar="REF",
                   help="a lead's external_ref: every stage of it (repeat for more)")
    s.add_argument("--tool", choices=TOOLS, default="lead",
                   help="the tool the refs came through (default lead)")
    s.add_argument("--unmark", action="store_true", help="count them again")
    s.set_defaults(run=cmd_mark_test)
    s = cs.add_parser("remove", help="soft-remove a lead's rows: each kept whole under Show "
                      "left out > Removed with when and why, out of every count")
    s.add_argument("site")
    s.add_argument("--ref", required=True, help="the lead's external_ref")
    s.add_argument("--tool", choices=TOOLS, default="lead",
                   help="the tool it came through (default lead)")
    s.add_argument("--stage", choices=STAGES, help="only this stage (default every stage)")
    s.add_argument("--action", help="only this action")
    s.add_argument("--why", required=True, help="why it goes (kept with each row)")
    s.add_argument("--dry-run", dest="dry_run", action="store_true",
                   help="list what would go; change nothing")
    s.set_defaults(run=cmd_remove)
    s = cs.add_parser("list", help="the latest conversions of a site, with their ids")
    s.add_argument("site")
    s.add_argument("--test", action="store_true", help="only the ones marked test")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(run=cmd_conversions_list)

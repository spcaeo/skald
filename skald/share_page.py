"""What a "Share with your developer" link's page asks (share_api.py routes
it, after finding the link usable): only its one task, for its one site.

  info     {site, task, method, send_url, hook_url, kit, beacon_on, expires_at,
            shown (the secret was shown already), secret (what Show makes)}
  reveal   the secret, made now: a sending token (send) or the hook's secret
           (hook); once per link, then 410 with "already shown"
  status   send and script: the fields of sites/status the Test reads (the
           batches, today's lines, the last refusal, verified or not, the
           tag's counters); hook: the hook's state and its last deliveries;
           nextjs: the doctor's Next.js line (doctor.next_pages: state, says)
  kit      send: the link's own way only: server, the one-file installer;
           docker or systemd, the older zip kit; with include_token, only
           a valid sending token of this site goes in
  test     hook: a signed sample lead posted to the receiver here, marked as
           a test (X-Skald-Test), so it is read, logged as "test" and never kept
"""
from __future__ import annotations

import json
import time

from . import connections_api, ingest, ingest_status, kit, share_links, site_verify
from .auth_api import answer, text
from .files import slug

TOKEN_NAME = "Shared link: {site}, {day}"


class Ctx:
    def __init__(self, h, db, entry, config, live_dir, allowed, config_path):
        self.h, self.db, self.entry, self.config = h, db, entry, config or {}
        self.live_dir, self.allowed, self.config_path = live_dir, allowed, config_path
        self.site = entry["site"]

    def ok(self, **body):
        return answer(self.h, 200, {"ok": True, **body})

    def no(self, code: int, error: str, **extra):
        return answer(self.h, code, {"ok": False, "error": error, **extra})

    def base(self) -> str:
        from .share_api import _base
        return _base(self.config, self.allowed)

    def hook_url(self) -> str | None:
        from .share_api import _hook_base
        e = self.entry
        return f"{_hook_base(self.config, self.allowed)}/traffic-hooks/{self.site}/{e['method']}" \
            if e["task"] == "hook" else None


def info(c: Ctx, form):
    e = c.entry
    secret = {"send": "sending token", "hook": "hook secret"}.get(e["task"])
    shown = bool(e["revealed_at"])
    return c.ok(site=c.site, task=e["task"], method=e["method"], base=c.base(),
                send_url=f"{c.base()}{ingest.PREFIX}{c.site}", hook_url=c.hook_url(),
                dashboard=f"{c.base()}/traffic/{slug(c.site)}/",
                kit={k: v for k, v in kit.available(c.config).items()},
                beacon_on=connections_api.beacon_on(c.config), expires_at=e["expires_at"],
                secret=secret, shown=shown,
                shown_words="The secret was shown already. Ask for a new link." if shown else None)


def reveal(c: Ctx, form):
    e = c.entry
    if e["task"] in share_links.NO_SECRET:
        return c.no(400, "The script tag needs no secret." if e["task"] == "script"
                    else "These steps need no secret.")
    if not share_links.claim_reveal(c.db, e):
        return c.no(410, "The secret was shown already. Ask for a new link.", shown=True)
    if e["task"] == "send":
        from .accounts import apitokens
        day = time.strftime("%Y-%m-%d", time.gmtime())
        token = apitokens.create(c.db, e["org_id"], TOKEN_NAME.format(site=c.site, day=day),
                                 sites=[c.site], scopes=("ingest",), actor=e["created_by"])
        share_links.note_secret(c.db, e["ref"], f"token:{token.split('_', 2)[1]}")
        return c.ok(kind="sending token", secret=token)
    return _hook_secret(c)


def _hook_secret(c: Ctx):
    from .conversions import hooks as hooks_mod, secrets_store
    from .integrations_api import OWN_SECRET
    e = c.entry
    tool = e["method"]
    if tool in OWN_SECRET:
        return c.no(409, "This tool signs with a secret it makes itself; paste it in Settings > "
                         "Leads & integrations instead.")
    conf = hooks_mod.site_configs(c.config, c.config_path).get(c.site) or c.config
    if secrets_store.env_name(conf, c.site, tool):
        return c.no(409, "This hook's secret is set on the server; ask its admin.")
    folder = hooks_mod.history_folder(c.config, c.config_path) if c.live_dir is None else c.live_dir
    path = secrets_store.path_for(c.config, folder)
    value = secrets_store.make()
    secrets_store.put(path, secrets_store.key(c.site, tool), value)
    share_links.note_secret(c.db, e["ref"], f"hook:{tool}")
    from .accounts import auditlog
    auditlog.record(c.db, e["org_id"], f"link:{e['ref']}", "hook.secret", f"{c.site}/{tool}",
                    "made from a shared link")
    return c.ok(kind="hook secret", secret=value)


def status(c: Ctx, form):
    e = c.entry
    if e["task"] == "hook":
        return c.ok(**hook_status(c))
    if e["task"] == "nextjs":
        return c.ok(**next_status(c))
    base = ingest.history_folder(c.config, c.live_dir)
    _, summary = connections_api.received(c.config, c.live_dir, c.site)
    verify = site_verify.shown(c.db, c.site)
    return c.ok(site=c.site, ingest_enabled=ingest.enabled(c.config), received=summary,
                **ingest_status.status(base, c.site),
                verify={"state": verify["state"]} if verify else None,
                beacon=connections_api.beacon_status(c.config, c.live_dir, c.config_path, c.site))


def next_status(c: Ctx) -> dict:
    """The doctor's Next.js line for the site's log: OK once its newest lines
    record the prefetch header; "" when the log holds no Next.js payload."""
    from .conversions import hooks as hooks_mod
    from .doctor import next_pages
    conf = hooks_mod.site_configs(c.config, c.config_path).get(c.site) or c.config
    got = next_pages(conf) or {"state": "", "says": "no Next.js page request in the log's "
                                                   "newest lines yet"}
    return {"site": c.site, "state": got["state"], "says": got["says"]}


def hook_status(c: Ctx) -> dict:
    """The hook's state in words and its last 5 deliveries (no body, no sender)."""
    from .conversions import hooks as hooks_mod, store
    from .conversions.roads import hook_states
    tool = c.entry["method"]
    conf = hooks_mod.site_configs(c.config, c.config_path).get(c.site) or c.config
    folder = hooks_mod.history_folder(c.config, c.config_path) if c.live_dir is None else c.live_dir
    path = store.path_for(c.config, folder)
    db = store.connect(path) if path.exists() else None
    try:
        state = next((s for s in hook_states(conf, folder, c.site, db, base=c.base())
                      if s["tool"] == tool), {})
        rows = store.deliveries(db, c.site, tool, 5) if db else []
    finally:
        if db is not None:
            db.close()
    keep = ("received_at", "outcome", "http_status", "error")
    return {"state": state.get("state"), "words": state.get("words"),
            "deliveries": [{k: r.get(k) for k in keep} for r in rows]}


def kit_zip(c: Ctx, form):
    from .accounts import apitokens
    e = c.entry
    method = text(form, "method", 20)
    server = ("server", *kit.METHODS)       # one server way since 2.30: the one file, or a zip under "Other ways"
    if e["task"] != "send" or method not in server or e["method"] not in server:
        return c.no(400, "This link has no install kit.")
    token = None
    if form.get("include_token") is True:
        token = text(form, "token", 200).strip()
        ok, why, _ = apitokens.check(c.db, f"Bearer {token}", c.site, "ingest")
        if not ok:
            return c.no(400, f"The token cannot go in the kit: {why}.")
    page = f"{c.base()}/traffic/{slug(c.site)}/"
    if method == "server":                        # the one bash file (kit.one_file)
        from .kit_api import send_bytes
        try:
            data = kit.one_file(c.site, f"{c.base()}{ingest.PREFIX}{c.site}", page,
                                f"{page}#help?part=troubleshooting-connections",
                                kit.image(c.config), kit.ship_path(c.config), token)
        except ValueError as why:
            return c.no(400, str(why))
        send_bytes(c.h, data, "text/x-shellscript; charset=utf-8", f"skald-install-{c.site}.sh")
        return None
    try:
        data = kit.build(c.site, f"{c.base()}{ingest.PREFIX}{c.site}", method, page,
                         f"{page}#help?part=troubleshooting-connections", kit.image(c.config),
                         kit.ship_path(c.config), token)
    except ValueError as why:
        return c.no(400, str(why))
    c.h.send_response(200)
    for k, v in (("Content-Type", "application/zip"), ("Cache-Control", "no-store"),
                 ("Content-Disposition", f'attachment; filename="skald-ship-{c.site}.zip"'),
                 ("X-Content-Type-Options", "nosniff"), ("Content-Length", str(len(data)))):
        c.h.send_header(k, v)
    c.h.end_headers()
    c.h.wfile.write(data)
    return None


def test(c: Ctx, form):
    """A signed sample lead, marked as a test: read, logged as "test", never kept."""
    from .conversions import hooks as hooks_mod, secrets_store
    from .conversions.adapters import adapter
    from .accounts import auditlog
    e = c.entry
    if e["task"] != "hook":
        return c.no(400, "This link has no hook to test.")
    tool = e["method"]
    conf = hooks_mod.site_configs(c.config, c.config_path).get(c.site) or c.config
    folder = hooks_mod.history_folder(c.config, c.config_path) if c.live_dir is None else c.live_dir
    try:
        value, _ = secrets_store.find(conf, folder, c.site, tool)
    except secrets_store.Exposed:
        return c.no(500, "The server's secrets file needs fixing first; ask its admin.")
    if not value:
        return c.no(409, "Show the secret first: the hook has none yet.")
    mod = adapter(tool)
    now = time.time()
    uri = c.hook_url()
    body = json.dumps(mod.sample(c.site, now)).encode()
    headers = {k.lower(): v for k, v in mod.sign(body, value, now, "POST", uri).items()}
    headers.update({"content-type": "application/json", "x-skald-test": "1",
                    ":method": "POST", ":uri": uri})
    code, got = hooks_mod.receiver(c.config, folder, c.config_path).process(
        c.site, tool, headers, body, value)
    auditlog.record(c.db, e["org_id"], f"link:{e['ref']}", "hook.test", f"{c.site}/{tool}",
                    str(code))
    return c.ok(status=code, answer=got)

"""Settings > Mail & reports > Client reports in the dashboard (client_reports.py), with accounts
(`access.mode: sessions`). Served by the refresh helper like settings_api.py,
under the same `settings/` prefix nginx already passes on:

  GET  settings/reports                the site's reports, each with its next send,
                                       its last one and which recipients confirmed;
                                       the organisation's branding
  POST settings/report-save            {id?, name, recipients, schedule, period,
                                       sections, notes, footer, agency_logo, paused};
                                       a recipient not confirmed gets a confirm link
  POST settings/report-delete          {id}
  POST settings/report-preview         {id} or the unsaved settings: {subject, html}
                                       (images written in), never sent
  POST settings/report-pdf             the same, as the PDF file
  POST settings/report-send            {id}: send it now; 3 per 10 minutes per person
  GET  settings/report-log?id=         its sends: who, when, period, ok or the error
  GET  settings/agency-logo            the organisation's logo (404: none)
  POST settings/agency-logo            {data: base64} to set it, {data: null} to remove

Admins and owners of the site's organisation only (and install admins);
every query names the organisation and the site, so nothing of another
organisation is ever read. Every POST needs the same-origin check and the
session's CSRF value. In basic mode every route answers 404.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import auth_api, client_reports as cr, client_reports_send as send_mod
from .accounts import auditlog, limits, sessions, users
from .auth_api import answer, csrf_ok

PATH = re.compile(r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
                  r"(?P<act>settings/(?:reports|report-(?:save|delete|preview|pdf|send|log)"
                  r"|agency-logo))$")
GETS = {"settings/reports", "settings/report-log", "settings/agency-logo"}
BOTH = {"settings/agency-logo"}
MAX_SPEC_BODY = 16 * 1024
MAX_LOGO_BODY = 400_000
SEND_LIMIT, SEND_MINUTES = 3, 10
STAND_IN = "recipient@preview.invalid"
IMAGE_CSP = "default-src 'none'; style-src 'unsafe-inline'; sandbox"


def match(path: str):
    path = path.split("?", 1)[0]
    return None if ".." in path else PATH.match(path)


def is_reports(path: str) -> bool:
    return match(path) is not None


class Ctx:
    def __init__(self, h, db, session, site, role, org, config, live_dir, history_path,
                 config_path, allowed):
        from .settings_api import site_config
        from . import settings_store as store
        self.h, self.db, self.session, self.site, self.role, self.org = (
            h, db, session, site, role, org)
        self.live_dir, self.allowed = live_dir, allowed
        self.history_path = history_path or (Path(live_dir) / "history.sqlite"
                                             if live_dir is not None else None)
        self.raw = site_config(config, config_path, site)
        self.config = store.apply(self.raw, site, live_dir)
        self.uid, self.email = session["user_id"], session["email"]

    def ok(self, **body):
        return answer(self.h, 200, {"ok": True, **body})

    def no(self, code: int, error: str, **extra):
        return answer(self.h, code, {"ok": False, "error": error, **extra})

    @property
    def trusted(self) -> list:
        to = (self.raw.get("mail") or {}).get("to") or []
        return [to] if isinstance(to, str) else list(to)


def _body(h, limit: int) -> dict | None:
    try:
        length = int(h.headers.get("Content-Length") or 0)
    except ValueError:
        length = -1
    if length < 0 or length > limit:
        answer(h, 413, {"ok": False, "error": "The request is too large."})
        return None
    raw = h.rfile.read(length) if length else b""
    try:
        got = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, ValueError):
        got = None
    if not isinstance(got, dict):
        answer(h, 400, {"ok": False, "error": "Send a JSON object."})
        return None
    return got


def handle(h, write: bool, config, live_dir, allowed, same_origin, history_path=None,
           config_path=None) -> None:
    if not auth_api.sessions_mode(config):
        return answer(h, 404, {"ok": False, "error": "not found"})
    m = match(h.path)
    act = m.group("act")
    if act not in BOTH and write == (act in GETS):
        return answer(h, 405, {"ok": False, "error": "wrong method"})
    if write and not same_origin(h.headers, allowed):
        return answer(h, 403, {"ok": False, "error": "same-origin requests only"})
    db = auth_api.open_db(config, live_dir)
    if db is None:
        return answer(h, 503, {"ok": False, "error": "accounts are not set up here"})
    try:
        session = sessions.resolve(db, auth_api.cookie_of(h.headers))
        if session is None:
            return answer(h, 401, {"ok": False, "error": "Sign in first."})
        if write and not csrf_ok(session, h.headers):
            return answer(h, 403, {"ok": False, "error": "The page is out of date. "
                                                         "Reload it and try again."})
        role, org = users.site_role(db, session["user_id"], m.group("site"))
        if org is None or (role is None and not session["install_admin"]):
            return answer(h, 403, {"ok": False, "error": "You are not a member here."})
        if role not in ("owner", "admin") and not session["install_admin"]:
            return answer(h, 403, {"ok": False, "error": "Only an admin can do this.",
                                   "role": role})
        c = Ctx(h, db, session, m.group("site"), role, org, config, live_dir, history_path,
                config_path, allowed)
        form = {}
        if write:
            form = _body(h, MAX_LOGO_BODY if act == "settings/agency-logo" else MAX_SPEC_BODY)
            if form is None:
                return None
        name = act.split("/", 1)[1]
        return ROUTES[name if name != "agency-logo" else ("logo-post" if write else "logo")](
            c, form)
    finally:
        db.close()


# ---------------------------------------------------------------- reads

def _tz(c: Ctx):
    from .window import zone
    try:
        return zone(c.config)
    except Exception:                   # noqa: BLE001 - a bad zone: UTC for the page
        return timezone.utc


def _shown(c: Ctx, report: dict) -> dict:
    spec = report["spec"]
    now = datetime.now(timezone.utc)
    nxt = None if spec.get("paused") else cr.next_send(spec, now, _tz(c))
    day = (nxt or now).astimezone(_tz(c)).date()
    first, last = cr.period_for(spec["period"], day)
    confirmed, waiting = cr.recipients_state(c.db, c.org["id"], spec["recipients"], c.trusted)
    sent = cr.sends(c.db, c.org["id"], report["id"], 1)
    return {"id": report["id"], "spec": spec, "created_by": report["created_by"],
            "updated_at": report["updated_at"],
            "next": nxt.isoformat() if nxt else None, "next_first": first.isoformat(),
            "next_last": last.isoformat(), "confirmed": confirmed, "waiting": waiting,
            "last_send": sent[0] if sent else None}


def _branding(c: Ctx) -> dict:
    from . import settings_store as store
    scope = f"org:{c.org['id']}"
    return {"agency_name": store.get(c.db, scope, "brand.agency_name"),
            "color": store.get(c.db, scope, "brand.color"),
            "logo": send_mod.agency_logo(c.live_dir, c.org["id"]) is not None}


def reports(c: Ctx, form):
    from .window import zone
    try:
        tz = str(zone(c.config))
    except Exception:                   # noqa: BLE001
        tz = "UTC"
    return c.ok(site=c.site, org=c.org["name"], timezone=tz,
                reports=[_shown(c, r) for r in cr.listing(c.db, c.org["id"], c.site)],
                branding=_branding(c), sections=list(cr.SECTIONS),
                section_words=cr.SECTION_WORDS, periods=cr.PERIOD_WORDS,
                search_console=_search_connected(c), mail_ready=_mail_ready(c))


def _search_connected(c: Ctx) -> bool:
    """Search Console connected for this site (Settings > Leads & tools > Search Console & Bing)."""
    from .search.sync import google_property
    return bool(google_property(c.config))


def _mail_ready(c: Ctx) -> bool:
    mail = c.config.get("mail") or {}
    return bool(str(mail.get("host") or "").strip() and str(mail.get("from") or "").strip())


def log(c: Ctx, form):
    report = cr.get(c.db, c.org["id"], c.site, auth_api.query(c.h.path).get("id"))
    if report is None:
        return c.no(404, "There is no such report.")
    return c.ok(id=report["id"], sends=cr.sends(c.db, c.org["id"], report["id"], 100))


# ---------------------------------------------------------------- writes

def save(c: Ctx, form):
    rid = form.pop("id", None)
    try:
        spec = cr.validate(form)
        report = cr.save(c.db, c.org["id"], c.site, spec, c.email, rid)
    except cr.Invalid as why:
        return c.no(400, str(why))
    auditlog.record(c.db, c.org["id"], c.uid, "report.save", c.site,
                    f"{report['id']}: {spec['name']}")
    shown = _shown(c, report)
    # What happened to the confirm links, for the page to say: "asked" (mailed now),
    # "no_mail" (no mail server: none sent, and no day's link used up), "none" (nobody waits).
    confirm = "none"
    if shown["waiting"] and _mail_ready(c):
        from .mail_confirm import ask
        ask(c.db, c.config, c.allowed, c.org, c.site, shown["waiting"])
        confirm = "asked"
    elif shown["waiting"]:
        confirm = "no_mail"
    return c.ok(report=shown, confirm=confirm)


def delete(c: Ctx, form):
    report = cr.get(c.db, c.org["id"], c.site, form.get("id"))
    if report is None or not cr.delete(c.db, c.org["id"], c.site, report["id"]):
        return c.no(404, "There is no such report.")
    auditlog.record(c.db, c.org["id"], c.uid, "report.delete", c.site,
                    f"{report['id']}: {report['spec']['name']}")
    return c.ok(deleted=report["id"])


def _report(c: Ctx, form) -> dict | None:
    """A saved report ({id}) or the unsaved settings on the page."""
    if form.get("id") is not None and len(form) == 1:
        got = cr.get(c.db, c.org["id"], c.site, form["id"])
        if got is None:
            c.no(404, "There is no such report.")
        return got
    draft = {k: v for k, v in form.items() if k != "id"}
    if not draft.get("recipients"):
        draft["recipients"] = [STAND_IN]
    try:
        spec = cr.validate(draft)
    except cr.Invalid as why:
        c.no(400, str(why))
        return None
    return {"id": None, "org_id": c.org["id"], "site": c.site, "spec": spec}


def _compose(c: Ctx, report: dict) -> dict | None:
    from .client_report_data import Refused
    try:
        return send_mod.compose(c.config, c.history_path, c.db, report, c.live_dir,
                                trusted=c.trusted)
    except Refused as why:
        c.no(409, f"The report cannot be made for this period: {why}.")
        return None


def preview(c: Ctx, form):
    from .client_report_data import coverage_lines
    report = _report(c, form)
    got = report and _compose(c, report)
    if not got:
        return None
    return c.ok(subject=got["subject"], html=send_mod.preview_html(got),
                first=got["first"].isoformat(), last=got["last"].isoformat(),
                coverage=coverage_lines(got["data"]), waiting=got["waiting"],
                file=got["file"])


def pdf(c: Ctx, form):
    report = _report(c, form)
    got = report and _compose(c, report)
    if not got:
        return None
    data, h = got["pdf"], c.h
    h.send_response(200)
    h.send_header("Content-Type", "application/pdf")
    h.send_header("Content-Disposition", f'attachment; filename="{got["file"]}"')
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data)
    return None


def send_now(c: Ctx, form):
    from .accounts import db as base
    report = cr.get(c.db, c.org["id"], c.site, form.get("id"))
    if report is None:
        return c.no(404, "There is no such report.")
    key = f"reportsend:{c.uid}"
    with base.tx(c.db):
        if limits.count(c.db, key, SEND_MINUTES) >= SEND_LIMIT:
            return answer(c.h, 429, {"ok": False, "error": f"At most {SEND_LIMIT} reports sent "
                                     f"by hand in {SEND_MINUTES} minutes. Try again later."},
                          {"Retry-After": str(SEND_MINUTES * 60)})
        limits.note_failure(c.db, key)
    ok, words = send_mod.send(c.config, c.history_path, c.db, report, c.live_dir, c.email,
                              trusted=c.trusted)
    auditlog.record(c.db, c.org["id"], c.uid, "report.send", c.site,
                    f"{report['id']}: {words}")
    if not ok:
        return c.no(400, words[:1].upper() + words[1:] + ".",
                    sends=cr.sends(c.db, c.org["id"], report["id"], 100))
    return c.ok(sent=True, words=words, sends=cr.sends(c.db, c.org["id"], report["id"], 100))


def logo(c: Ctx, form):
    got = send_mod.agency_logo(c.live_dir, c.org["id"])
    if got is None:
        return c.no(404, "No agency logo.")
    data, kind = got
    h = c.h
    h.send_response(200)
    h.send_header("Content-Type", send_mod.LOGO_KINDS[kind])
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("Content-Security-Policy", IMAGE_CSP)
    h.send_header("Cross-Origin-Resource-Policy", "same-origin")
    h.send_header("Cache-Control", "no-store")
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data)
    return None


def logo_post(c: Ctx, form):
    if c.live_dir is None:
        return c.no(503, "The server has no folder for logos.")
    if form.get("data") is None:
        send_mod.remove_agency_logo(c.live_dir, c.org["id"])
        auditlog.record(c.db, c.org["id"], c.uid, "brand.logo", c.org["name"], "removed")
        return c.ok(branding=_branding(c))
    try:
        body = base64.b64decode(str(form["data"]), validate=True)
        kind = send_mod.store_agency_logo(c.live_dir, c.org["id"], body)
    except (binascii.Error, ValueError) as why:
        words = str(why) if isinstance(why, ValueError) and not isinstance(
            why, binascii.Error) else "The file did not arrive whole; choose it again."
        return c.no(400, words)
    auditlog.record(c.db, c.org["id"], c.uid, "brand.logo", c.org["name"],
                    f"{kind}, {len(body)} bytes")
    return c.ok(branding=_branding(c))


ROUTES = {"reports": reports, "report-save": save, "report-delete": delete,
          "report-preview": preview, "report-pdf": pdf, "report-send": send_now,
          "report-log": log, "logo": logo, "logo-post": logo_post}

"""Building, previewing and sending client reports (client_reports.py), and
`skald reports`, which the container's scheduler runs every 15 minutes
(docker/scheduler.py):

    skald reports --due            send every report whose time has come
    skald reports --list           each report, its next send and its last one
    skald reports --send ID        send one now (as "Send now" does)
    skald reports --pdf ID --out F write its PDF for the latest period, send nothing

A report goes to its confirmed recipients only (mail_confirm.py; addresses
in config.yml's own mail.to count as confirmed). It is built from the site's
verified history (client_report_data.py) and refused, not shrunk, when the
period cannot add up; a scheduled report whose period's last day is not
stored yet waits for the morning run until 18:00. Every try is recorded.

The agency's logo: one PNG or JPEG per organisation, at most 256 KB, kept
in <history folder>/logos/org-<id>/agency.<png|jpg> (Settings > Reports).
"""
from __future__ import annotations

import base64
import smtplib
from datetime import datetime, timezone
from pathlib import Path

from . import client_reports as cr
from .files import slug

MAX_LOGO = 256 * 1024
LOGO_KINDS = {"png": "image/png", "jpg": "image/jpeg"}


# ------------------------------------------------------------- branding

def _folder(base, org_id) -> Path:
    from .site_logos import folder
    return folder(base, f"org-{int(org_id)}")


def agency_logo(base, org_id) -> tuple[bytes, str] | None:
    if base is None:
        return None
    for kind in LOGO_KINDS:
        path = _folder(base, org_id) / f"agency.{kind}"
        if path.is_file():
            data = path.read_bytes()
            return (data, kind) if len(data) <= MAX_LOGO else None
    return None


def store_agency_logo(base, org_id, body: bytes) -> str:
    """Keep an uploaded agency logo; ValueError in words when it is not one."""
    from .logo_image import check
    from .site_logos import _write_bytes
    if not body or len(body) > MAX_LOGO:
        raise ValueError("The logo is a PNG or JPEG of at most 256 KB.")
    try:
        kind, size = check(body, kinds=tuple(LOGO_KINDS))
    except Exception:                   # noqa: BLE001 - logo_image.Refused and any parse error
        raise ValueError("The logo is a PNG or JPEG of at most 256 KB.") from None
    if size and min(size) < 16:
        raise ValueError("The logo is too small: at least 16 pixels each way.")
    remove_agency_logo(base, org_id)
    _write_bytes(_folder(base, org_id) / f"agency.{kind}", body)
    return kind


def remove_agency_logo(base, org_id) -> None:
    for kind in LOGO_KINDS:
        (_folder(base, org_id) / f"agency.{kind}").unlink(missing_ok=True)


def _raster(data: bytes, kind: str) -> tuple[bytes, str] | None:
    """(bytes, kind) a mail and a PDF can both show, or None (the letter)."""
    from .pdf_writer import png_in_ico
    if kind == "ico":
        data, kind = png_in_ico(data) or b"", "png"
    if kind in LOGO_KINDS and data:
        return data, kind
    return None


def brand_for(config: dict, db, org_id, site: str, base, spec: dict | None = None) -> dict:
    from . import settings_store as store
    from .site_logos import chosen, letter, prefs
    got = {"agency_name": store.get(db, f"org:{int(org_id)}", "brand.agency_name"),
           "color": store.get(db, f"org:{int(org_id)}", "brand.color"),
           "letter": letter(site), "letter_color": prefs(config, site, base)["color"],
           "site_logo": None, "site_kind": None, "agency_logo": None, "agency_kind": None}
    found = chosen(config, site, base)
    if found is not None:
        try:
            pic = _raster(found[0].read_bytes(), found[1].get("kind"))
        except OSError:
            pic = None
        if pic:
            got["site_logo"], got["site_kind"] = pic
    if spec is None or spec.get("agency_logo", True):
        pic = agency_logo(base, org_id)
        if pic:
            got["agency_logo"], got["agency_kind"] = pic
    return got


# ------------------------------------------------------------- building

def subject(data: dict) -> str:
    from .client_report_data import period_words
    return f"{data['name']}: {data['site']}, {period_words(data['first'], data['last'])}"


def compose(config: dict, history_path, db, report: dict, base, now: datetime | None = None,
            day=None, trusted=()) -> dict:
    """Everything one send needs; client_report_data.Refused when the
    period cannot be reported honestly."""
    from .client_report_data import Refused, build
    from .client_report_html import as_text, render
    from .client_report_pdf import render as pdf
    from .store import History
    from .window import zone
    spec, site = report["spec"], report["site"]
    tz = zone(config)
    now = now or datetime.now(timezone.utc)
    day = day or now.astimezone(tz).date()
    first, last = cr.period_for(spec["period"], day)
    if history_path is None or not Path(history_path).is_file():
        raise Refused("no history is stored for this site yet")
    with History(history_path) as history:
        data = build(config, history, site, spec, first, last, tz)
    brand = brand_for(config, db, report["org_id"], site, base, spec)
    confirmed, waiting = cr.recipients_state(db, report["org_id"], spec["recipients"], trusted)
    shown = confirmed or spec["recipients"]
    return {"data": data, "brand": brand, "first": first, "last": last,
            "confirmed": confirmed, "waiting": waiting, "subject": subject(data),
            "html": render(data, brand, shown), "text": as_text(data, brand),
            "pdf": pdf(data, brand, now), "file": f"{slug(site)}-{first}-to-{last}.pdf"}


def preview_html(got: dict) -> str:
    """The mail's HTML with its images written in (a sandboxed frame shows it)."""
    from .client_report_html import AGENCY_CID, SITE_CID
    html = got["html"]
    for cid, key in ((SITE_CID, "site"), (AGENCY_CID, "agency")):
        data = got["brand"].get(f"{key}_logo")
        if data:
            uri = (f"data:{LOGO_KINDS[got['brand'][f'{key}_kind']]};base64,"
                   + base64.b64encode(data).decode("ascii"))
            html = html.replace(f"cid:{cid}", uri)
    return html


def message(config: dict, got: dict, now: datetime):
    """The mail to the confirmed recipients; mailer.Refused when it cannot go."""
    from . import mailer
    from .client_report_html import AGENCY_CID, SITE_CID
    if not got["confirmed"]:
        raise mailer.Refused("no recipient has confirmed yet (each gets a confirm link "
                             "first)")
    mail = dict(config.get("mail") or {})
    agency = got["brand"].get("agency_name")
    mail.update(to=list(got["confirmed"]), to_waiting=None,
                from_name=agency or mail.get("from_name"))
    cfg = mailer.settings({**config, "mail": mail})
    cfg["prefix"] = ""                  # the client's report, not a Skald system mail
    msg = mailer._message(cfg, got["subject"], got["text"], got["html"], now)
    body = msg.get_body(("html",))
    for cid, key in ((SITE_CID, "site"), (AGENCY_CID, "agency")):
        data = got["brand"].get(f"{key}_logo")
        if data:
            kind = got["brand"][f"{key}_kind"]
            body.add_related(data, maintype="image", subtype=LOGO_KINDS[kind].split("/")[1],
                             cid=f"<{cid}>", filename=f"{key}.{kind}", disposition="inline")
    msg.add_attachment(got["pdf"], maintype="application", subtype="pdf", filename=got["file"])
    return msg, cfg


def send(config: dict, history_path, db, report: dict, base, by: str,
         now: datetime | None = None, day=None, trusted=()) -> tuple[bool, str]:
    """Build and send one report, and record the try: (ok, words)."""
    from . import mailer
    from .client_report_data import Refused
    now = now or datetime.now(timezone.utc)
    first = last = None
    to: list = []
    try:
        got = compose(config, history_path, db, report, base, now, day, trusted)
        first, last, to = got["first"], got["last"], got["confirmed"]
        msg, cfg = message(config, got, now)
        mailer.send(msg, cfg)
        words = f"sent to {len(to)} recipient{'s' if len(to) != 1 else ''}"
        if got["waiting"]:
            words += f"; {len(got['waiting'])} not confirmed yet, left out"
        ok = True
    except (Refused, mailer.Refused) as why:
        ok, words = False, f"not sent: {why}"
    except (OSError, smtplib.SMTPException) as why:
        ok, words = False, f"the mail server did not take it: {type(why).__name__}"
    cr.record(db, report, by, ok, words, first, last, to,
              occurrence=day if by == "schedule" else None, at=now)
    return ok, words


# ------------------------------------------------------------- the clock

def run_due(config: dict, history_path, db, site: str, base, now: datetime | None = None,
            trusted=(), out=print) -> int:
    """Send each of the site's reports that is due; 1 when any failed."""
    from .window import zone
    from .store import History
    tz = zone(config)
    now = now or datetime.now(timezone.utc)
    failed = 0
    for report in cr.org_reports(db, site):
        spec = report["spec"]
        day = cr.due(spec, cr.sends(db, report["org_id"], report["id"], 20), now, tz,
                     report["created_at"])
        if day is None:
            continue
        first, last = cr.period_for(spec["period"], day)
        if history_path is not None and Path(history_path).is_file():
            with History(history_path) as history:
                missing = history.state(site, last) is None
            if cr.should_wait(missing, now, tz):
                out(f"reports: {site}: {spec['name']!r} waits for {last} to be stored")
                continue
        ok, words = send(config, history_path, db, report, base, "schedule", now, day, trusted)
        out(f"reports: {site}: {spec['name']!r} for {first} to {last}: {words}")
        failed += 0 if ok else 1
    return 1 if failed else 0


def _ctx_parts(ctx):
    from . import accounts
    base = ctx.db_path.parent
    path = accounts.path_for(ctx.config, base)
    if path is None or not Path(path).is_file():
        return base, None
    return base, accounts.connect(path)


def _trusted(ctx) -> list:
    to = ((ctx.raw_config or {}).get("mail") or {}).get("to") or []
    return [to] if isinstance(to, str) else list(to)


def cmd_reports(ctx) -> int:
    base, db = _ctx_parts(ctx)
    if db is None:
        if ctx.args.due:
            return 0                    # no accounts here: no client reports
        ctx.err("reports need accounts (access.mode: sessions)")
        return 2
    now = datetime.now(timezone.utc) if not getattr(ctx.args, "today", None) else ctx.now
    try:
        if ctx.args.due:
            return run_due(ctx.config, ctx.db_path, db, ctx.site, base, now, _trusted(ctx),
                           ctx.out)
        reports = cr.org_reports(db, ctx.site)
        if ctx.args.send or ctx.args.pdf:
            want = ctx.args.send or ctx.args.pdf
            report = next((r for r in reports if r["id"] == want), None)
            if report is None:
                ctx.err(f"{ctx.site}: no report {want}")
                return 2
            if ctx.args.pdf:
                from .client_report_data import Refused
                try:
                    got = compose(ctx.config, ctx.db_path, db, report, base, now,
                                  trusted=_trusted(ctx))
                except Refused as why:
                    ctx.err(f"refused: {why}")
                    return 1
                Path(ctx.args.out or got["file"]).write_bytes(got["pdf"])
                ctx.out(f"wrote {ctx.args.out or got['file']} ({len(got['pdf']):,} bytes)")
                return 0
            ok, words = send(ctx.config, ctx.db_path, db, report, base, "skald reports", now,
                             trusted=_trusted(ctx))
            ctx.out(f"{report['spec']['name']}: {words}")
            return 0 if ok else 1
        from .window import zone
        tz = zone(ctx.config)
        for r in reports:
            nxt = cr.next_send(r["spec"], now, tz)
            last = cr.sends(db, r["org_id"], r["id"], 1)
            when = f"next {nxt.astimezone(tz):%Y-%m-%d %H:%M}" if nxt else "not scheduled"
            ctx.out(f"{r['id']}: {r['spec']['name']} - {when}"
                    + (" (paused)" if r["spec"].get("paused") else ""))
            if last:
                ctx.out(f"    last {last[0]['at']}: {last[0]['detail']}")
        if not reports:
            ctx.out(f"{ctx.site}: no client reports")
        return 0
    finally:
        db.close()


def add_command(sub) -> None:
    p = sub.add_parser("reports", help="client reports: send the due ones, list, send or "
                       "write one (Settings > Reports)")
    which = p.add_mutually_exclusive_group()
    which.add_argument("--due", action="store_true", help="send every report that is due")
    which.add_argument("--list", action="store_true", help="each report and its sends")
    which.add_argument("--send", type=int, metavar="ID", help="send this report now")
    which.add_argument("--pdf", type=int, metavar="ID", help="write its PDF, send nothing")
    p.add_argument("--out", metavar="FILE", help="with --pdf: where to write it")
    p.set_defaults(run=cmd_reports)

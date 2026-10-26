"""Mail recipients typed on the page must confirm before Skald mails them.

The install's SMTP server sends for every organisation, so an address added
in Settings > Mail & reports (`mail.to`, a site or organisation row) gets nothing but
one confirm mail until its owner follows the link in it:

  * `request` makes the link: at most one per address per day, whichever
    organisation asks (so the server cannot be used to flood an address)
  * the link opens /traffic-auth/mail-confirm?t=<token>, a page with one
    button (a mail scanner that only fetches the link confirms nothing);
    the button posts the token back and the address is confirmed for that
    organisation. A link works for CONFIRM_DAYS days, once.
  * settings_store.apply drops every page-set recipient that is not
    confirmed, so the daily and weekly mails and alerts never reach it.
    Addresses in config.yml's own `mail.to` count as confirmed: whoever
    runs the server wrote them.

Kept in accounts.sqlite, table `mail_confirms`, made here on first use.
Like every address in that file, only an HMAC of the address is kept
(accounts/db.keyed_hash); the token only as SHA-256.
"""
from __future__ import annotations

import secrets
import sqlite3
from html import escape
from urllib.parse import parse_qs

from .accounts import db as base

CONFIRM_DAYS = 7
EVERY = 86400                 # seconds between two confirm mails to one address
PAGE = "mail-confirm"
TABLE = ("CREATE TABLE IF NOT EXISTS mail_confirms (org_id INTEGER NOT NULL, "
         "email_hash TEXT NOT NULL, token_hash TEXT, sent_at TEXT, confirmed_at TEXT, "
         "PRIMARY KEY (org_id, email_hash))")
CSP = ("default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
       "frame-ancestors 'none'; base-uri 'none'")


def _ready(db) -> None:
    db.execute(TABLE)


def _key(db, email: str) -> str:
    return base.keyed_hash(db, str(email).strip().lower())


def is_confirmed(db, org_id, email) -> bool:
    try:
        row = db.execute("SELECT confirmed_at FROM mail_confirms WHERE org_id = ? AND "
                         "email_hash = ?", (int(org_id or 0), _key(db, email))).fetchone()
    except sqlite3.OperationalError:          # no table yet: nobody confirmed
        return False
    return bool(row and row[0])


def keep_confirmed(db, org_id, emails, also=()) -> tuple[list, list]:
    """(the addresses that may be mailed, the ones still waiting). `also`:
    addresses that count as confirmed (config.yml's own)."""
    trusted = {str(e).strip().lower() for e in (also or [])}
    kept, waiting = [], []
    for email in emails or []:
        ok = str(email).strip().lower() in trusted or is_confirmed(db, org_id, email)
        (kept if ok else waiting).append(email)
    return kept, waiting


def mark_confirmed(db, org_id, email) -> None:
    """Confirm an address without a mail (tests; an install admin's tools)."""
    _ready(db)
    db.execute("INSERT INTO mail_confirms (org_id, email_hash, confirmed_at) VALUES (?, ?, ?) "
               "ON CONFLICT(org_id, email_hash) DO UPDATE SET confirmed_at = "
               "excluded.confirmed_at, token_hash = NULL",
               (int(org_id or 0), _key(db, email), base.now()))


def request(db, org_id, email) -> str | None:
    """A new confirm token for `email` in this organisation, or None when it
    is confirmed already or a confirm mail went to it in the last day."""
    _ready(db)
    if is_confirmed(db, org_id, email):
        return None
    key = _key(db, email)
    with base.tx(db):
        last = db.execute("SELECT MAX(sent_at) FROM mail_confirms WHERE email_hash = ?",
                          (key,)).fetchone()[0]
        if last and last > base.shift(-EVERY):
            return None
        token = secrets.token_urlsafe(32)
        db.execute("INSERT INTO mail_confirms (org_id, email_hash, token_hash, sent_at) "
                   "VALUES (?, ?, ?, ?) ON CONFLICT(org_id, email_hash) DO UPDATE SET "
                   "token_hash = excluded.token_hash, sent_at = excluded.sent_at",
                   (int(org_id or 0), key, base.sha256(token), base.now()))
    return token


def confirm(db, token) -> dict | None:
    """{"org_id"} when the token was good (used up now), else None."""
    if not token or len(str(token)) > 200:
        return None
    _ready(db)
    with base.tx(db):
        row = db.execute("SELECT org_id, email_hash, sent_at FROM mail_confirms WHERE "
                         "token_hash = ?", (base.sha256(str(token)),)).fetchone()
        if row is None or not row["sent_at"] or \
                row["sent_at"] < base.shift(-CONFIRM_DAYS * 86400):
            return None
        db.execute("UPDATE mail_confirms SET confirmed_at = ?, token_hash = NULL WHERE "
                   "org_id = ? AND email_hash = ?", (base.now(), row["org_id"],
                                                     row["email_hash"]))
    return {"org_id": row["org_id"]}


# ------------------------------------------------------------ the mail

def confirm_mail(config, to: str, link: str, org: str, site: str):
    from . import mailer
    from .accounts import mails
    org = mailer.display_name(org, "an organisation")
    site = mailer.display_name(site, "a site")
    lines = [f"Someone at {org} asked Skald to send traffic mails for {site} to this "
             "address.",
             f"Nothing more is sent to it unless you confirm. The link works for "
             f"{CONFIRM_DAYS} days."]
    foot = "If you did not expect this, ignore this mail: you get no other mail from it."
    text = (f"Confirm Skald mails\n\n{lines[0]}\n\nConfirm here:\n{link}\n\n{lines[1]}\n\n"
            f"{foot}\n")
    return mails._build(config, to, "Confirm Skald mails", text,
                        mails._html("Confirm Skald mails", lines, link, "Confirm", foot))


def ask(db, config, allowed, org: dict, site: str, emails) -> None:
    """Mail a confirm link to each address that needs one (at most one a
    day each), off the request's clock. Never logs an address or a link."""
    from . import auth_api
    from .accounts import mails
    todo = []
    for email in emails:
        token = request(db, org["id"], email)
        url = auth_api.link(config, allowed, PAGE, token) if token else None
        if url:
            todo.append((email, url))
        elif token:
            auth_api.note("mail confirm link made but no base URL is set; no mail sent")

    def work():
        for email, url in todo:
            try:
                mails.deliver(confirm_mail(config, email, url, org["name"], site), config,
                              email)
                auth_api.note("mail confirm sent")
            except Exception as why:          # noqa: BLE001 - a thread never takes the helper down
                auth_api.note(f"mail confirm not sent: {type(why).__name__}")
    if todo:
        auth_api.spawn(work)


# ------------------------------------------------------------- the page

def _page(h, code: int, title: str, words: str, token: str | None = None) -> None:
    form = ""
    if token:
        form = (f'<form method="post" action="/traffic-auth/{PAGE}">'
                f'<input type="hidden" name="t" value="{escape(token)}">'
                '<button type="submit">Confirm</button></form>')
    data = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1"><title>Skald</title></head>'
            '<body style="font:16px/1.5 sans-serif;max-width:32em;margin:2em auto;padding:0 '
            f'16px"><h1 style="font-size:1.3em">{escape(title)}</h1><p>{escape(words)}</p>'
            f"{form}</body></html>").encode()
    h.send_response(code)
    h.send_header("Content-Type", "text/html; charset=utf-8")
    h.send_header("Content-Security-Policy", CSP)
    h.send_header("Cache-Control", "no-store")
    h.send_header("Referrer-Policy", "no-referrer")
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data)


def http(h, write: bool, config, live_dir) -> None:
    """GET: the page with one button; POST (form or JSON {t}): confirm."""
    from . import auth_api
    if not write:
        token = (auth_api.query(h.path).get("t") or "")[:200]
        return _page(h, 200, "Confirm Skald mails", "Press the button to receive the "
                     "traffic mails at this address.", token or None)
    try:
        length = min(int(h.headers.get("Content-Length") or 0), 4096)
    except ValueError:
        length = 0
    raw = h.rfile.read(length).decode("utf-8", "replace") if length > 0 else ""
    token = (parse_qs(raw).get("t") or [""])[0]
    if not token and raw.lstrip().startswith("{"):
        import json
        try:
            token = str((json.loads(raw) or {}).get("t") or "")
        except (ValueError, AttributeError):
            token = ""
    db = auth_api.open_db(config, live_dir)
    if db is None:
        return _page(h, 503, "Not set up", "Accounts are not set up on this server.")
    try:
        done = confirm(db, token)
    finally:
        db.close()
    if done is None:
        return _page(h, 400, "This link is not valid", "It was used already, or it is older "
                     f"than {CONFIRM_DAYS} days. Ask for the mails to be set up again.")
    return _page(h, 200, "Confirmed", "This address now receives the traffic mails. To stop "
                 "them, ask an admin of the organisation to remove it.")

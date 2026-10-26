"""Settings > Mail & reports > Preview (2.13): the daily or weekly mail exactly as the site
would send it now, built by the same code (mailer.build, mail_html.render) from
the same verified history, and never sent.

    GET <page>/settings/mail-preview?kind=daily|weekly   (settings_api.py; admins)

The answer is {subject, html}: the mail's HTML part with its one image (the
Skald mark, a CID part in the real mail) written in as a data: address, so a
sandboxed frame on the page shows it whole. Nothing is posted to an SMTP
server; the preview does not even need one set up: a missing server, sender or
recipient is filled with a stand-in on the reserved .invalid domain, and no login is read. A mail
the history cannot give yet (a day withheld, a week not whole) is refused with
the same words the morning run would log.
"""
from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

KINDS = ("daily", "weekly")
STAND_IN_FROM = "sender@preview.invalid"
STAND_IN_TO = "recipient@preview.invalid"


class NotYet(Exception):
    """The history cannot give this mail yet; the words say why."""


def preview_config(config: dict) -> dict:
    """The site's config with a mail section that builds without a server:
    the real sender and recipients when set, stand-ins when not, no login."""
    mail = dict((config or {}).get("mail") or {})
    to = mail.get("to") or []
    if isinstance(to, str):
        to = [to]
    mail.update(host=mail.get("host") or "preview.invalid", to=list(to) or [STAND_IN_TO],
                user=None, user_env=None, password_env=None, to_waiting=None)
    mail["from"] = mail.get("from") or STAND_IN_FROM
    if str(mail.get("security") or "").lower() not in ("starttls", "ssl", "none"):
        mail["security"] = "starttls"
    return {**(config or {}), "mail": mail}


def build(config: dict, history_path, kind: str, now: datetime | None = None) -> dict:
    """{subject, html} of the `kind` mail, as it would go at `now`."""
    from . import mail_html, mailer
    from .store import History
    from .window import zone
    if kind not in KINDS:
        raise ValueError(kind)
    if history_path is None or not Path(history_path).is_file():
        raise NotYet("No history is stored for this site yet.")
    conf = preview_config(config)
    tz = zone(conf)
    try:
        with History(history_path) as history:
            msg = mailer.build(kind, conf, history, tz, now)
    except mailer.Refused as why:          # Withheld too: a day that does not add up
        raise NotYet(f"The {kind} mail would not go now: {why}.") from None
    html = msg.get_body(("html",)).get_content()
    logo = mailer._logo()
    if logo is not None:
        data = "data:image/png;base64," + base64.b64encode(logo).decode("ascii")
        html = html.replace(f"cid:{mail_html.LOGO_CID}", data)
    return {"subject": str(msg["Subject"]), "html": html}

"""The account mails: "reset your password" and "you are invited".

Plain text plus a small HTML part, sent through the install's own mail
settings (`mail.host`, `mail.from`, credentials from the environment, as
mailer.py reads them); only the recipient differs from the report mails.
`mail.to` is not needed for these. A link is the only secret in a mail and
is never logged: callers write "sent" or "not sent", never the link or the
address.

    msg = reset_mail(config, "person@example.com", link)
    deliver(msg, config, "person@example.com")     # mailer.Refused if mail is not set up
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape as esc

from .. import mailer
from .invites import INVITE_DAYS
from .resets import RESET_MINUTES

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
ROLE_WORDS = {"owner": "an owner", "admin": "an admin", "viewer": "a viewer"}


def mail_settings(config: dict | None, to: str) -> dict:
    """mailer.settings for one recipient; mailer.Refused when mail is not set up.
    The install's SMTP settings from Settings > Mail are laid over config.yml
    (settings_store.apply), and the password may come from secrets.json."""
    from ..settings_store import apply
    config = apply(config or {}, None)
    section = dict(config.get("mail") or {})
    section["to"] = [to]
    keep = {k: config[k] for k in ("_resolved", "history", "hooks", "access") if k in config}
    return mailer.settings({**keep, "mail": section})


def configured(config: dict | None) -> bool:
    try:
        mail_settings(config, "check@example.com")
    except mailer.Refused:
        return False
    return True


def _html(title: str, paras: list[str], link: str, button: str, foot: str) -> str:
    body = "".join(f'<p style="margin:0 0 14px;font:400 15px/1.55 {FONT};color:#17212b">'
                   f"{esc(p)}</p>" for p in paras)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="color-scheme" content="light"></head>'
        '<body style="margin:0;padding:24px;background:#f4f6f8">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #dde3e8;'
        'border-radius:10px"><tr><td style="padding:24px 26px">'
        f'<div style="font:600 18px/1.3 {FONT};color:#17212b;padding-bottom:14px">'
        f"{esc(title)}</div>{body}"
        f'<p style="margin:18px 0"><a href="{esc(link)}" style="display:inline-block;'
        f'background:#17212b;color:#ffffff;text-decoration:none;padding:10px 18px;'
        f'border-radius:7px;font:600 15px/1.2 {FONT}">{esc(button)}</a></p>'
        f'<p style="margin:0 0 14px;font:400 13px/1.55 {FONT};color:#5b6670">'
        f'Or copy this address into your browser:<br><span style="word-break:break-all">'
        f"{esc(link)}</span></p>"
        f'<p style="margin:0;font:400 13px/1.55 {FONT};color:#5b6670">{esc(foot)}</p>'
        "</td></tr></table></body></html>")


def _build(config, to: str, subject: str, text: str, html: str) -> EmailMessage:
    cfg = mail_settings(config, to)
    msg = mailer._message(cfg, subject, text, html, datetime.now(timezone.utc))
    return msg


def reset_mail(config: dict | None, to: str, link: str) -> EmailMessage:
    lines = ["Someone asked to reset the password of the Skald account for this address.",
             f"The link works once, for {RESET_MINUTES} minutes. Using it signs out every "
             "browser signed in to this account."]
    foot = "If you did not ask for this, ignore this mail: your password stays as it is."
    text = (f"Reset your password\n\n{lines[0]}\n\nChoose a new password here:\n{link}\n\n"
            f"{lines[1]}\n\n{foot}\n")
    return _build(config, to, "Reset your password", text,
                  _html("Reset your password", lines, link, "Choose a new password", foot))


def invite_mail(config: dict | None, to: str, link: str, org: str, role: str,
                inviter: str = "") -> EmailMessage:
    # The organisation's name is typed by whoever made it: cut like a From
    # name, so a subject cannot carry an address, a link or markup.
    org = mailer.display_name(org, "an organisation")
    who = f"{inviter} invited you" if inviter else "You are invited"
    lines = [f"{who} to {org}'s traffic pages on Skald, as {ROLE_WORDS.get(role, role)}.",
             f"The link works once, for {INVITE_DAYS} days. If this address already has a "
             "Skald account, the link adds the organisation to it."]
    foot = "If you did not expect this, ignore this mail: nothing happens without the link."
    text = (f"You are invited to {org}\n\n{lines[0]}\n\nJoin here:\n{link}\n\n{lines[1]}\n\n"
            f"{foot}\n")
    return _build(config, to, f"You are invited to {org}", text,
                  _html(f"You are invited to {org}", lines, link, f"Join {org}", foot))


def deliver(msg: EmailMessage, config: dict | None, to: str) -> None:
    """Hand the mail to the SMTP server; mailer.Refused or OSError/SMTP errors on failure."""
    mailer.send(msg, mail_settings(config, to))

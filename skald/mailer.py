"""Daily and weekly mail, built from history and refused when it cannot add up.

The mail is the existing report - as_text and as_html - run over a Totals
rebuilt from verified history, with a comparison block on top for the week.
Before anything is built, the same arithmetic checks run again on the rebuilt
figures. A mail goes out only when:

  * every day it covers was collected and verified (a withheld or missing
    day is a refusal, not a smaller number)
  * the window parsed at least one line
  * verify.check finds nothing wrong with the summed figures

Otherwise `Refused` is raised, the command exits non-zero and nothing is sent.

Credentials are never in the config. `mail.user_env` and `mail.password_env`
name environment variables, and they are read here at send time. If a
variable is named and not set, that is a refusal too: sending anonymously
because a password went missing is the kind of quiet fallback that ends with
a relay rejecting mail for a week while the cron log says nothing.

With Settings > Mail (settings_store.py) an install admin may type the SMTP
login instead: `mail.user` (a plain setting) and the password, kept in
secrets.json beside the history under the same name as its environment
variable (`mail.password_env`, else SKALD_SMTP_PASSWORD). The
environment always wins.
"""
from __future__ import annotations

import os
import re
import smtplib
import ssl
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid, parseaddr
from html import escape as esc
from zoneinfo import ZoneInfo

from . import brand
from .classify import Group
from .config import country_credit, setting, site_name
from .kpi import KPIS, change
from .report import FONT, INK, MUTE, RULE, FAINT, as_html, as_text
from .store import History, Period
from .verify import check

ORDER = [Group.PEOPLE, Group.ANSWER_ENGINE, Group.SEARCH_ENGINE,
         Group.BOTS, Group.OURS]


class Refused(Exception):
    """The mail would not be honest, or could not be sent safely."""


class Withheld(Refused):
    """Refused for the data, by design: a day in it is withheld, partial or
    not collected, or the sum does not reconcile. Not a failure of the run
    (no failure mail, failmail.py); a bad mail setting is a plain Refused."""


def _cards(config: dict) -> list[Group]:
    names = setting(config, "report", "cards")
    return [g for g in ORDER if not names or g.value in names]


def _long(d: date) -> str:
    return f"{d:%a} {d.day} {d:%b %Y}"


def _short(d: date) -> str:
    return f"{d.day} {d:%b}"


def settings(config: dict) -> dict:
    """The mail section, checked, with credentials read from the environment."""
    mail = config.get("mail") or {}
    host = mail.get("host")
    sender = mail.get("from")
    to = mail.get("to") or []
    if isinstance(to, str):
        to = [to]
    if host and sender and not to and mail.get("to_waiting"):
        # Every recipient typed on the page still has to confirm (mail_confirm.py).
        raise Withheld(f"no recipient has confirmed yet ({mail['to_waiting']} waiting for "
                       "the confirm link in their mail)")
    if not host or not sender or not to:
        raise Refused("mail.host, mail.from and mail.to must all be set")
    port = int(mail.get("port") or 587)
    security = str(mail.get("security") or ("ssl" if port == 465 else "starttls")).lower()
    if security not in ("starttls", "ssl", "none"):
        raise Refused(f"mail.security must be starttls, ssl or none, not {security!r}")

    user, password = login(config)
    if (user or password) and security == "none":
        raise Refused("refusing to send SMTP credentials without TLS; "
                      "set mail.security to starttls or ssl")
    return {
        "host": str(host), "port": port, "security": security,
        "from": _sender(str(sender), mail.get("from_name")), "to": [str(t) for t in to],
        "user": user, "password": password,
        # The brand's "[Skald]" unless the config names its own prefix.
        "prefix": str(mail.get("subject_prefix") or brand.prefix()).strip(),
    }


def login(config: dict) -> tuple[str | None, str | None]:
    """(user, password) for the SMTP server, or (None, None) for a relay
    that needs none. The user: `mail.user` (Settings), else the variable
    `mail.user_env` names. The password: the variable `mail.password_env`
    names (SKALD_SMTP_PASSWORD when only `mail.user` is set), from
    the environment, else from secrets.json. A named one missing: Refused."""
    from .settings_store import SMTP_PASSWORD_ENV, stored_secret
    mail = config.get("mail") or {}

    def secret(name: str, what: str) -> str:
        try:
            value = stored_secret(config, name)
        except PermissionError as why:
            raise Refused(f"the secrets file cannot be used: {why}") from None
        if not value:
            raise Refused(f"{what} is not set (environment variable {name}, "
                          "or Settings > Mail)")
        return value

    user = str(mail.get("user") or "").strip() or None
    if user is None and mail.get("user_env"):
        user = secret(str(mail["user_env"]), "mail.user_env")
    name = mail.get("password_env") or (SMTP_PASSWORD_ENV if user else None)
    password = secret(str(name), "the SMTP password") if name else None
    return user, password


# A name shown in a From header or a subject: letters, digits, spaces and
# . - ' only, at most NAME_MOST characters (the install's SMTP server sends
# for every organisation; a name like "Bank <help@...>" must not pass).
NAME_MOST = 40
NAME_NOT = re.compile(r"[^A-Za-z0-9 .'-]+")


def display_name(raw, fallback: str = "") -> str:
    """`raw` cut to the characters and length a shown name may have."""
    got = " ".join(NAME_NOT.sub(" ", str(raw or "")).split())[:NAME_MOST].strip()
    return got or fallback


def _sender(configured: str, name=None) -> str:
    """The From header: the configured address, shown as the brand's name
    (brand.py) unless `mail.from_name` names another (cut by display_name)."""
    _, address = parseaddr(configured)
    if not address:
        return configured
    brand_name = display_name(brand.load()["name"], "Skald")
    return formataddr((display_name(name, brand_name) if name else brand_name, address))


def _logo() -> bytes | None:
    """The Skald mark sent inside the mail (assets/brand/skald-180.png)."""
    try:
        data = (brand.ROOT / "assets" / "brand" / "skald-180.png").read_bytes()
    except OSError:
        return None
    return data if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) < 100_000 else None


def partial_words(period: Period, tz: ZoneInfo) -> str:
    """'partial day, data from 14:05', or '' for a whole day."""
    if not period.partial:
        return ""
    day = period.partial[0]
    parts = []
    if day in period.partial_from:
        parts.append(f"data from {period.partial_from[day].astimezone(tz):%H:%M}")
    if day in period.partial_until:
        parts.append(f"data until {period.partial_until[day].astimezone(tz):%H:%M}")
    return "partial day, " + ", ".join(parts)


def _gate(period: Period, what: str, allow_partial: bool = False) -> None:
    """Refuse unless every day is verified and the sum still reconciles.

    A partial day - the logs did not cover all of it - is refused for the
    week: a week with a short day in it is not a week to compare. The daily
    mail for that very day may go, saying so in its subject and first line.
    """
    if period.partial and not allow_partial:
        raise Withheld(f"{what}: partial day(s) "
                      + ", ".join(d.isoformat() for d in period.partial)
                      + " - the logs do not cover the whole day; a week needs "
                        "seven whole days")
    if period.withheld:
        raise Withheld(f"{what}: withheld because the figures did not reconcile on "
                      + ", ".join(d.isoformat() for d in period.withheld))
    if period.missing:
        raise Withheld(f"{what}: not collected for "
                      + ", ".join(d.isoformat() for d in period.missing)
                      + " - run collect or backfill first")
    if period.totals.parsed == 0:
        raise Withheld(f"{what}: the window parsed zero lines")
    problems = check(period.totals)
    if problems:
        raise Withheld(f"{what}: figures do not reconcile: "
                      + "; ".join(str(p) for p in problems))


def _link(url: str | None) -> tuple[str, str]:
    if not url:
        return "", ""
    text = f"\nDashboard: {url}\n"
    html = (f'<div style="font:400 13px/1.6 {FONT};color:{MUTE};padding-top:10px" '
            f'class="mute">Dashboard: <a href="{esc(url)}" style="color:{INK}">'
            f'{esc(url)}</a></div>')
    return text, html


def _comparison(current: Period, previous: Period) -> tuple[str, str]:
    """This week against the week before, as text and as a mail-safe table."""
    comparable = previous.complete
    lines = [f"THIS WEEK AGAINST THE WEEK BEFORE "
             f"({_short(previous.first)} to {_short(previous.last)})"]
    rows = []
    for k in KPIS:
        now_v = k.value(current.totals)
        before = k.value(previous.totals) if comparable else None
        arrow, words = change(now_v, before)
        shown = f"{arrow} {words}".strip()
        prev_s = f"{before:,}" if before is not None else "-"
        now_s = f"{now_v:,}" if now_v is not None else "-"
        lines.append(f"  {k.label:<34} {now_s:>9}  {prev_s:>9}  {shown}")
        rows.append(
            f'<tr><td style="padding:6px 8px 6px 0;border-bottom:1px solid {RULE};'
            f'font:400 13px/1.4 {FONT};color:{INK}" class="ink hr">{esc(k.label)}</td>'
            f'<td align="right" style="padding:6px 0 6px 8px;border-bottom:1px solid '
            f'{RULE};font:600 13px/1.4 {FONT};color:{INK}" class="ink hr">{now_s}</td>'
            f'<td align="right" style="padding:6px 0 6px 8px;border-bottom:1px solid '
            f'{RULE};font:400 13px/1.4 {FONT};color:{MUTE}" class="mute hr">{prev_s}</td>'
            f'<td align="right" style="padding:6px 0 6px 8px;border-bottom:1px solid '
            f'{RULE};font:400 13px/1.4 {FONT};color:{MUTE};white-space:nowrap" '
            f'class="mute hr">{esc(shown)}</td></tr>')
    if not comparable:
        note = (f"The week before is not fully recorded ({len(previous.recorded)} of "
                f"7 days), so no change is stated.")
    else:
        note = "Arrows show direction only: more bots is up, and so is more readers."
    lines.append(f"  {note}")
    th = (f'style="padding:0 0 6px 8px;font:600 11px/1.4 {FONT};color:{FAINT};'
          f'text-transform:uppercase;letter-spacing:.04em" class="mute"')
    html = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'class="card" style="border-collapse:collapse;background:#ffffff;'
        f'border:1px solid {RULE};border-radius:10px;margin-bottom:14px">'
        f'<tr><td style="padding:14px 18px">'
        f'<div class="ink" style="font:600 15px/1.3 {FONT};color:{INK};'
        f'padding-bottom:8px">This week against the week before</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse"><tr><td></td>'
        f'<td align="right" {th}>This week</td><td align="right" {th}>'
        f'{_short(previous.first)}-{_short(previous.last)}</td>'
        f'<td align="right" {th}>Change</td></tr>{"".join(rows)}</table>'
        f'<div class="mute" style="font:400 12px/1.5 {FONT};color:{FAINT};'
        f'padding-top:8px">{esc(note)}</div></td></tr></table>')
    return "\n".join(lines) + "\n\n", html


def _insights(history: History, site: str, anchor: date, config: dict,
              n: int) -> tuple[str, str]:
    """The top `n` insights (insights.py) as text and a mail-safe card."""
    from .insights import compute
    found = compute(history, site, anchor, config)["insights"][:n]
    if not found:
        return "", ""
    lines = ["WHAT CHANGED"] + [f"  - {i['title']} [{i['type']}]" for i in found]
    rows = "".join(
        f'<tr><td style="padding:5px 0;border-bottom:1px solid {RULE};font:400 13px/1.45 '
        f'{FONT};color:{INK}" class="ink hr">{esc(i["title"])} '
        f'<span style="color:{MUTE}" class="mute">({esc(i["type"])})</span></td></tr>'
        for i in found)
    html = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'class="card" style="border-collapse:collapse;background:#ffffff;border:1px solid '
            f'{RULE};border-radius:10px;margin-bottom:14px"><tr><td style="padding:14px 18px">'
            f'<div class="ink" style="font:600 15px/1.3 {FONT};color:{INK};padding-bottom:6px">'
            f'What changed</div><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" style="border-collapse:collapse">{rows}</table>'
            f'<div class="mute" style="font:400 12px/1.5 {FONT};color:{FAINT};padding-top:8px">'
            f'Only whole, verified days are compared.</div></td></tr></table>')
    return "\n".join(lines) + "\n\n", html


def _message(cfg: dict, subject: str, text: str, html: str,
             now: datetime) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"{cfg['prefix']} {subject}".strip()
    msg["From"] = cfg["from"]
    msg["To"] = ", ".join(cfg["to"])
    msg["Date"] = format_datetime(now)
    domain = cfg["from"].rsplit("@", 1)[-1].strip("> ") or None
    msg["Message-ID"] = make_msgid(domain=domain)
    msg["Auto-Submitted"] = "auto-generated"
    # Every mail ends with the brand line: name, version, release, tagline.
    sign = brand.line()
    msg.set_content(text.rstrip("\n") + f"\n\n-- \n{sign}\n")
    if esc(sign) not in html:           # the branded layout carries its own footer
        foot = (f'<p style="margin:24px 0 0;font:12px/1.5 {FONT};color:{MUTE}">'
                f"{esc(sign)}</p>")
        html = html.replace("</body>", foot + "</body>", 1) if "</body>" in html else html + foot
    msg.add_alternative(html, subtype="html")
    return msg


def build(kind: str, config: dict, history: History, tz: ZoneInfo,
          now: datetime | None = None) -> EmailMessage:
    """The daily (yesterday) or weekly (last 7 complete days) mail."""
    if kind not in ("daily", "weekly"):
        raise ValueError(kind)
    cfg = settings(config)
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    site = site_name(config)
    last = now.date() - timedelta(days=1)
    cards = _cards(config)
    link_text, link_html = _link(setting(config, "dashboard", "url"))
    zone = str(tz)

    if kind == "daily":
        period = history.period(site, last, last, include_partial=True)
        _gate(period, f"daily mail for {last}", allow_partial=True)
        when = _long(last)
        partial = partial_words(period, tz)
        title = f"{site}: traffic on {when}" + (f" - {partial}" if partial else "")
        subtitle = (f"{when}: {partial}. Not a whole day, and not used in any "
                    f"comparison." if partial else f"{when}, midnight to midnight {zone}")
        preface_text, preface_html = "", ""
        subject = f"{site}: daily traffic, {when}" + (f" - {partial}" if partial else "")
    else:
        first = last - timedelta(days=6)
        period = history.period(site, first, last)
        _gate(period, f"weekly mail for {first} to {last}")
        previous = history.period(site, first - timedelta(days=7),
                                  first - timedelta(days=1))
        when = f"{_short(first)} to {_short(last)} {last.year}"
        title = f"{site}: traffic, {when}"
        subtitle = f"7 days, {_long(first)} to {_long(last)}, {zone}"
        preface_text, preface_html = _comparison(period, previous)
        subject = f"{site}: weekly traffic, {when}"

    found_text, found_html = _insights(history, site, last, config,
                                       5 if kind == "daily" else 10)
    from .insights import compute
    found = compute(history, site, last, config)["insights"][:5 if kind == "daily" else 10]
    preface_text += found_text
    preface_html += found_html
    credit = country_credit(config)
    text = (f"{title}\n{subtitle}\n\n{preface_text}"
            + as_text(period.totals, cards, credit, tz_name=zone) + link_text)
    # The HTML part: the branded layout (mail_html.py), from the same period.
    from . import mail_html
    if kind == "daily":
        week_ago = last - timedelta(days=7)
        before = history.period(site, week_ago, week_ago)
        first = last
        partial_text = partial
    else:
        before, partial_text = previous, ""
    logo = _logo()
    html = mail_html.render(kind, config, history, tz, site, first, last, period, before,
                            found, partial_text, setting(config, "dashboard", "url"),
                            cfg["to"], credit, logo is not None)
    msg = _message(cfg, subject, text, html, now)
    if logo is not None:
        body = msg.get_body(("html",))
        body.add_related(logo, maintype="image", subtype="png",
                         cid=f"<{mail_html.LOGO_CID}>", filename="skald.png",
                         disposition="inline")  # "attachment" (the default with a filename) breaks the image in Gmail
    if kind == "weekly":
        # The printable report of the same week, when mail.weekly_report_attachment
        # is on (off by default). Built from the same verified days.
        from .report_export import Refused as NoReport, weekly_attachment
        try:
            got = weekly_attachment(config, history, tz, now)
        except NoReport:
            got = None
        if got:
            msg.add_attachment(got[1], maintype="text", subtype="html", filename=got[0])
    return msg


def send(msg: EmailMessage, cfg: dict) -> None:
    """Hand the message to the configured SMTP server."""
    context = ssl.create_default_context()
    if cfg["security"] == "ssl":
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30,
                                  context=context)
    else:
        server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=30)
    try:
        if cfg["security"] == "starttls":
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
        if cfg["user"]:
            server.login(cfg["user"], cfg["password"] or "")
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            pass


def preview(msg: EmailMessage) -> str:
    """What --dry-run prints: the headers and the text part."""
    head = "\n".join(f"{k}: {v}" for k, v in msg.items())
    text = msg.get_body(("plain",)).get_content()
    html = msg.get_body(("html",)).get_content()
    return (f"{head}\n\n{text}\n[HTML part: {len(html):,} characters; "
            f"pass --save-html PATH to look at it]\n")

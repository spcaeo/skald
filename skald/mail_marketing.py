"""The Monday marketing mail (2.43): last week from the log, then each connected
tool's own figures, apart and labelled. Optional, off by default: `mail.marketing`
(Settings > This site > Mail & reports). Sent on Mondays by run-daily, after the
weekly mail, to the same recipients (mail.to), through the same mail server.

  Skald's part    the last 7 whole days (the site's time zone): visitors, pages
                  read and leads, each with its change against the 7 days before
                  (only when both weeks are whole and verified), then where visitors
                  came from. The figures are mail_html.figures and mail_html._sources,
                  the weekly mail's own (leads: period_leads, counted twice)
  the tools       one card per connected tool (yourtools.api.view, the Overview
                  card's answer): its headline figures under "Counted from: <tool>",
                  the tool's own period and freshness. A figure the tool did not give
                  is "Not given", never 0; a withheld tool says so and shows nothing;
                  a tool that stopped answering says since when. Never added to
                  Skald's figures

Nothing new is counted here. The week is gated like the weekly mail (mailer._gate):
a day not whole, not verified or not collected refuses the mail, by design.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from html import escape as esc
from pathlib import Path

from . import mail_html as H
from . import mailer
from .classify import Group
from .config import site_name

TILES = (("visitors", "Visitors"), ("pages", "Pages read"), ("leads", "Leads"))


def on(config: dict) -> bool:
    """mail.marketing: off unless switched on."""
    got = (config.get("mail") or {}).get("marketing")
    return got is True or str(got).strip().lower() in ("true", "yes", "on", "1")


def _value(v) -> str:
    return "Not given" if v is None else f"{v:,}" if isinstance(v, int) else f"{v:,.2f}"


def tools(config: dict, folder, site: str, now: datetime) -> list[dict]:
    """The connected tools, as Overview's card has them."""
    from .yourtools import api
    got = api.view(config, folder, site, admin=False, now=now)
    return [t for t in got["tools"] if t["state"] not in ("off",)]


def _tool_lines(t: dict) -> tuple[list[tuple[str, str]], str]:
    """(label, value) rows and the note under them."""
    if t.get("withheld"):
        return [], t["withheld"]
    period = t.get("period") or {}
    when = (f"{period['start']} to {period['end']}" + (f", {period['note']}"
                                                       if period.get("note") else "")
            if period.get("start") else "")
    state = t["state"]
    fresh = {"answering": f"Answered {t['ago']}.",
             "failing": f"The last try failed; these are from {t['ago']}.",
             "stopped": (f"Stopped answering; these are from {t['ago']}." if t.get("last_ok")
                         else "Not answering yet."),
             "waiting": "Waiting for its first answer.",
             "no_key": "Needs its key."}.get(state, t.get("words", ""))
    rows = [(h["label"], _value(h["value"])) for h in t.get("headline") or []]
    return rows, " ".join(x for x in (f"The tool's own period: {when}." if when else "", fresh,
                                      "Never added to Skald's figures.") if x)


def build(config: dict, history, tz, now: datetime, folder) -> "mailer.EmailMessage":
    cfg = mailer.settings(config)
    now = now.astimezone(tz)
    site = site_name(config)
    last = now.date() - timedelta(days=1)
    first = last - timedelta(days=6)
    period = history.period(site, first, last)
    mailer._gate(period, f"marketing mail for {first} to {last}")
    before = history.period(site, first - timedelta(days=7), first - timedelta(days=1))
    now_f = H.figures(config, history, site, tz, period, first, last)
    before_f = (H.figures(config, history, site, tz, before, before.first, before.last)
                if H.whole(period) and H.whole(before) else None)
    people = period.totals.groups.get(Group.PEOPLE)
    when = f"{mailer._short(first)} to {mailer._short(last)} {last.year}"
    subject = f"{site}: marketing week, {when}"

    # The plain part.
    text = [f"{site}: marketing week, {when}", f"7 days, {mailer._long(first)} to "
            f"{mailer._long(last)}, {tz}", "", "Counted from: your server log"]
    for key, name in TILES:
        delta = H.change(now_f[key], (before_f or {}).get(key)) if before_f else "—"
        text.append(f"  {name}: {H._n(now_f[key])} ({delta} against the 7 days before)")
    by = (people.by or {}).get("source") or {} if people and period.totals.breakdowns else {}
    if by:
        text.append("  Where visitors came from:")
        for name, n in sorted(by.items(), key=lambda kv: (-kv[1], kv[0]))[:H.ROWS]:
            text.append(f"    {H.shown_text(name)}: {n:,}")
    connected = tools(config, folder, site, now)
    for t in connected:
        rows, note = _tool_lines(t)
        text += ["", t["counted_from"]] + [f"  {a}: {b}" for a, b in rows] + [f"  {note}"]
    if not connected:
        text += ["", "No tool connected (Settings > This site > Leads & tools > Connect a "
                     "tool)."]
    link_text, _ = mailer._link(mailer.setting(config, "dashboard", "url"))
    body_text = "\n".join(text) + "\n" + link_text

    # The HTML part: the weekly mail's cards.
    tiles = "".join(
        f'<td valign="top" width="33%" style="padding:4px 4px 10px"><div class="s-ink3" '
        f'style="font:600 11px/1.3 {H.FONT};color:{H.INK3};text-transform:uppercase;'
        f'letter-spacing:.04em">{esc(name)}</div><div class="s-ink" style="font:700 26px/1.2 '
        f'{H.FONT};color:{H.INK};padding:4px 0 2px">{H._n(now_f[key])}</div><div class="s-ink2" '
        f'style="font:500 12px/1.3 {H.FONT};color:{H.INK2}">'
        f'{esc(H.change(now_f[key], before_f.get(key)) if before_f else "—")}</div></td>'
        for key, name in TILES)
    cards = [H._card("Counted from: your server log",
                     f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                     f'style="border-collapse:collapse"><tr>{tiles}</tr></table>',
                     esc(f"Visitors are {H.VISITORS_RULE}. Change against the 7 days before, "
                         f"only when both are whole, verified weeks. {H.LEAD_RULE}")),
             H._sources(people) if period.totals.breakdowns
             else H._unmeasured("Where visitors came from")]
    for t in connected:
        rows, note = _tool_lines(t)
        cards.append(H._card(t["counted_from"],
                             H._table([(esc(a), b, "") for a, b in rows]) if rows else "",
                             esc(note)))
    if not connected:
        cards.append(H._card("From your tools", "", esc(
            "No tool connected. Connect one on Settings > This site > Leads & tools.")))
    who = ", ".join(cfg["to"])
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        f'<title>{esc(subject)}</title><style>{H.DARK}</style></head>'
        f'<body class="s-page" style="margin:0;padding:0;background:{H.PAGE}">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'class="s-page" bgcolor="{H.PAGE}" style="background:{H.PAGE}"><tr><td align="center" '
        f'style="padding:24px 10px"><table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0" style="max-width:640px;width:100%"><tr><td class="s-pad" '
        f'style="padding:0 6px">'
        f'<div class="s-ink" style="font:700 18px/1.35 {H.FONT};color:{H.INK};padding:0 0 2px">'
        f'{esc(site)} · Marketing week · {first:%a} {first.day} {first:%b} – {last:%a} '
        f'{last.day} {last:%b %Y}</div><div class="s-ink2" style="font:400 13px/1.5 {H.FONT};'
        f'color:{H.INK2};padding:0 0 16px">7 days, midnight to midnight, {esc(str(tz))}. '
        f'Skald\'s figures first; each tool\'s own figures after, apart.</div>'
        + "".join(cards) + H._button(mailer.setting(config, "dashboard", "url"))
        + f'<div class="s-ink3" style="font:400 12px/1.6 {H.FONT};color:{H.INK3};'
        f'text-align:center;padding:6px 12px 0">You get this because {esc(who)} '
        f'{"are" if len(cfg["to"]) > 1 else "is"} on the '
        f'report list for {esc(site)} and the Monday marketing mail is on (Settings › This '
        f'site › Mail &amp; reports).</div></td></tr></table></td></tr></table></body></html>')
    return mailer._message(cfg, subject, body_text, html, now)


def run(ctx, dry_run: bool) -> int:
    """run-daily's step: build and send; a week the history refuses stops the
    run by design, as the weekly mail does."""
    try:
        cfg = mailer.settings(ctx.config)
        with ctx.history() as history:
            msg = build(ctx.config, history, ctx.tz, ctx.now, Path(ctx.db_path).parent)
    except mailer.Refused as why:
        ctx.err(f"marketing mail REFUSED: {why}")
        if isinstance(why, mailer.Withheld):
            ctx.by_design = str(why)
        return 1
    if dry_run:
        ctx.out(mailer.preview(msg))
        return 0
    mailer.send(msg, cfg)
    ctx.out(f"sent marketing mail to {', '.join(cfg['to'])}: {msg['Subject']}")
    return 0


def due(ctx) -> bool:
    """Mondays, as the weekly mail (cli.daily_steps), when switched on."""
    return ctx.now.date().weekday() == 0 and on(ctx.config)

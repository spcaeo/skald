"""Reports to keep or send: `skald report --from D --to D [--view V]
--format html|csv-zip --out PATH`.

html     one self-contained page (inline styles, no script, nothing fetched):
         the period's cards - the same renderer as the mails, so the two
         cannot disagree - a day-by-day table, and which days are left out
         and why. Print it from a browser to get a PDF.
csv-zip  every export table (export.TABLES) as CSV over the same days, the
         daily figures first, plus README.txt naming the period, the view and
         the days recorded, partial, withheld and missing.

Both are built from history's verified days only, and refused when the
summed figures do not reconcile (verify.check) - the rule every mail and
page follows. The weekly mail can carry the html report as an attachment
(`mail.weekly_report_attachment: true`; off by default).
"""
from __future__ import annotations

import io
import zipfile
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from .config import country_credit, setting, site_name
from .store import History, view_key


class Refused(Exception):
    pass


def _period(history: History, key: str, first: date, last: date):
    from .verify import check
    period = history.period(key, first, last)
    if not period.recorded:
        raise Refused(f"no verified whole day between {first} and {last}")
    problems = check(period.totals)
    if problems:
        raise Refused("the period's figures do not reconcile: "
                      + "; ".join(str(p) for p in problems))
    return period


def _days(dates) -> str:
    return ", ".join(d.isoformat() for d in dates) or "none"


def coverage(period) -> list[tuple[str, str]]:
    return [("Days in the report", f"{len(period.recorded)} of {period.length}"),
            ("Partial days, left out", _days(period.partial)),
            ("Withheld days (did not reconcile)", _days(period.withheld)),
            ("Days not recorded", _days(period.missing))]


def html_report(config: dict, history: History, tz, first: date, last: date,
                view=None, now: datetime | None = None) -> str:
    from .mailer import _cards
    from .report import as_html
    site = site_name(config)
    key = view_key(site, view.slug if view else None)
    period = _period(history, key, first, last)
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    scope = f" - {view.name} ({view.describe()})" if view else ""
    from . import brand
    title = f"{site}{scope}: traffic report, {first:%d %b %Y} to {last:%d %b %Y}"
    subtitle = (f"{brand.line()}. {period.length} days, midnight to midnight {tz}; "
                f"verified days only. Made {now:%d %b %Y %H:%M}.")
    rows = "".join(
        f"<tr><td style='padding:3px 10px 3px 0'>{escape(k)}</td>"
        f"<td style='padding:3px 0'>{escape(v)}</td></tr>" for k, v in coverage(period))
    days = []
    for e in history.daily(key, first, last):
        if e["state"] in ("ok", "partial"):
            g = e["groups"]
            from .classify import Group
            people = g[Group.PEOPLE]
            cells = [e["day"].isoformat() + (" (partial)" if e["state"] == "partial" else ""),
                     people["readers"] if people["readers"] is not None else "-",
                     people["views"], g[Group.ANSWER_ENGINE]["hits"],
                     g[Group.SEARCH_ENGINE]["hits"], g[Group.BOTS]["hits"],
                     sum(v["hits"] for v in g.values())]
        else:
            cells = [e["day"].isoformat(), e["state"], "", "", "", "", ""]
        days.append("<tr>" + "".join(
            f"<td style='padding:3px 8px;border-bottom:1px solid #e5e5e5;text-align:"
            f"{'left' if i == 0 else 'right'}'>{escape(str(c))}</td>"
            for i, c in enumerate(cells)) + "</tr>")
    head = "".join(f"<th style='padding:3px 8px;text-align:{'left' if i == 0 else 'right'};"
                   f"border-bottom:2px solid #999'>{h}</th>" for i, h in enumerate(
                       ("Day", "Readers", "Pages read", "AI requests", "Search", "Bots",
                        "All requests")))
    preface = (f"<table style='font:13px/1.4 sans-serif;margin:0 0 16px'>{rows}</table>")
    postscript = (f"<h2 style='font:600 16px sans-serif;margin:24px 0 8px'>Day by day</h2>"
                  f"<table style='border-collapse:collapse;font:13px/1.4 sans-serif'>"
                  f"<thead><tr>{head}</tr></thead><tbody>{''.join(days)}</tbody></table>")
    body = as_html(period.totals, _cards(config), title, subtitle, preface=preface,
                   postscript=postscript, credit=country_credit(config), tz_name=str(tz))
    style = ("<style>@media print{body{margin:0}a{color:inherit;text-decoration:none}}"
             "@page{margin:14mm}</style>")
    meta = ('<meta name="robots" content="noindex, nofollow, noarchive">'
            '<meta name="referrer" content="no-referrer">')
    if "<head>" in body:
        return body.replace("<head>", "<head>" + meta + style, 1)
    return f"<!doctype html><html><head><meta charset='utf-8'>{meta}{style}" \
           f"<title>{escape(title)}</title></head><body>{body}</body></html>"


def csv_zip(config: dict, history: History, tz, first: date, last: date,
            view=None) -> bytes:
    from . import export
    site = site_name(config)
    key = view_key(site, view.slug if view else None)
    period = _period(history, key, first, last)
    credit = country_credit(config)
    credit_text = (credit[0] + (f" ({credit[1]})" if credit[1] else "")) if credit else None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        from . import brand
        readme = [brand.line(),
                  f"{site}" + (f" - view {view.name}: {view.describe()}" if view else ""),
                  f"Traffic report {first} to {last} (local days, {tz}). Verified days only.",
                  *(f"{k}: {v}" for k, v in coverage(period)),
                  "One CSV per table, one row per day; DATA-CONTRACT.md and README.md of "
                  "skald say what each column means. Aggregates only."]
        if credit_text:
            readme.append(f"Countries: {credit_text}")
        z.writestr("README.txt", "\n".join(readme) + "\n")
        for table in export.TABLES:
            try:
                rows, _ = export.rows_from_history(history, key, table, first, last,
                                                   export.Filters(), False, credit_text)
            except export.ExportError:
                continue
            z.writestr(f"{table}.csv", export.as_csv(rows))
    return buf.getvalue()


def weekly_attachment(config: dict, history: History, tz, now: datetime) -> tuple[str, bytes] | None:
    """(file name, html) for the weekly mail when switched on, else None."""
    on = setting(config, "mail", "weekly_report_attachment", False)
    if not (on is True or str(on).lower() in ("true", "yes", "1")):
        return None
    last = now.astimezone(tz).date() - timedelta(days=1)
    first = last - timedelta(days=6)
    html = html_report(config, history, tz, first, last, now=now)
    return f"traffic-report-{first}-to-{last}.html", html.encode("utf-8")


def cmd_report(ctx) -> int:
    from .window import parse_day, yesterday
    a = ctx.args
    last = parse_day(a.last, ctx.tz, ctx.now) if a.last else yesterday(ctx.tz, ctx.now)
    first = parse_day(a.first, ctx.tz, ctx.now) if a.first else last - timedelta(days=6)
    if last < first:
        ctx.err("--to is before --from")
        return 2
    view = None
    if a.view:
        view = next((v for v in ctx.views if a.view.lower() in (v.name.lower(), v.slug)), None)
        if view is None:
            ctx.err(f"no view named {a.view!r}")
            return 2
    try:
        with ctx.history() as history:
            if a.format == "html":
                data = html_report(ctx.config, history, ctx.tz, first, last, view,
                                   ctx.now).encode("utf-8")
            else:
                data = csv_zip(ctx.config, history, ctx.tz, first, last, view)
    except Refused as why:
        ctx.err(f"report REFUSED: {why}")
        return 1
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.name}.tmp")
    tmp.write_bytes(data)
    tmp.replace(out)
    ctx.out(f"wrote {out} ({len(data):,} bytes): {first} to {last}"
            + (f", view {view.name}" if view else ""))
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("report", help="a report to keep or send: one self-contained HTML "
                       "page (print it for a PDF) or a ZIP of CSV tables")
    p.add_argument("--from", dest="first", metavar="DATE", help="default: 7 days before --to")
    p.add_argument("--to", dest="last", metavar="DATE", help="default: yesterday")
    p.add_argument("--view", help="a dashboard.views name")
    p.add_argument("--format", choices=("html", "csv-zip"), default="html")
    p.add_argument("--out", required=True, metavar="PATH")
    p.set_defaults(run=cmd_report)

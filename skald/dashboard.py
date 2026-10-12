"""A private, static dashboard rendered from history.

One self-contained index.html per site: inline CSS, inline SVG, no script,
no font, nothing fetched from anywhere. It is meant to sit behind basic auth
on the same server that wrote the logs, and it carries robots and referrer
metas so that if it is ever exposed it is not indexed and does not leak its
own address to the sites its tables mention.

The honesty rules travel with the page:

  * every figure comes from verified days only; a day that failed verify is
    drawn as "withheld" and a day never collected as "not collected" - never
    as a zero, which would look like a quiet day
  * a change against the previous period is stated only when both periods
    are complete (kpi.change)
  * "people" is visits, an upper bound, never requests

The page is written atomically: a reader refreshing during a run sees the
old page or the new one, never half of one.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape as esc
from math import ceil, floor, log10
from pathlib import Path
from zoneinfo import ZoneInfo

from .classify import Group, ads_checks
from .files import slug, write_atomic
from . import dashboard_breakdowns as bd
from . import dashboard_visits as dv
from . import countries, data_files
from . import live
from .kpi import KPIS, change
from .report import TITLES
from .store import History, Period, view_key

# Categorical slots in fixed order, one per group. Light and dark are the same
# hues stepped for each surface, and the order passes the adjacent colour-
# vision checks in both. Three light steps sit under 3:1 on the surface, so
# every chart has a legend and a table view beside it.
SERIES = {
    Group.PEOPLE: ("#2a78d6", "#3987e5"),
    Group.ANSWER_ENGINE: ("#eb6834", "#d95926"),
    Group.SEARCH_ENGINE: ("#1baf7a", "#199e70"),
    Group.BOTS: ("#eda100", "#c98500"),
    Group.OURS: ("#e87ba4", "#d55181"),
}
VIEWS_LINE = ("#008300", "#008300")
ORDER = [Group.PEOPLE, Group.ANSWER_ENGINE, Group.SEARCH_ENGINE,
         Group.BOTS, Group.OURS]

ROBOTS = '<meta name="robots" content="noindex, nofollow, noarchive">'
REFERRER = '<meta name="referrer" content="no-referrer">'


def _day(d: date) -> str:
    return f"{d:%a} {d.day} {d:%b %Y}"


def _short(d: date) -> str:
    return f"{d.day} {d:%b}"


def _n(v: int) -> str:
    return f"{v:,}"


# ------------------------------------------------------------------ styling

def _tokens(mode: int) -> str:
    surface = ("#fcfcfb", "#1a1a19")[mode]
    page = ("#f3f3f1", "#121211")[mode]
    lines = [
        f"--page:{page}", f"--surface:{surface}",
        "--text-1:" + ("#0b0b0b", "#ffffff")[mode],
        "--text-2:" + ("#52514e", "#c3c2b7")[mode],
        "--text-3:" + ("#6b6a66", "#9d9c94")[mode],
        "--rule:" + ("#e4e3df", "#33332f")[mode],
        "--grid:" + ("#ecebe7", "#2a2a27")[mode],
        "--gap:" + ("#d6d5d0", "#4a4a45")[mode],
        f"--views:{VIEWS_LINE[mode]}",
    ]
    lines += [f"--g-{g.value}:{SERIES[g][mode]}" for g in ORDER]
    return ";".join(lines) + ";"


CSS = f"""
:root{{color-scheme:light;{_tokens(0)}}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{color-scheme:dark;{_tokens(1)}}}}}
:root[data-theme="dark"]{{color-scheme:dark;{_tokens(1)}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--page);color:var(--text-1);
 font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:20px 16px 40px}}
h1{{font-size:22px;margin:0 0 4px;font-weight:650}}
h2{{font-size:17px;margin:32px 0 10px;font-weight:650}}
h3{{font-size:14px;margin:0 0 8px;font-weight:600}}
p{{margin:0 0 10px}}
.meta,.note,caption{{color:var(--text-2);font-size:13px}}
.note{{margin-top:6px}}
.panel{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:14px 16px;margin-bottom:14px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}
.kpi{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:12px 14px}}
.kpi h3{{margin-bottom:2px}}
.kpi .sub{{color:var(--text-3);font-size:12px;margin-bottom:6px}}
.kpi table{{width:100%}}
.kpi td{{padding:3px 0;border:0}}
.kpi .v{{font-weight:650;font-size:16px;text-align:right;font-variant-numeric:tabular-nums}}
.kpi .c{{color:var(--text-2);font-size:12px;text-align:right;white-space:nowrap;padding-left:8px}}
.coverage{{font-size:13px;color:var(--text-2)}}
.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}}
.scroll{{overflow-x:auto}}
table{{border-collapse:collapse;width:100%;font-size:14px}}
caption{{text-align:left;padding-bottom:6px}}
th,td{{text-align:left;padding:6px 8px 6px 0;border-bottom:1px solid var(--rule);vertical-align:top}}
th{{font-weight:600;color:var(--text-2);font-size:12px;text-transform:uppercase;letter-spacing:.03em}}
td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums;padding-right:0;padding-left:8px}}
td.path{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px;word-break:break-all}}
.legend{{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--text-2);margin:2px 0 8px;padding:0;list-style:none}}
.sw{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}}
.sw.line{{height:3px;border-radius:2px;vertical-align:3px;width:14px}}
svg{{display:block;width:100%;height:auto}}
svg text{{fill:var(--text-2);font-size:11px}}
svg .grid{{stroke:var(--grid);stroke-width:1}}
svg .axis{{stroke:var(--rule);stroke-width:1}}
svg .absent{{fill:var(--gap)}}
svg .hit{{fill:transparent}}
svg .hit:hover{{fill:var(--grid);fill-opacity:.6}}
details{{margin-top:8px}}
summary{{cursor:pointer;color:var(--text-2);font-size:13px}}
.howto li{{margin-bottom:6px}}
footer{{color:var(--text-3);font-size:12px;margin-top:28px}}
.live{{border-color:var(--g-people)}}
.refresh{{float:right;margin:0}}
.refresh button{{font:inherit;font-size:13px;font-weight:600;padding:6px 12px;border-radius:8px;border:1px solid var(--rule);background:var(--surface);color:inherit;cursor:pointer}}
.badge{{display:inline-block;font-size:11px;font-weight:650;letter-spacing:.05em;text-transform:uppercase;
 color:var(--text-1);border:1px solid var(--g-people);border-radius:999px;padding:1px 8px;margin-left:8px;vertical-align:3px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:10px 0 14px}}
.tile{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:10px 12px}}
.tile .v{{font-size:22px;font-weight:650;font-variant-numeric:tabular-nums}}
.tile .l{{font-size:13px;color:var(--text-2)}}
.tile .s{{font-size:12px;color:var(--text-3)}}
a{{color:var(--text-1)}}
.dl{{font-size:13px}}
.views{{display:flex;flex-wrap:wrap;gap:6px;list-style:none;padding:0;margin:0 0 14px}}
.views a{{display:inline-block;padding:4px 12px;border:1px solid var(--rule);border-radius:999px;
 background:var(--surface);color:var(--text-2);text-decoration:none;font-size:13px}}
.views a[aria-current="page"]{{color:var(--text-1);border-color:var(--g-people);font-weight:600}}
h3.sub-h{{font-size:15px;margin:22px 0 8px}}
@media (max-width:480px){{main{{padding:14px 12px 32px}}.grid2{{grid-template-columns:1fr}}
 th,td{{padding:5px 6px 5px 0}}table{{font-size:13px}}}}
"""


# ------------------------------------------------------------------- charts

def _scale(top: int) -> tuple[int, int]:
    """A round axis maximum and step, about four gridlines."""
    if top <= 0:
        return 4, 1
    rough = top / 4
    exp = 10 ** floor(log10(rough))
    for m in (1, 2, 2.5, 5, 10):
        step = m * exp
        if step >= rough:
            break
    step = max(1, int(step))
    return step * ceil(top / step), step


W, H = 720, 250
LEFT, RIGHT, TOP, BOTTOM = 52, 12, 14, 30
PLOT_W, PLOT_H = W - LEFT - RIGHT, H - TOP - BOTTOM


def _frame(top: int, days: list[dict]) -> list[str]:
    """Gridlines, y labels and a few date labels."""
    axis_max, step = _scale(top)
    parts = []
    for v in range(0, axis_max + 1, step):
        y = TOP + PLOT_H - v / axis_max * PLOT_H
        parts.append(f'<line class="grid" x1="{LEFT}" x2="{W - RIGHT}" '
                     f'y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text x="{LEFT - 6}" y="{y + 4:.1f}" '
                     f'text-anchor="end">{_n(v)}</text>')
    n = len(days)
    every = 7 if n <= 31 else 14
    slot = PLOT_W / n
    for i, entry in enumerate(days):
        if (n - 1 - i) % every == 0:
            x = LEFT + slot * (i + 0.5)
            parts.append(f'<text x="{x:.1f}" y="{H - 10}" '
                         f'text-anchor="middle">{_short(entry["day"])}</text>')
    parts.append(f'<line class="axis" x1="{LEFT}" x2="{W - RIGHT}" '
                 f'y1="{TOP + PLOT_H}" y2="{TOP + PLOT_H}"/>')
    return parts


def _absent(entry: dict) -> str:
    return ("withheld: the figures did not reconcile"
            if entry["state"] == "withheld" else "not collected")


def _svg(chart_id: str, label: str, desc: str, body: list[str]) -> str:
    return (f'<svg viewBox="0 0 {W} {H}" role="img" '
            f'aria-labelledby="{chart_id}-t {chart_id}-d">'
            f'<title id="{chart_id}-t">{esc(label)}</title>'
            f'<desc id="{chart_id}-d">{esc(desc)}</desc>{"".join(body)}</svg>')


def stacked_chart(chart_id: str, days: list[dict]) -> str:
    """Requests per day, stacked by group. Absent days get a grey stub; a
    partial day is drawn faded and says so."""
    ok = [e for e in days if e["state"] == "ok"]
    drawn = [e for e in days if e["state"] in ("ok", "partial")]
    top = max((sum(e["groups"][g]["hits"] for g in ORDER) for e in drawn), default=0)
    axis_max, _ = _scale(top)
    slot = PLOT_W / len(days)
    width = max(1.0, slot - (2 if slot > 6 else 1))
    body = _frame(top, days)
    for i, entry in enumerate(days):
        x = LEFT + slot * i + (slot - width) / 2
        if entry["state"] == "before":
            continue
        if entry["state"] not in ("ok", "partial"):
            body.append(f'<g><title>{esc(_day(entry["day"]))}: {_absent(entry)}'
                        f'</title><rect class="absent" x="{x:.1f}" '
                        f'y="{TOP + PLOT_H - 4}" width="{width:.1f}" height="4"/></g>')
            continue
        y = TOP + PLOT_H
        rects, words = [], []
        for g in ORDER:
            v = entry["groups"][g]["hits"]
            words.append(f"{TITLES[g].lower()} {_n(v)}")
            if not v:
                continue
            h = v / axis_max * PLOT_H
            y -= h
            rects.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
                         f'height="{h:.1f}" fill="var(--g-{g.value})" '
                         f'stroke="var(--surface)" stroke-width="1"/>')
        total = sum(entry["groups"][g]["hits"] for g in ORDER)
        partial = (f" ({_partial_label(entry)})" if entry["state"] == "partial" else "")
        fade = ' opacity="0.45"' if partial else ""
        body.append(f'<g{fade}><title>{esc(_day(entry["day"]))}{esc(partial)}: '
                    f'{_n(total)} requests - {esc(", ".join(words))}</title>'
                    f'{"".join(rects)}</g>')

    sums = {g: sum(e["groups"][g]["hits"] for e in ok) for g in ORDER}
    desc = (f"Requests per day by group, {days[0]['day']} to {days[-1]['day']}. "
            f"Over the {len(ok)} recorded days: "
            + "; ".join(f"{TITLES[g].lower()} {_n(sums[g])}" for g in ORDER)
            + f". {len(drawn) - len(ok)} partial days drawn faded; "
            f"{len(days) - len(drawn)} days not shown.")
    return _svg(chart_id, f"Requests per day by group, last {len(days)} days",
                desc, body)


def line_chart(chart_id: str, days: list[dict]) -> str:
    """People who read a page, and pages read, per day. Breaks at absent days
    and at days collected before readers were counted."""
    def val(e, which):
        return e["groups"][Group.PEOPLE][which]

    ok = [e for e in days if e["state"] == "ok"]
    top = max((max(val(e, "readers") or 0, val(e, "views")) for e in ok), default=0)
    axis_max, _ = _scale(top)
    slot = PLOT_W / len(days)
    body = _frame(top, days)

    def point(i, v):
        return (LEFT + slot * (i + 0.5), TOP + PLOT_H - v / axis_max * PLOT_H)

    for which, colour in (("views", "var(--views)"), ("readers", "var(--g-people)")):
        run: list[str] = []
        segments: list[list[str]] = []
        for i, e in enumerate(days):
            v = val(e, which) if e["state"] == "ok" else None
            if v is None:
                if run:
                    segments.append(run)
                run = []
                continue
            x, y = point(i, v)
            run.append(f"{x:.1f},{y:.1f}")
        if run:
            segments.append(run)
        for seg in segments:
            if len(seg) == 1:
                x, y = seg[0].split(",")
                body.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{colour}"/>')
            else:
                body.append(f'<polyline points="{" ".join(seg)}" fill="none" '
                            f'stroke="{colour}" stroke-width="2" '
                            f'stroke-linejoin="round" stroke-linecap="round"/>')

    for i, e in enumerate(days):
        x = LEFT + slot * i
        if e["state"] == "before":
            continue
        if e["state"] == "ok":
            readers = val(e, "readers")
            words = (("readers not recorded, " if readers is None else
                      f"{_n(readers)} readers, ") + f"{_n(val(e, 'visits'))} sessions, "
                     f"{_n(val(e, 'views'))} pages read")
        else:
            words = _absent(e)
        body.append(f'<rect class="hit" x="{x:.1f}" y="{TOP}" width="{slot:.1f}" '
                    f'height="{PLOT_H}"><title>{esc(_day(e["day"]))}: {words}'
                    f'</title></rect>')

    visits = sum(val(e, "readers") or 0 for e in ok)
    views = sum(val(e, "views") for e in ok)
    desc = (f"People per day, {days[0]['day']} to {days[-1]['day']}: "
            f"{_n(visits)} readers and {_n(views)} pages read over "
            f"{len(ok)} recorded days. Lines break where a day is not shown.")
    if not ok:
        desc = "No people figures recorded in this period yet."
    return _svg(chart_id, f"People who read a page, and pages read, last {len(days)} days",
                desc, body)


def _readers(n) -> str:
    return "-" if n is None else _n(n)


def legend(items: list[tuple[str, str]], line: bool = False) -> str:
    cls = "sw line" if line else "sw"
    return ('<ul class="legend">' + "".join(
        f'<li><span class="{cls}" style="background:{colour}"></span>'
        f'{esc(name)}</li>' for name, colour in items) + "</ul>")


def daily_table(days: list[dict]) -> str:
    rows = []
    for e in reversed(days):
        if e["state"] == "before":
            continue
        if e["state"] not in ("ok", "partial"):
            rows.append(f"<tr><td>{esc(_day(e['day']))}</td>"
                        f'<td colspan="8">{_absent(e)}</td></tr>')
            continue
        g = e["groups"]
        cells = "".join(f'<td class="n">{_n(g[x]["hits"])}</td>' for x in ORDER)
        label = (f"<br><small>{esc(_partial_label(e))}</small>"
                 if e["state"] == "partial" else "")
        rows.append(f"<tr><td>{esc(_day(e['day']))}{label}</td>"
                    f'<td class="n">{_readers(g[Group.PEOPLE].get("readers"))}</td>'
                    f'<td class="n">{_n(g[Group.PEOPLE]["visits"])}</td>'
                    f'<td class="n">{_n(g[Group.PEOPLE]["views"])}</td>{cells}</tr>')
    head = "".join(f'<th scope="col" class="n">{esc(TITLES[x])}</th>' for x in ORDER)
    return ('<details><summary>Show the daily figures as a table</summary>'
            '<div class="scroll"><table><caption>Requests per group, and people '
            'visits and pages read, per day</caption><thead><tr>'
            '<th scope="col">Day</th><th scope="col" class="n">Readers</th>'
            '<th scope="col" class="n">Browser sessions</th>'
            f'<th scope="col" class="n">Pages read</th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></details>')


# ------------------------------------------------------------------- tables

def _credit(credit: tuple[str, str | None] | None) -> str:
    if not credit:
        return ""
    text, url = credit
    return (f'<a href="{esc(url)}">{esc(text)}</a>' if url else esc(text))


def _download(href: str) -> str:
    return f'<a class="dl" href="{esc(href)}" download>Download CSV</a>' if href else ""


def table(caption: str, head: tuple[str, ...], rows: list[tuple], empty: str,
          path_col: int | None = None, note: str = "", download: str = "") -> str:
    """A real table: caption, scoped headers, numbers right-aligned.

    `note` is HTML shown under the table - the caller's own markup.
    `download` is the relative path of the CSV holding the full list (the
    table shows the top rows; the file has every row history kept)."""
    if not rows:
        return f'<div class="panel"><h3>{esc(caption)}</h3><p class="meta">{esc(empty)}</p></div>'
    numeric = ' class="n"'
    ths = "".join(
        f'<th scope="col"{numeric if i == len(head) - 1 else ""}>{esc(h)}</th>'
        for i, h in enumerate(head))
    body = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i == len(row) - 1:
                cells.append(f'<td class="n">{_n(cell)}</td>')
            elif i == path_col:
                cells.append(f'<td class="path">{esc(str(cell))}</td>')
            else:
                cells.append(f"<td>{esc(str(cell))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<div class="panel scroll"><table><caption><h3>{esc(caption)}</h3>'
            f'</caption><thead><tr>{ths}</tr></thead><tbody>{"".join(body)}'
            f'</tbody></table>'
            + (f'<p class="note">{note}</p>' if note else "")
            + (f'<p class="note">{_download(download)}</p>' if download else "")
            + '</div>')


def _engine_label(name: str) -> str:
    return f"{name} (ads quality checks)" if ads_checks({name: 1}) else name


def _top(counter: Counter, limit: int = 20) -> list[tuple]:
    return [(name, n) for name, n in counter.most_common(limit)]


# --------------------------------------------------------------------- page

def _partial_label(entry: dict) -> str:
    """'partial day, data from 14:05' for a daily() entry."""
    bits = []
    if entry.get("partial_from"):
        bits.append(f"data from {entry['partial_from']:%H:%M}")
    if entry.get("partial_until"):
        bits.append(f"data until {entry['partial_until']:%H:%M}")
    return "partial day, " + ", ".join(bits)


def _coverage(period: Period, start: date | None) -> str:
    words = f"{len(period.recorded)} of {period.length} days recorded"
    if period.partial:
        words += ("; partial, so left out (the logs do not cover the whole day): "
                  + ", ".join(_short(d) for d in period.partial))
    if period.withheld:
        words += ("; withheld (did not reconcile): "
                  + ", ".join(_short(d) for d in period.withheld))
    early = [d for d in period.missing if start is None or d < start]
    gaps = [d for d in period.missing if d not in early]
    if gaps:
        words += "; not collected: " + ", ".join(_short(d) for d in gaps[:10])
        if len(gaps) > 10:
            words += f" and {len(gaps) - 10} more"
    if early:
        words += (f"; history starts {_short(start)}" if start
                  else "; nothing collected yet")
    return words


def kpi_section(history: History, site: str, anchor: date) -> tuple[str, dict]:
    spans = [("Yesterday", 1), ("Last 7 days", 7), ("Last 30 days", 30)]
    periods = {}
    for name, length in spans:
        first = anchor - timedelta(days=length - 1)
        current = history.period(site, first, anchor)
        before = history.period(site, first - timedelta(days=length),
                                first - timedelta(days=1))
        periods[name] = (current, before)

    cards = []
    for k in KPIS:
        rows = []
        for name, _ in spans:
            current, before = periods[name]
            if not current.recorded:
                rows.append(f'<tr><td>{name}</td><td class="v">-</td>'
                            f'<td class="c">no verified data</td></tr>')
                continue
            value = k.value(current.totals)
            previous = (k.value(before.totals)
                        if current.complete and before.complete else None)
            arrow, words = change(value, previous)
            label = f"{arrow} {words}".strip()
            aria = (f"{words} on the previous {name.lower().replace('last ', '')}"
                    if previous is not None else "no comparison")
            shown = "-" if value is None else _n(value)
            rows.append(f'<tr><td>{name}</td><td class="v">{shown}</td>'
                        f'<td class="c" aria-label="{esc(aria)}">{esc(label)}</td></tr>')
        cards.append(f'<div class="kpi"><h3>{esc(k.label)}</h3>'
                     f'<div class="sub">{esc(k.note)}</div>'
                     f'<table><tbody>{"".join(rows)}</tbody></table></div>')

    start = history.first_day(site)

    def span(p: Period) -> str:
        if p.first == p.last:
            return _short(p.first)
        return f"{_short(p.first)} to {_short(p.last)}"

    coverage = "".join(
        f"<li>{name} ({span(periods[name][0])}): "
        f"{_coverage(periods[name][0], start)}</li>"
        for name, _ in spans)
    html = (f'<div class="kpis">{"".join(cards)}</div>'
            f'<p class="note">Change is against the period of the same length '
            f'just before. It is shown only when both periods are fully '
            f'recorded; otherwise "not comparable".</p>'
            f'<ul class="coverage">{coverage}</ul>')
    return html, periods


HOW_TO_READ = """
<ul class="howto">
<li><strong>Every request is in exactly one of five groups</strong>, and the
groups add up to the requests the server answered for this site. A day where
they did not add up is withheld, not shown.</li>
<li><strong>Real people is readers: visits that read at least one page.</strong>
A browser session that only loaded assets, payloads or redirects is counted
as a session, not a reader. A session that fetched robots.txt or a sitemap is
a crawler, whatever browser it claims. Readers are still an upper bound: a
user agent is self-reported.</li>
<li><strong>Visits are not requests.</strong> One visit is one address and
browser within a 30-minute gap, until a page arrives from a new outside source
(an assistant, a search engine, another site, a tagged link). One person reading
one page makes dozens of requests. A visit past midnight counts on both days.</li>
<li><strong>AI citations undercount.</strong> They are counted from the
referrer, which is often stripped. Google AI Overview clicks look exactly like
ordinary Google clicks and are not in this number at all.</li>
<li><strong>Answer engines are split by why they came</strong>: to train or
index (nobody is waiting), or to answer a question someone asked just now.
"Fetched" is not "read".</li>
<li><strong>Scanner probes</strong> are requests for paths no real site
serves, hunting for credentials. They are bots whatever browser they claim to
be.</li>
<li><strong>Top lists over 7 or 30 days</strong> are sums of each day's top
50, so the long tail is undercounted.</li>
<li>Nothing here identifies a visitor. Only totals are kept: no addresses, no
user agents.</li>
</ul>
"""


def _nav(view, all_views) -> str:
    """Links between the All page and each view's page. Plain links."""
    if not all_views:
        return ""
    up = "../" if view else ""
    items = [("All", up or "./", view is None)]
    items += [(v.name, f"{up}{v.slug}/", view is not None and v.slug == view.slug)
              for v in all_views]
    current_mark = ' aria-current="page"'
    links = "".join(
        f'<li><a href="{esc(href)}"{current_mark if current else ""}>{esc(name)}</a></li>'
        for name, href, current in items)
    return f'<nav aria-label="Views"><ul class="views">{links}</ul></nav>'


REFRESH_SECONDS = 120

LIVE_KINDS = {
    "training": "fetched to train or index",
    "asked": "fetched for a live question",
    "citation": "a person followed a citation",
}


def live_panel(snap: dict | None, tz: ZoneInfo, now: datetime,
               credit: tuple[str, str | None] | None = None,
               refresh: bool = False) -> str:
    """The "Today so far" section, from a live snapshot (live.py).

    Shown only for today: a snapshot left over from yesterday is said to be
    stale, never shown as today. Withheld and empty snapshots carry no
    figures, so none are drawn.
    """
    if snap is None:
        return ""
    # "Refresh now" posts to <page>/refresh; nginx hands that to refresh_server.py,
    # which runs `live` and sends the browser back here. A form, so no script.
    button = ('<form class="refresh" method="post" action="refresh">'
              '<button type="submit">Refresh now</button></form>' if refresh else "")
    head = ('<section aria-labelledby="h-live">' + button + '<h2 id="h-live">Today so far'
            '<span class="badge">Live, partial</span></h2>')
    caveat = ("Live and partial: not checked against a full day; not used in "
              "comparisons or emails. The page reloads itself every "
              f"{REFRESH_SECONDS // 60} minutes.")
    today = now.astimezone(tz).date()
    if snap.get("day") != today.isoformat():
        return (head + '<div class="panel live"><p>No live figures for today yet. '
                f'The last live update was for {esc(str(snap.get("day")))}.</p>'
                f'<p class="note">{caveat}</p></div></section>')
    try:
        stamp = datetime.fromisoformat(snap["generated_at"]).astimezone(tz)
        since = datetime.fromisoformat(snap["from"]).astimezone(tz)
        updated = (f"Updated {stamp:%H:%M %Z}, covering {since:%H:%M} to "
                   f"{stamp:%H:%M} today.")
    except (KeyError, ValueError):
        updated = ""
    state = snap.get("state")
    if state == "empty":
        return (head + f'<div class="panel live"><p class="meta">{esc(updated)}</p>'
                '<p>No requests logged yet today.</p>'
                f'<p class="note">{caveat}</p></div></section>')
    if state != "ok":
        problems = "".join(f"<li>{esc(str(p))}</li>" for p in snap.get("problems", []))
        return (head + f'<div class="panel live"><p class="meta">{esc(updated)}</p>'
                "<p><strong>Withheld.</strong> Today's figures so far do not "
                "reconcile, so none are shown.</p>"
                f'<ul class="coverage">{problems}</ul>'
                f'<p class="note">{caveat}</p></div></section>')

    people = snap.get("people", {})
    groups = snap.get("groups", {})
    ai_tiers = snap.get("ai_tiers", {})
    bots = snap.get("bots", {})

    def tile(value: int, label: str, sub: str = "") -> str:
        tail = f'<div class="s">{esc(sub)}</div>' if sub else ""
        return (f'<div class="tile"><div class="v">{_n(int(value))}</div>'
                f'<div class="l">{esc(label)}</div>{tail}</div>')

    tiles = "".join([
        tile(people.get("readers", 0), "Real people: readers",
             f"visits that read a page; {_n(int(people.get('visits', 0)))} "
             f"browser sessions in all"),
        tile(people.get("views", 0), "Pages read by people"),
        tile(people.get("cited_visits", 0), "Visitors from an AI citation",
             "once per visitor; undercounts"),
        tile(ai_tiers.get("training", 0), "AI fetches to train or index"),
        tile(ai_tiers.get("asked", 0), "AI fetches for a live question"),
        tile(groups.get(Group.SEARCH_ENGINE.value, 0) - ads_checks(snap.get("search", {})),
             "Search-engine fetches",
             f"indexing; {_n(ads_checks(snap.get('search', {})))} ads quality checks apart"),
        tile(bots.get("requests", 0), "Bots and scanners",
             f"{_n(int(bots.get('probes', 0)))} scanner probes"),
        tile(snap.get("ours", 0), "Our own traffic", "not traffic; shown so it adds up"),
    ])

    ai = snap.get("ai", {})
    assistants = sorted(
        [(name, "to train or index", n) for name, n in ai.get("training", {}).items()]
        + [(name, "someone just asked", n) for name, n in ai.get("asked", {}).items()],
        key=lambda r: -r[2])
    events = []
    for e in snap.get("events") or []:
        try:
            at = datetime.fromisoformat(e["at"]).astimezone(tz)
        except (KeyError, ValueError):
            continue
        events.append(
            f'<tr><td>{at:%H:%M:%S}</td><td>{esc(LIVE_KINDS.get(e.get("kind"), ""))}</td>'
            f'<td>{esc(str(e.get("who", "")))}</td>'
            f'<td class="path">{esc(str(e.get("path", "")))}</td></tr>')
    activity = (
        '<div class="panel scroll"><table><caption><h3>Latest AI activity today</h3>'
        '</caption><thead><tr><th scope="col">Time</th><th scope="col">What</th>'
        '<th scope="col">Assistant or source</th><th scope="col">Page</th></tr></thead>'
        f'<tbody>{"".join(events)}</tbody></table>'
        '<p class="note">Most recent first. Names are what the assistant calls '
        'itself; a citation shows the site the visitor came from.</p></div>'
        if events else
        '<div class="panel"><h3>Latest AI activity today</h3>'
        '<p class="meta">No assistant fetches or citation clicks yet today.</p></div>')

    def rows(d: dict) -> list[tuple]:
        return [(k, int(v)) for k, v in d.items()]

    tables = [
        table("AI assistants today", ("Assistant", "Why it came", "Fetches"),
              assistants[:20], "No answer engines yet today."),
        table("Visitors from AI citations today", ("Came from", "Visitors"),
              rows(people.get("cited_by", {})), "Nobody has followed a citation yet today."),
        table("Search engines today", ("Crawler", "Fetches"),
              [(_engine_label(k), v) for k, v in rows(snap.get("search", {}))],
              "No search crawlers yet today."),
        table("Pages read by people today", ("Page", "Page views"),
              rows(people.get("pages", {})), "No page views yet today.", 0),
    ]
    extra = ""
    if snap.get("lines_read"):
        extra += (f'<p class="note">Unreadable lines: {_n(int(snap.get("unparsed", 0)))} '
                  f'of {_n(int(snap["lines_read"]))} today so far.</p>')
    if snap.get("unfiltered"):
        extra += (f'<p class="note">{_n(int(snap["unfiltered"]))} of today\'s requests '
                 f'had no host in the log line, so the host list could not be '
                 f'applied to them; they are included.</p>')
    b = snap.get("breakdowns")
    span = f"00:00 to {snap.get('generated_at', '')[11:16]}"
    if b:
        more = (bd.who_section(b.get("by"), int(people.get("readers", 0)), span,
                               str(tz), _credit(credit), today=True)
                + bd.health_section(b.get("statuses"), b.get("not_found", {}),
                                    b.get("server_errors", {}), b.get("speeds", {}),
                                    b.get("slow_pages", {}), b.get("posts", {}),
                                    span, today=True))
    else:
        more = ('<p class="note">Breakdowns appear from the next live update.</p>')
    return (head + f'<div class="panel live"><p class="meta">{esc(updated)} '
            f'{_n(int(snap.get("requests", 0)))} requests so far, in five groups '
            f'that add up exactly.</p>'
            f'<p class="note">{caveat}</p>'
            f'<div class="tiles">{tiles}</div>{extra}'
            f'<p class="note">{_download(EXPORT_DIR + "today.csv")}</p></div>'
            f'{dv.live_section(snap)}{activity}<div class="grid2">{"".join(tables)}'
            f'{dv.ours_box(snap.get("ours_rules"), snap.get("ours_labels"), "today")}'
            f'</div>{more}</section>')


def render(history: History, site: str, tz: ZoneInfo,
           now: datetime | None = None,
           credit: tuple[str, str | None] | None = None,
           snap: dict | None = None, view=None, all_views=(),
           refresh: bool = False) -> str:
    """The dashboard page for one site, as a string.

    `credit` is (text, url) for the source of the country figures, shown
    under the countries table as a plain text link (config.country_credit).
    `snap` is today's live snapshot, if any: it adds the "Today so far" panel
    and a meta refresh, so the page reloads itself without any script.
    `view` (a config.View) renders that view's page from its own history
    rows; `all_views` builds the row of links between the pages.
    """
    key = view_key(site, view.slug) if view else site
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    anchor = now.date() - timedelta(days=1)
    collected = history.last_collected(key)
    if collected:
        stamp = datetime.fromisoformat(collected).astimezone(tz)
        updated = f"Data last collected {_day(stamp.date())} {stamp:%H:%M %Z}"
    else:
        updated = "No data collected yet"
    heading = f"{site} - {view.name}" if view else site
    scope_line = (
        f'<p class="meta">This view counts only requests for {esc(view.describe())}. '
        f'Its five groups add up to its own requests, exactly as the whole '
        f'site\'s do. A visitor who reads pages in two views is a visit in each.'
        f' The live panel below counts this view\'s requests only.</p>' if view else "")

    kpis, periods = kpi_section(history, key, anchor)
    days30 = history.daily(key, anchor - timedelta(days=29), anchor)
    days90 = history.daily(key, anchor - timedelta(days=89), anchor)
    month, _ = periods["Last 30 days"]
    t = month.totals
    people = t.groups.get(Group.PEOPLE)
    engines = t.groups.get(Group.ANSWER_ENGINE)
    search = t.groups.get(Group.SEARCH_ENGINE)
    bots = t.groups.get(Group.BOTS)
    tiers = history.engine_tiers(key, month.first, month.last)
    span = f"last 30 days, {_short(month.first)} to {_short(month.last)}"

    assistants = sorted(
        [(name, "to train or index", n) for name, n in tiers["training"].items()]
        + [(name, "someone just asked", n) for name, n in tiers["asked"].items()],
        key=lambda r: -r[2])
    bot_rows = []
    if bots:
        bot_rows.append(("Scanner probes (credential hunting)", bots.probes))
        bot_rows += _top(bots.agents, 15)

    groups_legend = legend([(TITLES[g], f"var(--g-{g.value})") for g in ORDER])
    tables = [
        table(f"Pages read by people ({span})", ("Page", "Page views"),
              _top(people.pages) if people else [], "No page views recorded.", 0,
              download=EXPORT_DIR + "pages-30d.csv"),
        table(f"Pages AI assistants fetched ({span})", ("Page", "Fetches"),
              _top(engines.pages) if engines else [], "No answer-engine fetches recorded.", 0,
              download=EXPORT_DIR + "ai-pages-30d.csv"),
        table(f"AI assistants by name and tier ({span})",
              ("Assistant", "Why it came", "Fetches"), assistants[:30],
              "No answer engines recorded.", download=EXPORT_DIR + "ai-30d.csv"),
        table(f"Visitors who followed an AI citation, by assistant ({span})",
              ("Came from", "Visitors"),
              _top(people.cited_by) if people else [],
              "Nobody arrived by following a citation.",
              download=EXPORT_DIR + "citations-30d.csv"),
        table(f"Search engines ({span})", ("Crawler", "Fetches"),
              [(_engine_label(n), c) for n, c in _top(search.engines)] if search else [],
              "No search crawlers recorded.",
              note="Ads quality checks are Google's ad systems checking ad landing "
                   "pages. They are in the search group but not in the indexing "
                   "figure above." if search and ads_checks(search.engines) else "",
              download=EXPORT_DIR + "search-30d.csv"),
    ]
    if not t.breakdowns:
        # Before the breakdowns: countries of visits, the only list there was.
        tables.append(table(f"Countries of people's visits ({span})", ("Country", "Visits"),
              [(countries.label(c), v) for c, v in _top(people.countries)] if people else [],
              "No country recorded. The log needs a country field (cc=) for "
              "this; it is never guessed.",
              note=_credit(credit) if people and people.countries else "",
              download=EXPORT_DIR + "countries-30d.csv"))
    tables.append(table(f"Bots and scanners ({span})", ("What", "Requests"), bot_rows,
                        "No bots recorded."))
    before = periods["Last 30 days"][1]
    comparable = (month.complete and before.complete and t.breakdowns
                  and before.totals.breakdowns)
    b = bd.from_totals(t)
    prev = bd.from_totals(before.totals) if comparable else None
    prev_people = before.totals.groups.get(Group.PEOPLE)
    breakdown_html = (
        bd.who_section(b["by"] if b else None, people.readers if people else 0,
                       span, str(tz), _credit(credit),
                       previous=prev["by"] if prev else None,
                       previous_readers=prev_people.readers if prev_people else None,
                       unmeasured=len(month.unmeasured_breakdowns))
        + (bd.health_section(b["statuses"], b["not_found"], b["server_errors"],
                             b["speeds"], b["slow_pages"], b["posts"], span)
           if b else bd.health_section(None, {}, {}, {}, {}, {}, span,
                                       unmeasured=len(month.unmeasured_breakdowns))))
    visits_html = (dv.period_section(t, span, month.unmeasured_visits,
                                     (snap or {}).get("journey_days"))
                   + (dv.ours_box((snap or {}).get("ours_rules"), t.ours_labels, span)
                      if t.ours_labels is not None else ""))
    excluded = ""
    if t.lines_read:
        excluded += (f'<p class="note">Unreadable lines over the {span}: '
                     f'{_n(t.unparsed)} of {_n(t.lines_read)} lines in those days '
                     f'({t.unparsed / t.lines_read:.1%}). Each day was checked '
                     f'against the limit when it was collected.'
                     + (f' Not counted for {len(month.unmeasured_lines)} days '
                        f'collected by an older version.' if month.unmeasured_lines else "")
                     + '</p>')
    if t.unfiltered:
        excluded += (f'<p class="note">{_n(t.unfiltered)} requests over the '
                     f'{span} had no host in the log line (an older log format), '
                     f'so the site\'s host list could not be applied to them. They '
                     f'are included in the figures above.</p>')
    if month.unmeasured:
        excluded += (f'<p class="note">{len(month.unmeasured)} of these days were '
                     f'collected by an older version that did not record how many '
                     f'requests had no host, so that count is missing for them. '
                     f'Re-collecting them with backfill --force fills it in while '
                     f'the logs still hold those days.</p>')
    if t.other_hosts:
        excluded += (f'<p class="note">Also excluded over the {span}: '
                    f'{_n(t.other_hosts)} requests for other hosts on the same '
                    f'server (' + esc(", ".join(f"{h} {_n(n)}" for h, n in
                                                 t.other_host_names.most_common(5)))
                    + "). They are not in any figure above.</p>")

    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"{ROBOTS}{REFERRER}"
        + (f'<meta http-equiv="refresh" content="{REFRESH_SECONDS}">' if snap else "")
        + f"<title>Traffic: {esc(heading)}</title><style>{CSS}</style></head><body><main>"
        f"{_nav(view, all_views)}"
        f"<header><h1>Traffic: {esc(heading)}</h1>{scope_line}"
        f'<p class="meta">{esc(updated)}. Page rendered {_day(now.date())} '
        f'{now:%H:%M %Z}. Days run midnight to midnight, {esc(str(tz))}.</p></header>'
        f'{live_panel(snap, tz, now, credit, refresh)}'
        f'<section aria-labelledby="h-kpi"><h2 id="h-kpi">At a glance</h2>{kpis}</section>'
        f'<section aria-labelledby="h-groups"><h2 id="h-groups">Requests by group</h2>'
        f'<div class="panel">{groups_legend}{stacked_chart("g30", days30)}'
        f'<p class="note">Last 30 days. A grey stub is a day not shown: '
        f'withheld or not collected. Hover a bar for its figures.</p></div>'
        f'<div class="panel">{groups_legend}{stacked_chart("g90", days90)}'
        f'<p class="note">Last 90 days. {_download(EXPORT_DIR + "daily.csv")}</p>'
        f'{daily_table(days90)}</div></section>'
        f'<section aria-labelledby="h-people"><h2 id="h-people">People</h2>'
        f'<div class="panel">'
        + legend([("Readers", "var(--g-people)"), ("Pages read", "var(--views)")],
                 line=True)
        + f'{line_chart("p90", days90)}<p class="note">Last 90 days. Visits are '
        f'an upper bound on people; pages read excludes payloads, assets and '
        f'redirects.</p></div>{visits_html}</section>'
        f'<section aria-labelledby="h-who"><h2 id="h-who">Readers and site health</h2>'
        f'{breakdown_html}</section>'
        f'<section aria-labelledby="h-detail"><h2 id="h-detail">Detail</h2>'
        f'<div class="grid2">{"".join(tables)}</div>{excluded}</section>'
        f'<section aria-labelledby="h-how"><h2 id="h-how">How to read this</h2>'
        f'<div class="panel">{HOW_TO_READ}</div></section>'
        f"<footer>From the server's access logs, so bots are visible - a "
        f"JavaScript tracker cannot see them. Aggregates only: no visitor "
        f"addresses or user agents are stored.</footer>"
        "</main></body></html>\n"
    )


def render_index(sites: list[str], now: datetime) -> str:
    items = "".join(f'<li><a href="{esc(slug(s))}/">{esc(s)}</a></li>' for s in sites)
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"{ROBOTS}{REFERRER}<title>Traffic dashboards</title>"
        f"<style>{CSS}</style></head><body><main><h1>Traffic dashboards</h1>"
        f'<p class="meta">Rendered {now:%Y-%m-%d %H:%M %Z}.</p>'
        f'<div class="panel"><ul>{items or "<li>No sites recorded yet.</li>"}</ul>'
        "</div></main></body></html>\n"
    )


EXPORT_DIR = "exports/"

# The files beside each page, and what each holds. Every one is built by
# export.py from the same history the page is drawn from, so a figure in a
# table and the same figure in its CSV cannot differ.
EXPORTS = {
    "daily.csv": ("daily", 90, False, {}),
    "pages-30d.csv": ("pages", 30, True, {}),
    "ai-pages-30d.csv": ("ai_pages", 30, True, {}),
    "ai-30d.csv": ("engines", 30, True, {"group": "answer_engines"}),
    "search-30d.csv": ("engines", 30, True, {"group": "search_engines"}),
    "citations-30d.csv": ("citations", 30, True, {}),
    "countries-30d.csv": ("countries", 30, True, {}),
}
# Readers by country, browser and the rest; statuses, 404s, 5xx, speed, posts.
EXPORTS.update({name: (t, 30, True, f) for name, (t, f) in bd.PERIOD_FILES.items()})
EXPORTS.update(dv.PERIOD_FILES)      # visit figures, paths, journeys


def write_exports(directory: Path, history: History, key: str, anchor: date,
                  credit: tuple[str, str | None] | None,
                  snap: dict | None = None) -> list[Path]:
    """The CSV files a page links to, in <page>/exports/. Verified days only.

    today.csv exists only while there is a reconciled snapshot for today;
    otherwise it is removed, so an old one is never served as today's.
    """
    from . import export
    credit_text = (credit[0] + (f" ({credit[1]})" if credit[1] else "")) if credit else None
    written = []
    folder = Path(directory) / EXPORT_DIR
    for name, (table_name, days, summed, filters) in EXPORTS.items():
        rows, _ = export.rows_from_history(
            history, key, table_name, anchor - timedelta(days=days - 1), anchor,
            export.Filters(**filters), credit=credit_text)
        if summed:
            rows = export.total(rows, table_name)
        write_atomic(folder / name, export.as_csv(rows))
        written.append(folder / name)
    current = bool(snap and snap.get("state") == "ok" and snap.get("day") == (
        anchor + timedelta(days=1)).isoformat())
    live_files = {"today.csv": ("daily", {})}
    if current and snap.get("breakdowns"):
        live_files.update(bd.TODAY_FILES)
    if current and snap.get("visits"):
        live_files.update(dv.TODAY_FILES)
    for name in ["today.csv", *bd.TODAY_FILES, *dv.TODAY_FILES]:
        path = folder / name
        if current and name in live_files:
            table_name, filters = live_files[name]
            write_atomic(path, export.as_csv(export.rows_from_live(
                snap, table_name, export.Filters(**filters), credit=credit_text)))
            written.append(path)
        elif path.exists():
            path.unlink()
    return written


def write(out: Path, history: History, tz: ZoneInfo,
          now: datetime | None = None,
          credit: tuple[str, str | None] | None = None,
          live_dir: Path | None = None, views=(),
          refresh: bool = False, app: bool = False,
          config: dict | None = None, only: str | None = None,
          index_sites: list[str] | None = None) -> list[Path]:
    """Every site in the history, plus an index linking them. Paths written.

    With `live_dir`, each site's live snapshot found there is shown in its
    "Today so far" panel, and a site with only a snapshot gets a page too.
    With `app`, the site page is the web app (dashboard_webapp) and this
    static page is written beside it as classic.html.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    written = []
    sites = history.sites()
    if live_dir is not None:
        sites = sorted(set(sites) | set(live.sites_in(live_dir)))
    # Several sites (multisite.py): each run draws its own site's pages, with
    # its own config, and the index lists them all.
    listed = sorted(set(sites) | set(index_sites or []))
    if only is not None:
        sites = [only]
    for site in sites:
        page = Path(out) / slug(site) / ("classic.html" if app else "index.html")
        snap = live.load(live.path_for(live_dir, site)) if live_dir is not None else None
        anchor = now.date() - timedelta(days=1)
        write_atomic(page, render(history, site, tz, now, credit, snap,
                                  all_views=views, refresh=refresh))
        written.append(page)
        written += write_exports(page.parent, history, site, anchor, credit, snap)
        # The data files (DATA-CONTRACT.md) beside the page: data_files.py.
        ai = live.load_ai(live.path_for(live_dir, site)) if live_dir is not None else None
        written += data_files.write(page.parent, data_files.Page(
            history, site, site, None, tz, now, snap, config or {}, views, ai, refresh, credit,
            live_dir))
        for view in views:
            page = Path(out) / slug(site) / view.slug / "index.html"
            part = live.view_snapshot(snap, view.slug)
            write_atomic(page, render(history, site, tz, now, credit, part,
                                      view=view, all_views=views, refresh=refresh))
            written.append(page)
            written += write_exports(page.parent, history,
                                     view_key(site, view.slug), anchor, credit, part)
            written += data_files.write(page.parent, data_files.Page(
                history, view_key(site, view.slug), site, view, tz, now, part, config or {},
                views, ai, refresh, credit, live_dir))
        if app:
            from . import dashboard_webapp
            written += dashboard_webapp.write(out, history, site, tz, now, snap,
                                              views, refresh, credit, config)
    root = Path(out) / "index.html"
    write_atomic(root, render_index(listed, now))
    written.append(root)
    return written

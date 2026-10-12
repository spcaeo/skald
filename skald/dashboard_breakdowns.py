"""The dashboard's breakdown sections: who the readers were, and site health.

Kept apart from dashboard.py so neither file grows past what one person can
read. Every function takes plain dictionaries - {label: count} - so the same
tables draw a month from history and today from the live snapshot.

The rules are the dashboard's own:

  * readers are visits that read a page; every breakdown of them adds up to
    the readers exactly (verify._breakdowns), so each table states its
    total and the shares sum to 100%
  * a change is stated only against a previous period that is complete and
    was counted the same way; otherwise "-", never a guess
  * a period with a day collected before the breakdowns existed shows none,
    and says so, rather than a sum of some of its days
"""
from __future__ import annotations

from html import escape as esc

from . import countries
from .aggregate import READER_DIMS
from .classify import Group
from .dimensions import HOURS, OTHER, SLOW, SPEEDS, STATUSES
from .kpi import change
from .report import TITLES

EXPORT_DIR = "exports/"

# dimension: (title, column heading, what it means)
WHO = {
    "country": ("Countries", "Country",
                "where each reader was, from the log's country field; Unknown "
                "when it had none - never guessed"),
    "device": ("Devices", "Device", "from the user agent; bots are never in it"),
    "browser": ("Browsers", "Browser",
                "self-reported; Brave counts as Chrome, an in-app browser by its app"),
    "os": ("Operating systems", "System",
           "an iPad asking for the desktop site counts as macOS"),
    "source": ("Traffic sources", "Source",
               "from the referrer of the first page read; often stripped, so "
               "Direct includes those"),
    "referrer": ("Referring sites", "Site", "the first page's referrer, host only"),
    "campaign": ("Campaigns", "source / medium / campaign",
                 "utm_ tags or an ad click id on the landing URL"),
    "landing": ("Landing pages", "Page", "the first page each reader read"),
    "hour": ("Hour of day", "Hour", "when each reader's first page was read"),
}

# File names beside each page. dashboard.EXPORTS builds them from history,
# dashboard.TODAY_EXPORTS from the live snapshot.
PERIOD_FILES = {f"readers-{d}-30d.csv": ("readers", {"dimension": d}) for d in READER_DIMS}
PERIOD_FILES.update({
    "statuses-30d.csv": ("statuses", {}),
    "not-found-30d.csv": ("not_found", {}),
    "server-errors-30d.csv": ("server_errors", {}),
    "posts-30d.csv": ("posts", {}),
    "speed-30d.csv": ("speed", {}),
    "slow-pages-30d.csv": ("slow_pages", {}),
})
TODAY_FILES = {f"today-{name.replace('-30d', '')}": spec
               for name, spec in PERIOD_FILES.items()}


def _n(v) -> str:
    return "-" if v is None else f"{int(v):,}"


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else "-"


def _label(dimension: str, name: str, tz_name: str) -> str:
    if dimension == "country":
        return countries.label(name)
    if dimension == "hour" and name in HOURS:
        h = int(name)
        return f"{h:02d}:00-{(h + 1) % 24:02d}:00"
    return name


def _download(name: str) -> str:
    return (f'<p class="note"><a class="dl" href="{esc(EXPORT_DIR + name)}" '
            f'download>Download CSV</a></p>') if name else ""


def _table(caption: str, head: tuple[str, ...], rows: list[tuple], note: str = "",
           download: str = "", numeric_from: int = 1, path: bool = False,
           empty: str = "None recorded.") -> str:
    """A captioned table whose columns from `numeric_from` are figures."""
    if not rows:
        return (f'<div class="panel"><h3>{esc(caption)}</h3>'
                f'<p class="meta">{esc(empty)}</p>{_download(download)}</div>')
    num = ' class="n"'
    ths = "".join(
        f'<th scope="col"{num if i >= numeric_from else ""}>{esc(h)}</th>'
        for i, h in enumerate(head))
    body = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i >= numeric_from:
                cells.append(f'<td class="n">{esc(str(cell))}</td>')
            elif path and i == 0:
                cells.append(f'<td class="path">{esc(str(cell))}</td>')
            else:
                cells.append(f"<td>{esc(str(cell))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<div class="panel scroll"><table><caption><h3>{esc(caption)}</h3>'
            f'</caption><thead><tr>{ths}</tr></thead><tbody>{"".join(body)}'
            f'</tbody></table>'
            + (f'<p class="note">{note}</p>' if note else "")
            + _download(download) + '</div>')


def _ordered(dimension: str, counts: dict) -> list[tuple[str, int]]:
    """Largest first; hours in clock order; the folded tail last."""
    items = [(k, int(v)) for k, v in counts.items() if int(v)]
    if dimension == "hour":
        return sorted(items, key=lambda kv: kv[0])
    items.sort(key=lambda kv: (kv[0] == OTHER, -kv[1], kv[0]))
    return items


def hour_chart(counts: dict, tz_name: str, chart_id: str = "hours") -> str:
    """Readers by hour of day: 24 bars, inline SVG, labelled every 3 hours."""
    values = [int(counts.get(h, 0)) for h in HOURS]
    top = max(values) or 1
    # Narrow on purpose: on a phone the labels stay near their real size.
    w, h, left, bottom = 360, 120, 4, 18
    slot = (w - 2 * left) / 24
    parts = []
    for i, v in enumerate(values):
        bar = (h - bottom - 8) * v / top
        x = left + slot * i + 1
        y = h - bottom - bar
        parts.append(f'<g><title>{i:02d}:00-{(i + 1) % 24:02d}:00: {v:,} readers</title>'
                     f'<rect x="{x:.1f}" y="{y:.1f}" width="{slot - 2:.1f}" '
                     f'height="{max(bar, 0):.1f}" fill="var(--g-people)"/>'
                     f'<rect class="hit" x="{x:.1f}" y="0" width="{slot - 4:.1f}" '
                     f'height="{h - bottom}"/></g>')
        if i % 6 == 0:
            parts.append(f'<text x="{x + (slot - 4) / 2:.1f}" y="{h - 4}" '
                         f'text-anchor="middle">{i:02d}</text>')
    parts.append(f'<line class="axis" x1="{left}" x2="{w - left}" '
                 f'y1="{h - bottom}" y2="{h - bottom}"/>')
    busiest = max(range(24), key=lambda i: values[i])
    desc = (f"Readers by hour of day, {tz_name} time. Busiest hour "
            f"{busiest:02d}:00 with {values[busiest]:,} readers.")
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="{chart_id}-t '
            f'{chart_id}-d"><title id="{chart_id}-t">Readers by hour of day</title>'
            f'<desc id="{chart_id}-d">{esc(desc)}</desc>{"".join(parts)}</svg>')


def who_section(by: dict | None, readers: int | None, span: str, tz_name: str,
                credit_html: str = "", previous: dict | None = None,
                previous_readers: int | None = None, today: bool = False,
                unmeasured: int = 0) -> str:
    """Who the readers were: one table per dimension, each adding to `readers`.

    `previous` is the same breakdown for the period just before, given only
    when that period is complete and was counted the same way; each row then
    states its change. `today` names the live CSVs instead of the 30-day ones.
    """
    title = "Who the readers were" + (" today" if today else "")
    head = f'<h3 class="sub-h">{esc(title)} ({esc(span)})</h3>'
    if by is None:
        why = (f"{unmeasured} of these days were collected before the breakdowns "
               f"existed, so none are shown for the period: a sum of some of its "
               f"days would not add up to its readers. backfill --force fills "
               f"them in while the logs still hold those days."
               if unmeasured else "No whole day recorded in this period yet. Partial "
               "days are left out here, as everywhere on this page; the live panel "
               "above has today so far.")
        return f'<div class="panel">{head}<p class="meta">{esc(why)}</p></div>'
    if not readers:
        return (f'<div class="panel">{head}<p class="meta">No readers in this '
                f'period, so there is nothing to break down.</p></div>')
    files = TODAY_FILES if today else PERIOD_FILES
    blocks = []
    for dimension in ("country", "device", "browser", "os", "source", "referrer",
                      "campaign", "landing", "hour"):
        caption, column, meaning = WHO[dimension]
        counts = by.get(dimension) or {}
        before = (previous or {}).get(dimension) if previous is not None else None
        rows = []
        for name, n in _ordered(dimension, counts):
            row = [_label(dimension, name, tz_name), f"{n:,}", _pct(n, readers)]
            if before is not None:
                arrow, words = change(n, int(before.get(name, 0)))
                row.append(f"{arrow} {words}".strip())
            rows.append(tuple(row))
        cols = (column, "Readers", "Share") + (("Change",) if before is not None else ())
        note = esc(meaning[:1].upper() + meaning[1:]) + f". Adds up to {readers:,} readers."
        if dimension == "country" and credit_html:
            note += " " + credit_html
        if dimension == "hour":
            note = esc(f"{tz_name} time. ") + note
        limit = 24 if dimension == "hour" else 15
        shown = rows if dimension == "hour" else rows[:limit]
        if len(rows) > len(shown):
            note += f" Top {limit} of {len(rows)} shown; the CSV has every row."
        table = _table(f"{caption} ({span})", cols, shown, note,
                       files and _file(files, "readers", dimension),
                       path=dimension == "landing")
        if dimension == "hour":
            table = table.replace('<div class="panel scroll">',
                                  '<div class="panel scroll">'
                                  + hour_chart(counts, tz_name,
                                               "hours-today" if today else "hours"), 1)
        blocks.append(table)
    if previous is None and not today:
        compare = ("No change column: the period before is not fully recorded "
                   "with these breakdowns yet.")
    elif today:
        compare = "Live and partial: no change is stated for today."
    else:
        compare = "Change is against the 30 days just before."
    return (f'{head}<p class="note">{esc(compare)} Readers are visits that read '
            f'at least one page; each table adds up to them exactly.</p>'
            f'<div class="grid2">{"".join(blocks)}</div>')


def _file(files: dict, table: str, dimension: str | None = None) -> str:
    for name, (t, filters) in files.items():
        if t == table and filters.get("dimension") == dimension:
            return name
    return ""


def health_section(statuses: dict | None, not_found: dict, server_errors: dict,
                   speeds: dict, slow_pages: dict, posts: dict, span: str,
                   today: bool = False, unmeasured: int = 0) -> str:
    """Status classes per group, the 404s people met, 5xx, speed and posts.

    `statuses` is {group value: {class: n}}; `posts` {group value: {"total":
    n, "pages": {path: n}}}. None when the period was not counted this way.
    """
    title = "Site health" + (" today" if today else "")
    head = f'<h3 class="sub-h">{esc(title)} ({esc(span)})</h3>'
    if statuses is None:
        why = (f"{unmeasured} of these days were collected before these figures "
               f"existed, so none are shown for the period." if unmeasured
               else "No whole day recorded in this period yet.")
        return f'<div class="panel">{head}<p class="meta">{esc(why)}</p></div>'
    files = TODAY_FILES if today else PERIOD_FILES
    order = [Group.PEOPLE, Group.ANSWER_ENGINE, Group.SEARCH_ENGINE, Group.BOTS,
             Group.OURS]
    rows = []
    for g in order:
        got = statuses.get(g.value) or {}
        total = sum(int(v) for v in got.values())
        if not total:
            continue
        rows.append((TITLES[g], *[f"{int(got.get(s, 0)):,}" for s in STATUSES],
                     f"{total:,}"))
    blocks = [_table(f"Responses by status ({span})",
                     ("Group", *STATUSES, "Requests"), rows,
                     "Each row adds up to that group's requests. 404 is page not "
                     "found; 4xx the other client errors; 5xx server errors.",
                     _file(files, "statuses"))]

    people_404 = int((statuses.get(Group.PEOPLE.value) or {}).get("404", 0))
    blocks.append(_table(
        f"Pages not found, seen by real people ({span})", ("Path", "Requests"),
        [(p, f"{int(n):,}") for p, n in _ordered("", not_found)][:20],
        f"{people_404:,} requests from real people got a 404. Includes assets "
        f"(an image or script that is missing), not only pages.",
        _file(files, "not_found"), path=True,
        empty="No real person was served a 404."))

    errors = sum(int((statuses.get(g.value) or {}).get("5xx", 0)) for g in order)
    blocks.append(_table(
        f"Server errors, 5xx ({span})", ("Path", "Requests"),
        [(p, f"{int(n):,}") for p, n in _ordered("", server_errors)][:20],
        f"{errors:,} server errors, to anyone. The status table above says "
        f"which group got them.", _file(files, "server_errors"), path=True,
        empty="No server errors."))

    views = sum(int(v) for v in speeds.values())
    logged = views - int(speeds.get("not logged", 0))
    speed_rows = [(b, f"{int(speeds.get(b, 0)):,}", _pct(int(speeds.get(b, 0)), views))
                  for b in SPEEDS if int(speeds.get(b, 0))]
    slow = sum(int(speeds.get(b, 0)) for b in SLOW)
    blocks.append(_table(
        f"How fast people's pages were served ({span})",
        ("Server time", "Page views", "Share"), speed_rows,
        (f"Time the server took to answer (nginx request time), not the time "
         f"to draw the page in the browser. {slow:,} page views took 1 s or more."
         if logged else "The log has no response time for these page views."),
        _file(files, "speed"), empty="No page views by people."))
    if slow_pages:
        blocks.append(_table(
            f"Slow pages: 1 s or more ({span})", ("Page", "Page views"),
            [(p, f"{int(n):,}") for p, n in _ordered("", slow_pages)][:15],
            "Page views by real people that took the server 1 s or more.",
            _file(files, "slow_pages"), path=True))

    post_rows = []
    for g in order:
        got = posts.get(g.value) or {}
        for path, n in _ordered("", got.get("pages") or {})[:10]:
            post_rows.append((path, TITLES[g], f"{int(n):,}"))
    totals = ", ".join(f"{TITLES[g].lower()} {int((posts.get(g.value) or {}).get('total', 0)):,}"
                       for g in order if (posts.get(g.value) or {}).get("total"))
    blocks.append(_table(
        f"Form posts and other POST requests ({span})", ("Path", "From", "Requests"),
        post_rows,
        "Counted only: what was sent is never logged or stored. "
        + (f"By group: {totals}." if totals else ""),
        _file(files, "posts"), numeric_from=2, path=True, empty="No POST requests."))
    return f'{head}<div class="grid2">{"".join(blocks)}</div>'


def from_totals(totals) -> dict | None:
    """The breakdowns of a Totals as plain dictionaries, or None when it
    was not counted with them (live.breakdowns has the same shape)."""
    if not totals.breakdowns:
        return None
    from .live import breakdowns
    return breakdowns(totals)

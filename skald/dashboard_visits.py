"""The dashboard's visits sections, and the "Our own traffic" box.

Kept apart from dashboard.py so neither file grows past what one person can
read. Three pieces:

  * live_section - "Visits today": metrics, the newest 50 anonymous
    journeys, one per row and readable as a sentence, and today's top
    entry pages, exit pages and steps
  * period_section - the same metrics and top lists for the last 30 days
    from history, with links to the CSVs (journeys of the last
    report.journey_days days among them)
  * ours_box - what counts as our own traffic, by the LABEL of each rule
    and how many requests each matched. The address behind an address
    rule is never on the page: it lives only in the server's config.

A journey shows when the visit started (to the minute), the country, the
device, browser and system, where it came from, and the pages in order.
No address, no user agent, no visitor key is in it - visits.py never
writes them.
"""
from __future__ import annotations

from html import escape as esc

from .dashboard_breakdowns import _table
from .dimensions import OTHER
from .visits import (ARROW, FLAG_WORDS, VisitStats, came_from, duration_words,
                     pages_words, visitor)

EXPORT_DIR = "exports/"
SHOWN = 50          # journeys in the "Visits today" table

# Files beside each page: {name: (export table, days, total over them, filters)}
# from history, and {name: (table, filters)} from the live snapshot.
PERIOD_FILES = {
    "visits-30d.csv": ("visits", 30, False, {}),
    "visit-paths-30d.csv": ("visit_paths", 30, True, {}),
    "journeys.csv": ("journeys", 30, False, {}),
}
TODAY_FILES = {
    "today-journeys.csv": ("journeys", {}),
    "today-visit-paths.csv": ("visit_paths", {}),
}

def _download(name: str, words: str = "Download CSV") -> str:
    return f'<a class="dl" href="{esc(EXPORT_DIR + name)}" download>{esc(words)}</a>'


def _trail_html(j: dict) -> str:
    parts = []
    for path, how in j.get("trail") or []:
        if how == "app":
            parts.append(f'<em title="seen from the next request\'s referrer; '
                         f'the app showed it without loading a page">{esc(path)} '
                         f'(in-app)</em>')
        else:
            parts.append(esc(path))
    more = int(j.get("seen", 0)) - len(j.get("trail") or [])
    tail = f" … and {more} more" if more > 0 else ""
    flags = []
    if j.get("not_found"):
        flags.append("met a 404")
    if j.get("posted"):
        flags.append("sent a form")
    note = (f'<br><small>{esc(", ".join(flags))}</small>') if flags else ""
    return f'<span class="path">{esc(ARROW).join(parts)}{esc(tail)}</span>{note}'


def journeys_table(journeys: list[dict], total: int, download: str) -> str:
    """The newest SHOWN journeys, one per row: time, visitor and source,
    the pages, how many and how long."""
    if not journeys:
        return ('<div class="panel"><h3>Visits today</h3><p class="meta">No visits '
                'that read a page yet today.</p></div>')
    rows = []
    for j in journeys[:SHOWN]:
        rows.append(
            f'<tr><td>{esc(str(j.get("start", ""))[11:16])}</td>'
            f'<td>{esc(visitor(j))}<br><small>{esc(came_from(j))}</small></td>'
            f'<td class="path">{_trail_html(j)}</td>'
            f'<td class="n">{esc(pages_words(j))}</td>'
            f'<td class="n">{esc(duration_words(j.get("seconds")))}</td></tr>')
    shown = min(len(journeys), SHOWN)
    note = (f"Newest first; {shown:,} of {total:,} visits today shown. "
            if total > shown else "Newest first. ")
    note += ("One row per visit, anonymous: no address or browser string is kept. "
             "Pages in italics were shown by the site's app without loading a page, "
             "seen from the referrer of the visitor's next request: the Pages column "
             "states them as seen in the browser, apart from the pages loaded. "
             "Length is first request to last.")
    return ('<div class="panel scroll"><table><caption><h3>Visits today</h3></caption>'
            '<thead><tr><th scope="col">Time</th><th scope="col">Visitor and source</th>'
            '<th scope="col">Pages, in order</th><th scope="col" class="n">Pages</th>'
            '<th scope="col" class="n">Length</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table><p class="note">{esc(note)}</p>'
            f'<p class="note">{_download(download)}</p></div>')


def _tiles(stats: VisitStats) -> str:
    def tile(value: str, label: str, sub: str = "") -> str:
        tail = f'<div class="s">{esc(sub)}</div>' if sub else ""
        return (f'<div class="tile"><div class="v">{esc(value)}</div>'
                f'<div class="l">{esc(label)}</div>{tail}</div>')

    per = stats.per_visit()
    one = stats.one_page()
    share = f"{one / stats.visits:.0%}" if stats.visits else "-"
    return '<div class="tiles">' + "".join([
        tile(f"{stats.visits:,}", "Visits", "visits that read a page; equal to readers"),
        tile("-" if per is None else f"{per:.1f}", "Pages per visit",
             f"{stats.views():,} pages loaded"),
        tile(duration_words(stats.median_seconds()), "Median visit length",
             "first request to last"),
        tile(share, "One-page visits", f"{one:,} visits; an upper bound, see in-app"),
        tile(f"{stats.flags.get('in_app', 0):,}", "Moved in-app",
             "went on to pages without loading them"),
    ]) + "</div>"


def _top_tables(stats: VisitStats, span: str, download: str = "") -> str:
    def rows(counter, limit=10):
        named = [(k, n) for k, n in counter.most_common() if k != OTHER][:limit]
        return [(k, f"{n:,}", f"{n / stats.visits:.0%}" if stats.visits else "-")
                for k, n in named]

    return '<div class="grid2">' + "".join([
        _table(f"Entry pages ({span})", ("Page", "Visits", "Share"), rows(stats.entries),
               "The first page each visit loaded.", download, path=True,
               empty="No visits."),
        _table(f"Exit pages ({span})", ("Page", "Visits", "Share"), rows(stats.exits),
               "The last page each visit was seen on, in-app pages included.",
               path=True, empty="No visits."),
        _table(f"Top 2-step paths ({span})", ("From → to", "Times", "Share of visits"),
               rows(stats.steps),
               "Each move from one page to the next, in-app moves included. "
               f"{sum(stats.steps.values()):,} moves in all.", path=True,
               empty="No visit went past its first page."),
    ]) + "</div>"


def flag_note(stats: VisitStats) -> str:
    parts = [f"{stats.flags.get(f, 0):,} {FLAG_WORDS[f]}" for f in ("not_found", "posted")]
    return (f'<p class="note">Of these visits: {esc("; ".join(parts))}. Visits by '
            f'country, device and source are the readers tables below - a visit '
            f'that read a page is a reader.</p>')


def live_section(snap: dict) -> str:
    """"Visits today" for the live panel, from a reconciled snapshot."""
    stats = VisitStats.from_dict(snap.get("visits"))
    if stats is None:
        return '<p class="note">Visits appear from the next live update.</p>'
    span = f"today, 00:00 to {str(snap.get('generated_at', ''))[11:16]}"
    return ('<h3 class="sub-h">Visits today</h3>' + _tiles(stats)
            + journeys_table(snap.get("journeys") or [],
                             int(snap.get("journeys_total", stats.visits)),
                             "today-journeys.csv")
            + _top_tables(stats, span, "today-visit-paths.csv") + flag_note(stats))


def period_section(totals, span: str, unmeasured: int, keep_days: int | None = None) -> str:
    """Visits over the period, from history (store_visits)."""
    head = f'<h3 class="sub-h">Visits ({esc(span)})</h3>'
    stats = totals.visits
    if stats is None:
        why = (f"{unmeasured} of these days were collected before visits were counted, "
               f"so none are shown for the period. backfill --force fills them in "
               f"while the logs still hold those days." if unmeasured else
               "No whole day recorded in this period yet. The live panel above has "
               "today's visits.")
        return f'<div class="panel">{head}<p class="meta">{esc(why)}</p></div>'
    if not stats.visits:
        return f'<div class="panel">{head}<p class="meta">No visits in this period.</p></div>'
    days = f"the last {keep_days} days" if keep_days else "the last days kept"
    links = (f'<p class="note">{_download("visits-30d.csv", "Visit figures per day (CSV)")}'
             f' · {_download("visit-paths-30d.csv", "Entry, exit and step lists (CSV)")}'
             f' · {_download("journeys.csv", "Every anonymous journey kept (CSV)")}</p>'
             f'<p class="note">Journeys, one row per visit, are kept for {esc(days)} '
             f'only and then deleted; the figures above are kept for good.</p>')
    return head + _tiles(stats) + _top_tables(stats, span) + flag_note(stats) + links


def ours_box(rules: list[dict] | None, counts: dict | None, when: str) -> str:
    """What counts as our own traffic, by label, and the requests each rule
    matched `when` (e.g. "today"). Labels only: never an address."""
    counts = dict(counts or {})
    rows, seen = [], set()
    for rule in rules or []:
        label = str(rule.get("label", ""))
        if label in seen:
            continue
        seen.add(label)
        kind = str(rule.get("kind", "")) + (" (paused)" if rule.get("paused") else "")
        rows.append((label, kind, f"{int(counts.get(label, 0)):,}"))
    for label, n in sorted(counts.items(), key=lambda kv: -int(kv[1])):
        if label not in seen:
            rows.append((label, "no longer configured", f"{int(n):,}"))
    if not rows:
        return ""
    return _table(f"Our own traffic ({when})", ("What counts as ours", "Matched by",
                                                "Requests"), rows,
                  "Our own browsing, crawler, tests and health checks: not visitors, "
                  "kept apart so the five groups still add up. Each rule is shown by "
                  "its label; an address is never shown here. It is set in the "
                  "server's config under ours.addresses.", numeric_from=2)

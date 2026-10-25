"""Where visitors came from, across sites: the table under the site picker
(/traffic/, site_picker.py). One row per site the viewer may see, for today,
7, 30 or 90 days: visitors from Search, Social (and the top networks: X,
LinkedIn, Facebook, Instagram, Reddit, YouTube), AI and Direct. Each figure
links to that site's Traffic > Sources, with the network open.

No new figure here: it reads each site's stored, audited figures from the
files the dashboard writes beside the site's page, the same its own Sources
tab reads, and sums them the way the page does (data.js `total`):

  data/app.json        each day's state and readers by source type
                       (days[].by.source); today: the live count's
                       (live.figures.by.source), only while it is "ok"
  data/campaigns.json  each day's social_networks (social_networks.py);
                       today: today.social_networks

Only verified ("ok") days are summed; a withheld or missing day is counted
and named, never added as 0. A figure no verified day of the range recorded
reads "Not recorded" (a social network before 2.34, a source type before
breakdowns). A network figure whose day does not add up (its networks
against its Social media visits, or against the Sources row) is "Withheld".
Visitors are each site's own: one person who visited two sites is on both.

Which sites: the caller's (helper_sessions.listing passes only the sites of
the viewer's organisations; the static picker every site of the install).
A site the viewer may not open is never read, so nothing of it shows.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from html import escape as esc
from pathlib import Path

from .files import slug
from .social_names import NAMES

RANGES = (("today", "Today"), ("7d", "7 days"), ("30d", "30 days"), ("90d", "90 days"))
NETWORKS = ("x", "linkedin", "facebook", "instagram", "reddit", "youtube")
SOURCES = (("search", "Search", "Search engine"), ("social", "Social", "Social media"),
           ("ai", "AI", "AI assistant"), ("direct", "Direct", "Direct or unknown"))
SOCIAL = "Social media"
NOT_RECORDED = "Not recorded"
WITHHELD = "Withheld"

_CACHE: dict[str, tuple] = {}


def _read(path: Path, pick):
    """`pick(json)` of a file, worked out once per version of the file."""
    try:
        st = path.stat()
    except OSError:
        return None
    stamp = (st.st_mtime_ns, st.st_size)
    got = _CACHE.get(str(path))
    if got and got[0] == stamp:
        return got[1]
    try:
        body = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    value = pick(body) if isinstance(body, dict) else None
    if len(_CACHE) > 200:
        _CACHE.clear()
    _CACHE[str(path)] = (stamp, value)
    return value


def _app(body: dict) -> dict:
    days = {}
    for d in body.get("days") or []:
        if isinstance(d, dict) and d.get("day"):
            by = d.get("by")
            days[d["day"]] = {"state": d.get("state"),
                              "source": (by or {}).get("source") if isinstance(by, dict) else None}
    live = body.get("live") or {}
    fig = live.get("figures") or {}
    return {"anchor": body.get("anchor"), "today": body.get("today"), "days": days,
            "live": {"day": live.get("day"), "state": live.get("state"),
                     "source": (fig.get("by") or {}).get("source") if fig.get("by") else None}}


def _camp(body: dict) -> dict:
    days = {d["day"]: {"state": d.get("state"), "blob": d.get("social_networks")}
            for d in body.get("days") or [] if isinstance(d, dict) and d.get("day")}
    today = body.get("today") or {}
    return {"days": days, "today": {"state": today.get("state"),
                                    "blob": today.get("social_networks")}}


def _adds_up(blob: dict, source: dict | None) -> bool:
    nets = blob.get("networks") or {}
    try:
        social = int(blob.get("social", 0))
        if sum(int(v) for v in nets.values()) != social:
            return False
        return source is None or int(source.get(SOCIAL, 0)) == social
    except (TypeError, ValueError):
        return False


def figures(out: Path, site: str, rng: str) -> dict:
    """One site's row for a range: {"days", "verified", "withheld", "missing",
    "sources": {id: n or None}, "networks": {id: n or None or WITHHELD},
    "social_days"}. None in a figure: not recorded."""
    data = Path(out) / slug(site) / "data"
    app = _read(data / "app.json", _app)
    camp = _read(data / "campaigns.json", _camp) or {"days": {}, "today": {}}
    row = {"days": 0, "verified": 0, "withheld": 0, "missing": 0, "social_days": 0,
           "sources": {k: None for k, _, _ in SOURCES}, "networks": {k: None for k in NETWORKS}}
    if not app:
        return row
    entries = []      # (state, readers by source or None, social blob or None)
    if rng == "today":
        row["days"] = 1
        live = app["live"]
        if live.get("day") == app.get("today") and live.get("state") == "ok":
            got = camp.get("today") or {}
            entries.append(("ok", live.get("source"),
                            got.get("blob") if got.get("state") == "ok" else None))
        else:
            row["missing"] = 1
    else:
        try:
            anchor = date.fromisoformat(app.get("anchor") or "")
        except ValueError:
            return row
        n = int(rng.rstrip("d"))
        row["days"] = n
        for i in range(n):
            day = (anchor - timedelta(days=i)).isoformat()
            e = app["days"].get(day)
            if e is None:
                row["missing"] += 1
                continue
            c = camp["days"].get(day) or {}
            entries.append((e.get("state"), e.get("source"),
                            c.get("blob") if c.get("state") == "ok" else None))
    nets: dict = {k: 0 for k in NETWORKS}
    held = False
    sums: dict = {}
    for state, source, blob in entries:
        if state != "ok":
            if state == "withheld":
                row["withheld"] += 1
            else:
                row["missing"] += 1
            continue
        row["verified"] += 1
        if source is not None:
            for key, _, name in SOURCES:
                sums[key] = sums.get(key, 0) + int(source.get(name, 0) or 0)
        if blob is not None:
            row["social_days"] += 1
            if not _adds_up(blob, source):
                held = True
                continue
            for k in NETWORKS:
                nets[k] += int((blob.get("networks") or {}).get(k, 0) or 0)
    for key, _, _ in SOURCES:
        row["sources"][key] = sums.get(key)
    if held:
        row["networks"] = {k: WITHHELD for k in NETWORKS}
    elif row["social_days"]:
        row["networks"] = nets
    return row


# ------------------------------------------------------------------- page

CSS = """
.ax{display:flex;flex-direction:column;gap:12px}
.ax h2{margin:0;font-size:20px;font-weight:700;letter-spacing:-.01em}
.ax-lede{margin:0;color:var(--ink-2);font-size:14px}
.ax-r{display:none;flex-direction:column;gap:10px}
.ax-r:target,#sources-today{display:flex}.ax-r:target~#sources-today{display:none}
.ax-pick{display:flex;flex-wrap:wrap;gap:6px;margin:0;padding:0;list-style:none}
.ax-pick a{display:inline-block;min-height:32px;padding:5px 12px;border:1px solid var(--rule);
border-radius:16px;font-size:13.5px;text-decoration:none;color:var(--ink-2);background:var(--surface)}
.ax-pick a[aria-current]{background:var(--ink);color:var(--surface);border-color:var(--ink)}
.ax-wrap{overflow-x:auto;border:1px solid var(--rule);border-radius:12px;background:var(--surface)}
.ax table{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}
.ax th,.ax td{padding:8px 10px;border-bottom:1px solid var(--grid);text-align:right;white-space:nowrap}
.ax th:first-child,.ax td:first-child{text-align:left;position:sticky;left:0;background:var(--surface)}
.ax thead th{font-size:12.5px;color:var(--ink-3);font-weight:600}
.ax th.ax-g{border-left:1px solid var(--grid)}
.ax tbody tr:last-child td{border-bottom:0}
.ax td a{color:inherit;text-decoration:none;border-bottom:1px dotted var(--gap)}
.ax td a:hover{border-bottom-color:var(--ink)}
.ax th small,.ax-none{display:block;color:var(--ink-3);font-size:12px;font-weight:400}
.ax tbody th{font-weight:600}
.ax-none{display:inline}
"""


def _sources_href(path: str, rng: str, seg: str = "", net: str = "") -> str:
    q = [] if rng == "today" else [f"range={rng}"]
    if seg:
        q.append(f"src_seg={seg}")
    if net:
        q.append(f"net={net}")
    return f"{path}#traffic/sources" + (f"?{'&'.join(q)}" if q else "")


def _cell(value, href: str, why: str) -> str:
    if value is None:
        return f'<td><span class="ax-none" title="{esc(why)}">{NOT_RECORDED}</span></td>'
    if value == WITHHELD:
        return (f'<td><span class="ax-none" title="These days\' figures do not add up">'
                f'{WITHHELD}</span></td>')
    return f'<td><a href="{esc(href)}">{int(value):,}</a></td>'


def _covered(row: dict) -> str:
    if not row["days"]:
        return "no figures written yet"
    bits = [f"{row['verified']} of {row['days']} day{'s' if row['days'] != 1 else ''} verified"
            if row["days"] > 1 else ("verified" if row["verified"] else "not counted yet")]
    if row["withheld"]:
        bits.append(f"{row['withheld']} withheld")
    if row["verified"] and row["social_days"] and row["social_days"] < row["verified"]:
        bits.append(f"networks over {row['social_days']}")
    return ", ".join(bits)


def _table(out, sites: list[dict], rng: str) -> str:
    cols = []
    for key, words, _ in SOURCES:
        group = ' class="ax-g"' if key == "social" else ""
        cols.append(f'<th scope="col"{group}>{esc(words)}</th>')
        if key == "social":
            cols += [f'<th scope="col">{esc(NAMES[n])}</th>' for n in NETWORKS]
    head = '<tr><th scope="col">Site</th>' + "".join(cols) + "</tr>"
    body = []
    for s in sites:
        name = s["name"]
        path = s.get("path") or f"{slug(name)}/"
        row = figures(out, name, rng)
        why = ("waiting for its first log lines" if s.get("waiting")
               else "no verified day in this range recorded it")
        cells = []
        for key, _, _ in SOURCES:
            seg = "social" if key == "social" else ""
            cells.append(_cell(row["sources"][key], _sources_href(path, rng, seg), why))
            if key == "social":
                nwhy = ("social networks were not counted yet on these days" if row["verified"]
                        and not row["social_days"] else why)
                cells += [_cell(row["networks"][n], _sources_href(path, rng, "social", n), nwhy)
                          for n in NETWORKS]
        body.append(f'<tr><th scope="row"><a href="{esc(path)}">{esc(name)}</a>'
                    f'<small>{esc(_covered(row))}</small></th>{"".join(cells)}</tr>')
    return (f'<div class="ax-wrap"><table><caption class="vh">Visitors by source, '
            f'{esc(dict(RANGES)[rng].lower())}</caption><thead>{head}</thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def section(out, sites: list[dict]) -> str:
    """The table, one panel per range; the address's #sources-<range> picks
    the one shown (Today when it names none), so a link keeps the range and
    Back and Forward move between them. "" when there is no site or no
    folder to read."""
    sites = [s for s in sites if isinstance(s, dict) and s.get("name")]
    if not sites or out is None:
        return ""
    panels = []
    # Today last: an earlier panel picked by the address hides it (CSS ~).
    for rng, words in [r for r in RANGES if r[0] != "today"] + [RANGES[0]]:
        on = ' aria-current="true"'
        pick = "".join(f'<li><a href="#sources-{k}"{on if k == rng else ""}>{esc(w)}</a></li>'
                       for k, w in RANGES)
        panels.append(f'<section class="ax-r" id="sources-{rng}" aria-label="{esc(words)}">'
                      f'<ul class="ax-pick" aria-label="Period">{pick}</ul>'
                      f"{_table(out, sites, rng)}</section>")
    return ('<section class="ax" aria-labelledby="ax-h"><h2 id="ax-h">Where visitors came '
            'from, all your sites</h2><p class="ax-lede">Visitors by source type and by social '
            "network, from each site's own verified figures. Open a figure for that site's "
            "Sources, with the network open. Today is the live count so far; other periods "
            "end yesterday and add verified days only. One person who visited two sites "
            f"counts on both.</p>{''.join(panels)}</section>")

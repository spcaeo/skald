"""The site picker (/traffic/, after sign-in) and the parts of sites.json the
site switcher reads: each site's logo and today so far (2.6.0).

A card per site: its logo (site_logos.py; the first letter on the site's
colour while there is none), its name, a line about it, "Live" while the
two-minute count is current, and today's visitors, leads and demos booked.

Today's figures are read, never counted here: visitors are live.json's
`people.readers` (the Overview's Visitors tile for Today, checked by the live
count), leads and demos booked are today's `days[]` entry of
conversions.json, summed the way the dashboard sums them (leadfigs.js
dayLeads: the finished stages of `lead_actions` and of `demo_actions`), and
only when that day is "ok", which the second count (audit_conversions.py)
has matched. Anything else - no live count for today, a withheld or
missing day, no conversions file - is null in sites.json and "-" on the
card, never 0.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from html import escape as esc
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import brand, site_logos
from .across_sites import CSS as ACROSS_CSS, section as across_section
from .files import slug

LIVE_MINUTES = 15            # a count older than this is not called live
FINISHED = ("completed", "paid")
LEADS = ("contact", "signup", "waitlist", "trial", "demo")
DEMOS = ("demo",)


def _json(path: Path):
    try:
        got = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) else None


def day_leads(conv: dict | None, day: str | None) -> tuple[int | None, int | None]:
    """(leads, demos booked) on `day` from conversions.json, or (None, None)
    when the file, the day or its check is missing."""
    if not day or not conv or not conv.get("available") or not isinstance(conv.get("days"), list):
        return None, None
    entry = next((d for d in conv["days"] if isinstance(d, dict) and d.get("day") == day), None)
    if not entry or entry.get("state") != "ok":
        return None, None
    finished = set(conv.get("finished") or FINISHED)
    leads, demos = set(conv.get("lead_actions") or LEADS), set(conv.get("demo_actions") or DEMOS)
    n_leads = n_demos = 0
    for action, per in (entry.get("stages") or {}).items():
        for stage, n in (per or {}).items():
            if stage not in finished or not isinstance(n, int):
                continue
            n_leads += n if action in leads else 0
            n_demos += n if action in demos else 0
    return n_leads, n_demos


def today(out: Path | None, site: str, now: datetime | None = None) -> dict:
    """sites.json's `today` for one site: {"day", "visitors", "leads",
    "demos", "live", "timezone"}; a figure that is not known is null."""
    got = {"day": None, "visitors": None, "leads": None, "demos": None, "live": False,
           "timezone": None}
    if out is None:
        return got
    data = Path(out) / slug(site) / "data"
    snap = _json(data / "live.json")
    if not snap:
        return got
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    zone = snap.get("timezone")
    try:
        local = now.astimezone(ZoneInfo(zone)).date().isoformat() if zone else None
    except (ZoneInfoNotFoundError, ValueError):
        local = None
    day = snap.get("day")
    if not day or (local and day != local) or snap.get("stale"):
        return {**got, "timezone": zone}
    got.update(day=day, timezone=zone)
    if snap.get("state") == "ok":
        readers = (snap.get("people") or {}).get("readers")
        got["visitors"] = readers if isinstance(readers, int) else None
        try:
            made = datetime.fromisoformat(snap.get("generated_at") or "")
            got["live"] = now - made.astimezone(timezone.utc) <= timedelta(minutes=LIVE_MINUTES)
        except (TypeError, ValueError):
            got["live"] = False
    got["leads"], got["demos"] = day_leads(_json(data / "conversions.json"), day)
    return got


def _configs(config: dict, config_path) -> dict:
    """{site name: its merged config}, read once (multisite.py)."""
    from .config import site_name
    found = {site_name(config or {}): config or {}}
    if config_path is None:
        return found
    from . import multisite
    try:
        for c in multisite.site_configs(config or {}, Path(config_path)):
            found.setdefault(site_name(c), c)
    except (SystemExit, Exception):     # noqa: BLE001 - a broken file: the install's config
        pass
    return found


def enrich(sites: list[dict], out, config: dict, base, config_path=None,
           now: datetime | None = None) -> list[dict]:
    """The sites.json entries with each one's `logo` and `today` as they are
    now (the helper answers sites.json and the picker with these)."""
    configs = _configs(config, config_path)
    done = []
    for s in sites:
        if not isinstance(s, dict) or not s.get("name"):
            continue
        name = s["name"]
        cfg = configs.get(name, config or {})
        # A site still showing its letter is asked again, on a thread, at most
        # once a day (2.25); this answer shows what is there now.
        site_logos.retry_missing(cfg, name, base, out)
        done.append({**s, "logo": site_logos.entry(cfg, name, base),
                     "today": today(out, name, now)})
    return done


# ------------------------------------------------------------------- page

MARK = ('<svg width="28" height="28" viewBox="0 0 64 64" aria-hidden="true">'
        '<rect width="64" height="64" rx="15" fill="var(--ink)"/>'
        '<path d="M20 14.5 27 11v41l-7 3.5z" fill="var(--page)"/>'
        '<g fill="var(--page)" stroke="var(--ink)" stroke-width="3" stroke-linejoin="round" '
        'paint-order="stroke"><path d="M25 41C28 29 38 17 51 10c-2 9-6 16-11 21l-3.5-.5 1.5 3'
        'c-3 3.5-7 7-10.5 9.5z"/><path d="M24.6 39.2l3.6 3.2L11.5 56.5z"/></g></svg>')

CSS = """
:root{color-scheme:light;--page:#edf0f3;--surface:#fbfcfd;--sunk:#e4e9ee;--ink:#17212b;
--ink-2:#4f5d6b;--ink-3:#5a6672;--rule:#d8dfe6;--grid:#e6ebf0;--gap:#c3ccd5;--good:#1b7f52;
--shadow:0 1px 0 rgba(23,33,43,.04),0 8px 24px -12px rgba(23,33,43,.18);
--sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--page:#0d1319;--surface:#141c24;
--sunk:#1b252f;--ink:#e4eaf0;--ink-2:#a9b5c1;--ink-3:#8593a0;--rule:#26313c;--grid:#1e2832;
--gap:#3a4652;--good:#48b883;--shadow:0 1px 0 rgba(0,0,0,.3),0 10px 30px -14px rgba(0,0,0,.7)}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);
font:14px/1.5 var(--sans)}a{color:inherit}
:focus-visible{outline:2px solid var(--ink);outline-offset:2px;border-radius:8px}
.pk-top{display:flex;align-items:center;justify-content:space-between;gap:16px;
padding:14px 32px;border-bottom:1px solid var(--rule);background:var(--surface);flex-wrap:wrap}
.pk-brand{display:flex;align-items:center;gap:10px;font-weight:720;font-size:18px;
letter-spacing:-.01em}.pk-brand svg{display:block}
.pk-me{display:flex;align-items:center;gap:8px;min-height:40px;padding:0 14px 0 7px;
border:1px solid var(--rule);border-radius:22px;color:var(--ink-2);font-size:14px;
max-width:100%;overflow:hidden}
.pk-me b{width:26px;height:26px;flex:none;border-radius:13px;background:var(--ink);
color:var(--surface);display:grid;place-items:center;font-size:12px}
.pk-me span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
main{max-width:1040px;margin:0 auto;padding:44px 32px 56px;display:flex;flex-direction:column;
gap:26px}
h1{margin:0;font-size:30px;font-weight:720;letter-spacing:-.02em;line-height:1.15}
.pk-lede{margin:6px 0 0;color:var(--ink-2);font-size:15.5px}
.pk-org h2{margin:0;font-size:19px;font-weight:680;letter-spacing:-.01em}
.pk-org h2 small{margin-left:6px;color:var(--ink-2);font-size:14px;font-weight:500}
.pk-org .pk-grid{margin-top:12px}
.pk-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px;
list-style:none;margin:0;padding:0}
.pk-card{display:flex;flex-direction:column;gap:18px;height:100%;padding:22px;
text-decoration:none;background:var(--surface);border:1px solid var(--rule);border-radius:12px;
box-shadow:var(--shadow);transition:border-color .15s,transform .15s}
.pk-card:hover{border-color:var(--gap);transform:translateY(-1px)}
.pk-head{display:flex;align-items:center;gap:14px;min-width:0}
.pk-logo{position:relative;width:48px;height:48px;flex:none;border-radius:12px;display:grid;
place-items:center;color:#fff;font-weight:720;font-size:21px;overflow:hidden}
.pk-logo img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;
background:var(--surface)}
.pk-name{display:flex;flex-direction:column;gap:2px;min-width:0}
.pk-name b{font-size:19px;font-weight:680;overflow:hidden;text-overflow:ellipsis;
white-space:nowrap}
.pk-name small{font-size:13px;color:var(--ink-3)}
.pk-live{margin-left:auto;display:flex;align-items:center;gap:6px;font-size:13px;
font-weight:600;color:var(--good);flex:none}
.pk-live i{width:8px;height:8px;border-radius:4px;background:var(--good)}
.pk-figs{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) auto;gap:12px;margin:0;
border-top:1px solid var(--grid);padding-top:16px}
.pk-figs div{display:flex;flex-direction:column-reverse;gap:2px;margin:0}
.pk-figs dd{margin:0;font-size:24px;font-weight:700;font-variant-numeric:tabular-nums;
line-height:1.2}
.pk-figs dt{font-size:13px;color:var(--ink-3);white-space:nowrap}
.pk-add{display:flex;align-items:center;justify-content:center;gap:12px;min-height:160px;
height:100%;padding:22px;border:1.5px dashed var(--gap);border-radius:12px;color:var(--ink-2);
font-size:16px;font-weight:600;text-decoration:none}
.pk-add:hover{color:var(--ink);border-color:var(--ink-3)}
.pk-note{margin:0;font-size:13px;color:var(--ink-3)}
.pk-build{margin:8px 0 0;font-size:12px;color:var(--ink-3)}
.pk-setup{display:flex;align-items:center;justify-content:space-between;gap:8px;
margin-top:8px;padding:10px 14px;border-radius:8px;background:#1d64c2;color:#fff;
font-size:14px;font-weight:650;text-decoration:none;box-shadow:0 1px 0 rgba(0,0,0,.08),
0 6px 16px -8px rgba(29,100,194,.7)}.pk-setup:after{content:"\\2192";font-size:16px}
.pk-setup:hover{background:#1857a8}.pk-setup:focus-visible{outline:2px solid var(--ink);
outline-offset:2px}
.pk-grid>li{display:flex;flex-direction:column}.pk-grid>li>.pk-card{height:auto;flex:1}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);
white-space:nowrap}
.pk-empty{padding:22px;border:1px solid var(--rule);border-radius:12px;background:var(--surface)}
@media (max-width:600px){.pk-top{padding:12px 16px}main{padding:28px 16px 40px;gap:20px}
h1{font-size:26px}.pk-grid{grid-template-columns:minmax(0,1fr);gap:14px}.pk-card{padding:18px}}
"""


def _place(zone: str | None) -> str | None:
    if not zone or "/" not in zone:
        return None
    return zone.rsplit("/", 1)[1].replace("_", " ")


def _figure(n, one: str, many: str, why: str) -> str:
    if n is None:
        return (f'<div><dt>{esc(many)}</dt><dd title="{esc(why)}">-'
                f'<span class="vh"> ({esc(why)})</span></dd></div>')
    return f"<div><dt>{esc(one if n == 1 else many)}</dt><dd>{n:,}</dd></div>"


def logo_tile(logo: dict | None, name: str, prefix: str = "") -> str:
    """The logo over its letter tile: if the image cannot load, the letter shows."""
    logo = logo or {}
    color = logo.get("color") if logo.get("color") in site_logos.COLORS else \
        site_logos.default_color(name)
    letter = logo.get("letter") or site_logos.letter(name)
    img = (f'<img src="{esc(prefix + logo["url"])}" alt="" width="48" height="48" '
           f'decoding="async">' if logo.get("url") else "")
    return (f'<span class="pk-logo" style="background:{color}" role="img" '
            f'aria-label="{esc(name)} logo">{esc(letter)}{img}</span>')


def sub_line(site: dict) -> str:
    if site.get("waiting"):
        return "waiting for its first log lines"
    views = site.get("views") or []
    return f"{len(views)} view{'s' if len(views) != 1 else ''}" if views else "all pages"


def card(site: dict) -> str:
    name = site["name"]
    t = site.get("today") or {}
    why = "not recorded for today yet"
    live = ('<span class="pk-live"><i aria-hidden="true"></i>Live</span>'
            if t.get("live") else "")
    return (f'<li><a class="pk-card" href="{esc(site.get("path") or slug(name) + "/")}">'
            f'<span class="pk-head">{logo_tile(site.get("logo"), name)}'
            f'<span class="pk-name"><b>{esc(name)}</b><small>{esc(sub_line(site))}</small></span>'
            f'{live}</span><dl class="pk-figs" aria-label="{esc(name)}, today so far">'
            + _figure(t.get("visitors"), "visitor", "visitors", why)
            + _figure(t.get("leads"), "lead", "leads", why)
            + _figure(t.get("demos"), "demo booked", "demos booked", why)
            + "</dl></a>" + badge(site) + "</li>")


def badge(site: dict) -> str:
    """The wizard's link under a card: "Setup: step 3 of 5, continue", or
    "No visits yet: test the connection" (helper_sessions.py fills it)."""
    got = site.get("badge") or {}
    if not got.get("href") or not got.get("words"):
        return ""
    return f'<a class="pk-setup" href="{esc(got["href"])}">{esc(got["words"])}</a>'


def lede(sites: list[dict]) -> str:
    zones = {(s.get("today") or {}).get("timezone") for s in sites} - {None}
    place = _place(next(iter(zones))) if len(zones) == 1 else None
    when = (f"Today so far, {place} time." if place else
            "Today so far, in each site's own time zone." if zones else "Today so far.")
    return f"Each site shows its own logo, taken from the site itself. {when}"


def _groups(sites: list[dict], orgs: dict[str, str]) -> list[tuple[str, list[dict]]]:
    """[(organisation, its sites)] in the order the sites come, for a reader
    in two or more organisations (`orgs`: {site: organisation}); a site with
    no organisation named goes last, under "Other sites"."""
    out: dict[str, list[dict]] = {}
    for s in sites:
        out.setdefault(orgs.get(s["name"]) or "", []).append(s)
    return sorted(out.items(), key=lambda kv: kv[0] == "")


def render(sites: list[dict], now: datetime, who: str | None = None,
           add_href: str | None = None, title: str = "Choose a site", across: str = "",
           orgs: dict[str, str] | None = None) -> str:
    """The picker page. `sites`: sites.json entries with `logo` and `today`
    (enrich); `who`: the signed-in email; `add_href`: where "Add a site"
    goes (an admin's Settings > Sites), or None for no card;
    `across`: the sources table under the cards (across_sites.section);
    `orgs`: {site: organisation} for a reader in two or more (2.38.0): the
    cards are grouped under each organisation's name."""
    named = [s for s in sites if isinstance(s, dict) and s.get("name")]
    cards = "".join(card(s) for s in named)
    add = (f'<li><a class="pk-add" href="{esc(add_href)}"><svg width="22" height="22" '
           'viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" '
           'stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
           'Add a site</a></li>' if add_href else "")
    if orgs and named:
        grid = "".join(
            f'<section class="pk-org"><h2>{esc(name or "Other sites")} <small>'
            f'{len(group)} site{"" if len(group) == 1 else "s"}</small></h2>'
            f'<ul class="pk-grid">{"".join(card(s) for s in group)}</ul></section>'
            for name, group in _groups(named, orgs))
        grid += f'<ul class="pk-grid">{add}</ul>' if add else ""
    else:
        grid = (f'<ul class="pk-grid">{cards}{add}</ul>' if cards or add
                else '<p class="pk-empty">No sites recorded yet.</p>')
    me = (f'<span class="pk-me"><b aria-hidden="true">{esc(who[:1].upper())}</b>'
          f'<span>{esc(who)}</span></span>' if who else "")
    zones = {(s.get("today") or {}).get("timezone") for s in sites if isinstance(s, dict)} - {None}
    text, tip = brand.release_line(next(iter(zones)) if len(zones) == 1 else None)
    foot = f'<p class="pk-build" title="{esc(tip)}">{esc(text)}</p>' if text else ""
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow, noarchive">'
        '<meta name="referrer" content="no-referrer"><meta name="color-scheme" content="light dark">'
        f"<title>{esc(title)} · Skald</title><style>{CSS}{ACROSS_CSS}</style></head><body>"
        f'<header class="pk-top"><span class="pk-brand">{MARK}Skald</span>{me}</header>'
        f'<main><div><h1>{esc(title)}</h1><p class="pk-lede">{esc(lede(sites))}</p></div>'
        f"{grid}{across}"
        '<p class="pk-note">No logo found on a site? Skald shows its first letter on the '
        "site's colour instead. Logos are fetched from each site itself, never from an outside "
        f'icon service. Updated {now:%H:%M %Z}.</p>{foot}</main></body></html>\n')


def static_page(names: list[str], now: datetime, out: Path | None) -> str:
    """The picker the dashboard writes as <dashboard.out>/index.html, for an
    install without the helper in front: every site, today's figures from
    the files beside it, letters for logos (the image needs the helper)."""
    known = {}
    try:
        listed = json.loads((Path(out) / "sites.json").read_text()).get("sites") or []
        known = {s["name"]: s for s in listed if isinstance(s, dict) and s.get("name")}
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        pass
    sites = []
    for name in names:
        s = dict(known.get(name) or {})
        s.setdefault("name", name)
        s.setdefault("path", f"{slug(name)}/")
        s["logo"] = {"url": None, "letter": site_logos.letter(name),
                     "color": (s.get("logo") or {}).get("color") or site_logos.default_color(name)}
        s["today"] = today(out, name, now)
        sites.append(s)
    return render(sites, now, across=across_section(out, sites))

"""Several sites in one install.

The main config is the first site. `sites:` in it lists more, each a
config file (relative to the main one) whose sections are laid over the
main config's - so a second site names its own `site`, `logs`, `dashboard.views`,
`leads`, mail recipients and so on, and inherits the rest (history file,
dashboard folder, time zone, mail server):

    sites:
      - sites/shop.example.yml

All sites share one history file (rows are filed by site name) and one
dashboard folder (a folder per site, an index of sites, and sites.json for
the switcher). Each other site keeps its own live snapshot and state files
in `<history folder>/sites/<site>/`, so its alerts, markers and private
lists never mix with the first site's.

Sites made from the dashboard (Settings > Sites, accounts/site_configs.py)
are rows in accounts.sqlite, not files. They are loaded after the files, laid
over the install's config the same way, but without the parts that belong
to the first site's owner: no mail recipients (daily and weekly mail and alert
mail off until the site's own admin sets them in Settings), no leads, page
speed, hooks, conversions or markers, and no beacon origins or goals. A
config-file site of the same name wins and the row is skipped. A removed
row is not loaded: its processing stops, its data stays. Until a dashboard
site's first log line, run-daily and live report it as "waiting for its first
log lines" (waiting()) and go on: exit 0, nothing stored, no failure mail.

`skald live`, `run-daily`, `dashboard`, `check`, `collect`, `backfill`, `doctor`,
`audit`, `verify-bots`, `pagespeed` and the search syncs (`search-console`, `bing`,
`search`) run for every site in turn (each
one's exit status counted; the worst is returned); `--site NAME` picks one.
Every other command works on the first site unless `--site` names another.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config, site_name, views as config_views
from .files import slug, write_atomic

PER_SITE = ("live", "run-daily", "dashboard", "check", "collect", "backfill", "audit",
            "verify-bots", "pagespeed", "doctor", "search-console", "bing", "search", "reports",
            "ai-answers")


def merged(base: dict, over: dict) -> dict:
    """`over`'s sections laid over `base`'s, key by key; `sites` dropped."""
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (base or {}).items()
           if k != "sites"}
    for section, values in (over or {}).items():
        if section == "sites":
            continue
        if isinstance(values, dict) and isinstance(out.get(section), dict):
            out[section] = {**out[section], **values}
        else:
            out[section] = values
    # A site's own pages are its own: views and refresh settings come from its
    # file or not at all, never from the first site's paths.
    if "views" not in ((over or {}).get("dashboard") or {}):
        out.setdefault("dashboard", {})
        out["dashboard"] = {k: v for k, v in out["dashboard"].items() if k != "views"}
    return out


def site_configs(config: dict, config_path: Path) -> list[dict]:
    """The other sites' merged configs, in the order listed. Raises
    SystemExit for a missing file or a name used twice."""
    raw = (config or {}).get("sites") or []
    if isinstance(raw, str):
        raw = [raw]
    found, names = [], {site_name(config)}
    for entry in raw:
        path = Path(str(entry))
        if not path.is_absolute():
            path = Path(config_path).resolve().parent / path
        if not path.exists():
            raise SystemExit(f"sites: {path} not found")
        got = merged(config, load_config(path))
        name = site_name(got)
        if name in names:
            raise SystemExit(f"sites: two sites are both named {name!r}")
        names.add(name)
        found.append(got)
    return found + dashboard_site_configs(config, config_path, names)


# Sections a dashboard site never takes from the install's config: they name the
# first site's own people, pages and tools.
NOT_INHERITED = ("leads", "pagespeed", "hooks", "conversions", "markers")


def tenant_base(config: dict) -> dict:
    """The install's config as a base for a dashboard site.

    Nothing of the first site's `site:` section is taken: its asset
    prefixes, rendering rule and legacy paths describe that site's pages.
    Inherited, a static first site's `asset_prefixes` (/style.css ...) made
    every Next.js dashboard site wait for those files instead of
    /_next/static/, and a returning reader with them cached was no person."""
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (config or {}).items()
           if k not in NOT_INHERITED}
    out["site"] = {}
    mail = dict(out.get("mail") or {})
    mail.update({"to": [], "daily": False, "weekly": False})
    out["mail"] = mail
    out["alerts"] = {**(out.get("alerts") or {}), "mail": False}
    if isinstance(out.get("beacon"), dict):
        out["beacon"] = {k: v for k, v in out["beacon"].items() if k not in ("origins", "goals")}
    return out


def history_folder(config: dict, config_path: Path) -> Path:
    raw = Path(str((config.get("history") or {}).get("db") or "history.sqlite")).expanduser()
    if not raw.is_absolute():
        raw = Path(config_path).resolve().parent / raw
    return raw.parent


def dashboard_site_configs(config: dict, config_path: Path, taken: set[str]) -> list[dict]:
    """The active sites made from the dashboard (accounts.sqlite), merged over
    `tenant_base(config)`. Nothing when there is no accounts file."""
    from .accounts import db as base, site_configs
    from .ingest_log import site_folder, root as ingest_root
    folder = history_folder(config, config_path)
    path = base.path_for(config, folder)
    if path is None or not Path(path).is_file():
        return []
    db = base.connect(path)
    try:
        rows = site_configs.active(db)
    finally:
        db.close()
    found, start = [], tenant_base(config)
    for entry in rows:
        if entry["name"] in taken:
            print(f"sites: {entry['name']} is a config-file site; the dashboard's row "
                  "is skipped", file=sys.stderr)
            continue
        default_dir = site_folder(ingest_root(config, folder), entry["name"])
        found.append(merged(start, site_configs.as_config(entry, default_dir)))
        taken = taken | {entry["name"]}
    return found


WAITING = "waiting for its first log lines"


def waiting(config: dict, db_path, lines_read: int = 0) -> bool:
    """True for a site made from the dashboard that has no day stored yet
    and, for the window looked at, not one line (readable or not).

    Such a site has simply not shipped anything yet: run-daily and live say
    so and go on, instead of failing the whole install. A config-file site,
    a site with a day stored, or one whose lines do not parse is not waiting:
    an empty or unreadable day there is a real failure, as before."""
    if not (config or {}).get("_dashboard_site") or lines_read:
        return False
    if not Path(db_path).is_file():
        return True
    from .store import History
    history = History.reader(db_path)
    try:
        return history.first_day(site_name(config)) is None
    except Exception:                   # noqa: BLE001 - a new file without tables
        return True
    finally:
        history.db.close()


def state_dir(base: Path, site: str) -> Path:
    """Where another site's live snapshot and state files live."""
    path = Path(base) / "sites" / slug(site)
    path.mkdir(parents=True, exist_ok=True)
    return path


def describe(configs: list[dict], history) -> list[dict]:
    """sites.json's list: every site, with its views, the days stored and
    its logo (site_logos.py; the files beside the history)."""
    from . import site_logos
    base = Path(history.path).parent if getattr(history, "path", None) else None
    out = []
    for config in configs:
        name = site_name(config)
        try:
            views = config_views(config)
        except ValueError:
            views = []
        first = history.first_day(name)
        last = history.db.execute("SELECT MAX(day) FROM days WHERE site = ?",
                                  (name,)).fetchone()[0]
        out.append({"name": name, "slug": slug(name), "path": f"{slug(name)}/",
                    "views": [{"slug": v.slug, "name": v.name} for v in views],
                    "first_day": first.isoformat() if first else None, "last_day": last,
                    # A dashboard site with no day stored yet (waiting()).
                    "waiting": bool(config.get("_dashboard_site")) and first is None,
                    "logo": site_logos.entry(config, name, base)})
    return out


def write_sites(out: Path, sites: list[dict], live_names: set[str]) -> list[Path]:
    """sites.json at the dashboard's root and in each site's data folder,
    each site with today so far from the files beside it (site_picker.py)."""
    from .site_picker import today
    written = []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    listed = [{**s, "live": s["name"] in live_names, "today": today(out, s["name"])}
              for s in sites]
    for current in [None] + [s["name"] for s in sites]:
        body = {"schema_version": 1, "generated_at": now, "sites": listed, "current": current}
        path = (Path(out) / "sites.json" if current is None
                else Path(out) / slug(current) / "data" / "sites.json")
        if current is not None and not path.parent.exists():
            continue
        write_atomic(path, json.dumps(body, separators=(",", ":")) + "\n")
        written.append(path)
    return written


def run_each(contexts: list) -> list[int]:
    """Run the command for every site, one after another. A site that crashes is
    reported (its run is already recorded as failed in its runs.json) and counts as
    2, but the sites after it still run: one site's failure must not cost the
    others their day (2026-10-22: one site failed at 07:16 and the two sites after it
    were never collected)."""
    import traceback
    codes = []
    for c in contexts:
        try:
            codes.append(c.args.run(c))
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:               # noqa: BLE001 - the next site still runs
            sys.stderr.write(f"{c.site}: {c.args.command} crashed; the other sites go on\n")
            traceback.print_exc()
            codes.append(2)
    return codes

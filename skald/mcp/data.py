"""The data files the MCP tools read, and the rules for reading them.

The tools never count anything: they read the same JSON files the dashboard
reads (DATA-CONTRACT.md), from `<dashboard.out>/<site>/[<view>/]data/`, and
sum whole, verified days the way the web app does (webapp/js/data.js): a
range is the sum of its `ok` days only; `partial`, `withheld` and `missing`
days are left out and named by date, never counted as a quiet day. A figure
that was not recorded on a counted day makes the whole sum null, never 0.

`Context` is what one MCP request may read: the output folder, and a
`checker(site) -> (allowed, why, private)` that says whether the caller may
read a site at all and whether it may read the two files that hold
addresses (`requests`, `ai_activity`).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

SITE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,99}$")
VIEW = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PRIVATE = ("requests", "ai_activity")        # the files that hold addresses (tokens.PRIVATE)
MAX_RANGE = 180                               # the data files hold 180 days
DEFAULT_DAYS = 7
OTHERS = "(all others)"
HONEST = ("Visits (an upper bound on people) are browsers that read at least one page. "
          "A browser's name can be faked, so this is at most the number of people, "
          "never a count of them.")


class Refused(Exception):
    """A plain-words answer the tool gives back as an error (isError)."""


def data_file(out: Path | None, site: str, view: str | None, name: str) -> Path | None:
    """The data file a tool asks for, inside the dashboard folder only (the
    same rule as refresh_server.data_file)."""
    if out is None:
        return None
    path = Path(out) / site / (view or "") / "data" / f"{name}.json"
    try:
        path.resolve().relative_to(Path(out).resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


class Context:
    """What one MCP session or request may read."""

    def __init__(self, out_dir, *, config: dict | None = None, live_dir=None,
                 history_path=None, checker=None, only_sites=None,
                 configs: dict | None = None, default_site: str | None = None):
        self.out = Path(out_dir) if out_dir else None
        self.config = config or {}
        self.live_dir = Path(live_dir) if live_dir else None
        self.history_path = Path(history_path) if history_path else None
        self.checker = checker
        self.only_sites = set(only_sites) if only_sites else None
        self.configs = configs or {}
        self.default_site = default_site
        self._checks: dict[str, tuple[bool, str, bool]] = {}

    # ------------------------------------------------------------ who may read

    def check(self, site: str) -> tuple[bool, str, bool]:
        if site not in self._checks:
            if self.only_sites is not None and site not in self.only_sites:
                got = (False, "this server answers for another site only", False)
            elif self.checker is None:
                got = (True, "", False)
            else:
                ok, why, private = self.checker(site)
                got = (bool(ok), str(why or ""), bool(private))
            self._checks[site] = got
        return self._checks[site]

    def private(self, site: str) -> bool:
        return self.check(site)[2]

    def all_sites(self) -> list[str]:
        """Every site the dashboard folder holds, in sites.json's order."""
        if self.out is None or not self.out.is_dir():
            return []
        names = []
        try:
            listed = json.loads((self.out / "sites.json").read_text()).get("sites") or []
            names = [str(s.get("name") or "") for s in listed if isinstance(s, dict)]
        except (OSError, ValueError, AttributeError):
            pass
        names += sorted(p.parent.parent.name for p in self.out.glob("*/data/overview.json"))
        seen, out = set(), []
        for n in names:
            if n and n not in seen and SITE.match(n) and (self.out / n / "data").is_dir():
                seen.add(n)
                out.append(n)
        return out

    def sites(self) -> list[str]:
        """The sites this caller may read."""
        return [s for s in self.all_sites() if self.check(s)[0]]

    def site(self, given) -> str:
        """The site a tool works on: the one named, or the only (or default)
        one the caller may read. Refused in plain words otherwise."""
        if given in (None, ""):
            readable = self.sites()
            if self.default_site in readable:
                return self.default_site
            if len(readable) == 1:
                return readable[0]
            if not readable:
                raise Refused("There is no site here you may read.")
            raise Refused("Say which site: " + ", ".join(readable) + ".")
        if not isinstance(given, str) or not SITE.match(given):
            raise Refused(f"{given!r} is not a site name; list_sites gives the names.")
        ok, why, _ = self.check(given)
        if not ok:
            # The same words whether or not the site exists: nothing leaks.
            raise Refused(f"You may not read {given}: {why or 'not allowed'}.")
        if self.out is None or not (self.out / given / "data").is_dir():
            raise Refused(f"There is no site {given} here; list_sites gives the names.")
        return given

    def view(self, site: str, given) -> str | None:
        if given in (None, ""):
            return None
        if not isinstance(given, str) or not VIEW.match(given) or \
                not (self.out / site / given / "data").is_dir():
            raise Refused(f"{site} has no view {given!r}; list_sites names its views.")
        return given

    # ---------------------------------------------------------------- files

    def load(self, site: str, view: str | None, name: str, required: bool = True):
        if name in PRIVATE and not self.private(site):
            raise Refused(f"{name} holds visitors' addresses; this token may not read it "
                          "(it needs the read_private scope).")
        path = data_file(self.out, site, view, name)
        if path is None:
            if required:
                raise Refused(f"{name}.json is not there for {site}"
                              f"{' / ' + view if view else ''}: the dashboard has not "
                              "written it yet.")
            return None
        try:
            doc = json.loads(path.read_text())
        except (OSError, ValueError):
            raise Refused(f"{name}.json could not be read just now (it is rewritten every "
                          "2 minutes); try again.")
        if isinstance(doc, dict) and doc.get("state") == "error":
            raise Refused(f"{name}.json could not be built on the last run "
                          f"({doc.get('error') or 'no reason given'}); its figures are not "
                          "shown, never as zero.")
        return doc

    def config_for(self, site: str) -> dict:
        """The site's own config. For a site this server has no config for,
        the main one without the parts that belong to one site (the CMS
        leads, the website's page list), so no site's leads are shown as
        another's."""
        if site in self.configs:
            return self.configs[site]
        from ..config import site_name
        if not self.config or site_name(self.config) == site:
            return self.config
        out = {k: v for k, v in self.config.items() if k != "leads"}
        out["report"] = {k: v for k, v in (self.config.get("report") or {}).items()
                         if k != "pages_meta"}
        return out


# ----------------------------------------------------------------- dates

def parse_day(text, what: str) -> date:
    if not isinstance(text, str) or not DAY.match(text):
        raise Refused(f"{what} is a date written YYYY-MM-DD, not {text!r}.")
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise Refused(f"{what} {text!r} is not a real date.")


def anchor_of(doc: dict) -> date:
    """Yesterday as the data files see it: the last whole day they hold."""
    raw = (doc or {}).get("anchor")
    if raw:
        return date.fromisoformat(raw)
    days = [d.get("day") for d in (doc or {}).get("days") or [] if d.get("day")]
    if not days:
        raise Refused("The data files hold no days yet.")
    return date.fromisoformat(max(days))


def period(args: dict, anchor: date, first_key="from", last_key="to",
           max_days: int = MAX_RANGE) -> tuple[date, date]:
    """The range asked for; by default the last 7 whole days."""
    first = parse_day(args[first_key], first_key) if args.get(first_key) else None
    last = parse_day(args[last_key], last_key) if args.get(last_key) else None
    if first is None and last is None:
        last = anchor
    if last is None:
        last = max(first, min(first + timedelta(days=DEFAULT_DAYS - 1), anchor))
    if first is None:
        first = last - timedelta(days=DEFAULT_DAYS - 1)
    if last < first:
        raise Refused(f"{last_key} ({last}) is before {first_key} ({first}).")
    if (last - first).days + 1 > max_days:
        raise Refused(f"A range is at most {max_days} days here (the data files hold "
                      f"{MAX_RANGE}); the compare tool goes back up to 400.")
    return first, last


def coverage(days: list, first: date, last: date, anchor: date) -> tuple[dict, list[dict]]:
    """Which days of first..last are counted, and why the others are not.
    Returns (coverage, the counted `ok` entries)."""
    by = {d.get("day"): d for d in days or [] if isinstance(d, dict)}
    cov = {"from": first.isoformat(), "to": last.isoformat(),
           "days": (last - first).days + 1, "counted": 0, "partial": [], "withheld": [],
           "missing": [], "not_over": []}
    used = []
    day = first
    while day <= last:
        iso = day.isoformat()
        e = by.get(iso)
        state = (e or {}).get("state")
        if day > anchor:
            cov["not_over"].append(iso)
        elif e is None or state in ("missing", "before", None):
            cov["missing"].append(iso)
        elif state == "ok":
            used.append(e)
        elif state == "partial":
            cov["partial"].append({"day": iso, "from": e.get("partial_from"),
                                   "until": e.get("partial_until")})
        elif state == "withheld":
            cov["withheld"].append({"day": iso, "why": e.get("problems") or ""})
        else:
            cov["missing"].append(iso)
        day += timedelta(days=1)
    cov["counted"] = len(used)
    cov["complete"] = len(used) == cov["days"]
    return cov, used


def coverage_text(cov: dict) -> str:
    """One plain sentence or two: what was counted and what was left out."""
    out = [f"Counted {cov['counted']} whole, verified day{'s' if cov['counted'] != 1 else ''} "
           f"of {cov['days']} ({cov['from']} to {cov['to']})."]
    left = []
    if cov["withheld"]:
        left.append("withheld (the figures did not reconcile, so none are shown): "
                    + ", ".join(w["day"] + (f" ({w['why']})" if w["why"] else "")
                                for w in cov["withheld"]))
    if cov["partial"]:
        left.append("partial (the logs did not cover the whole day): "
                    + ", ".join(p["day"] for p in cov["partial"]))
    if cov["missing"]:
        left.append("missing (not collected): " + _dates(cov["missing"]))
    if cov["not_over"]:
        left.append("not over yet (see live_today for today): " + _dates(cov["not_over"]))
    if left:
        out.append("Left out, never counted as zero - " + "; ".join(left) + ".")
    return " ".join(out)


def _dates(days: list[str]) -> str:
    if len(days) <= 12:
        return ", ".join(days)
    return f"{', '.join(days[:10])} and {len(days) - 10} more ({days[0]} to {days[-1]})"


# ---------------------------------------------------------------- sums

def dig(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def total(entries: list[dict], *keys) -> int | float | None:
    """The sum over the counted days, or None when there is no counted day
    or any of them did not record it (null, never 0)."""
    if not entries:
        return None
    vals = [dig(e, *keys) for e in entries]
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in vals):
        return None
    return sum(vals)


def counters(entries: list[dict], *keys) -> Counter | None:
    """{label: n} summed over the counted days, or None as `total`."""
    if not entries:
        return None
    got = Counter()
    for e in entries:
        c = dig(e, *keys)
        if not isinstance(c, dict):
            return None
        got.update({str(k): int(v) for k, v in c.items() if isinstance(v, (int, float))})
    return got


def top(counter: Counter | None, limit: int, fold: bool = True) -> list[dict] | None:
    """Rows biggest first; past `limit`, the rest folded into "(all others)"
    so the rows still add up."""
    if counter is None:
        return None
    rest = counter.get(OTHERS, 0)
    items = sorted(((k, v) for k, v in counter.items() if k != OTHERS),
                   key=lambda kv: (-kv[1], kv[0]))
    rows = [{"label": k, "n": v} for k, v in items[:limit]]
    rest += sum(v for _, v in items[limit:])
    if rest and fold:
        rows.append({"label": OTHERS, "n": rest})
    return rows


def num(n) -> str:
    if n is None:
        return "not recorded"
    if isinstance(n, float):
        return f"{n:,.1f}"
    return f"{n:,}"


def pct(a, b) -> float | None:
    if a is None or b in (None, 0):
        return None
    return round((a - b) / b * 100, 1)

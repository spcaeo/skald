"""The second count of Security (day kind `security`, security.py).

Registered in audit_more.RECOUNTS, so it rides on audit.recount's one pass: it
sees every line of the site's hosts with the audit's own group and what the
audit's judge found (a spoof, a visit that never rendered, a crawler session,
too fast), and each line of another host (`other_host`), and builds the whole
blob again by its own code. It shares with security.py only the name lists and
thresholds of security_names.py and classify.py's scanner patterns:

  a probe          a line the audit put in bots whose path or URL matches
                   classify.PROBE / PROBE_QUERY and is under none of the
                   site's old paths; and a line of another host whose Host is
                   an IP literal and whose path or URL matches them
  a pair           the line's address and user agent; its country is its
                   first line's (the audit's GeoIP fill)
  own referrer     the referrer's host is a site host, or a subdomain of one
                   with "www." taken off (no hosts listed: the line's host)
  rendered         such a referrer on an asset (the audit's asset rule) or a
                   framework payload
  episodes         per address, over its people and bots lines in time order:
                   for each line the earliest line within the window before
                   it (two pointers); every line of a window holding the
                   threshold is marked (a difference array); marked lines
                   whose gap stays within the window make one episode
  the shell        per host, every 2xx probe answer with a size above 0; for
                   each such size, the distinct paths answered within the
                   tolerance of it; the size with the most paths (the
                   smallest of a tie) is the shell when they are at least
                   `shell_paths`
  hosting          the hosting list read by the audit's own crawler checks
                   (audit_release2.Checks); None when it has none

Every figure of the stored blob is compared leaf by leaf. On a whole day kept
with addresses (security_kept.py), each kept row's address and user agent are
checked against the recount's own ranking of the same rows: the address in
full, shortened by the documented rule on a site that shortens (audit_people's
reader), or "(removed)" with no user agent. No address is written into a
problem.
"""
from __future__ import annotations

import bisect
import ipaddress
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .classify import PROBE, PROBE_QUERY
from . import security_names as N

REMOVED = "(removed)"
PAYLOAD = ("_rsc=", "__flight__=", "_data=")


def _ip_host(host: str) -> bool:
    text = (host or "").strip().lower()
    if text.startswith("["):
        text = text[1:].partition("]")[0]
    elif text.count(":") == 1:
        text = text.partition(":")[0]
    try:
        ipaddress.ip_address(text)
        return True
    except ValueError:
        return False


def _theirs(ref_host: str, own: set) -> bool:
    if not ref_host:
        return False
    for h in own:
        root = h[4:] if h.startswith("www.") else h
        if ref_host in (h, root) or ref_host.endswith("." + root):
            return True
    return False


def _cls(status: str) -> str:
    first = (status or " ")[0]
    return first + "xx" if first in ("2", "3", "4", "5") else "other"


def _what(path: str, url: str) -> str:
    for key, _, rx in N.CATEGORIES:
        if rx.search(url if key == "injection" else path.lower()):
            return key
    return N.OTHER[0]


def _kind(url: str) -> str:
    return next((key for key, _, rx in N.INJECTION if rx.search(url)), "other")


def _aware(when):
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _stamp(when) -> str:
    w = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return w.astimezone(timezone.utc).isoformat(timespec="seconds")


def _ranked(counter: Counter, keep: int) -> dict:
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    out = dict(items[:keep])
    tail = sum(v for _, v in items[keep:])
    if tail:
        out[N.FOLD] = tail
    return out


def _plain(counter) -> dict:
    return {k: counter[k] for k in sorted(counter)}


def short_address(address: str) -> str:
    from .audit_people import short_address as cut
    return cut(address)


class Recount:
    def __init__(self, config: dict, day, tz, own: set) -> None:
        self.config, self.day = config, day
        self.own = {h.lower() for h in own}
        self.rules = N.settings(config)
        raw = ((config or {}).get("site") or {}).get("legacy_paths") or []
        self.old = tuple(str(p) for p in (raw.split() if isinstance(raw, str) else raw)
                         if str(p).startswith("/"))
        self.seen: dict[tuple, list] = {}       # pair -> [(line, group, info, other)]
        self.order: list[tuple] = []
        self.site_lines: list = []              # every line of the site's hosts (log signs)

    # ------------------------------------------------------------- feeding

    def _keep(self, line, group, info, other: bool) -> None:
        key = (line.address, line.agent)
        got = self.seen.get(key)
        if got is None:
            got = self.seen[key] = []
            self.order.append(key)
        got.append((line, group, info, other))

    def judged(self, line, group, info) -> None:
        self._keep(line, group, dict(info or {}), False)
        self.site_lines.append(line)

    def other_host(self, line) -> None:
        if _ip_host(line.host):
            self._keep(line, None, {}, True)

    def visit(self, lines, is_page, labels) -> None:
        return None

    # ------------------------------------------------------------ counting

    def _probe(self, line, group, other: bool) -> bool:
        if not (PROBE.search(line.path) or PROBE_QUERY.search(line.url)):
            return False
        if other:
            return True
        return group == "bots" and not any(line.path.startswith(p) for p in self.old)

    def _asset(self, line) -> bool:
        from .audit import _asset
        url = line.url.lower()
        return _asset(line) or any(("?" + p) in url or ("&" + p) in url for p in PAYLOAD)

    def _page(self, line) -> bool:
        from .audit import is_page
        return is_page(line)

    def build(self) -> tuple[dict, list]:
        """(the blob, [(seq, address, agent)])."""
        from .audit_release2 import Checks
        checks = Checks(self.config, datetime.now(timezone.utc))
        known = bool(checks.hosting)
        rows = {}
        answered = []                              # (host, path, when, status, size, cat, pair)
        sizes = defaultdict(list)                  # host -> [(size, path)]
        inj = {}
        probes = other_probes = bare_probes = query_only = 0
        watched = defaultdict(list)                # address -> [(when, cls, path, pair)]
        posts = defaultdict(list)
        for key in self.order:
            r = {"requests": 0, "first": None, "last": None, "status": Counter(),
                 "own_ref": 0, "rendered": 0, "bare": 0, "country": "", "probes": 0,
                 "cats": Counter(), "pstatus": Counter(), "paths": Counter(),
                 "fakes": Counter(), "pages": Counter(), "injection": 0, "login": 0,
                 "burst": 0}
            for i, (line, group, info, other) in enumerate(self.seen[key]):
                if i == 0:
                    r["country"] = (line.country or "").upper()
                r["requests"] += 1
                r["first"] = line.when if r["first"] is None else min(r["first"], line.when)
                r["last"] = line.when if r["last"] is None else max(r["last"], line.when)
                r["status"][_cls(line.status)] += 1
                if _ip_host(line.host):
                    r["bare"] += 1
                if line.referrer:
                    mine = self.own or ({line.host.lower()} if line.host else set())
                    if _theirs((urlsplit(line.referrer).hostname or "").lower(), mine):
                        r["own_ref"] += 1
                        if self._asset(line):
                            r["rendered"] += 1
                if self._probe(line, group, other):
                    probes += 1
                    other_probes += other
                    bare_probes += _ip_host(line.host)
                    r["probes"] += 1
                    what = _what(line.path, line.url)
                    c = _cls(line.status)
                    r["cats"][what] += 1
                    r["pstatus"][c] += 1
                    r["paths"][line.path[:200]] += 1
                    if what == "injection":
                        r["injection"] += 1
                        slot = inj.setdefault((key, _kind(line.url)), [0, [], Counter()])
                        slot[0] += 1
                        slot[1].append(line.when)
                        slot[2][c] += 1
                    if c == "2xx" and not PROBE.search(line.path):
                        query_only += 1             # an ordinary page, its query an attack
                    elif c == "2xx":
                        host = (line.host or "").lower()[:100]
                        answered.append((host, line.path[:200], line.when, line.status,
                                         line.size, what, key))
                        if line.size is not None and int(line.size) > 0:
                            sizes[host].append((int(line.size), line.path[:200]))
                if group == "bots":
                    fake = None
                    if info.get("spoofed"):
                        fake = "claims:" + info["spoofed"]
                    elif info.get("not_rendered"):
                        fake = "not_rendered"
                    elif info.get("too_fast"):
                        fake = "too_fast"
                    elif info.get("crawler"):
                        fake = "crawler_session"
                    if fake:
                        r["fakes"][fake] += 1
                        if self._page(line):
                            r["pages"][line.path[:200]] += 1
                if group in ("people", "bots"):
                    item = (line.when, _cls(line.status), line.path[:200], key)
                    watched[line.address].append(item)
                    if line.method == "POST" and N.LOGIN_PATH.search(line.path):
                        posts[line.address].append(item)
            rows[key] = r
        logins = self._episodes(posts, self.rules["login_posts"], self.rules["login_seconds"])
        bursts = self._episodes(watched, self.rules["burst_requests"],
                                self.rules["burst_seconds"])
        for eps, field in ((logins, "login"), (bursts, "burst")):
            for ep in eps:
                for key, n in ep["pairs"].items():
                    rows[key][field] += n
        suspect = [k for k, r in rows.items()
                   if r["probes"] or r["fakes"] or r["login"] or r["burst"]]
        suspect.sort(key=lambda k: (-rows[k]["probes"], -(rows[k]["login"] + rows[k]["burst"]),
                                    -rows[k]["requests"], _stamp(rows[k]["first"]), k[0], k[1]))
        top = suspect[:N.WHO]
        seq = {k: i for i, k in enumerate(top)}
        scanners = [k for k, r in rows.items() if r["probes"]]
        cats, stat, where, paths = Counter(), Counter(), Counter(), Counter()
        hosting = 0 if known else None
        for k in scanners:
            r = rows[k]
            cats += r["cats"]
            stat += r["pstatus"]
            where[r["country"] or N.UNKNOWN] += r["probes"]
            paths += r["paths"]
            if known and checks.from_hosting(k[0]):
                hosting += r["probes"]
        fakes, fake_pages = Counter(), Counter()
        for r in rows.values():
            fakes += r["fakes"]
            fake_pages += r["pages"]
        blob = {
            "rules": {**self.rules, "exposure_rule": N.EXPOSURE_RULE},
            "probes": probes, "probes_other": other_probes,
            "scanners": len(scanners), "addresses": len({k[0] for k in scanners}),
            "requests": sum(rows[k]["requests"] for k in scanners),
            "categories": _plain(cats), "status": _plain(stat),
            "countries": _ranked(where, N.TOP_COUNTRIES), "hosting": hosting,
            "forged": sum(1 for k in suspect if rows[k]["own_ref"] and not rows[k]["rendered"]),
            "bare_ip": bare_probes, "paths": _ranked(paths, N.TOP_PATHS),
            "exposure": self._exposure(answered, sizes, seq, query_only),
            "attacks": {"injection": self._inj(inj, seq),
                        "login": self._eps(logins, seq, "posts"),
                        "bursts": self._eps(bursts, seq, "requests")},
            "fake": {"requests": sum(fakes.values()),
                     "pairs": sum(1 for r in rows.values() if r["fakes"]),
                     "kinds": _plain(fakes), "pages": _ranked(fake_pages, N.FAKE_PAGES)},
            "signs": self._signs(),
            "who": [self._row(i, k, rows[k], checks if known else None)
                    for i, k in enumerate(top)],
            "who_folded": len(suspect) - len(top),
        }
        return blob, [(i, k[0], k[1]) for i, k in enumerate(top)]

    def _signs(self) -> dict:
        """Gateway errors and .php requests by UTC hour, POST sizes: its own reading."""
        gw, php = {}, {}
        recorded = large = 0
        biggest = None
        paths = Counter()
        for line in self.site_lines:
            w = line.when if line.when.tzinfo else line.when.replace(tzinfo=timezone.utc)
            hour = w.astimezone(timezone.utc).isoformat()[:13]
            if line.status in ("502", "503", "504"):
                gw[hour] = gw.get(hour, 0) + 1
            low = line.path.lower()
            if re.search(r"\.php[0-9]?(/|$)", low):
                php[hour] = php.get(hour, 0) + 1
            if line.method == "POST" and line.length is not None:
                recorded += 1
                biggest = line.length if biggest is None else max(biggest, line.length)
                if line.length >= self.rules["large_post_bytes"]:
                    large += 1
                    paths[line.path[:200]] += 1
        return {"gateway": {"requests": sum(gw.values()), "hours": {h: gw[h] for h in sorted(gw)}},
                "php": {"requests": sum(php.values()), "hours": {h: php[h] for h in sorted(php)}},
                "posts": None if not recorded else {"recorded": recorded, "large": large,
                                                     "max": biggest,
                                                     "paths": _ranked(paths, N.SIGN_PATHS)}}

    def _row(self, i, key, r, checks) -> dict:
        fake = min(r["fakes"].items(), key=lambda kv: (-kv[1], kv[0]))[0] if r["fakes"] else None
        return {"seq": i,
                "kinds": [name for name, on in (("scanner", r["probes"]),
                                                ("attack", r["login"] + r["burst"]),
                                                ("fake", sum(r["fakes"].values()))) if on],
                "first": _stamp(r["first"]), "last": _stamp(r["last"]),
                "requests": r["requests"], "probes": r["probes"],
                "categories": _plain(r["cats"]), "status": _plain(r["status"]),
                "probe_status": _plain(r["pstatus"]),
                "forged": bool(r["own_ref"]) and not r["rendered"], "bare_ip": r["bare"],
                "country": r["country"] or None,
                "hosting": None if checks is None else checks.from_hosting(key[0]),
                "fake": fake, "fake_requests": sum(r["fakes"].values()),
                "injection": r["injection"], "login": r["login"], "burst": r["burst"],
                "paths": _ranked(r["paths"], N.ROW_PATHS), "pages": _ranked(r["pages"], N.ROW_PATHS)}

    @staticmethod
    def _episodes(per: dict, need: int, seconds: int) -> list[dict]:
        span = timedelta(seconds=seconds)
        out = []
        for address, items in per.items():
            n = len(items)
            if n < need:
                continue
            # The address's requests in time order, whatever order they were read in or
            # which of its agents made them; ties by status, path and pair.
            items = sorted(items, key=lambda it: (_aware(it[0]), it[1], it[2], it[3]))
            times = [it[0] for it in items]
            diff = [0] * (n + 1)
            j = 0
            for k in range(n):
                while times[k] - times[j] > span:
                    j += 1
                if k - j + 1 >= need:
                    diff[j] += 1
                    diff[k + 1] -= 1
            running, prev, ep = 0, None, None
            for k in range(n):
                running += diff[k]
                if running <= 0:
                    continue
                when = times[k]
                if ep is None or when - prev > span:
                    ep = {"start": when, "end": when, "n": 0, "status": Counter(),
                          "paths": Counter(), "pairs": Counter()}
                    out.append(ep)
                ep["end"] = when
                ep["n"] += 1
                ep["status"][items[k][1]] += 1
                ep["paths"][items[k][2]] += 1
                ep["pairs"][items[k][3]] += 1
                prev = when
        return out

    @staticmethod
    def _eps(eps: list, seq: dict, unit: str) -> dict:
        rows = [{"start": _stamp(e["start"]), "end": _stamp(e["end"]), unit: e["n"],
                 "status": _plain(e["status"]),
                 "path": min(e["paths"].items(), key=lambda kv: (-kv[1], kv[0]))[0],
                 "paths": len(e["paths"]),
                 "who": sorted(seq[k] for k in e["pairs"] if k in seq)} for e in eps]
        rows.sort(key=lambda r: (-r[unit], r["start"], r["end"], r["path"], r["who"],
                                 sorted(r["status"].items())))
        return {unit: sum(r[unit] for r in rows), "episodes": len(rows),
                "rows": rows[:N.EPISODES]}

    @staticmethod
    def _inj(inj: dict, seq: dict) -> dict:
        rows = [{"who": seq.get(key), "kind": kind, "requests": v[0],
                 "first": _stamp(min(v[1])), "last": _stamp(max(v[1])), "status": _plain(v[2])}
                for (key, kind), v in inj.items()]
        rows.sort(key=lambda r: (-r["requests"], r["first"], r["kind"],
                                 -1 if r["who"] is None else r["who"], r["last"],
                                 sorted(r["status"].items())))
        kinds = Counter()
        for (_, kind), v in inj.items():
            kinds[kind] += v[0]
        return {"requests": sum(kinds.values()), "kinds": _plain(kinds),
                "rows": rows[:N.EPISODES]}

    def _exposure(self, answered: list, sizes: dict, seq: dict, query_only: int = 0) -> dict:
        tol, need = self.rules["tolerance"], self.rules["shell_paths"]
        for pairs in sizes.values():
            pairs.sort()

        def around(host, s) -> int:
            pairs = sizes.get(host) or []
            keys = [k for k, _ in pairs]
            lo = bisect.bisect_left(keys, s - tol)
            hi = bisect.bisect_right(keys, s + tol)
            return len({p for _, p in pairs[lo:hi]})
        shell, every = {}, {}
        for host, pairs in sizes.items():
            counted = [(around(host, s), s) for s in sorted({k for k, _ in pairs})]
            counted.sort(key=lambda c: (-c[0], c[1]))
            kept = []
            for n, s in counted:
                if n < need:
                    break
                if not any(abs(s - q) <= tol for q, _ in kept):
                    kept.append((s, n))
            shell[host] = kept[0] if kept else None
            every[host] = sorted(s for s, _ in kept)
        hosts, rows, tally = {}, [], Counter()
        for host, path, when, status, size, what, key in answered:
            sh = shell.get(host)
            if size is None:
                v = "unknown"
            elif int(size) == 0:
                v = "empty"
            elif around(host, int(size)) >= need:
                v = "shell"
            else:
                v = "possible"
            tally[v] += 1
            if host not in hosts:
                hosts[host] = {"bare_ip": _ip_host(host), "shell_size": sh[0] if sh else None,
                               "shell_paths": sh[1] if sh else 0,
                               "shell_sizes": every.get(host, []), "answered": 0, "shell": 0,
                               "empty": 0, "possible": 0, "unknown": 0}
            hosts[host]["answered"] += 1
            hosts[host][v] += 1
            if v in ("possible", "unknown"):
                rows.append({"host": host, "path": path, "at": _stamp(when), "status": status,
                             "size": None if size is None else int(size), "verdict": v,
                             "category": what, "shell_size": sh[0] if sh else None,
                             "who": seq.get(key)})
        rows.sort(key=lambda r: (r["verdict"] != "possible", r["at"], r["host"], r["path"]))
        return {"answered": len(answered), "query_only": query_only,
                "shell": tally["shell"], "empty": tally["empty"],
                "possible": tally["possible"], "unknown": tally["unknown"],
                "hosts": {h: hosts[h] for h in sorted(hosts)},
                "rows": rows[:N.EXPOSURE_ROWS], "folded": max(0, len(rows) - N.EXPOSURE_ROWS)}

    # ----------------------------------------------------------- comparing

    def compare(self, stored: dict, same, problems: list) -> None:
        blob = stored.get("security")
        if blob is None:
            return
        mine, who = self.build()
        _leaves("security", blob, mine, same, problems)
        self._kept(who, same, problems)

    def _kept(self, who: list, same, problems: list) -> None:
        """A whole day kept with addresses: each row's address and agent."""
        from .audit_people import _site, _store, shortens
        path = _store(self.config)
        if path is None or not Path(path).is_file():
            return
        db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
        try:
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE "
                                              "type = 'table'")}
            if not {"security_rows", "security_days"} <= names:
                return
            key = (_site(self.config), self.day.isoformat())
            day = db.execute("SELECT state, rows FROM security_days WHERE site = ? AND day = ?",
                             key).fetchone()
            if day is None or day[0] != "whole":
                return
            kept = {s: (ip, ua) for s, ip, ua in db.execute(
                "SELECT seq, ip, user_agent FROM security_rows WHERE site = ? AND day = ?", key)}
        finally:
            db.close()
        same("security: rows kept with an address", len(kept), len(who))
        same("security: the day's own row count", int(day[1]), len(kept))
        cut = shortens(self.config)
        differ = 0
        for s, address, agent in who:
            got = kept.get(s)
            if got is None:
                differ += 1
                continue
            ip, ua = got
            if ip == REMOVED:
                differ += ua is not None
                continue
            # A full-address site may hold a day kept while it shortened.
            want = {short_address(address)} if cut else {address, short_address(address)}
            if ip not in want or (ua or "") != (agent or "")[:400]:
                differ += 1
        same("security: kept rows whose address or agent differ from the recount", differ, 0)


def _leaves(where: str, stored, mine, same, problems: list) -> None:
    """Every leaf of the two blobs: numbers through `same`, anything else
    equal or a problem (never an address: the blob holds none)."""
    if isinstance(stored, dict) and isinstance(mine, dict):
        for k in sorted(set(stored) | set(mine), key=str):
            if k not in stored or k not in mine:
                problems.append(f"{where}.{k}: only in the "
                                f"{'recount' if k in mine else 'stored day'}")
                continue
            _leaves(f"{where}.{k}", stored[k], mine[k], same, problems)
        return
    if isinstance(stored, list) and isinstance(mine, list):
        same(f"{where}: entries", len(stored), len(mine))
        for i, (a, b) in enumerate(zip(stored, mine)):
            _leaves(f"{where}[{i}]", a, b, same, problems)
        return
    numeric = (isinstance(stored, int) and not isinstance(stored, bool)
               and isinstance(mine, int) and not isinstance(mine, bool))
    if numeric:
        same(where, stored, mine)
    elif stored != mine:
        problems.append(f"{where}: history has {stored!r}, the recount finds {mine!r}")


# ------------------------------------------------- the scan-wave alert

STATE_FILE = "alerts-state.json"


def set_up(ctx) -> bool:
    on = ((getattr(ctx, "config", None) or {}).get("alerts") or {})
    flag = lambda v: v is True or str(v).strip().lower() in ("1", "true", "yes", "on")  # noqa: E731
    return flag(on.get("enabled", False)) and flag(on.get("scan_wave", False))


def daily(ctx, day) -> list[str] | None:
    """run-daily's recounts: the scan-wave evaluation kept in the alert state,
    worked out again from history (None: nothing kept yet)."""
    import json
    try:
        state = json.loads((Path(ctx.live_dir) / STATE_FILE).read_text())
    except (OSError, ValueError):
        return None
    kept = ((state or {}).get("security") or {}) if isinstance(state, dict) else {}
    if not kept.get("wave"):
        return None
    with ctx.history() as history:
        return recheck(history.db, ctx.site, kept)


def _probes(db, site: str, d: str):
    """The day's probes when it is verified and whole, else None."""
    import json
    row = db.execute("SELECT verified, partial_from, partial_until FROM days WHERE site = ? "
                     "AND day = ?", (site, d)).fetchone()
    if not row or not row[0] or row[1] is not None or row[2] is not None:
        return None
    got = db.execute("SELECT data FROM day_extras WHERE site = ? AND day = ? AND kind = ?",
                     (site, d, "security")).fetchone()
    return None if got is None else int(json.loads(got[0])["probes"])


def recheck(db, site: str, kept: dict) -> list[str]:
    from datetime import date as day_of
    wave, cfg = kept["wave"], kept.get("settings") or {}
    out = []
    if wave.get("state") != "ok":
        return out
    day = day_of.fromisoformat(wave["day"])
    figure = _probes(db, site, wave["day"])
    if figure != wave.get("figure"):
        out.append(f"scan wave {wave['day']}: probes kept {wave.get('figure')}, history "
                   f"gives {figure}")
    values = []
    for k in range(1, int(cfg.get("scan_wave_days", 14)) + 1):
        d = (day - timedelta(days=k)).isoformat()
        n = _probes(db, site, d)
        if n is not None:
            values.append(n)
    values.sort()
    mid = len(values) // 2
    median = (values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2) \
        if values else None
    if median != wave.get("median"):
        out.append(f"scan wave {wave['day']}: median kept {wave.get('median')}, history "
                   f"gives {median}")
    if median is not None:
        need = max(int(cfg.get("scan_wave_factor", 3)) * median,
                   int(cfg.get("scan_wave_minimum", 200)))
        if bool(figure is not None and figure >= need) != bool(wave.get("found")):
            out.append(f"scan wave {wave['day']}: the alert says {bool(wave.get('found'))}, "
                       f"history says {not wave.get('found')}")
    return out

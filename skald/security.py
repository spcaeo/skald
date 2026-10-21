"""Security: scanners, what they were answered, attack attempts and fake browsers.

The day kind `security` (docs/DATA-CONTRACT-SECURITY.md) and its collector. A
view across the five groups, never a group of its own: every request stays
where classify.py put it, so the partition is unchanged. Built in the tally
pass (extras.Extras offers every counted hit to Collector.add; aggregate.Tally
offers each line of another host whose Host is an IP literal to
Collector.other_host), for the whole site only (a view's tally has none).

Who is what (the name lists and thresholds are security_names.py):

  scanner probe     a request in the bots group whose path or query a scanner
                    pattern matches (classify.PROBE / PROBE_QUERY), not under
                    one of the site's old paths (site.legacy_paths); and a line
                    sent to a bare IP of another host whose path matches them
  scanner           an (address, user agent) pair with at least one probe that
                    day; all its requests are counted on its row
  category          what a probe looked for: the first of
                    security_names.CATEGORIES that matches, else "other"
  forged referrer   a suspect pair that sent a referrer of the site's own
                    hosts (or a subdomain of one) and never loaded an asset
                    with such a referrer: it never rendered a page
  bare IP           a request whose Host is an IP literal
  login hammering   at least `login_posts` POSTs to a login or form path
                    (security_names.LOGIN_PATH) from one address within
                    `login_seconds`, people and bots only
  burst             at least `burst_requests` requests from one address within
                    `burst_seconds`, people and bots only
  fake browser      a request classify.py moved to bots as a browser that never
                    rendered the page, read too fast, fetched robots.txt or a
                    sitemap, or claimed a crawler's name it could not prove

An episode (login or burst): every request that lies in some window of the
threshold's length holding at least the threshold's count, grouped while the
gap between two such requests stays within the window.

"Is anything exposed?" Each probe answered 2xx is one of:

  shell     its size is within `tolerance` bytes of the host's shell: the size
            (within the tolerance) that the most distinct probe paths of that
            host were answered 2xx with that day, if at least `shell_paths`
            paths share it. A single-page app answers every path it does not have with
            its index; a default server page answers every path sent to the
            bare IP. Each host (and each IP literal) has its own: the size the
            log records is the size sent, after compression, so the same page
            can be 392 bytes through one door and 404 through another
  empty     a body of 0 bytes
  possible  any other size: a possible exposure, to check now
  unknown   the line has no size: Skald cannot tell, and never calls it safe

The log records a size, never the content; nothing here can prove a file was
or was not leaked. DATA-CONTRACT-SECURITY.md says what each figure promises.

No address and no user agent is in the blob: the suspect rows (`who`) carry a
sequence number, and the addresses behind them are kept apart, in the
conversions file, only while the site keeps addresses (security_kept.py). The
second count is audit_security.py.
"""
from __future__ import annotations

import bisect
from collections import Counter
from datetime import timedelta, timezone
from urllib.parse import urlsplit

from .classify import CRAWLER_SESSION, NOT_RENDERED, PROBE, PROBE_QUERY, TOO_FAST, Group
from .parse import ASSET, RSC_PAYLOAD
from . import security_names as N

STATUS = ("2xx", "3xx", "4xx", "5xx")
WATCHED = (Group.PEOPLE, Group.BOTS)          # login hammering and bursts
FAKE_WORDS = {"not_rendered": "Never rendered the page", "too_fast": "Too fast for a person",
              "crawler_session": "Browser-like crawler (robots.txt or sitemap)"}
CLAIM = "claims:"


def status_class(status: str) -> str:
    s = (status or "")[:1]
    return f"{s}xx" if s in "2345" and s else "other"


def category(path: str, url: str) -> str:
    low = path.lower()
    for key, _, pattern in N.CATEGORIES:
        if pattern.search(url if key == "injection" else low):
            return key
    return N.OTHER[0]


def injection_kind(url: str) -> str:
    for key, _, pattern in N.INJECTION:
        if pattern.search(url):
            return key
    return "other"


def fake_kind(verdict) -> str | None:
    if verdict.group is not Group.BOTS:
        return None
    if verdict.verified == "spoofed" and verdict.claim:
        return CLAIM + verdict.claim
    return {NOT_RENDERED: "not_rendered", TOO_FAST: "too_fast",
            CRAWLER_SESSION: "crawler_session"}.get(verdict.engine)


def fake_words(kind: str) -> str:
    return f"Claims to be {kind[len(CLAIM):]}" if kind.startswith(CLAIM) else FAKE_WORDS.get(kind, kind)


def _utc(when):
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _iso(when) -> str | None:
    return None if when is None else _utc(when).astimezone(timezone.utc).isoformat(timespec="seconds")


def _top(counter: Counter, keep: int) -> dict:
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    out = {str(k): int(v) for k, v in ranked[:keep]}
    rest = sum(v for _, v in ranked[keep:])
    if rest:
        out[N.FOLD] = int(rest)
    return out


class _Pair:
    __slots__ = ("requests", "first", "last", "status", "own_ref", "rendered", "bare_ip",
                 "country", "probes", "cats", "probe_status", "paths", "fakes", "pages",
                 "injection", "login", "burst")

    def __init__(self, when, country: str) -> None:
        self.requests = self.own_ref = self.rendered = self.bare_ip = 0
        self.first = self.last = when
        self.status: Counter = Counter()
        self.country = country
        self.probes = self.injection = self.login = self.burst = 0
        self.cats: Counter | None = None
        self.probe_status: Counter | None = None
        self.paths: Counter | None = None
        self.fakes: Counter | None = None
        self.pages: Counter | None = None

    def suspect(self) -> bool:
        return bool(self.probes or self.fakes or self.login or self.burst)


class Runs:
    """Episodes of one kind (login posts or requests) per address (see the module for the
    rule). Every request is kept and the episodes are worked out at the end over the
    address's requests sorted by (time, status, path, pair): never in the order lines
    arrive, which a real log does not keep (nginx writes at the answer's end; shippers
    merge files). An episode's end is its latest time."""

    def __init__(self, need: int, seconds: int) -> None:
        self.need, self.span = need, float(seconds)
        self.per: dict[str, list] = {}

    def add(self, address: str, when, item: tuple) -> None:
        self.per.setdefault(address, []).append((_utc(when).timestamp(), when, item))

    def episodes(self) -> list[tuple[str, list]]:
        out = []
        for address, got in self.per.items():
            if len(got) < self.need:
                continue
            got.sort(key=lambda e: (e[0], e[2][0], e[2][1], e[2][2]))
            stamps = [e[0] for e in got]
            marks = [0] * (len(got) + 1)
            for k, t in enumerate(stamps):
                j = bisect.bisect_left(stamps, t - self.span)
                if k - j + 1 >= self.need:
                    marks[j] += 1
                    marks[k + 1] -= 1
            on, last, ep = 0, None, None
            for k, (t, when, it) in enumerate(got):
                on += marks[k]
                if on <= 0:
                    continue
                if ep is None or t - last > self.span:
                    ep = [_utc(when), _utc(when), 0, Counter(), Counter(), Counter()]
                    out.append((address, ep))
                ep[1] = max(ep[1], _utc(when))
                ep[2] += 1
                ep[3][it[0]] += 1          # status class
                ep[4][it[1]] += 1          # path
                ep[5][it[2]] += 1          # pair
                last = t
        return out


class Collector:
    """Fed every counted hit of the whole site (extras.Extras.add) and each
    bare-IP line of another host (other_host)."""

    def __init__(self, rules: dict | None = None) -> None:
        self.rules = dict(rules or N.DEFAULTS)
        self.own: set = set()
        self.verifier = None                   # bot_verify.Verifier (summarise_views)
        self.pairs: dict[tuple, _Pair] = {}
        self.answered: list[tuple] = []        # (host, path, when, status, size, cat, pair)
        self.sizes: dict[str, dict] = {}       # host -> {size: {paths}}
        self.probes = self.probes_other = self.probes_bare = self.query_only = 0
        self.inj: dict[tuple, list] = {}       # (pair, kind) -> [n, first, last, statuses]
        self.login = Runs(self.rules["login_posts"], self.rules["login_seconds"])
        self.bursts = Runs(self.rules["burst_requests"], self.rules["burst_seconds"])
        # Log signs: gateway errors and .php requests by UTC hour; POST sizes.
        self.gateway: Counter = Counter()
        self.php: Counter = Counter()
        self.posts = {"recorded": 0, "large": 0, "max": None, "paths": Counter()}
        self._hosts: dict[str, bool] = {}      # host -> an IP literal (asked once per host)
        self._refs: dict[str, str] = {}        # referrer -> its host (bounded)

    def _bare(self, host: str) -> bool:
        got = self._hosts.get(host)
        if got is None:
            got = N.bare_ip(host)
            if len(self._hosts) < 10_000:
                self._hosts[host] = got
        return got

    def set_rules(self, rules: dict | None) -> None:
        self.rules = dict(rules or N.DEFAULTS)
        self.login = Runs(self.rules["login_posts"], self.rules["login_seconds"])
        self.bursts = Runs(self.rules["burst_requests"], self.rules["burst_seconds"])

    def _pair(self, hit) -> tuple[tuple, _Pair]:
        key = (hit.address, hit.user_agent)
        p = self.pairs.get(key)
        when = _utc(hit.when)
        if p is None:
            p = self.pairs[key] = _Pair(when, (hit.country or "").upper())
        p.requests += 1
        if when < p.first:              # a line read late: the earliest one names the country
            p.first = when
            p.country = (hit.country or "").upper()
        if when > p.last:
            p.last = when
        p.status[status_class(hit.status)] += 1
        if self._bare(hit.host):
            p.bare_ip += 1
        return key, p

    def _referrer(self, hit, p: _Pair) -> None:
        if not hit.referrer:
            return
        own = self.own or ({hit.host.lower()} if hit.host else set())
        ref = self._refs.get(hit.referrer)
        if ref is None:
            ref = (urlsplit(hit.referrer).hostname or "").lower()
            if len(self._refs) < 50_000:
                self._refs[hit.referrer] = ref
        if not N.own_like(ref, own):
            return
        p.own_ref += 1
        if ASSET.search(hit.path) or RSC_PAYLOAD.search(hit.url):
            p.rendered += 1

    def _probe(self, hit, key, p: _Pair, other: bool) -> None:
        self.probes += 1
        if other:
            self.probes_other += 1
        if self._bare(hit.host):
            self.probes_bare += 1
        p.probes += 1
        cat = category(hit.path, hit.url)
        if p.cats is None:
            p.cats, p.probe_status, p.paths = Counter(), Counter(), Counter()
        cls = status_class(hit.status)
        p.cats[cat] += 1
        p.probe_status[cls] += 1
        p.paths[hit.path[:200]] += 1
        if cat == "injection":
            p.injection += 1
            when = _utc(hit.when)
            got = self.inj.get((key, injection_kind(hit.url)))
            if got is None:
                got = self.inj[(key, injection_kind(hit.url))] = [0, when, when, Counter()]
            got[0] += 1
            got[1], got[2] = min(got[1], when), max(got[2], when)
            got[3][cls] += 1
        if cls == "2xx" and not PROBE.search(hit.path):
            # Only the query string is an attack: the path is an ordinary page, answered as
            # one. Attack attempts lists it; no file was asked for, so it is no exposure.
            self.query_only += 1
        elif cls == "2xx":
            host = (hit.host or "").lower()[:100]
            self.answered.append((host, hit.path[:200], _utc(hit.when), hit.status, hit.size,
                                  cat, key))
            if hit.size is not None and int(hit.size) > 0:
                self.sizes.setdefault(host, {}).setdefault(int(hit.size), set()).add(hit.path[:200])

    def _signs(self, hit) -> None:
        hour = None
        if hit.status in N.GATEWAY:
            hour = _utc(hit.when).astimezone(timezone.utc).strftime("%Y-%m-%dT%H")
            self.gateway[hour] += 1
        if N.PHP_PATH.search(hit.path):
            hour = hour or _utc(hit.when).astimezone(timezone.utc).strftime("%Y-%m-%dT%H")
            self.php[hour] += 1
        length = getattr(hit, "request_length", None)
        if hit.method == "POST" and length is not None:
            got = self.posts
            got["recorded"] += 1
            got["max"] = length if got["max"] is None else max(got["max"], length)
            if length >= self.rules["large_post_bytes"]:
                got["large"] += 1
                got["paths"][hit.path[:200]] += 1

    def add(self, hit, verdict) -> None:
        key, p = self._pair(hit)
        self._signs(hit)
        self._referrer(hit, p)
        group = verdict.group
        if group is Group.BOTS and not verdict.legacy and (
                PROBE.search(hit.path) or PROBE_QUERY.search(hit.url)):
            self._probe(hit, key, p, False)
        kind = fake_kind(verdict)
        if kind is not None:
            if p.fakes is None:
                p.fakes, p.pages = Counter(), Counter()
            p.fakes[kind] += 1
            if hit.is_page:
                p.pages[hit.path[:200]] += 1
        if group in WATCHED:
            item = (status_class(hit.status), hit.path[:200], key)
            when = _utc(hit.when)
            self.bursts.add(hit.address, when, item)
            if hit.method == "POST" and N.LOGIN_PATH.search(hit.path):
                self.login.add(hit.address, when, item)

    def other_host(self, hit) -> None:
        """A line of a host the site does not list: only one sent to a bare IP
        counts here, and only towards Security (never a group)."""
        if not self._bare(hit.host):
            return
        key, p = self._pair(hit)
        self._referrer(hit, p)
        if PROBE.search(hit.path) or PROBE_QUERY.search(hit.url):
            self._probe(hit, key, p, True)

    # ------------------------------------------------------------ finish

    def _hosting(self, address: str):
        v = self.verifier
        if v is None or getattr(v, "hosting_set", None) is None:
            return None
        return bool(v.hosting(address))

    def finish(self) -> dict:
        rules = self.rules
        for p in self.pairs.values():
            p.login = p.burst = 0
        for runs, field in ((self.login, "login"), (self.bursts, "burst")):
            for _, ep in runs.episodes():
                for key, n in ep[5].items():
                    setattr(self.pairs[key], field, getattr(self.pairs[key], field) + n)
        suspects = [(k, p) for k, p in self.pairs.items() if p.suspect()]
        suspects.sort(key=lambda kp: (-kp[1].probes, -(kp[1].login + kp[1].burst),
                                      -kp[1].requests, _iso(kp[1].first), kp[0][0], kp[0][1]))
        kept = suspects[:N.WHO]
        seq = {k: i for i, (k, _) in enumerate(kept)}
        self.kept = [(i, k[0], k[1]) for i, (k, _) in enumerate(kept)]
        scanners = [(k, p) for k, p in self.pairs.items() if p.probes]
        cats, status, countries, paths = Counter(), Counter(), Counter(), Counter()
        hosting = 0 if self.verifier is not None and getattr(
            self.verifier, "hosting_set", None) is not None else None
        for (address, _), p in scanners:
            cats.update(p.cats)
            status.update(p.probe_status)
            countries[p.country or N.UNKNOWN] += p.probes
            paths.update(p.paths)
            if hosting is not None and self._hosting(address):
                hosting += p.probes
        forged = sum(1 for p in self.pairs.values() if p.suspect() and p.own_ref and not p.rendered)
        exposure = self._exposure(seq)
        fake, fake_pages, fake_pairs = Counter(), Counter(), 0
        for p in self.pairs.values():
            if p.fakes:
                fake.update(p.fakes)
                fake_pages.update(p.pages)
                fake_pairs += 1
        return {
            "rules": dict(rules, exposure_rule=N.EXPOSURE_RULE),
            "probes": self.probes, "probes_other": self.probes_other,
            "scanners": len(scanners), "addresses": len({k[0] for k, _ in scanners}),
            "requests": sum(p.requests for _, p in scanners),
            "categories": {k: int(v) for k, v in sorted(cats.items())},
            "status": {k: int(v) for k, v in sorted(status.items())},
            "countries": _top(countries, N.TOP_COUNTRIES),
            "hosting": hosting,
            "forged": forged,
            "bare_ip": self.probes_bare,
            "paths": _top(paths, N.TOP_PATHS),
            "exposure": exposure,
            "attacks": {"injection": self._injection(seq),
                        "login": self._episodes(self.login, seq, "posts"),
                        "bursts": self._episodes(self.bursts, seq, "requests")},
            "fake": {"requests": int(sum(fake.values())), "pairs": fake_pairs,
                     "kinds": {k: int(v) for k, v in sorted(fake.items())},
                     "pages": _top(fake_pages, N.FAKE_PAGES)},
            "signs": {"gateway": {"requests": int(sum(self.gateway.values())),
                                  "hours": dict(sorted(self.gateway.items()))},
                      "php": {"requests": int(sum(self.php.values())),
                              "hours": dict(sorted(self.php.items()))},
                      # None: no line of the day recorded request_length= (not recorded)
                      "posts": None if not self.posts["recorded"] else {
                          "recorded": self.posts["recorded"], "large": self.posts["large"],
                          "max": self.posts["max"],
                          "paths": _top(self.posts["paths"], N.SIGN_PATHS)}},
            "who": [self._row(i, k, p) for i, (k, p) in enumerate(kept)],
            "who_folded": len(suspects) - len(kept),
        }

    def _injection(self, seq: dict) -> dict:
        rows = [{"who": seq.get(key), "kind": kind, "requests": v[0], "first": _iso(v[1]),
                 "last": _iso(v[2]), "status": {k: int(n) for k, n in sorted(v[3].items())}}
                for (key, kind), v in self.inj.items()]
        rows.sort(key=lambda r: (-r["requests"], r["first"], r["kind"],
                                 -1 if r["who"] is None else r["who"]))
        kinds = Counter()
        for (_, kind), v in self.inj.items():
            kinds[kind] += v[0]
        return {"requests": int(sum(kinds.values())),
                "kinds": {k: int(v) for k, v in sorted(kinds.items())},
                "rows": rows[:N.EPISODES]}

    def _row(self, i: int, key: tuple, p: _Pair) -> dict:
        kinds = [k for k, on in (("scanner", p.probes), ("attack", p.login or p.burst),
                                 ("fake", p.fakes)) if on]
        fake = None
        if p.fakes:
            fake = sorted(p.fakes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        return {"seq": i, "kinds": kinds, "first": _iso(p.first), "last": _iso(p.last),
                "requests": p.requests, "probes": p.probes,
                "categories": {k: int(v) for k, v in sorted((p.cats or {}).items())},
                "status": {k: int(v) for k, v in sorted(p.status.items())},
                "probe_status": {k: int(v) for k, v in sorted((p.probe_status or {}).items())},
                "forged": bool(p.own_ref and not p.rendered),
                "bare_ip": p.bare_ip, "country": p.country or None,
                "hosting": self._hosting(key[0]),
                "fake": fake, "fake_requests": int(sum((p.fakes or {}).values())),
                "injection": p.injection, "login": p.login, "burst": p.burst,
                "paths": _top(p.paths or Counter(), N.ROW_PATHS) if p.paths else {},
                "pages": _top(p.pages or Counter(), N.ROW_PATHS) if p.pages else {}}

    def _episodes(self, runs: Runs, seq: dict, unit: str) -> dict:
        rows = []
        for _, ep in runs.episodes():
            rows.append({"start": _iso(ep[0]), "end": _iso(ep[1]), unit: ep[2],
                         "status": {k: int(v) for k, v in sorted(ep[3].items())},
                         "path": sorted(ep[4].items(), key=lambda kv: (-kv[1], kv[0]))[0][0],
                         "paths": len(ep[4]),
                         "who": sorted(seq[k] for k in ep[5] if k in seq)})
        rows.sort(key=lambda r: (-r[unit], r["start"], r["end"], r["path"], r["who"],
                                 sorted(r["status"].items())))
        return {unit: int(sum(r[unit] for r in rows)), "episodes": len(rows),
                "rows": rows[:N.EPISODES]}

    def _exposure(self, seq: dict) -> dict:
        tol, need = self.rules["tolerance"], self.rules["shell_paths"]

        def near(host: str, size: int) -> int:
            """Distinct probe paths of the host answered 2xx within the tolerance of `size`."""
            paths = set()
            for other, got in self.sizes.get(host, {}).items():
                if abs(other - size) <= tol:
                    paths |= got
            return len(paths)
        shells, fallbacks = {}, {}
        for host, by_size in self.sizes.items():
            # Every size shared by `shell_paths` probe paths is a fallback size (a host can
            # send its page compressed and not: 404 and 626 bytes); the one most paths share
            # (the smallest of a tie) is its main one. Listed once per tolerance.
            ranked = sorted(((near(host, s), s) for s in by_size), key=lambda c: (-c[0], c[1]))
            picked = []
            for n, s in ranked:
                if n >= need and all(abs(s - q) > tol for q, _ in picked):
                    picked.append((s, n))
            shells[host] = picked[0] if picked else None
            fallbacks[host] = sorted(s for s, _ in picked)
        hosts: dict[str, dict] = {}
        rows = []
        counts = Counter()
        for host, path, when, status, size, cat, key in self.answered:
            shell = shells.get(host)
            if size is None:
                verdict = "unknown"
            elif int(size) == 0:
                verdict = "empty"
            elif near(host, int(size)) >= need:
                verdict = "shell"
            else:
                verdict = "possible"
            counts[verdict] += 1
            h = hosts.setdefault(host, {"bare_ip": N.bare_ip(host),
                                        "shell_size": shell[0] if shell else None,
                                        "shell_paths": shell[1] if shell else 0,
                                        "shell_sizes": fallbacks.get(host, []),
                                        "answered": 0, "shell": 0, "empty": 0,
                                        "possible": 0, "unknown": 0})
            h["answered"] += 1
            h[verdict] += 1
            if verdict in ("possible", "unknown"):
                rows.append({"host": host, "path": path, "at": _iso(when), "status": status,
                             "size": None if size is None else int(size), "verdict": verdict,
                             "category": cat, "shell_size": shell[0] if shell else None,
                             "who": seq.get(key)})
        rows.sort(key=lambda r: (r["verdict"] != "possible", r["at"], r["host"], r["path"]))
        return {"answered": len(self.answered), "query_only": self.query_only,
                **{v: int(counts.get(v, 0)) for v in ("shell", "empty", "possible", "unknown")},
                "hosts": dict(sorted(hosts.items())), "rows": rows[:N.EXPOSURE_ROWS],
                "folded": max(0, len(rows) - N.EXPOSURE_ROWS)}


# ---------------------------------------------------- day_more registry

def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    got = getattr(extras, "security", None)
    if got is None:
        return None
    blob = got.finish()
    # The addresses behind the rows (seq, address, agent), memory only: kept by
    # security_kept.py while the site keeps addresses.
    totals.security_kept = got.kept
    return blob


def current(blob: dict | None) -> bool:
    """A day counted with today's exposure rule (alerts read nothing older)."""
    return bool(blob) and int(((blob.get("rules") or {}).get("exposure_rule")) or 1) >= \
        N.EXPOSURE_RULE


def _sum(d) -> int:
    return int(sum(int(v) for v in (d or {}).values()))


def check(totals, blob, differs, problems) -> None:
    """Every sum DATA-CONTRACT-SECURITY.md promises."""
    from .verify import Problem
    probes = int(blob["probes"])
    for part in ("categories", "status", "countries", "paths"):
        differs(f"security: probes by {part}", _sum(blob.get(part)), probes, "requests")
    bots = totals.groups.get(Group.BOTS)
    bad = []
    if probes - int(blob["probes_other"]) > (bots.hits if bots else 0):
        bad.append("more probes of the site's hosts than bot requests")
    if int(blob["requests"]) < probes:
        bad.append("scanners made fewer requests than probes")
    if int(blob["addresses"]) > int(blob["scanners"]):
        bad.append("more scanner addresses than scanners")
    ex = blob["exposure"]
    differs("security: probes answered 2xx", int(ex["answered"]) + int(ex.get("query_only") or 0),
            int((blob.get("status") or {}).get("2xx", 0)), "requests")
    differs("security: answered by verdict",
            sum(int(ex[v]) for v in ("shell", "empty", "possible", "unknown")),
            int(ex["answered"]), "requests")
    differs("security: answered by host",
            sum(int(h["answered"]) for h in (ex.get("hosts") or {}).values()),
            int(ex["answered"]), "requests")
    differs("security: possible and unknown answers listed",
            len(ex.get("rows") or []) + int(ex.get("folded") or 0),
            int(ex["possible"]) + int(ex["unknown"]), "requests")
    inj = blob["attacks"]["injection"]
    differs("security: injection by kind", _sum(inj.get("kinds")), int(inj["requests"]),
            "requests")
    differs("security: injection probes", int(inj["requests"]),
            int((blob.get("categories") or {}).get("injection", 0)), "requests")
    for name, unit in (("login", "posts"), ("bursts", "requests")):
        part = blob["attacks"][name]
        rows = part.get("rows") or []
        if sum(int(r[unit]) for r in rows) > int(part[unit]) or len(rows) > int(part["episodes"]):
            bad.append(f"{name}: listed episodes larger than the total")
        if len(rows) == int(part["episodes"]):
            differs(f"security: {name} by episode", sum(int(r[unit]) for r in rows),
                    int(part[unit]), unit)
    fake = blob["fake"]
    differs("security: fake browsers by kind", _sum(fake.get("kinds")), int(fake["requests"]),
            "requests")
    if _sum(fake.get("pages")) > int(fake["requests"]):
        bad.append("fake browsers took more pages than they made requests")
    signs = blob.get("signs") or {}
    for part in ("gateway", "php"):
        if signs.get(part) is not None:
            differs(f"security: {part} by hour", _sum(signs[part]["hours"]),
                    int(signs[part]["requests"]), "requests")
    posts = signs.get("posts")
    if posts is not None:
        differs("security: large POSTs by path", _sum(posts["paths"]), int(posts["large"]),
                "requests")
        if int(posts["large"]) > int(posts["recorded"]):
            bad.append("more large POSTs than POSTs with a recorded size")
    lines = getattr(totals, "parsed", None)
    if lines is not None and signs.get("gateway") is not None and \
            int(signs["gateway"]["requests"]) + int((signs.get("php") or {}).get("requests") or 0) \
            > 2 * int(lines):
        bad.append("more gateway errors or .php requests than lines")
    who = blob.get("who") or []
    if [r["seq"] for r in who] != list(range(len(who))):
        bad.append("suspect rows out of sequence")
    if sum(int(r["probes"]) for r in who) > probes:
        bad.append("suspect rows hold more probes than the day")
    for r in who:
        if _sum(r.get("categories")) != int(r["probes"]) or \
                _sum(r.get("probe_status")) != int(r["probes"]) or \
                _sum(r.get("status")) != int(r["requests"]):
            bad.append(f"suspect row {r['seq']}: its parts do not add up")
            break
    for why in bad:
        problems.append(Problem("security", why))

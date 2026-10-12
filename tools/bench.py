#!/usr/bin/env python3
"""Time Skald's hot paths on synthetic histories of three sizes.

    python3 tools/bench.py                      # 1x and 10x (a few minutes)
    python3 tools/bench.py --scale 1x           # one size only
    python3 tools/bench.py --scale 100x         # the large one (slow to build)
    python3 tools/bench.py --json out.json      # also save the timings
    python3 tools/bench.py --against before.json   # print before | after
    python3 tools/bench.py --keep DIR           # build in DIR and leave it there

Each size is built in a temporary folder with the real pipeline: the last
7 days of every site are synthetic logs collected by `skald collect`, the
older days are copies of those rows on other dates (tools/bench_data.py),
and today has a log up to noon for `live`. Then it times:

  live            `skald live` (the snapshot and the dashboard redraw, every site)
  dashboard       `skald dashboard` (every data file, every site)
  audit --live    the second count of today so far
  backup          `skald backup` (history, accounts and conversions, restore-tested)
  api ...         HTTP requests to the refresh helper in sessions mode, with a
                  signed-in cookie: a data file (overview), compare over 90 and 400
                  days (cold: the parsed-blob cache emptied; warm: asked again),
                  a page's story, the sites list, and nginx's auth check
  session check   access.session_caller alone (what every gated request pays)
  mcp ...         MCP tools through the protocol handler
  conversions     conversions.json's body (conversions_data.blob)

Sizes (requests/day per site, days, sites, distinct pages):
  1x    10,000 x 60 days x 1 site, 60 pages   - about the first live install
  10x   10,000 x 300 days x 2 sites, 200 pages (10x the site-days, more visits)
  100x  20,000 x 400 days x 8 sites, 600 pages (about 100x the requests)
Times are seconds (wall clock) on this machine; the median of the repeats.
Nothing here is a secret: documentation addresses, example.com, a dummy key.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shutil
import statistics
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_data as bd  # noqa: E402

SCALES = {
    "1x": {"sites": 1, "days": 60, "lines": 10_000, "pages": 60, "people": 0.006,
           "users": 5, "conversions": 10},
    "10x": {"sites": 2, "days": 300, "lines": 10_000, "pages": 200, "people": 0.012,
            "users": 50, "conversions": 50},
    "100x": {"sites": 8, "days": 400, "lines": 20_000, "pages": 600, "people": 0.03,
             "users": 500, "conversions": 200},
}
TODAY = date(2026, 10, 12)
TEMPLATES = 7
TZ_NAME = "America/New_York"
# A made-up visitor key, so returning visitors are counted: not a secret.
DUMMY_KEY = "bench-only-dummy-visitor-key"


def site_names(n: int) -> list[str]:
    return ["example.com"] + [f"site{i}.example.com" for i in range(2, n + 1)]


def config_text(root: Path, sites: list[str]) -> str:
    text = (
        "site:\n  name: example.com\n  hosts: [example.com]\n"
        f"logs:\n  dir: {root / 'logs' / 'example.com'}\n  base: access.log\n  days: 2\n"
        "  format: auto\n"
        "ours:\n  user_agents:\n    - {agent: skald-heartbeat, label: heartbeat}\n"
        f"report:\n  session_gap_minutes: 30\n  timezone: {TZ_NAME}\n"
        "  retention_days: 400\n  journey_days: 7\n  heartbeat_label: heartbeat\n"
        "history:\n  db: history.sqlite\n"
        "dashboard:\n  out: www\n  app: true\n"
        "  url: https://stats.example.com/traffic/example.com/\n"
        "  views:\n"
        "    - {name: US English, exclude_prefix: /ca/}\n"
        "    - {name: Canada English, path_prefix: /ca/, exclude_prefix: /ca/fr/}\n"
        "    - {name: Canada French, path_prefix: /ca/fr/}\n"
        "access:\n  mode: sessions\n  base_url: https://stats.example.com\n"
        "mcp:\n  enabled: true\n"
    )
    if len(sites) > 1:
        text += "sites:\n" + "".join(f"  - sites/{s}.yml\n" for s in sites[1:])
    return text


def site_text(root: Path, name: str) -> str:
    return (f"site:\n  name: {name}\n  hosts: [{name}]\n"
            f"logs:\n  dir: {root / 'logs' / name}\n  base: access.log\n  days: 2\n"
            "  format: auto\n")


def quiet(fn, *args, **kw):
    """fn's result, its prints swallowed."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kw)


def cli(cfg: Path, *argv: str) -> int:
    from skald import cli as ti
    return quiet(ti.main, ["--config", str(cfg), "--today", TODAY.isoformat(), *argv])


# ------------------------------------------------------------------ build

def build(root: Path, spec: dict, say=print) -> dict:
    """The install for one size, in `root`. Returns what the timings need."""
    os.environ["SKALD_VISITOR_KEY"] = DUMMY_KEY
    tz = ZoneInfo(TZ_NAME)
    sites = site_names(spec["sites"])
    (root / "sites").mkdir(parents=True, exist_ok=True)
    (root / "templates").mkdir(exist_ok=True)
    cfg = root / "config.yml"
    cfg.write_text(config_text(root, sites))
    for name in sites[1:]:
        (root / "sites" / f"{name}.yml").write_text(site_text(root, name))
    paths = bd.pages(spec["pages"])
    yesterday = TODAY - timedelta(days=1)
    first = TODAY - timedelta(days=spec["days"])
    templates = [yesterday - timedelta(days=TEMPLATES - 1 - i) for i in range(TEMPLATES)]
    started = time.perf_counter()
    db = root / "history.sqlite"
    _accounts(root, sites, spec["users"])
    # The last TEMPLATES days of every site through the real pipeline; the
    # older days are copies of them; then the newest is collected once more,
    # which prunes what is kept only for a while, as on a server.
    for k, name in enumerate(sites):
        logs = root / "logs" / name
        logs.mkdir(parents=True, exist_ok=True)
        for i, day in enumerate(templates):
            lines = bd.day_lines(day, tz, spec["lines"], paths, seed=1000 * k + i,
                                 people=spec["people"], host=name)
            log = root / "templates" / f"{name}-{day}.log"
            log.write_text("".join(lines))
            if cli(cfg, "--site", name, "collect", "--day", day.isoformat(),
                   "--log", str(log)) != 0:
                raise SystemExit(f"collect {name} {day} failed")
        plan, d = [], first
        while d < templates[0]:
            plan.append((templates[(d - first).days % TEMPLATES].isoformat(), name,
                         d.isoformat()))
            d += timedelta(days=1)
        bd.clone_days(db, name, plan)
        day = templates[-1]
        cli(cfg, "--site", name, "collect", "--day", day.isoformat(),
            "--log", str(root / "templates" / f"{name}-{day}.log"))
        midnight = datetime.combine(TODAY, datetime.min.time(), tzinfo=tz)
        today = bd.day_lines(TODAY, tz, spec["lines"], paths, seed=1000 * k + 99,
                             until=midnight + timedelta(hours=12), people=spec["people"],
                             host=name)
        (logs / "access.log").write_text("".join(today))
    bd.fill_conversions(root / "conversions.sqlite", sites, TODAY - timedelta(days=89),
                        TODAY, spec["conversions"])
    built = time.perf_counter() - started
    size = db.stat().st_size
    say(f"  built in {built:.0f} s: history {size / 1e6:.1f} MB, {len(sites)} site(s), "
        f"{spec['days']} days")
    return {"cfg": cfg, "sites": sites, "paths": paths, "db": db,
            "cookie": (root / ".cookie").read_text(), "history_mb": round(size / 1e6, 1)}


def _accounts(root: Path, sites: list[str], users: int) -> None:
    from skald import accounts
    db = accounts.connect(root / "accounts.sqlite")
    try:
        org = accounts.create_org(db, "Bench", "bench")
        owner = accounts.create_user(db, "owner@example.com", "Owner", install_admin=True)
        accounts.add_member(db, org["id"], owner["id"], "owner", "bench")
        for s in sites:
            accounts.assign_site(db, s, org["id"], "bench")
        for i in range(users):
            other = accounts.create_org(db, f"Other {i}", "bench")
            u = accounts.create_user(db, f"user{i}@example.com", f"User {i}")
            accounts.add_member(db, other["id"], u["id"], "owner", "bench")
            accounts.add_member(db, org["id"], u["id"], "viewer", "bench")
            accounts.sessions.start(db, u["id"], "192.0.2.1", "bench")
        cookie, _ = accounts.sessions.start(db, owner["id"], "192.0.2.1", "bench")
    finally:
        db.close()
    (root / ".cookie").write_text(cookie)


# ------------------------------------------------------------------ timing

def timed(fn, repeat: int = 1) -> float:
    got = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        got.append(time.perf_counter() - t)
    return statistics.median(got)


class Helper:
    """The refresh helper on a free local port, in this process."""

    def __init__(self, cfg: Path, root: Path) -> None:
        from skald import refresh_server as rs
        from skald.config import load_config
        config = load_config(cfg)
        db = root / "history.sqlite"
        config.setdefault("_resolved", {"history_db": str(db), "live_dir": str(root)})
        runner = rs.Runner(["true"], root)
        handler = rs.make_handler(runner, set(), config, root / "www", root, db, cfg)
        self.server = rs.HelperServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def get(self, path: str, headers: dict) -> int:
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers=headers)
        try:
            with urllib.request.urlopen(req) as r:
                r.read()
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def measure(root: Path, got: dict, say=print) -> dict[str, float]:
    cfg, site = got["cfg"], got["sites"][0]
    out: dict[str, float] = {}

    def run(label, fn, repeat=1):
        out[label] = timed(fn, repeat)
        say(f"  {label:<28} {out[label]:8.3f} s")

    run("live", lambda: cli(cfg, "live"))
    run("dashboard", lambda: cli(cfg, "dashboard"))
    run("audit --live", lambda: cli(cfg, "audit", "--live"))
    run("backup", lambda: cli(cfg, "backup", "--dir", str(root / "backups")))
    _api(root, got, run)
    _mcp(root, got, run)
    from skald import conversions_data
    from skald.config import load_config
    from skald.store import History
    config = load_config(cfg)
    tz = ZoneInfo(TZ_NAME)

    def conv():
        with History.reader(got["db"]) as h:
            conversions_data.blob(config, root, site, tz, TODAY,
                                  datetime.combine(TODAY, datetime.min.time(), tzinfo=tz)
                                  + timedelta(hours=12), history=h)
    run("conversions.json body", conv, 3)
    return out


def _api(root: Path, got: dict, run) -> None:
    from skald import access, compare
    from skald.config import load_config
    site = got["sites"][0]
    cookie = {"Cookie": f"skald_session={got['cookie']}"}
    helper = Helper(got["cfg"], root)
    a90 = f"{TODAY - timedelta(days=90)}..{TODAY - timedelta(days=1)}"
    b90 = f"{TODAY - timedelta(days=180)}..{TODAY - timedelta(days=91)}"
    a400 = f"{TODAY - timedelta(days=400)}..{TODAY - timedelta(days=1)}"
    b400 = f"{TODAY - timedelta(days=800)}..{TODAY - timedelta(days=401)}"
    page = got["paths"][6]

    def ask(path, want=200):
        code = helper.get(path, cookie)
        if code != want:
            raise SystemExit(f"{path}: HTTP {code}")

    def cold(path):
        def go():
            compare._CACHE.clear()
            ask(path)
        return go
    try:
        base = f"/traffic/{site}/"
        run("api overview (data file)", lambda: ask(base + "api/v1/overview"), 9)
        run("api compare 90 d, cold", cold(f"{base}api/compare?a={a90}&b={b90}"), 3)
        run("api compare 90 d, warm", lambda: ask(f"{base}api/compare?a={a90}&b={b90}"), 3)
        run("api compare 400 d, cold", cold(f"{base}api/compare?a={a400}&b={b400}"), 3)
        run("api compare 400 d, warm", lambda: ask(f"{base}api/compare?a={a400}&b={b400}"), 3)
        run("api page story", lambda: ask(f"{base}api/page?path={page}"), 3)
        run("api sites list", lambda: ask("/traffic/sites.json"), 9)
        check = {**cookie, "X-Original-URI": base + "data/overview.json",
                 "X-Original-Path": base + "data/overview.json"}
        run("api auth check (nginx)", lambda: helper.get("/traffic-auth/check", check), 9)
    finally:
        helper.close()
    config = load_config(got["cfg"])
    run("session check (no HTTP)",
        lambda: access.session_caller(config, root, cookie, site), 21)


def _mcp(root: Path, got: dict, run) -> None:
    from skald.config import load_config
    from skald.mcp import protocol
    from skald.mcp.data import Context
    site = got["sites"][0]
    config = load_config(got["cfg"])
    ctx = Context(root / "www", config=config, live_dir=root, history_path=got["db"],
                  default_site=site)
    first = (TODAY - timedelta(days=30)).isoformat()
    last = (TODAY - timedelta(days=1)).isoformat()
    calls = {
        "list_sites": {}, "overview": {"from": first, "to": last},
        "breakdown": {"dimension": "source"}, "top_pages": {}, "ai_activity": {},
        "compare": {"a_from": first, "a_to": last,
                    "b_from": (TODAY - timedelta(days=60)).isoformat(),
                    "b_to": (TODAY - timedelta(days=31)).isoformat()},
        "page_story": {"path": got["paths"][6]}, "site_health": {}, "data_quality": {},
        "conversions": {}}

    def call(name, args):
        def go():
            res = protocol.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                   "params": {"name": name, "arguments": args}}, ctx)
            if "error" in res:
                raise SystemExit(f"mcp {name}: {res['error']}")
        return go
    for name, args in calls.items():
        run(f"mcp {name}", call(name, args), 3)


# ------------------------------------------------------------------ report

def table(results: dict, against: dict | None) -> str:
    scales = list(results)
    labels = []
    for s in scales:
        for k in results[s]["times"]:
            if k not in labels:
                labels.append(k)
    head = ["operation"]
    for s in scales:
        head += [f"{s} before", f"{s} after"] if against else [s]
    rows = [head]
    for k in labels:
        row = [k]
        for s in scales:
            now = results[s]["times"].get(k)
            if against:
                was = ((against.get(s) or {}).get("times") or {}).get(k)
                row.append(_fmt(was))
            row.append(_fmt(now))
        rows.append(row)
    widths = [max(len(r[i]) for r in rows) for i in range(len(head))]
    lines = ["| " + " | ".join(c.ljust(w) for c, w in zip(r, widths)) + " |" for r in rows]
    lines.insert(1, "|" + "|".join("-" * (w + 2) for w in widths) + "|")
    return "\n".join(lines)


def _fmt(v) -> str:
    if v is None:
        return "-"
    if v < 0.01:
        return f"{v * 1000:.1f} ms"
    return f"{v * 1000:.0f} ms" if v < 1 else f"{v:.2f} s"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scale", action="append", choices=list(SCALES),
                    help="a size to run (repeatable; default 1x and 10x)")
    ap.add_argument("--json", metavar="FILE", help="save the timings here")
    ap.add_argument("--against", metavar="FILE", help="earlier timings, shown beside")
    ap.add_argument("--keep", metavar="DIR", help="build in DIR and keep it")
    a = ap.parse_args(argv)
    results = {}
    for scale in a.scale or ["1x", "10x"]:
        print(f"{scale}:")
        if a.keep:
            root = Path(a.keep) / scale
            if root.exists():
                shutil.rmtree(root)
            root.mkdir(parents=True)
            tmp = None
        else:
            tmp = tempfile.TemporaryDirectory(prefix=f"skald-bench-{scale}-")
            root = Path(tmp.name)
        try:
            got = build(root, SCALES[scale])
            results[scale] = {"spec": SCALES[scale], "history_mb": got["history_mb"],
                              "times": measure(root, got)}
        finally:
            if tmp is not None:
                tmp.cleanup()
    against = json.loads(Path(a.against).read_text()) if a.against else None
    print()
    print(table(results, against))
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

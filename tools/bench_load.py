#!/usr/bin/env python3
"""How fast the dashboard opens: bytes, requests and time to the key figures.

    python3 tools/bench_load.py --keep DIR             # build the sample in DIR, then measure
    python3 tools/bench_load.py --keep DIR --reuse     # measure again on the same sample
    python3 tools/bench_load.py ... --json after.json --against before.json

It builds a large sample install with tools/bench.py's real pipeline (two sites,
120 days, 3,000 pages, a few thousand lost addresses; example.com hosts and RFC 5737
addresses only), writes its dashboard files, then serves them the way the Docker
image does: this checkout's docker/nginx.conf on a local nginx, the refresh helper
behind it (sessions mode, so every file goes through the auth check), and a TLS +
HTTP/2 nginx in front of it, like the host nginx on a real server.

A headless Chromium (Playwright; PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs,
as the e2e tests) opens the Overview signed in, over a throttled line (2.5 MB/s down,
40 ms round trip: about the owner's connection on 2026-10-26), three times:

  cold     a new browser profile, empty cache
  warm     the same page again (reload, cache kept)
  switch   the second site, cache kept

For each it reports the requests that went to the network (a 304 counts; a file
the cache served without asking does not), the bytes received (headers and
compressed bodies, as on the wire) and the time from navigation to the key
figures being on screen, and to the network falling quiet.

Needs nginx (with auth_request, gzip_static, http_v2, ssl), openssl and node.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import ssl
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench  # noqa: E402
import bench_data as bd  # noqa: E402

SPEC = {"sites": 2, "days": 120, "lines": 12_000, "pages": 3000, "people": 0.008,
        "users": 2, "conversions": 20}
LOST_PER_DAY = 2500       # 404 lines a day beyond bench_data's own
LOST_POOL = 6000          # distinct lost addresses they are drawn from
MIME = Path("/opt/homebrew/etc/nginx/mime.types")


def lost_lines(day, tz, seed: int, host: str, until=None) -> list[str]:
    """404s for addresses that were moved or never existed: search crawlers,
    people, AI crawlers and bots, from a pool of LOST_POOL paths."""
    rng = random.Random(seed * 7 + 1)
    start = datetime.combine(day, datetime.min.time(), tzinfo=tz)
    out = []
    for _ in range(LOST_PER_DAY):
        when = start + timedelta(seconds=rng.randint(0, 86399))
        if until is not None and when >= until:
            continue
        n = int(rng.paretovariate(0.9)) % LOST_POOL
        path = (f"/old-blog/{n}-a-post-that-moved/", f"/guides/retired-{n}/",
                f"/wp-content/uploads/2019/{n % 12 + 1:02d}/img-{n}.jpg")[n % 3]
        kind = rng.random()
        if kind < 0.45:
            agent, ref = rng.choice(bd.SEARCH), "-"
        elif kind < 0.65:
            agent, ref = rng.choice(bd.BROWSERS), f"https://www.google.com/"
        elif kind < 0.8:
            agent, ref = rng.choice(bd.TRAINING), "-"
        else:
            agent, ref = rng.choice(bd.BOTS), "-"
        out.append(bd.log_line(when, bd.address(rng), path, agent, ref, status=404,
                               host=host))
    return out


def patch_lost() -> None:
    """bench_data.day_lines with the lost addresses mixed in, in time order."""
    orig = bd.day_lines

    def day_lines(day, tz, n, paths, seed, until=None, people=0.02, host="example.com"):
        got = orig(day, tz, n, paths, seed, until=until, people=people, host=host)
        got += lost_lines(day, tz, seed, host, until)
        got.sort(key=lambda line: line.split(" ", 1)[0])
        return got
    bd.day_lines = day_lines


def build(root: Path) -> dict:
    patch_lost()
    got = bench.build(root, SPEC)
    for args in (("dashboard",), ("live",)):
        code = bench.cli(got["cfg"], *args)
        if code not in (0, 1):
            raise SystemExit(f"skald {' '.join(args)} failed ({code})")
    meta = {"sites": got["sites"], "cookie": got["cookie"]}
    (root / "bench-load.json").write_text(json.dumps(meta))
    return meta


def redraw(root: Path) -> None:
    """Write the dashboard files again with this checkout's code (a reused sample)."""
    cfg = root / "config.yml"
    os.environ["SKALD_VISITOR_KEY"] = bench.DUMMY_KEY
    for args in (("dashboard",), ("live",)):
        code = bench.cli(cfg, *args)
        if code not in (0, 1):
            raise SystemExit(f"skald {' '.join(args)} failed ({code})")
    if os.environ.get("BENCH_PRELOAD") == "off":      # an experiment: the shell without modulepreload
        for shell in (root / "www").glob("*/index.html"):
            shell.write_text("".join(line for line in shell.read_text().splitlines(True)
                                     if 'rel="modulepreload"' not in line))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def nginx_conf(run: Path, www: Path, port: int, helper: int, front: int) -> Path:
    """docker/nginx.conf as the image runs it, on local ports and folders, with a
    TLS + HTTP/2 front server like the host's."""
    text = (ROOT / "docker" / "nginx.conf").read_text()
    text = text.replace("/etc/nginx/mime.types", str(MIME))
    text = text.replace("/var/www/skald/", f"{www}/")
    text = text.replace("server 127.0.0.1:8765;", f"server 127.0.0.1:{helper};")
    text = text.replace("/var/log/nginx/skald-beacon.log", str(run / "beacon.log"))
    text = text.replace("/tmp/skald-nginx", str(run))
    (run / "listen.conf").write_text(f"listen 127.0.0.1:{port};\n")
    (run / "trusted.conf").write_text("")
    front_block = f"""
    server {{
        listen 127.0.0.1:{front} ssl;
        http2 on;
        ssl_certificate {run}/cert.pem;
        ssl_certificate_key {run}/key.pem;
        gzip on;
        location / {{
            proxy_pass http://127.0.0.1:{port};
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}
    }}
"""
    if os.environ.get("BENCH_CODE_AUTH") == "off":      # an experiment: no session check on the code
        text = text.replace("        location ~ ^/traffic/(?:index\\.html)?$ {",
                            "        location ^~ /traffic/_app/ { auth_request off; }\n"
                            "        location ~ ^/traffic/(?:index\\.html)?$ {", 1)
        assert "auth_request off" in text
    text = text.rstrip()
    assert text.endswith("}")
    text = text[:-1] + front_block + "}\n"
    conf = run / "nginx.conf"
    conf.write_text(text)
    return conf


class Served:
    """The helper and nginx for one sample, stopped on exit."""

    def __init__(self, root: Path) -> None:
        self.run = Path(tempfile.mkdtemp(prefix="skald-load-"))
        for sub in ("body", "proxy", "fastcgi", "uwsgi", "scgi"):
            (self.run / sub).mkdir()
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=127.0.0.1", "-keyout", str(self.run / "key.pem"),
                        "-out", str(self.run / "cert.pem")], check=True, capture_output=True)
        # The browser trusts this certificate by its key (--ignore-certificate-errors-spki-list):
        # Chromium keeps nothing in its cache from a host whose certificate is in error.
        pub = subprocess.run(["openssl", "x509", "-in", str(self.run / "cert.pem"), "-pubkey",
                              "-noout"], check=True, capture_output=True).stdout
        der = subprocess.run(["openssl", "pkey", "-pubin", "-outform", "der"], input=pub,
                             check=True, capture_output=True).stdout
        self.spki = base64.b64encode(hashlib.sha256(der).digest()).decode()
        self.helper_port, self.port, self.front = free_port(), free_port(), free_port()
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        self.helper = subprocess.Popen(
            [sys.executable, "-m", "skald.refresh_server", "--config",
             str(root / "config.yml"), "--port", str(self.helper_port)],
            cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        conf = nginx_conf(self.run, root / "www", self.port, self.helper_port, self.front)
        test = subprocess.run(["nginx", "-t", "-p", str(self.run), "-c", str(conf)],
                              capture_output=True, text=True)
        if test.returncode != 0:
            self.close()
            raise SystemExit(f"nginx -t failed:\n{test.stderr}")
        self.nginx = subprocess.Popen(["nginx", "-p", str(self.run), "-c", str(conf),
                                       "-g", "daemon off;"], stderr=subprocess.DEVNULL)
        self._wait()

    def _wait(self) -> None:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        for _ in range(100):
            try:
                urllib.request.urlopen(f"https://127.0.0.1:{self.front}/traffic-auth/login",
                                       context=ctx, timeout=2).read()
                return
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.1)
        raise SystemExit("the local nginx or helper did not come up")

    @property
    def base(self) -> str:
        return f"https://127.0.0.1:{self.front}"

    def close(self) -> None:
        for proc in (getattr(self, "nginx", None), getattr(self, "helper", None)):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        shutil.rmtree(self.run, ignore_errors=True)


def browse(served: Served, meta: dict, repeat: int, latency: int = 40) -> dict:
    script = Path(__file__).resolve().parent / "bench_load.mjs"
    args = ["node", str(script), served.base, meta["cookie"], *meta["sites"][:2],
            "--repeat", str(repeat), "--spki", served.spki, "--latency", str(latency)]
    got = subprocess.run(args, capture_output=True, text=True, timeout=900)
    if got.returncode != 0:
        raise SystemExit(f"bench_load.mjs failed:\n{got.stdout}\n{got.stderr}")
    return json.loads(got.stdout.strip().splitlines()[-1])


def sizes(root: Path, site: str) -> dict[str, int]:
    data = root / "www" / site / "data"
    return {p.name: p.stat().st_size for p in sorted(data.glob("*.json"))}


def table(now: dict, was: dict | None) -> str:
    # ready: the Overview over 30 days with its page cards drawn (period), Traffic > Pages
    # with its leaderboard drawn (pages); the first three loads have no such step.
    rows = [["load", "requests", "bytes", "key figures", "ready", "quiet"]]
    if was:
        rows[0] = ["load", "requests before", "after", "bytes before", "after",
                   "key figures before", "after", "ready before", "after", "quiet before", "after"]
    for k in ("cold", "warm", "switch", "period", "pages"):
        n = now.get(k)
        if n is None:
            continue
        if was:
            b = was.get(k) or {"requests": "-", "bytes": None, "kpis_ms": None, "quiet_ms": None}
            rows.append([k, str(b["requests"]), str(n["requests"]), mb(b["bytes"]), mb(n["bytes"]),
                         sec(b["kpis_ms"]), sec(n["kpis_ms"]), sec(b.get("ready_ms")),
                         sec(n.get("ready_ms")), sec(b["quiet_ms"]), sec(n["quiet_ms"])])
        else:
            rows.append([k, str(n["requests"]), mb(n["bytes"]), sec(n["kpis_ms"]),
                         sec(n.get("ready_ms")), sec(n["quiet_ms"])])
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    out = ["| " + " | ".join(c.ljust(w) for c, w in zip(r, widths)) + " |" for r in rows]
    out.insert(1, "|" + "|".join("-" * (w + 2) for w in widths) + "|")
    return "\n".join(out)


def mb(n) -> str:
    if n is None:
        return "-"
    return f"{n / 1e6:.2f} MB" if n >= 1e5 else f"{n / 1e3:.0f} kB"


def sec(ms) -> str:
    return "-" if ms is None else f"{ms / 1000:.2f} s"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", metavar="DIR", required=True, help="the sample's folder")
    ap.add_argument("--reuse", action="store_true",
                    help="measure the sample already in DIR (its files redrawn with this code)")
    ap.add_argument("--repeat", type=int, default=3, help="runs of each load (median)")
    ap.add_argument("--latency", type=int, default=40, metavar="MS",
                    help="the line's round trip (40: the owner's line on 2026-10-26)")
    ap.add_argument("--json", metavar="FILE", help="save the result here")
    ap.add_argument("--against", metavar="FILE", help="an earlier result, shown beside")
    ap.add_argument("--serve", action="store_true",
                    help="only serve the sample (prints the address and cookie) until Ctrl-C")
    a = ap.parse_args(argv)
    root = Path(a.keep)
    if a.reuse and (root / "bench-load.json").exists():
        meta = json.loads((root / "bench-load.json").read_text())
        redraw(root)
    else:
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        meta = build(root)
    files = sizes(root, meta["sites"][0])
    print(f"{meta['sites'][0]} data files: {len(files)}, {mb(sum(files.values()))} on disk; "
          + ", ".join(f"{k} {mb(v)}" for k, v in sorted(files.items(), key=lambda x: -x[1])[:5]))
    served = Served(root)
    if a.serve:
        print(f"{served.base}/traffic/{meta['sites'][0]}/  cookie skald_session={meta['cookie']}"
              f"  spki {served.spki}", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0
        finally:
            served.close()
    try:
        result = browse(served, meta, a.repeat, a.latency)
    finally:
        served.close()
    result["files"] = files
    was = json.loads(Path(a.against).read_text()) if a.against else None
    print(table(result, was))
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

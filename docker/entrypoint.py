#!/usr/bin/env python3
"""The Docker image's entrypoint: one container, four processes, one port.

    serve (default)   nginx on SKALD_PORT (8080), the refresh helper on
                      127.0.0.1:8765, the beacon helper on 127.0.0.1:8766 (always:
                      it receives the signed tool hooks; the script tag and
                      /traffic-beacon only with SKALD_BEACON_ORIGINS), and docker/scheduler.py (live, run-daily,
                      backup). Each is restarted when it stops; SIGTERM stops all.
    health            the HEALTHCHECK: the sign-in page answers through nginx and
                      the helper, and the scheduler wrote its heartbeat lately.
    config            print the config file in use (the generated one, or yours).
    peers             the addresses connected to SKALD_PORT now: the platform's
                      proxy, to put in SKALD_TRUSTED_PROXIES (docs/HOSTING.md).
    sh | bash         a shell.
    anything else     skald --config <config> <arguments>, e.g.
                      `accounts init --org "Example Co" --owner-email owner@example.com`.

The config: /etc/skald/config.yml when you mount one, else
/var/lib/skald/config.yml, written at every start from the SKALD_*
environment (docs/INSTALL.md lists them). Secrets never go in it: SMTP_USER and
SMTP_PASSWORD stay in the environment, and the visitor key is made once into
/var/lib/skald/env (0600). Standard library only.

Started as root (the image's default), it first gives the data disk to the
image's user (uid 10001) when a platform mounted it for root (Railway, Fly,
Render), then drops to that user for good, before every command. Started as
uid 10001 (Kubernetes runAsUser, docker --user), it changes nothing.
"""
from __future__ import annotations

import ipaddress
import json
import os
import pwd
import re
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

APP = Path(os.environ.get("SKALD_APP", "/opt/skald"))
DATA = Path(os.environ.get("SKALD_DATA", "/var/lib/skald"))
MOUNTED_CONFIG = Path("/etc/skald/config.yml")
GENERATED_CONFIG = DATA / "config.yml"
RANGES = DATA / "ranges"             # bots.ranges_dir: the crawler owners' address lists
VERIFY_OFF = ("0", "false", "off", "no")
ENV_FILES = (Path("/etc/skald/env"), DATA / "env")
RUN = Path("/tmp/skald-nginx")
BEAT = Path("/tmp/skald-scheduler.beat")
DASHBOARD = Path("/var/www/skald")
PRIVATE = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
APP_USER, APP_ID = "skald", 10001
REAL_IP_HEADER = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,63}$")
SITE_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]{0,252}$")
TIME_ZONE = re.compile(r"^[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)*$")
# The image a site's shipper kit runs (Settings > Connections, skald/kit):
# this image, at its major version, unless SKALD_KIT_IMAGE or ingest.kit_image names another.
KIT_IMAGE = "ghcr.io/spcaeo/skald"


def log(msg: str) -> None:
    print(f"skald: {msg}", flush=True)


# ------------------------------------------------------------------ config

def _words(value: str | None) -> list[str]:
    return [w for w in re.split(r"[\s,]+", value or "") if w]


def _origin(url: str) -> str | None:
    m = re.match(r"^(https?://[^/?#]+)", url.strip())
    return m.group(1) if m else None


def render_config(env: dict) -> dict:
    """The config the container runs with, from the SKALD_* environment.

    Sessions mode (accounts) is on: nginx in the image is set up for it. The
    mails are off until an SMTP host is given (here, or in Settings > Mail),
    so a fresh container never fails its daily run for want of a mail server.
    """
    site = (env.get("SKALD_SITE") or "site").strip().lower()
    if not SITE_NAME.match(site):
        raise SystemExit(f"SKALD_SITE {site!r}: use a host name such as example.com")
    tz = (env.get("SKALD_TIMEZONE") or env.get("TZ") or "UTC").strip()
    if not TIME_ZONE.match(tz):
        raise SystemExit(f"SKALD_TIMEZONE {tz!r} is not a time zone name")
    base = (env.get("SKALD_BASE_URL") or "http://localhost:8080").strip().rstrip("/")
    if not _origin(base):
        raise SystemExit(f"SKALD_BASE_URL {base!r}: give an http(s) address")
    config: dict = {
        "site": {"name": site, "hosts": _words(env.get("SKALD_HOSTS"))},
        "logs": {"dir": env.get("SKALD_LOG_DIR") or "/logs",
                 "base": env.get("SKALD_LOG_FILE") or "access.log",
                 "format": env.get("SKALD_LOG_FORMAT") or "auto"},
        "report": {"timezone": tz, "env_file": str(DATA / "env")},
        "history": {"db": str(DATA / "history.sqlite")},
        # app: the dashboard web app (menu, tabs, drawers). Without it only the
        # plain fallback page (classic.html) is written, as the site's page.
        "dashboard": {"out": str(DASHBOARD), "url": f"{base}/traffic/{site}/",
                      "app": True, "refresh_button": True},
        "backup": {"dir": str(DATA / "backups")},
        "access": {"mode": "sessions", "base_url": base},
    }
    if env.get("SKALD_COUNTRY_DB"):
        # A GeoIP .mmdb (DB-IP's free country file): a line with no country
        # of its own gets its address's, and so does a lead hook's ip.
        config["logs"]["country_db"] = env["SKALD_COUNTRY_DB"].strip()
    if (env.get("SKALD_CITY_DB") or "").strip():
        # A GeoIP city .mmdb (DB-IP's free "IP to City Lite"): each visit's
        # city, readers by city, and the cities on the real-time map.
        config["logs"]["city_db"] = env["SKALD_CITY_DB"].strip()
    if env.get("SKALD_ASSET_PREFIXES"):
        config["site"]["asset_prefixes"] = _words(env["SKALD_ASSET_PREFIXES"])
    to = _words(env.get("SKALD_EMAIL"))
    mail: dict = {"to": to, "daily": False, "weekly": False}
    if env.get("SKALD_SMTP_HOST"):
        mail.update({"host": env["SKALD_SMTP_HOST"],
                     "port": env.get("SKALD_SMTP_PORT") or "587",
                     "security": env.get("SKALD_SMTP_SECURITY") or "starttls",
                     "from": env.get("SKALD_MAIL_FROM") or (to[0] if to else ""),
                     "daily": bool(to), "weekly": bool(to)})
        if env.get("SMTP_USER") or env.get("SMTP_PASSWORD"):
            # The NAMES of the variables; the values stay in the environment.
            mail.update({"user_env": "SMTP_USER", "password_env": "SMTP_PASSWORD"})
    config["mail"] = mail
    origins = _words(env.get("SKALD_BEACON_ORIGINS"))
    if origins:
        config["beacon"] = {"enabled": True, "origins": origins,
                            "log": "/var/log/nginx/skald-beacon.log"}
    # 2.22: the public "Is my site exposed?" check (stack_public_api.py), off unless asked.
    if str(env.get("SKALD_PUBLIC_CHECK", "")).strip().lower() in ("1", "true", "on", "yes"):
        config["security"] = {"public_check": True,
                              "public_check_origins": _words(env.get("SKALD_PUBLIC_CHECK_ORIGINS")),
                              "public_check_info_url":
                                  (env.get("SKALD_PUBLIC_CHECK_INFO_URL") or "").strip()}
    if str(env.get("SKALD_INGEST", "")).lower() in ("1", "true", "on", "yes"):
        config["ingest"] = {"enabled": True, "root": str(DATA / "ingest")}
    # 2.26: MCP over HTTP (POST /traffic-mcp, docs/MCP.md). The image's nginx has
    # always passed the path on, but a config made from the environment had no way
    # to say `mcp.enabled`, so the helper answered 404 "MCP is not switched on here".
    if str(env.get("SKALD_MCP", "")).strip().lower() in ("1", "true", "on", "yes"):
        config["mcp"] = {"enabled": True}
    # Crawler address checks (bot_verify.py), on unless SKALD_VERIFY_BOTS says
    # off. Without bots.ranges_dir nothing was ever checked in Docker: a fake
    # Googlebot counted as Googlebot, no hosting-network flag, and run-daily skipped
    # verify-bots. The folder is made at start (ranges_folder).
    if str(env.get("SKALD_VERIFY_BOTS", "")).strip().lower() not in VERIFY_OFF:
        config["bots"] = {"ranges_dir": str(RANGES)}
    # 2.4.0: keep each visit's IP address and leads' names and emails. Unset,
    # a new install keeps them and one upgraded from before 2.4.0 does not
    # (people/policy.py) until this, or Settings > Data retention, says so.
    # 2.15.0: `short` keeps each address shortened (203.0.113.57 as 203.0.113.0).
    keep = str(env.get("SKALD_KEEP_IPS", "")).strip().lower()
    if keep in ("1", "true", "on", "yes", "full", "0", "false", "off", "no"):
        config["privacy"] = {"keep_ips": keep in ("1", "true", "on", "yes", "full")}
    elif keep == "short":
        config["privacy"] = {"keep_ips": "short"}
    identity = str(env.get("SKALD_IDENTITY", "")).strip().lower()
    if identity:
        if identity not in ("full", "anonymous"):
            raise SystemExit(f"SKALD_IDENTITY {identity!r}: use full or anonymous")
        config["conversions"] = {"identity": identity}
    return config


def config_path(env: dict) -> Path:
    """The config in use: SKALD_CONFIG, a mounted one, else the generated one
    (rewritten only when the environment changed it)."""
    if env.get("SKALD_CONFIG"):
        return Path(env["SKALD_CONFIG"])
    if MOUNTED_CONFIG.exists():
        return MOUNTED_CONFIG
    # JSON is YAML, and config.py reads it without PyYAML too. Edits are lost
    # at the next start: mount your own /etc/skald/config.yml instead.
    text = json.dumps(render_config(env), indent=2) + "\n"
    if not GENERATED_CONFIG.exists() or GENERATED_CONFIG.read_text() != text:
        tmp = GENERATED_CONFIG.with_suffix(".tmp")
        tmp.write_text(text)
        os.chmod(tmp, 0o640)
        os.replace(tmp, GENERATED_CONFIG)
    return GENERATED_CONFIG


def read_config(path: Path) -> dict:
    sys.path.insert(0, str(APP))
    from skald.config import load_config
    return load_config(path)


# -------------------------------------------------------------- environment

def env_file_values(path: Path) -> dict:
    """`export NAME='value'` lines, read the way cron and systemd's units read
    them: sourced by the shell. Values are never printed."""
    if not path.is_file() or not os.access(path, os.R_OK):
        return {}
    got = subprocess.run(["/bin/sh", "-c", '. "$1" >/dev/null 2>&1 && env -0', "sh", str(path)],
                         capture_output=True, timeout=20, env={"PATH": os.environ.get("PATH", "")})
    if got.returncode != 0:
        log(f"could not read {path}; carrying on without it")
        return {}
    out = {}
    for item in got.stdout.split(b"\0"):
        name, sep, value = item.decode("utf-8", "replace").partition("=")
        if sep and name and name not in ("PWD", "SHLVL", "_", "PATH"):
            out[name] = value
    return out


def ensure_visitor_key() -> None:
    """A key for returning visitors (keyed hashes, 30 days), made once."""
    path = DATA / "env"
    if path.exists():
        return
    old = os.umask(0o177)
    try:
        path.write_text("# Made by the container on its first start. Keep it; never share it.\n"
                        f"export SKALD_VISITOR_KEY='{secrets.token_hex(32)}'\n")
    finally:
        os.umask(old)


def load_environment() -> None:
    for path in ENV_FILES:
        for name, value in env_file_values(path).items():
            os.environ.setdefault(name, value)


# ------------------------------------------------------ the visitor's address

def trusted_conf(env: dict) -> str:
    """nginx's realip lines from SKALD_TRUSTED_PROXIES and SKALD_REAL_IP_HEADER.

    Empty (the default): nobody is believed, the visitor's address is the
    connection's own; right when the container faces the internet. Behind a
    proxy (a platform's, an Ingress, your nginx or Caddy), list its ranges, or
    `private`: then the header (X-Forwarded-For unless SKALD_REAL_IP_HEADER
    says otherwise) is believed from them only, walked right to left past
    every trusted hop (real_ip_recursive), so the visitor's own claims in it
    are never taken. 0.0.0.0/0 is refused: every visitor could claim any address.
    """
    nets: list[str] = []
    for word in _words(env.get("SKALD_TRUSTED_PROXIES")):
        if word.lower() in ("none", "off"):
            continue
        if word.lower() == "private":
            nets += PRIVATE
            continue
        try:
            net = ipaddress.ip_network(word, strict=False)
        except ValueError:
            raise SystemExit(f"SKALD_TRUSTED_PROXIES {word!r}: give addresses or ranges "
                             "such as 10.0.0.0/8, or `private`") from None
        if net.prefixlen == 0:
            raise SystemExit(f"SKALD_TRUSTED_PROXIES {word!r} trusts every address: "
                             "give the proxy's own range (docs/HOSTING.md)")
        nets.append(str(net))
    header = (env.get("SKALD_REAL_IP_HEADER") or "X-Forwarded-For").strip()
    if not REAL_IP_HEADER.match(header):
        raise SystemExit(f"SKALD_REAL_IP_HEADER {header!r}: give a header name, "
                         "e.g. X-Forwarded-For")
    if not nets:
        return ("# SKALD_TRUSTED_PROXIES is empty: no proxy is believed, the visitor's\n"
                "# address is the connection's own.\n")
    lines = ["# From SKALD_TRUSTED_PROXIES and SKALD_REAL_IP_HEADER (docs/HOSTING.md)."]
    lines += [f"set_real_ip_from {n};" for n in dict.fromkeys(nets)]
    lines += [f"real_ip_header {header};", "real_ip_recursive on;"]
    return "\n".join(lines) + "\n"


def _proc_address(text: str) -> str:
    raw = bytes.fromhex(text)                # 32-bit words in the kernel's (little-endian) order
    raw = b"".join(raw[i:i + 4][::-1] for i in range(0, len(raw), 4))
    addr = ipaddress.ip_address(raw)
    if addr.version == 6 and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return str(addr)


def peers(port: int, proc: Path = Path("/proc/net")) -> list[str]:
    """The remote addresses with an open connection to the port: behind a
    platform, its proxy's (the health check's too)."""
    found: set[str] = set()
    for name in ("tcp", "tcp6"):
        try:
            rows = (proc / name).read_text().splitlines()[1:]
        except OSError:
            continue
        for row in rows:
            f = row.split()
            if len(f) < 4 or f[3] != "01":       # 01: established
                continue
            local, remote = f[1].rsplit(":", 1), f[2].rsplit(":", 1)
            if int(local[1], 16) == port:
                found.add(_proc_address(remote[0]))
    return sorted(found, key=lambda a: (ipaddress.ip_address(a).version, ipaddress.ip_address(a)))


def show_peers(env: dict) -> int:
    port = int(env.get("SKALD_PORT") or 8080)
    got = peers(port)
    if not got:
        print(f"no connection to port {port} right now: load the dashboard and run this again")
        return 1
    print(f"connected to port {port} now (load the dashboard while you run this):")
    for addr in got:
        print(f"  {addr}")
    print("Your own address is not here when a proxy is in front: these are the proxy's.\n"
          "Put its range in SKALD_TRUSTED_PROXIES (docs/HOSTING.md says which, per platform).")
    return 0


# ------------------------------------------------------------- the user

def app_user() -> tuple[str, int, int]:
    try:
        pw = pwd.getpwnam(APP_USER)
        return APP_USER, pw.pw_uid, pw.pw_gid
    except KeyError:
        return APP_USER, APP_ID, APP_ID


def own_data(uid: int, gid: int) -> None:
    """A data disk mounted for root becomes the image's user's, with all it
    holds. Checked at every start (the folder and its first level, a few
    stat calls); the whole tree is walked only when one is someone else's.
    Symbolic links are changed themselves, never followed."""
    try:
        top = os.lstat(DATA)
        first = [os.lstat(p) for p in DATA.iterdir()]
    except OSError:
        return
    if top.st_uid == uid and all(s.st_uid == uid for s in first):
        return
    log(f"{DATA} belongs to uid {top.st_uid}: giving it to uid {uid}")
    try:
        os.lchown(DATA, uid, gid)
        os.chmod(DATA, 0o750)
        for folder, dirs, files in os.walk(DATA):
            for name in dirs + files:
                os.lchown(os.path.join(folder, name), uid, gid)
    except OSError as why:
        log(f"could not hand {DATA} over ({why}); if it is not writable, "
            f"chown -R {uid}:{gid} it on the host")


def drop_privileges(fix_data: bool) -> None:
    """Root only long enough to hand the data disk over, then uid 10001."""
    if os.getuid() != 0:
        return
    name, uid, gid = app_user()
    if fix_data:
        own_data(uid, gid)
    try:
        os.initgroups(name, gid)                 # its own group and adm (gid 4: /logs)
        os.setgid(gid)
        os.setuid(uid)
    except OSError as why:
        raise SystemExit(f"started as root but cannot become uid {uid} ({why}): run the "
                         f"container as that user (docker --user {uid}:{gid}) or allow "
                         "SETUID and SETGID") from None
    os.environ["HOME"] = str(DATA)


# ---------------------------------------------------------------- the serve

def runtime_nginx_files(env: dict) -> None:
    for sub in ("", "body", "proxy", "fastcgi", "uwsgi", "scgi"):
        (RUN / sub).mkdir(parents=True, exist_ok=True)
    port = int(env.get("SKALD_PORT") or 8080)
    (RUN / "listen.conf").write_text(f"listen {port};\nlisten [::]:{port};\n"
                                     if Path("/proc/net/if_inet6").exists()
                                     else f"listen {port};\n")
    (RUN / "trusted.conf").write_text(trusted_conf(env))
    (DATA / "nginx").mkdir(exist_ok=True)


def ranges_folder(config: dict) -> None:
    """Make the config's bots.ranges_dir, so the first run-daily's verify-bots
    has somewhere to keep the lists. A folder it cannot make is only logged:
    verify-bots makes it again, and counting goes on without the checks."""
    raw = ((config or {}).get("bots") or {}).get("ranges_dir")
    if not raw:
        return
    try:
        Path(str(raw)).mkdir(parents=True, exist_ok=True)
    except OSError as why:
        log(f"bots.ranges_dir {raw}: {why}; crawler checks wait for it")


def build_json() -> None:
    """The footer's build.json: what the image says it is."""
    src = APP / "build.json"
    if src.exists():
        try:
            (DASHBOARD / "build.json").write_text(src.read_text())
        except OSError:
            pass


def programs(cfg_path: Path, config: dict, env: dict) -> dict[str, list[str]]:
    py = sys.executable
    origins = _words(env.get("SKALD_ORIGIN"))
    base = (config.get("access") or {}).get("base_url") or ""
    if not origins and _origin(str(base)):
        origins = [_origin(str(base))]
    refresh = [py, "-m", "skald.refresh_server", "--config", str(cfg_path), "--port", "8765"]
    for o in origins:
        refresh += ["--origin", o]
    progs = {
        "nginx": ["nginx", "-c", str(APP / "docker" / "nginx.conf"), "-e", "stderr",
                  "-g", "daemon off;"],
        "refresh": refresh,
    }
    # Always: it is also the receiver of the signed tool hooks (Calendly, Stripe,
    # the `lead` hook...), which must not wait on the script tag being switched on.
    # Without beacon.origins it takes hooks only (beacon_server.py).
    progs["beacon"] = [py, "-m", "skald.beacon_server", "--config", str(cfg_path),
                       "--port", "8766"]
    if str(env.get("SKALD_SCHEDULER", "on")).lower() not in ("0", "off", "false", "no"):
        progs["scheduler"] = [py, str(APP / "docker" / "scheduler.py"), "--config", str(cfg_path)]
    return progs


class Supervisor:
    """Start each program, restart it when it stops (5 s, doubling to 60 s
    while it keeps failing fast), reap every child (this is PID 1), and stop
    them all on SIGTERM."""

    def __init__(self, progs: dict[str, list[str]]):
        self.progs = progs
        self.pids: dict[int, str] = {}
        self.started: dict[str, float] = {}
        self.delay: dict[str, float] = {n: 5.0 for n in progs}
        self.due: dict[str, float] = {n: 0.0 for n in progs}
        self.stopping = False

    def start(self, name: str) -> None:
        try:
            proc = subprocess.Popen(self.progs[name], cwd=str(APP))
        except OSError as why:
            log(f"{name}: cannot start: {why}")
            self.due[name] = time.monotonic() + self.delay[name]
            return
        self.pids[proc.pid] = name
        self.started[name] = time.monotonic()
        log(f"{name}: started (pid {proc.pid})")

    def stop(self, *_):
        self.stopping = True

    def run(self) -> int:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        for name in self.progs:
            self.start(name)
        while not self.stopping:
            self.reap()
            now = time.monotonic()
            running = set(self.pids.values())
            for name in self.progs:
                if name not in running and self.due[name] and now >= self.due[name]:
                    self.due[name] = 0.0
                    self.start(name)
            time.sleep(0.5)
        log("stopping")
        for pid in list(self.pids):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        end = time.monotonic() + 50          # the scheduler gives a running job 45 s
        while self.pids and time.monotonic() < end:
            self.reap()
            time.sleep(0.2)
        for pid in list(self.pids):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return 0

    def reap(self) -> None:
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return
            if pid == 0:
                return
            name = self.pids.pop(pid, None)
            if name is None or self.stopping:
                continue                     # an orphan re-parented to PID 1, or a stop
            code = os.waitstatus_to_exitcode(status)
            ran = time.monotonic() - self.started.get(name, 0)
            self.delay[name] = 5.0 if ran > 60 else min(self.delay[name] * 2, 60.0)
            self.due[name] = time.monotonic() + self.delay[name]
            log(f"{name}: stopped (exit {code}) after {ran:.0f} s; "
                f"restarting in {self.delay[name]:.0f} s")


def serve(env: dict) -> int:
    cfg_path = config_path(env)
    config = read_config(cfg_path)
    runtime_nginx_files(env)
    ranges_folder(config)
    build_json()
    log(f"config {cfg_path}; dashboard on port {int(env.get('SKALD_PORT') or 8080)} "
        f"at /traffic/; site {config.get('site', {}).get('name') or 'site'}")
    return Supervisor(programs(cfg_path, config, env)).run()


def health(env: dict) -> int:
    port = int(env.get("SKALD_PORT") or 8080)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/traffic-auth/login", timeout=8) as r:
            ok = r.status < 500
    except urllib.error.HTTPError as e:
        ok = e.code < 500
    except OSError as why:
        print(f"unhealthy: port {port}: {why}")
        return 1
    if not ok:
        print("unhealthy: the sign-in page does not answer")
        return 1
    if str(env.get("SKALD_SCHEDULER", "on")).lower() not in ("0", "off", "false", "no"):
        try:
            age = time.time() - BEAT.stat().st_mtime
        except OSError:
            age = 1e9
        if age > 300:
            print("unhealthy: the scheduler has not run for 5 minutes")
            return 1
    print("ok")
    return 0


def kit_defaults() -> None:
    """SKALD_KIT_IMAGE (this image at its major version) and SKALD_KIT_SHIP_PATH
    (the shipper inside it), unless the environment already names them (empty
    counts as unset)."""
    try:
        major = (APP / "VERSION").read_text().strip().split(".")[0]
    except OSError:
        major = ""
    tag = major if major.isdigit() else "latest"
    if not (os.environ.get("SKALD_KIT_IMAGE") or "").strip():      # compose passes it empty
        os.environ["SKALD_KIT_IMAGE"] = f"{KIT_IMAGE}:{tag}"
    if not (os.environ.get("SKALD_KIT_SHIP_PATH") or "").strip():
        os.environ["SKALD_KIT_SHIP_PATH"] = str(APP / "tools" / "skald-ship.py")


def main(argv: list[str]) -> int:
    args = argv or ["serve"]
    drop_privileges(fix_data=args[0] not in ("health", "peers"))
    if args[0] in ("sh", "bash", "/bin/sh", "/bin/bash"):
        os.execvp(args[0], args)
    if args[0] == "health":
        return health(dict(os.environ))
    if args[0] == "peers":
        return show_peers(dict(os.environ))
    if DATA.is_dir() and os.access(DATA, os.W_OK):
        ensure_visitor_key()
    load_environment()
    kit_defaults()
    env = dict(os.environ)
    if args[0] == "serve":
        return serve(env)
    cfg_path = config_path(env)
    if args[0] == "config":
        print(f"# {cfg_path}")
        print(cfg_path.read_text(), end="")
        return 0
    if args[0] == "skald":           # the image's /usr/local/bin wrapper names itself
        args = args[1:]
    os.chdir(APP)
    os.execv(sys.executable, [sys.executable, str(APP / "bin/skald"), "--config", str(cfg_path), *args])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

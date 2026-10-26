"""The shipper kit's shell and text templates (skald/kit/).

Fills the placeholders the way the kit builder does (plain str.replace), then:
syntax-checks every script, runs the install scripts with --dry-run behind
PATH shims, and runs check.sh against a made-up server under SKALD_CHECK_ROOT
(docker, curl, pgrep, systemctl and journalctl are shims). Test addresses are
RFC 5737 only; the token is made up.
"""
import grp
import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "skald" / "kit"
BASH = "/bin/bash" if os.path.exists("/bin/bash") else shutil.which("bash")

SITE = "example.com"
URL = "https://stats.example.com/traffic-ingest/example.com"
VALUES = {
    "__SITE__": SITE,
    "__URL__": URL,
    "__HOST__": "stats.example.com",
    "__IMAGE__": "registry.example.com/skald:2",
    "__SHIP_PATH__": "/opt/skald/tools/skald-ship.py",
    "__DASHBOARD__": "https://stats.example.com/traffic/example.com/",
    "__HELP__": "https://stats.example.com/traffic/example.com/#help?part=connections",
}
TOKEN = "skald_ab12cd34_" + "Zq7Lm2Np9Rs4Tv8Wx1Yb5Cd3Fg6Hj0Kk2Mp7Qr9St4Uv"[:43]
ADDRESSES = re.compile(r"192\.0\.2\.\d+|203\.0\.113\.\d+")
TEMPLATES = ["install-docker.sh", "install-systemd.sh", "uninstall.sh", "check.sh",
             "README-docker.txt", "README-systemd.txt"]
LOG = "/var/log/nginx/example.com.access.log"


def fill(name, method="docker"):
    text = (KIT / name).read_text(encoding="utf-8")
    for key, value in dict(VALUES, __METHOD__=method).items():
        text = text.replace(key, value)
    return text


def shim(folder, name, body):
    path = Path(folder) / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


def env_with(shims, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SKALD_")}
    env["PATH"] = f"{shims}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["LC_ALL"] = "C"
    env.update(extra)
    return env


@unittest.skipIf(BASH is None, "bash is not installed")
class Templates(unittest.TestCase):

    def test_placeholders_fill_and_scripts_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in TEMPLATES:
                raw = (KIT / name).read_text(encoding="utf-8")
                for word in ("skaldanalytics", "ghcr.io", "Teams"):
                    self.assertNotIn(word, raw, f"{name} names {word}")
                for method in ("docker", "systemd"):
                    text = fill(name, method)
                    left = re.findall(r"__[A-Z_]+__", text)
                    self.assertEqual(left, [], f"{name}: placeholders left: {left}")
                    if name.endswith(".sh"):
                        path = Path(tmp) / f"{method}-{name}"
                        path.write_text(text, encoding="utf-8")
                        got = subprocess.run([BASH, "-n", str(path)], capture_output=True,
                                             text=True)
                        self.assertEqual(got.returncode, 0, f"{name}: {got.stderr}")

    def test_every_file_is_short(self):
        for name in TEMPLATES:
            lines = (KIT / name).read_text(encoding="utf-8").count("\n")
            self.assertLess(lines, 1000, name)

    def test_install_scripts_use_a_kit_token_and_remove_it(self):
        for name, save in (("install-docker.sh", 'chgrp adm "$BASE/ship-token"'),
                           ("install-systemd.sh", 'chgrp "$USER_NAME" "$CONF/token"')):
            text = (KIT / name).read_text(encoding="utf-8")
            self.assertIn('if [ -s "$HERE/ship-token" ]', text, name)
            self.assertIn("(umask 027; printf '%s\\n' \"$1\" >", text, name)
            self.assertIn(save, text, name)
            self.assertIn('rm -f "$HERE/ship-token"', text, name)
            self.assertIn("read -r -s -p", text, name)
            self.assertIn("ship.conf", text, name)
            self.assertNotIn('echo "$TOKEN"', text, name)
        unit = (KIT / "install-systemd.sh").read_text(encoding="utf-8")
        for part in ("--url $URL", "--from-end", "--log $LOG", "--token-file $CONF/token",
                     "daemon-reload", "enable --now skald-ship", "(3, 9)",
                     "journalctl -u skald-ship -n 20 -o cat"):
            self.assertIn(part, unit)

    def test_uninstall_has_both_methods(self):
        text = (KIT / "uninstall.sh").read_text(encoding="utf-8")
        for part in ('METHOD="__METHOD__"', "docker rm -f skald-ship", "disable --now skald-ship",
                     "/usr/local/bin/skald-ship", "/var/lib/skald-ship", "/etc/skald-ship"):
            self.assertIn(part, text)


@unittest.skipIf(BASH is None, "bash is not installed")
class InstallDryRun(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        shim(self.bin, "docker", 'case "$1" in ps) echo other-app ;; esac\nexit 0\n')
        shim(self.bin, "systemctl", "exit 0\n")
        shim(self.bin, "python3", f'exec "{sys.executable}" "$@"\n')
        self.kit = self.tmp / f"skald-ship-{SITE}"
        self.kit.mkdir()
        self.log = self.tmp / "access.log"
        self.log.write_text('192.0.2.10 - - [21/Oct/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 5\n')

    def run_install(self, template, method, answers, kit_token=True, extra_env=None):
        (self.kit / "install.sh").write_text(fill(template, method), encoding="utf-8")
        (self.kit / "skald-ship.py").write_text("# stand-in\n", encoding="utf-8")
        held = self.kit / "ship-token"
        if kit_token:
            held.write_text(TOKEN + "\n", encoding="utf-8")
            held.chmod(0o600)
        else:
            held.unlink(missing_ok=True)
        got = subprocess.run([BASH, "install.sh", "--dry-run"], cwd=self.kit, input=answers,
                             capture_output=True, text=True,
                             env=env_with(self.bin, **(extra_env or {})), timeout=60)
        out = got.stdout + got.stderr
        self.assertEqual(got.returncode, 0, out)
        self.assertNotIn(TOKEN, out)
        self.assertNotIn(TOKEN[15:], out)
        self.assertNotIn("192.0.2.10", out)
        if kit_token:
            self.assertTrue(held.exists(), "a dry run must not delete the kit's token")
            self.assertIn("would delete the kit's copy", out)
        return out

    def test_docker_with_the_token_in_the_kit(self):
        out = self.run_install("install-docker.sh", "docker", f"{self.log}\n")
        self.assertIn("would save the token to /srv/skald/ship-token", out)
        self.assertIn("would write /srv/skald/ship.conf", out)
        self.assertIn("registry.example.com/skald:2 /opt/skald/tools/skald-ship.py", out)
        self.assertIn(f"--url {URL}", out)
        self.assertIn("--from-end", out)

    def test_docker_with_a_pasted_token(self):
        out = self.run_install("install-docker.sh", "docker", f"{self.log}\n{TOKEN}\n",
                               kit_token=False)
        self.assertIn("would save the token", out)

    # A zip made without the token (the page's box unticked): install.sh asks for it, or
    # reads SKALD_SHIP_TOKEN, or a ship-token file the admin made (the kit-token path).
    def test_without_the_token_in_the_kit_it_reads_the_environment(self):
        for template, method, saved in (("install-docker.sh", "docker", "/srv/skald/ship-token"),
                                        ("install-systemd.sh", "systemd", "/etc/skald-ship/token")):
            out = self.run_install(template, method, f"{self.log}\n", kit_token=False,
                                   extra_env={"SKALD_SHIP_TOKEN": f"  {TOKEN}\n"})
            self.assertIn("the token is in SKALD_SHIP_TOKEN; it is used, not shown", out)
            self.assertIn(f"would save the token to {saved}", out)
            self.assertNotIn("This kit has no token", out, "the variable is used: nothing is asked")

    def test_without_the_token_in_the_kit_it_asks_on_stdin(self):
        for template, method in (("install-docker.sh", "docker"), ("install-systemd.sh", "systemd")):
            out = self.run_install(template, method, f"{self.log}\n{TOKEN}\n", kit_token=False)
            self.assertIn("This kit has no token: it was sent to you separately.", out)
            # read -p prints its prompt only on a terminal; the token came from stdin.
            self.assertIn("would save the token", out)

    def test_a_ship_token_file_the_admin_made_is_used(self):
        # The README's first way: the admin writes ship-token next to install.sh.
        out = self.run_install("install-systemd.sh", "systemd", f"{self.log}\n")
        self.assertIn("would save the token to /etc/skald-ship/token", out)
        self.assertIn("this kit holds the token (the file ship-token)", out)
        self.assertNotIn("This kit has no token", out)

    def test_without_any_token_it_stops_and_says_how(self):
        for template, method in (("install-docker.sh", "docker"), ("install-systemd.sh", "systemd")):
            (self.kit / "install.sh").write_text(fill(template, method), encoding="utf-8")
            (self.kit / "skald-ship.py").write_text("# stand-in\n", encoding="utf-8")
            (self.kit / "ship-token").unlink(missing_ok=True)
            got = subprocess.run([BASH, "install.sh", "--dry-run"], cwd=self.kit,
                                 input=f"{self.log}\n\n", capture_output=True, text=True,
                                 env=env_with(self.bin), timeout=60)
            self.assertEqual(got.returncode, 1, got.stdout + got.stderr)
            self.assertIn("no token given", got.stderr)
            self.assertIn("SKALD_SHIP_TOKEN", got.stderr)
            got = subprocess.run([BASH, "install.sh", "--dry-run"], cwd=self.kit,
                                 input=f"{self.log}\n", capture_output=True, text=True,
                                 env=env_with(self.bin, SKALD_SHIP_TOKEN="short"), timeout=60)
            self.assertEqual(got.returncode, 1)
            self.assertIn("SKALD_SHIP_TOKEN does not hold a token", got.stderr)

    def test_the_readmes_say_the_three_ways(self):
        for name in ("README-docker.txt", "README-systemd.txt"):
            text = fill(name)
            for part in ("If the token is not in this kit", "A file named ship-token in this folder",
                         "read -rs SKALD_SHIP_TOKEN && export SKALD_SHIP_TOKEN",
                         "sudo --preserve-env=SKALD_SHIP_TOKEN bash install.sh",
                         "Pasted when install.sh asks for it"):
                self.assertIn(part, text, name)

    def test_docker_refuses_a_short_kit_token(self):
        (self.kit / "install.sh").write_text(fill("install-docker.sh"), encoding="utf-8")
        (self.kit / "ship-token").write_text("short\n", encoding="utf-8")
        got = subprocess.run([BASH, "install.sh", "--dry-run"], cwd=self.kit,
                             input=f"{self.log}\n", capture_output=True, text=True,
                             env=env_with(self.bin), timeout=60)
        self.assertEqual(got.returncode, 1)
        self.assertIn("too short", got.stderr)

    def test_systemd_with_the_token_in_the_kit(self):
        out = self.run_install("install-systemd.sh", "systemd", f"{self.log}\n")
        self.assertIn("would save the token to /etc/skald-ship/token", out)
        self.assertIn("install -m 0755", out)
        self.assertIn("/usr/local/bin/skald-ship", out)
        self.assertIn(f"--url {URL}", out)
        self.assertIn(f"--log {self.log}", out)
        self.assertIn("--from-end", out)
        self.assertIn("enable --now skald-ship", out)
        self.assertIn("journalctl -u skald-ship -n 20 -o cat", out)


@unittest.skipIf(BASH is None, "bash is not installed")
class Check(unittest.TestCase):
    """check.sh against a made-up server: a working one, then a broken one."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = self.tmp / "root"
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.kit = self.tmp / "kit"
        self.kit.mkdir()

    def put(self, path, text, mode=0o644, age=0):
        full = self.root / path.lstrip("/")
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(text, encoding="utf-8")
        full.chmod(mode)
        if age:
            when = time.time() - age
            os.utime(full, (when, when))
        return full

    def access_log(self, age=0, path=LOG):
        lines = "".join(f'192.0.2.{n} - - [21/Oct/2026:10:00:0{n} +0000] "GET / HTTP/1.1" '
                        f'200 512 "-" "Mozilla/5.0"\n' for n in range(1, 6))
        lines += '203.0.113.5 - - [21/Oct/2026:10:00:09 +0000] "GET /a HTTP/1.1" 200 9 "-" "-"\n'
        self.put(path, lines, 0o644, age)

    def nginx(self, shared=False):
        self.put("/etc/nginx/nginx.conf",
                 "http {\n"
                 "  log_format j escape=json '{\"a\":\"$remote_addr\"}';\n"
                 "  access_log /var/log/nginx/access.log;\n"
                 "  include /etc/nginx/sites-enabled/*;\n}\n")
        text = ("server {\n  listen 443 ssl;\n  server_name www.example.com example.com;\n"
                f"  access_log {LOG};\n  location / {{\n    return 200;\n  }}\n}}\n"
                "server {\n  listen 80 default_server;\n  server_name _;\n}\n")
        if shared:
            text += ("server {\n  server_name blog.example.org;\n"
                     f"  access_log {LOG} combined;\n}}\n")
        self.put("/etc/nginx/sites-enabled/example.com", text)

    def token(self, mode=0o640, where="/srv/skald/ship-token"):
        made = self.put(where, TOKEN + "\n", mode)
        st = made.stat()
        self.owner = pwd.getpwuid(st.st_uid).pw_name
        self.group = grp.getgrgid(st.st_gid).gr_name

    def docker_shim(self, state, logs):
        (self.tmp / "docker-logs").write_text(logs, encoding="utf-8")
        shim(self.bin, "docker",
             'case "$1" in\n'
             "  info) exit 0 ;;\n"
             "  ps) echo 'skald-ship 203.0.113.9' ;;\n"
             '  inspect) case "$*" in\n'
             f"    *Args*) printf '%s\\n' /opt/skald/tools/skald-ship.py --url {URL} "
             f"--token-file /run/skald-ship/token --log {LOG} --state /state/state.json ;;\n"
             f"    *State*) echo '{state}' ;;\n"
             "    *) echo '[{\"IPAddress\": \"203.0.113.9\"}]' ;;\n"
             "  esac ;;\n"
             f'  logs) cat "{self.tmp / "docker-logs"}" >&2 ;;\n'
             "esac\nexit 0\n")

    def run_check(self, method="docker", wait="0"):
        (self.kit / "check.sh").write_text(fill("check.sh", method), encoding="utf-8")
        env = env_with(self.bin, SKALD_CHECK_ROOT=str(self.root), SKALD_CHECK_WAIT=wait,
                       SKALD_CHECK_OWNER=self.owner, SKALD_CHECK_GROUP=self.group)
        got = subprocess.run([BASH, "check.sh"], cwd=self.kit, capture_output=True, text=True,
                             env=env, timeout=60)
        out = got.stdout + got.stderr
        self.assertNotIn(TOKEN, out)
        self.assertNotIn(TOKEN[15:], out)
        self.assertNotIn(TOKEN[15:30], out)
        self.assertIsNone(ADDRESSES.search(out), out)
        self.assertIn("Copy this and send it to us:", out)
        block = out.split("Copy this and send it to us:", 1)[1]
        for part in (f"method: {method}", f"site: {SITE}", "send to: stats.example.com", "UTC"):
            self.assertIn(part, block)
        return got.returncode, out, block

    def test_docker_all_ok(self):
        self.nginx()
        self.access_log()
        self.token()
        self.put("/srv/skald/ship.conf", f"METHOD=docker\nLOG={LOG}\nURL={URL}\nSITE={SITE}\n",
                 0o640)
        self.put("/srv/skald/ship-state/state.json", '{"offset": 10}\n', 0o600)
        self.docker_shim("running false 0",
                         "skald-ship: sent batch 1: 5 lines, 5 accepted, 0 rejected\n"
                         "skald-ship: a note naming 203.0.113.7\n")
        shim(self.bin, "curl", "printf 401\n")
        shim(self.bin, "pgrep", 'case "$*" in *nginx*) exit 0 ;; esac\nexit 1\n')
        code, out, block = self.run_check(wait="1")
        self.assertEqual(code, 0, out)
        self.assertNotIn("✗", out)
        checks = [line for line in out.splitlines() if line.startswith(("✓", "✗", "?"))]
        self.assertGreaterEqual(len(checks), 9, out)
        self.assertTrue(all(line.startswith("✓ OK  ") for line in checks), out)
        self.assertIn(f"www.example.com writes to {LOG}", out)
        self.assertIn("401 without a token is expected", out)
        self.assertIn(f"log: {LOG} (", block)
        self.assertNotIn("PROBLEM", block)

    def test_docker_broken(self):
        self.nginx(shared=True)
        self.access_log(age=3600)
        self.token(mode=0o644)
        self.put("/srv/skald/ship-state/state.json", '{"offset": 10}\n', 0o600, age=7200)
        self.docker_shim("restarting true 7",
                         "skald-ship: retry in 4 s: HTTP 401 unrecognised or revoked token\n"
                         "skald-ship: retry in 8 s: HTTP 401 unrecognised or revoked token\n"
                         "skald-ship: retry in 9 s: HTTP 403 this token is not for that site\n"
                         "skald-ship: sent batch 2: 4 lines, 1 accepted, 3 rejected\n"
                         "skald-ship: seen from 192.0.2.44 and 203.0.113.5\n")
        shim(self.bin, "curl", "printf 000\nexit 6\n")
        shim(self.bin, "pgrep", "exit 1\n")
        code, out, block = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn("✗ PROBLEM  neither nginx nor Apache is running", out)
        self.assertIn("✗ PROBLEM  nothing was written to", out)
        self.assertIn("is shared with other host names: blog.example.org", out)
        self.assertIn("✗ PROBLEM  this server cannot find stats.example.com", out)
        self.assertIn("✗ PROBLEM  the token file /srv/skald/ship-token is", out)
        self.assertIn("644", out)
        self.assertIn("✗ PROBLEM  skald-ship keeps restarting (7 restarts)", out)
        self.assertIn("the token is wrong or was revoked (HTTP 401) (in 2 of", out)
        self.assertIn("make a new sending token in Skald (Settings > Collect data > Send logs)", out)
        self.assertIn("the token is for another site (HTTP 403) (in 1 of", out)
        self.assertIn("3 lines were in a log format Skald does not read", out)
        self.assertIn("set the site's log format to auto", out)
        self.assertIn("  fix: ", out)
        for part in ("shipper: 401 wrong or revoked token (x2)",
                     "shipper: 403 token for another site (x1)",
                     "shipper: 3 lines rejected", "PROBLEM  skald-ship keeps restarting"):
            self.assertIn(part, block)
        # the log was found from the container's own arguments (no ship.conf here)
        self.assertIn(f"log: {LOG} (", block)
        self.assertNotIn("unrecognised or revoked token", out)

    def test_docker_log_unreadable_and_state_stale_while_growing(self):
        self.nginx()
        self.access_log()
        (self.root / LOG.lstrip("/")).chmod(0o600)
        self.token()
        self.put("/srv/skald/ship.conf", f"METHOD=docker\nLOG={LOG}\n", 0o640)
        self.put("/srv/skald/ship-state/state.json", "{}\n", 0o600, age=7200)
        self.docker_shim("running false 0", "")
        shim(self.bin, "curl", "printf 401\n")
        shim(self.bin, "pgrep", 'case "$*" in *nginx*) exit 0 ;; esac\nexit 1\n')
        code, out, _ = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn("group adm may not read", out)
        self.assertIn("the log grows but no lines have left", out)

    def test_systemd_apache_all_ok(self):
        log = "/var/log/apache2/example.com.access.log"
        self.put("/etc/apache2/sites-enabled/example.com.conf",
                 "<VirtualHost *:443>\n  ServerName www.example.com\n  ServerAlias example.com\n"
                 "  CustomLog ${APACHE_LOG_DIR}/example.com.access.log combined\n"
                 "</VirtualHost>\n")
        self.access_log(path=log)
        self.token(where="/etc/skald-ship/token")
        self.put("/etc/skald-ship/ship.conf", f"METHOD=systemd\nURL={URL}\nSITE={SITE}\n", 0o640)
        self.put("/etc/systemd/system/skald-ship.service",
                 "[Service]\nExecStart=/usr/local/bin/skald-ship \\\n"
                 f"    --url {URL} \\\n    --token-file /etc/skald-ship/token \\\n"
                 f"    --log {log} \\\n    --state /var/lib/skald-ship/state.json \\\n"
                 "    --from-end\n")
        self.put("/var/lib/skald-ship/state.json", "{}\n", 0o600)
        shim(self.bin, "systemctl",
             'case "$*" in\n  "is-active skald-ship") echo active ;;\n'
             '  *NRestarts*) echo NRestarts=1 ;;\n  *) exit 1 ;;\nesac\n')
        shim(self.bin, "journalctl",
             "echo 'skald-ship: sent batch 4: 10 lines, 10 accepted, 0 rejected'\n"
             "echo 'skald-ship: retry in 3 s: HTTP 429 too many batches for this site; "
             "slow down'\n")
        shim(self.bin, "curl", "printf 401\n")
        shim(self.bin, "pgrep", 'case "$*" in *apache2*) exit 0 ;; esac\nexit 1\n')
        code, out, block = self.run_check(method="systemd")
        self.assertEqual(code, 0, out)
        self.assertNotIn("✗", out)
        self.assertNotIn("Docker", out)
        self.assertIn(f"www.example.com writes to {log}", out)
        self.assertIn("the web server (apache2) is running", out)
        self.assertIn("skald-ship is running (1 restarts)", out)
        self.assertIn("slow down", out)
        self.assertIn("shipper: 429 slowed down (x1)", block)


@unittest.skipIf(BASH is None, "bash is not installed")
class CheckNextjs(unittest.TestCase):
    """check.sh's Next.js line: silent for other sites, advice (never a problem) when the
    log has ?_rsc= requests but does not record Next.js's prefetch header."""

    setUp, put, nginx, token = Check.setUp, Check.put, Check.nginx, Check.token
    docker_shim, run_check = Check.docker_shim, Check.run_check

    def working(self, lines, log_format=""):
        self.nginx()
        if log_format:
            self.put("/etc/nginx/conf.d/skald-log.conf", log_format)
        self.put(LOG, lines)
        self.token()
        self.put("/srv/skald/ship.conf", f"METHOD=docker\nLOG={LOG}\nURL={URL}\nSITE={SITE}\n",
                 0o640)
        self.put("/srv/skald/ship-state/state.json", '{"offset": 10}\n', 0o600)
        self.docker_shim("running false 0",
                         "skald-ship: sent batch 1: 5 lines, 5 accepted, 0 rejected\n")
        shim(self.bin, "curl", "printf 401\n")
        shim(self.bin, "pgrep", 'case "$*" in *nginx*) exit 0 ;; esac\nexit 1\n')
        return self.run_check()

    @staticmethod
    def lines(url="/pricing/?_rsc=1x2y", tail=""):
        return "".join(f'192.0.2.{n} - - [21/Oct/2026:10:00:0{n} +0000] "GET {url} HTTP/1.1" '
                       f'200 512 "-" "Mozilla/5.0"{tail}\n' for n in range(1, 6))

    def test_silent_for_a_site_that_is_not_nextjs(self):
        code, out, block = self.working(self.lines(url="/pricing/"))
        self.assertEqual(code, 0, out)
        self.assertNotIn("Next.js", out)
        self.assertNotIn("ADVICE", out)

    def test_advice_with_the_lines_and_no_problem(self):
        code, out, block = self.working(self.lines())
        self.assertEqual(code, 0, out)
        self.assertNotIn("✗", out)
        self.assertIn("! ADVICE  pages opened inside this Next.js site are not counted", out)
        self.assertIn("append rsc_prefetch=$http_next_router_prefetch at the end of the site's "
                      "nginx log_format", out)
        self.assertIn("rsc_prefetch=%{Next-Router-Prefetch}i", out)
        self.assertIn("sudo nginx -t && sudo systemctl reload nginx", out)
        self.assertIn("This script never edits nginx.", out)
        self.assertIn("ADVICE   pages opened inside this Next.js site are not counted", block)
        self.assertNotIn("PROBLEM", block)

    def test_ok_when_the_log_records_the_header(self):
        code, out, _ = self.working(self.lines(tail=" rsc_prefetch=-"))
        self.assertEqual(code, 0, out)
        self.assertIn("✓ OK  pages opened inside this Next.js site are counted", out)
        self.assertNotIn("ADVICE", out)

    def test_reload_advice_when_the_format_has_it_but_the_log_not(self):
        code, out, _ = self.working(
            self.lines(), "log_format intel '$remote_addr [$time_local] \"$request\" $status "
                          "rsc_prefetch=$http_next_router_prefetch';\n")
        self.assertEqual(code, 0, out)
        self.assertIn("! ADVICE  the log_format has rsc_prefetch= but the log does not show it "
                      "yet", out)
        self.assertIn("fix: sudo nginx -t && sudo systemctl reload nginx", out)
        self.assertNotIn("not counted", out)


if __name__ == "__main__":
    unittest.main()

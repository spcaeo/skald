"""The one-file installer (skald/kit/install-server.sh, kit.one_file).

Fills it as the helper does, syntax-checks it and the two commands it leaves
on the server, then runs it with --dry-run behind PATH shims, against a
made-up server's nginx and Apache settings under SKALD_INSTALL_ROOT. Every
run starts a new session, so no run can reach a real terminal. Test
addresses are RFC 5737 only; the token is made up.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from skald import kit

BASH = "/bin/bash" if os.path.exists("/bin/bash") else shutil.which("bash")
SITE = "example.com"
URL = "https://stats.example.com/traffic-ingest/example.com"
DASH = "https://stats.example.com/traffic/example.com/"
HELP = DASH + "#help?part=troubleshooting-connections"
IMAGE = "registry.example.com/skald:2"
SHIP = "/opt/skald/tools/skald-ship.py"
TOKEN = "skald_ab12cd34_" + "Zq7Lm2Np9Rs4Tv8Wx1Yb5Cd3Fg6Hj0Kk2Mp7Qr9St4Uv"[:43]
LINE = '192.0.2.10 - - [21/Oct/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 5\n'


def one(token=None, image=IMAGE, ship=SHIP) -> str:
    return kit.one_file(SITE, URL, DASH, HELP, image, ship, token).decode()


def embedded(text: str, mark: str) -> str:
    """The text of one heredoc inside the installer."""
    return re.search(rf"<<'{mark}'\n(.*?)\n{mark}\n", text, re.S).group(1)


def shim(folder: Path, name: str, body: str) -> None:
    path = folder / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


@unittest.skipIf(BASH is None, "bash is not installed")
class Fill(unittest.TestCase):
    def parses(self, text: str, name: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_text(text, encoding="utf-8")
            got = subprocess.run([BASH, "-n", str(path)], capture_output=True, text=True)
            self.assertEqual(got.returncode, 0, got.stderr)

    def test_filled_whole_and_parses(self):
        for token in (None, TOKEN):
            text = one(token)
            self.assertEqual(re.findall(r"__[A-Z][A-Z_]*__", text), [])
            self.parses(text, "skald-install.sh")
            for word in ("skaldanalytics", "ghcr.io"):
                self.assertNotIn(word, text)
            self.assertIn(f'URL="{URL}"', text)
            self.assertIn(f'IMAGE="{IMAGE}"', text)
            self.assertTrue(text.rstrip().endswith('main "$@"'), "parsed whole before it runs")

    def test_the_token_only_when_given(self):
        self.assertIn("KIT_TOKEN=''", one())
        self.assertNotIn("skald_ab12cd34", one())
        with_token = one(TOKEN)
        self.assertEqual(with_token.count(TOKEN), 1)
        self.assertIn(f"KIT_TOKEN='{TOKEN}'", with_token)
        with self.assertRaises(ValueError):
            one("not-a-token")

    def test_the_shipper_check_and_uninstall_are_inside(self):
        import base64
        text = one()
        shipper = base64.b64decode(embedded(text, "SKALD_SHIPPER_EOF"))
        self.assertEqual(shipper, kit.SHIPPER.read_bytes())
        check = embedded(text, "SKALD_CHECK_EOF").replace("@@METHOD@@", "docker")
        undo = embedded(text, "SKALD_UNINSTALL_EOF").replace("@@METHOD@@", "systemd")
        self.parses(check, "check.sh")
        self.parses(undo, "uninstall.sh")
        self.assertIn('METHOD="@@METHOD@@"', embedded(text, "SKALD_CHECK_EOF"))
        self.assertIn("sudo skald-ship-check", check)
        self.assertNotIn("bash install.sh", check)
        self.assertIn("rm -f /usr/local/bin/skald-ship-check /usr/local/bin/skald-ship-uninstall", undo)

    def test_without_an_image_docker_is_not_offered(self):
        text = one(image=None)
        self.assertIn('IMAGE=""', text)
        self.parses(text, "x.sh")

    def test_neither_image_nor_shipper(self):
        real = kit.SHIPPER
        try:
            kit.SHIPPER = Path("/nonexistent/skald-ship.py")
            with self.assertRaises(ValueError) as got:
                one(image=None)
            self.assertIn("neither", str(got.exception))
            self.assertIn('IMAGE="', one())          # Docker alone is enough
        finally:
            kit.SHIPPER = real

    def test_available_says_server(self):
        got = kit.available({"ingest": {"kit_image": IMAGE}})
        self.assertTrue(got["server"])


@unittest.skipIf(BASH is None, "bash is not installed")
class DryRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = self.tmp / "root"
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        shim(self.bin, "python3", f'exec "{sys.executable}" "$@"\n')
        shim(self.bin, "systemctl", "exit 0\n")

    def docker(self, works=True, running=""):
        shim(self.bin, "docker", f'case "$1" in info) exit {0 if works else 1} ;; '
                                 f'ps) printf "%s" "{running}" ;; esac\nexit 0\n')

    def put(self, path: str, text: str) -> Path:
        full = self.root / path.lstrip("/")
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(text, encoding="utf-8")
        return full

    def run_it(self, *args, token=TOKEN, image=IMAGE, code=0, tty=None, **env):
        script = self.tmp / "skald-install.sh"
        script.write_text(one(token, image=image), encoding="utf-8")
        environ = {k: v for k, v in os.environ.items() if not k.startswith("SKALD_")}
        environ.update(PATH=f"{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin", LC_ALL="C",
                       SKALD_INSTALL_ROOT=str(self.root), **env)
        if tty is not None:
            answers = self.tmp / "answers"
            answers.write_text(tty, encoding="utf-8")
            environ["SKALD_TTY"] = str(answers)
        else:
            environ["SKALD_TTY"] = str(self.tmp / "no-terminal")
        got = subprocess.run([BASH, str(script), "--dry-run", *args], capture_output=True,
                             text=True, env=environ, timeout=60, stdin=subprocess.DEVNULL,
                             start_new_session=True)
        out = got.stdout + got.stderr
        self.assertEqual(got.returncode, code, out)
        self.assertNotIn(TOKEN, out)
        self.assertNotIn(TOKEN[15:], out)
        self.assertNotIn("192.0.2.10", out)
        return out

    def nginx_site(self, log="/var/log/nginx/example.access.log"):
        self.put("/etc/nginx/nginx.conf", "http {\n  access_log /var/log/nginx/access.log;\n"
                 "  include /etc/nginx/sites-enabled/*;\n}\n")
        self.put("/etc/nginx/sites-enabled/other", "server {\n  server_name other.example.org;\n"
                 "  access_log /var/log/nginx/other.log;\n}\n")
        self.put("/etc/nginx/sites-enabled/example", (
            "server {\n  listen 443 ssl;  # the site\n"
            "  server_name example.com www.example.com;\n"
            f"  access_log {log} combined;\n"
            "  location /assets/ { access_log off; }\n}\n"))
        self.put("/var/log/nginx/other.log", LINE)
        self.put("/var/log/nginx/access.log", LINE)
        return self.put(log, LINE * 3)

    def test_docker_finds_the_log_in_nginx(self):
        self.docker()
        log = self.nginx_site()
        out = self.run_it()
        self.assertIn("with docker (Docker works here)", out)
        self.assertIn(f"found in the web server's settings: {log}", out)
        self.assertIn("this file holds the token; it is used, not shown", out)
        self.assertIn("would save the token to /srv/skald/ship-token (root:adm, 0640)", out)
        self.assertIn(f"{IMAGE} {SHIP}", out)
        self.assertIn(f"--url {URL}", out)
        self.assertIn(f"--log {log}", out)
        self.assertIn("would write /usr/local/bin/skald-ship-check", out)

    def test_systemd_when_docker_does_not_work(self):
        self.docker(works=False)
        log = self.nginx_site()
        out = self.run_it()
        self.assertIn("with systemd", out)
        self.assertNotIn("could not be unpacked", out)
        self.assertIn("install -m 0755", out)
        self.assertIn("/usr/local/bin/skald-ship", out)
        self.assertIn(f"--log {log}", out)
        self.assertIn("would save the token to /etc/skald-ship/token (root:skald-ship, 0640)", out)
        self.assertIn("enable --now skald-ship", out)

    def test_no_way_at_all_says_what_to_install(self):
        self.docker(works=False)
        (self.bin / "systemctl").unlink()
        self.nginx_site()
        out = self.run_it(code=1)
        self.assertIn("Install Docker", out)
        self.assertIn("Python 3.9 or newer with systemd", out)

    def test_apache_with_its_log_dir(self):
        self.docker()
        self.put("/etc/apache2/sites-enabled/example.conf", (
            "<VirtualHost *:443>\n    ServerName www.example.com:443\n"
            "    ServerAlias example.com\n"
            '    CustomLog "${APACHE_LOG_DIR}/example-access.log" combined\n'
            "</VirtualHost>\n"))
        log = self.put("/var/log/apache2/example-access.log", LINE)
        out = self.run_it()
        self.assertIn(f"found in the web server's settings: {log}", out)

    def test_nginx_host_variable(self):
        self.docker()
        self.nginx_site(log="/var/log/nginx/$host.log")
        log = self.put("/var/log/nginx/www.example.com.log", LINE)
        out = self.run_it()
        self.assertIn(f"found in the web server's settings: {log}", out)

    def test_two_logs_without_a_terminal_takes_the_biggest(self):
        self.docker()
        self.nginx_site()
        self.put("/etc/nginx/conf.d/plain.conf", "server {\n server_name example.com;\n"
                 " access_log /var/log/nginx/plain.log;\n}\n")
        self.put("/var/log/nginx/plain.log", LINE)
        out = self.run_it("--yes")
        self.assertIn("name 2 access logs", out)
        self.assertIn("took the biggest", out)
        self.assertIn(f"--log {self.root}/var/log/nginx/example.access.log", out)

    def test_two_logs_with_a_terminal_asks(self):
        self.docker()
        self.nginx_site()
        self.put("/etc/nginx/conf.d/plain.conf", "server {\n server_name example.com;\n"
                 " access_log /var/log/nginx/plain.log;\n}\n")
        plain = self.put("/var/log/nginx/plain.log", LINE)
        out = self.run_it(tty="1\n")             # conf.d is read before sites-enabled
        self.assertIn(f"1) {plain}", out)
        self.assertIn(f"using {plain}", out)
        self.assertNotIn("took the biggest", out)

    def test_the_log_given(self):
        self.docker()
        log = self.put("/srv/www/given.log", LINE)
        out = self.run_it("--log", str(log))
        self.assertIn(f"the log given with --log: {log}", out)

    def test_nothing_found_and_nobody_to_ask(self):
        self.docker()
        out = self.run_it(code=1)
        self.assertIn("Run this again with --log", out)

    def test_the_usual_place_when_no_block_names_the_site(self):
        self.docker()
        log = self.put("/var/log/nginx/access.log", LINE)
        out = self.run_it()
        self.assertIn(f"took the usual place: {log}", out)

    def test_token_from_the_environment_or_asked(self):
        self.docker()
        self.nginx_site()
        out = self.run_it(token=None, SKALD_SHIP_TOKEN=f" {TOKEN}\n")
        self.assertIn("the token is in SKALD_SHIP_TOKEN; it is used, not shown", out)
        out = self.run_it(token=None, tty=f"{TOKEN}\n")
        self.assertIn("would save the token to /srv/skald/ship-token", out)
        out = self.run_it(token=None, code=1)
        self.assertIn("no token", out)
        out = self.run_it(token=None, tty="not-a-token-at-all\n", code=1)
        self.assertIn("not a Skald sending token", out)

    def test_unknown_option(self):
        self.docker()
        out = self.run_it("--colour", code=1)
        self.assertIn("unknown option --colour", out)


if __name__ == "__main__":
    unittest.main()

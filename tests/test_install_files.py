"""The install files: docker/, docker-compose.yml, install.sh (docs/INSTALL.md).

  * the container scheduler's clock (every N minutes, a daily time in the
    site's zone across the clock changes) and its log rotation;
  * the config the container writes from its environment: sessions mode,
    mails off without SMTP, never a secret's value;
  * docker/nginx.conf is DEPLOY.md's sessions-mode config, regenerated, and
    every helper route reaches its helper there too (test_nginx_routes);
  * no secret, private address or real domain in any of the files;
  * install.sh: strict mode, root check, idempotent config, the uninstall
    path, shellcheck-clean when shellcheck is installed.
"""
from __future__ import annotations

import importlib.util
import ipaddress
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_nginx_routes as nr  # noqa: E402

UTC = timezone.utc


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scheduler = _load("skald_docker_scheduler", ROOT / "docker" / "scheduler.py")
entrypoint = _load("skald_docker_entrypoint", ROOT / "docker" / "entrypoint.py")
build_nginx = _load("skald_docker_build_nginx", ROOT / "docker" / "build-nginx-conf.py")

FILES = [ROOT / "docker-compose.yml", ROOT / "install.sh", ROOT / ".dockerignore",
         ROOT / "docs" / "INSTALL.md",
         *sorted(p for p in (ROOT / "docker").iterdir() if p.is_file())]


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


class SchedulerClock(unittest.TestCase):
    def test_every_two_minutes(self):
        self.assertEqual(scheduler.next_every(utc(2026, 10, 11, 10, 0, 0), 2), utc(2026, 10, 11, 10, 2))
        self.assertEqual(scheduler.next_every(utc(2026, 10, 11, 10, 1, 59), 2), utc(2026, 10, 11, 10, 2))
        self.assertEqual(scheduler.next_every(utc(2026, 10, 11, 23, 59, 30), 2), utc(2026, 10, 12, 0, 0))
        with self.assertRaises(ValueError):
            scheduler.next_every(utc(2026, 10, 11), 0)

    def test_daily_in_the_site_zone(self):
        # 07:15 in New York is 11:15 UTC in summer, 12:15 in winter.
        self.assertEqual(scheduler.next_daily(utc(2026, 7, 1, 9, 0), "07:15", "America/New_York"),
                         utc(2026, 7, 1, 11, 15))
        self.assertEqual(scheduler.next_daily(utc(2026, 7, 1, 11, 15), "07:15", "America/New_York"),
                         utc(2026, 7, 2, 11, 15), "strictly after: not twice in one minute")
        self.assertEqual(scheduler.next_daily(utc(2026, 1, 10, 13, 0), "07:15", "America/New_York"),
                         utc(2026, 1, 11, 12, 15))
        self.assertEqual(scheduler.next_daily(utc(2026, 10, 11, 21, 0), "03:30", "UTC"),
                         utc(2026, 10, 12, 3, 30))

    def test_the_clock_changes(self):
        # 2026-03-08 02:30 does not exist in New York: it runs once, an hour on (07:30 UTC).
        got = scheduler.next_daily(utc(2026, 3, 8, 5, 0), "02:30", "America/New_York")
        self.assertEqual(got, utc(2026, 3, 8, 7, 30))
        # 2026-11-01 01:30 happens twice: the run is the first, then the next day.
        first = scheduler.next_daily(utc(2026, 11, 1, 4, 0), "01:30", "America/New_York")
        self.assertEqual(first, utc(2026, 11, 1, 5, 30))
        self.assertEqual(scheduler.next_daily(first, "01:30", "America/New_York"),
                         utc(2026, 11, 2, 6, 30))

    def test_times_of_day(self):
        self.assertEqual(scheduler.parse_hhmm("7:05"), (7, 5))
        self.assertEqual(scheduler.parse_hhmm("23:59"), (23, 59))
        for bad in ("24:00", "7", "07:60", "", "seven"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                scheduler.parse_hhmm(bad)

    def test_rotation_is_logrotate_daily(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "skald-beacon.log"
            self.assertFalse(scheduler.rotate(log), "no file: nothing to do")
            for day in range(1, 18):
                log.write_text(f"day {day}\n")
                self.assertTrue(scheduler.rotate(log, keep=14))
            names = sorted(p.name for p in Path(tmp).iterdir())
            self.assertIn("skald-beacon.log.1", names)
            self.assertIn("skald-beacon.log.14.gz", names)
            self.assertNotIn("skald-beacon.log.15.gz", names)
            self.assertEqual(len(names), 14)
            self.assertEqual((Path(tmp) / "skald-beacon.log.1").read_text(), "day 17\n")
            import gzip
            with gzip.open(Path(tmp) / "skald-beacon.log.2.gz", "rt") as f:
                self.assertEqual(f.read(), "day 16\n")
            log.write_text("")
            self.assertFalse(scheduler.rotate(log), "an empty log is not rotated")


class ContainerConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = entrypoint.render_config({})
        self.assertEqual(cfg["site"]["name"], "site")
        self.assertEqual(cfg["logs"]["dir"], "/logs")
        self.assertEqual(cfg["access"]["mode"], "sessions")
        self.assertEqual(cfg["dashboard"]["out"], "/var/www/skald")
        self.assertIs(cfg["dashboard"]["app"], True, "the web app, not only the plain fallback page")
        self.assertEqual(cfg["mail"]["daily"], False, "no SMTP: no mail, and no failed run for it")
        self.assertEqual(cfg["report"]["timezone"], "UTC")
        self.assertNotIn("beacon", cfg)

    def test_from_the_environment(self):
        env = {"SKALD_SITE": "Example.com", "SKALD_HOSTS": "example.com, www.example.com",
               "SKALD_TIMEZONE": "Europe/Berlin", "SKALD_BASE_URL": "https://stats.example.com/",
               "SKALD_EMAIL": "owner@example.com", "SKALD_SMTP_HOST": "smtp.example.com",
               "SMTP_USER": "user@example.com", "SMTP_PASSWORD": "not-a-real-password-123",
               "SKALD_BEACON_ORIGINS": "https://www.example.com"}
        cfg = entrypoint.render_config(env)
        self.assertEqual(cfg["site"], {"name": "example.com",
                                       "hosts": ["example.com", "www.example.com"]})
        self.assertEqual(cfg["dashboard"]["url"], "https://stats.example.com/traffic/example.com/")
        self.assertEqual(cfg["access"]["base_url"], "https://stats.example.com")
        self.assertEqual(cfg["mail"]["from"], "owner@example.com")
        self.assertTrue(cfg["mail"]["daily"])
        self.assertEqual((cfg["mail"]["user_env"], cfg["mail"]["password_env"]),
                         ("SMTP_USER", "SMTP_PASSWORD"))
        self.assertTrue(cfg["beacon"]["enabled"])
        text = json.dumps(cfg)
        self.assertNotIn("not-a-real-password-123", text, "a secret's value never goes in the config")

    def test_the_config_reads_without_pyyaml(self):
        from skald.config import tiny_yaml  # noqa: F401 - the fallback exists
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yml"
            path.write_text(json.dumps(entrypoint.render_config({"SKALD_SITE": "example.com"})))
            from skald.config import load_config, site_name
            self.assertEqual(site_name(load_config(path)), "example.com")

    def test_bad_values_stop_the_start(self):
        for env in ({"SKALD_SITE": "../etc"}, {"SKALD_TIMEZONE": "Europe/../x y"},
                    {"SKALD_BASE_URL": "stats.example.com"}):
            with self.subTest(env=env), self.assertRaises(SystemExit):
                entrypoint.render_config(env)


class DockerNginx(nr.Coverage, unittest.TestCase):
    """The image's nginx is DEPLOY.md's, so the same route checks hold."""
    text = (ROOT / "docker" / "nginx.conf").read_text()

    @staticmethod
    def _part(text: str, name: str) -> str:
        return text[text.index(f"# ---- {name} level ----"):text.index(f"# ---- end {name} level ----")]

    config = nr.Config(_part.__func__(text, "http"), _part.__func__(text, "server"), {})

    def test_generated_from_deploy_md(self):
        self.assertEqual(self.text, build_nginx.build(nr.DEPLOY.read_text()),
                         "docker/nginx.conf is out of date: python3 docker/build-nginx-conf.py")

    def test_container_parts(self):
        self.assertIn("absolute_redirect off;", self.text)
        self.assertIn("include /tmp/skald-nginx/trusted.conf;", self.text)
        self.assertIn("location = / { return 302 /traffic/; }", self.text)
        self.assertNotIn("include snippets/", self.text)


class NoSecrets(unittest.TestCase):
    EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
    IPV4 = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?:/\d{1,2})?(?![\w.])")
    ALLOWED_NETS = [ipaddress.ip_network(n) for n in (
        "127.0.0.0/8", "0.0.0.0/32", "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24",
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
    SECRETISH = re.compile(r"(?i)(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20}|sk_live_|"
                           r"xox[bp]-|AKIA[0-9A-Z]{16}|\$2[aby]\$\d\d\$)")

    def test_the_files_exist(self):
        for path in FILES:
            with self.subTest(path=path.name):
                self.assertTrue(path.exists(), path)

    def test_no_secret_or_real_address(self):
        for path in FILES:
            text = path.read_text()
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIsNone(self.SECRETISH.search(text))
                for m in self.EMAIL.finditer(text):
                    self.assertTrue(m.group(1).endswith("example.com"), m.group(0))
                for m in self.IPV4.finditer(text):
                    addr = ipaddress.ip_address(m.group(1))
                    self.assertTrue(any(addr in n for n in self.ALLOWED_NETS), m.group(0))
                for line in text.splitlines():
                    # A password or token may be named, never given a value.
                    m = re.search(r"(?i)(?<![a-z])(PASSWORD|TOKEN|SECRET|API_KEY)\s*[:=]\s*['\"]?"
                                  r"(?![.\-$])([\w+/=!@%^&*.-]{6,})", line)
                    if m and not line.lstrip().startswith(("#", "-", "|", "`")):
                        self.fail(f"{line.strip()!r} gives a secret a value")

    def test_compose_takes_secrets_from_the_environment_only(self):
        text = (ROOT / "docker-compose.yml").read_text()
        self.assertIn('SMTP_PASSWORD: "${SMTP_PASSWORD:-}"', text)
        self.assertIn('"${SKALD_BIND:-127.0.0.1}:${SKALD_HOST_PORT:-8080}:8080"', text,
                      "recipe A: only this machine reaches the container by default")
        self.assertIn(":/logs:ro", text, "the access log is mounted read-only")


class Dockerfile(unittest.TestCase):
    text = (ROOT / "docker" / "Dockerfile").read_text()

    def test_pinned_small_non_root(self):
        base = re.search(r"^FROM (\S+)", self.text, re.M).group(1)
        self.assertRegex(base, r"^python:3\.1[1-9]\.\d+-slim-\w+$", "a pinned slim tag")
        # Not `USER skald`: the entrypoint drops to it itself
        # (tests/test_hosting_container.py, DropPrivileges).
        self.assertIn("--uid \"$UID\"", self.text)
        self.assertIn("HEALTHCHECK", self.text)
        self.assertIn("PyYAML==", self.text)

    def test_the_image_leaves_local_files_out(self):
        ignore = (ROOT / ".dockerignore").read_text().split()
        for must in (".git", "config.yml", "*.sqlite", "HANDOVER", "deployments"):
            self.assertIn(must, ignore)


class InstallScript(unittest.TestCase):
    text = (ROOT / "install.sh").read_text()

    def test_strict_and_root(self):
        self.assertTrue(self.text.startswith("#!/usr/bin/env bash\n"))
        self.assertRegex(self.text, r"(?m)^set -euo pipefail$")
        self.assertIn('[ "$(id -u)" = 0 ]', self.text)

    def test_uninstall_keeps_data_unless_purge(self):
        self.assertIn("--uninstall) UNINSTALL=1", self.text)
        self.assertIn("--purge) PURGE=1", self.text)
        body = self.text[self.text.index("uninstall() {"):self.text.index("pick_python() {")]
        purge_at = body.index('if [ "$PURGE" = 1 ]')
        self.assertNotIn('rm -rf "$APP"', body[:purge_at], "data and code go only with --purge")
        self.assertIn('rm -f "$CRON_FILE"', body[:purge_at])

    def test_a_command_on_the_path_and_uninstall_removes_it(self):
        self.assertIn("CMD_FILE=/usr/local/bin/skald\n", self.text)
        body = self.text[self.text.index("install_command() {"):self.text.index("first_run() {")]
        # The command runs the script file by its full path, as the service user, with the config.
        self.assertIn('exec $PY $APP/bin/skald --config $ETC/config.yml "\\$@"', body)
        self.assertIn("exec runuser -u $SVC_USER", body)
        self.assertIn("  install_command\n", self.text[self.text.index("main() {"):])
        uninstall = self.text[self.text.index("uninstall() {"):self.text.index("pick_python() {")]
        purge_at = uninstall.index('if [ "$PURGE" = 1 ]')
        self.assertIn('"$CMD_FILE"', uninstall[:purge_at])

    def test_an_interpreter_always_gets_the_scripts_full_path(self):
        # `$PY bin/skald` from inside $APP worked by luck of the cwd; the public copy's
        # command is bin/<name>, and the package folder beside it is no script.
        self.assertIsNone(re.search(r"\$\{?PY\}?\s+ti\.py", self.text))
        self.assertGreaterEqual(self.text.count("$PY $APP/bin/skald"), 3)

    def test_idempotent_config_and_env(self):
        self.assertIn('if [ -f "$cfg" ]; then', self.text)
        self.assertIn('if [ -f "$env" ]; then return; fi', self.text)

    def test_python_311(self):
        self.assertIn("sys.version_info < (3, 11)", self.text)

    @unittest.skipUnless(shutil.which("shellcheck"), "shellcheck is not installed here")
    def test_shellcheck(self):
        got = subprocess.run(["shellcheck", "-x", str(ROOT / "install.sh")],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)


if __name__ == "__main__":
    unittest.main()

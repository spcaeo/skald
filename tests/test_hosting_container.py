"""The container on hosting platforms (docs/HOSTING.md).

  * every SKALD_* setting the entrypoint and scheduler read is passed
    through by docker-compose.yml and listed in docs/INSTALL.md;
  * the visitor's address behind a platform's proxy: SKALD_TRUSTED_PROXIES
    and SKALD_REAL_IP_HEADER become nginx realip lines, none by default;
  * `peers` reads the addresses connected to the port from /proc/net;
  * a disk mounted for root is given to the image's user, then the
    entrypoint drops to that user before it does anything else;
  * render.yaml at the root (Render's button) is deploy/render.yaml;
  * the Sites table names the drain formats.
"""
from __future__ import annotations

import importlib.util
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


entrypoint = _load("skald_docker_entrypoint_hosting", ROOT / "docker" / "entrypoint.py")

# Read by the code but not settings: paths inside the image, the image's own
# port, a mounted config, and the scheduler's test-only zone.
INTERNAL = {"SKALD_APP", "SKALD_DATA", "SKALD_JOB_LOGS", "SKALD_CONFIG", "SKALD_PORT",
            "SKALD_SCHEDULE_TZ"}


def settings_read() -> set[str]:
    names = set()
    for path in (ROOT / "docker" / "entrypoint.py", ROOT / "docker" / "scheduler.py"):
        names |= set(re.findall(r"""["'](SKALD_[A-Z_]+)["']""", path.read_text()))
    return names - INTERNAL


class ComposeAndInstall(unittest.TestCase):
    def test_the_list_is_found(self):
        got = settings_read()
        for name in ("SKALD_INGEST", "SKALD_LOG_DIR", "SKALD_TRUSTED_PROXIES",
                     "SKALD_REAL_IP_HEADER", "SKALD_LIVE_MINUTES"):
            self.assertIn(name, got)

    def test_compose_passes_every_setting(self):
        text = (ROOT / "docker-compose.yml").read_text()
        for name in sorted(settings_read()):
            with self.subTest(name=name):
                self.assertRegex(text, rf'(?m)^\s+{name}: "\$\{{{name}:-[^}}]*\}}"$')

    def test_install_md_lists_every_setting(self):
        text = (ROOT / "docs" / "INSTALL.md").read_text()
        for name in sorted(settings_read()):
            with self.subTest(name=name):
                self.assertIn(f"`{name}`", text)

    def test_compose_trusts_its_own_proxies(self):
        text = (ROOT / "docker-compose.yml").read_text()
        self.assertIn('SKALD_TRUSTED_PROXIES: "${SKALD_TRUSTED_PROXIES:-private}"', text)
        self.assertIn('SKALD_REAL_IP_HEADER: "${SKALD_REAL_IP_HEADER:-X-Real-IP}"', text)


class TrustedProxies(unittest.TestCase):
    conf = staticmethod(entrypoint.trusted_conf)

    def test_none_by_default(self):
        for env in ({}, {"SKALD_TRUSTED_PROXIES": ""}, {"SKALD_TRUSTED_PROXIES": "none"}):
            with self.subTest(env=env):
                text = self.conf(env)
                self.assertNotIn("set_real_ip_from", text, "exposed directly: $remote_addr")
                self.assertNotIn("real_ip_header", text)

    def test_ranges_and_forwarded_for(self):
        text = self.conf({"SKALD_TRUSTED_PROXIES": "10.0.0.0/8, 100.64.0.0/10 fdaa::/16"})
        self.assertEqual([ln for ln in text.splitlines() if not ln.startswith("#")], [
            "set_real_ip_from 10.0.0.0/8;", "set_real_ip_from 100.64.0.0/10;",
            "set_real_ip_from fdaa::/16;", "real_ip_header X-Forwarded-For;",
            "real_ip_recursive on;"])

    def test_private_and_a_header_of_choice(self):
        text = self.conf({"SKALD_TRUSTED_PROXIES": "private",
                          "SKALD_REAL_IP_HEADER": "Fly-Client-IP"})
        for net in entrypoint.PRIVATE:
            self.assertIn(f"set_real_ip_from {net};", text)
        self.assertIn("real_ip_header Fly-Client-IP;", text)

    def test_one_address_and_a_loose_range(self):
        text = self.conf({"SKALD_TRUSTED_PROXIES": "192.0.2.7,198.51.100.9/24"})
        self.assertIn("set_real_ip_from 192.0.2.7/32;", text)
        self.assertIn("set_real_ip_from 198.51.100.0/24;", text)

    def test_bad_values_stop_the_start(self):
        for env in ({"SKALD_TRUSTED_PROXIES": "10.0.0.0/8;evil"},
                    {"SKALD_TRUSTED_PROXIES": "proxy.example.com"},
                    {"SKALD_TRUSTED_PROXIES": "0.0.0.0/0"},       # everyone could claim any address
                    {"SKALD_TRUSTED_PROXIES": "::/0"},
                    {"SKALD_TRUSTED_PROXIES": "10.0.0.0/8", "SKALD_REAL_IP_HEADER": "X; evil"}):
            with self.subTest(env=env), self.assertRaises(SystemExit):
                self.conf(env)

    def test_nginx_takes_the_header_from_the_include(self):
        text = (ROOT / "docker" / "nginx.conf").read_text()
        self.assertNotRegex(text, r"(?m)^\s*real_ip_header ", "the header is the include's, not fixed")
        self.assertIn("include /tmp/skald-nginx/trusted.conf;", text)
        # The helpers hear the address nginx settled on: the visitor's.
        self.assertIn("proxy_set_header X-Real-IP $remote_addr;", text)


class Peers(unittest.TestCase):
    TCP = """\
  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid
   0: 00000000:1F90 00000000:0000 0A 00000000:00000000 00:00000000 00000000 10001
   1: 0400000A:1F90 0700000A:D2F0 01 00000000:00000000 00:00000000 00000000 10001
   2: 0100007F:2231 0100007F:9C40 01 00000000:00000000 00:00000000 00000000 10001
"""
    TCP6 = """\
  sl  local_address                         remote_address                        st
   0: 0000000000000000FFFF00000400000A:1F90 0000000000000000FFFF00000900000A:C350 01 0
   1: 00000000000000000000000001000000:1F90 0000AAFD000000000000000002000000:C351 01 0
"""

    def test_connected_addresses_on_the_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tcp").write_text(self.TCP)
            (Path(tmp) / "tcp6").write_text(self.TCP6)
            self.assertEqual(entrypoint.peers(8080, Path(tmp)),
                             ["10.0.0.7", "10.0.0.9", "fdaa::2"])
            self.assertEqual(entrypoint.peers(8081, Path(tmp)), [])

    def test_no_proc(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(entrypoint.peers(8080, Path(tmp)), [])


class DropPrivileges(unittest.TestCase):
    def run_as_root(self, data: Path, owner: int) -> list:
        calls: list = []
        stat = os.stat_result

        def fake_lstat(path, *a, **k):
            real = os.stat(path, follow_symlinks=False)
            return stat((real.st_mode, real.st_ino, real.st_dev, real.st_nlink, owner, owner,
                         real.st_size, 0, 0, 0))
        with mock.patch.object(entrypoint, "DATA", data), \
             mock.patch.object(entrypoint.os, "getuid", return_value=0), \
             mock.patch.object(entrypoint.os, "lstat", side_effect=fake_lstat), \
             mock.patch.object(entrypoint.os, "lchown", side_effect=lambda p, u, g: calls.append(("chown", str(p), u, g))), \
             mock.patch.object(entrypoint.os, "chmod", side_effect=lambda p, m: calls.append(("chmod", str(p), m))), \
             mock.patch.object(entrypoint.os, "initgroups", side_effect=lambda n, g: calls.append(("groups", n, g))), \
             mock.patch.object(entrypoint.os, "setgid", side_effect=lambda g: calls.append(("setgid", g))), \
             mock.patch.object(entrypoint.os, "setuid", side_effect=lambda u: calls.append(("setuid", u))), \
             mock.patch.object(entrypoint, "app_user", return_value=("skald", 10001, 10001)), \
             mock.patch.object(entrypoint, "log"), \
             mock.patch.dict(entrypoint.os.environ, {}, clear=False):
            entrypoint.drop_privileges(fix_data=True)
        return calls

    def test_a_root_owned_disk_is_given_to_the_user_then_root_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "backups").mkdir()
            (data / "backups" / "one.sqlite.gz").write_text("x")
            (data / "history.sqlite").write_text("x")
            calls = self.run_as_root(data, owner=0)
        chowned = {Path(c[1]).relative_to(data).as_posix() for c in calls if c[0] == "chown"}
        self.assertEqual(chowned, {".", "backups", "backups/one.sqlite.gz", "history.sqlite"})
        self.assertTrue(all(c[2:] == (10001, 10001) for c in calls if c[0] == "chown"))
        order = [c[0] for c in calls if c[0] in ("groups", "setgid", "setuid")]
        self.assertEqual(order, ["groups", "setgid", "setuid"], "the uid goes last")
        self.assertEqual(calls[-1], ("setuid", 10001))

    def test_an_owned_disk_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = self.run_as_root(Path(tmp), owner=10001)
        self.assertFalse([c for c in calls if c[0] in ("chown", "chmod")])
        self.assertEqual(calls[-1], ("setuid", 10001))

    def test_not_root_nothing_changes(self):
        with mock.patch.object(entrypoint.os, "getuid", return_value=10001), \
             mock.patch.object(entrypoint.os, "setuid") as setuid, \
             mock.patch.object(entrypoint.os, "lchown") as lchown:
            entrypoint.drop_privileges(fix_data=True)
        setuid.assert_not_called()
        lchown.assert_not_called()

    def test_every_command_drops_before_it_runs(self):
        text = (ROOT / "docker" / "entrypoint.py").read_text()
        body = text[text.index("def main("):]
        self.assertLess(body.index("drop_privileges("), body.index("os.execvp"))
        self.assertLess(body.index("drop_privileges("), body.index("ensure_visitor_key()"))

    def test_the_image_starts_as_root_only_to_hand_over(self):
        text = (ROOT / "docker" / "Dockerfile").read_text()
        self.assertNotRegex(text, r"(?m)^USER ", "the entrypoint drops to uid 10001 itself")
        self.assertIn("--uid \"$UID\"", text)


class RenderAndSites(unittest.TestCase):
    def test_render_yaml_at_the_root_is_the_deploy_copy(self):
        self.assertEqual((ROOT / "render.yaml").read_text(),
                         (ROOT / "deploy" / "render.yaml").read_text(),
                         "keep render.yaml and deploy/render.yaml the same: cp render.yaml deploy/")

    def test_the_sites_table_names_the_drains(self):
        text = (ROOT / "skald" / "webapp" / "js" / "tabs" / "sitesadmin.js").read_text()
        self.assertIn('vercel_json: "Vercel log drain"', text)
        self.assertIn('netlify_json: "Netlify log drain"', text)

    def test_the_public_readme_has_the_render_button(self):
        # In this repo the public README is the overlay; in the public copy it is the README.
        readme = ROOT / "public" / "README.md"
        text = (readme if readme.exists() else ROOT / "README.md").read_text()
        self.assertIn("https://render.com/deploy?repo=https://github.com/spcaeo/skald", text)


if __name__ == "__main__":
    unittest.main()

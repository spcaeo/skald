"""Settings > Connections: the shipper's install kit (skald/kit, POST
<page>/sites/kit, connections_api.py) and the deployment's make-kit.sh that
builds the same zip. The zip's contents and modes, every placeholder filled,
no token unless asked (then only a valid sending token of that site, in a 0600
file install.sh moves into place), and who may ask for it.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B  # noqa: E402
from ingest_support import TenantServer  # noqa: E402

from skald import kit  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
URL = "https://stats.example.com/traffic-ingest/example.com"
IMAGE = "registry.example.com/skald:2"
LEFT = re.compile(rb"__[A-Z][A-Z_]*__")
TOKEN = "skald_ab12cd34_" + "x" * 43


def unzip(data: bytes) -> dict:
    """{name: (bytes, unix mode)} of the zip's files."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {i.filename: (z.read(i), (i.external_attr >> 16) & 0o7777)
                for i in z.infolist() if not i.is_dir()}


class Build(unittest.TestCase):
    def build(self, method="docker", token=None):
        return unzip(kit.build("example.com", URL, method, "https://stats.example.com/traffic/example.com/",
                               "https://stats.example.com/traffic/example.com/#help?part=troubleshooting-connections",
                               IMAGE, "/opt/skald/tools/skald-ship.py", token))

    def test_the_docker_kit(self):
        got = self.build()
        d = "skald-ship-example.com/"
        self.assertEqual(sorted(got), [d + n for n in ("README.txt", "check.sh", "install.sh", "uninstall.sh")])
        for name, (data, mode) in got.items():
            self.assertIsNone(LEFT.search(data), name)
            self.assertEqual(mode, 0o755 if name.endswith(".sh") else 0o644, name)
            for word in (b"skaldanalytics", b"ghcr.io", b"Teams"):
                self.assertNotIn(word, data, name)
        install = got[d + "install.sh"][0].decode()
        self.assertIn(f'URL="{URL}"', install)
        self.assertIn(f'IMAGE="{IMAGE}"', install)
        self.assertIn("/opt/skald/tools/skald-ship.py", install)
        self.assertIn('SITE="example.com"', install)
        self.assertIn('METHOD="docker"', got[d + "check.sh"][0].decode())
        readme = got[d + "README.txt"][0].decode()
        self.assertIn("sudo bash check.sh", readme)
        self.assertIn("#help?part=troubleshooting-connections", readme)

    def test_the_systemd_kit_carries_the_shipper(self):
        got = self.build("systemd")
        d = "skald-ship-example.com/"
        self.assertIn(d + "skald-ship.py", got)
        self.assertEqual(got[d + "skald-ship.py"][0], (ROOT / "tools" / "skald-ship.py").read_bytes())
        self.assertEqual(got[d + "skald-ship.py"][1], 0o755)
        self.assertIn("systemctl", got[d + "install.sh"][0].decode())
        self.assertIn('METHOD="systemd"', got[d + "uninstall.sh"][0].decode())

    def test_no_token_unless_asked_and_then_a_private_file(self):
        for method in kit.METHODS:
            got = self.build(method)
            self.assertNotIn("skald-ship-example.com/ship-token", got)
            self.assertFalse(any(b"skald_" in data and re.search(rb"skald_[0-9a-f]{8}_", data)
                                 for n, (data, _) in got.items() if not n.endswith(".py")))
            got = self.build(method, TOKEN)
            data, mode = got["skald-ship-example.com/ship-token"]
            self.assertEqual(data, (TOKEN + "\n").encode())
            self.assertEqual(mode, 0o600)
            # install.sh takes it, saves it 0640 (umask 027) for root and the shipper's
            # group, and deletes the kit's copy.
            install = got["skald-ship-example.com/install.sh"][0].decode()
            self.assertIn('"$HERE/ship-token"', install)
            self.assertIn("umask 027", install)
            self.assertIn('rm -f "$HERE/ship-token"', install)
            self.assertRegex(install, r'chgrp (adm|"\$USER_NAME") ')
        with self.assertRaises(ValueError):
            self.build("docker", "not a token")

    def test_refusals(self):
        with self.assertRaises(ValueError):
            kit.build("Example.com", URL, "docker", "", "", IMAGE)
        with self.assertRaises(ValueError):            # the address must be this site's
            kit.build("example.org", URL, "docker", "", "", IMAGE)
        with self.assertRaises(ValueError) as why:     # no image, no Docker kit
            kit.build("example.com", URL, "docker", "", "", None)
        self.assertIn("ingest.kit_image", str(why.exception))
        with self.assertRaises(ValueError):            # nothing a shell would run
            kit.build("example.com", URL, "docker", "https://x.example.com/$(id)", "", IMAGE)

    def test_the_image_comes_from_config_then_the_environment(self):
        self.assertEqual(kit.image({"ingest": {"kit_image": IMAGE}}), IMAGE)
        old = os.environ.pop("SKALD_KIT_IMAGE", None)
        try:
            self.assertIsNone(kit.image({}))
            self.assertFalse(kit.available({})["docker"])
            os.environ["SKALD_KIT_IMAGE"] = "registry.example.com/other:3"
            self.assertEqual(kit.image({}), "registry.example.com/other:3")
            self.assertTrue(kit.available({})["docker"])
        finally:
            os.environ.pop("SKALD_KIT_IMAGE", None)
            if old is not None:
                os.environ["SKALD_KIT_IMAGE"] = old

    @unittest.skipUnless(shutil.which("bash"), "bash not installed")
    def test_make_kit_sh_builds_the_same_zip_without_a_token(self):
        script = ROOT / "deployments/skaldanalytics.com/ship-kit/make-kit.sh"
        if not script.exists():
            self.skipTest("deployments/ is not in the public copy")
        with tempfile.TemporaryDirectory() as tmp:
            done = subprocess.run(["bash", str(script),
                                   "example.com", tmp], capture_output=True, text=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)
            got = unzip((Path(tmp) / "skald-ship-example.com.zip").read_bytes())
        self.assertEqual(len(got), 4)
        self.assertNotIn("skald-ship-example.com/ship-token", got)
        for name, (data, _) in got.items():
            self.assertIsNone(LEFT.search(data), name)


class Endpoint(TenantServer):
    def setUp(self):
        super().setUp()
        self.config["ingest"]["kit_image"] = IMAGE

    def test_an_admin_downloads_the_kit_with_or_without_the_token(self):
        cookie, csrf = self.session("admin@example.com")
        got = self.post(f"/traffic/{A}/sites/kit", {"site": A, "method": "docker"}, cookie, csrf)
        self.assertEqual(got.status, 200, got.raw[:200])
        self.assertEqual(got.header("Content-Type"), "application/zip")
        self.assertIn(f'filename="skald-ship-{A}.zip"', got.header("Content-Disposition"))
        files = unzip(got.raw)
        install = files[f"skald-ship-{A}/install.sh"][0].decode()
        self.assertIn(f"https://www.example.com/traffic-ingest/{A}", install)
        self.assertNotIn(f"skald-ship-{A}/ship-token", files)
        token = self.token(self.alpha, sites=[A])
        got = self.post(f"/traffic/{A}/sites/kit", {"site": A, "method": "systemd", "include_token": True,
                                                   "token": token}, cookie, csrf)
        self.assertEqual(got.status, 200, got.raw[:200])
        data, mode = unzip(got.raw)[f"skald-ship-{A}/ship-token"]
        self.assertEqual(data.decode().strip(), token)
        self.assertEqual(mode, 0o600)
        # A token is put in only when asked, even when sent.
        got = self.post(f"/traffic/{A}/sites/kit", {"site": A, "method": "docker", "token": token}, cookie, csrf)
        self.assertNotIn(f"skald-ship-{A}/ship-token", unzip(got.raw))

    def test_only_a_sending_token_of_that_site_goes_in(self):
        cookie, csrf = self.session("owner@example.com")
        reader = self.token(self.alpha, scopes=("read",), sites=[A])
        foreign = self.token(self.beta, sites=[B])
        for bad in (reader, foreign, "skald_00000000_" + "y" * 43):
            got = self.post(f"/traffic/{A}/sites/kit", {"site": A, "method": "docker", "include_token": True,
                                                       "token": bad}, cookie, csrf)
            self.assertEqual(got.status, 400, got.json)
            self.assertNotIn(bad, got.raw.decode())

    def test_who_may_ask(self):
        cookie, csrf = self.session("viewer@example.com")
        got = self.post(f"/traffic/{A}/sites/kit", {"site": A, "method": "docker"}, cookie, csrf)
        self.assertEqual(got.status, 403)
        cookie, csrf = self.session("owner@example.com")
        got = self.post(f"/traffic/{A}/sites/kit", {"site": A, "method": "docker"}, cookie, None)
        self.assertEqual(got.status, 403)                      # no CSRF value
        got = self.post(f"/traffic/{A}/sites/kit", {"site": B, "method": "docker"}, cookie, csrf)
        self.assertEqual(got.status, 404)                      # another organisation's site
        got = self.call("GET", f"/traffic/{A}/sites/kit", cookie=cookie)
        self.assertEqual(got.status, 405)

    def test_without_an_image_the_docker_kit_says_why(self):
        del self.config["ingest"]["kit_image"]
        old = os.environ.pop("SKALD_KIT_IMAGE", None)
        try:
            cookie, csrf = self.session("owner@example.com")
            got = self.post(f"/traffic/{A}/sites/kit", {"site": A, "method": "docker"}, cookie, csrf)
            self.assertEqual(got.status, 400)
            self.assertIn("ingest.kit_image", got.json["error"])
            listing = self.call("GET", f"/traffic/{A}/sites", cookie=cookie).json
            self.assertFalse(listing["kit"]["docker"])
            self.assertTrue(listing["kit"]["systemd"])
        finally:
            if old is not None:
                os.environ["SKALD_KIT_IMAGE"] = old


if __name__ == "__main__":
    unittest.main()

"""The one-file lead helpers (skald/kit/leadfiles.py): every template
fills with no placeholder left, the secret is in a file only when given (and
never in the README), the WordPress plugin comes as an installable zip, and
the Python helper's request is one the hook receiver keeps. The PHP and Node
files are syntax-checked when php and node are installed. Hosts are
example.com; the secrets are made up."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import SECRET, FakeHandler  # noqa: E402
from test_conversions_hooks import Base  # noqa: E402

from skald.kit import leadfiles  # noqa: E402

URL = "https://stats.example.com/traffic-hooks/example.com/lead"
MADE = "skh_" + "Made0Up0Secret0For0The0Tests0Only0x"


class Files(unittest.TestCase):
    def test_every_file_fills_with_no_placeholder_left(self):
        for secret in (None, MADE):
            got = leadfiles.files("example.com", URL, secret)
            self.assertEqual(sorted(got), sorted(leadfiles.FILES))
            for name, data in got.items():
                text = data.decode("utf-8")
                for key in leadfiles.PLACEHOLDERS:
                    self.assertNotIn(f"__{key}__", text, name)
                if name != "README.md":
                    self.assertIn(URL, text, name)
                    self.assertIn("SKALD_LEAD_SECRET", text, name)

    def test_the_secret_is_in_the_code_only_when_given(self):
        bare = leadfiles.files("example.com", URL, None)
        for name, data in bare.items():
            self.assertNotIn(MADE.encode(), data, name)
            self.assertNotIn(b"skh_", data, name)
        self.assertIn(b"Nothing secret is in this file", bare["skald-lead.php"])
        self.assertIn(b"define('SKALD_LEAD_SECRET'", bare[leadfiles.PLUGIN])
        given = leadfiles.files("example.com", URL, MADE)
        for name in ("skald-lead.php", "skald-lead.cjs", "skald_lead.py", leadfiles.PLUGIN):
            self.assertEqual(given[name].count(MADE.encode()), 1, name)
            self.assertIn(b"move it", given[name], name)
        self.assertNotIn(MADE.encode(), given["README.md"], "the README never holds it")

    def test_the_address_and_the_secret_are_checked(self):
        self.assertEqual(leadfiles.address("example.com", "https://stats.example.com/"), URL)
        self.assertEqual(leadfiles.address("example.com", URL + "/"), URL)
        for bad in ("ftp://stats.example.com", "https://stats.example.com/other",
                    URL.replace("example.com/lead", "example.org/lead"), URL + "?x=1",
                    "https://stats.example.com'/", 'https://a"b.example.com', ""):
            with self.subTest(url=bad), self.assertRaises(ValueError):
                leadfiles.files("example.com", bad, None)
        with self.assertRaises(ValueError):
            leadfiles.files("Example.com", URL, None)
        for bad in ("short", "has space in it here", "quote'in'it-123456", "back\\slash123456"):
            with self.subTest(secret=bad), self.assertRaises(ValueError):
                leadfiles.files("example.com", URL, bad)

    def test_one_file_per_language(self):
        names = {lang: leadfiles.one(lang, "example.com", URL, None)[:1] for lang in
                 leadfiles.LANGS}
        self.assertEqual(names, {"php": ("skald-lead.php",), "node": ("skald-lead.cjs",),
                                 "python": ("skald_lead.py",),
                                 "wordpress": ("skald-leads.zip",)})
        for name, _data, _mime in (leadfiles.one(lang, "example.com", URL, None)
                                   for lang in leadfiles.LANGS):
            self.assertFalse(name.endswith((".js", ".mjs")), "Gmail refuses zips holding those")
        with self.assertRaises(ValueError):
            leadfiles.one("ruby", "example.com", URL, None)

    def test_the_plugin_zip_installs_as_one_folder(self):
        name, data, mime = leadfiles.one("wordpress", "example.com", URL, MADE)
        self.assertEqual(mime, "application/zip")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(z.namelist(), ["skald-leads/", "skald-leads/skald-leads.php"])
            text = z.read("skald-leads/skald-leads.php").decode()
        self.assertIn("Plugin Name: Skald Leads", text)
        self.assertIn(MADE, text)
        for hook in ("wpcf7_mail_sent", "wpforms_process_complete", "gform_after_submission",
                     "elementor_pro/forms/new_record", "ninja_forms_after_submission"):
            self.assertIn(hook, text)
        self.assertIn("'blocking' => false", text)


@unittest.skipUnless(shutil.which("php") or shutil.which("node"), "neither php nor node here")
class Syntax(unittest.TestCase):
    def test_php_and_node_files_parse(self):
        for secret in (None, MADE):
            got = leadfiles.files("example.com", URL, secret)
            with tempfile.TemporaryDirectory() as tmp:
                for name, data in got.items():
                    (Path(tmp) / Path(name).name).write_bytes(data)
                checks = []
                if shutil.which("php"):
                    checks += [["php", "-l", str(Path(tmp) / n)]
                               for n in ("skald-lead.php", "skald-leads.php")]
                if shutil.which("node"):
                    checks.append(["node", "--check", str(Path(tmp) / "skald-lead.cjs")])
                for cmd in checks:
                    run = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


class PythonHelperIsKept(Base):
    """The filled skald_lead.py signs a request the receiver keeps."""

    def setUp(self):
        super().setUp()
        self.now = time.time()          # the helper signs with the real clock

    def helper(self, secret):
        data = leadfiles.files("example.com", URL, secret)["skald_lead.py"]
        path = Path(self.tmp.name) / "skald_lead.py"
        path.write_bytes(data)
        spec = importlib.util.spec_from_file_location("skald_lead_under_test", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def send(self, mod, *args, **kw):
        """Call skald_lead; the request it would send goes to the receiver."""
        sent = []

        def urlopen(req, timeout=None):
            self.assertLessEqual(timeout, 3)
            sent.append(req)
            headers = {k: v for k, v in req.header_items()}
            status, _ = self.rx.http(FakeHandler(
                req.full_url.split("stats.example.com", 1)[1], req.data, headers))
            answer = mock.MagicMock(status=status)
            answer.__enter__.return_value = answer
            return answer

        with mock.patch("urllib.request.urlopen", urlopen):
            got = mod.skald_lead(*args, **kw)
        return got, sent

    def test_the_embedded_secret_signs_a_kept_lead(self):
        mod = self.helper(SECRET)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SKALD_LEAD_SECRET", None)
            got, sent = self.send(mod, "PY-1", "contact", email="person@example.com",
                                  name="A Person", label="sales", vid="skv_" + "Q" * 22)
        self.assertTrue(got)
        self.assertEqual(sent[0].full_url, URL)
        self.assertIn("X-skald-signature", dict(sent[0].header_items()))
        self.assertEqual(json.loads(sent[0].data)["external_ref"], "PY-1")
        self.assertEqual(self.rows("SELECT external_ref, action, label, vid FROM conversions"),
                         [("PY-1", "contact", "sales", "skv_" + "Q" * 22)])

    def test_the_environment_wins_and_a_wrong_secret_is_refused(self):
        mod = self.helper(None)
        with mock.patch.dict(os.environ, {"SKALD_LEAD_SECRET": SECRET}):
            self.assertTrue(self.send(mod, "PY-2", "demo")[0])
        with mock.patch.dict(os.environ, {"SKALD_LEAD_SECRET": "skh_not_the_secret_x"}):
            self.assertFalse(self.send(mod, "PY-3", "demo")[0])
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SKALD_LEAD_SECRET", None)
            got, sent = self.send(mod, "PY-4", "demo")
        self.assertEqual((got, sent), (False, []), "no secret anywhere: nothing sent")
        self.assertEqual(self.rows("SELECT external_ref FROM conversions"), [("PY-2",)])
        self.assertEqual(self.rows("SELECT outcome FROM deliveries ORDER BY id"),
                         [("recorded",), ("bad_signature",)])

    def test_it_never_raises(self):
        mod = self.helper(None)

        def broken(req, timeout=None):
            raise OSError("network down")

        with mock.patch.dict(os.environ, {"SKALD_LEAD_SECRET": SECRET}), \
                mock.patch("urllib.request.urlopen", broken):
            self.assertFalse(mod.skald_lead("PY-5", "demo"))
            self.assertFalse(mod.skald_lead("PY-6", "demo", when=object()))


if __name__ == "__main__":
    unittest.main()

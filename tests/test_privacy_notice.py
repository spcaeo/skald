"""2.15.0: wording for a site's privacy notice, made from its settings
(people/notice.py). Every setting that changes the wording, in every
combination: IP addresses (full, short, off), leads' names and emails (full,
anonymous), the script tag (off, on, on with visitor IDs); and the city file.
"""
from __future__ import annotations

import itertools
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, Server  # noqa: E402

from skald.people import notice, policy  # noqa: E402

TAGS = {"none": {}, "tag": {"enabled": True}, "ids": {"enabled": True, "visitor_ids": True}}


def config(mode: str, identity: str, tag: str, days: int = 395, city: bool = False) -> dict:
    out = {"privacy": {"keep_ips": mode, "keep_days": days},
           "conversions": {"identity": identity}, "beacon": dict(TAGS[tag])}
    if city:
        out["logs"] = {"city_db": "/var/lib/example/city.mmdb"}
    return out


class Wording(unittest.TestCase):
    def test_every_combination(self):
        for mode, identity, tag in itertools.product(policy.MODES, ("full", "anonymous"), TAGS):
            with self.subTest(mode=mode, identity=identity, tag=tag):
                got = notice.wording(config(mode, identity, tag, days=30))
                text = got["text"]
                self.assertEqual(text, got["intro"] + "\n\n"
                                 + "\n".join(f"- {i}" for i in got["items"]))
                self.assertEqual(got["note"], "A starting point, not legal advice. Your "
                                              "notice must match your own situation.")
                self.assertEqual(got["uses"], {"ip_mode": mode, "keep_days": 30,
                                               "identity": identity,
                                               "script_tag": tag != "none",
                                               "visitor_ids": tag == "ids"})
                # Always: the log, no cookie from it, how to ask for deletion.
                self.assertIn("sets no cookie and stores nothing on your device", text)
                self.assertIn(notice.CONTACT, text)
                self.assertIn(notice.LOG_DAYS, text)
                # IP addresses.
                self.assertEqual("kept as 203.0.113.0" in text, mode == "short")
                self.assertEqual("first 48 bits" in text, mode == "short")
                self.assertEqual("We do not keep IP addresses" in text, mode == "off")
                self.assertEqual("We keep each visit's IP address with its browser" in text,
                                 mode == "full")
                self.assertEqual("for 30 days" in text, mode != "off")
                # Names and emails.
                self.assertEqual("we keep your name and email" in text, identity == "full")
                self.assertEqual("keep no name or email" in text, identity == "anonymous")
                self.assertEqual("or the email you used" in text, identity == "full")
                # The script tag.
                self.assertEqual("small script" in text, tag != "none")
                self.assertEqual("Do Not Track or Global Privacy Control" in text, tag != "none")
                self.assertEqual(notice.CONSENT in text, tag != "none")
                self.assertEqual("random visitor ID in your browser's local storage" in text,
                                 tag == "ids")
                self.assertEqual("skald_vid" in text, tag == "ids")
                self.assertEqual("keeps no ID and stores nothing" in text, tag == "tag")
                # Every placeholder listed is in the text, and only those.
                for mark in got["placeholders"]:
                    self.assertIn(mark, text)
                self.assertEqual(len(got["placeholders"]), 2 + (tag != "none") + (tag == "ids"))

    def test_days_city_and_one_day(self):
        got = notice.wording(config("full", "full", "none", days=1, city=True))["text"]
        self.assertIn("for 1 day,", got)
        self.assertIn("country and city", got)
        short = notice.wording(config("short", "full", "none", city=False))["text"]
        self.assertIn("The visit's country is looked up from the full address", short)

    def test_an_upgraded_install_reads_as_its_settings_do(self):
        # Unset on an upgraded install: off and anonymous (policy.legacy), as the page says.
        import sqlite3
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db = sqlite3.connect(Path(tmp) / "history.sqlite")
            db.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
            db.execute("INSERT INTO meta VALUES ('privacy_legacy', 'x')")
            db.commit()
            db.close()
            got = notice.wording({}, Path(tmp))
            self.assertEqual(got["uses"]["ip_mode"], "off")
            self.assertEqual(got["uses"]["identity"], "anonymous")
            self.assertIn("We do not keep IP addresses", got["text"])

    def test_no_product_or_host_name(self):
        for mode, identity, tag in itertools.product(policy.MODES, ("full", "anonymous"), TAGS):
            text = notice.wording(config(mode, identity, tag))["text"].lower()
            # The product name is renamed in the public copy and the cookie keeps it
            # (skald_vid), so only host names and links are ruled out.
            for word in ("skaldanalytics", "example.com", "http://", "https://"):
                self.assertNotIn(word, text)


class InThePage(Server):
    def test_the_settings_page_sends_it_and_a_save_makes_it_again(self):
        cookie, csrf = self.session("owner@example.com")
        got = self.call("GET", f"/traffic/{A}/settings", cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        self.assertIn("items", got.json["notice"])
        self.assertEqual(got.json["notice"]["uses"]["ip_mode"], "full")
        saved = self.post(f"/traffic/{A}/settings/save", {"privacy.keep_ips": "short"},
                          cookie, csrf)
        self.assertEqual(saved.status, 200, saved.json)
        self.assertEqual(saved.json["settings"]["privacy.keep_ips"]["value"], "short")
        self.assertEqual(saved.json["notice"]["uses"]["ip_mode"], "short")
        self.assertIn("kept as 203.0.113.0", saved.json["notice"]["text"])
        saved = self.post(f"/traffic/{A}/settings/save", {"privacy.keep_ips": False},
                          cookie, csrf)
        self.assertEqual(saved.json["settings"]["privacy.keep_ips"]["value"], "off")
        self.assertIn("We do not keep IP addresses", saved.json["notice"]["text"])

    def test_the_page_draws_the_choice_and_the_card_from_the_real_answer(self):
        import json
        import shutil
        import subprocess
        import tempfile
        if not shutil.which("node"):
            self.skipTest("node not installed")
        cookie, _ = self.session("owner@example.com")
        got = self.call("GET", f"/traffic/{A}/settings", cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "answer.json"
            path.write_text(json.dumps(got.json))
            js = Path(__file__).resolve().parent / "js" / "settings-privacy.mjs"
            done = subprocess.run(["node", str(js)], capture_output=True, text=True,
                                  timeout=60, env={**os.environ, "SETTINGS_JSON": str(path)})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("settings-privacy: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()

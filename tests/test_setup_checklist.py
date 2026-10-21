"""Overview's "Set up this site" checklist (js/tabs/checklist.js, setup-items.js)
and its Set up dialogs (js/tabs/setup-*.js), drawn in node from a real helper's
answers (tests/js/setup-checklist.mjs): GET settings, integrations, sites and
sites/status, the script tag's status before and after a page opened with it,
a lead hook's secret and signed test, and the saves of the privacy and mail
choices. The lines are plain (no server words outside "For your server admin"),
each open line has a Set up button, each dialog walks its steps, and the mail
to the developer holds the steps and never the secret.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, ORIGIN  # noqa: E402
from ingest_support import TenantServer  # noqa: E402


class Drawn(TenantServer):
    def setUp(self):
        super().setUp()
        self.spool = Path(self._tmp.name) / "spool"
        self.config["beacon"] = {"enabled": True, "origins": [ORIGIN], "spool": str(self.spool)}

    def get(self, path, cookie):
        got = self.call("GET", f"/traffic/{A}/{path}", cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        return got.json

    def test_the_checklist_and_its_dialogs_from_the_real_answers(self):
        if not shutil.which("node"):
            self.skipTest("node not installed")
        cookie, csrf = self.session("owner@example.com")
        given = {"site": A, "settings": self.get("settings", cookie),
                 "integ": self.get(f"integrations?site={A}", cookie),
                 "sites": self.get("sites", cookie),
                 "status_before": self.get(f"sites/status?site={A}", cookie)}
        # The doctor's script line is the technical one the page must not show plainly.
        script = next(x for x in given["integ"]["status"] if x["id"] == "script")
        self.assertEqual(script["state"], "NEEDS ATTENTION", script)
        self.assertIn("nginx", script["fix"])
        self.assertEqual(given["status_before"]["beacon"]["last_open_at"], None)
        # A page opened with the tag: the status says so.
        self.spool.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).date().isoformat()
        (self.spool / f"opens-{day}.jsonl").write_text('{"p": "/"}\n')
        given["status_after"] = self.get(f"sites/status?site={A}", cookie)
        self.assertTrue(given["status_after"]["beacon"]["last_open_at"])
        # The lead hook: its secret, made once, and a signed test.
        made = self.post(f"/traffic/{A}/integrations/secret", {"site": A, "tool": "lead"}, cookie, csrf)
        self.assertEqual(made.status, 200, made.json)
        given["secret"] = made.json
        tested = self.post(f"/traffic/{A}/integrations/test", {"site": A, "tool": "lead"}, cookie, csrf)
        self.assertEqual(tested.status, 200, tested.json)
        given["hooktest"] = tested.json
        given["integ_after"] = self.get(f"integrations?site={A}", cookie)
        lead = next(t for t in given["integ_after"]["tools"] if t["tool"] == "lead")
        self.assertEqual(lead["state"], "ready", lead)
        # The privacy and mail choices, saved as the dialogs save them.
        saved = self.post(f"/traffic/{A}/settings/save", {"privacy.keep_ips": "short",
                                                          "conversions.identity": "full"}, cookie, csrf)
        self.assertEqual(saved.status, 200, saved.json)
        self.assertEqual(saved.json["settings"]["privacy.keep_ips"]["source"], "site")
        given["saved_privacy"] = saved.json
        saved = self.post(f"/traffic/{A}/settings/save", {"mail.to": ["owner@example.com"]},
                          cookie, csrf)
        self.assertEqual(saved.status, 200, saved.json)
        given["saved_mail"] = saved.json
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "answers.json"
            path.write_text(json.dumps(given))
            js = Path(__file__).resolve().parent / "js" / "setup-checklist.mjs"
            done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60,
                                  env={**os.environ, "SETUP_JSON": str(path)})
        self.assertEqual(done.returncode, 0, done.stderr[-3000:])
        self.assertIn("setup-checklist: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()

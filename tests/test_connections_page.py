"""Settings > Connections and the "Add a site" wizard, drawn in node from a
real helper's answers (tests/js/connections.mjs): GET sites, GET tokens and
GET sites/status after a batch was shipped with a sending token, and POST
sites/detect (the site check) for a new site and for this one, from canned
answers (site_fetch's lookup and network stubbed: nothing leaves the machine).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402

from skald import site_fetch  # noqa: E402

NGINX = {"Server": "nginx/1.28.3 (Ubuntu)", "X-Powered-By": "Next.js"}
PROXIED = {"Server": "cloudflare", "CF-Ray": "8a1b2c3d4e5f-LHR"}
CANNED = {"https://www.example.org/": (200, NGINX), "https://example.org/": (200, NGINX),
          f"https://{A}/": (200, PROXIED)}


def canned():
    def answer(scheme, host, address, port, method, target, timeout, max_bytes):
        url = f"{scheme}://{host}{target}"
        status, headers = CANNED.get(url, (404, {}))
        return site_fetch.Answer(status, {k.lower(): [v] for k, v in headers.items()}, b"",
                                 url, address)
    return mock.patch.multiple(site_fetch, lookup=lambda host, port: ["8.8.8.8"],
                               open_pinned=answer)


class Drawn(TenantServer):
    def test_the_page_and_the_dialogs_from_the_real_answers(self):
        if not shutil.which("node"):
            self.skipTest("node not installed")
        self.config["ingest"]["kit_image"] = "registry.example.com/skald:2"
        sending = self.token(self.alpha, sites=[A], name=f"Sending logs: {A}")
        self.token(self.alpha, scopes=("read",), sites=[A], name="Weekly sheet")
        self.assertEqual(self.ship(A, sending, lines(4)).status, 200)
        cookie, _ = self.session("owner@example.com")
        got = {"site": A}
        for key, path in (("sites", "sites"), ("tokens", "tokens"), ("status", f"sites/status?site={A}")):
            answer = self.call("GET", f"/traffic/{A}/{path}", cookie=cookie)
            self.assertEqual(answer.status, 200, answer.json)
            got[key] = answer.json
        self.assertTrue(got["sites"]["kit"]["docker"])
        cookie, csrf = self.session("admin@example.com")
        link = self.post(f"/traffic/{A}/sites/share", {"site": A, "task": "send", "method": "docker",
                                                     "days": 7}, cookie, csrf).json["link"]
        got["share_info"] = self.call("GET", "/" + link.split("/", 3)[3] + "/info").json
        self.assertTrue(got["share_info"]["ok"])
        with canned(), redirect_stderr(StringIO()):
            for key, address in (("detect_new", "www.example.org"), ("detect_here", A)):
                answer = self.post(f"/traffic/{A}/sites/detect", {"address": address}, cookie, csrf)
                self.assertEqual(answer.status, 200, answer.json)
                got[key] = answer.json
        self.assertEqual(got["detect_new"]["found"]["recommended_method"], "docker")
        self.assertEqual(got["detect_here"]["found"]["recommended_method"], "cloudflare")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "answers.json"
            path.write_text(json.dumps(got))
            js = Path(__file__).resolve().parent / "js" / "connections.mjs"
            done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60,
                                  env={**os.environ, "CONN_JSON": str(path)})
        self.assertEqual(done.returncode, 0, done.stderr[-3000:])
        self.assertIn("connections: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()

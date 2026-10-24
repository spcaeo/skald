"""The one line for an AI agent (kit/agent.py on the beacon helper,
POST <page>/sites/agentlink and sites/agentstatus in kit_api.py).

The store never holds the code or a usable key; the keys go out once, to curl
or Wget only, and never on HEAD; /steps, install.sh and the lead files hold no
secret; the report keeps only its known fields; the dashboard never sees the
token or the lead secret. Old install links work as before. Test data:
example.com and RFC 5737 addresses; the keys are made here.
"""
from __future__ import annotations

import http.client
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B  # noqa: E402
from ingest_support import TenantServer  # noqa: E402

from skald.accounts import apitokens, auditlog, site_setup  # noqa: E402
from skald.conversions import secrets_store  # noqa: E402
from skald.kit import agent, link, pack  # noqa: E402

IMAGE = "registry.example.com/skald:2"
TOKEN = "skald_ab12cd34_" + "Zq7Lm2Np9Rs4Tv8Wx1Yb5Cd3Fg6Hj0Kk2Mp7Qr9St4Uv"[:43]
LEAD = "skh_" + "Lq3Wm8Xr1Tz6Vb4Nc9Pd2Hf7Jg5Kk0Ms3Qa8Ry1Ue6Io"
FIELDS = {"url": "https://stats.example.com/traffic-ingest/example.com",
          "dashboard": "https://stats.example.com/traffic/example.com/",
          "help": "https://stats.example.com/traffic/example.com/#help",
          "image": IMAGE, "ship_path": "/opt/skald/tools/skald-ship.py",
          "base": "https://stats.example.com",
          "lead_url": "https://stats.example.com/traffic-hooks/example.com/lead",
          "tag": '<script src="https://stats.example.com/traffic-js/skald.js" '
                 'data-site="example.com" defer></script>'}
FOUND = {"reachable": True, "https": True, "server": "nginx", "framework": "nextjs",
         "recommended_method": "docker", "asset_prefixes": ["/_next/"]}
WEB_READERS = ("Mozilla/5.0 (compatible; Claude-User/1.0)", "python-requests/2.31",
               "node-fetch/1.0", "")


def make(folder, **kw):
    args = dict(lead_secret=LEAD, lead_note="included", found=FOUND)
    args.update(kw)
    return agent.make(folder, "example.com", TOKEN, "ab12cd34", FIELDS, **args)[:2]


def report_key(folder, code) -> str:
    """The report key, from the entry's seal (before the keys are taken)."""
    entry = agent.find(folder, code)
    return link.unseal(entry["sealed_report"], code, agent.REPORT_LABEL)


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def entry(self, code):
        return json.loads((self.folder / link.FILE).read_text())["links"][link.digest(code)]

    def test_the_store_holds_no_key_and_no_code(self):
        code, expires = make(self.folder)
        path = self.folder / link.FILE
        raw = path.read_text()
        key = report_key(self.folder, code)
        self.assertGreaterEqual(len(key), 32)
        for secret in (TOKEN, TOKEN[15:], LEAD, LEAD[4:], code, key):
            self.assertNotIn(secret, raw)
        self.assertEqual(self.entry(code)["report_key"], agent._key_hash(key))
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertAlmostEqual(expires - time.time(), 24 * 3600, delta=5)
        self.assertEqual(self.entry(code)["kind"], "agent")

    def test_the_states(self):
        now = time.time()
        code, _ = make(self.folder, now=now)
        lid = agent.link_id(code)
        self.assertEqual(lid, link.digest(code)[:16])
        self.assertEqual(agent.status(self.folder, "example.com", lid)["state"], "waiting")
        agent.opened(self.folder, code)
        got = agent.status(self.folder, "example.com", lid)
        self.assertEqual(got["state"], "opened")
        self.assertTrue(got["opened_at"].endswith("Z"))
        self.assertIsNone(got["keys_at"])
        key = report_key(self.folder, code)
        state, _, keys = agent.take(self.folder, code)
        self.assertEqual((state, keys), ("ok", {"token": TOKEN, "lead": LEAD, "report_key": key}))
        got = agent.status(self.folder, "example.com", lid)
        self.assertEqual(got["state"], "keys_taken")
        self.assertTrue(got["keys_at"])
        self.assertEqual(agent.take(self.folder, code)[0], "keys_taken")
        self.assertEqual(agent.status(self.folder, "example.com", "0" * 16)["state"], "unknown")
        self.assertEqual(agent.status(self.folder, "example.com", "../x")["state"], "unknown")
        late = now + 24 * 3600 + 1
        other, _ = make(self.folder, now=now)
        self.assertEqual(agent.status(self.folder, "example.com", agent.link_id(other),
                                      now=late)["state"], "expired")
        self.assertEqual(agent.take(self.folder, other, now=late)[0], "expired")
        self.assertEqual(agent.status(self.folder, "example.com", lid, now=late)["state"],
                         "keys_taken", "keys taken stays so after the expiry")

    def test_only_the_sites_own_entries(self):
        code, _ = make(self.folder)
        self.assertEqual(agent.status(self.folder, "other.example.com",
                                      agent.link_id(code))["state"], "unknown")
        install, _ = link.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS)
        self.assertEqual(agent.status(self.folder, "example.com",
                                      agent.link_id(install))["state"], "unknown")

    def test_the_lead_secret_has_its_own_seal(self):
        code, _ = make(self.folder)
        entry = self.entry(code)
        self.assertEqual(link.unseal(entry["sealed_lead"], code, agent.LEAD_LABEL), LEAD)
        self.assertNotEqual(link.unseal(entry["sealed_lead"], code), LEAD)
        self.assertNotEqual(link.unseal(entry["sealed_lead"], "y" * 43, agent.LEAD_LABEL), LEAD)
        agent.take(self.folder, code)
        entry = self.entry(code)
        self.assertIsNone(entry["sealed"])
        self.assertIsNone(entry["sealed_lead"])
        code, _ = make(self.folder, lead_secret=None, lead_note="none")
        self.assertIsNone(self.entry(code)["sealed_lead"])
        self.assertIsNone(agent.take(self.folder, code)[2]["lead"])

    def test_install_link_functions_never_hand_out_an_agent_code(self):
        code, _ = make(self.folder)
        self.assertEqual(link.look(self.folder, code)[0], "unknown")
        self.assertEqual(link.take(self.folder, code)[0], "unknown")
        self.assertIsNotNone(self.entry(code)["sealed"], "nothing burned")
        install, _ = link.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS)
        self.assertIsNone(agent.find(self.folder, install))
        self.assertEqual(agent.take(self.folder, install)[0], "unknown")
        self.assertEqual(link.take(self.folder, install)[2], TOKEN)

    def test_the_token_never_has_the_install_links_seal(self):
        """An older image's link.take ignores `kind`: it must not open an agent's token."""
        code, _ = make(self.folder)
        entry = self.entry(code)
        self.assertNotEqual(link.unseal(entry["sealed"], code), TOKEN)
        self.assertEqual(link.unseal(entry["sealed"], code, agent.TOKEN_LABEL), TOKEN)
        self.assertNotEqual(link.unseal(entry["sealed_report"], code),
                            link.unseal(entry["sealed_report"], code, agent.REPORT_LABEL))

    def test_an_expired_code_is_wiped_then_dropped(self):
        now = time.time()
        code, _ = make(self.folder, now=now)
        install, _ = link.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS, now=now)
        agent.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS,
                   now=now + 24 * 3600 + 60)             # a write after the expiry
        kept = json.loads((self.folder / link.FILE).read_text())["links"]
        self.assertIn(link.digest(code), kept, "kept a day, so the wizard says expired")
        self.assertIsNone(kept[link.digest(code)]["sealed"])
        self.assertIsNone(kept[link.digest(code)]["sealed_lead"])
        self.assertNotIn(link.digest(install), kept, "an install link is dropped as before")
        agent.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS,
                   now=now + 48 * 3600 + 60)
        kept = json.loads((self.folder / link.FILE).read_text())["links"]
        self.assertNotIn(link.digest(code), kept)

    def test_cancel(self):
        code, _ = make(self.folder)
        lid = agent.link_id(code)
        self.assertEqual(agent.cancel(self.folder, "other.example.com", lid), [],
                         "only the site's own codes")
        self.assertEqual(agent.cancel(self.folder, "example.com", "nothex"), [])
        self.assertEqual(agent.cancel(self.folder, "example.com", lid), [(lid, "ab12cd34")])
        entry = self.entry(code)
        self.assertIsNone(entry["sealed"])
        self.assertIsNone(entry["sealed_lead"])
        self.assertTrue(entry["cancelled_at"])
        got = agent.status(self.folder, "example.com", lid)
        self.assertEqual(got["state"], "cancelled")
        self.assertTrue(got["cancelled_at"])
        self.assertEqual(agent.take(self.folder, code)[2], None)
        self.assertEqual(agent.keep_report(self.folder, code, {"hosting": "x"}, None), "refused")
        self.assertEqual(agent.cancel(self.folder, "example.com", lid), [], "once")
        taken, _ = make(self.folder)
        agent.take(self.folder, taken)
        self.assertEqual(agent.cancel(self.folder, "example.com", agent.link_id(taken)),
                         [(agent.link_id(taken), None)], "its token was handed out: kept")

    def test_a_new_line_cancels_the_older_unused_ones(self):
        now = time.time()
        live, _ = make(self.folder)
        opened, _ = make(self.folder)
        agent.opened(self.folder, opened)
        taken, _ = make(self.folder)
        agent.take(self.folder, taken)
        old, _ = make(self.folder, now=now - 25 * 3600)
        other = agent.make(self.folder, "other.example.com", TOKEN, "ff00ff00", FIELDS)[0]
        new, _, got = agent.make(self.folder, "example.com", TOKEN, "cc00cc00", FIELDS,
                                 replace=True)
        self.assertEqual(sorted(got), sorted([(agent.link_id(live), "ab12cd34", "cancelled"),
                                              (agent.link_id(opened), "ab12cd34", "cancelled"),
                                              (agent.link_id(old), "ab12cd34", "expired")]))
        for code, want in ((new, "waiting"), (taken, "keys_taken"), (old, "expired"),
                           (live, "cancelled"), (opened, "cancelled")):
            self.assertEqual(agent.status(self.folder, "example.com",
                                          agent.link_id(code))["state"], want)
        self.assertEqual(agent.status(self.folder, "other.example.com",
                                      agent.link_id(other))["state"], "waiting")
        third, _, got = agent.make(self.folder, "example.com", TOKEN, "dd00dd00", FIELDS,
                                   replace=True)
        self.assertEqual(got, [(agent.link_id(new), "cc00cc00", "cancelled")],
                         "an expired line's token is handed back once only")

    def test_a_line_whose_clock_reads_earlier_still_ends_the_one_stored_first(self):
        """Two calls may read the clock in one order and take the lock in the other:
        whatever its made_at, a line already in the store is the older one."""
        now = time.time()
        first, _ = make(self.folder, now=now + 0.02, replace=True)
        second, _ = make(self.folder, now=now, replace=True)
        self.assertEqual(agent.state(agent.find(self.folder, first)), "cancelled")
        self.assertEqual(agent.state(agent.find(self.folder, second)), "waiting")

    def test_two_lines_made_at_once_leave_exactly_one_live(self):
        """Two tabs asking sites/agentlink together: the later wins, never neither."""
        start = threading.Barrier(8)
        made = []

        def one(n):
            start.wait()
            made.append(agent.make(self.folder, "example.com", TOKEN, f"{n:08x}", FIELDS,
                                   replace=True)[0])
        threads = [threading.Thread(target=one, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        states = [agent.status(self.folder, "example.com", agent.link_id(c))["state"]
                  for c in made]
        self.assertEqual(sorted(states), ["cancelled"] * 7 + ["waiting"])

    def test_the_report_is_cleaned_and_capped(self):
        raw = {"hosting": "own server\n\x1b[31m", "server": "nginx", "framework": "Next.js",
               "log_path": "/var/log/nginx/access.log",
               "asset_paths": ["/_next/static/", "no-slash", "/a b", 7, "/_next/static/"]
               + [f"/p{n}/" for n in range(40)],
               "script_tag": "app/layout.tsx",
               "leads": [{"tool": "contact form", "file": "app/api/contact/route.ts",
                          "secret": "x"}, "not a dict", {}],
               "privacy": {"keep_ips": "yes", "days": 30, "notice_url": "javascript:x",
                           "extra": 1},
               "nextjs_log_field": "true", "changed_files": ["app/layout.tsx"] * 3,
               "left_for_user": [f"thing {n}" for n in range(30)],
               "notes": f"token {TOKEN} and {LEAD} " + "n" * 3000,
               "evil": "<script>", "token": TOKEN}
        got = agent.clean_report(raw)
        self.assertEqual(set(got), {"hosting", "server", "framework", "log_path", "asset_paths",
                                    "script_tag", "leads", "privacy", "changed_files",
                                    "left_for_user", "notes"})
        self.assertEqual(got["hosting"], "own server [31m")
        self.assertEqual(got["asset_paths"][0], "/_next/static/")
        self.assertEqual(len(got["asset_paths"]), 10)     # as many as site.asset_prefixes takes
        self.assertNotIn("no-slash", got["asset_paths"])
        self.assertEqual(got["leads"], [{"tool": "contact form",
                                         "file": "app/api/contact/route.ts"}])
        self.assertEqual(got["privacy"], {"days": 30})
        self.assertEqual(got["changed_files"], ["app/layout.tsx"])
        self.assertEqual(len(got["left_for_user"]), 20)
        self.assertEqual(len(got["notes"]), 1000)
        dumped = json.dumps(got)
        self.assertNotIn(TOKEN[15:], dumped)
        self.assertNotIn(LEAD[4:], dumped)
        self.assertIn("[removed]", got["notes"])
        got = agent.clean_report({"privacy": {"keep_ips": False, "days": True,
                                              "notice_url": "https://example.com/privacy"},
                                  "nextjs_log_field": False})
        self.assertEqual(got, {"privacy": {"keep_ips": False,
                                           "notice_url": "https://example.com/privacy"},
                               "nextjs_log_field": False})
        for bad in (None, [], "text", 3):
            with self.assertRaises(ValueError):
                agent.clean_report(bad)

    def test_the_steps_hold_no_secret(self):
        code, _ = make(self.folder)
        text = agent.steps(agent.find(self.folder, code), code, "https://stats.example.com")
        for secret in (TOKEN, TOKEN[15:], LEAD, LEAD[4:]):
            self.assertNotIn(secret, text)
        self.assertIsNone(re.search(r"__[A-Z][A-Z_]*__", text))
        here = f"https://stats.example.com/traffic-kit/{code}"
        for must in (f"{here}/keys", f"{here}/install.sh", f"{here}/leads/", f"{here}/report",
                     FIELDS["url"], FIELDS["lead_url"], FIELDS["tag"],
                     "$HOME/.config/skald/example.com.env", "curl -sS -X POST -H @- ",
                     "X-Skald-Report-Key", "git ls-files --error-unmatch wp-config.php",
                     "case A", "Web server: `nginx`", "rsc_prefetch=$http_next_router_prefetch",
                     "ask the user one plain question and wait", "IP addresses",
                     "SKALD_SHIP_TOKEN", "SKALD_LEAD_SECRET` in the keys file",
                     "Never paste the code or the keys anywhere but the commands shown here"):
            self.assertIn(must, text)
        code, _ = make(self.folder, lead_secret=None, lead_note="env", found=None)
        text = agent.steps(agent.find(self.folder, code), code, "")
        self.assertIn("the Skald server's environment", text)
        self.assertIn("the check did not run", text)
        code, _ = make(self.folder, found={"server": "__HI__", "framework": "__SITE__",
                                           "server_detail": "a`b " + "x" * 500,
                                           "hosts": ["__KEYS_URL__", "ok.example.com"],
                                           "reason": "made by __LEFT__"})
        text = agent.steps(agent.find(self.folder, code), code, "")
        self.assertIsNone(re.search(r"__[A-Z][A-Z_]*__", text))
        self.assertIn("- Web server: `_ _HI_ _`", text)
        self.assertIn("- Its addresses: `_ _KEYS_URL_ _`, `ok.example.com`", text)
        self.assertIn("- Why that way: made by _ _LEFT_ _", text)
        detail = re.search(r"- Server details: `([^`]*)`", text).group(1)
        self.assertEqual(len(detail), agent.FOUND_MOST)
        self.assertTrue(detail.startswith("a'b "))
        guide = agent.guide("https://stats.example.com")
        self.assertIn("curl -fsSL https://stats.example.com/traffic-kit/<code>/steps", guide)
        self.assertNotIn("is fine", guide)
        self.assertNotIn(code, guide)


class BeaconHelper(unittest.TestCase):
    """/traffic-kit/ through the beacon helper's own handler."""

    def setUp(self):
        from skald.beacon_server import Limiter, Sink, make_handler
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        config = {"site": {"name": "example.com", "hosts": ["example.com"]},
                  "history": {"db": str(self.folder / "history.sqlite")},
                  "access": {"base_url": "https://stats.example.com"}}
        config_path = self.folder / "config.yml"
        config_path.write_text("")
        sink = Sink(config, self.folder / "beacon")
        sink.config_path = config_path
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(sink, Limiter(), set()))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.n = 0

    def call(self, path, agent_name="curl/8.5.0", method="GET", body=None, address=None,
             headers=None):
        self.n += 1                     # each try from its own address: the limit is per address
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
        hdrs = {"User-Agent": agent_name, "X-Real-IP": address or f"198.51.100.{self.n}"}
        hdrs.update(headers or {})
        conn.request(method, path, body=body, headers=hdrs)
        got = conn.getresponse()
        data = got.read()
        conn.close()
        return got, data

    def text(self, *args, **kw):
        got, data = self.call(*args, **kw)
        return got, data.decode()

    def state(self, code):
        return agent.status(self.folder, "example.com", agent.link_id(code))["state"]

    def test_llms_txt(self):
        for n in range(12):                             # no limit: it holds no code
            got, body = self.text("/traffic-kit/llms.txt", agent_name="Claude-User",
                                  address="203.0.113.7")
            self.assertEqual(got.status, 200)
        self.assertIn("https://stats.example.com/traffic-kit/<code>/steps", body)
        self.assertIn("curl or wget", body)
        self.assertIn("Never paste the code or the keys anywhere but the commands", body)
        self.assertEqual(got.getheader("Cache-Control"), "no-store")
        self.assertIn("noindex", got.getheader("X-Robots-Tag"))
        got, _ = self.text("/traffic-kit/llms.txt", method="POST", body=b"{}")
        self.assertEqual(got.status, 405)

    def test_the_bare_code_never_answers_markdown_to_curl(self):
        code, _ = make(self.folder)
        for tool in ("curl/8.5.0", "Wget/1.21.4"):
            got, body = self.text(f"/traffic-kit/{code}", agent_name=tool)
            self.assertEqual(got.status, 200)
            self.assertTrue(body.startswith("#!/bin/sh\n"), body)
            self.assertIn(f"read https://stats.example.com/traffic-kit/{code}/steps", body)
            self.assertTrue(body.rstrip().endswith("exit 1"))
            self.assertNotIn("##", body)
            self.assertNotIn(TOKEN, body)
        got, body = self.text(f"/traffic-kit/{code}", agent_name="Mozilla/5.0")
        self.assertEqual(got.status, 200)
        self.assertTrue(body.startswith("This code is for an AI agent: read "))
        self.assertEqual(self.state(code), "waiting", "never burned, never opened")
        self.assertIsNotNone(agent.find(self.folder, code)["sealed"])

    def test_steps_for_any_reader(self):
        code, _ = make(self.folder)
        got, body = self.text(f"/traffic-kit/{code}/steps", method="HEAD", agent_name="Mozilla/5.0")
        self.assertEqual(got.status, 200)
        self.assertEqual(self.state(code), "waiting", "HEAD opens nothing")
        got, body = self.text(f"/traffic-kit/{code}/steps", agent_name="Mozilla/5.0 Claude-User")
        self.assertEqual(got.status, 200)
        self.assertTrue(got.getheader("Content-Type").startswith("text/markdown"))
        self.assertTrue(body.startswith("# Set up Skald for example.com"))
        self.assertNotIn(TOKEN, body)
        self.assertNotIn(LEAD, body)
        self.assertEqual(self.state(code), "opened")
        first = agent.find(self.folder, code)["opened_at"]
        self.assertEqual(self.call(f"/traffic-kit/{code}/keys")[0].status, 200)
        got, body = self.text(f"/traffic-kit/{code}/steps")
        self.assertEqual(got.status, 200, "the steps stay readable after the keys are taken")
        self.assertEqual(agent.find(self.folder, code)["opened_at"], first)
        install, _ = link.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS)
        self.assertEqual(self.call(f"/traffic-kit/{install}/steps")[0].status, 404)
        with mock.patch.object(agent, "steps", side_effect=ValueError("left")):
            got, body = self.text(f"/traffic-kit/{code}/steps")
        self.assertEqual(got.status, 500)
        self.assertIn("The steps could not be made", body)
        self.assertEqual(self.call("/traffic-kit/" + "z" * 43 + "/steps")[0].status, 404)

    def test_the_keys_once_and_only_for_curl_or_wget(self):
        code, _ = make(self.folder)
        for reader in WEB_READERS:
            got, body = self.text(f"/traffic-kit/{code}/keys", agent_name=reader)
            self.assertEqual(got.status, 403, reader)
            self.assertIn("curl in a shell into a file; never with a web reader", body)
            self.assertNotIn(TOKEN, body)
        got, body = self.text(f"/traffic-kit/{code}/keys", method="HEAD")
        self.assertEqual((got.status, body), (200, ""))
        self.assertEqual(self.state(code), "waiting", "neither a web reader nor HEAD burns")
        key = report_key(self.folder, code)
        got, body = self.text(f"/traffic-kit/{code}/keys", agent_name="Wget/1.21.4")
        self.assertEqual(got.status, 200, body)
        env = dict(line.split("=", 1) for line in body.splitlines()
                   if line and not line.startswith("#"))
        self.assertEqual(env, {"SKALD_SITE": "example.com", "SKALD_INGEST_URL": FIELDS["url"],
                               "SKALD_INGEST_TOKEN": TOKEN, "SKALD_LEAD_URL": FIELDS["lead_url"],
                               "SKALD_LEAD_SECRET": LEAD, "SKALD_REPORT_KEY": key})
        self.assertEqual(got.getheader("Cache-Control"), "no-store")
        self.assertEqual(self.state(code), "keys_taken")
        got, body = self.text(f"/traffic-kit/{code}/keys")
        self.assertEqual(got.status, 410)
        self.assertIn("taken already", body)
        self.assertNotIn(TOKEN, body)
        self.assertEqual(self.call(f"/traffic-kit/{code}/keys", method="HEAD")[0].status, 410)
        raw = (self.folder / link.FILE).read_text()
        self.assertNotIn(TOKEN[15:], raw)
        self.assertNotIn(LEAD[4:], raw)
        code, _ = make(self.folder, lead_secret=None, lead_note="none", leads=False)
        got, body = self.text(f"/traffic-kit/{code}/keys")
        self.assertNotIn("SKALD_LEAD_SECRET", body)
        self.assertIn("SKALD_LEAD_URL=", body)

    def test_the_keys_file_quotes_each_value(self):
        """It is sourced with `.`: an odd value (an address from a Host header) stays a value."""
        entry = {"site": "example.com",
                 "fields": {"url": FIELDS["url"], "lead_url": "https://a.example.com/x y$(id)'"}}
        text = agent.keys_file(entry, {"token": TOKEN, "lead": LEAD, "report_key": "k" * 32})
        self.assertIn(f"SKALD_INGEST_TOKEN={TOKEN}\n", text, "a plain value stays plain")
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        env_file = folder / "keys.env"
        env_file.write_text(text)
        got = subprocess.run(["sh", "-c", '. "$1"; printf %s "$SKALD_LEAD_URL"', "sh",
                              str(env_file)], capture_output=True, text=True)
        self.assertEqual(got.stdout, "https://a.example.com/x y$(id)'")

    def test_an_expired_code(self):
        code, _ = make(self.folder, now=time.time() - 25 * 3600)
        for sub in ("/steps", "/keys", "/install.sh", "/leads/README.md"):
            got, body = self.text(f"/traffic-kit/{code}{sub}")
            self.assertEqual(got.status, 410, sub)
            self.assertIn("expired", body)
        got, body = self.text(f"/traffic-kit/{code}")
        self.assertIn("exit 1", body)
        self.assertIn("expired", body)

    def test_a_cancelled_code_answers_as_an_expired_one(self):
        code, _ = make(self.folder)
        key = report_key(self.folder, code)
        agent.cancel(self.folder, "example.com", agent.link_id(code))
        for sub in ("/steps", "/keys", "/install.sh", "/leads/README.md"):
            got, body = self.text(f"/traffic-kit/{code}{sub}")
            self.assertEqual(got.status, 410, sub)
            self.assertIn("was cancelled", body)
            self.assertNotIn(TOKEN, body)
        got, body = self.text(f"/traffic-kit/{code}")
        self.assertIn("was cancelled", body)
        self.assertIn("exit 1", body)
        self.assertEqual(self.post(code, {"hosting": "x"}, key)[0].status, 410)
        self.assertEqual(self.post(code, {"hosting": "x"})[0].status, 403)
        self.assertEqual(self.state(code), "cancelled")

    def test_the_installer_and_lead_files_hold_no_secret(self):
        code, _ = make(self.folder)
        got, body = self.text(f"/traffic-kit/{code}/install.sh", agent_name="Mozilla/5.0")
        self.assertEqual(got.status, 200, body[:200])
        self.assertTrue(body.startswith("#!/bin/bash"))
        self.assertIn(f"access log to {FIELDS['url']}.\n", body, "no 'over HTTPS' on an http base")
        self.assertIn("KIT_TOKEN=''", body)
        self.assertIn("SKALD_SHIP_TOKEN", body)
        self.assertNotIn(TOKEN, body)
        for name in ("skald-lead.php", "skald-lead.cjs", "skald_lead.py", "README.md",
                     "wordpress/skald-leads/skald-leads.php"):
            got, data = self.call(f"/traffic-kit/{code}/leads/{name}")
            self.assertEqual(got.status, 200, name)
            self.assertNotIn(LEAD.encode(), data)
            self.assertIn(FIELDS["lead_url"].encode(), data)
        got, data = self.call(f"/traffic-kit/{code}/leads/skald-leads.zip")
        self.assertEqual(got.getheader("Content-Type"), "application/zip")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(z.namelist(), ["skald-leads/", "skald-leads/skald-leads.php"])
        self.assertEqual(self.call(f"/traffic-kit/{code}/leads/../keys")[0].status, 404)
        self.assertEqual(self.call(f"/traffic-kit/{code}/nothing")[0].status, 404)
        self.assertEqual(self.state(code), "waiting")

    def post(self, code, body, key=None):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if key is not None:
            headers[agent.REPORT_HEADER] = key
        got, data = self.call(f"/traffic-kit/{code}/report", method="POST", body=raw,
                              headers=headers)
        return got, json.loads(data or b"null")

    def test_the_report_needs_the_report_key(self):
        code, _ = make(self.folder)
        got, body = self.text(f"/traffic-kit/{code}/keys")
        key = re.search(r"^SKALD_REPORT_KEY=(\S+)$", body, re.M).group(1)
        for wrong in (None, "", "x" * 32, key[:-1] + ("A" if key[-1] != "A" else "B")):
            got, answer = self.post(code, {"hosting": "forged"}, wrong)
            self.assertEqual(got.status, 403, wrong)
            self.assertIn("X-Skald-Report-Key", answer["error"])
        status = agent.status(self.folder, "example.com", agent.link_id(code))
        self.assertIsNone(status["report"], "nothing kept")
        self.assertIsNone(status["reported_at"])
        got, answer = self.post(code, {"hosting": "own server"}, key)
        self.assertEqual((got.status, answer), (200, {"ok": True}))
        self.assertEqual(agent.status(self.folder, "example.com",
                                      agent.link_id(code))["report"], {"hosting": "own server"})

    def test_the_report_header_through_a_pipe_as_the_steps_say(self):
        """steps.md step 8: the key goes to curl as a header through a pipe (-H @-), never
        on a command line or in a file (an agent run from an allow list may not redirect
        into a file)."""
        code, _ = make(self.folder)
        port = self.server.server_address[1]
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        keys = home / ".config" / "skald" / "example.com.env"
        script = (
            "umask 077 && mkdir -p ~/.config/skald && curl -sS -o "
            f"$HOME/.config/skald/example.com.env.part -w 'HTTP %{{http_code}}\\n' "
            f"'http://127.0.0.1:{port}/traffic-kit/{code}/keys' && grep -q '^SKALD_INGEST_TOKEN=' "
            "$HOME/.config/skald/example.com.env.part && mv $HOME/.config/skald/example.com.env.part "
            "$HOME/.config/skald/example.com.env\n"
            "grep '^SKALD_REPORT_KEY=' $HOME/.config/skald/example.com.env | "
            "sed 's/^SKALD_REPORT_KEY=/X-Skald-Report-Key: /' | "
            "curl -sS -X POST -H @- -H 'Content-Type: application/json' "
            "--data '{\"hosting\": \"own server\"}' "
            f"'http://127.0.0.1:{port}/traffic-kit/{code}/report'\n")
        if shutil.which("curl") is None:
            self.skipTest("curl is not installed")
        got = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                             env={**os.environ, "HOME": str(home)}, timeout=30)
        self.assertIn("HTTP 200", got.stdout, got.stderr)
        self.assertIn('{"ok": true}', got.stdout, got.stderr)
        self.assertEqual(stat.S_IMODE(keys.stat().st_mode), 0o600)
        self.assertFalse(keys.with_name("example.com.env.hdr").exists())
        self.assertNotIn(TOKEN, got.stdout + got.stderr)
        self.assertEqual(agent.status(self.folder, "example.com",
                                      agent.link_id(code))["report"], {"hosting": "own server"})

    def test_the_report(self):
        code, _ = make(self.folder)
        key = report_key(self.folder, code)
        got, body = self.post(code, {"hosting": "own server", "privacy": {"keep_ips": True,
                                     "days": 30}, "unknown": "dropped"}, key)
        self.assertEqual((got.status, body), (200, {"ok": True}))
        status = agent.status(self.folder, "example.com", agent.link_id(code))
        self.assertEqual(status["report"], {"hosting": "own server",
                                            "privacy": {"keep_ips": True, "days": 30}})
        self.assertTrue(status["reported_at"])
        self.assertEqual(self.post(code, b"not json", key)[0].status, 400)
        self.assertEqual(self.post(code, [1, 2], key)[0].status, 400)
        self.assertEqual(self.post(code, b"[" * 9000 + b"]" * 9000)[0].status, 413)
        self.assertEqual(self.post(code, b"[" * 3000 + b"]" * 3000)[0].status, 400)
        self.assertEqual(self.post(code, {"notes": "n" * 17000})[0].status, 413)
        self.assertEqual(self.post("z" * 43, {"hosting": "x"})[0].status, 404)
        install, _ = link.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS)
        self.assertEqual(self.post(install, {"hosting": "x"})[0].status, 404)
        got, _ = self.call(f"/traffic-kit/{code}/steps", method="POST", body=b"{}")
        self.assertEqual(got.status, 405)
        got, _ = self.call(f"/traffic-kit/{code}/report")
        self.assertEqual(got.status, 404)
        old, _ = make(self.folder, now=time.time() - 25 * 3600)
        self.assertEqual(self.post(old, {"hosting": "x"}, report_key(self.folder, old))[0].status,
                         410)

    def test_old_install_links_work_as_before(self):
        code, _ = link.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS)
        got, body = self.text(f"/traffic-kit/{code}", agent_name="Mozilla/5.0")
        self.assertIn(f"curl -fsSL https://stats.example.com/traffic-kit/{code} | sudo bash", body)
        got, body = self.text(f"/traffic-kit/{code}")
        self.assertTrue(body.startswith("#!/bin/bash"))
        self.assertIn(f"KIT_TOKEN='{TOKEN}'", body)
        got, body = self.text(f"/traffic-kit/{code}")
        self.assertIn("This install link was used or has expired", body)
        got, body = self.text("/traffic-kit/" + "z" * 43)
        self.assertIn("This install link was used or has expired", body)


class Nginx(unittest.TestCase):
    """DEPLOY.md's /traffic-kit/ block (docker/nginx.conf is built from it)."""

    def test_the_code_is_in_no_log(self):
        import test_nginx_routes as routes
        config = routes.from_deploy()
        kit = [loc for loc in config.locations if loc.arg == "/traffic-kit/"][0]
        self.assertEqual(kit.directives("error_log"), [["stderr", "crit"]],
                         "nginx's error lines hold the request line, so the code")
        self.assertEqual(kit.directives("access_log"), [["off"]])
        self.assertEqual(kit.directives("add_header"), [], "the helper sends them itself")
        report = routes.find(config.locations, "/traffic-kit/" + "a" * 43 + "/report")
        self.assertIn(report, kit.children)
        self.assertEqual(report.directives("error_log"), [], "inherited from the kit block")
        self.assertEqual(report.directives("client_max_body_size"), [["16k"]])
        self.assertEqual(report.directives("limit_except")[0], ["POST"])
        self.assertEqual(kit.directives("limit_except")[0], ["GET"])


class Endpoints(TenantServer):
    def setUp(self):
        super().setUp()
        self.config["ingest"]["kit_image"] = IMAGE
        patcher = mock.patch.object(pack, "lead_files", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cookie, self.csrf = self.session("admin@example.com")

    def audit(self, action):
        db = self.accounts_db()
        try:
            return auditlog.recent(db, self.alpha["id"], 50, action)
        finally:
            db.close()

    def agentlink(self, body=None):
        return self.post(f"/traffic/{A}/sites/agentlink", body or {"site": A},
                         self.cookie, self.csrf)

    def secrets(self):
        return secrets_store.load(secrets_store.path_for(self.config, self.live))

    def code_of(self, body):
        return re.search(r"use code ([A-Za-z0-9_-]{43}) ", body["line"]).group(1)

    def test_the_line_never_holds_a_key(self):
        got = self.agentlink()
        self.assertEqual(got.status, 200, got.json)
        body = got.json
        self.assertEqual(set(body), {"ok", "line", "llms_url", "steps_url", "expires_at",
                                     "token_id", "link_id", "cancelled"})
        self.assertEqual(body["cancelled"], 0)
        code = self.code_of(body)
        self.assertEqual(body["llms_url"], "https://www.example.com/traffic-kit/llms.txt")
        self.assertEqual(body["line"], f"set up Skald for {A} — read {body['llms_url']} and use "
                                       f"code {code} (works once, 24 hours)")
        self.assertEqual(body["steps_url"], f"https://www.example.com/traffic-kit/{code}/steps")
        self.assertEqual(body["link_id"], agent.link_id(code))
        self.assertTrue(body["expires_at"].endswith("Z"))
        raw = got.raw.decode()
        self.assertNotIn(f"skald_{body['token_id']}_", raw)
        self.assertNotIn("skh_", raw)
        lead = self.secrets()[secrets_store.key(A, "lead")]
        self.assertNotIn(lead, raw)
        db = self.accounts_db()
        try:
            made = [t for t in apitokens.listing(db, self.alpha["id"])
                    if t["id"] == body["token_id"]]
        finally:
            db.close()
        self.assertEqual(len(made), 1)
        self.assertIn("(AI agent set-up)", made[0]["name"])
        state, entry, keys = agent.take(self.live, code)
        token, secret = keys["token"], keys["lead"]
        self.assertEqual(state, "ok")
        self.assertTrue(token.startswith(f"skald_{body['token_id']}_"))
        self.assertEqual(secret, lead)
        self.assertEqual(entry["fields"]["lead_url"],
                         f"https://www.example.com/traffic-hooks/{A}/lead")
        rows = self.audit("kit.agentlink")
        self.assertTrue(rows)
        self.assertIn(body["link_id"], rows[0]["detail"])
        self.assertNotIn(code, json.dumps(rows))
        self.assertNotIn(token, json.dumps(rows))
        raw = (self.live / link.FILE).read_text()
        self.assertNotIn(code, raw)
        self.assertNotIn(token[15:], raw)

    def test_an_existing_lead_secret_is_copied_not_replaced(self):
        path = secrets_store.path_for(self.config, self.live)
        secrets_store.put(path, secrets_store.key(A, "lead"), LEAD)
        got = self.agentlink()
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(self.secrets()[secrets_store.key(A, "lead")], LEAD)
        self.assertEqual(agent.take(self.live, self.code_of(got.json))[2]["lead"], LEAD)
        db = self.accounts_db()
        try:
            rows = auditlog.recent(db, self.alpha["id"], 50, "hook.secret")
        finally:
            db.close()
        self.assertIn("copied (AI agent set-up)", rows[0]["detail"])

    def test_without_leads(self):
        got = self.agentlink({"site": A, "leads": False})
        self.assertEqual(got.status, 200, got.json)
        self.assertNotIn(secrets_store.key(A, "lead"), self.secrets())
        self.assertIsNone(agent.take(self.live, self.code_of(got.json))[2]["lead"])

    def test_the_status_shows_only_the_sites_own_entries(self):
        got = self.agentlink()
        lid = got.json["link_id"]
        ask = lambda body: self.post(f"/traffic/{A}/sites/agentstatus", body,  # noqa: E731
                                     self.cookie, self.csrf)
        status = ask({"site": A, "link_id": lid})
        self.assertEqual(status.status, 200, status.json)
        self.assertEqual(status.json["state"], "waiting")
        for key in ("opened_at", "keys_at", "reported_at", "report"):
            self.assertIsNone(status.json[key])
        agent.opened(self.live, self.code_of(got.json))
        self.assertEqual(ask({"site": A, "link_id": lid}).json["state"], "opened")
        other = agent.make(self.live, "other.example.com", TOKEN, "ab12cd34", FIELDS)[0]
        self.assertEqual(ask({"site": A, "link_id": agent.link_id(other)}).json["state"],
                         "unknown")
        self.assertEqual(ask({"site": B, "link_id": lid}).status, 404)
        self.assertEqual(ask({"site": A, "link_id": "nothex"}).status, 400)
        self.assertNotIn("skald_", json.dumps(ask({"site": A, "link_id": lid}).json))

    def test_roles_and_the_switched_off_endpoint(self):
        cookie, csrf = self.session("viewer@example.com")
        for route in ("agentlink", "agentstatus", "agentcancel"):
            got = self.post(f"/traffic/{A}/sites/{route}", {"site": A, "link_id": "0" * 16},
                            cookie, csrf)
            self.assertEqual(got.status, 403, route)
        self.config["ingest"]["enabled"] = False
        self.assertEqual(self.agentlink().status, 409)

    def revoked(self, tid):
        db = self.accounts_db()
        try:
            return bool([t for t in apitokens.listing(db, self.alpha["id"])
                         if t["id"] == tid][0]["revoked_at"])
        finally:
            db.close()

    def cancel(self, body):
        return self.post(f"/traffic/{A}/sites/agentcancel", body, self.cookie, self.csrf)

    def test_cancel_a_line(self):
        made = self.agentlink().json
        got = self.cancel({"site": A, "link_id": made["link_id"]})
        self.assertEqual((got.status, got.json), (200, {"ok": True, "state": "cancelled"}))
        self.assertTrue(self.revoked(made["token_id"]), "the token was never handed out")
        status = self.post(f"/traffic/{A}/sites/agentstatus",
                           {"site": A, "link_id": made["link_id"]}, self.cookie, self.csrf)
        self.assertEqual(status.json["state"], "cancelled")
        self.assertEqual(agent.take(self.live, self.code_of(made))[2], None)
        rows = self.audit("kit.agentcancel")
        self.assertIn(f"link {made['link_id']}; cancelled; its unused token", rows[0]["detail"])
        self.assertEqual(self.cancel({"site": A, "link_id": made["link_id"]}).json["state"],
                         "cancelled", "again: the same answer")
        self.assertEqual(len(self.audit("kit.agentcancel")), 1)
        self.assertEqual(self.cancel({"site": A, "link_id": "0" * 16}).status, 404)
        self.assertEqual(self.cancel({"site": A, "link_id": "nothex"}).status, 400)
        self.assertEqual(self.cancel({"site": B, "link_id": made["link_id"]}).status, 404)

    def test_cancel_after_the_keys_were_taken_keeps_the_token(self):
        made = self.agentlink().json
        agent.take(self.live, self.code_of(made))
        self.assertEqual(self.cancel({"site": A, "link_id": made["link_id"]}).status, 200)
        self.assertFalse(self.revoked(made["token_id"]))
        self.assertIn("its keys were taken", self.audit("kit.agentcancel")[0]["detail"])

    def test_a_new_line_cancels_the_older_unused_ones(self):
        first = self.agentlink().json
        second = self.agentlink().json
        self.assertEqual(second["cancelled"], 1)
        self.assertTrue(self.revoked(first["token_id"]))
        self.assertFalse(self.revoked(second["token_id"]))
        state = lambda made: agent.status(self.live, A, made["link_id"])["state"]  # noqa: E731
        self.assertEqual((state(first), state(second)), ("cancelled", "waiting"))
        self.assertIn("a new line replaced it", self.audit("kit.agentcancel")[0]["detail"])
        agent.take(self.live, self.code_of(second))
        third = self.agentlink().json
        self.assertEqual(third["cancelled"], 0, "a line whose keys were taken is not cancelled")
        self.assertEqual(state(second), "keys_taken")
        self.assertFalse(self.revoked(second["token_id"]))

    def test_a_new_line_revokes_the_unused_token_of_an_expired_one(self):
        old = agent.make(self.live, A, TOKEN, "ab12cd34", FIELDS,
                         now=time.time() - 25 * 3600)[0]
        db = self.accounts_db()
        try:
            expired_token = apitokens.create(db, self.alpha["id"], "Sending logs: old line",
                                             sites=[A], scopes=("ingest",))
        finally:
            db.close()
        tid = expired_token.split("_", 2)[1]
        path = self.live / link.FILE
        links = json.loads(path.read_text())
        links["links"][link.digest(old)]["token_id"] = tid
        path.write_text(json.dumps(links))
        got = self.agentlink().json
        self.assertEqual(got["cancelled"], 0, "an expired line is not counted as cancelled")
        self.assertTrue(self.revoked(tid))
        self.assertEqual(agent.status(self.live, A, agent.link_id(old))["state"], "expired")

    def test_the_wizard_may_save_the_agent_method(self):
        db = self.accounts_db()
        try:
            got = site_setup.save(db, self.alpha["id"], A, "cli", step=3, method="agent")
        finally:
            db.close()
        self.assertEqual(got["method"], "agent")


if __name__ == "__main__":
    unittest.main()

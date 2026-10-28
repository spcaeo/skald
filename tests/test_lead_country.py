"""A lead's country from the visitor's address (owner, 2026-10-27: "why country
not recorded, it should never happen"). A site without the script tag sends
leads from its own server with no visitor ID; the lead files now send the
visitor's address (`ip`), Skald looks the country up and drops the address,
and Skald says so when a site's last leads came with no country.

  * the hook: `ip` alone, a header's list, a port; `ip` with `vid` (both kept,
    the country from ip); `country` wins; a private address and no country
    file say why in the answer and the delivery log; the address is never kept
  * roads.unplaced -> the doctor's line and the set-up checklist's lead line
  * GET .../leads says `country_recorded`, never the country
  * the four lead files read and check the address (node, php when installed)
  * the README and the agent's lead job say how

Addresses are RFC 5737 (192.0.2.0/24 is "CA" in the test country file) and
private ranges; hosts example.com; the secret is made up."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import SECRET, VID, FakeHandler  # noqa: E402
from test_conversions_hooks import Base, lead  # noqa: E402

from skald import setup_items  # noqa: E402
from skald.conversions import geo, roads, store  # noqa: E402
from skald.conversions.adapters.lead import sign_get  # noqa: E402
from skald.conversions.hooks import IP_NOTE, NO_FILE_NOTE  # noqa: E402
from skald.doctor import hook_items  # noqa: E402
from skald.kit import leadfiles  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
URL = "https://stats.example.com/traffic-hooks/example.com/lead"
VISITOR = "192.0.2.10"


def bare(**kw) -> dict:
    """A lead as a site without the script tag sends it: no vid, no touches."""
    return {"external_ref": "L-1", "action": "contact", **kw}


class Address(unittest.TestCase):
    def test_what_is_read_as_an_address(self):
        for given, want in (("192.0.2.10", "192.0.2.10"), (" 192.0.2.10 ", "192.0.2.10"),
                            ("192.0.2.10, 10.0.0.1", "192.0.2.10"),
                            ("192.0.2.10:51234", "192.0.2.10"),
                            ("2001:db8::1", "2001:db8::1"), ("[2001:db8::1]:443", "2001:db8::1"),
                            ("2001:DB8::1", "2001:db8::1")):
            with self.subTest(given=given):
                self.assertEqual(geo.address(given), want)
        for bad in (None, "", "unknown", "192.0.2", "192.0.2.300", "example.com",
                    "<script>", ", 192.0.2.10", 12345):
            with self.subTest(bad=bad):
                self.assertIsNone(geo.address(bad))


class Hook(Base):
    def stored(self):
        return self.rows("SELECT external_ref, vid, country FROM conversions ORDER BY id")

    def note(self):
        return self.rows("SELECT error FROM deliveries ORDER BY id DESC LIMIT 1")[0][0]

    def test_ip_alone_gives_the_country(self):
        status, answer = self.post("lead", bare(ip=VISITOR))
        self.assertEqual(status, 200)
        self.assertNotIn("notes", answer)
        self.assertEqual(self.stored(), [("L-1", None, "CA")])

    def test_a_header_list_and_a_port_are_read(self):
        self.post("lead", bare(external_ref="L-1", ip="192.0.2.10, 10.0.0.1"))
        self.post("lead", bare(external_ref="L-2", ip="192.0.2.11:51234"))
        self.post("json", bare(external_ref="J-1", ip=VISITOR))
        self.assertEqual(self.rows("SELECT external_ref, country FROM conversions ORDER BY id"),
                         [("L-1", "CA"), ("L-2", "CA"), ("J-1", "CA")])

    def test_vid_and_ip_both_kept_the_country_from_ip(self):
        self.post("lead", lead(ip=VISITOR))
        self.assertEqual(self.stored(), [("L-1", VID, "CA")])
        # Without ip, a vid gives no country: the visits are never read for it.
        self.post("lead", lead(external_ref="L-2"))
        self.assertEqual(self.stored()[1], ("L-2", VID, None))

    def test_a_country_sent_wins_over_ip(self):
        self.post("lead", bare(ip=VISITOR, country="de"))
        self.assertEqual(self.stored(), [("L-1", None, "DE")])

    def test_a_private_or_bad_address_says_why(self):
        for n, ip in enumerate(("10.0.0.7", "127.0.0.1", "not an address")):
            status, answer = self.post("lead", bare(external_ref=f"P-{n}", ip=ip))
            self.assertEqual(status, 200)
            self.assertEqual(answer["notes"], [IP_NOTE], ip)
            self.assertIn(IP_NOTE, self.note())
            self.assertNotIn(ip, self.note(), "the address is never in the log")
        self.assertEqual({r[2] for r in self.stored()}, {None})

    def test_no_note_without_ip(self):
        status, answer = self.post("lead", bare())
        self.assertEqual((status, answer.get("notes")), (200, None))
        self.assertIsNone(self.note())

    def test_the_address_is_never_kept(self):
        self.post("lead", bare(ip="192.0.2.77"))
        for path in self.folder.rglob("*"):
            if path.is_file() and path.suffix != ".mmdb":
                self.assertNotIn(b"192.0.2.77", path.read_bytes(), path.name)

    def test_a_test_delivery_says_the_country(self):
        from skald.conversions.adapters import adapter
        body = json.dumps(bare(ip=VISITOR)).encode()
        path = "/traffic-hooks/example.com/lead"
        headers = {"Host": "www.example.com", "X-Skald-Test": "1",
                   **adapter("lead").sign(body, SECRET, self.now, "POST",
                                          "https://www.example.com" + path)}
        status, answer = self.rx.http(FakeHandler(path, body, headers))
        self.assertEqual((status, answer["test"]), (200, True))
        self.assertEqual(answer["read"][0]["country"], "CA")
        body = json.dumps(bare(ip="10.0.0.7")).encode()
        headers.update(adapter("lead").sign(body, SECRET, self.now, "POST",
                                            "https://www.example.com" + path))
        status, answer = self.rx.http(FakeHandler(path, body, headers))
        self.assertIn(IP_NOTE, answer["notes"])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions"), [(0,)])


class HookNoCountryFile(Base):
    def setUp(self):
        super().setUp()
        self.rx.country_db = None

    def test_ip_without_a_country_file_says_so(self):
        status, answer = self.post("lead", bare(ip=VISITOR))
        self.assertEqual((status, answer["notes"]), (200, [NO_FILE_NOTE]))
        self.assertEqual(self.rows("SELECT country FROM conversions"), [(None,)])


class HookVisitorIdsOff(Base):
    visitor_ids = False

    def test_the_vid_goes_the_country_stays(self):
        self.post("lead", lead(ip=VISITOR))
        self.assertEqual(self.rows("SELECT vid, country FROM conversions"), [(None, "CA")])


class Unplaced(Base):
    """roads.unplaced, and where Skald says it: the doctor and the checklist."""

    def keep(self, ref, tool="lead", country=None, vid=None, test=False, received=None):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            store.record_conversion(db, {"site": "example.com", "action": "contact",
                                         "stage": "completed", "tool": tool,
                                         "external_ref": ref, "at": "2026-10-11T09:00:00Z",
                                         "vid": vid, "country": country, "test": test,
                                         "received_at": received})
        finally:
            db.close()

    def state(self, tool="lead", config=None):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            return roads.unplaced(db, "example.com", tool, config or self.config)
        finally:
            db.close()

    def test_the_last_three_without_a_country(self):
        for n in range(4):
            self.keep(f"L-{n}", received=f"2026-10-1{n}T10:00:00Z")
        got = self.state()
        self.assertEqual((got["leads"], got["no_vid"]), (3, True))
        self.assertEqual(got["says"], "Your last 3 leads came without a visitor ID or the "
                                      "visitor's address, so their country and the pages they "
                                      "read are not recorded")
        self.assertIn("`ip`", got["fix"])
        self.assertIn("lead job", got["fix"])
        self.assertIn("stay without a country", got["fix"])

    def test_one_lead_and_one_with_a_vid(self):
        self.keep("L-1", vid=VID)
        got = self.state()
        self.assertEqual(got["says"], "Your last lead came without the visitor's address, so "
                                      "their country is not recorded")

    def test_one_of_the_last_three_with_a_country_is_enough(self):
        self.keep("L-1", received="2026-10-10T10:00:00Z")
        self.keep("L-2", country="CA", received="2026-10-11T10:00:00Z")
        self.keep("L-3", received="2026-10-12T10:00:00Z")
        self.assertIsNone(self.state())
        # An older lead with a country does not hide three newer ones without.
        for n in range(4, 7):
            self.keep(f"L-{n}", received=f"2026-10-1{n}T10:00:00Z")
        self.assertEqual(self.state()["leads"], 3)

    def test_test_rows_other_tools_and_nothing_yet(self):
        self.assertIsNone(self.state(), "no lead yet: nothing to say")
        self.keep("T-1", test=True)
        self.assertIsNone(self.state(), "a test lead is not the site's leads")
        self.keep("C-1", tool="calendly")
        self.assertIsNone(self.state("calendly"), "Calendly cannot send an address")
        self.keep("J-1", tool="json")
        self.assertEqual(self.state("json")["leads"], 1)

    def test_no_country_file_says_that_instead(self):
        self.keep("L-1")
        got = self.state(config={"site": {"name": "example.com"}})
        self.assertIn("no country file", got["says"])
        self.assertIn("logs.country_db", got["fix"])

    def test_the_doctor_and_the_hook_state_say_it(self):
        self.post("lead", bare(external_ref="L-1"))
        self.post("lead", bare(external_ref="L-2"))
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            states = {s["tool"]: s for s in roads.hook_states(self.config, self.folder,
                                                               "example.com", db)}
        finally:
            db.close()
        self.assertEqual(states["lead"]["unplaced"]["leads"], 2)
        self.assertFalse(states["lead"]["attention"], "the hook itself works")
        self.assertIsNone(states["calendly"]["unplaced"])
        from datetime import datetime, timezone
        lines = {i["id"]: i for i in hook_items(self.config, self.folder, "example.com",
                                                 datetime.now(timezone.utc), "skald")}
        self.assertEqual(lines["hook:lead"]["state"], "OK")
        self.assertEqual(lines["place:lead"]["state"], "NEEDS ATTENTION")
        self.assertTrue(lines["place:lead"]["says"].startswith("Your last 2 leads"))
        # A lead with its address puts it right; the leads kept before stay as they are.
        self.post("lead", bare(external_ref="L-3", ip=VISITOR))
        lines = {i["id"] for i in hook_items(self.config, self.folder, "example.com",
                                             datetime.now(timezone.utc), "skald")}
        self.assertNotIn("place:lead", lines)
        self.assertEqual(self.rows("SELECT external_ref, country FROM conversions ORDER BY id"),
                         [("L-1", None), ("L-2", None), ("L-3", "CA")])


class Checklist(unittest.TestCase):
    def test_the_lead_line_asks_for_the_lead_job(self):
        u = {"leads": 3, "no_vid": True, "says": "Your last 3 leads came without a visitor ID",
             "fix": "Pass the visitor's address as `ip`."}
        tools = [{"tool": "lead", "name": "Your site's server (lead)", "state": "received",
                  "attention": False, "words": "last received 1 h ago (kept)", "fix": None,
                  "unplaced": u}]
        line = next(i for i in setup_items.items(tools=tools) if i["id"] == "lead")
        self.assertEqual((line["state"], line["act"], line["optional"]), ("todo", "lead", True))
        self.assertEqual(line["says"], "Your site's server (lead): Your last 3 leads came "
                                       "without a visitor ID.")
        self.assertEqual(line["tech"], "Fix: Pass the visitor's address as `ip`.")
        self.assertEqual(setup_items.job_of(line), "lead")
        tools[0]["unplaced"] = None
        line = next(i for i in setup_items.items(tools=tools) if i["id"] == "lead")
        self.assertEqual(line["state"], "done")


class ReadBack(Base):
    """GET .../leads: `country_recorded`, never the country."""

    def test_country_recorded_true_or_false(self):
        self.post("lead", bare(external_ref="L-1", ip=VISITOR))
        self.post("lead", bare(external_ref="L-2"))
        target = "/traffic-hooks/example.com/leads"
        status, got = self.rx.http(FakeHandler(target, b"", sign_get(target, SECRET, self.now),
                                               "GET"))
        self.assertEqual(status, 200)
        self.assertEqual([(r["external_ref"], r["country_recorded"]) for r in got["rows"]],
                         [("L-1", True), ("L-2", False)])
        self.assertNotIn('"CA"', json.dumps(got))
        self.assertNotIn("country", got["rows"][0])


# ------------------------------------------------------------------ the lead files

class _Catch(BaseHTTPRequestHandler):
    """A stand-in for Skald: keeps what a lead file posts, answers 200."""
    got: list = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        type(self).got.append((self.path, dict(self.headers), body))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *args):
        pass


class Files(unittest.TestCase):
    def test_every_file_and_the_readme_name_ip(self):
        got = leadfiles.files("example.com", URL, None)
        for name in ("skald-lead.php", "skald-lead.cjs", "skald_lead.py", leadfiles.PLUGIN,
                     "README.md"):
            self.assertIn(b"ip", got[name], name)
        readme = got["README.md"].decode()
        for word in ("The visitor's address", "x-forwarded-for", "CF-Connecting-IP",
                     "SKALD_LEAD_IP_HEADER", "Vercel", "req.ip", "request.remote_addr",
                     "HTTP_X_FORWARDED_FOR", "country_recorded", "Both `vid` and `ip`",
                     "never guesses a country"):
            self.assertIn(word, readme, word)
        self.assertIn(b"SKALD_LEAD_IP_HEADER", got["skald-lead.php"])
        self.assertIn(b"SKALD_LEAD_IP_HEADER", got[leadfiles.PLUGIN])
        self.assertIn(b"Version: 1.1.0", got[leadfiles.PLUGIN])

    def test_the_agent_job_asks_for_the_address_and_checks_it(self):
        job = (ROOT / "skald" / "kit" / "agent" / "jobs" / "lead.md").read_text()
        for word in ("`ip`", "x-forwarded-for", "(await headers()).get(\"x-forwarded-for\")",
                     "CF-Connecting-IP", "`vid`", "country_recorded", "__ENV_FILE__"):
            self.assertIn(word, job, word)


class PythonFile(Base):
    def setUp(self):
        super().setUp()
        self.now = time.time()          # the helper signs with the real clock
        data = leadfiles.files("example.com", URL, SECRET)["skald_lead.py"]
        path = Path(self.tmp.name) / "skald_lead.py"
        path.write_bytes(data)
        spec = importlib.util.spec_from_file_location("skald_lead_ip_test", path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def send(self, *args, **kw):
        sent = []

        def urlopen(req, timeout=None):
            sent.append(json.loads(req.data))
            status, _ = self.rx.http(FakeHandler(req.full_url.split("stats.example.com", 1)[1],
                                                 req.data, dict(req.header_items())))
            answer = mock.MagicMock(status=status)
            answer.__enter__.return_value = answer
            return answer

        with mock.patch("urllib.request.urlopen", urlopen), \
                mock.patch.dict(os.environ, {"SKALD_LEAD_SECRET": SECRET}):
            self.assertTrue(self.mod.skald_lead(*args, **kw))
        return sent[0]

    def test_the_address_is_checked_and_kept_as_a_country(self):
        self.assertEqual(self.mod.visitor_ip("192.0.2.10, 10.0.0.1"), "192.0.2.10")
        self.assertEqual(self.mod.visitor_ip("[2001:db8::1]:443"), "2001:db8::1")
        self.assertIsNone(self.mod.visitor_ip("nope"))
        self.assertIsNone(self.mod.visitor_ip(None))
        body = self.send("PY-1", "contact", ip="192.0.2.10, 10.0.0.1", vid=VID)
        self.assertEqual((body["ip"], body["vid"]), ("192.0.2.10", VID))
        self.assertNotIn("ip", self.send("PY-2", "contact", ip="not-an-address"))
        self.assertNotIn("ip", self.send("PY-3", "contact", ip=None))
        self.assertEqual(self.rows("SELECT external_ref, vid, country FROM conversions "
                                   "ORDER BY id"),
                         [("PY-1", VID, "CA"), ("PY-2", None, None), ("PY-3", None, None)])


class _Served(unittest.TestCase):
    """The lead files posting to a stand-in Skald on 127.0.0.1."""

    def setUp(self):
        _Catch.got = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Catch)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}/traffic-hooks/example.com/lead"
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        for name, data in leadfiles.files("example.com", self.url, SECRET).items():
            (self.dir / Path(name).name).write_bytes(data)

    def run_in(self, cmd: list[str], env: dict | None = None) -> str:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=self.dir,
                              env={**os.environ, "SKALD_LEAD_SECRET": SECRET, **(env or {})})
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done.stdout

    def bodies(self) -> list[dict]:
        return [json.loads(b) for _, _, b in _Catch.got]


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class NodeFile(_Served):
    def test_ip_is_checked_then_sent(self):
        script = self.dir / "t.cjs"
        script.write_text("""
const { skaldLead, visitorIp } = require("./skald-lead.cjs");
(async () => {
  const out = { ip: ["192.0.2.10, 10.0.0.1", "192.0.2.10:51234", "[2001:db8::1]:443",
                     "2001:db8::1", "nope", "", null, "192.0.2"].map(visitorIp) };
  out.sent = [
    await skaldLead("N-1", "contact", { ip: "192.0.2.10, 10.0.0.1", vid: "skv_" + "Q".repeat(22) }),
    await skaldLead("N-2", "contact", { ip: "not-an-address" }),
    await skaldLead("N-3", "contact", {}),
  ];
  console.log(JSON.stringify(out));
})();
""")
        out = json.loads(self.run_in(["node", str(script)]))
        self.assertEqual(out["ip"], ["192.0.2.10", "192.0.2.10", "2001:db8::1", "2001:db8::1",
                                     None, None, None, None])
        self.assertEqual(out["sent"], [True, True, True])
        bodies = self.bodies()
        self.assertEqual(bodies[0]["ip"], "192.0.2.10")
        self.assertEqual(bodies[0]["vid"], "skv_" + "Q" * 22)
        self.assertNotIn("ip", bodies[1])
        self.assertNotIn("ip", bodies[2])


PHP_CALL = """<?php
$_SERVER = array_merge($_SERVER, json_decode(getenv('T_SERVER'), true));
require __DIR__ . '/skald-lead.php';
$extra = json_decode(getenv('T_EXTRA'), true);
echo json_encode(array('ip' => skald_lead_visitor_ip(), 'sent' => skald_lead('P-1', 'contact', null, null, $extra)));
"""

WP_CALL = """<?php
define('ABSPATH', __DIR__);
$GLOBALS['t_posted'] = array();
function add_action() {}
function apply_filters($name, $value) { return $value; }
function wp_unslash($v) { return $v; }
function wp_json_encode($v) { return json_encode($v); }
function is_email($v) { return (bool) filter_var($v, FILTER_VALIDATE_EMAIL); }
function wp_generate_password($n) { return 'abcdefabcdef'; }
function wp_remote_post($url, $args) { $GLOBALS['t_posted'][] = json_decode($args['body'], true); }
$_SERVER = array_merge($_SERVER, json_decode(getenv('T_SERVER'), true));
if (getenv('T_HEADER')) { define('SKALD_LEAD_IP_HEADER', getenv('T_HEADER')); }
require __DIR__ . '/skald-leads.php';
skald_leads_send('cf7', 7, array('your-email' => 'person@example.com'));
echo json_encode($GLOBALS['t_posted'][0]);
"""


@unittest.skipUnless(shutil.which("php"), "php is not installed")
class PhpFiles(_Served):
    CASES = [
        # (the request's $_SERVER, SKALD_LEAD_IP_HEADER, the address sent)
        ({"REMOTE_ADDR": "192.0.2.10"}, "", "192.0.2.10"),
        # A public REMOTE_ADDR: a header a visitor wrote is never read.
        ({"REMOTE_ADDR": "192.0.2.10", "HTTP_X_FORWARDED_FOR": "198.51.100.9"}, "", "192.0.2.10"),
        # nginx on the same server in front of PHP: X-Real-IP, else the first X-Forwarded-For.
        ({"REMOTE_ADDR": "127.0.0.1", "HTTP_X_REAL_IP": "192.0.2.11",
          "HTTP_X_FORWARDED_FOR": "198.51.100.9"}, "", "192.0.2.11"),
        ({"REMOTE_ADDR": "10.0.0.2", "HTTP_X_FORWARDED_FOR": "192.0.2.12, 10.0.0.1"}, "",
         "192.0.2.12"),
        ({"REMOTE_ADDR": "10.0.0.2", "HTTP_X_FORWARDED_FOR": "garbage"}, "", "10.0.0.2"),
        # A named header (Cloudflare): only it.
        ({"REMOTE_ADDR": "198.51.100.1", "HTTP_CF_CONNECTING_IP": "192.0.2.13"},
         "CF-Connecting-IP", "192.0.2.13"),
        ({"REMOTE_ADDR": "198.51.100.1"}, "CF-Connecting-IP", None),
        ({}, "", None),                          # the command line, a cron job: no request
    ]

    def test_skald_lead_php_reads_the_address(self):
        (self.dir / "t.php").write_text(PHP_CALL)
        for server, header, want in self.CASES:
            with self.subTest(server=server, header=header):
                _Catch.got = []
                out = json.loads(self.run_in(["php", "t.php"], {
                    "T_SERVER": json.dumps(server), "T_EXTRA": "[]",
                    "SKALD_LEAD_IP_HEADER": header}))
                self.assertEqual(out, {"ip": want, "sent": True})
                self.assertEqual(self.bodies()[0].get("ip"), want)
        # Passed by the caller: checked; null sends none.
        for extra, want in (({"ip": "192.0.2.14, 10.0.0.1"}, "192.0.2.14"),
                            ({"ip": None}, None), ({"ip": "nope"}, None)):
            with self.subTest(extra=extra):
                _Catch.got = []
                self.run_in(["php", "t.php"], {"T_SERVER": json.dumps({"REMOTE_ADDR": VISITOR}),
                                               "T_EXTRA": json.dumps(extra)})
                self.assertEqual(self.bodies()[0].get("ip"), want)

    def test_skald_lead_php_is_kept_with_a_country(self):
        (self.dir / "t.php").write_text(PHP_CALL)
        self.run_in(["php", "t.php"], {"T_SERVER": json.dumps({"REMOTE_ADDR": "127.0.0.1",
                                                               "HTTP_X_FORWARDED_FOR": VISITOR}),
                                       "T_EXTRA": "[]"})
        path, headers, body = _Catch.got[0]
        rx = Base("run")
        rx.setUp()
        self.addCleanup(rx.tearDown)
        rx.now = time.time()
        status, _ = rx.rx.http(FakeHandler(path, body, headers))
        self.assertEqual(status, 200)
        self.assertEqual(rx.rows("SELECT external_ref, country FROM conversions"),
                         [("P-1", "CA")])

    def test_the_wordpress_plugin_reads_the_address(self):
        (self.dir / "t.php").write_text(WP_CALL)
        for server, header, want in self.CASES:
            with self.subTest(server=server, header=header):
                body = json.loads(self.run_in(["php", "t.php"], {
                    "T_SERVER": json.dumps(server), "T_HEADER": header}))
                self.assertEqual(body.get("ip"), want)
                self.assertEqual(body["external_ref"], "cf7-7")


if __name__ == "__main__":
    unittest.main()

"""Many sites, one line each (2.40, docs/plans/2026-10-26-agent-everywhere.md): the
owner works on each site on its own (its own repo, its own Claude Code or Codex
session) and gives his go per site.

  * ten sites, ten lines, made one after another and used at once from ONE
    machine (one address): none ends another, every route answers, each keys
    file holds only its own site's keys; one live line per site stays the rule
  * the per-address limit across codes still stops a flood
  * GET sites/agentleft: every site's open jobs and its newest line, admins only
  * the search job: POST <code>/searchkey takes a Search Console key from stdin
    only for a line an install admin made, never replaces a key, refuses a wrong
    shape, never logs or echoes it; the steps' commands run in bash with curl
  * the code adds nothing: no route under /traffic-kit/ makes a site
  * MCP: a token with mcp and setup for one site, made from the dashboard, makes
    that site's line without naming it; two sites' tokens never end each other's

Test data: example.com names and RFC 5737 addresses; the keys are made here.
"""
from __future__ import annotations

import contextlib
import http.client
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A  # noqa: E402
from ingest_support import TenantServer  # noqa: E402
from search_support import VECTOR, service_key  # noqa: E402
from test_kit_agent import IMAGE  # noqa: E402

from skald.accounts import apitokens, auditlog, site_configs, users  # noqa: E402
from skald.conversions import secrets_store  # noqa: E402
from skald.kit import agent, pack  # noqa: E402
from skald.search import google  # noqa: E402

MORE = [f"s{n}.example.com" for n in range(1, 10)]
ADDRESS = "203.0.113.7"
CODE = re.compile(r"use code ([A-Za-z0-9_-]{43}) ")


class Base(TenantServer):
    def setUp(self):
        super().setUp()
        self.config["ingest"]["kit_image"] = IMAGE
        self.config["mcp"] = {"enabled": True}
        self.config.setdefault("hooks", {})["test_url"] = "http://127.0.0.1:9"
        patcher = mock.patch.object(pack, "lead_files", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        db = self.accounts_db()
        try:
            for name in MORE:
                site_configs.create(db, self.alpha["id"], name, "cli", fmt="nginx_combined",
                                    log_dir=str(self.live / "ingest" / name))
        finally:
            db.close()
        self.cookie, self.csrf = self.session("admin@example.com")
        self.port = None

    def kit(self, route, body, cookie=None, csrf=None):
        return self.post(f"/traffic/{A}/sites/{route}", body, cookie or self.cookie,
                         csrf or self.csrf)

    def line(self, site=A, jobs=None):
        got = self.kit("agentlink", {"site": site, **({"jobs": jobs} if jobs else {})})
        self.assertEqual(got.status, 200, got.json)
        return got.json, CODE.search(got.json["line"]).group(1)

    def audit(self, action):
        db = self.accounts_db()
        try:
            return auditlog.recent(db, self.alpha["id"], 100, action)
        finally:
            db.close()

    def beacon(self) -> int:
        if self.port is None:
            from skald.beacon_server import Limiter, Sink, make_handler
            sink = Sink(self.config, self.live / "beacon")
            sink.config_path = self.config_path
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(sink, Limiter(), set()))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            self.port = server.server_address[1]
        return self.port

    def kit_call(self, method, path, body=None, headers=None, agent_name="curl/8.5.0",
                 address=ADDRESS):
        hdrs = {"User-Agent": agent_name, "X-Real-IP": address, **(headers or {})}
        conn = http.client.HTTPConnection("127.0.0.1", self.beacon(), timeout=10)
        conn.request(method, path, body=body, headers=hdrs)
        got = conn.getresponse()
        data = got.read().decode()
        conn.close()
        return got.status, data


class TenSitesAtOnce(Base):
    def test_ten_lines_from_one_machine_never_end_each_other(self):
        sites = [A, *MORE]
        made = {}
        for site in sites:
            body, code = self.line(site)
            self.assertEqual(body["cancelled"], 0, f"{site}: another site's line never ends it")
            made[site] = (body, code)
        left = {r["site"]: r for r in self.call("GET", f"/traffic/{A}/sites/agentleft",
                                                cookie=self.cookie).json["sites"]}
        self.assertEqual({s: left[s]["line"]["state"] for s in sites}, dict.fromkeys(sites, "waiting"))
        # Ten sessions on one laptop: one address, each its own code, all at once.
        for site, (_, code) in made.items():
            self.assertEqual(self.kit_call("GET", f"/traffic-kit/{code}/steps")[0], 200, site)
        for site, (_, code) in made.items():
            status, text = self.kit_call("GET", f"/traffic-kit/{code}/keys")
            self.assertEqual(status, 200, (site, text))
            self.assertIn(f"SKALD_SITE={site}\n", text)
            others = [s for s in sites if s != site]
            self.assertFalse(any(f"/traffic-ingest/{o}\n" in text for o in others),
                             "only its own site's keys")
            key = re.search(r"^SKALD_REPORT_KEY=(\S+)$", text, re.M).group(1)
            raw = json.dumps({"jobs": {"logs": "done"}, "hosting": "own server"}).encode()
            status, answer = self.kit_call("POST", f"/traffic-kit/{code}/report", raw,
                                           {agent.REPORT_HEADER: key.strip("'"),
                                            "Content-Type": "application/json"})
            self.assertEqual((status, json.loads(answer)), (200, {"ok": True}), site)
        left = {r["site"]: r for r in self.call("GET", f"/traffic/{A}/sites/agentleft",
                                                cookie=self.cookie).json["sites"]}
        for site in sites:
            line = left[site]["line"]
            self.assertEqual((line["state"], line["link_id"]),
                             ("keys_taken", made[site][0]["link_id"]), site)
            self.assertTrue(line["reported_at"], site)
        db = self.accounts_db()
        try:
            tokens = apitokens.listing(db, self.alpha["id"])
        finally:
            db.close()
        sending = [t for t in tokens if "AI agent set-up" in t["name"]]
        self.assertEqual(sorted(t["sites"][0] for t in sending), sorted(sites))
        self.assertFalse(any(t["revoked_at"] for t in sending), "every site keeps its token")
        # One live line per site stays: a new line for s1 ends s1's untaken one only.
        fresh, _ = self.line(MORE[0])
        again, _ = self.line(MORE[0])
        self.assertEqual((fresh["cancelled"], again["cancelled"]), (0, 1))
        left = {r["site"]: r for r in self.call("GET", f"/traffic/{A}/sites/agentleft",
                                                cookie=self.cookie).json["sites"]}
        self.assertEqual(left[MORE[1]]["line"]["state"], "keys_taken", "another site untouched")

    def test_one_address_flooding_codes_is_still_stopped(self):
        got = [self.kit_call("GET", f"/traffic-kit/{'Q' * 42}{n % 10}/steps")[0]
               for n in range(80)]
        self.assertIn(429, got, "the per-address limit across codes")
        self.assertEqual(self.kit_call("GET", f"/traffic-kit/{'Q' * 43}/steps",
                                       address="198.51.100.9")[0], 404, "another address")

    def test_the_code_adds_no_site(self):
        _, code = self.line()
        for path in (f"/traffic-kit/{code}/addsite", f"/traffic-kit/{code}/sites/add",
                     f"/traffic-kit/{code}/sites"):
            self.assertIn(self.kit_call("POST", path, b'{"host": "new.example.com"}',
                                        {"Content-Type": "application/json"})[0], (404, 405))
        db = self.accounts_db()
        try:
            self.assertIsNone(site_configs.get(db, "new.example.com"))
        finally:
            db.close()


class Left(Base):
    def test_every_site_with_its_jobs_for_admins_only(self):
        got = self.call("GET", f"/traffic/{A}/sites/agentleft", cookie=self.cookie)
        self.assertEqual(got.status, 200, got.json)
        rows = {r["site"]: r for r in got.json["sites"]}
        self.assertEqual(set(rows), {A, *MORE})
        self.assertIn("logs", rows[MORE[0]]["jobs"])
        self.assertIn("search", rows[MORE[0]]["jobs"], "Search Console is an agent job")
        self.assertIsNone(rows[MORE[0]]["line"])
        self.assertTrue(got.json["mcp"]["url"].endswith("/traffic-mcp"))
        self.assertTrue(got.json["mcp"]["on"])
        viewer, _ = self.session("viewer@example.com")
        self.assertEqual(self.call("GET", f"/traffic/{A}/sites/agentleft", cookie=viewer).status,
                         403)

    def test_several_sites_added_with_the_same_checks_and_limits(self):
        for name in ("new1.example.com", "new2.example.com"):
            got = self.kit("add", {"host": name, "token": False})
            self.assertEqual(got.status, 200, got.json)
            self.assertIsNone(got.json["token"], "no token: each line makes its own")
        self.assertEqual(self.kit("add", {"host": "new1.example.com", "token": False}).status, 400,
                         "the same name twice")
        with mock.patch("skald.sites_api.plan_allows",
                        return_value="Your plan does not allow another site."):
            got = self.kit("add", {"host": "new3.example.com", "token": False})
        self.assertEqual((got.status, got.json["error"]), (403, "Your plan does not allow another site."))
        rows = {r["site"] for r in self.call("GET", f"/traffic/{A}/sites/agentleft",
                                             cookie=self.cookie).json["sites"]}
        self.assertTrue({"new1.example.com", "new2.example.com"} <= rows)
        self.assertNotIn("new3.example.com", rows)


class SearchKey(Base):
    KEY = service_key()

    def install_admin(self, flag=True):
        db = self.accounts_db()
        try:
            if not flag:                     # never the last one: the owner stays one
                users.set_install_admin(db, self.uids["owner@example.com"], True, "cli")
            users.set_install_admin(db, self.uids["admin@example.com"], flag, "cli")
        finally:
            db.close()

    def send(self, code, body, key, agent_name="curl/8.5.0"):
        hdrs = {"Content-Type": "application/json"}
        if key is not None:
            hdrs[agent.REPORT_HEADER] = key
        self.n = getattr(self, "n", 0) + 1           # its own address: the route's limit
        status, data = self.kit_call("POST", f"/traffic-kit/{code}/searchkey",
                                     body if isinstance(body, bytes) else body.encode(), hdrs,
                                     agent_name, address=f"198.51.100.{self.n}")
        return status, json.loads(data)

    def report_key(self, code):
        return agent.take(self.live, code)[2]["report_key"]

    def stored(self):
        return secrets_store.load(secrets_store.path_for(self.config, self.live)).get(
            google.SECRET)

    def test_only_an_install_admins_line_hands_skald_a_key(self):
        _, code = self.line(jobs=["search"])
        text = agent.steps(agent.find(self.live, code), code, "")
        self.assertIn("only whoever runs the user's Skald may set one", text)
        self.assertNotIn("gcloud iam", text)
        status, got = self.send(code, self.KEY, self.report_key(code))
        self.assertEqual(status, 403)
        self.assertIn("install admin", got["error"])
        self.assertIsNone(self.stored())

    def test_the_key_is_kept_once_never_replaced_never_echoed(self):
        self.install_admin()
        body, code = self.line(jobs=["search"])
        text = agent.steps(agent.find(self.live, code), code, "")
        self.assertIn("gcloud iam service-accounts keys create", text)
        self.assertIn(f"/traffic-kit/{code}/searchkey", text)
        key = self.report_key(code)
        pem_body = VECTOR["pkcs8_der_base64"][:40]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            refused = [self.send(code, self.KEY, key, "Mozilla/5.0 (compatible; Claude-User/1.0)"),
                       self.send(code, self.KEY, None), self.send(code, self.KEY, "x" * 32),
                       self.send(code, json.dumps({"key": self.KEY}), key),
                       self.send(code, "not json at all", key),
                       self.send(code, service_key(token_uri="https://evil.example.com/t"), key)]
            self.assertEqual([s for s, _ in refused], [403, 403, 403, 400, 400, 400])
            self.assertIsNone(self.stored(), "nothing kept before a good key")
            status, got = self.send(code, self.KEY, key)
            self.assertEqual((status, got), (200, {"ok": True, "client_email": "robot@example.com"}))
            again = self.send(code, service_key("other@example.com"), key)
        self.assertEqual(again[0], 409)
        self.assertEqual(again[1]["client_email"], "robot@example.com", "the robot to add")
        self.assertEqual(json.loads(self.stored())["client_email"], "robot@example.com")
        rows = self.audit("search.key")
        self.assertEqual((rows[0]["actor"], rows[0]["target"]), ("ai-agent", "google"))
        self.assertIn(f"link {body['link_id']}", rows[0]["detail"])
        seen = json.dumps(rows) + err.getvalue() + json.dumps([g for _, g in refused])
        self.assertNotIn(pem_body, seen, "the key is never logged or echoed")

    def test_refused_without_the_search_job_or_once_demoted(self):
        self.install_admin()
        _, other = self.line(jobs=["script"])
        status, got = self.send(other, self.KEY, self.report_key(other))
        self.assertEqual(status, 403)
        self.assertIn("no search job", got["error"])
        _, code = self.line(jobs=["search"])
        key = self.report_key(code)
        self.install_admin(False)
        self.assertEqual(self.send(code, self.KEY, key)[0], 403, "checked again at the upload")
        self.assertEqual(agent.route("A" * 43 + "/searchkey"), "searchkey", "its own limit")

    def test_the_steps_commands_run_as_written(self):
        """The keys command and the key upload, cut from the steps, in bash with curl:
        the key file goes in from stdin, the report key through a pipe."""
        if shutil.which("curl") is None or shutil.which("bash") is None:
            self.skipTest("curl or bash is not installed")
        self.install_admin()
        _, code = self.line(jobs=["search"])
        text = agent.steps(agent.find(self.live, code), code, "")
        here = f"http://127.0.0.1:{self.beacon()}/traffic-kit/"

        def command(start):
            got = [ln.strip() for ln in text.splitlines() if ln.strip().startswith(start)]
            self.assertTrue(got, start)
            return re.sub(r"https?://[^/']+/traffic-kit/", here, got[0])
        keys = command("umask 077 && mkdir -p ~/.config/skald")
        upload = command("curl -sS -w")
        self.assertIn("--data-binary @- '", upload)
        self.assertTrue(upload.endswith(f"< $HOME/.config/skald/{A}.gsc-key.json"), upload)
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        (home / ".config" / "skald").mkdir(parents=True)
        keyfile = home / ".config" / "skald" / f"{A}.gsc-key.json"
        keyfile.write_text(self.KEY)
        keyfile.chmod(0o600)
        got = subprocess.run(["bash", "-c", "\n".join((keys, upload))], capture_output=True,
                             text=True, env={**os.environ, "HOME": str(home)}, timeout=30)
        self.assertIn('"client_email": "robot@example.com"', got.stdout, got.stderr)
        self.assertIn("HTTP 200", got.stdout)
        self.assertNotIn(VECTOR["pkcs8_der_base64"][:40], got.stdout + got.stderr)
        self.assertEqual(json.loads(self.stored())["client_email"], "robot@example.com")


class TwoLines(Base):
    def rpc(self, token, name, args):
        got = self.call("POST", "/traffic-mcp", body={"jsonrpc": "2.0", "id": 1,
                                                      "method": "tools/call",
                                                      "params": {"name": name,
                                                                 "arguments": args}},
                        headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(got.status, 200, got.json)
        return got.json["result"]

    def token(self, site):
        got = self.post(f"/traffic/{A}/tokens/create",
                        {"name": f"AI agent (MCP + set-up): {site}", "sites": [site],
                         "scopes": ["mcp", "setup"]}, self.cookie, self.csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual((got.json["scopes"], got.json["sites"]), (["mcp", "setup"], [site]))
        return got.json["token"]

    def test_line_two_needs_no_site_and_two_sites_never_end_each_other(self):
        first, second = self.token(A), self.token(MORE[0])
        a = self.rpc(first, "setup_line", {"jobs": ["script", "search"]})
        self.assertFalse(a["isError"], a)
        self.assertEqual(a["structuredContent"]["site"], A, "the token's one site")
        self.assertEqual(a["structuredContent"]["jobs"], ["script", "search"])
        self.assertIn("follow the line yourself now", a["content"][0]["text"])
        b = self.rpc(second, "setup_line", {"site": MORE[0], "jobs": ["script"]})
        self.assertFalse(b["isError"], b)
        self.assertEqual(b["structuredContent"].get("cancelled", 0), 0)
        left = {r["site"]: r for r in self.call("GET", f"/traffic/{A}/sites/agentleft",
                                                cookie=self.cookie).json["sites"]}
        self.assertEqual(left[A]["line"]["state"], "waiting", "the other site's line kept it")
        self.assertEqual(left[A]["line"]["link_id"], a["structuredContent"]["link_id"])
        refused = self.rpc(second, "setup_line", {"site": A, "jobs": ["script"]})
        self.assertTrue(refused["isError"], "one site per token")

    def test_a_viewer_cannot_make_the_token(self):
        viewer, csrf = self.session("viewer@example.com")
        got = self.post(f"/traffic/{A}/tokens/create",
                        {"name": "x", "sites": [A], "scopes": ["mcp", "setup"]}, viewer, csrf)
        self.assertEqual(got.status, 403)


if __name__ == "__main__":
    unittest.main()

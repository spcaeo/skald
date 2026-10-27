"""2.39: one AI agent line for any set-up job (kit/agent_jobs.py, kit/agent.py,
kit/agent_hooks.py, kit_api.py; docs/plans/2026-10-26-agent-everywhere.md).

  * without `jobs` the line, the keys file and the keys are today's
  * each job alone: the keys file holds only its keys, the steps only its part
  * unknown or empty job lists: 400 in plain words
  * the report's `jobs` and `tools`: cleaned, capped, the line's own only
  * POST <code>/hooksecret: Skald's secret once as an env line, or the tool's
    own kept as pasted; refused without the lead job, the report key, curl or
    Wget, or a known tool
  * every token a line made is revoked when it ends unused

Test data: example.com, alpha.example and RFC 5737 addresses; the keys are made here.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A  # noqa: E402
from ingest_support import TenantServer  # noqa: E402
from test_kit_agent import FIELDS, IMAGE, LEAD, TOKEN, make, report_key  # noqa: E402

from skald import kit_api  # noqa: E402
from skald.accounts import apitokens, auditlog  # noqa: E402
from skald.conversions import secrets_store  # noqa: E402
from skald.kit import agent, agent_jobs, link, pack  # noqa: E402

HEADINGS = {"logs": "Connect the logs", "script": "Add the script tag",
            "lead": "Leads, and the booking, form or payment tools",
            "rsc": "Add the Next.js log field", "assets": "Find where the pages load their own",
            "privacy": "Check the privacy settings",
            "search": "Connect Google Search Console",
            "connect-tools": "Connect the user's own tools",
            "mcp": "Connect the user's AI assistant to Skald (MCP)",
            "connect-journeys": "Connect recorded journeys"}
NAMES = {"logs": ["SKALD_SITE", "SKALD_INGEST_URL", "SKALD_INGEST_TOKEN", "SKALD_LEAD_URL",
                  "SKALD_REPORT_KEY"],
         "script": ["SKALD_SITE", "SKALD_REPORT_KEY"],
         "lead": ["SKALD_SITE", "SKALD_LEAD_URL", "SKALD_LEAD_SECRET", "SKALD_REPORT_KEY"],
         "rsc": ["SKALD_SITE", "SKALD_REPORT_KEY"], "assets": ["SKALD_SITE", "SKALD_REPORT_KEY"],
         "privacy": ["SKALD_SITE", "SKALD_REPORT_KEY"],
         "search": ["SKALD_SITE", "SKALD_REPORT_KEY"],
         "connect-tools": ["SKALD_SITE", "SKALD_REPORT_KEY"],
         "mcp": ["SKALD_SITE", "SKALD_MCP_URL", "SKALD_MCP_TOKEN", "SKALD_REPORT_KEY"],
         "connect-journeys": ["SKALD_SITE", "SKALD_REPORT_KEY"]}
MCP = "skald_ee11ff22_" + "Mq4Wn7Xs2Ty5Vc8Bd1Fg3Hj6Kk9Lm0Np2Qr5St8Uv1Wx"
STRIPE = "whsec_" + "Tq2Wm5Xr8Tz1Vb4Nc7Pd0Hf3Jg6Kk9Ms2"


def names(text: str) -> list[str]:
    return [line.split("=", 1)[0] for line in text.splitlines() if line and line[0] != "#"]


class Jobs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def test_ids_are_checked_in_plain_words(self):
        self.assertEqual(agent_jobs.clean(["mcp", "logs", "mcp"]), ["logs", "mcp"],
                         "the contract's order, each once")
        for bad, words in (([], "at least one job"), (["nope"], 'no job "nope"'),
                           ("logs", "a list of job ids"), ([1], "a list of job ids"),
                           (["logs"] * 21, "At most 20")):
            with self.assertRaises(ValueError) as got:
                agent_jobs.clean(bad)
            self.assertIn(words, str(got.exception))

    def test_the_default_line_keys_and_file_are_todays(self):
        code, _ = make(self.folder)
        entry = agent.find(self.folder, code)
        self.assertEqual(entry["jobs"], ["logs", "script", "lead"])
        self.assertEqual(agent_jobs.line("example.com", "https://stats.example.com/traffic-kit/"
                                         "llms.txt", "c" * 43, entry["jobs"]),
                         "set up Skald for example.com — read https://stats.example.com/"
                         "traffic-kit/llms.txt and use code " + "c" * 43 + " (works once, 24 hours)")
        key = report_key(self.folder, code)
        state, entry, keys = agent.take(self.folder, code)
        self.assertEqual(keys, {"token": TOKEN, "lead": LEAD, "report_key": key})
        self.assertEqual(agent.keys_file(entry, keys), (
            "# Skald keys for example.com. Keep this file 0600 and out of any repository;\n"
            "# never print it or paste it in a chat.\n"
            "SKALD_SITE=example.com\n"
            f"SKALD_INGEST_URL={FIELDS['url']}\nSKALD_INGEST_TOKEN={TOKEN}\n"
            f"SKALD_LEAD_URL={FIELDS['lead_url']}\nSKALD_LEAD_SECRET={LEAD}\n"
            f"SKALD_REPORT_KEY={key}\n"), "byte for byte as before 2.39")
        old = {k: v for k, v in entry.items() if k != "jobs"}       # an entry from 2.38
        self.assertEqual(agent_jobs.of(old), ["logs", "script", "lead"])
        self.assertEqual(agent_jobs.of({**old, "leads": False}), ["logs", "script"])
        self.assertTrue(agent_jobs.is_default(["logs", "script"]))

    def test_the_line_names_its_jobs(self):
        got = agent_jobs.line("example.com", "https://stats.example.com/traffic-kit/llms.txt",
                              "c" * 43, ["script", "mcp"])
        self.assertEqual(got, "finish setting up Skald for example.com (add the script tag, "
                              "connect the AI assistant (MCP)) — read https://stats.example.com/"
                              "traffic-kit/llms.txt and use code " + "c" * 43 +
                              " (works once, 24 hours)")

    def test_each_job_alone_has_only_its_keys_and_its_steps(self):
        for job in agent_jobs.JOBS:
            with self.subTest(job=job):
                code = agent.make(self.folder, "example.com",
                                  TOKEN if job == "logs" else None,
                                  "ab12cd34" if job == "logs" else None,
                                  {**FIELDS, "mcp_url": "https://stats.example.com/traffic-mcp"},
                                  lead_secret=LEAD if job == "lead" else None,
                                  lead_note="included" if job == "lead" else "none",
                                  jobs=[job], mcp_token=MCP if job == "mcp" else None,
                                  mcp_token_id="ee11ff22" if job == "mcp" else None)[0]
                text = agent.steps(agent.find(self.folder, code), code, "")
                self.assertNotIn("<!--", text)
                self.assertIsNone(re.search(r"__[A-Z][A-Z_]*__", text))
                heads = re.findall(r"^## Step (\d+)\. (.*)$", text, re.M)
                self.assertEqual([n for n, _ in heads], ["1", "2", "3"], heads)
                self.assertTrue(heads[0][1].startswith("Take the keys"))
                self.assertTrue(heads[1][1].startswith(HEADINGS[job]), heads)
                self.assertEqual(heads[2][1], "Report")
                self.assertIn("**Check first.**", text)
                for other, head in HEADINGS.items():
                    if other != job:
                        self.assertNotIn(f". {head}", text, other)
                self.assertIn(f'"jobs": {{"{job}": "done"}}', text)
                state, entry, keys = agent.take(self.folder, code)
                self.assertEqual(state, "ok")
                body = agent.keys_file(entry, keys)
                self.assertEqual(names(body), NAMES[job])
                for secret in (TOKEN, LEAD, MCP):
                    if not any(n.endswith(("TOKEN", "SECRET")) for n in NAMES[job]):
                        self.assertNotIn(secret, body)
                for name in NAMES[job][1:-1]:
                    self.assertIn(f"`{name}`", text, "the keys step names what the file holds")

    def test_every_job_at_once_is_numbered_in_the_contracts_order(self):
        code = agent.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS, lead_secret=LEAD,
                          lead_note="included", jobs=list(reversed(agent_jobs.JOBS)),
                          mcp_token=MCP, mcp_token_id="ee11ff22")[0]
        text = agent.steps(agent.find(self.folder, code), code, "")
        heads = [h for _, h in re.findall(r"^## Step (\d+)\. (.*)$", text, re.M)]
        self.assertEqual(len(heads), len(agent_jobs.JOBS) + 2)
        for n, job in enumerate(agent_jobs.JOBS, 1):
            self.assertTrue(heads[n].startswith(HEADINGS[job]), (n, heads[n]))
        self.assertIn("the log field Next.js needs is step\n   5", text,
                      "with the rsc job, the logs step points at it")
        self.assertNotIn("Ask the privacy question", text, "the privacy job asks it")
        self.assertIn("Do step 3 (the script tag)", text)

    def test_the_report_keeps_jobs_and_tools_cleaned_and_capped(self):
        got = agent.clean_report({
            "jobs": {"logs": "done", "script": "bogus", "nope": "done", "lead": "left",
                     "mcp": ["done"]},
            "tools": [{"tool": "calendly", "hook": "set"}, {"tool": "calendly", "hook": "left"},
                      {"tool": "nope", "hook": "set"}, {"tool": "stripe", "hook": "maybe"},
                      "text", {"tool": "hubspot", "hook": "left", "secret": STRIPE}]
            + [{"tool": t, "hook": "set"} for t in ("lead", "json", "calcom", "typeform",
                                                    "stripe", "lead")] * 5})
        self.assertEqual(got["jobs"], {"logs": "done", "lead": "left"})
        self.assertEqual(got["tools"][:2], [{"tool": "calendly", "hook": "set"},
                                            {"tool": "hubspot", "hook": "left"}])
        self.assertEqual(len(got["tools"]), 7, "each tool once")
        self.assertNotIn(STRIPE, json.dumps(got))
        self.assertEqual(agent.clean_report({"jobs": "done", "tools": {}}), {})
        self.assertIn("[removed]", agent.clean_report({"notes": f"it is {STRIPE}"})["notes"])

    def test_a_report_keeps_only_the_lines_own_jobs(self):
        code = agent.make(self.folder, "example.com", None, None, FIELDS, jobs=["script"])[0]
        key = report_key(self.folder, code)
        report = agent.clean_report({"jobs": {"script": "already", "logs": "done"},
                                     "tools": [{"tool": "stripe", "hook": "set"}],
                                     "script_tag": "app/layout.tsx"})
        self.assertEqual(agent.keep_report(self.folder, code, report, key), "ok")
        got = agent.status(self.folder, "example.com", agent.link_id(code))
        self.assertEqual(got["report"], {"jobs": {"script": "already"},
                                         "script_tag": "app/layout.tsx"})
        self.assertEqual((got["jobs"], got["tools"], got["line_jobs"]),
                         ({"script": "already"}, None, ["script"]))

    def test_a_line_without_a_sending_token_still_gives_its_keys_once(self):
        code = agent.make(self.folder, "example.com", None, None, FIELDS, jobs=["privacy"])[0]
        self.assertIsNone(agent.find(self.folder, code)["sealed"])
        state, _, keys = agent.take(self.folder, code)
        self.assertEqual((state, keys["token"], keys["lead"]), ("ok", None, None))
        self.assertTrue(keys["report_key"])
        self.assertEqual(agent.take(self.folder, code)[0], "keys_taken")

    def test_the_mcp_token_has_its_own_seal_and_is_never_on_disk(self):
        code = agent.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS,
                          jobs=["logs", "mcp"], mcp_token=MCP, mcp_token_id="ee11ff22")[0]
        raw = (self.folder / link.FILE).read_text()
        self.assertNotIn(MCP[15:], raw)
        entry = agent.find(self.folder, code)
        self.assertEqual(link.unseal(entry["sealed_mcp"], code, agent.MCP_LABEL), MCP)
        self.assertNotEqual(link.unseal(entry["sealed_mcp"], code, agent.TOKEN_LABEL), MCP)
        agent.cancel(self.folder, "example.com", agent.link_id(code))
        self.assertIsNone(agent.find(self.folder, code)["sealed_mcp"], "wiped with the others")
        code = agent.make(self.folder, "example.com", None, None, FIELDS, jobs=["mcp"],
                          mcp_token=MCP, mcp_token_id="ee11ff22", now=time.time() - 25 * 3600)[0]
        agent.mark_revoked(self.folder, [])                           # the tidy after expiry
        self.assertIsNone(agent.find(self.folder, code)["sealed_mcp"])

    def test_every_token_a_line_made_is_handed_back_and_marked_one_by_one(self):
        code = agent.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS,
                          jobs=["logs", "mcp"], mcp_token=MCP, mcp_token_id="ee11ff22")[0]
        lid = agent.link_id(code)
        self.assertEqual(agent.cancel(self.folder, "example.com", lid),
                         [(lid, "ab12cd34"), (lid, "ee11ff22")])
        self.assertEqual(agent.unrevoked(self.folder, "example.com"),
                         [(lid, "ab12cd34"), (lid, "ee11ff22")])
        self.assertEqual(agent.mark_revoked(self.folder, [(lid, "ab12cd34")]), 1)
        entry = agent.find(self.folder, code)
        self.assertEqual((entry.get("token_revoked"), entry["revoked_ids"]), (None, ["ab12cd34"]))
        self.assertEqual(agent.unrevoked(self.folder, "example.com"), [(lid, "ee11ff22")])
        self.assertEqual(agent.mark_revoked(self.folder, [(lid, "ee11ff22")]), 1)
        self.assertTrue(agent.find(self.folder, code)["token_revoked"])
        self.assertEqual(agent.unrevoked(self.folder, "example.com"), [])
        none = agent.make(self.folder, "example.com", None, None, FIELDS, jobs=["script"])[0]
        self.assertEqual(agent.cancel(self.folder, "example.com", agent.link_id(none)),
                         [(agent.link_id(none), "")], "a line that made no token")


class Endpoints(TenantServer):
    def setUp(self):
        super().setUp()
        self.config["ingest"]["kit_image"] = IMAGE
        patcher = mock.patch.object(pack, "lead_files", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cookie, self.csrf = self.session("admin@example.com")
        self.n = 0

    def kit(self, route, body):
        return self.post(f"/traffic/{A}/sites/{route}", body, self.cookie, self.csrf)

    def line(self, jobs=None):
        got = self.kit("agentlink", {"site": A} if jobs is None else {"site": A, "jobs": jobs})
        self.assertEqual(got.status, 200, got.json)
        return got.json, re.search(r"use code ([A-Za-z0-9_-]{43}) ", got.json["line"]).group(1)

    def audit(self, action):
        db = self.accounts_db()
        try:
            return auditlog.recent(db, self.alpha["id"], 50, action)
        finally:
            db.close()

    def tokens(self):
        db = self.accounts_db()
        try:
            return {t["id"]: t for t in apitokens.listing(db, self.alpha["id"])}
        finally:
            db.close()

    def secrets(self):
        return secrets_store.load(secrets_store.path_for(self.config, self.live))

    def test_bad_jobs_are_refused_in_plain_words(self):
        for jobs, words in (([], "at least one job"), (["logs", "nope"], 'no job "nope"'),
                            ("logs", "a list of job ids")):
            got = self.kit("agentlink", {"site": A, "jobs": jobs})
            self.assertEqual(got.status, 400, jobs)
            self.assertIn(words, got.json["error"])
        self.assertEqual(self.tokens(), {}, "nothing made")

    def test_each_job_makes_only_the_keys_it_needs(self):
        for job in agent_jobs.JOBS:
            with self.subTest(job=job):
                body, code = self.line([job])
                self.assertEqual(body["jobs"], [job])
                title = agent_jobs.TITLES[job]
                self.assertTrue(body["line"].startswith(f"finish setting up Skald for {A} "
                                                        f"({title}) — read "), body["line"])
                self.assertEqual(body["token_id"] is not None, job == "logs")
                self.assertEqual("mcp_token_id" in body, job == "mcp")
                self.assertEqual(secrets_store.key(A, "lead") in self.secrets(), job == "lead",
                                 "a lead secret only for the lead job")
                _, entry, keys = agent.take(self.live, code)
                self.assertEqual(names(agent.keys_file(entry, keys)), NAMES[job])
            path = secrets_store.path_for(self.config, self.live)
            secrets_store.delete(path, lambda _k: True)

    def test_the_mcp_token_reads_this_site_only(self):
        body, code = self.line(["mcp"])
        made = self.tokens()[body["mcp_token_id"]]
        self.assertEqual((made["scopes"], made["sites"], made["private"]), (["mcp"], [A], False))
        token = agent.take(self.live, code)[2]["mcp"]
        db = self.accounts_db()
        try:
            self.assertTrue(apitokens.check(db, f"Bearer {token}", A, "mcp")[0])
            self.assertFalse(apitokens.check(db, f"Bearer {token}", A, "read")[0])
        finally:
            db.close()
        self.assertIn(f"MCP token {body['mcp_token_id']}", self.audit("kit.agentlink")[0]["detail"])
        self.assertNotIn(token, json.dumps(self.audit("kit.agentlink")))

    def test_make_agent_line_called_directly(self):
        """The MCP's setup_line calls the route's core with an open db."""
        from auth_support import B
        db = self.accounts_db()
        try:
            def call(site=A, jobs=("script", "mcp"), **more):
                return kit_api.make_agent_line(db, self.config, self.alpha, site, list(jobs),
                                               "cli", live_dir=self.live,
                                               config_path=self.config_path, **more)
            got = call(origin="https://dash.example.com/")
            self.assertNotIn("ok", got)
            self.assertEqual(got["jobs"], ["script", "mcp"])
            self.assertIsNone(got["token_id"])
            self.assertTrue(got["line"].startswith(f"finish setting up Skald for {A} ("))
            entry = agent.take(self.live, re.search(r"use code (\S{43}) ", got["line"])
                               .group(1))[1]
            self.assertIn("https://dash.example.com/traffic-js/skald.js", entry["fields"]["tag"])
            made = apitokens.listing(db, self.alpha["id"])
            self.assertEqual([t["id"] for t in made], [got["mcp_token_id"]])
            row = auditlog.recent(db, self.alpha["id"], 5, "kit.agentlink")[0]
            self.assertEqual(row["actor"], "cli")
            self.assertIn(f"link {got['link_id']}; jobs script,mcp", row["detail"])
            again = call(jobs=["lead"])        # no origin: the configured address
            self.assertEqual(again["cancelled"], 0, "the first line's keys were taken")
            for site, jobs, status in ((B, ["script"], 404), (A, ["nope"], 400), (A, [], 400)):
                with self.assertRaises(kit_api.Refused) as no:
                    call(site=site, jobs=jobs)
                self.assertEqual(no.exception.status, status)
                self.assertIsInstance(no.exception, ValueError)
            self.config["ingest"]["enabled"] = False
            with self.assertRaises(ValueError) as no:
                call(jobs=["logs"])
            self.assertIn("log endpoint is switched off", str(no.exception))
        finally:
            db.close()

    def test_jobs_without_logs_work_with_the_log_endpoint_off(self):
        self.config["ingest"]["enabled"] = False
        self.assertEqual(self.kit("agentlink", {"site": A, "jobs": ["script"]}).status, 200)
        self.assertEqual(self.kit("agentlink", {"site": A, "jobs": ["logs"]}).status, 409)

    def revoked(self, tid):
        return bool(self.tokens()[tid]["revoked_at"])

    def test_cancel_revokes_every_token_the_line_made(self):
        body, _ = self.line(["logs", "mcp"])
        got = self.kit("agentcancel", {"site": A, "link_id": body["link_id"]})
        self.assertEqual(got.json, {"ok": True, "state": "cancelled"})
        self.assertTrue(self.revoked(body["token_id"]))
        self.assertTrue(self.revoked(body["mcp_token_id"]))
        rows = self.audit("kit.agentcancel")
        self.assertEqual(len(rows), 1, "one row for the line")
        self.assertIn(body["token_id"], rows[0]["detail"])
        self.assertIn(body["mcp_token_id"], rows[0]["detail"])
        only, _ = self.line(["mcp"])
        self.kit("agentcancel", {"site": A, "link_id": only["link_id"]})
        self.assertTrue(self.revoked(only["mcp_token_id"]))
        none, _ = self.line(["script"])
        self.assertEqual(self.kit("agentcancel", {"site": A, "link_id": none["link_id"]}).status,
                         200)
        self.assertIn("it made no token", self.audit("kit.agentcancel")[0]["detail"])

    def test_a_new_line_and_a_taken_one(self):
        first, _ = self.line(["logs", "mcp"])
        second, code = self.line(["mcp"])
        self.assertEqual(second["cancelled"], 1)
        self.assertTrue(self.revoked(first["token_id"]))
        self.assertTrue(self.revoked(first["mcp_token_id"]))
        agent.take(self.live, code)
        self.kit("agentcancel", {"site": A, "link_id": second["link_id"]})
        self.assertFalse(self.revoked(second["mcp_token_id"]), "its keys were taken: it stays")

    def test_a_failed_revoke_of_one_token_is_tried_again(self):
        body, _ = self.line(["logs", "mcp"])
        real = apitokens.revoke

        def flaky(db, org, tid, actor):
            if tid == body["mcp_token_id"]:
                raise sqlite3.OperationalError("database is locked")
            return real(db, org, tid, actor)
        with mock.patch.object(apitokens, "revoke", side_effect=flaky):
            got = self.kit("agentcancel", {"site": A, "link_id": body["link_id"]})
        self.assertEqual(got.json["not_revoked"], [body["mcp_token_id"]])
        self.assertTrue(self.revoked(body["token_id"]))
        self.assertFalse(self.revoked(body["mcp_token_id"]))
        self.assertEqual(agent.unrevoked(self.live, A), [(body["link_id"], body["mcp_token_id"])])
        self.kit("agentstatus", {"site": A, "link_id": body["link_id"]})   # found ended: again
        self.assertTrue(self.revoked(body["mcp_token_id"]))
        self.assertEqual(agent.unrevoked(self.live, A), [])

    def test_the_daily_run_revokes_an_expired_lines_tokens(self):
        db = self.accounts_db()
        try:
            send = apitokens.create(db, self.alpha["id"], "old send", sites=[A], scopes=("ingest",))
            mcp = apitokens.create(db, self.alpha["id"], "old mcp", sites=[A], scopes=("mcp",))
        finally:
            db.close()
        ids = [t.split("_", 2)[1] for t in (send, mcp)]
        agent.make(self.live, A, send, ids[0], FIELDS, jobs=["logs", "mcp"], mcp_token=mcp,
                   mcp_token_id=ids[1], now=time.time() - 25 * 3600)
        out, err = [], []
        ctx = SimpleNamespace(db_path=self.live / "history.sqlite", site=A, config=self.config,
                              out=out.append, err=err.append)
        self.assertEqual(kit_api.daily(ctx), 0)
        self.assertEqual(err, [])
        self.assertIn("2 unused token(s)", out[0])
        self.assertTrue(all(self.revoked(tid) for tid in ids))

    def test_the_status_carries_the_reports_jobs_and_tools(self):
        body, code = self.line()
        key = report_key(self.live, code)
        report = agent.clean_report({"jobs": {"logs": "done", "lead": "left"},
                                     "tools": [{"tool": "calendly", "hook": "left"}]})
        agent.keep_report(self.live, code, report, key)
        got = self.kit("agentstatus", {"site": A, "link_id": body["link_id"]}).json
        self.assertEqual(got["jobs"], {"logs": "done", "lead": "left"})
        self.assertEqual(got["tools"], [{"tool": "calendly", "hook": "left"}])
        self.assertEqual(got["line_jobs"], ["logs", "script", "lead"])

    # ---------------------------------------------------------- hooksecret

    def beacon(self) -> int:
        from skald.beacon_server import Limiter, Sink, make_handler
        sink = Sink(self.config, self.live / "beacon")
        sink.config_path = self.config_path
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(sink, Limiter(), set()))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_address[1]

    def hook(self, port, code, body, key, agent_name="curl/8.5.0"):
        self.n += 1
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        headers = {"User-Agent": agent_name, "X-Real-IP": f"198.51.100.{self.n % 250 + 1}",
                   "Content-Type": "application/json"}
        if key is not None:
            headers[agent.REPORT_HEADER] = key
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("POST", f"/traffic-kit/{code}/hooksecret", body=raw, headers=headers)
        got = conn.getresponse()
        data = got.read().decode()
        conn.close()
        return got, data

    def test_hooksecret_makes_a_secret_once_as_an_env_line(self):
        port = self.beacon()
        body, code = self.line()
        key = report_key(self.live, code)
        got, data = self.hook(port, code, {"tool": "calendly", "make": True}, key)
        self.assertEqual(got.status, 200, data)
        self.assertTrue(got.getheader("Content-Type").startswith("text/plain"))
        self.assertEqual(got.getheader("Cache-Control"), "no-store")
        made = self.secrets()[secrets_store.key(A, "calendly")]
        self.assertEqual(data, f"SKALD_HOOK_SECRET_CALENDLY={made}\n")
        row = self.audit("hook.secret")[0]
        self.assertEqual((row["actor"], row["target"]), ("ai-agent", f"{A}/calendly"))
        self.assertIn(f"made (AI agent set-up, link {body['link_id']})", row["detail"])
        self.assertNotIn(made, json.dumps(self.audit("hook.secret")))
        got, data = self.hook(port, code, {"tool": "calendly", "make": True}, key)
        self.assertEqual(got.status, 409, "a second run never breaks a working hook")
        self.assertIn('"replace": true', json.loads(data)["error"])
        self.assertEqual(self.secrets()[secrets_store.key(A, "calendly")], made)
        got, data = self.hook(port, code, {"tool": "calendly", "make": True, "replace": True}, key)
        self.assertEqual(got.status, 200)
        self.assertNotEqual(self.secrets()[secrets_store.key(A, "calendly")], made)
        self.assertIn("made, replaced", self.audit("hook.secret")[0]["detail"])

    def test_hooksecret_makes_the_journey_secret_for_a_connect_journeys_line(self):
        """Recorded journeys (2.43): a connect-journeys line gets the journey secret and its
        address once, as env lines; a line without the job, or a pasted secret, is refused."""
        port = self.beacon()
        _, plain = self.line(["script"])
        got, data = self.hook(port, plain, {"tool": "journey", "make": True},
                              report_key(self.live, plain))
        self.assertEqual(got.status, 403, data)
        self.assertNotIn(secrets_store.key(A, "journey"), self.secrets())
        body, code = self.line(["connect-journeys"])
        key = report_key(self.live, code)
        got, data = self.hook(port, code, {"tool": "journey", "secret": "x" * 20}, key)
        self.assertEqual(got.status, 400, data)
        got, data = self.hook(port, code, {"tool": "calendly", "make": True}, key)
        self.assertEqual(got.status, 403, "no lead job: no tool secret")
        got, data = self.hook(port, code, {"tool": "journey", "make": True}, key)
        self.assertEqual(got.status, 200, data)
        made = self.secrets()[secrets_store.key(A, "journey")]
        lines = data.splitlines()
        self.assertEqual(lines[0], f"SKALD_JOURNEY_SECRET={made}")
        self.assertTrue(lines[1].startswith("SKALD_JOURNEY_URL=") and
                        lines[1].endswith(f"/traffic-hooks/{A}/journey"), lines[1])
        row = self.audit("hook.secret")[0]
        self.assertEqual((row["actor"], row["target"]), ("ai-agent", f"{A}/journey"))
        self.assertNotIn(made, json.dumps(self.audit("hook.secret")))
        got, data = self.hook(port, code, {"tool": "journey", "make": True}, key)
        self.assertEqual(got.status, 409, "a second run never breaks a working relay")
        self.assertEqual(self.secrets()[secrets_store.key(A, "journey")], made)
        steps = agent.steps(agent.find(self.live, code), code, "")
        self.assertIn(f"/traffic-hooks/{A}/journey", steps)
        self.assertIn("/traffic-js/journeys.js", steps)
        self.assertIn("SKALD_JOURNEY_SECRET", steps)
        self.assertNotIn(made, steps)

    def test_hooksecret_keeps_a_tools_own_secret(self):
        port = self.beacon()
        _, code = self.line()
        key = report_key(self.live, code)
        got, data = self.hook(port, code, {"tool": "stripe", "secret": STRIPE}, key)
        self.assertEqual((got.status, json.loads(data)),
                         (200, {"ok": True, "tool": "stripe", "replaced": False}))
        self.assertEqual(self.secrets()[secrets_store.key(A, "stripe")], STRIPE)
        self.assertIn("pasted (AI agent set-up", self.audit("hook.secret")[0]["detail"])
        for form, status in (({"tool": "stripe", "secret": "not-a-stripe-secret"}, 400),
                             ({"tool": "stripe", "make": True}, 409),
                             ({"tool": "json", "secret": "a" * 20}, 400),
                             ({"tool": "hubspot", "secret": "short"}, 400),
                             ({"tool": "nope", "make": True}, 400),
                             ({"tool": "lead", "make": True}, 400),
                             ({"tool": "calendly"}, 400),
                             ({"tool": "calendly", "make": True, "secret": "a" * 20}, 400)):
            with self.subTest(form=form):
                self.assertEqual(self.hook(port, code, form, key)[0].status, status)
        self.assertEqual(self.hook(port, code, b"not json", key)[0].status, 400)
        self.assertEqual(set(self.secrets()), {secrets_store.key(A, "lead"),
                                               secrets_store.key(A, "stripe")})

    def test_hooksecret_refusals_use_nothing_up(self):
        port = self.beacon()
        _, code = self.line()
        key = report_key(self.live, code)
        for wrong in (None, "", "x" * 32):
            got, data = self.hook(port, code, {"tool": "calendly", "make": True}, wrong)
            self.assertEqual(got.status, 403)
            self.assertIn("X-Skald-Report-Key", data)
        for reader in ("Mozilla/5.0 (compatible; Claude-User/1.0)", "python-requests/2.31", ""):
            got, data = self.hook(port, code, {"tool": "calendly", "make": True}, key, reader)
            self.assertEqual(got.status, 403, reader)
            self.assertIn("web reader", data)
        self.assertNotIn(secrets_store.key(A, "calendly"), self.secrets())
        self.assertEqual(self.hook(port, "z" * 43, {"tool": "calendly", "make": True},
                                   key)[0].status, 404)
        _, script = self.line(["script"])
        got, data = self.hook(port, script, {"tool": "calendly", "make": True},
                              report_key(self.live, script))
        self.assertEqual(got.status, 403)
        self.assertIn("no lead job", data)
        self.assertEqual(self.hook(port, code, {"tool": "calendly", "make": True}, key)[0].status,
                         410, "the newer line cancelled it")
        self.assertNotIn(secrets_store.key(A, "calendly"), self.secrets())
        self.assertEqual(agent.route("A" * 43 + "/hooksecret"), "hooksecret", "its own limit")

    def test_hooksecret_leaves_a_secret_kept_in_the_environment(self):
        self.config["hooks"] = {f"{A}/typeform": "SKALD_HOOK_TYPEFORM_TEST"}
        port = self.beacon()
        _, code = self.line()
        got, data = self.hook(port, code, {"tool": "typeform", "make": True},
                              report_key(self.live, code))
        self.assertEqual(got.status, 409)
        self.assertIn("SKALD_HOOK_TYPEFORM_TEST", data)

    def test_the_steps_commands_run_as_written(self):
        """The keys, make and paste commands, cut from the steps, in bash with curl."""
        if shutil.which("curl") is None or shutil.which("bash") is None:
            self.skipTest("curl or bash is not installed")
        port = self.beacon()
        _, code = self.line()
        text = agent.steps(agent.find(self.live, code), code, "")
        here = f"http://127.0.0.1:{port}/traffic-kit/"

        def command(start):
            got = [line.strip() for line in text.splitlines() if line.strip().startswith(start)]
            self.assertTrue(got, start)
            return re.sub(r"https?://[^/']+/traffic-kit/", here, got[0])
        keys = command("umask 077 && mkdir -p ~/.config/skald")
        made = command("umask 077 && grep '^SKALD_REPORT_KEY='").replace("<tool>", "calcom")
        paste = command("<a command that prints only the secret").replace(
            "<a command that prints only the secret, on one line>", f"printf '%s\\n' {STRIPE}"
        ).replace("<tool>", "stripe")
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        got = subprocess.run(["bash", "-c", "\n".join((keys, made, paste))], capture_output=True,
                             text=True, env={**os.environ, "HOME": str(home)}, timeout=30)
        self.assertIn("HTTP 200\nHTTP 200\n", got.stdout, got.stderr)
        self.assertIn('{"ok": true, "tool": "stripe", "replaced": false}', got.stdout)
        file = home / ".config" / "skald" / f"{A}.calcom.env"
        self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(file.read_text(), "SKALD_HOOK_SECRET_CALCOM="
                         f"{self.secrets()[secrets_store.key(A, 'calcom')]}\n")
        self.assertEqual(self.secrets()[secrets_store.key(A, "stripe")], STRIPE)
        self.assertFalse(file.with_name(f"{A}.calcom.env.part").exists())
        self.assertNotIn(STRIPE, got.stdout + got.stderr)


if __name__ == "__main__":
    unittest.main()

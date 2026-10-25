"""The AI agent line's store and tokens (kit/agent.py, kit_api.py), the fixes
after 2.31.0:

  * a request that changes nothing (a refused report) never rewrites
    kit-links.json
  * a token is marked revoked only once its revoke succeeded; a failed one
    stays as it was, is said, and is tried again
  * an expired line's unused token is revoked when it is found expired
    (sites/agentstatus) and by the daily run, not only by the next line
  * each /traffic-kit/ route has its own rate limit

Test data: example.com and RFC 5737 addresses; the keys are made here.
"""
from __future__ import annotations

import http.client
import json
import sqlite3
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
from skald.kit import agent, link, pack  # noqa: E402

DAY = 24 * 3600


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.path = self.folder / link.FILE

    def seen(self):
        st = self.path.stat()
        return self.path.read_bytes(), st.st_mtime_ns, st.st_ino

    def entry(self, code):
        return json.loads(self.path.read_text())["links"][link.digest(code)]

    def test_a_refused_report_leaves_the_store_untouched(self):
        code, _ = make(self.folder)
        key = report_key(self.folder, code)
        before = self.seen()
        time.sleep(0.01)
        for wrong in (None, "", "x" * 32):
            self.assertEqual(agent.keep_report(self.folder, code, {"hosting": "x"}, wrong),
                             "refused")
        self.assertEqual(self.seen(), before, "refused: not rewritten")
        self.assertEqual(agent.keep_report(self.folder, code, {"hosting": "own"}, key), "ok")
        self.assertNotEqual(self.seen(), before, "a kept report is written")

    def test_nothing_else_that_changes_nothing_rewrites_it(self):
        code, _ = make(self.folder)
        agent.opened(self.folder, code)
        agent.take(self.folder, code)
        before = self.seen()
        time.sleep(0.01)
        agent.opened(self.folder, code)                    # opened already
        self.assertEqual(agent.take(self.folder, code)[0], "keys_taken")
        self.assertEqual(self.seen(), before)
        old, _ = make(self.folder, now=time.time() - 25 * 3600)
        key = report_key(self.folder, old)
        before = self.seen()
        time.sleep(0.01)
        self.assertEqual(agent.keep_report(self.folder, old, {"hosting": "x"}, key), "expired")
        self.assertEqual(agent.take(self.folder, old)[0], "expired")
        self.assertEqual(self.seen(), before, "an expired code's answers write nothing")

    def test_a_token_is_marked_revoked_only_by_mark_revoked(self):
        now = time.time()
        code, _ = make(self.folder)
        lid = agent.link_id(code)
        self.assertEqual(agent.cancel(self.folder, "example.com", lid), [(lid, "ab12cd34")])
        self.assertFalse(self.entry(code).get("token_revoked"), "not before the revoke")
        self.assertEqual(agent.unrevoked(self.folder, "example.com"), [(lid, "ab12cd34")],
                         "still to revoke")
        old, _ = make(self.folder, now=now - 25 * 3600)
        taken, _ = make(self.folder, now=now - 25 * 3600)
        agent.take(self.folder, taken, now=now - 24 * 3600)
        make(self.folder)                                  # live: not ended
        agent.make(self.folder, "other.example.com", TOKEN, "ff00ff00", FIELDS,
                   now=now - 25 * 3600)
        self.assertEqual(sorted(agent.unrevoked(self.folder, "example.com")),
                         sorted([(lid, "ab12cd34"), (agent.link_id(old), "ab12cd34")]),
                         "ended, keys never taken, this site's only")
        self.assertEqual(agent.mark_revoked(self.folder, [(lid, "ab12cd34")]), 1)
        self.assertTrue(self.entry(code)["token_revoked"])
        self.assertEqual(agent.mark_revoked(self.folder, [(lid, "00000000")]), 0,
                         "the token id must match too")
        self.assertEqual(agent.unrevoked(self.folder, "example.com"),
                         [(agent.link_id(old), "ab12cd34")])
        new, _, ended = agent.make(self.folder, "example.com", TOKEN, "cc00cc00", FIELDS,
                                   replace=True)
        self.assertIn((agent.link_id(old), "ab12cd34", "expired"), ended)
        self.assertNotIn(lid, [one for one, _, _ in ended], "revoked: never handed back")

    def test_mark_revoked_with_nothing_tidies_only_when_needed(self):
        code, _ = make(self.folder)
        before = self.seen()
        time.sleep(0.01)
        self.assertEqual(agent.mark_revoked(self.folder, []), 0)
        self.assertEqual(self.seen(), before, "nothing to tidy: not rewritten")
        agent.mark_revoked(self.folder, [], now=time.time() + DAY + 60)
        self.assertIsNone(self.entry(code)["sealed"], "an expired code's seals are wiped")
        agent.mark_revoked(self.folder, [], now=time.time() + 2 * DAY + 60)
        self.assertNotIn(link.digest(code), json.loads(self.path.read_text())["links"])

    def test_each_route_has_its_own_name(self):
        c = "A" * 43
        for path, want in ((c, "code"), (f"{c}/steps", "steps"), (f"{c}/keys", "keys"),
                           (f"{c}/install.sh", "install.sh"), (f"{c}/leads/x.php", "leads"),
                           (f"{c}/report", "report"), (f"{c}/nope", "other")):
            self.assertEqual(agent.route(path), want, path)
            self.assertIn(want, agent.ROUTES)


class Limits(unittest.TestCase):
    """The beacon helper: one route used up never stops another."""

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

    def status(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
        conn.request("GET", path, headers={"User-Agent": "curl/8.5.0",
                                           "X-Real-IP": "203.0.113.7"})
        got = conn.getresponse()
        got.read()
        conn.close()
        return got.status

    def test_steps_read_often_leave_the_keys_their_tries(self):
        code, _ = make(self.folder)
        got = [self.status(f"/traffic-kit/{code}/steps") for _ in range(7)]
        self.assertEqual(got[:5], [200] * 5)
        self.assertEqual(got[-1], 429, "the steps' own limit")
        self.assertEqual(self.status(f"/traffic-kit/{code}/keys"), 200, "its own limit")
        self.assertEqual(self.status(f"/traffic-kit/{code}/install.sh"), 200)


class Endpoints(TenantServer):
    def setUp(self):
        super().setUp()
        self.config["ingest"]["kit_image"] = IMAGE
        patcher = mock.patch.object(pack, "lead_files", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cookie, self.csrf = self.session("admin@example.com")

    def kit(self, route, body):
        return self.post(f"/traffic/{A}/sites/{route}", body, self.cookie, self.csrf)

    def audit(self, action):
        db = self.accounts_db()
        try:
            return auditlog.recent(db, self.alpha["id"], 50, action)
        finally:
            db.close()

    def revoked(self, tid):
        db = self.accounts_db()
        try:
            return bool([t for t in apitokens.listing(db, self.alpha["id"])
                         if t["id"] == tid][0]["revoked_at"])
        finally:
            db.close()

    def entry(self, lid):
        links = json.loads((self.live / link.FILE).read_text())["links"]
        return [e for k, e in links.items() if k.startswith(lid)][0]

    def expired_line(self, taken=False):
        """An expired line of A whose token is a real one; (link_id, token id)."""
        old = agent.make(self.live, A, TOKEN, "ab12cd34", FIELDS, lead_secret=LEAD,
                         now=time.time() - 25 * 3600)[0]
        if taken:
            agent.take(self.live, old, now=time.time() - 24.5 * 3600)
        db = self.accounts_db()
        try:
            token = apitokens.create(db, self.alpha["id"], "Sending logs: old line",
                                     sites=[A], scopes=("ingest",))
        finally:
            db.close()
        tid = token.split("_", 2)[1]
        path = self.live / link.FILE
        links = json.loads(path.read_text())
        links["links"][link.digest(old)]["token_id"] = tid
        path.write_text(json.dumps(links))
        return agent.link_id(old), tid

    def test_a_failed_revoke_keeps_the_token_as_it_was_and_says_so(self):
        made = self.kit("agentlink", {"site": A}).json
        lid, tid = made["link_id"], made["token_id"]
        with mock.patch.object(apitokens, "revoke",
                               side_effect=sqlite3.OperationalError("database is locked")):
            got = self.kit("agentcancel", {"site": A, "link_id": lid})
        self.assertEqual(got.status, 200)
        self.assertEqual(got.json, {"ok": True, "state": "cancelled", "not_revoked": [tid]})
        self.assertFalse(self.revoked(tid))
        self.assertFalse(self.entry(lid).get("token_revoked"), "kept as it was")
        self.assertIn("could not be revoked (OperationalError)",
                      self.audit("kit.agentcancel")[0]["detail"])
        again = self.kit("agentcancel", {"site": A, "link_id": lid})
        self.assertEqual(again.json, {"ok": True, "state": "cancelled"}, "tried again: done")
        self.assertTrue(self.revoked(tid))
        self.assertTrue(self.entry(lid)["token_revoked"])

    def test_a_failed_revoke_on_a_new_line_is_said_and_tried_again(self):
        first = self.kit("agentlink", {"site": A}).json
        with mock.patch.object(apitokens, "revoke", side_effect=OSError("disk")):
            second = self.kit("agentlink", {"site": A}).json
        self.assertEqual((second["cancelled"], second["not_revoked"]),
                         (1, [first["token_id"]]))
        self.assertFalse(self.entry(first["link_id"]).get("token_revoked"))
        third = self.kit("agentlink", {"site": A}).json
        self.assertNotIn("not_revoked", third)
        self.assertTrue(self.revoked(first["token_id"]), "the next line tried again")
        self.assertTrue(self.revoked(second["token_id"]))

    def test_the_status_of_an_expired_line_revokes_its_unused_token(self):
        lid, tid = self.expired_line()
        got = self.kit("agentstatus", {"site": A, "link_id": lid})
        self.assertEqual(got.json["state"], "expired")
        self.assertTrue(self.revoked(tid), "found expired: revoked, no new line needed")
        self.assertTrue(self.entry(lid)["token_revoked"])

    def test_the_status_of_a_live_line_revokes_nothing(self):
        made = self.kit("agentlink", {"site": A}).json
        lid, tid = self.expired_line()
        self.assertEqual(self.kit("agentstatus", {"site": A, "link_id": made["link_id"]})
                         .json["state"], "waiting")
        self.assertFalse(self.revoked(tid), "only a status that reads ended sweeps")

    def ctx(self):
        out, err = [], []
        return SimpleNamespace(db_path=self.live / "history.sqlite", site=A, config=self.config,
                               out=out.append, err=err.append), out, err

    def test_the_daily_run_revokes_an_expired_lines_unused_token(self):
        lid, tid = self.expired_line()
        taken_lid, taken_tid = self.expired_line(taken=True)
        ctx, out, err = self.ctx()
        self.assertEqual(kit_api.daily(ctx), 0)
        self.assertEqual(err, [])
        self.assertIn("1 unused token(s)", out[0])
        self.assertTrue(self.revoked(tid))
        self.assertTrue(self.entry(lid)["token_revoked"])
        self.assertFalse(self.revoked(taken_tid), "its keys were taken: it stays")
        self.assertIsNone(self.entry(lid)["sealed"], "and the store is tidied")
        rows = [r for r in self.audit("token.revoke") if r["target"] == tid]
        self.assertEqual(rows[0]["actor"], "run-daily")
        out.clear()
        self.assertEqual(kit_api.daily(ctx), 0)
        self.assertEqual(out, [], "once only")

    def test_the_daily_run_never_fails_and_tries_again(self):
        lid, tid = self.expired_line()
        ctx, out, err = self.ctx()
        with mock.patch.object(apitokens, "revoke",
                               side_effect=sqlite3.OperationalError("database is locked")):
            self.assertEqual(kit_api.daily(ctx), 0)
        self.assertIn("could not be revoked (OperationalError); tried again tomorrow", err[0])
        self.assertFalse(self.entry(lid).get("token_revoked"))
        self.assertEqual(kit_api.daily(ctx), 0)
        self.assertTrue(self.revoked(tid))


if __name__ == "__main__":
    unittest.main()

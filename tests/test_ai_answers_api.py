"""AI answers over real HTTP (answers/api.py, sessions mode): members read
the lists and profiles, admins change them (viewers cannot), a profile is
made, edited, duplicated, paused, resumed, asked to run and deleted (never
erased), a stored answer is read in full, keys only ever say set or not, the
audit log is written, and basic mode answers 404. Keys are made up."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B, Server  # noqa: E402

from skald.accounts import auditlog  # noqa: E402
from skald.answers import profiles, store  # noqa: E402

T = f"/traffic/{A}/"
KEY = "sk-made-up-api-key-0000"
PROFILE = {"name": "Toronto", "city": "Toronto", "region": "Ontario", "country": "CA",
           "language": "en", "questions": ["Best server log analytics?"],
           "providers": ["openai", "gemini"], "frequency": "weekly", "repeats": 3, "cap": 2}


class Api(Server):
    def get(self, path="ai-answers", email="owner@example.com"):
        cookie, _ = self.session(email)
        return self.call("GET", T + path, cookie=cookie)

    def do(self, act, body, email="owner@example.com"):
        cookie, csrf = self.session(email)
        return self.post(T + "ai-answers/" + act, body, cookie, csrf)

    def test_read_change_and_never_erase(self):
        env = mock.patch.dict(os.environ, {"SKALD_OPENAI_API_KEY": KEY, "SKALD_GEMINI_API_KEY": KEY})
        env.start()
        self.addCleanup(env.stop)
        got = self.get(email="viewer@example.com")
        self.assertEqual(got.status, 200, got.json)
        self.assertFalse(got.json["editable"])
        self.assertTrue(got.json["keys"]["openai"])
        self.assertNotIn(KEY, json.dumps(got.json))
        self.assertEqual(self.do("profiles/save", PROFILE, "viewer@example.com").status, 403)
        got = self.do("lists", {"questions": "Best analytics?\nCookie-free analytics?",
                                "brands": ["Example Analytics"], "competitors": []})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(len(got.json["lists"]["questions"]), 2)
        got = self.do("profiles/save", PROFILE, "admin@example.com")
        self.assertEqual(got.status, 200, got.json)
        pid = got.json["profiles"][0]["id"]
        self.assertEqual(got.json["profiles"][0]["estimate"]["answers"], 6)
        self.assertEqual(self.do("profiles/save", {**PROFILE, "country": "Canada"}).status, 400)
        got = self.do("profiles/save", {**PROFILE, "id": pid, "repeats": 5, "use_site_questions": True})
        self.assertEqual((got.json["profiles"][0]["version"], got.json["profiles"][0]["asks_questions"]),
                         (2, 2))
        self.assertEqual(len(self.do("profiles/duplicate", {"id": pid}).json["profiles"]), 2)
        for act in ("pause", "resume", "run"):
            self.assertEqual(self.do(f"profiles/{act}", {"id": pid}).status, 200)
        got = self.do("profiles/delete", {"id": pid})
        self.assertEqual([p["name"] for p in got.json["profiles"]], ["Toronto (copy)"])
        self.assertEqual(self.do("profiles/pause", {"id": pid}).status, 404)
        with store.opened(self.live) as db:
            kept = profiles.one(db, A, pid)
            self.assertIsNotNone(kept["removed_at"])
            self.assertEqual(len(kept["paused"]), 1)
            self.assertTrue(profiles.one(db, A, pid + 1)["run_requested_at"] is None)
        db = self.db()
        try:
            actions = [r["action"] for r in auditlog.recent(db, None)]
        finally:
            db.close()
        self.assertIn("ai_answers.profile.delete", actions)
        self.assertIn("ai_answers.lists", actions)

    def test_one_answer_in_full_and_only_for_its_site(self):
        with store.opened(self.live) as db:
            pid = profiles.create(db, A, profiles.check(PROFILE), "t")
            db.execute("INSERT INTO answers (run_id, site, profile_id, provider, model, qi, try, "
                       "question, sent, asked_at, day, ok, text, citations, cost, location) VALUES "
                       "(1, ?, ?, 'openai', 'm', 0, 1, 'Q?', 'Q?', 'x', '2026-10-11', 1, 'The text', "
                       "'[{\"url\": \"https://example.com/\"}]', 0.03, 'api')", (A, pid))
            db.commit()
        got = self.get("ai-answers/answer?id=1", "viewer@example.com")
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["answer"]["text"], "The text")
        cookie, _ = self.session()
        self.assertEqual(self.call("GET", f"/traffic/{B}/ai-answers/answer?id=1", cookie=cookie).status, 403)
        self.assertEqual(self.get("ai-answers/answer?id=2").status, 404)
        self.assertEqual(self.call("GET", T + "ai-answers").status, 401)


class Basic(Server):
    MODE = "basic"

    def test_not_found_in_basic_mode(self):
        self.assertEqual(self.call("GET", T + "ai-answers").status, 404)


if __name__ == "__main__":
    unittest.main()

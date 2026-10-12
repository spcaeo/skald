"""Settings > Integrations, second security review: the webhook test is
limited to 3 in 10 minutes per user, and the audit log keeps only the
webhook address's host, never its path or query (a token often lives
there). Hosts are example.com; the secrets are made up."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_integrations_api import Base  # noqa: E402
from test_conversions_outgoing import Catcher  # noqa: E402


class Limits(Base):
    def setUp(self):
        super().setUp()
        self.catcher = Catcher()
        self.addCleanup(self.catcher.stop)
        url = self.catcher.url.replace("/hook?x=1", "/hook/tok_PATHSECRET?key=QUERYSECRET")
        got = self.do("webhooks/add", {"url": url, "events": ["lead.won"]})
        self.assertEqual(got.status, 200, got.json)
        self.wid = got.json["webhook"]["id"]

    def test_three_tests_in_ten_minutes(self):
        for _ in range(3):
            self.assertEqual(self.do("webhooks/test", {"id": self.wid}).status, 200)
        late = self.do("webhooks/test", {"id": self.wid})
        self.assertEqual(late.status, 429, late.json)
        self.assertEqual(len(self.catcher.got), 3)

    def test_audit_keeps_the_host_only(self):
        self.assertEqual(self.do("webhooks/remove", {"id": self.wid}).status, 200)
        logged = json.dumps(self.audit())
        self.assertNotIn("PATHSECRET", logged)
        self.assertNotIn("QUERYSECRET", logged)
        self.assertIn("127.0.0.1", logged)


if __name__ == "__main__":
    unittest.main()

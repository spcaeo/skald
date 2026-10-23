"""POST <page>/integrations/leadfile (integrations_api.py): the one-file lead
helper as a download, for admins only; the secret in the file only when the
request carries the lead hook's own; never in the audit log. Hosts are
example.com; the secrets are made up."""
from __future__ import annotations

import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_integrations_api import Base, T  # noqa: E402

from auth_support import A  # noqa: E402

HOOK = f"https://www.example.com/traffic-hooks/{A}/lead"


class LeadFile(Base):
    def test_without_a_secret_the_file_reads_the_environment(self):
        got = self.do("leadfile", {"lang": "php"})
        self.assertEqual(got.status, 200, got.raw[:200])
        self.assertEqual(got.header("Content-Disposition"),
                         'attachment; filename="skald-lead.php"')
        self.assertEqual(got.header("Cache-Control"), "no-store")
        text = got.raw.decode()
        self.assertIn(HOOK, text)
        self.assertIn("getenv('SKALD_LEAD_SECRET')", text)
        self.assertNotIn("skh_", text)
        for lang, name in (("node", "skald-lead.cjs"), ("python", "skald_lead.py")):
            got = self.do("leadfile", {"lang": lang})
            self.assertEqual(got.status, 200)
            self.assertIn(f'filename="{name}"', got.header("Content-Disposition"))

    def test_the_secret_goes_in_only_when_sent_and_only_the_hooks_own(self):
        self.assertEqual(self.do("leadfile", {"lang": "php", "secret": "skh_made_up_secret"})
                         .status, 409, "no lead secret yet")
        value = self.do("secret", {"tool": "lead"}).json["secret"]
        got = self.do("leadfile", {"lang": "python", "secret": value})
        self.assertEqual(got.status, 200)
        self.assertIn(value, got.raw.decode())
        got = self.do("leadfile", {"lang": "python"})
        self.assertNotIn(value, got.raw.decode(), "not unless the request carries it")
        wrong = self.do("leadfile", {"lang": "php", "secret": "skh_" + "x" * 40})
        self.assertEqual(wrong.status, 400)
        self.assertIn("not this site's lead secret", wrong.json["error"])
        got = self.do("leadfile", {"lang": "wordpress", "secret": value})
        self.assertEqual(got.header("Content-Type"), "application/zip")
        self.assertIn('filename="skald-leads.zip"', got.header("Content-Disposition"))
        with zipfile.ZipFile(io.BytesIO(got.raw)) as z:
            self.assertIn(value, z.read("skald-leads/skald-leads.php").decode())
        log = self.audit()
        self.assertIn("hook.leadfile", [e["action"] for e in log])
        self.assertNotIn(value, json.dumps(log))

    def test_refusals(self):
        self.assertEqual(self.do("leadfile", {"lang": "ruby"}).status, 400)
        self.assertEqual(self.do("leadfile", {"lang": "php"}, "viewer@example.com").status, 403)
        cookie, _ = self.session()
        self.assertEqual(self.call("GET", T + "integrations/leadfile", cookie=cookie).status, 405)
        self.assertEqual(self.post(T + "integrations/leadfile", {"lang": "php"}, cookie, None)
                         .status, 403, "the CSRF value")
        self.assertEqual(self.do("leadfile", {"lang": "php", "site": "other.example.com"})
                         .status, 403)


if __name__ == "__main__":
    unittest.main()

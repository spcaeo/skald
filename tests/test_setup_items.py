"""The checklist's lines worked out on the server (skald/setup_items.py,
2.39.0) held to the page's own (js/setup-items.js): both get the same answers
(app.json, the doctor's lines, the hook states, the settings, the recipients
still to confirm) and must give the same lines: ids, titles, states, plain
words, the admin's words and the Set up dialog. tests/js/setup-items-parity.mjs
runs the page's function in node. Addresses are RFC 5737; sites example.com."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skald import setup_items  # noqa: E402

JS = ROOT / "tests" / "js" / "setup-items-parity.mjs"
TODAY = "2026-10-18"


def app(live=None, days=(), live_day=TODAY):
    return {"today": TODAY, "live": {"state": "ok", "day": live_day, "figures": live}
            if live is not None else None, "days": list(days)}


def doc(part, state, says="", fix=None, name=None):
    return {"id": part, "part": name or part.title(), "state": state, "says": says, "fix": fix}


def hook(tool, state, attention=False, words="ready", fix=None, name=None):
    return {"tool": tool, "name": name or tool.title(), "state": state, "attention": attention,
            "words": words, "fix": fix}


def settings(to=(), daily=False, weekly=False, ips=None, ips_source="default", days=None,
             search=None):
    return {"search.google_property": {"value": search, "source": "site" if search else "default"},
            "mail.to": {"value": list(to), "source": "site" if to else "default"},
            "mail.daily": {"value": daily, "source": "default"},
            "mail.weekly": {"value": weekly, "source": "default"},
            "privacy.keep_ips": {"value": ips, "source": ips_source},
            "privacy.keep_days": {"value": days, "source": "default"}}


PEOPLE = {"requests": 90, "hits": {"people": 12}, "readers": 9, "by": {"country": {"DE": 5}}}
ALL_OK = [doc("logs", "OK", "read 2 minutes ago"), doc("assets", "OK", "seen"),
          doc("rsc", "OK", "fine"), doc("script", "OK", "the last event came 4 minutes ago")]
FINISHED = {"app": app(PEOPLE), "status": ALL_OK,
            "tools": [hook("lead", "received", words="last received 1 hour ago (kept)")],
            "settings": settings(["owner@example.com"], daily=True, ips="short",
                                 ips_source="site", days=30, search="sc-domain:example.com")}

CASES = [
    {},                                                            # nothing answered yet
    {"status": [], "tools": [], "settings": {}},                   # answered, all empty
    {"app": app({"requests": 40, "hits": {"people": 0}, "by": {"country": {}}})},
    {"app": app({"requests": 40, "hits": {"people": 12},
                 "by": {"country": {"Unknown": 12, "(not set)": 2, "": 1}}})},
    {"app": app({"requests": 5}, live_day="2026-10-17",
                days=[{"day": "2026-10-15", "state": "ok", "readers": 3, "requests": 9},
                      {"day": "2026-10-16", "state": "withheld", "requests": 9},
                      {"day": "2026-10-17", "state": "ok", "requests": 0}])},
    {"app": app(None, days=[{"day": "2026-10-16", "state": "ok", "requests": 7,
                             "hits": {"people": 2}, "by": {"country": {"FR": 2}}}])},
    {"status": [doc("logs", "NEEDS ATTENTION", "the log was last read 3 days ago",
                    "Check the shipper on the site's server."),
                doc("assets", "NEEDS ATTENTION", "no asset requests", "Set report.assets."),
                doc("rsc", "NEEDS ATTENTION", "payloads without the prefetch header",
                    "Add $http_next_router_prefetch to log_format."),
                doc("script", "NEEDS ATTENTION", "the helper does not serve /traffic-js/",
                    "Add the nginx location.")],
     "app": app({"requests": 3})},
    {"status": [doc("logs", "OK", "read"), doc("assets", "OFF", "not needed: no assets"),
                doc("script", "NEEDS ATTENTION", "on; the last event came 3 days ago",
                    "Check the tag.")]},
    {"status": [doc("script", "OFF", "off")], "app": app(PEOPLE)},
    {"status": [doc("script", "NEEDS ATTENTION", "no event yet")]},
    {"tools": [hook("lead", "needs_secret", words="needs a secret"),
               hook("calendly", "received", attention=True,
                    words="last delivery 2 hours ago was refused: bad signature",
                    fix="Paste the signing secret again."),
               hook("cal", "ready", words="ready: a test passed")]},
    {"tools": [hook("lead", "never", attention=True,
                    words="secret set, but nothing has arrived, not even a test")]},
    {"tools": [hook("lead", "missing", attention=True, words="its secret comes from X",
                    fix=None)]},
    {"tools": [hook("lead", "ready", words="ready: a test passed 1 hour ago"),
               hook("calendly", "received", words="last received 1 hour ago (kept)")]},
    {"tools": [hook("lead", "needs_secret", words="needs a secret")]},
    # Leads arrive, but the last ones came without a country (roads.unplaced).
    {"tools": [hook("calendly", "received", words="last received 1 hour ago (kept)"),
               {**hook("lead", "received", words="last received 2 hours ago (kept)"),
                "unplaced": {"leads": 3, "no_vid": True,
                             "says": "Your last 3 leads came without a visitor ID or the "
                                     "visitor's address, so their country and the pages they "
                                     "read are not recorded",
                             "fix": "Pass the visitor's address as `ip` in the lead call."}}]},
    {"tools": [{**hook("lead", "received", words="last received 2 hours ago (kept)"),
                "unplaced": None}]},
    {"settings": settings(["a@example.com", "b@example.com"], daily=True), "waiting":
        ["b@example.com"]},
    {"settings": settings(["a@example.com"], daily=False, weekly=False)},
    {"settings": settings(["a@example.com"], weekly=True, ips="full", ips_source="org")},
    {"settings": settings(["a@example.com", "b@example.com"], daily=True, ips=True,
                          ips_source="upgrade", days=90)},
    {"settings": settings(ips=False, ips_source="site")},
    {"settings": settings(ips="off", ips_source="install", days=14)},
    {"settings": settings(search="https://example.com/")},             # 2.40: Search Console
    {"settings": {k: v for k, v in settings().items() if k != "search.google_property"}},
    FINISHED,
    # Your own tools: one optional line each, every state.
    {"yourtools": [{"tool": "ga4", "name": "Google Analytics", "state": s, "words": w}
                   for s, w in (("off", "Not connected"),)]},
    {"yourtools": [{"tool": "ga4", "name": "Google Analytics", "state": s, "words": w}
                   for s, w in (("answering", "Answering"),)], **FINISHED},
    {"yourtools": [{"tool": t, "name": t.upper(), "state": s, "words": w} for t, s, w in (
        ("a", "off", "Paused"), ("b", "no_key", "Needs its key"),
        ("c", "waiting", "Waiting for its first answer"), ("d", "failing", "Last try failed"),
        ("e", "stopped", "Stopped answering"), ("f", "withheld", "Withheld"))]},
    {"yourtools": []},
]


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class SameLinesAsThePage(unittest.TestCase):
    def test_python_and_the_page_give_the_same_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cases.json"
            src.write_text(json.dumps(CASES))
            done = subprocess.run(["node", str(JS), str(src)], capture_output=True, text=True,
                                  timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        pages = json.loads(done.stdout)
        self.assertEqual(len(pages), len(CASES))
        for n, (case, page) in enumerate(zip(CASES, pages)):
            got = setup_items.items(case.get("app"), status=case.get("status"),
                                    tools=case.get("tools"), settings=case.get("settings"),
                                    waiting=case.get("waiting", []),
                                    yourtools=case.get("yourtools"))
            with self.subTest(case=n):
                self.assertEqual([i["id"] for i in got], [i["id"] for i in page["items"]])
                self.assertEqual([i["state"] for i in got], [i["state"] for i in page["items"]])
                self.assertEqual(got, page["items"])
                self.assertEqual(setup_items.done(got), page["done"])


class Lines(unittest.TestCase):
    def test_a_fresh_site(self):
        got = {i["id"]: i for i in setup_items.items(None, status=[], tools=[],
                                                     settings=settings())}
        self.assertEqual(list(got), ["logs", "assets", "countries", "script", "lead", "mail",
                                     "privacy", "search"])
        self.assertEqual(got["logs"]["state"], "todo")
        self.assertEqual({k: setup_items.job_of(v) for k, v in got.items()},
                         {"logs": "logs", "assets": None, "countries": None, "script": "script",
                          "lead": "lead", "mail": None, "privacy": "privacy",
                          "search": "search"})
        self.assertFalse(setup_items.done(list(got.values())))

    def test_a_finished_site(self):
        got = setup_items.items(FINISHED["app"], status=FINISHED["status"],
                                tools=FINISHED["tools"], settings=FINISHED["settings"])
        self.assertTrue(all(i["state"] == "done" for i in got), got)
        self.assertTrue(setup_items.done(got))
        self.assertEqual([setup_items.job_of(i) for i in got], [None] * len(got))
        self.assertIn("kept shortened with each visit for 30 days",
                      next(i for i in got if i["id"] == "privacy")["says"])

    def test_jobs_are_the_agent_jobs_and_never_countries_or_mail(self):
        self.assertEqual(setup_items.JOBS, ("logs", "script", "lead", "rsc", "assets", "privacy",
                                            "search", "connect-tools"))
        self.assertEqual(setup_items.job_of({"state": "todo", "act": "connect-tools"}),
                         "connect-tools", "a tool's line is the connect-tools job")
        for act in ("countries", "mail"):
            self.assertIsNone(setup_items.job_of({"state": "todo", "act": act}))


if __name__ == "__main__":
    unittest.main()

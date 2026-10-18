"""Plain words in what a person reads (UI review, 2026-10-18).

  * an assistant has one name: the JavaScript table (labels.js) and the
    Python one (visits.ASSISTANTS) are the same;
  * an insight's title says its metric in words ("visitors", "AI fetches"),
    never the stored key ("readers", "ai_fetches");
  * the app's own strings name no file, config key, variable or shell road
    (leads.json, alerts.enabled, docs/HOSTING.md, $request_time,
    skald('track', ...), SSH tunnel, "(CMS)"); Help keeps the exact names;
  * the request log says "page view", and an assistant by its name;
  * the real-time legend swatch and robots.txt's rule key are two classes.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skald import funnels, insights, visits  # noqa: E402

APP = ROOT / "skald" / "webapp"
TECH = re.compile(r"leads\.json|alerts\.enabled|docs/HOSTING\.md|\$request_time|skald\('track'"
                  r"|SSH tunnel|\(CMS\)|file downloads")
GENERATED = {"help-data.js", "about-data.js", "help-index.js"}


def strings_of(src: str):
    """The string literals of a JS file, comments left out."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = "\n".join(line.split("//")[0] if line.lstrip().startswith("//") else line
                    for line in src.splitlines())
    return re.findall(r'"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`', src)


class Words(unittest.TestCase):

    def test_one_name_per_assistant(self):
        js = (APP / "js" / "labels.js").read_text()
        body = re.search(r"export const ASSISTANTS = \{(.*?)\};", js, re.S).group(1)
        table = dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', body))
        self.assertEqual(table, visits.ASSISTANTS)
        self.assertEqual(visits.assistant_label("chatgpt.com"), "ChatGPT")

    def test_insight_titles_say_words(self):
        for key in ("readers", "ai_fetches", "bots", "search", "server_errors"):
            said = insights._words(key)
            self.assertNotIn("_", said)
            self.assertNotEqual(said, "readers")
        self.assertEqual(insights._words("readers"), "visitors")

    def test_no_technical_words_in_app_strings(self):
        found = []
        for path in sorted((APP / "js").rglob("*.js")):
            if path.name in GENERATED or "vendor" in path.parts:
                continue
            found += [f"{path.name}: {s[:80]}" for s in strings_of(path.read_text()) if TECH.search(s)]
        self.assertEqual(found, [])
        labels = [st["label"] for f in funnels.defaults() for st in f["steps"]]
        self.assertFalse([x for x in labels if "(CMS)" in x])

    def test_rt_legend_and_robots_rule_are_two_classes(self):
        rt = (APP / "css" / "realtime.css").read_text()
        self.assertIsNone(re.search(r"^\.rt-k\b", rt, re.M),
                          "realtime.css must not style robots.txt's .rt-k")
        self.assertIn(".rtm-k", rt)
        self.assertIn('"rtm-k"', (APP / "js" / "tabs" / "realtime.js").read_text())


if __name__ == "__main__":
    unittest.main()

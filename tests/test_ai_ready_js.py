"""AI readiness in the page (2.35): js/ai-ready.js's six lines, the block and the list
(tests/js/ai-ready.mjs), and js/robots-match.js held to skald/robots_match.py's
answers on made-up robots.txt rules and paths."""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skald import robots_match  # noqa: E402

JS = ROOT / "tests" / "js" / "ai-ready.mjs"


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestAiReadyJs(unittest.TestCase):
    def node(self, *args: str) -> str:
        done = subprocess.run(["node", str(JS), *args], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def test_the_lines_the_block_and_the_list(self):
        self.assertIn("ai-ready: all passed", self.node())

    def test_the_page_and_the_server_read_robots_txt_alike(self):
        rnd = random.Random(11)
        bits = ["/", "/blog", "/blog/", "/a*", "*.php", "/x$", "/%7Eu", "/%7eu/", "/café", "/b*c$",
                "*", "/docs/*/v1", "/a%2Fb", "/$", "/*/end$", "/%E2%9C%93"]
        paths = ["/", "/blog/x", "/a1/b", "/index.php", "/x", "/xy", "/~u/1", "/caf%C3%A9", "/bxc",
                 "/docs/a/v1/z", "/a/b", "/a%2fb", "/q/end", "/✓", "/%E2%9C%93/"]
        cases = []
        for _ in range(600):
            rules = [[rnd.choice(["allow", "disallow"]), rnd.choice(bits)] for _r in range(rnd.randint(0, 4))]
            cases.append({"rules": rules, "path": rnd.choice(paths)})
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cases.json"
            src.write_text(json.dumps(cases))
            got = json.loads(self.node(str(src)))
        for case, js in zip(cases, got):
            allowed, rule = robots_match.decide(case["rules"], case["path"])
            self.assertEqual((js["allowed"], js["rule"]), (allowed, rule), case)


if __name__ == "__main__":
    unittest.main()

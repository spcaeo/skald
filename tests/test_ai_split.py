"""SKALD-49: the web app's page test for AI fetches (tabs/ai-split.js formatOf) says what
ai_formats.format_of says, for the same paths. The feed hides a row by the JS rule and the
figures count by the Python one: they must never disagree."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skald.ai_formats import format_of  # noqa: E402

PATHS = [
    "/", "/pricing/", "/blog/ai-crawlers-explained", "/features/?utm_source=perplexity",
    "/robots.txt", "/ROBOTS.TXT", "/llms.txt", "/llms-full.txt", "/docs/llms.txt",
    "/guide.md", "/guide.MDX", "/sitemap.xml", "/sitemap_index.xml", "/post-sitemap.xml",
    "/notes.txt", "/_astro/monday-com-vs-bonterra.jpg", "/img/a.webp", "/a.avif", "/f.woff2",
    "/css/sk-base.css?v=cf7fdc06", "/js/sk.js", "/_next/static/chunks/app.js", "/static/x",
    "/assets/logo", "/feed.rss", "/report.pdf", "/api/v1/jobs", "/api", "/collect",
    "/beacon", "/ping", "/pinguin/", "/apiary/", "/page?_rsc=abc", "/page?x=1&_data=r",
    "/page?__flight__=1", "/a.json", "/manifest.webmanifest", "/download.zip", "/x.html",
]


class TestSameRule(unittest.TestCase):
    def test_js_and_python_agree(self):
        script = (
            "const M = await import(process.argv[1]);"
            "console.log(JSON.stringify(JSON.parse(process.argv[2]).map((p) => M.formatOf(p))));")
        mod = (ROOT / "skald/webapp/js/tabs/ai-split.js").as_uri()
        done = subprocess.run(["node", "--input-type=module", "-e", script, mod, json.dumps(PATHS)],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        got = dict(zip(PATHS, json.loads(done.stdout)))
        for path in PATHS:
            self.assertEqual(got[path], format_of(path.split("?", 1)[0], path), path)


if __name__ == "__main__":
    unittest.main()

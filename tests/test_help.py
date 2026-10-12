"""The Help pages are built from docs/help/*.md: the built files must match them."""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "skald" / "webapp" / "js"
HELP = ROOT / "docs" / "help"


def data(name):
    text = (JS / name).read_text(encoding="utf-8")
    return text, json.loads(re.search(r"export default (.*);\n$", text, re.S).group(1))


class HelpData(unittest.TestCase):
    def test_the_built_files_match_the_guides(self):
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "build-about.py"), "--check"], capture_output=True)
        self.assertEqual(done.returncode, 0, "js/help-data.js or js/help-index.js is stale: run tools/build-about.py")

    def test_every_guide_is_built_with_a_title_and_a_summary(self):
        _, built = data("help-data.js")
        _, index = data("help-index.js")
        names = sorted(p.stem for p in HELP.glob("*.md") if p.stem.lower() != "readme")
        self.assertEqual(sorted(g["id"] for g in built["guides"]), names)
        self.assertEqual([g["id"] for g in index], [g["id"] for g in built["guides"]])
        for g in built["guides"]:
            self.assertTrue(g["title"] and g["summary"] and g["blocks"], g["id"])

    def test_links_go_to_a_guide_or_a_page_of_the_app(self):
        text, built = data("help-data.js")
        ids = {g["id"] for g in built["guides"]}
        tabs = set(re.findall(r'\["([a-z/]+)", "[^"]+"\]', (JS / "state.js").read_text(encoding="utf-8")))
        for href in re.findall(r'"href":"([^"]+)"', text):
            if href.startswith("https://"):
                continue
            m = re.match(r"^#help\?part=([a-z-]+)$", href)
            if m:
                self.assertIn(m.group(1), ids, href)
            else:
                self.assertIn(href.lstrip("#").split("?")[0], tabs, href)

    def test_no_markup_secret_or_real_address_reaches_the_page(self):
        text, built = data("help-data.js")
        # Markup may appear only as an example: in a code block or a `code` piece, drawn as text.
        prose = []

        def walk(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    if not (k == "code" or (k == "text" and x.get("t") == "pre")):
                        walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
            elif isinstance(x, str):
                prose.append(x)
        walk(built)
        words = "\n".join(prose)
        for bad in ("<script", "<style", "javascript:", "<br", "<sub>"):
            self.assertNotIn(bad, words)
        # Examples use RFC 5737 addresses and example.com only.
        for ip in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text):
            self.assertRegex(ip, r"^(192\.0\.2|198\.51\.100|203\.0\.113)\.", ip)
        self.assertNotIn("acme", text.lower())
        self.assertNotRegex(text, r"skald_[0-9a-f]{6,}_[A-Za-z0-9]{8,}")


if __name__ == "__main__":
    unittest.main()

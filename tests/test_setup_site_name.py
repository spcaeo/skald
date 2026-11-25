"""SKALD-57: every set-up step names the site exactly as it was added. A site added as
www.example.com is never told about www.www.example.com; a site added as example.com is
never told about www.example.com. Covers the kit's READMEs and scripts, the agent pack's
Cloudflare notes and logs job, and the web app's set-up steps (tests/js/setup-site-name.mjs)."""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "skald" / "kit"
# Every kit file that holds __SITE__ and is read by a person (or an agent).
SHOWN = ["README-docker.txt", "README-systemd.txt", "setup-pack/cloudflare.md",
         "setup-pack/vercel-netlify.md", "setup-pack/START-HERE.md", "agent/jobs/logs.md"]
# The only places a script still puts "www." before the site: matching a web server's
# own host names (a bare site's server block may name www.<site>), and install-server.sh's
# lookup of nginx's $host, which skips it for a site that already starts with www.
MATCHING = {
    "check.sh": ['*" www.$SITE "*|*" $SITE "*|*" .$SITE "*|*" *.$SITE "*)'],
    "install-server.sh": ['if (a[j] == site || a[j] == "www." site || a[j] == "." site || a[j] == "*." site) hit = 1',
                          'if (a[j] == site || a[j] == "www." site || a[j] == "*." site) hit = 1',
                          'local p q name ald=/var/log/apache2 alt="www.$SITE"'],
}


class Kit(unittest.TestCase):
    def test_no_template_puts_www_before_the_site(self):
        for path in sorted(KIT.rglob("*")):
            if path.suffix not in {".md", ".txt", ".sh"}:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("www.__SITE__", text, path.name)
            allowed = MATCHING.get(path.name, [])
            for line in text.splitlines():
                if re.search(r'www\.(\$\{?SITE|" ?site)', line):
                    self.assertIn(line.strip(), allowed, f"{path.name}: {line.strip()}")

    def test_the_shown_files_name_the_site_as_added(self):
        for name in SHOWN:
            source = (KIT / name).read_text(encoding="utf-8")
            if "__SITE__" not in source:
                continue
            www = source.replace("__SITE__", "www.example.com")
            self.assertNotIn("www.www.", www, name)
            bare = source.replace("__SITE__", "example.com")
            self.assertNotIn("www.example.com", bare, name)

    def test_the_cloudflare_route(self):
        for name in ("setup-pack/cloudflare.md", "agent/jobs/logs.md"):
            text = (KIT / name).read_text(encoding="utf-8").replace("__SITE__", "www.example.com")
            self.assertIn("`www.example.com/*`", text, name)


class SetupSteps(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_web_app_steps(self):
        js = ROOT / "tests" / "js" / "setup-site-name.mjs"
        got = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=120)
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)
        self.assertIn("setup-site-name: all passed", got.stdout)


if __name__ == "__main__":
    unittest.main()

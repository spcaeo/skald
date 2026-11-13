"""A referrer that urllib cannot split never stops a count (#61).

On 13 Nov 2026 a router-attack scanner sent the referrer
"{[RootURL]}/admin/more.html". urlsplit raises ValueError ("Invalid IPv6 URL")
on a host part holding "[" or "]" that is not an IPv6 address, and the live
count of the site crashed on every round from then on. What is pinned:
- the day's collect, its audit, the live count and the live audit all end 0
  with such lines in the log, from a scanner and from a browser reading a page;
- such a referrer has no host: no source, no citation, no own-site asset;
- the audit agrees with the count (both treat it as a referrer with no host);
- a citation from an assistant that shares its host (bing.com/chat) still reads;
- guard: no urlsplit of a referrer anywhere in skald outside a try that
  catches ValueError (urlhost.py is the main code's one road).
"""
from __future__ import annotations

import ast
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import CHROME, Sandbox, line  # noqa: E402

from skald import classify, dimensions  # noqa: E402

UTC = timezone.utc
BAD = ("{[RootURL]}/admin/more.html", "http://[RootURL/x", "https://[::1/", "//[a]b/")


class ReadAsNoHost(unittest.TestCase):

    def test_each_part_gives_no_host(self):
        for ref in BAD:
            with self.subTest(ref=ref):
                self.assertEqual(dimensions.referrer_host(ref), "")
                self.assertEqual(classify.cited_by(ref), "")

    def test_a_good_citation_still_reads(self):
        self.assertEqual(classify.cited_by("https://www.bing.com/chat?q=x"),
                         "copilot.microsoft.com")
        self.assertEqual(dimensions.referrer_host("https://www.google.com/"), "google.com")


class NoUnguardedSplit(unittest.TestCase):

    def test_every_referrer_split_catches_value_error(self):
        root = Path(__file__).resolve().parent.parent / "skald"
        bare = []
        for path in root.rglob("*.py"):
            if ".claude" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            guarded = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Try) and any(
                        h.type is not None and "ValueError" in ast.unparse(h.type)
                        for h in node.handlers):
                    for part in node.body:
                        guarded.update(id(n) for n in ast.walk(part))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and ast.unparse(node.func).endswith("urlsplit") \
                        and node.args and "ref" in ast.unparse(node.args[0]).lower() \
                        and id(node) not in guarded:
                    bare.append(f"{path.name}:{node.lineno}")
        self.assertEqual(bare, [], "split a referrer with urlhost.split / host_of, or "
                                   "catch ValueError (#61)")


class TheDayStillCounts(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.now = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)

    def lines(self, day_start: datetime) -> list[str]:
        out = []
        for i, ref in enumerate(BAD):
            when = day_start + timedelta(minutes=10 + i)
            out.append(line(when, f"198.51.100.{20 + i}", "/goform/set_hidessid_cfg",
                            "Mozilla/5.0", referrer=ref, status=404))
            out.append(line(when, f"203.0.113.{20 + i}", "/pricing/", CHROME, referrer=ref))
            out.append(line(when, f"203.0.113.{20 + i}", "/app.css", CHROME, referrer=ref))
        out.append(line(day_start + timedelta(hours=1), "203.0.113.50", "/", CHROME,
                        referrer="https://www.google.com/"))
        return out

    def test_collect_and_audit_of_the_day(self):
        self.box.log(self.lines(datetime(2026, 10, 5, 8, 0, tzinfo=UTC)))
        code, out, err = self.box.run("--today", "2026-10-06", "collect")
        self.assertEqual(code, 0, err + out)
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 0, err + out)

    def test_live_and_its_audit(self):
        self.box.log(self.lines(self.now - timedelta(hours=2)))
        with mock.patch("skald.cli._now", return_value=self.now):
            code, out, err = self.box.run("live")
            self.assertEqual(code, 0, err + out)
            code, out, err = self.box.run("audit", "--live")
        self.assertEqual(code, 0, err + out)


if __name__ == "__main__":
    unittest.main()

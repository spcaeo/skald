"""No "unknown" in anything a person reads (owner, 2026-10-18).

History keeps the stored names "Direct or unknown" and "Unknown" (the audit
compares them, and old days would split from new ones if they changed). What a
person reads goes through skald/labels.py or webapp/js/labels.js:
"Direct" and "Not recorded". Pinned here, for a sample day with direct visits
and visits whose country the log did not record:

  * the mail, both parts, says neither word;
  * every label in the app's data files, as the app shows it, says neither;
  * the two label tables (Python and JavaScript) are the same;
  * no string in the app's own code says "unknown", except the stored names
    it compares against;
  * the stored names themselves are unchanged.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import countries, dimensions, labels, mailer, webapp  # noqa: E402
from skald.config import load_config  # noqa: E402
from skald.store import History  # noqa: E402

from support import SECRETS, UTC, Sandbox, day_lines, line, totals_for  # noqa: E402

APP = Path(webapp.__file__).resolve().parent
DAY = date(2026, 10, 6)
WORD = re.compile(r"unknown", re.I)


def sample(day: date) -> list[str]:
    """day_lines' readers (five of six direct), and three direct readers whose
    country the log did not record."""
    noon = datetime(day.year, day.month, day.day, 15, tzinfo=UTC)
    return day_lines(day, 6) + [
        line(noon + timedelta(minutes=i), f"203.0.113.{60 + i}", "/", country="-")
        for i in range(3)]


def strings(obj):
    """Every key and string value in a JSON document."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)
    elif isinstance(obj, str):
        yield obj


class StoredNamesStay(unittest.TestCase):

    def test_the_stored_names_are_unchanged(self):
        self.assertEqual(dimensions.source_type("", "/", False, set()), "Direct or unknown")
        self.assertEqual(countries.UNKNOWN, "Unknown")

    def test_shown_and_stored_turn_into_each_other(self):
        self.assertEqual(labels.shown("Direct or unknown"), "Direct")
        self.assertEqual(labels.shown("Unknown"), "Not recorded")
        self.assertEqual(labels.stored("Direct"), "Direct or unknown")
        self.assertEqual(labels.stored("Not recorded"), "Unknown")
        self.assertEqual(labels.shown("Search engine"), "Search engine")
        self.assertEqual(labels.shown_text("from Direct or unknown, 3 pages"), "from Direct, 3 pages")
        self.assertEqual(countries.label("Unknown"), "Not recorded")


class TheMail(unittest.TestCase):

    def test_neither_part_says_unknown(self):
        box = Sandbox()
        self.addCleanup(box.close)
        history = History(box.db)
        self.addCleanup(history.close)
        totals = totals_for(sample(DAY))
        by = totals.groups[next(iter(totals.groups))].by
        self.assertIn("Unknown", by["country"], "the sample has an unrecorded country")
        self.assertIn("Direct or unknown", by["source"], "the sample has direct visits")
        history.record("example.com", DAY, totals, "UTC", [])
        with mock.patch.dict(os.environ, SECRETS):
            msg = mailer.build("daily", load_config(box.config), history, UTC,
                               datetime(2026, 10, 7, 9, tzinfo=UTC))
        text = msg.get_body(("plain",)).get_content()
        html = msg.get_body(("html",)).get_content()
        self.assertIn("Not recorded", text)
        self.assertIn("Direct", text)
        for part in (text, html):
            m = WORD.search(part)
            self.assertIsNone(m, part[max(0, m.start() - 80):m.start() + 80] if m else "")


class TheApp(unittest.TestCase):

    def test_every_label_in_the_data_is_shown_without_unknown(self):
        box = Sandbox()
        self.addCleanup(box.close)
        text = box.config.read_text().replace("  app: false\n", "  app: true\n")
        box.config.write_text(text)
        box.log(sample(DAY))
        self.assertEqual(box.run("--today", "2026-10-07", "collect")[0], 0)
        code, _, err = box.run("--today", "2026-10-07", "dashboard")
        self.assertEqual(code, 0, err)
        folder = box.root / "www" / "example.com" / "data"
        raw = " ".join(p.read_text() for p in folder.glob("*.json"))
        self.assertIn("Direct or unknown", raw, "the data keeps the stored name")
        bad = set()
        for path in folder.glob("*.json"):
            for s in strings(json.loads(path.read_text())):
                if WORD.search(labels.shown_text(s)) and not re.fullmatch(r"[a-z]+(_[a-z]+)+", s):
                    bad.add((path.name, s))     # an identifier such as unknown_medium is a key, not words
        self.assertEqual(bad, set())

    def test_the_two_label_tables_agree(self):
        js = (APP / "js" / "labels.js").read_text()
        body = re.search(r"export const SHOWN = \{(.*?)\};", js, re.S).group(1)
        pairs = dict(re.findall(r'"?([^":\n]+?)"?:\s*"([^"]*)"', body))
        self.assertEqual({k.strip(): v for k, v in pairs.items()}, labels.SHOWN)

    def test_the_code_says_unknown_only_to_compare_stored_names(self):
        allowed = {"Direct or unknown", "Unknown", "unknown", "unknown_medium"}
        found = []
        for path in sorted((APP / "js").rglob("*.js")):
            if path.name in ("labels.js",):
                continue
            for i, text in enumerate(path.read_text().splitlines(), 1):
                code = re.sub(r"^\s*(//|/\*|\*).*$", "", text)
                code = re.sub(r"\s//\s.*$", "", code)
                code = re.sub(r"\.[Uu]nknown\b|\b[Uu]nknown\[", "", code)   # a field such as got.unknown
                for lit in re.findall(r'"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`', code):
                    s = re.sub(r"\$\{[^}]*\}", "", lit[0] or lit[1])  # code inside a template is not words
                    if WORD.search(s) and s not in allowed:
                        found.append(f"{path.relative_to(APP)}:{i}: {s[:80]}")
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()

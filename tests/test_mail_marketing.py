"""The Monday marketing mail (skald/mail_marketing.py).

  * off by default; on Mondays only; its own switch (mail.marketing) in Mail & reports
  * Skald's part: the weekly mail's own figures (mail_html.figures, _sources) for the
    same 7 whole days, the change only when both weeks are whole
  * each connected tool apart, under "Counted from: <tool>", its own period; a figure
    not given is "Not given", never 0; a withheld tool says so and shows nothing
  * a week not whole refuses the mail by design; the run-daily step sends it once
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from html import unescape
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import mail_html, mail_marketing, mailer, settings_store  # noqa: E402
from skald.config import load_config  # noqa: E402
from skald.store import History  # noqa: E402
from skald.yourtools import conn, sync  # noqa: E402

from support import SECRETS, UTC, Sandbox, day_lines, totals_for  # noqa: E402
from test_yourtools_ga4 import PROP, Google, service_key  # noqa: E402

ANCHOR = date(2026, 10, 25)
NOW = datetime(2026, 10, 26, 9, tzinfo=UTC)               # a Monday
BRAND = {"name": "Skald", "version": "1.0.0", "tagline": "Every visit, truly told.",
         "release": 70, "commit": "abc", "deployed_at": None}


def flat(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


class Base(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.history = History(self.box.db)
        self.addCleanup(self.history.close)
        patch = mock.patch("skald.brand.load", return_value=BRAND)
        patch.start()
        self.addCleanup(patch.stop)
        self.config = load_config(self.box.config)
        self.folder = Path(self.box.db).parent

    def fill(self, days: int):
        for i in range(days):
            day = ANCHOR - timedelta(days=i)
            self.history.record("example.com", day, totals_for(day_lines(day, 3 if i < 7 else 2)),
                                "UTC", [])

    def ga4(self):
        sync.connect(self.config, self.folder, "example.com", "ga4", {"property": PROP}, "cli",
                     key=service_key())
        job = sync.Job(self.config, "example.com", self.folder, NOW, lambda *a: None,
                       lambda *a: None, opener=Google(), sleep=lambda s: None,
                       send=lambda *a: None)
        self.assertEqual(sync.run(job), 0)

    def build(self):
        with mock.patch.dict(os.environ, SECRETS):
            msg = mail_marketing.build(self.config, self.history, UTC, NOW, self.folder)
        return msg, msg.get_body(("html",)).get_content(), msg.get_body(("plain",)).get_content()


class Switch(unittest.TestCase):
    def test_off_by_default_and_mondays_only(self):
        key = settings_store.SCHEMA["mail.marketing"]
        self.assertEqual((key.kind, key.default, key.config, key.label),
                         ("bool", False, ("mail", "marketing"), "Monday marketing mail"))
        self.assertFalse(mail_marketing.on({}))
        self.assertTrue(mail_marketing.on({"mail": {"marketing": True}}))
        ctx = SimpleNamespace(now=NOW, config={"mail": {"marketing": True}})
        self.assertTrue(mail_marketing.due(ctx))
        ctx.now = NOW + timedelta(days=1)
        self.assertFalse(mail_marketing.due(ctx))
        ctx.now, ctx.config = NOW, {}
        self.assertFalse(mail_marketing.due(ctx))


class Built(Base):
    def test_skald_first_then_each_tool_apart(self):
        self.fill(14)
        self.ga4()
        msg, html, text = self.build()
        self.assertIn("marketing week, 19 Oct to 25 Oct 2026", msg["Subject"])
        page = flat(html)
        period = self.history.period("example.com", date(2026, 10, 19), ANCHOR)
        want = mail_html.figures(self.config, self.history, "example.com", UTC, period,
                                 date(2026, 10, 19), ANCHOR)
        self.assertIn(f"Visitors {want['visitors']:,} ▲ 50%", page)
        self.assertIn("Counted from: your server log", page)
        self.assertIn("Where visitors came from", page)
        self.assertIn("Counted from: Google Analytics", page)
        self.assertIn("Sessions 1,234", page)
        self.assertIn("The tool's own period: 2026-09-28 to 2026-10-25", page)
        self.assertIn("Never added to Skald's figures", page)
        self.assertLess(page.index("Counted from: your server log"),
                        page.index("Counted from: Google Analytics"))
        self.assertIn("Counted from: Google Analytics\n  Sessions: 1,234", text)
        self.assertNotIn("calendly", text.lower())          # not connected: not listed

    def test_not_given_and_withheld(self):
        self.fill(14)
        self.ga4()
        tools = mail_marketing.tools(self.config, self.folder, "example.com", NOW)
        tools[0]["headline"][2]["value"] = None
        rows, _ = mail_marketing._tool_lines(tools[0])
        self.assertEqual(rows[2][1], "Not given")
        conn.update(self.folder, "example.com", "ga4", audit={"ok": False})
        _, html, text = self.build()
        self.assertIn("Withheld: Skald's recheck", flat(html))
        self.assertNotIn("1,234", text)

    def test_no_tool_connected(self):
        self.fill(14)
        _, html, _ = self.build()
        self.assertIn("No tool connected", flat(html))
        self.assertIn("owner@example.com, second@example.com are on the report list", flat(html))

    def test_a_week_not_whole_is_refused(self):
        self.fill(5)
        with mock.patch.dict(os.environ, SECRETS), self.assertRaises(mailer.Withheld):
            mail_marketing.build(self.config, self.history, UTC, NOW, self.folder)


class Step(Base):
    def test_run_sends_once_and_dry_run_sends_nothing(self):
        self.fill(14)
        out, err, sent = [], [], []
        ctx = SimpleNamespace(config=self.config, tz=UTC, now=NOW, db_path=self.box.db,
                              out=out.append, err=err.append, by_design=None,
                              history=lambda: History(self.box.db))
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer, "send", lambda msg, cfg: sent.append(msg)):
            self.assertEqual(mail_marketing.run(ctx, dry_run=True), 0)
            self.assertEqual(sent, [])
            self.assertEqual(mail_marketing.run(ctx, dry_run=False), 0)
        self.assertEqual(len(sent), 1)
        self.assertTrue(out[-1].startswith("sent marketing mail to "))

    def test_a_refused_week_stops_by_design(self):
        self.fill(5)
        err = []
        ctx = SimpleNamespace(config=self.config, tz=UTC, now=NOW, db_path=self.box.db,
                              out=print, err=err.append, by_design=None,
                              history=lambda: History(self.box.db))
        with mock.patch.dict(os.environ, SECRETS):
            self.assertEqual(mail_marketing.run(ctx, dry_run=True), 1)
        self.assertTrue(err[0].startswith("marketing mail REFUSED"))
        self.assertTrue(ctx.by_design)

    def test_a_step_of_run_daily(self):
        from skald import cli
        src = Path(cli.__file__).read_text()
        self.assertIn('if mail_marketing.due(ctx):\n        steps.append(("marketing mail", '
                      'lambda: mail_marketing.run(ctx, ctx.args.dry_run)))', src)


if __name__ == "__main__":
    unittest.main()

"""Settings > Mail > Preview (mail_preview.py, settings_api.py): the daily and
weekly mail as the site would send it, built by the real mail code from the
verified history, never sent and needing no SMTP login; refused in the run's
own words when the history cannot give it; for admins only. Hosts are
example.com; the SMTP login named in the fixture is never read."""
from __future__ import annotations

import os
import re
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import mail_preview, mailer  # noqa: E402
from skald.config import load_config  # noqa: E402
from skald.store import History  # noqa: E402

from auth_support import A, SAME, Server  # noqa: E402
from support import UTC, Sandbox, day_lines, totals_for  # noqa: E402

ANCHOR = date(2026, 10, 5)
NOW = datetime(2026, 10, 6, 9, tzinfo=UTC)
T = f"/traffic/{A}/"


def fill(path, site: str, last: date, days: int = 15) -> None:
    with History(path) as history:
        for i in range(days):
            day = last - timedelta(days=i)
            history.record(site, day, totals_for(day_lines(day, 3 if i < 7 else 2)), "UTC", [])


class Build(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.config = load_config(self.box.config)

    def test_the_daily_and_weekly_mail_as_they_would_go_never_sent(self):
        fill(self.box.db, "example.com", ANCHOR)
        # No SMTP login in the environment: the preview never reads one; nothing is sent.
        with mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.object(mailer, "send", side_effect=AssertionError("sent")) as send:
            os.environ.pop("TI_TEST_SMTP_USER", None)
            os.environ.pop("TI_TEST_SMTP_PASSWORD", None)
            daily = mail_preview.build(self.config, self.box.db, "daily", NOW)
            weekly = mail_preview.build(self.config, self.box.db, "weekly", NOW)
        send.assert_not_called()
        self.assertIn("example.com: daily traffic, Mon 5 Oct 2026", daily["subject"])
        self.assertIn("weekly traffic", weekly["subject"])
        for got in (daily, weekly):
            self.assertNotIn("cid:", got["html"])
            flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", got["html"]))
            self.assertIn("Where visitors came from", flat)
        # The same HTML the real mail carries, but for its image.
        with mock.patch.dict(os.environ, {"TI_TEST_SMTP_USER": "u", "TI_TEST_SMTP_PASSWORD": "p"}):
            with History(self.box.db) as history:
                real = mailer.build("daily", self.config, history, UTC, NOW).get_body(("html",)).get_content()
        self.assertEqual(re.sub(r'src="[^"]*"', "", real), re.sub(r'src="[^"]*"', "", daily["html"]))

    def test_no_server_set_up_uses_stand_ins(self):
        conf = {**self.config, "mail": {}}
        got = mail_preview.preview_config(conf)["mail"]
        self.assertEqual((got["host"], got["from"], got["to"]), ("preview.invalid", "sender@preview.invalid", ["recipient@preview.invalid"]))
        fill(self.box.db, "example.com", ANCHOR)
        self.assertIn("daily traffic", mail_preview.build(conf, self.box.db, "daily", NOW)["subject"])

    def test_a_day_not_stored_is_refused_in_words(self):
        with self.assertRaises(mail_preview.NotYet):
            mail_preview.build(self.config, self.box.root / "none.sqlite", "daily", NOW)
        fill(self.box.db, "example.com", ANCHOR - timedelta(days=3))
        with self.assertRaises(mail_preview.NotYet) as got:
            mail_preview.build(self.config, self.box.db, "daily", NOW)
        self.assertIn("would not go now", str(got.exception))
        with self.assertRaises(ValueError):
            mail_preview.build(self.config, self.box.db, "monthly", NOW)


class Route(Server):
    def test_admins_see_it_viewers_do_not(self):
        self.config["site"] = {"name": A}
        self.config["report"] = {"timezone": "UTC"}
        cookie, _ = self.session("viewer@example.com")
        self.assertEqual(self.call("GET", T + "settings/mail-preview?kind=daily", cookie=cookie).status, 403)
        cookie, _ = self.session("admin@example.com")
        got = self.call("GET", T + "settings/mail-preview?kind=daily", cookie=cookie)
        self.assertEqual(got.status, 409, got.json)              # no history yet
        self.assertIn("No history", got.json["error"])
        self.assertEqual(self.call("GET", T + "settings/mail-preview?kind=yearly", cookie=cookie).status, 400)
        fill(self.live / "history.sqlite", A, datetime.now(timezone.utc).date() - timedelta(days=1))
        got = self.call("GET", T + "settings/mail-preview?kind=daily", cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        self.assertIn(f"{A}: daily traffic", got.json["subject"])
        self.assertIn("<html", got.json["html"])
        self.assertEqual(self.post(T + "settings/mail-preview", {}, cookie, self.session("admin@example.com")[1]).status, 405)


class BasicRoute(Server):
    MODE = "basic"

    def test_404_without_accounts(self):
        self.assertEqual(self.call("GET", T + "settings/mail-preview?kind=daily", None, SAME).status, 404)


if __name__ == "__main__":
    unittest.main()

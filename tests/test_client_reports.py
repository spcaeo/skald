"""Client reports (client_reports*.py, client_report_*.py, pdf_writer.py,
audit_client_reports.py): the schedule's arithmetic in the site's zone, the
confirm rule for recipients, a PDF a reader can parse, withheld days listed
and never counted, the second count, and nothing of another organisation.
Hosts and addresses are example.com; client addresses RFC 5737."""
from __future__ import annotations

import json
import re
import smtplib
import struct
import sys
import unittest
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import (accounts, audit_client_reports, client_report_data as data_mod,  # noqa: E402
                          client_report_pdf, client_reports as cr, client_reports_send as rs,
                          mail_confirm, mailer, pdf_writer as pw)
from skald.store import History  # noqa: E402
from skald.verify import Problem  # noqa: E402

from auth_support import A, B, Server  # noqa: E402
from support import Sandbox, day_lines, totals_for  # noqa: E402

UTC = timezone.utc
BERLIN = ZoneInfo("Europe/Berlin")
T = f"/traffic/{A}/"


def spec(**over) -> dict:
    raw = {"name": "Monthly traffic report", "recipients": ["client@example.com"],
           "schedule": {"kind": "monthly", "day": 1, "at": "08:00"}, "period": "last_month",
           "sections": list(cr.SECTIONS), "notes": "We fixed the pricing page.",
           "footer": "Example Agency"}
    raw.update(over)
    return cr.validate(raw)


def fill(path, site: str, first: date, last: date, withheld=(), skip=(), people=3) -> None:
    with History(path) as history:
        d = first
        while d <= last:
            if d not in skip:
                bad = [Problem("test", "does not reconcile")] if d in withheld else []
                history.record(site, d, totals_for(day_lines(d, people + d.day % 3)), "UTC", bad)
            d += timedelta(days=1)


# ------------------------------------------------------------ schedule math

class Schedule(unittest.TestCase):
    def test_weekly_goes_at_its_local_time_in_the_sites_zone(self):
        s = spec(schedule={"kind": "weekly", "weekday": 0, "at": "08:00"}, period="last_week")
        monday = date(2026, 10, 12)
        # 08:00 in Berlin (summer time, UTC+2) is 06:00 UTC.
        self.assertEqual(cr.at_local(s, monday, BERLIN), datetime(2026, 10, 12, 6, 0, tzinfo=UTC))
        self.assertIsNone(cr.latest(s, datetime(2026, 10, 12, 5, 59, tzinfo=UTC), BERLIN))
        self.assertEqual(cr.latest(s, datetime(2026, 10, 12, 6, 0, tzinfo=UTC), BERLIN), monday)
        # After the clocks go back (UTC+1), the same 08:00 is 07:00 UTC.
        self.assertEqual(cr.at_local(s, date(2026, 11, 2), BERLIN),
                         datetime(2026, 11, 2, 7, 0, tzinfo=UTC))
        self.assertEqual(cr.next_send(s, datetime(2026, 10, 12, 6, 0, tzinfo=UTC), BERLIN),
                         datetime(2026, 10, 19, 6, 0, tzinfo=UTC))
        # Late on Sunday in UTC is already Monday in Tokyo.
        tokyo = ZoneInfo("Asia/Tokyo")
        self.assertEqual(cr.latest(s, datetime(2026, 10, 11, 23, 30, tzinfo=UTC), tokyo), monday)

    def test_monthly_day_past_a_short_month_is_its_last_day(self):
        s = spec(schedule={"kind": "monthly", "day": 31, "at": "09:30"})
        got = cr.scheduled_days(s, date(2027, 1, 1), date(2027, 4, 30))
        self.assertEqual(got, [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31),
                               date(2027, 4, 30)])

    def test_every_n_days_from_a_start(self):
        s = spec(schedule={"kind": "custom", "every": 14, "start": "2026-10-01", "at": "07:45"})
        self.assertEqual(cr.scheduled_days(s, date(2026, 9, 1), date(2026, 11, 1)),
                         [date(2026, 10, 1), date(2026, 10, 15), date(2026, 10, 29)])

    def test_a_time_the_clocks_skip_still_goes_once(self):
        s = spec(schedule={"kind": "weekly", "weekday": 6, "at": "02:30"})
        when = cr.at_local(s, date(2027, 3, 28), BERLIN)          # 02:30 does not exist that day
        self.assertEqual(when, datetime(2027, 3, 28, 1, 30, tzinfo=UTC))

    def test_periods(self):
        self.assertEqual(cr.period_for("last_week", date(2026, 10, 14)),
                         (date(2026, 10, 5), date(2026, 10, 11)))
        self.assertEqual(cr.period_for("last_week", date(2026, 10, 12)),
                         (date(2026, 10, 5), date(2026, 10, 11)))
        self.assertEqual(cr.period_for("last_month", date(2026, 3, 1)),
                         (date(2026, 2, 1), date(2026, 2, 28)))
        self.assertEqual(cr.period_for("month_to_date", date(2026, 10, 18)),
                         (date(2026, 10, 1), date(2026, 10, 17)))
        self.assertEqual(cr.period_for("month_to_date", date(2026, 10, 1)),
                         (date(2026, 9, 1), date(2026, 9, 30)))

    def test_due_once_then_one_retry_then_never_before_it_was_made(self):
        s = spec(schedule={"kind": "weekly", "weekday": 0, "at": "08:00"})
        at = datetime(2026, 10, 12, 6, 5, tzinfo=UTC)
        self.assertEqual(cr.due(s, [], at, BERLIN, "2026-10-01T00:00:00Z"), date(2026, 10, 12))
        # Made after this week's time had passed: this week's is not sent late.
        self.assertIsNone(cr.due(s, [], at, BERLIN, "2026-10-12T06:01:00Z"))
        first_try = {"occurrence": "2026-10-12", "by": "schedule", "ok": False,
                     "at": "2026-10-12T06:05:00Z"}
        self.assertIsNone(cr.due(s, [first_try], at + timedelta(minutes=10), BERLIN))
        self.assertEqual(cr.due(s, [first_try], at + timedelta(minutes=31), BERLIN),
                         date(2026, 10, 12))
        again = {**first_try, "at": "2026-10-12T06:36:00Z"}
        self.assertIsNone(cr.due(s, [first_try, again], at + timedelta(hours=2), BERLIN))
        self.assertIsNone(cr.due(s, [{**first_try, "ok": True}], at + timedelta(hours=2), BERLIN))
        # A hand send does not count against the schedule; a paused report never goes.
        by_hand = {**first_try, "by": "owner@example.com", "ok": True}
        self.assertEqual(cr.due(s, [by_hand], at, BERLIN), date(2026, 10, 12))
        self.assertIsNone(cr.due({**s, "paused": True}, [], at, BERLIN))
        # Days later it is not caught up.
        self.assertIsNone(cr.due(s, [], at + timedelta(days=3), BERLIN))

    def test_validation(self):
        for bad in ({"recipients": []}, {"recipients": ["not an address"]},
                    {"schedule": {"kind": "yearly"}}, {"schedule": {"kind": "monthly", "day": 40}},
                    {"schedule": {"kind": "weekly", "weekday": 0, "at": "25:00"}},
                    {"period": "forever"}, {"sections": []}, {"name": ""},
                    {"notes": "x" * 2001}):
            with self.assertRaises(cr.Invalid, msg=bad):
                spec(**bad)
        got = spec(recipients="a@example.com, A@example.com\nb@example.com",
                   sections=["notes", "summary", "nonsense"])
        self.assertEqual(got["recipients"], ["a@example.com", "b@example.com"])
        self.assertEqual(got["sections"], ["summary", "notes"])


# ------------------------------------------------------------- the PDF

def _png_rgba(w: int, h: int) -> bytes:
    raw = b"".join(b"\0" + bytes(v for x in range(w) for v in (x * 9 % 256, y * 7 % 256, 120,
                                                              255 if x > 2 else 0))
                   for y in range(h))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(
            ">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def parse_pdf(test: unittest.TestCase, blob: bytes) -> dict[int, bytes]:
    """Read it back the way a reader does: startxref, the table, every object."""
    test.assertTrue(blob.startswith(b"%PDF-1.4\n"))
    test.assertTrue(blob.rstrip().endswith(b"%%EOF"))
    start = int(re.search(rb"startxref\n(\d+)\n%%EOF", blob).group(1))
    test.assertEqual(blob[start:start + 4], b"xref")
    head = re.match(rb"xref\n0 (\d+)\n", blob[start:])
    count = int(head.group(1))
    rows = blob[start + head.end():].split(b"\n")[:count]
    test.assertEqual(rows[0], b"0000000000 65535 f ")
    objects = {}
    for n, row in enumerate(rows[1:], start=1):
        offset = int(row[:10])
        test.assertEqual(blob[offset:offset + len(f"{n} 0 obj".encode())], f"{n} 0 obj".encode())
        end = blob.index(b"endobj", offset)
        objects[n] = blob[offset:end]
    trailer = blob[blob.index(b"trailer", start):]
    test.assertIn(f"/Size {count}".encode(), trailer)
    root = int(re.search(rb"/Root (\d+) 0 R", trailer).group(1))
    test.assertIn(b"/Type /Catalog", objects[root])
    for body in objects.values():      # every stream's /Length is its true length
        m = re.search(rb"/Length (\d+) >>\nstream\n", body)
        if m:
            data = body[m.end():m.end() + int(m.group(1))]
            test.assertTrue(body[m.end() + int(m.group(1)):].startswith(b"\nendstream"))
            if b"/FlateDecode" in body[:m.start()] and b"/Subtype /Image" not in body:
                zlib.decompress(data)
    return objects


def text_of(objects: dict[int, bytes]) -> str:
    out = []
    for body in objects.values():
        m = re.search(rb"/Length (\d+) >>\nstream\n", body)
        if m and b"/Subtype" not in body:
            ops = zlib.decompress(body[m.end():m.end() + int(m.group(1))]).decode("ascii")
            out += re.findall(r"\((.*?)\) Tj", ops)
    return " ".join(out)


class Pdf(unittest.TestCase):
    def test_a_document_parses_and_carries_its_text_and_images(self):
        doc = pw.Document(title="Report (draft) \\ café")
        page = doc.add_page()
        page.text(40, 60, "Visitors (all) 1,234 – café", 12, bold=True)
        page.rect(40, 80, 100, 50, fill="#2a78d6", radius=4, top_only=True)
        page.line(40, 140, 300, 140, "#d8dfe6")
        img = doc.image(_png_rgba(6, 4))
        self.assertIsNotNone(img)
        page.image(img, 40, 160, 60, 40)
        self.assertIsNone(doc.image(b"<svg xmlns='http://www.w3.org/2000/svg'/>"))
        doc.add_page().text(40, 60, "Second page")
        blob = doc.to_bytes(datetime(2026, 10, 18, tzinfo=UTC))
        self.assertEqual(blob, doc.to_bytes(datetime(2026, 10, 18, tzinfo=UTC)))
        objects = parse_pdf(self, blob)
        pages = [b for b in objects.values() if b"/Type /Pages" in b]
        self.assertIn(b"/Count 2", pages[0])
        self.assertTrue(any(b"/SMask" in b for b in objects.values()))   # the alpha kept
        words = text_of(objects)
        self.assertIn(r"Visitors \(all\) 1,234 \226 caf\351", words)  # WinAnsi, escaped
        self.assertIn("Second page", words)

    def test_measure_fit_wrap(self):
        self.assertAlmostEqual(pw.text_width("Hello", 10), 22.78, places=2)
        self.assertGreater(pw.text_width("Hello", 10, bold=True), pw.text_width("Hello", 10))
        cut = pw.fit("/a/very/long/page/path/that/goes/on/and/on", 9, 80)
        self.assertTrue(cut.endswith("...") and pw.text_width(cut, 9) <= 80)
        lines = pw.wrap("one two three four five six seven eight nine ten", 10, 60)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(pw.text_width(line, 10) <= 60 for line in lines))
        self.assertEqual(pw.encode("→ ünïcode ✓"), b"? \xfcn\xefcode ?")

    def test_png_kinds(self):
        w, h, rgb, alpha = pw.decode_png(_png_rgba(5, 3))
        self.assertEqual((w, h, len(rgb), len(alpha)), (5, 3, 45, 15))
        with self.assertRaises(pw.ImageError):
            pw.decode_png(b"GIF89a")
        ico = (b"\0\0\1\0\1\0" + bytes((5, 3, 0, 0, 1, 0, 32, 0)) +
               struct.pack("<II", len(_png_rgba(5, 3)), 22) + _png_rgba(5, 3))
        self.assertEqual(pw.png_in_ico(ico), _png_rgba(5, 3))


# ------------------------------------------------- figures: withheld, audit

class Figures(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)

    def build(self, s=None, first=date(2026, 9, 1), last=date(2026, 9, 30)):
        with History(self.box.db) as history:
            return data_mod.build({}, history, "example.com", s or spec(), first, last, UTC)

    def test_withheld_and_missing_days_are_listed_drawn_as_gaps_and_never_counted(self):
        fill(self.box.db, "example.com", date(2026, 8, 1), date(2026, 9, 30),
             withheld={date(2026, 9, 12)}, skip={date(2026, 9, 20)})
        got = self.build()
        self.assertEqual(got["coverage"]["withheld"], ["2026-09-12"])
        self.assertEqual(got["coverage"]["missing"], ["2026-09-20"])
        self.assertEqual(got["coverage"]["recorded"], 28)
        bars = {b["day"]: b["visitors"] for b in got["daily"]}
        self.assertIsNone(bars["2026-09-12"])
        self.assertIsNone(bars["2026-09-20"])
        with History(self.box.db) as history:
            whole = [e for e in history.daily("example.com", date(2026, 9, 1), date(2026, 9, 30))
                     if e["state"] == "ok"]
        self.assertEqual(got["headline"]["visitors"],
                         sum(e["groups"][next(iter(e["groups"]))]["readers"] for e in whole))
        self.assertIsNone(got["changes"]["visitors"])          # not whole: no change stated
        lines = data_mod.coverage_lines(got)
        self.assertIn("Withheld, not counted (the figures did not reconcile): 12 Sep.", lines)
        self.assertIn("Not recorded: 20 Sep.", lines)
        # The same in the PDF and the mail.
        brand = {"agency_name": "Example Agency", "color": "#0f766e", "letter": "E"}
        words = text_of(parse_pdf(self, client_report_pdf.render(got, brand)))
        self.assertIn("Withheld, not counted", words)
        from skald.client_report_html import render
        self.assertIn("Withheld, not counted", render(got, brand, ["client@example.com"]))

    def test_a_whole_period_is_compared_with_the_one_before(self):
        fill(self.box.db, "example.com", date(2026, 8, 1), date(2026, 9, 30))
        got = self.build()
        self.assertTrue(got["compared"])
        self.assertIsNotNone(got["changes"]["visitors"])

    def test_nothing_verified_is_refused_not_zero(self):
        fill(self.box.db, "example.com", date(2026, 9, 1), date(2026, 9, 3),
             withheld={date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)})
        with self.assertRaises(data_mod.Refused):
            self.build(first=date(2026, 9, 1), last=date(2026, 9, 3))

    def test_the_second_count_catches_a_wrong_sum_or_bar(self):
        fill(self.box.db, "example.com", date(2026, 9, 1), date(2026, 9, 30),
             withheld={date(2026, 9, 5)})
        got = self.build()
        first, last = date(2026, 9, 1), date(2026, 9, 30)
        self.assertEqual(audit_client_reports.recount(self.box.db, "example.com", first, last,
                                                      got), [])
        wrong = json.loads(json.dumps(got))
        wrong["headline"]["visitors"] += 1
        wrong["daily"][4]["visitors"] = 3                       # the withheld day, as a figure
        wrong["coverage"]["withheld"] = []
        found = audit_client_reports.recount(self.box.db, "example.com", first, last, wrong)
        self.assertEqual(len(found), 3, found)
        with mock.patch.object(audit_client_reports, "recount", return_value=["visitors 1 against 2"]):
            with self.assertRaises(data_mod.Refused):
                self.build()

    def test_only_the_reports_own_site_is_read(self):
        fill(self.box.db, "example.com", date(2026, 9, 1), date(2026, 9, 30), people=3)
        alone = self.build()["headline"]
        fill(self.box.db, "other.example.com", date(2026, 9, 1), date(2026, 9, 30), people=9)
        self.assertEqual(self.build()["headline"], alone)

    def test_search_console_uses_the_synced_final_days_and_marks_the_provisional(self):
        from skald.search import days as sd
        fill(self.box.db, "example.com", date(2026, 9, 1), date(2026, 9, 30))
        s = spec(sections=["summary", "search_console"])
        # Not connected: said so, nothing counted.
        got = self.build(s)
        self.assertEqual(got["search_console"], {"connected": None})
        self.assertIn("not connected", data_mod.search_console_lines(got["search_console"])[0])

        def day(n, clicks, shown):
            t = {"clicks": clicks, "impressions": shown, "position": 5.0}
            return {"total": sd.fold([["(all)", clicks, shown, 5.0]], t, 1),
                    "query": sd.fold([["skald analytics", clicks - 1, shown // 2, 3.0],
                                      ["server logs", 1, shown // 2, 8.0]], t, sd.TOP["query"]),
                    "page": sd.fold([["https://example.com/", clicks, shown, 5.0]], t,
                                    sd.TOP["page"])}
        stored = {date(2026, 9, d): day(d, 10 + d, 100 * d) for d in range(1, 29)}
        finals = {d: d.day <= 26 for d in stored}            # 27, 28 provisional; 29, 30 not synced
        with History(self.box.db) as history:
            sd.write(history.db, "example.com", "google", stored, finals, "sc-domain:example.com")
            sd.write(history.db, "other.example.com", "google", {date(2026, 9, 1): day(1, 999, 9)},
                     {date(2026, 9, 1): True}, "sc-domain:other.example.com")
        config = {"search_console": {"property": "sc-domain:example.com"}}
        with History(self.box.db) as history:
            got = data_mod.build(config, history, "example.com", s, date(2026, 9, 1),
                                 date(2026, 9, 30), UTC)
        sc = got["search_console"]
        self.assertEqual(sc["connected"], "sc-domain:example.com")
        self.assertEqual(len(sc["final"]), 26)
        self.assertEqual(sc["provisional"], ["2026-09-27", "2026-09-28"])
        self.assertEqual(sc["missing"], ["2026-09-29", "2026-09-30"])
        self.assertEqual(sc["totals"]["clicks"], sum(10 + d for d in range(1, 27)))
        self.assertEqual(sc["totals"]["impressions"], sum(100 * d for d in range(1, 27)))
        self.assertEqual(sc["totals"]["position"], 5.0)
        self.assertEqual(sc["queries"][0]["name"], "skald analytics")
        self.assertEqual(sc["queries"][0]["clicks"], sum(9 + d for d in range(1, 27)))
        self.assertEqual(sc["pages"][0]["clicks"], sc["totals"]["clicks"])
        # The second road agrees, and catches a wrong sum or a provisional day counted.
        first, last = date(2026, 9, 1), date(2026, 9, 30)
        self.assertEqual(audit_client_reports.recount(self.box.db, "example.com", first, last,
                                                      got), [])
        wrong = json.loads(json.dumps(got))
        wrong["search_console"]["totals"]["clicks"] += 1
        wrong["search_console"]["final"].append("2026-09-27")
        wrong["search_console"]["provisional"] = ["2026-09-28"]
        found = audit_client_reports.recount(self.box.db, "example.com", first, last, wrong)
        self.assertEqual(len(found), 3, found)
        # Drawn the same in the mail, its text and the PDF.
        lines = data_mod.search_console_lines(sc)
        self.assertIn(f"{sc['totals']['clicks']:,} clicks", lines[0])
        self.assertIn("Provisional, not counted (Google may still change them): 27 Sep, 28 Sep.",
                      lines)
        self.assertIn("Not in Search Console yet: 29 Sep, 30 Sep.", lines)
        from skald.client_report_html import as_text, render
        brand = {"agency_name": "Example Agency", "color": "#0f766e", "letter": "E"}
        html = render(got, brand, ["client@example.com"])
        self.assertIn("skald analytics", html)
        self.assertIn("Provisional, not counted", html)
        self.assertIn("SEARCH CONSOLE", as_text(got, brand))
        words = text_of(parse_pdf(self, client_report_pdf.render(got, brand)))
        self.assertIn("Provisional, not counted", words)


class LeadsAndWords(unittest.TestCase):
    """2.13: one "Leads" everywhere (the dashboard tile's: finished lead actions from the
    conversions file, test rows left out), counted twice; places and assistants in the app's
    words (alpha-3 with the flag kept apart, "Direct", "ChatGPT")."""

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        fill(self.box.db, "example.com", date(2026, 8, 1), date(2026, 9, 30))
        from skald.conversions import store
        self.conv = Path(self.box.db).parent / store.FILE
        db = store.connect(self.conv)
        rows = [("signup", "completed", "2026-09-02T10:00:00Z", 0), ("contact", "completed", "2026-09-03T10:00:00Z", 0),
                ("demo", "completed", "2026-09-04T10:00:00Z", 0), ("demo", "cancelled", "2026-09-05T10:00:00Z", 0),
                ("signup", "started", "2026-09-06T10:00:00Z", 0), ("signup", "completed", "2026-09-07T10:00:00Z", 1),
                ("paid", "paid", "2026-09-08T10:00:00Z", 0), ("signup", "completed", "2026-08-20T10:00:00Z", 0),
                ("contact", "completed", "2026-09-09T10:00:00Z", 0)]
        for i, (action, stage, at, test) in enumerate(rows):
            store.record_conversion(db, {"site": "example.com", "action": action, "stage": stage, "at": at,
                                         "external_ref": f"r{i}", "tool": "lead" if test else "calendly"})
            if test:
                db.execute("UPDATE conversions SET test = 1 WHERE external_ref = ?", (f"r{i}",))
                db.commit()
        store.record_conversion(db, {"site": "other.example.com", "action": "signup", "stage": "completed",
                                     "at": "2026-09-02T11:00:00Z", "external_ref": "x", "tool": "lead"})
        db.close()

    def test_the_report_and_the_mail_count_the_dashboards_leads_twice(self):
        from skald import conversions_leads, mail_html
        with History(self.box.db) as history:
            got = data_mod.build({}, history, "example.com", spec(), date(2026, 9, 1), date(2026, 9, 30), UTC)
            mail = mail_html._leads({}, history, "example.com", UTC, date(2026, 9, 1), date(2026, 9, 30))
            before = conversions_leads.period_leads({}, history, "example.com", UTC, date(2026, 8, 1), date(2026, 8, 31))
        # signup, contact x2, demo completed: not the cancelled demo, the start, the test row,
        # the payment (not a lead action), August's or another site's.
        self.assertEqual(got["headline"]["leads"], 4)
        self.assertEqual(got["leads"]["by_action"], {"signup": 1, "contact": 2, "demo": 1})
        self.assertEqual([r["name"] for r in got["leads"]["rows"]], ["Contact forms", "Demos booked", "Sign-ups"])
        self.assertEqual(mail, 4)
        self.assertEqual(audit_client_reports.recount_leads(self.conv, "example.com", UTC, date(2026, 9, 1),
                                                            date(2026, 9, 30)), {"signup": 1, "contact": 2, "demo": 1})
        # The second count catches a wrong sum; the mail then shows no figure.
        wrong = {**got["leads"], "total": 5}
        self.assertTrue(audit_client_reports.check_leads(self.conv, "example.com", UTC, date(2026, 9, 1),
                                                         date(2026, 9, 30), wrong))
        with mock.patch.object(audit_client_reports, "check_leads", return_value=["leads 5 against 4"]):
            with History(self.box.db) as history:
                self.assertIsNone(mail_html._leads({}, history, "example.com", UTC, date(2026, 9, 1), date(2026, 9, 30)))
                with self.assertRaises(data_mod.Refused):
                    data_mod.build({}, history, "example.com", spec(), date(2026, 9, 1), date(2026, 9, 30), UTC)
        # A period that starts before conversions were recorded: no partial sum, said so.
        self.assertEqual(before, {"state": "not_recorded", "since": "2026-08-20"})
        self.assertIn("recorded from 20 Aug 2026", data_mod.leads_missing(before))
        from skald.client_report_html import render
        brand = {"agency_name": "Example Agency", "color": "#0f766e", "letter": "E"}
        html = render(got, brand, ["client@example.com"])
        self.assertIn("as on the dashboard", html)
        self.assertNotIn("lead database, every day", html)
        self.assertIn("as on the dashboard", text_of(parse_pdf(self, client_report_pdf.render(got, brand))))
        # No conversions file: not recorded, never 0.
        self.conv.unlink()
        with History(self.box.db) as history:
            self.assertIsNone(data_mod.build({}, history, "example.com", spec(), date(2026, 9, 1),
                                             date(2026, 9, 30), UTC)["headline"]["leads"])

    def test_places_sources_and_assistants_in_the_apps_words(self):
        self.assertEqual(data_mod._country("US"), "USA")
        self.assertEqual(data_mod._country_more("US"), {"flag": "\U0001F1FA\U0001F1F8", "title": "United States"})
        self.assertEqual(data_mod._country("Unknown"), "Not recorded")
        self.assertEqual(data_mod._city("London, England, GB"), "London, England, GBR")
        self.assertEqual(data_mod._city_more("London, England, GB")["title"], "London, England, United Kingdom")
        self.assertEqual(data_mod._city("Unknown"), "Not recorded")
        got = {"site": "example.com", "name": "R", "first": "2026-09-01", "last": "2026-09-30", "days": 30,
               "timezone": "UTC", "coverage": {"recorded": 30, "withheld": [], "partial": [], "missing": []},
               "sections": ["sources", "places", "ai"], "headline": {}, "changes": {}, "compared": False,
               "daily": [], "breakdowns": True,
               "sources": data_mod._ranked({"Direct or unknown": 5, "Search engine": 3}, 8, data_mod.shown),
               "pages": [], "countries": data_mod._ranked({"US": 5, "GB": 3}, 8, data_mod._country,
                                                          more=data_mod._country_more),
               "cities": data_mod._ranked({"London, England, GB": 3}, 8, data_mod._city, more=data_mod._city_more),
               "ai": {"asked": 1, "training": 0, "search": 0, "bots": 0, "crawlers": [],
                      "cited_by": data_mod._ranked({"chatgpt.com": 2}, 2, data_mod.assistant_label)},
               "leads": None, "notes": "", "footer": "", "search_console": None}
        from skald.client_report_html import as_text, render
        brand = {"agency_name": "Example Agency", "color": "#0f766e", "letter": "E"}
        html = render(got, brand, ["client@example.com"])
        for word in ("Direct", "\U0001F1FA\U0001F1F8 USA", 'title="United States"', "London, England, GBR", "ChatGPT"):
            self.assertIn(word, html)
        visible = re.sub(r"<[^>]+>", " ", html)
        for word in ("Direct or unknown", "United States", "chatgpt.com"):
            self.assertNotIn(word, visible)
        words = text_of(parse_pdf(self, client_report_pdf.render(got, brand)))
        self.assertIn("USA", words)
        self.assertNotIn("?", words)                     # no flag drawn as "?" by WinAnsi
        self.assertIn("ChatGPT", as_text(got, brand) + html)


# -------------------------------------------- the API, the mail, the clock

class Api(Server):
    def setUp(self):
        super().setUp()
        self.config["report"] = {"timezone": "UTC"}
        self.mail_on()
        self.history = self.live / "history.sqlite"
        today = datetime.now(UTC).date()
        fill(self.history, A, today - timedelta(days=70), today - timedelta(days=1))
        fill(self.history, B, today - timedelta(days=70), today - timedelta(days=1), people=9)
        self.mailed = []
        patch = mock.patch.object(mailer, "send", side_effect=lambda msg, cfg: self.mailed.append(msg))
        patch.start()
        self.addCleanup(patch.stop)

    def body(self, **over):
        raw = {"name": "Monthly traffic report", "recipients": ["client@example.com", "boss@example.com"],
               "schedule": {"kind": "monthly", "day": 1, "at": "08:00"}, "period": "last_month",
               "sections": list(cr.SECTIONS), "notes": "Hello.", "footer": "Example Agency"}
        raw.update(over)
        return raw

    def make(self, cookie, csrf, **over):
        got = self.post(T + "settings/report-save", self.body(**over), cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        return got.json["report"]

    def test_save_asks_each_recipient_to_confirm_and_send_goes_to_confirmed_only(self):
        cookie, csrf = self.session("admin@example.com")
        got = self.post(T + "settings/report-save", self.body(), cookie, csrf)
        self.assertEqual((got.status, got.json["confirm"]), (200, "asked"), got.json)
        rep = got.json["report"]
        self.assertEqual(rep["waiting"], ["client@example.com", "boss@example.com"])
        from skald import auth_api
        auth_api.drain()
        self.assertEqual(sorted(to for to, _ in self.sent), ["boss@example.com", "client@example.com"])
        # Nobody confirmed: nothing goes, and the try is recorded.
        got = self.post(T + "settings/report-send", {"id": rep["id"]}, cookie, csrf)
        self.assertEqual(got.status, 400, got.json)
        self.assertIn("no recipient has confirmed", got.json["error"])
        self.assertEqual(self.mailed, [])
        db = self.db()
        try:
            mail_confirm.mark_confirmed(db, self.alpha["id"], "client@example.com")
        finally:
            db.close()
        got = self.post(T + "settings/report-send", {"id": rep["id"]}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        msg = self.mailed[-1]
        self.assertEqual(msg["To"], "client@example.com")
        self.assertNotIn("[Skald]", msg["Subject"])
        pdf = [p for p in msg.iter_attachments() if p.get_content_type() == "application/pdf"]
        self.assertEqual(len(pdf), 1)
        parse_pdf(self, pdf[0].get_content())
        self.assertIn("1 not confirmed yet", got.json["words"])
        log = self.call("GET", T + f"settings/report-log?id={rep['id']}", cookie=cookie).json
        self.assertEqual([s["ok"] for s in log["sends"]], [True, False])
        self.assertEqual(log["sends"][0]["by"], "admin@example.com")
        self.assertEqual(log["sends"][0]["recipients"], ["client@example.com"])
        self.assertTrue(log["sends"][0]["first"].endswith("-01"))

    def test_save_without_mail_says_no_confirm_link_went(self):
        """No mail server: the save says no link was sent ("no_mail"), sends nothing, and
        uses up no recipient's one link a day, so a save after mail is set up mails them."""
        self.config.pop("mail", None)
        cookie, csrf = self.session("admin@example.com")
        got = self.post(T + "settings/report-save", self.body(), cookie, csrf)
        self.assertEqual((got.status, got.json["confirm"]), (200, "no_mail"), got.json)
        from skald import auth_api
        auth_api.drain()
        self.assertEqual(self.sent, [])
        self.mail_on()
        got = self.post(T + "settings/report-save", {**self.body(), "id": got.json["report"]["id"]}, cookie, csrf)
        self.assertEqual(got.json["confirm"], "asked", got.json)
        auth_api.drain()
        self.assertEqual(sorted(to for to, _ in self.sent), ["boss@example.com", "client@example.com"])
        # Everyone confirmed: nobody waits, nothing to say about links.
        db = self.db()
        try:
            for to in ("client@example.com", "boss@example.com"):
                mail_confirm.mark_confirmed(db, self.alpha["id"], to)
        finally:
            db.close()
        got = self.post(T + "settings/report-save", {**self.body(), "id": got.json["report"]["id"]}, cookie, csrf)
        self.assertEqual(got.json["confirm"], "none", got.json)

    def test_preview_and_pdf_send_nothing(self):
        cookie, csrf = self.session("owner@example.com")
        got = self.post(T + "settings/report-preview", self.body(recipients=[]), cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertNotIn("cid:", got.json["html"])
        self.assertIn("Monthly traffic report", got.json["subject"])
        rep = self.make(cookie, csrf)
        got = self.post(T + "settings/report-pdf", {"id": rep["id"]}, cookie, csrf)
        self.assertEqual(got.status, 200)
        self.assertEqual(got.header("Content-Type"), "application/pdf")
        parse_pdf(self, got.raw)
        self.assertEqual(self.mailed, [])

    def test_another_organisation_sees_nothing_of_it(self):
        cookie, csrf = self.session("admin@example.com")
        rep = self.make(cookie, csrf)
        bob, bob_csrf = self.session("bob@example.com")
        self.assertEqual(self.call("GET", T + "settings/reports", cookie=bob).status, 403)
        self.assertEqual(self.post(T + "settings/report-send", {"id": rep["id"]}, bob, bob_csrf).status, 403)
        other = f"/traffic/{B}/"
        listed = self.call("GET", other + "settings/reports", cookie=bob)
        self.assertEqual(listed.status, 200)
        self.assertEqual(listed.json["reports"], [])
        for act in ("report-preview", "report-pdf", "report-send", "report-delete"):
            got = self.post(other + f"settings/{act}", {"id": rep["id"]}, bob, bob_csrf)
            self.assertEqual(got.status, 404, (act, got.json))
        self.assertEqual(self.call("GET", other + f"settings/report-log?id={rep['id']}",
                                   cookie=bob).status, 404)
        viewer, _ = self.session("viewer@example.com")
        self.assertEqual(self.call("GET", T + "settings/reports", cookie=viewer).status, 403)

    def test_agency_branding_logo_and_colour(self):
        cookie, csrf = self.session("admin@example.com")
        import base64
        png = _png_rgba(32, 16)
        got = self.post(T + "settings/agency-logo", {"data": base64.b64encode(png).decode()}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertTrue(got.json["branding"]["logo"])
        self.assertEqual(self.call("GET", T + "settings/agency-logo", cookie=cookie).raw, png)
        bad = self.post(T + "settings/agency-logo", {"data": base64.b64encode(b"<svg/>").decode()}, cookie, csrf)
        self.assertEqual(bad.status, 400)
        got = self.post(T + "settings/save", {"brand.agency_name": "Example Agency", "brand.color": "#0F766E"}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        got = self.post(T + "settings/save", {"brand.color": "teal"}, cookie, csrf)
        self.assertEqual(got.status, 400)
        listed = self.call("GET", T + "settings/reports", cookie=cookie).json
        self.assertEqual(listed["branding"], {"agency_name": "Example Agency", "color": "#0f766e", "logo": True})
        preview = self.post(T + "settings/report-preview", self.body(), cookie, csrf).json
        self.assertIn("data:image/png;base64,", preview["html"])
        self.assertIn("#0f766e", preview["html"])
        # Beta's organisation has no logo of its own.
        bob, _ = self.session("bob@example.com")
        self.assertEqual(self.call("GET", f"/traffic/{B}/settings/agency-logo", cookie=bob).status, 404)
        got = self.post(T + "settings/agency-logo", {"data": None}, cookie, csrf)
        self.assertFalse(got.json["branding"]["logo"])

    def test_the_clock_sends_once_retries_once_and_waits_for_the_day(self):
        db = self.db()
        try:
            rep = cr.save(db, self.alpha["id"], A, spec(schedule={"kind": "weekly", "weekday": 0,
                                                                  "at": "08:00"},
                                                        period="last_week"), "cli")
            db.execute("UPDATE client_reports SET created_at = '2020-01-01T00:00:00Z'")
            mail_confirm.mark_confirmed(db, self.alpha["id"], "client@example.com")
            today = datetime.now(UTC).date()
            monday = today - timedelta(days=today.weekday())
            at = datetime.combine(monday, datetime.min.time(), UTC) + timedelta(hours=8, minutes=1)
            run = lambda when: rs.run_due(self.config, self.history, db, A, self.live, when,
                                          out=lambda *_: None)
            with mock.patch.object(mailer, "send", side_effect=smtplib.SMTPException("down")):
                self.assertEqual(run(at), 1)
                self.assertEqual(run(at + timedelta(minutes=5)), 0)      # waits 30 minutes
                self.assertEqual(run(at + timedelta(minutes=31)), 1)     # the one retry
                self.assertEqual(run(at + timedelta(hours=2)), 0)        # then no more
            tries = cr.sends(db, self.alpha["id"], rep["id"])
            self.assertEqual([t["ok"] for t in tries], [False, False])
            self.assertIn("did not take it", tries[0]["detail"])
            self.assertEqual(tries[0]["occurrence"], monday.isoformat())
            # Next week: the period's last day (Sunday) not stored yet, before 18:00: it waits.
            nxt = at + timedelta(days=7)
            with History(self.history) as history:
                history.db.execute("DELETE FROM days WHERE site = ? AND day = ?",
                                   (A, (monday + timedelta(days=6)).isoformat()))
                history.db.commit()
            with mock.patch.object(cr, "should_wait", return_value=True):
                self.assertEqual(run(nxt), 0)
            self.assertEqual(len(cr.sends(db, self.alpha["id"], rep["id"])), 2)
        finally:
            db.close()

    def test_delete_takes_its_history(self):
        cookie, csrf = self.session("admin@example.com")
        rep = self.make(cookie, csrf)
        self.assertEqual(self.post(T + "settings/report-delete", {"id": rep["id"]}, cookie, csrf).status, 200)
        self.assertEqual(self.call("GET", T + "settings/reports", cookie=cookie).json["reports"], [])


class BasicMode(Server):
    MODE = "basic"

    def test_404_without_accounts(self):
        from auth_support import SAME
        self.assertEqual(self.call("GET", T + "settings/reports", None, SAME).status, 404)


if __name__ == "__main__":
    unittest.main()

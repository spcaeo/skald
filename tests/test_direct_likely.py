"""Direct, likely <reason> (direct_likely.py) and its second count
(audit_direct_likely.py).

What is pinned:
- each reason on a synthetic day: a Stripe, PayPal or checkout-end landing is
  a checkout return; an Instagram or Facebook in-app browser is in-app; a
  share marker (igshid=, ref=whatsapp, via=copy-link) or a link preview of
  the page in the window before is a shared link;
- the order: checkout before in-app before shared, one reason a visit;
- what stays plain Direct: a bare /thank-you, ref=producthunt, a session_id
  that is not Stripe's, a preview too long before or after the visit; and
  what is not Direct at all (a referrer, a utm_source) is never split;
- every sum the blob promises is checked, and a planted error is caught;
- the switch and the window are honoured;
- the audit rebuilds the figure from the raw lines, a tampered figure fails
  it (the live audit too), and the stored window is the one recounted;
- the two roads' rules agree on a list of addresses, written apart;
- campaigns.json carries each day's blob and the method; visits.json each
  likely visit's reason;
- the recount shares only direct_names.py's lists.
Addresses are RFC 5737, hosts example.com.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import Sandbox, line, totals_for  # noqa: E402

from skald import (audit_direct_likely, audit_more, dashboard_webapp, day_more,  # noqa: E402
                          direct_likely, direct_names, extras, store_extras)
from skald.store import History  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
IG = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, "
      "like Gecko) Mobile/15E148 Instagram 300.0.0.0 (iPhone14,2; iOS 17_0; en_US)")
FB = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, "
      "like Gecko) Mobile/15E148 [FBAN/FBIOS;FBAV/440.0.0.0]")
WHATSAPP = "WhatsApp/2.23.20.0 A"
SLACK = "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)"
DISCORD = "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)"


def at(hour: int, minute: int, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def synthetic(day: date = DAY) -> list[str]:
    return [
        line(at(9, 0, day), "203.0.113.20", "/thank-you?session_id=cs_test_a1"),   # Stripe
        line(at(9, 5, day), "203.0.113.21", "/checkout/order-received/123/"),      # return page
        line(at(9, 10, day), "203.0.113.22", "/success?PayerID=ABC&token=EC-1", IG),  # PayPal first
        line(at(9, 15, day), "203.0.113.23", "/", IG),                             # in-app
        line(at(9, 20, day), "203.0.113.24", "/blog/post?igshid=abc"),             # share marker
        line(at(9, 25, day), "203.0.113.25", "/blog/post?ref=whatsapp", FB),       # in-app first
        line(at(10, 0, day), "198.51.100.60", "/guides/alpha", WHATSAPP),          # a preview
        line(at(10, 12, day), "203.0.113.26", "/guides/alpha/"),                   # shared, 12 min
        line(at(10, 50, day), "203.0.113.27", "/guides/alpha"),                    # too late
        line(at(11, 0, day), "198.51.100.61", "/docs", SLACK),
        line(at(11, 1, day), "198.51.100.62", "/docs", WHATSAPP),
        line(at(11, 5, day), "203.0.113.28", "/docs"),                             # two apps
        line(at(11, 30, day), "203.0.113.29", "/thank-you"),                       # bare: plain
        line(at(11, 35, day), "203.0.113.30", "/pricing?ref=producthunt"),         # plain
        line(at(11, 40, day), "203.0.113.31", "/success?session_id=abc"),          # not cs_: plain
        line(at(11, 45, day), "203.0.113.32", "/x", referrer="https://www.google.com/"),
        line(at(11, 50, day), "203.0.113.33",
             "/thank-you?session_id=cs_live_x&utm_source=stripe"),                 # tagged
        line(at(12, 0, day), "203.0.113.34", "/", IG, referrer="https://l.instagram.com/"),
        line(at(12, 4, day), "203.0.113.35", "/later"),                            # before it
        line(at(12, 5, day), "198.51.100.63", "/later", DISCORD),
        line(at(12, 10, day), "203.0.113.36", "/orders/abc/thank_you.html"),       # return page
        line(at(12, 15, day), "203.0.113.37", "/?via=copy-link"),                  # share tag
    ]


WANT = {"share_window_minutes": 30, "visits": 18, "direct": 15, "likely": 10, "plain": 5,
        "reasons": {"checkout": 4, "in_app": 2, "shared": 4},
        "details": {"checkout": {"(return page)": 2, "PayPal": 1, "Stripe": 1},
                    "in_app": {"Facebook app": 1, "Instagram app": 1},
                    "shared": {"(more than one)": 1, "(share tag)": 1, "Instagram": 1,
                               "WhatsApp": 1}}}


def tally(lines, conf):
    from skald import Classifier, read
    from skald.aggregate import summarise_views
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "access.log"
        path.write_text("".join(lines))
        return summarise_views(read([path]), Classifier(["MyCompanyCrawler"]), 30, top=50,
                               hosts=["example.com"], options={"direct_likely": conf})[0]


class TestTheDay(unittest.TestCase):

    def test_the_synthetic_day(self):
        totals = totals_for(synthetic())
        self.assertEqual(totals.extras["direct_likely"], WANT)
        self.assertEqual(extras.check(totals), [])
        marked = {j["start"][11:16]: j.get("likely_direct") for j in totals.journeys}
        self.assertEqual(marked["09:00"], {"reason": "checkout", "detail": "Stripe"})
        self.assertEqual(marked["09:05"], {"reason": "checkout", "detail": "(return page)"})
        self.assertEqual(marked["09:15"], {"reason": "in_app", "detail": "Instagram app"})
        self.assertEqual(marked["09:20"], {"reason": "shared", "detail": "Instagram"})
        self.assertEqual(marked["10:12"], {"reason": "shared", "detail": "WhatsApp", "minutes": 12})
        self.assertEqual(marked["11:05"], {"reason": "shared", "detail": "(more than one)",
                                           "minutes": 4})
        self.assertEqual(marked["12:10"], {"reason": "checkout", "detail": "(return page)"})
        self.assertEqual(marked["12:15"], {"reason": "shared", "detail": "(share tag)"})

    def test_one_reason_a_visit_checkout_then_in_app_then_shared(self):
        marked = {j["start"][11:16]: j.get("likely_direct") for j in totals_for(synthetic()).journeys}
        # A PayPal return opened in Instagram's browser: the return wins.
        self.assertEqual(marked["09:10"], {"reason": "checkout", "detail": "PayPal"})
        # A ref=whatsapp link opened in Facebook's browser: the in-app browser wins.
        self.assertEqual(marked["09:25"], {"reason": "in_app", "detail": "Facebook app"})
        # A share marker before a preview of the same page.
        lines = [line(at(10, 0), "198.51.100.60", "/a", WHATSAPP),
                 line(at(10, 1), "203.0.113.20", "/a?ref=share")]
        got = totals_for(lines).journeys[0]["likely_direct"]
        self.assertEqual(got, {"reason": "shared", "detail": "(share tag)"})

    def test_what_stays_plain_or_is_not_direct(self):
        marked = {j["start"][11:16]: j for j in totals_for(synthetic()).journeys}
        for when in ("10:50", "11:30", "11:35", "11:40", "12:04"):
            self.assertEqual(marked[when]["source"], "Direct or unknown", when)
            self.assertNotIn("likely_direct", marked[when], when)
        for when in ("11:45", "11:50", "12:00"):     # a referrer or a utm_source
            self.assertNotEqual(marked[when]["source"], "Direct or unknown", when)
            self.assertNotIn("likely_direct", marked[when], when)

    def test_the_window_and_the_switch(self):
        got = tally(synthetic(), {"on": True, "window": 5}).extras["direct_likely"]
        # /guides/alpha/ is 12 minutes after its preview; /docs 4 and 5 after its two.
        self.assertEqual(got["details"]["shared"], {"(more than one)": 1, "(share tag)": 1,
                                                    "Instagram": 1})
        self.assertEqual(got["share_window_minutes"], 5)
        got = tally(synthetic(), {"on": True, "window": 4}).extras["direct_likely"]
        self.assertEqual(got["details"]["shared"].get("Slack"), None)
        self.assertEqual(got["details"]["shared"]["WhatsApp"], 1)      # /docs: only 11:01 is in 4
        off = tally(synthetic(), {"on": False, "window": 30}).extras
        self.assertNotIn("direct_likely", off)
        self.assertNotIn("likely_direct", json.dumps(tally(synthetic(), {"on": False}).journeys))

    def test_settings(self):
        self.assertEqual(direct_likely.settings({}), {"on": True, "window": 30})
        self.assertEqual(direct_likely.settings({"attribution": {
            "direct_likely": "off", "share_window_minutes": "10"}}), {"on": False, "window": 10})
        self.assertEqual(direct_likely.settings({"attribution": {"share_window_minutes": "x"}}),
                         {"on": True, "window": 30})
        note = direct_likely.note({})
        self.assertIn("Likely, never certain", note["method"])
        self.assertIn("30 minutes", note["method"])
        self.assertEqual(note["reasons"]["in_app"], "in-app browser")

    def test_planted_errors_are_caught(self):
        for change, what in (
                (lambda b: b["reasons"].update({"in_app": 3}),
                 "direct_likely: likely visits by reason does not sum"),
                (lambda b: b.update({"plain": 6}),
                 "direct_likely: likely and plain visits does not sum"),
                (lambda b: b["details"]["shared"].update({"Slack": 1}),
                 "direct_likely: shared by detail does not sum"),
                (lambda b: b.update({"visits": 19}), "direct_likely: visits does not sum"),
                (lambda b: b.update({"direct": 16, "plain": 6}),
                 "direct_likely: direct visits does not sum")):
            totals = totals_for(synthetic())
            change(totals.extras["direct_likely"])
            self.assertIn(what, [p.what for p in extras.check(totals)])
        totals = totals_for(synthetic())
        next(j for j in totals.journeys if j.get("likely_direct")).pop("likely_direct")
        self.assertIn("direct_likely: journeys marked checkout does not sum",
                      [p.what for p in extras.check(totals)])

    def test_it_is_registered_and_stored(self):
        self.assertIn("direct_likely", day_more.KINDS)
        self.assertIn("direct_likely", store_extras.KINDS)
        self.assertIn("direct_likely", audit_more._modules(audit_more.RECOUNTS))

    def test_journeys_carry_the_reason_to_the_app(self):
        mark = {"reason": "in_app", "detail": "Instagram app"}
        got = dashboard_webapp.journey({"start": "2026-10-05T10:00", "trail": [["/", "page"]],
                                        "likely_direct": mark})
        self.assertEqual(got["likely_direct"], mark)
        self.assertNotIn("likely_direct", dashboard_webapp.journey({"start": "2026-10-05T10:00",
                                                                     "trail": []}))


# Addresses both roads must read alike: (address, checkout detail, share detail).
RULES = [
    ("/thank-you?session_id=cs_test_a1", "Stripe", ""),
    ("/done?payment_intent=pi_3Ab&payment_intent_client_secret=x&redirect_status=succeeded",
     "Stripe", ""),
    ("/billing?setup_intent=seti_1x", "Stripe", ""),
    ("/x?payerid=ABC", "PayPal", ""),
    ("/x?ba_token=BA-123&token=EC-9", "PayPal", ""),
    ("/x?ba_token=ba-123", "", ""),                      # the prefix keeps its case
    ("/paid?razorpay_payment_id=pay_29QQoUBi66xm2f", "Razorpay", ""),
    ("/3ds?cko-session-id=sid_y3oqhf46pyzuxjbcn2giaqnb44", "Checkout.com", ""),
    ("/return?redirectResult=X3XtfGC9%21H4sIAAAAAAAA", "Adyen", ""),
    ("/x?session_id=", "", ""),                          # no value
    ("/x?session_id=abc123", "", ""),                    # not a Stripe Checkout session
    ("/x?token=EC-1", "", ""),                           # PayPal's bare token is not enough
    ("/checkout/success", "(return page)", ""),
    ("/Checkout/Thank_You/", "(return page)", ""),
    ("/checkouts/c/abc123/thank-you", "(return page)", ""),
    ("/en/order-confirmation.html", "(return page)", ""),
    ("/pay/done.php", "(return page)", ""),
    ("/success", "", ""),
    ("/thank-you", "", ""),
    ("/success/checkout", "", ""),                       # the done word must come after
    ("/blog/checkout-complete-guide", "", ""),
    ("/order/success-stories", "", ""),
    ("/payments/returns-policy", "", ""),
    ("/blog/post?igshid=MzRlODBiNWFlZA==", "", "Instagram"),
    ("/p?igsh=abc", "", "Instagram"),
    ("/p?mibextid=Zxz2cZ", "", "Facebook"),
    ("/p?ref=whatsapp", "", "WhatsApp"),
    ("/p?source=WhatsApp_Share", "", "WhatsApp"),
    ("/p?ref=share", "", "(share tag)"),
    ("/p?via=copy-link", "", "(share tag)"),
    ("/p?share=telegram", "", "Telegram"),
    ("/p?from=sms", "", "SMS"),
    ("/p?src=imessage", "", "iMessage"),
    ("/p?ref=producthunt", "", ""),
    ("/p?ref=", "", ""),
    ("/p?si=abc123", "", ""),                            # YouTube's and Spotify's own links
    ("/p?shared=", "", ""),
    ("/p?a=1&ref=newsletter&via=slack", "", "Slack"),    # ref names no share, via does
    ("/p?ref=whatsapp&ref=producthunt", "", ""),         # the last value wins, on both roads
]


class TestTheRules(unittest.TestCase):

    def test_each_address_on_the_main_road(self):
        for url, paid, shared in RULES:
            self.assertEqual(direct_likely.checkout(url), paid, url)
            self.assertEqual(direct_likely.share_marker(url), shared, url)

    def test_the_audit_reads_them_alike(self):
        for url, paid, shared in RULES:
            self.assertEqual(audit_direct_likely._paid_return(url), paid, url)
            self.assertEqual(audit_direct_likely._share_tag(url), shared, url)

    def test_every_in_app_label_is_a_browser_label(self):
        from skald import dimensions
        self.assertLessEqual(set(direct_names.IN_APP_BROWSERS), set(dimensions.BROWSER_NAMES))
        for name in ("Chrome", "Safari", "Samsung Internet", "Other"):
            self.assertNotIn(name, direct_names.IN_APP_BROWSERS)

    def test_the_reasons_and_their_words(self):
        self.assertEqual(direct_names.REASONS, ("checkout", "in_app", "shared"))
        self.assertEqual(set(direct_names.REASON_WORDS), set(direct_names.REASONS))


class TestTheAudit(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(synthetic())

    def tearDown(self):
        self.box.close()

    def stored(self):
        with History(self.box.db) as h:
            return h.extras("example.com", DAY, DAY)[DAY.isoformat()]

    def tamper(self, blob):
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'direct_likely'",
                       (json.dumps(blob),))
        db.close()

    def test_the_recount_matches_and_planted_errors_are_caught(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)
        got = self.stored()["direct_likely"]
        self.assertEqual(got, WANT)
        wrong = json.loads(json.dumps(got))
        wrong["details"]["in_app"] = {"Instagram app": 2}
        self.tamper(wrong)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("direct_likely: in_app, Instagram app: history has 2, the recount finds 1",
                      err)
        self.assertIn("direct_likely: in_app, Facebook app: history has 0, the recount finds 1",
                      err)
        wrong = dict(got, likely=11, plain=4)
        self.tamper(wrong)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("direct_likely: likely visits: history has 11, the recount finds 10", err)

    def test_an_unknown_reason_fails_it(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        got = self.stored()["direct_likely"]
        got["reasons"]["guess"] = 0
        self.tamper(got)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("a reason the recount does not know: guess", err)

    def test_the_stored_window_is_the_one_recounted(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        text = self.box.config.read_text() + "attribution:\n  share_window_minutes: 1\n"
        self.box.config.write_text(text)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)

    def test_switched_off_is_not_recorded_and_not_recounted(self):
        text = self.box.config.read_text() + "attribution:\n  direct_likely: false\n"
        self.box.config.write_text(text)
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        self.assertNotIn("direct_likely", self.stored())
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)

    def test_the_live_audit_compares_it_too(self):
        stamp = at(23, 0).timestamp()
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))
        self.assertEqual(self.box.run("--today", DAY.isoformat(), "live")[0], 0)
        code, _, err = self.box.run("--today", DAY.isoformat(), "audit", "--live")
        self.assertEqual(code, 0, err)
        snap = json.loads((self.box.root / "live-example.com.json").read_text())
        got = snap["extras"]["direct_likely"]
        # Today so far: the live run reads up to its own end, so fewer visits than the day.
        self.assertGreater(got["likely"], 0)
        self.assertEqual(got["likely"], sum(1 for j in snap["journeys"] if j.get("likely_direct")))
        self.assertEqual(got["likely"] + got["plain"], got["direct"])

    def test_campaigns_json_and_visits_json_carry_it(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.box.run("--today", TODAY, "dashboard")
        self.assertEqual(code, 0, err)
        data = self.box.root / "www" / "example.com" / "data"
        got = json.loads((data / "campaigns.json").read_text())
        day = next(d for d in got["days"] if d["day"] == DAY.isoformat())
        self.assertEqual(day["direct_likely"], WANT)
        self.assertEqual(got["direct_likely"]["share_window_minutes"], 30)
        self.assertIn("Likely, never certain", got["direct_likely"]["method"])
        visits = json.loads((data / "visits.json").read_text())
        reasons = sorted(j["likely_direct"]["reason"] for j in visits["journeys"]
                         if j.get("likely_direct"))
        self.assertEqual(reasons, ["checkout"] * 4 + ["in_app"] * 2 + ["shared"] * 4)
        # Names and counts only: no query value of a landing address is kept.
        kept = json.dumps([day["direct_likely"], got["direct_likely"],
                           [j.get("likely_direct") for j in visits["journeys"]]])
        for value in ("cs_test_a1", "ABC", "EC-1", "igshid"):
            self.assertNotIn(value, kept, value)


class TestIndependence(unittest.TestCase):

    def test_the_recount_shares_only_the_name_lists(self):
        tree = ast.parse(Path(audit_direct_likely.__file__).read_text())
        got = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level}
        self.assertEqual(got, {"direct_names"})

    def test_the_name_lists_import_nothing(self):
        tree = ast.parse(Path(direct_names.__file__).read_text())
        got = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(got, {"__future__"})


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestThePage(unittest.TestCase):

    def test_the_pages_reading_of_the_blobs(self):
        got = subprocess.run(["node", str(ROOT / "tests" / "js" / "direct-likely.mjs")],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr + got.stdout)


if __name__ == "__main__":
    unittest.main()

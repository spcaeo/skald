"""2.15.0: `privacy.keep_ips: short` - each kept visit's address shortened.

The rule (people/policy.py): an IPv4 address's last octet zeroed, an IPv6
address cut to its first 48 bits, an IPv4-mapped IPv6 address read as IPv4,
anything else kept as it is. The second count (audit_people.py) shortens by
its own code and must agree. Addresses are RFC 5737 and RFC 3849; the host is
example.com.
"""
from __future__ import annotations

import sqlite3
import sys
import unittest
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import Sandbox, day_lines  # noqa: E402

from skald import audit_people, settings_store  # noqa: E402
from skald.config import load_config  # noqa: E402
from skald.people import lookup, policy, visits as people_visits  # noqa: E402

DAY = date(2026, 10, 6)
SITE = "example.com"
CASES = {
    "203.0.113.57": "203.0.113.0",
    "198.51.100.255": "198.51.100.0",
    "192.0.2.0": "192.0.2.0",
    "2001:db8:85a3:8d3::": "2001:db8:85a3::",
    "2001:db8:85a3:8d3:1319:8a2e:370:7348": "2001:db8:85a3::",
    "2001:db8::1": "2001:db8::",
    "::ffff:203.0.113.57": "203.0.113.0",
    "(removed)": "(removed)",
    "not an address": "not an address",
    "": "",
}


def rows(box: Sandbox, sql: str):
    db = sqlite3.connect(box.root / "conversions.sqlite")
    try:
        return db.execute(sql).fetchall()
    finally:
        db.close()


def change(box: Sandbox, sql: str, args=()) -> None:
    db = sqlite3.connect(box.root / "conversions.sqlite")
    db.execute(sql, args)
    db.commit()
    db.close()


class Rule(unittest.TestCase):
    def test_the_documented_rule(self):
        for full, short in CASES.items():
            self.assertEqual(policy.shorten(full), short, full)

    def test_the_audit_shortens_by_its_own_code_to_the_same_answer(self):
        for full, short in CASES.items():
            self.assertEqual(audit_people.short_address(full), short, full)
        for i in range(0, 256, 17):
            for a in (f"203.0.113.{i}", f"2001:db8:{i:x}:{i:x}::{i:x}", f"::ffff:192.0.2.{i}"):
                self.assertEqual(audit_people.short_address(a), policy.shorten(a), a)

    def test_modes_and_old_words(self):
        mode = lambda v: policy.ip_mode({"privacy": {"keep_ips": v}})  # noqa: E731
        for value, want in ((True, "full"), ("true", "full"), ("1", "full"), ("full", "full"),
                            (False, "off"), ("false", "off"), ("0", "off"), ("off", "off"),
                            ("short", "short"), (" Short ", "short")):
            self.assertEqual(mode(value), want, value)
        self.assertEqual(policy.ip_mode({}), "full")            # a new install
        self.assertTrue(policy.keep_ips({"privacy": {"keep_ips": "short"}}))
        self.assertFalse(policy.keep_ips({"privacy": {"keep_ips": "off"}}))
        got = policy.describe({"privacy": {"keep_ips": "short"}})
        self.assertEqual((got["keep_ips"], got["ip_mode"]), (True, "short"))
        self.assertIs(policy.kept_ip({"privacy": {"keep_ips": "short"}}), policy.shorten)
        self.assertIsNone(policy.kept_ip({"privacy": {"keep_ips": False}}))

    def test_the_audit_reads_short_only_from_the_word(self):
        self.assertTrue(audit_people.shortens({"privacy": {"keep_ips": "short"}}))
        for value in (True, False, "full", "off", None):
            self.assertFalse(audit_people.shortens({"privacy": {"keep_ips": value}}), value)

    def test_a_row_keeps_country_and_city_of_the_full_address(self):
        journey = {"source": "Direct or unknown", "country": "GB", "city": "GB|London",
                   "pages": 1, "trail": [["/", "page"]]}
        got = people_visits.rows(SITE, "2026-10-06", [journey],
                                 [{"ip": "203.0.113.57", "user_agent": "Firefox"}],
                                 kept=policy.shorten)[0]
        cols = people_visits.COLUMNS.split(", ")
        self.assertEqual(got[cols.index("ip")], "203.0.113.0")
        self.assertEqual(got[cols.index("country")], "GB")
        self.assertEqual(got[cols.index("city")], "GB|London")
        # The forgotten list is asked about the full address.
        gone = people_visits.rows(SITE, "2026-10-06", [journey],
                                  [{"ip": "203.0.113.57", "user_agent": "Firefox"}],
                                  hidden=lambda ip: ip == "203.0.113.57",
                                  kept=policy.shorten)[0]
        self.assertEqual(gone[cols.index("ip")], "(removed)")


class Settings(unittest.TestCase):
    def test_three_values_and_the_old_ones(self):
        v = lambda x: settings_store.validate("privacy.keep_ips", x)  # noqa: E731
        self.assertEqual([v(True), v(False), v("true"), v("false"), v("short"), v("full"),
                          v("off")], ["full", "off", "full", "off", "short", "full", "off"])
        with self.assertRaises(settings_store.Invalid):
            v("half")
        key = settings_store.SCHEMA["privacy.keep_ips"]
        self.assertEqual((key.kind, key.default, key.choices),
                         ("ipmode", "full", ("full", "short", "off")))
        self.assertEqual(settings_store.LEGACY_DEFAULTS["privacy.keep_ips"], "off")

    def test_config_true_false_and_short(self):
        for raw, want in ((True, "full"), (False, "off"), ("short", "short")):
            got = settings_store.explain({"privacy": {"keep_ips": raw}})["privacy.keep_ips"]
            self.assertEqual((got["value"], got["source"]), (want, "config"))

    def test_docker_env_takes_short(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "docker"))
        import entrypoint
        self.assertEqual(entrypoint.render_config({"SKALD_KEEP_IPS": "short"})["privacy"],
                         {"keep_ips": "short"})
        self.assertEqual(entrypoint.render_config({"SKALD_KEEP_IPS": "1"})["privacy"],
                         {"keep_ips": True})
        self.assertEqual(entrypoint.render_config({"SKALD_KEEP_IPS": "0"})["privacy"],
                         {"keep_ips": False})


class Shortened(unittest.TestCase):
    """day_lines: four readers, 203.0.113.10 to .13: one shortened address."""

    def setUp(self):
        self.box = Sandbox(mail=False)
        self.box.log(day_lines(DAY, 4))

    def tearDown(self):
        self.box.close()

    def mode(self, word: str) -> None:
        text = self.box.config.read_text().split("privacy:\n")[0]
        self.box.config.write_text(text + f"privacy:\n  keep_ips: {word}\n")

    def collect(self, today="2026-10-07"):
        code, out, err = self.box.run("--today", today, "collect")
        self.assertEqual(code, 0, out + err)

    def audit(self, day="2026-10-06", today="2026-10-07"):
        return self.box.run("--today", today, "audit", "--day", day)

    def test_kept_shortened_and_the_second_count_agrees(self):
        self.mode("short")
        self.collect()
        got = rows(self.box, "SELECT ip, country FROM visits ORDER BY seq")
        self.assertEqual([r[0] for r in got], ["203.0.113.0"] * 4)
        self.assertEqual([r[1] for r in got], ["US", "GB", "US", "GB"])
        self.assertEqual(rows(self.box, "SELECT visits, pages FROM visit_days"), [(4, 4)])
        code, out, err = self.audit()
        self.assertEqual(code, 0, out + err)

    def test_the_second_count_catches_a_full_address_and_a_moved_visit(self):
        self.mode("short")
        self.collect()
        change(self.box, "UPDATE visits SET ip = '203.0.113.11' WHERE seq = 1")
        code, out, err = self.audit()
        self.assertEqual(code, 1)
        self.assertIn("addresses kept in full on a site that keeps them shortened", err)
        self.assertNotIn("203.0.113", err, "no address in a problem")
        change(self.box, "UPDATE visits SET ip = '198.51.100.0' WHERE seq = 1")
        code, out, err = self.audit()
        self.assertEqual(code, 1)
        self.assertIn("shortened addresses whose kept visits differ", err)

    def test_full_to_short_shortens_the_rows_kept_at_the_next_run(self):
        self.collect()
        self.assertEqual(len({r[0] for r in rows(self.box, "SELECT ip FROM visits")}), 4)
        self.mode("short")
        self.box.log(day_lines(DAY, 4) + day_lines(date(2026, 10, 7), 2))
        self.collect("2026-10-08")
        self.assertEqual({r for r in rows(self.box, "SELECT day, ip FROM visits")},
                         {("2026-10-06", "203.0.113.0"), ("2026-10-07", "203.0.113.0")})
        code, out, err = self.audit()
        self.assertEqual(code, 0, out + err)

    def test_short_to_full_keeps_old_rows_short_and_new_rows_full(self):
        self.mode("short")
        self.collect()
        self.mode("full")
        self.box.log(day_lines(DAY, 4) + day_lines(date(2026, 10, 7), 2))
        self.collect("2026-10-08")
        got = rows(self.box, "SELECT day, ip FROM visits ORDER BY day, seq")
        self.assertEqual([ip for d, ip in got if d == "2026-10-06"], ["203.0.113.0"] * 4)
        self.assertEqual([ip for d, ip in got if d == "2026-10-07"],
                         ["203.0.113.10", "203.0.113.11"])
        # The older day was kept shortened: its second count still reconciles...
        code, out, err = self.audit(today="2026-10-08")
        self.assertEqual(code, 0, out + err)
        # ...and still catches a changed row.
        change(self.box, "UPDATE visits SET pages = pages + 1 WHERE day = '2026-10-06' "
                         "AND seq = 0")
        code, out, err = self.audit(today="2026-10-08")
        self.assertEqual(code, 1)

    def test_a_forgotten_address_inside_a_shortened_one(self):
        self.mode("short")
        self.collect()
        code, out, err = self.box.run("forget", "--ip", "203.0.113.11")
        self.assertEqual(code, 0, err)
        self.assertIn("4 kept visit", out)              # the shortened form's rows too
        self.assertEqual(rows(self.box, "SELECT COUNT(*) FROM visits"), [(0,)])
        self.collect()                                  # again: .11 hidden, the rest shortened
        got = Counter(r[0] for r in rows(self.box, "SELECT ip FROM visits"))
        self.assertEqual(got, Counter({"203.0.113.0": 3, "(removed)": 1}))
        code, out, err = self.audit()
        self.assertEqual(code, 0, out + err)

    def test_a_full_address_finds_its_shortened_visits(self):
        self.mode("short")
        self.collect()
        config = load_config(self.box.config)
        config["_resolved"] = {"history_db": str(self.box.db)}
        got = lookup.person(config, self.box.root, SITE, "203.0.113.12", self.box.root)
        self.assertEqual(got["query"], {"kind": "ip", "value": "203.0.113.12",
                                        "short": "203.0.113.0"})
        self.assertEqual(len(got["visits"]), 4)
        self.assertEqual(got["kept"]["ip_mode"], "short")
        self.assertIn("203.0.113.0", got["keys"]["ips"])
        from skald.people import timeline
        first = got["visits"][-1]
        line = timeline.visitor(config, self.box.root, SITE, first["day"], first["seq"])
        self.assertEqual(line["linked_by"], "short_address")

    def test_first_touch_links_by_the_shortened_address(self):
        self.mode("short")
        self.collect()
        import json
        db = sqlite3.connect(self.box.db)
        try:
            blob = json.loads(db.execute("SELECT data FROM day_extras WHERE kind = "
                                         "'first_touch'").fetchone()[0])
        finally:
            db.close()
        self.assertEqual(blob["address_form"], "short")
        # Four browsers alike on one shortened address: the three later ones link
        # to the first (a weaker link, said so).
        self.assertEqual(blob["by"]["address"], 3)


class SecondCountUnit(unittest.TestCase):
    """audit_people.Recount.compare on its own, without the files."""

    def check(self, short: bool, recount: dict, kept: dict) -> list:
        config = {"privacy": {"keep_ips": "short" if short else True}}
        r = audit_people.Recount(config, DAY, None, set())
        for address, (n, p) in recount.items():
            r.visits[address], r.pages[address] = n, p
        visits = sum(n for n, _ in kept.values())
        pages = sum(p for _, p in kept.values())
        r.kept = lambda: (("whole", visits, pages), kept)
        bad = []
        r.compare({}, lambda what, a, b: bad.append(what) if a != b else None, [])
        return bad

    def test_exact_groups_pass_and_a_shifted_page_fails(self):
        recount = {"203.0.113.5": (2, 3), "203.0.113.9": (1, 1), "192.0.2.4": (1, 2)}
        self.assertEqual(self.check(True, recount, {"203.0.113.0": (3, 4),
                                                    "192.0.2.0": (1, 2)}), [])
        self.assertTrue(self.check(True, recount, {"203.0.113.0": (3, 5),
                                                   "192.0.2.0": (1, 1)}))

    def test_with_a_forgotten_address_a_group_may_hold_less_never_more(self):
        recount = {"203.0.113.5": (2, 3), "203.0.113.9": (1, 1)}
        self.assertEqual(self.check(True, recount, {"203.0.113.0": (2, 3),
                                                    "(removed)": (1, 1)}), [])
        self.assertTrue(self.check(True, recount, {"203.0.113.0": (3, 4),
                                                   "(removed)": (1, 1)}))

    def test_a_full_site_with_a_day_kept_shortened(self):
        recount = {"203.0.113.5": (2, 3), "203.0.113.9": (1, 1)}
        self.assertEqual(self.check(False, recount, {"203.0.113.0": (3, 4)}), [])
        self.assertEqual(self.check(False, recount, {"203.0.113.5": (2, 3),
                                                     "203.0.113.9": (1, 1)}), [])
        self.assertTrue(self.check(False, recount, {"203.0.113.5": (3, 4)}))


if __name__ == "__main__":
    unittest.main()

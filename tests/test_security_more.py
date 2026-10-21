"""Security beyond the day kind: the addresses kept behind its rows (security_kept.py) by
privacy mode, `forget --ip`, the helper's people/security for owners and admins only,
security.json, and the two alerts (alerts_security.py) with their recheck."""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import alerts_security, audit_security  # noqa: E402
from skald.config import load_config  # noqa: E402
from skald.people import api  # noqa: E402

from security_support import DAY, box, day_lines, ln, put, stored  # noqa: E402
from test_people_lookup import FakeHandler  # noqa: E402

SITE = "example.com"
URL = f"/traffic/{SITE}/people/security?first=2026-10-05&last=2026-10-05"


def kept(b) -> list:
    with sqlite3.connect(b.root / "conversions.sqlite") as db:
        return db.execute("SELECT seq, ip, user_agent FROM security_rows ORDER BY seq").fetchall()


class Kept(unittest.TestCase):
    def collect(self, extra: str = ""):
        self.box = box(extra=extra)
        code, _, err = self.box.run("--today", "2026-10-06", "collect")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.box.close()

    def test_full_addresses_behind_the_rows_and_audited(self):
        self.collect()
        rows = kept(self.box)
        blob = stored(self.box)
        self.assertEqual(len(rows), len(blob["who"]))
        ips = {ip for _, ip, _ in rows}
        self.assertIn("198.51.100.8", ips)
        self.assertIn("203.0.113.200", ips)
        self.assertNotIn("203.0.113.5", ips, "the person who rendered the page is not kept here")
        self.assertEqual(self.box.run("--today", "2026-10-06", "audit")[0], 0)

    def test_the_audit_catches_a_swapped_address(self):
        self.collect()
        with sqlite3.connect(self.box.root / "conversions.sqlite") as db:
            db.execute("UPDATE security_rows SET ip = '198.51.100.99' WHERE seq = 0")
        code, _, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 1)
        self.assertIn("kept rows whose address or agent differ", err)
        self.assertNotIn("198.51.100.99", err)

    def test_short_keeps_networks_only(self):
        self.collect("privacy:\n  keep_ips: short\n")
        ips = {ip for _, ip, _ in kept(self.box)}
        self.assertIn("198.51.100.0", ips)
        self.assertFalse(any(ip.endswith((".7", ".8", ".200")) for ip in ips))
        self.assertEqual(self.box.run("--today", "2026-10-06", "audit")[0], 0)

    def test_off_keeps_nothing_and_the_day_still_counts(self):
        self.collect("privacy:\n  keep_ips: off\n")
        path = self.box.root / "conversions.sqlite"
        if path.exists():
            with sqlite3.connect(path) as db:
                have = {r[0] for r in db.execute("SELECT name FROM sqlite_master")}
                if "security_rows" in have:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM security_rows").fetchone()[0], 0)
        self.assertEqual(stored(self.box)["probes"], 12)
        self.assertEqual(self.box.run("--today", "2026-10-06", "audit")[0], 0)

    def test_forget_deletes_an_address(self):
        self.collect()
        code, out, _ = self.box.run("forget", "--ip", "198.51.100.8")
        self.assertEqual(code, 0)
        self.assertNotIn("198.51.100.8", {ip for _, ip, _ in kept(self.box)})


class Route(unittest.TestCase):
    def setUp(self):
        self.box = box()
        self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)
        self.config = load_config(self.box.config)
        self.config["_resolved"] = {"history_db": str(self.box.db)}

    def tearDown(self):
        self.box.close()

    def ask(self, path, role="admin", headers=None):
        h = FakeHandler(path, role)
        h.headers = {"Sec-Fetch-Site": "same-origin"} if headers is None else headers
        self.assertTrue(api.is_people(path.split("?")[0]))
        api.handle(h, self.config, self.box.root, self.box.db, self.box.config)
        return h.sent

    def test_owners_and_admins_only_and_an_audit_row(self):
        code, body = self.ask(URL, "viewer")
        self.assertEqual(code, 403)
        self.assertNotIn("rows", body)
        code, _ = self.ask(URL, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(code, 403, "only the page itself")
        code, body = self.ask(URL, "owner")
        self.assertEqual(code, 200)
        self.assertEqual(body["mode"], "full")
        self.assertIn("198.51.100.8", {r["ip"] for r in body["rows"]})
        log = (self.box.root / "privacy.log").read_text()
        self.assertIn("security addresses viewed 2026-10-05..2026-10-05", log)
        self.assertNotIn("198.51.100.", log)

    def test_off_says_so_and_a_bad_period_is_refused(self):
        self.config["privacy"] = {"keep_ips": "off"}
        code, body = self.ask(URL)
        self.assertEqual((code, body["mode"], body["rows"]), (200, "off", []))
        code, _ = self.ask(f"/traffic/{SITE}/people/security?first=2026-10-05&last=2026-10-01")
        self.assertEqual(code, 400)


class DataFile(unittest.TestCase):
    def test_the_file_days_not_recorded_and_no_address(self):
        b = box(day_lines() + [ln(datetime(2026, 10, 4, 9, tzinfo=timezone.utc), "203.0.113.7", "/")])
        try:
            self.assertEqual(b.run("--today", "2026-10-06", "collect")[0], 0)
            with sqlite3.connect(b.db) as db:      # 10-04 collected before Security existed
                self.assertEqual(b.run("--today", "2026-10-05", "collect")[0], 0)
                db.execute("DELETE FROM day_extras WHERE kind = 'security' AND day = '2026-10-04'")
            self.assertEqual(b.run("--today", "2026-10-06", "dashboard")[0], 0)
            f = json.loads((b.root / "www" / SITE / "data" / "security.json").read_text())
            days = {d["day"]: d for d in f["days"]}
            self.assertIsNone(days["2026-10-04"]["security"], "not recorded, never 0")
            self.assertEqual(days[DAY]["security"]["exposure"]["possible"], 1)
            self.assertTrue(days[DAY]["security"]["who_kept"])
            self.assertEqual(f["rules"]["login_posts"], 20)
            self.assertEqual([a["cause"] for a in f["alerts"]], ["security_exposure", "scan_wave", "stack_advisory"])
            text = json.dumps(f)
            for word in ("198.51.100.", "203.0.113.", "python-requests"):
                self.assertNotIn(word, text)
        finally:
            b.close()


class Alerts(unittest.TestCase):
    def setUp(self):
        self.box = box()
        self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)

    def tearDown(self):
        self.box.close()

    def history(self):
        from skald.store import History
        return History(self.box.db)

    def test_settings_exposure_on_wave_off(self):
        cfg = alerts_security.settings({})
        self.assertTrue(cfg["security_exposure"])
        self.assertFalse(cfg["scan_wave"])
        rules = {r["cause"]: r["on"] for r in alerts_security.rules(cfg)}
        self.assertEqual(rules, {"security_exposure": True, "scan_wave": False, "stack_advisory": True})
        from skald.settings_store import SCHEMA
        self.assertTrue(SCHEMA["alerts.security_exposure"].default)
        self.assertFalse(SCHEMA["alerts.scan_wave"].default)

    def test_a_possible_exposure_opens_one_alert_per_path_with_advice(self):
        with self.history() as h:
            found = alerts_security.findings({}, {}, None, h, SITE, date(2026, 10, 5))
        self.assertEqual(len(found), 1)
        f = found[0]
        self.assertEqual((f["cause"], f["subject"], f["figure"]), ("security_exposure", "example.com/.env.production", 1873))
        self.assertIn("never the content", f["detail"])
        self.assertIn("location ~ /\\. { deny all; }", f["detail"])
        snap = {"state": "ok", "extras": {"security": stored(self.box)}}
        with self.history() as h:
            again = alerts_security.findings({}, {}, snap, h, SITE, date(2026, 10, 5))
        self.assertEqual(len(again), 1, "today's and yesterday's same path: one alert")
        with self.history() as h:
            off = alerts_security.findings({}, {"alerts": {"security_exposure": False}}, None, h, SITE,
                                           date(2026, 10, 5))
        self.assertEqual(off, [])

    def test_it_goes_through_the_alert_machinery_and_its_webhook(self):
        from skald import alerts
        self.assertEqual(alerts.SEVERITY["security_exposure"], "high")
        self.assertEqual(alerts.SETTING["scan_wave"], "alerts.scan_wave")
        with self.history() as h:
            f = alerts_security.findings({}, {}, None, h, SITE, date(2026, 10, 5))[0]
        state = {}
        opened, _ = alerts.apply(state, [f], datetime(2026, 10, 6, 12, tzinfo=timezone.utc),
                                 alerts.settings({"alerts": {"enabled": True}}))
        self.assertEqual(len(opened), 1)
        body = alerts.hook_body(opened[0], SITE)
        self.assertEqual(body["event"], "alert.opened")
        self.assertIn("Possible exposure", body["text"])
        self.assertEqual(body["alert"]["severity"], "high")
        mailed = []
        text = alerts._body(opened[0], None)
        mailed.append(text)
        self.assertIn("1873 bytes", mailed[0])

    def test_a_scan_wave_with_its_median_and_its_recheck(self):
        b = stored(self.box)
        with sqlite3.connect(self.box.db) as db:
            row = db.execute("SELECT * FROM days WHERE day = ?", (DAY,)).fetchone()
            cols = [c[1] for c in db.execute("PRAGMA table_info(days)")]
            for k in range(1, 9):              # eight quiet days before it
                d = (date(2026, 10, 5) - timedelta(days=k)).isoformat()
                vals = dict(zip(cols, row), day=d)
                db.execute(f"INSERT INTO days ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                           [vals[c] for c in cols])
                db.execute("INSERT INTO day_extras (site, day, kind, data) VALUES (?, ?, 'security', ?)",
                           (SITE, d, json.dumps({**b, "probes": 2})))
        cfg = {"alerts": {"scan_wave": True, "scan_wave_minimum": 5}}
        state = {}
        with self.history() as h:
            found = alerts_security.findings(state, cfg, None, h, SITE, date(2026, 10, 5))
        wave = [f for f in found if f["cause"] == "scan_wave"]
        self.assertEqual(len(wave), 1)
        self.assertEqual((wave[0]["figure"], wave[0]["threshold"]), (12, 6))
        self.assertEqual(state["security"]["wave"]["median"], 2)
        with self.history() as h:
            self.assertEqual(audit_security.recheck(h.db, SITE, state["security"]), [])
            state["security"]["wave"]["median"] = 1
            self.assertTrue(audit_security.recheck(h.db, SITE, state["security"]))
        with self.history() as h:            # too few days: it waits, never fires
            got = alerts_security.wave(alerts_security.settings({"alerts": {"scan_wave_min_days": 9}}),
                                       h, SITE, date(2026, 10, 5))
        self.assertEqual(got["state"], "waiting")

    def test_the_data_files_rules_list(self):
        put(self.box, stored(self.box))
        cfg = alerts_security.settings({"alerts": {"scan_wave": "on"}})
        self.assertTrue(cfg["scan_wave"])


if __name__ == "__main__":
    unittest.main()

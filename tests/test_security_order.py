"""2.21.1: bursts and login hammering are counted the same way by both roads, whatever order
the log's lines are in. Real logs are not in time order (nginx writes a line when the answer
ends; shippers merge files), and an address can send several user agents. Both roads define
an episode on the address's requests sorted by time; its end is its latest time."""
from __future__ import annotations

import random
import sys
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import security  # noqa: E402
from skald.classify import Group, Verdict  # noqa: E402
from skald.parse import Hit  # noqa: E402

from security_support import box, ln, stored  # noqa: E402

UTC = timezone.utc
T = datetime(2026, 10, 5, 8, tzinfo=UTC)
AGENTS = ["Scrapy/2.11", "python-requests/2.31", "Go-http-client/1.1"]


def day() -> list[str]:
    out = []
    # a burst from one address rotating three agents, out of order, with ties
    for i in range(330):
        out.append(ln(T + timedelta(seconds=i // 6), "198.51.100.11", f"/blog/{i % 9}",
                      AGENTS[i % 3], 200 if i % 7 else 503, 9000))
    # the same agents come back slowly all morning: never part of the burst, whichever
    # agent's lines are read first (the audit once read an address's lines agent by agent)
    for i in range(60):
        out.append(ln(T + timedelta(minutes=2, seconds=37 * i), "198.51.100.11", "/feed",
                      AGENTS[i % 3], 200, 900))
    # two bursts from one address, 300 in 30 s each, 62 s apart: two episodes, never one
    for i in range(600):
        out.append(ln(T + timedelta(minutes=20, seconds=i // 10 + (62 if i >= 300 else 0)),
                      "198.51.100.12", "/", "Scrapy/2.11", 200, 9000))
    # login hammering read out of order, its end second written late
    for i in range(24):
        out.append(ln(T + timedelta(hours=1, seconds=7 * i), "198.51.100.13", "/login",
                      AGENTS[i % 2], 401, 60, method="POST"))
    # just under the thresholds: never an episode
    for i in range(19):
        out.append(ln(T + timedelta(hours=2, seconds=i), "198.51.100.14", "/login",
                      "curl/8.7.1", 401, 60, method="POST"))
    return out


class Order(unittest.TestCase):
    def collect(self, lines):
        b = box(lines)
        try:
            code, _, err = b.run("--today", "2026-10-06", "collect")
            self.assertEqual(code, 0, err)
            code, _, err = b.run("--today", "2026-10-06", "audit")
            self.assertEqual(code, 0, err)
            return stored(b)
        finally:
            b.close()

    def test_any_order_the_same_figures_and_the_audit_agrees(self):
        lines = day()
        first = self.collect(sorted(lines))
        for seed in (1, 2):
            shuffled = lines[:]
            random.Random(seed).shuffle(shuffled)
            got = self.collect(shuffled)
            self.assertEqual(got["attacks"], first["attacks"], f"shuffle {seed}")
            self.assertEqual(got["who"], first["who"], f"shuffle {seed}")
        bursts = first["attacks"]["bursts"]
        self.assertEqual((bursts["episodes"], bursts["requests"]), (3, 930))
        login = first["attacks"]["login"]
        self.assertEqual((login["episodes"], login["posts"]), (1, 24), "19 POSTs: none")
        self.assertEqual(login["rows"][0]["end"], "2026-10-05T09:02:41+00:00", "the latest time")

    def test_the_collector_alone_ignores_arrival_order(self):
        def run(order):
            c = security.Collector()
            for i in order:
                c.add(Hit(when=T + timedelta(seconds=i // 6), address="198.51.100.20", host="example.com",
                          method="GET", url="/", status="200", referrer="",
                          user_agent=AGENTS[i % 3], size=10), Verdict(Group.BOTS))
            return c.finish()["attacks"]["bursts"]
        straight = run(range(320))
        back = run(reversed(range(320)))
        self.assertEqual(straight, back)
        self.assertEqual((straight["episodes"], straight["rows"][0]["end"]), (1, "2026-10-05T08:00:53+00:00"))


def reference(rows: list, need: int, seconds: float) -> list:
    """The episode rule read straight from the module's words, slowly: a request is in an
    episode when some window [T - seconds, T] that holds it holds `need` requests or more;
    an address's such requests, in (time, status, path, pair) order, are one episode while
    each follows the one before within `seconds`. Each episode as (address, start, end,
    requests, status classes, paths, pairs)."""
    out = []
    for address in sorted({r[0] for r in rows}):
        got = sorted((r[1], r[2], r[3], r[4]) for r in rows if r[0] == address)
        stamps = [g[0] for g in got]
        marked = [any(end - seconds <= t <= end and
                      sum(1 for s in stamps if end - seconds <= s <= end) >= need
                      for end in stamps)
                  for t in stamps]
        episode = None
        for g, on in zip(got, marked):
            if not on:
                continue
            if episode is None or g[0] - episode[2] > seconds:
                episode = [address, g[0], g[0], 0, Counter(), Counter(), Counter()]
                out.append(episode)
            episode[2] = g[0]
            episode[3] += 1
            episode[4][g[1]] += 1
            episode[5][g[2]] += 1
            episode[6][g[3]] += 1
    return sorted((a, datetime.fromtimestamp(s, UTC).isoformat(timespec="seconds"),
                   datetime.fromtimestamp(e, UTC).isoformat(timespec="seconds"), n,
                   sorted(st.items()), sorted(pa.items()), sorted(pr.items()))
                  for a, s, e, n, st, pa, pr in out)


class Reference(unittest.TestCase):
    """2.22.2: Runs keeps only what an episode reads and sorts each address once; its
    episodes equal the plain reading of the rule on a shuffled synthetic day."""

    def synthetic(self, seed: int) -> list:
        rnd = random.Random(seed)
        rows = []
        for a in range(8):
            address = f"198.51.100.{30 + a}"
            for _ in range(rnd.randint(0, 3)):            # a few dense runs, with ties
                start = rnd.uniform(0, 86_000)
                for _ in range(rnd.randint(2, 40)):
                    rows.append((address, start + rnd.choice((0, 0.5, 1, rnd.uniform(0, 12)))))
            for _ in range(rnd.randint(0, 60)):            # and scattered requests
                rows.append((address, rnd.uniform(0, 86_400)))
        out = []
        for address, offset in rows:
            out.append((address, (T + timedelta(seconds=round(offset, 3))).timestamp(),
                        rnd.choice(("2xx", "4xx", "5xx")), rnd.choice(("/", "/login", "/a")),
                        (address, rnd.choice(AGENTS))))
        rnd.shuffle(out)
        return out

    def test_the_same_episodes_as_the_rule_read_plainly(self):
        for seed in range(1, 7):
            for need, seconds in ((5, 10), (12, 30), (3, 1)):
                rows = self.synthetic(seed)
                runs = security.Runs(need, seconds)
                for address, ts, status, path, pair in rows:
                    runs.add(address, datetime.fromtimestamp(ts, UTC), (status, path, pair))
                got = sorted((a, ep[0].isoformat(timespec="seconds"),
                              ep[1].isoformat(timespec="seconds"), ep[2],
                              sorted(ep[3].items()), sorted(ep[4].items()),
                              sorted(ep[5].items())) for a, ep in runs.episodes())
                self.assertEqual(got, reference(rows, need, seconds), f"seed {seed}, {need}/{seconds}s")
                self.assertIs(runs.episodes(), runs.episodes(), "worked out once")
        self.assertTrue(any(reference(self.synthetic(s), 5, 10) for s in range(1, 7)),
                        "the synthetic days hold episodes")

    def test_an_address_under_the_threshold_holds_no_episode(self):
        runs = security.Runs(20, 300)
        for i in range(19):
            runs.add("198.51.100.40", T + timedelta(seconds=i), ("4xx", "/login", ("198.51.100.40", "x")))
        self.assertEqual(runs.episodes(), [])
        runs.add("198.51.100.40", T + timedelta(seconds=19), ("4xx", "/login", ("198.51.100.40", "x")))
        self.assertEqual([ep[2] for _, ep in runs.episodes()], [20], "a new request: worked out again")


class Midnight(unittest.TestCase):
    def test_a_burst_across_midnight_in_the_sites_zone(self):
        night = datetime(2026, 10, 6, 3, 59, 30, tzinfo=UTC)       # 23:59:30 in New York
        lines = [ln(night + timedelta(seconds=i // 12), "198.51.100.15", "/", "Scrapy/2.11", 200, 900)
                 for i in range(720)]
        random.Random(3).shuffle(lines)
        b = box(lines)
        b.config.write_text(b.config.read_text().replace("timezone: UTC", "timezone: America/New_York"))
        try:
            for day in ("2026-10-06", "2026-10-07"):
                code, _, err = b.run("--today", day, "collect")
                self.assertEqual(code, 0, err)
                code, _, err = b.run("--today", day, "audit")
                self.assertEqual(code, 0, err)
            self.assertEqual(stored(b, "2026-10-05")["attacks"]["bursts"]["requests"], 360,
                             "each day counts its own side of midnight")
        finally:
            b.close()


if __name__ == "__main__":
    unittest.main()

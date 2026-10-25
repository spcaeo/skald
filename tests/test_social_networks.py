"""Social networks (social_networks.py) and their second count (audit_social.py).

What is pinned:
- each network's host rollup on a synthetic day: X = t.co, x.com, twitter.com,
  mobile.twitter.com and the X app; LinkedIn = linkedin.com, lnkd.in and its
  app; Facebook = facebook.com and its l./m. hosts; Threads before Instagram
  (its app id starts like Instagram's); Pinterest under any country domain; ...
- the hosts the Social media rule does not call social stay out (a Mastodon
  server other than mastodon.social, producthunt.com, fb.me, threads.com), and
  a utm_source=pinterest link is a Tagged link, not social;
- the utm rule: utm_source's words, then utm_medium's, then a social click id;
  words naming two networks, or none, are "Social, network not named";
- the networks add up to the Social media visits (the Sources row), every sum
  the blob promises is checked, and a planted error is caught;
- the landing pages fold to the top and "(all others)", still adding up;
- the audit rebuilds the figure from the raw lines, a tampered figure fails it
  (the live audit too); the two roads agree on a list of referrers and links;
- a day stored before 2.34.0 (no social_networks) is filled by `backfill --force`
  from the raw log, and `audit --day` runs the second count on it;
- campaigns.json carries each day's blob and the names; the recount shares only
  social_names.py's lists.
Addresses are RFC 5737, hosts example.com and the networks' own.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import unittest
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import Sandbox, line, totals_for  # noqa: E402

from skald import (audit_more, audit_social, day_more, extras, social_names,  # noqa: E402
                          social_networks, store_extras)
from skald.store import History  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"

# (referrer or "-", landing address, the network, how): one visit each.
VISITS = [
    ("https://t.co/AbC123", "/blog/a", "x", "t.co"),
    ("https://x.com/home", "/blog/a", "x", "x.com"),
    ("https://twitter.com/someone/status/1", "/blog/b", "x", "twitter.com"),
    ("https://mobile.twitter.com/", "/", "x", "mobile.twitter.com"),
    ("android-app://com.twitter.android/", "/", "x", "android-app://com.twitter.android"),
    ("-", "/?utm_source=twitter&utm_medium=social", "x", "(utm_source)"),
    ("-", "/pricing?twclid=2abc", "x", "(twclid)"),
    ("https://www.linkedin.com/feed/", "/", "linkedin", "linkedin.com"),
    ("https://lnkd.in/gAbc", "/guides", "linkedin", "lnkd.in"),
    ("android-app://com.linkedin.android/", "/guides", "linkedin",
     "android-app://com.linkedin.android"),
    ("-", "/?utm_source=social&utm_medium=linkedin", "linkedin", "(utm_medium)"),
    ("-", "/?li_fat_id=abc", "linkedin", "(li_fat_id)"),
    ("https://l.facebook.com/l.php?u=x", "/", "facebook", "l.facebook.com"),
    ("https://m.facebook.com/", "/", "facebook", "m.facebook.com"),
    ("https://lm.facebook.com/", "/", "facebook", "lm.facebook.com"),
    ("-", "/?fbclid=IwAR0abc", "facebook", "(fbclid)"),
    ("https://l.instagram.com/", "/", "instagram", "l.instagram.com"),
    ("android-app://com.instagram.barcelona/", "/", "threads",
     "android-app://com.instagram.barcelona"),
    ("https://www.threads.net/@someone", "/", "threads", "threads.net"),
    ("https://old.reddit.com/r/selfhosted/", "/", "reddit", "old.reddit.com"),
    ("https://youtu.be/abc", "/", "youtube", "youtu.be"),
    ("android-app://com.google.android.youtube/", "/", "youtube",
     "android-app://com.google.android.youtube"),
    ("https://www.tiktok.com/", "/", "tiktok", "tiktok.com"),
    ("https://www.pinterest.co.uk/pin/1", "/", "pinterest", "pinterest.co.uk"),
    ("https://pinterest.com/", "/", "pinterest", "pinterest.com"),
    ("https://bsky.app/profile/x", "/", "bluesky", "bsky.app"),
    ("https://mastodon.social/@someone", "/", "mastodon", "mastodon.social"),
    ("https://news.ycombinator.com/item?id=1", "/", "hackernews", "news.ycombinator.com"),
    ("https://t.me/somechannel", "/", "telegram", "t.me"),
    ("-", "/?utm_source=social", "other", "(utm_source)"),
    ("-", "/?utm_source=facebook-instagram", "other", "(utm_source)"),
]
# Not Social media by the existing rule: never in any network.
NOT_SOCIAL = [
    ("https://fosstodon.org/@someone", "/", "Other website"),
    ("https://www.producthunt.com/posts/x", "/", "Other website"),
    ("https://fb.me/abc", "/", "Other website"),
    ("https://www.threads.com/@someone", "/", "Other website"),
    ("-", "/?utm_source=pinterest", "Tagged link"),
    ("https://www.google.com/", "/", "Search engine"),
    ("-", "/", "Direct or unknown"),
    ("-", "/?gclid=abc&fbclid=xyz", "Search engine"),
]


def at(i: int, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, 9, tzinfo=UTC) + timedelta(minutes=i)


def synthetic(day: date = DAY) -> list[str]:
    out = []
    for i, (ref, url, _, _) in enumerate(VISITS):
        out.append(line(at(i, day), f"203.0.113.{10 + i}", url, referrer=ref))
    for i, (ref, url, _) in enumerate(NOT_SOCIAL):
        out.append(line(at(60 + i, day), f"198.51.100.{10 + i}", url, referrer=ref))
    return out


def want() -> dict:
    nets = Counter(n for _, _, n, _ in VISITS)
    via: dict = {}
    pages: dict = {}
    for _, url, net, how in VISITS:
        via.setdefault(net, Counter())[how] += 1
        pages.setdefault(net, Counter())[url.split("?", 1)[0]] += 1
    return {"visits": len(VISITS) + len(NOT_SOCIAL), "social": len(VISITS),
            "networks": dict(nets), "via": {k: dict(v) for k, v in via.items()},
            "landings": {k: dict(v) for k, v in pages.items()}}


def same(a: dict, b: dict) -> bool:
    return json.loads(json.dumps(a, sort_keys=True)) == json.loads(json.dumps(b, sort_keys=True))


class TestTheDay(unittest.TestCase):

    def test_the_synthetic_day(self):
        totals = totals_for(synthetic())
        got = totals.extras["social_networks"]
        self.assertTrue(same(got, want()), json.dumps(got, indent=1))
        self.assertEqual(extras.check(totals), [])
        # The networks add up to the Social media row of Sources.
        people = totals.groups[next(g for g in totals.groups if g.value == "people")]
        self.assertEqual(sum(got["networks"].values()), people.by["source"]["Social media"])
        # Biggest first, so the page reads them in order.
        self.assertEqual(list(got["networks"])[:3], ["x", "linkedin", "facebook"])

    def test_each_networks_hosts(self):
        rolled = {}
        for ref, url, net, how in VISITS:
            rolled.setdefault(net, set()).add(how)
        self.assertEqual(rolled["x"], {"t.co", "x.com", "twitter.com", "mobile.twitter.com",
                                       "android-app://com.twitter.android", "(utm_source)",
                                       "(twclid)"})
        self.assertEqual(rolled["linkedin"], {"linkedin.com", "lnkd.in",
                                              "android-app://com.linkedin.android",
                                              "(utm_medium)", "(li_fat_id)"})
        for ref, url, net, how in VISITS:
            self.assertEqual(social_networks.network("Social media", "" if ref == "-" else ref,
                                                     url), (net, how), ref + " " + url)

    def test_what_is_not_social_stays_out(self):
        journeys = totals_for(synthetic()).journeys
        for (ref, url, kind), j in zip(NOT_SOCIAL, journeys[len(VISITS):]):
            self.assertEqual(j["source"], kind, ref + " " + url)
            self.assertIsNone(social_networks.network(kind, ref, url))

    def test_the_utm_rule(self):
        net = lambda url: social_networks.network("Social media", "", url)  # noqa: E731
        self.assertEqual(net("/?utm_source=x"), ("x", "(utm_source)"))
        self.assertEqual(net("/?utm_source=X&utm_medium=cpc"), ("x", "(utm_source)"))
        self.assertEqual(net("/?utm_source=linkedin_ads"), ("linkedin", "(utm_source)"))
        # utm_source first: utm_medium only when the source names no network.
        self.assertEqual(net("/?utm_source=facebook&utm_medium=linkedin"),
                         ("facebook", "(utm_source)"))
        self.assertEqual(net("/?utm_source=spring&utm_medium=instagram"),
                         ("instagram", "(utm_medium)"))
        # A tag before a click id; a click id when no tag names a network.
        self.assertEqual(net("/?utm_source=x&fbclid=1"), ("x", "(utm_source)"))
        self.assertEqual(net("/?utm_medium=social&ttclid=1"), ("tiktok", "(ttclid)"))
        # Two networks named, or none: not named, counted once.
        self.assertEqual(net("/?utm_source=x-and-linkedin"), ("other", "(utm_source)"))
        self.assertEqual(net("/?utm_medium=social"), ("other", "(utm_medium)"))
        # "xbox" is not "x": whole words only.
        self.assertEqual(net("/?utm_source=social&utm_medium=xbox"), ("other", "(utm_source)"))
        # A referrer always decides first, whatever the tags say.
        self.assertEqual(social_networks.network("Social media", "https://lnkd.in/a",
                                                 "/?utm_source=twitter"),
                         ("linkedin", "lnkd.in"))

    def test_the_landing_pages_fold_and_still_add_up(self):
        pages = Counter({f"/p{i:02d}": 30 - i for i in range(25)})
        got = social_networks.fold(pages)
        self.assertEqual(len(got), social_names.LANDINGS_KEPT)
        self.assertEqual(sum(got.values()), sum(pages.values()))
        self.assertEqual(got[social_names.ALL_OTHERS], sum(30 - i for i in range(19, 25)))
        self.assertEqual(audit_social._fold(pages), got)
        tie = Counter({"/b": 1, "/a": 1})
        self.assertEqual(list(social_networks.fold(tie)), ["/a", "/b"])

    def test_planted_errors_are_caught(self):
        for change, what in (
                (lambda b: b["networks"].update({"x": 8}),
                 "social_networks: visits by network does not sum"),
                (lambda b: b["via"]["x"].update({"t.co": 2}),
                 "social_networks: x by via does not sum"),
                (lambda b: b["landings"]["linkedin"].update({"/": 9}),
                 "social_networks: linkedin by landings does not sum"),
                (lambda b: b.update({"visits": 40}), "social_networks: visits does not sum"),
                (lambda b: (b.update({"social": 32}), b["networks"].update({"other": 3}),
                            b["via"]["other"].update({"(none)": 1}),
                            b["landings"]["other"].update({"/x": 1})),
                 "social_networks: social visits does not sum")):
            totals = totals_for(synthetic())
            change(totals.extras["social_networks"])
            self.assertIn(what, [p.what for p in extras.check(totals)])
        totals = totals_for(synthetic())
        blob = totals.extras["social_networks"]
        blob["networks"]["myspace"] = 1
        blob["social"] += 1
        self.assertIn("social_networks", [p.what for p in extras.check(totals)])

    def test_a_day_without_a_social_visit(self):
        totals = totals_for([line(at(0), "203.0.113.10", "/")])
        self.assertEqual(totals.extras["social_networks"],
                         {"visits": 1, "social": 0, "networks": {}, "via": {}, "landings": {}})
        self.assertEqual(extras.check(totals), [])

    def test_it_is_registered_and_stored(self):
        self.assertIn("social_networks", day_more.KINDS)
        self.assertIn("social_networks", store_extras.KINDS)
        self.assertIn("social_networks", audit_more._modules(audit_more.RECOUNTS))


class TestTheNames(unittest.TestCase):

    def test_ids_are_short_and_unique(self):
        self.assertEqual(len(set(social_names.IDS)), len(social_names.IDS))
        for net in social_names.IDS:
            self.assertRegex(net, r"^[a-z]{1,12}$")
        self.assertEqual(set(social_names.NAMES), set(social_names.IDS))

    def test_every_host_listed_is_social_by_the_existing_rule(self):
        """The lists group the Social media hosts; they never make a new one."""
        from skald import dimensions
        for net, _name, hosts, bases, apps, _w, _ids in social_names.NETWORKS:
            for host in hosts + tuple(f"{b}.com" for b in bases):
                self.assertEqual(dimensions.source_type(f"https://{host}/", "/", False, set()),
                                 "Social media", host)
            for app in apps:
                self.assertEqual(dimensions.source_type(f"android-app://{app}.android/", "/",
                                                        False, set()), "Social media", app)
            for word in _w:
                self.assertEqual(dimensions.source_type("", f"/?utm_source={word}", False,
                                                        set()), "Social media", word)

    def test_every_social_host_of_the_rule_has_its_network(self):
        from skald import audit_labels
        for host in audit_labels._SOCIAL_SITES:
            self.assertNotEqual(social_networks.network("Social media", f"https://{host}/", "/")[0],
                                "other", host)
        for app in audit_labels._SOCIAL_APPS:
            self.assertNotEqual(social_networks.network(
                "Social media", f"android-app://{app}/", "/")[0], "other", app)


# Referrer and landing pairs both roads must read alike: (referrer, url).
RULES = [(ref if ref != "-" else "", url) for ref, url, _, _ in VISITS] + [
    ("https://WWW.LinkedIn.com./in/x", "/"),
    ("https://u:@x.com:443/a", "/"),
    ("x.com/no-scheme", "/"),
    ("https://a.b.pinterest.de/", "/"),
    ("https://pinterest.example.com/", "/"),      # Social media by the rule: Pinterest
    ("android-app://com.slack/", "/"),
    ("android-app://com.whatsapp.w4b/", "/"),
    ("android-app://org.telegram.messenger/", "/"),
    ("https://discord.com/channels/1", "/"),
    ("https://www.quora.com/q", "/"),
    ("", "/?utm_source=Twitter+Ads"),
    ("", "/?utm_source=&utm_medium=linkedin"),
    ("", "/?utm_source=x&utm_source=reddit"),       # the last value wins, on both roads
    ("", "/?utm_medium=youtube%20video"),
    ("", "/?fbclid=&ttclid=1"),
    ("", "/?a=1&b&utm_medium=social"),
]


class TestTheRules(unittest.TestCase):

    def test_the_audit_reads_them_alike(self):
        for ref, url in RULES:
            main = social_networks.network("Social media", ref, url)
            self.assertEqual(audit_social.network_of(ref, url), main, f"{ref} {url}")


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
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'social_networks'",
                       (json.dumps(blob),))
        db.close()

    def test_the_recount_matches_and_planted_errors_are_caught(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)
        got = self.stored()["social_networks"]
        self.assertTrue(same(got, want()))
        wrong = json.loads(json.dumps(got))
        wrong["via"]["x"] = {"t.co": 7}
        self.tamper(wrong)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("social_networks: x via, t.co: history has 7, the recount finds 1", err)
        self.assertIn("social_networks: x via, x.com: history has 0, the recount finds 1", err)
        wrong = json.loads(json.dumps(got))
        wrong["networks"]["linkedin"] = 6
        self.tamper(wrong)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("social_networks: linkedin: history has 6, the recount finds 5", err)

    def test_an_unknown_network_fails_it(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        got = self.stored()["social_networks"]
        got["networks"]["myspace"] = 0
        self.tamper(got)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("a network the recount does not know: myspace", err)

    def test_the_live_audit_compares_it_too(self):
        stamp = at(120).timestamp()
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))
        self.assertEqual(self.box.run("--today", DAY.isoformat(), "live")[0], 0)
        code, _, err = self.box.run("--today", DAY.isoformat(), "audit", "--live")
        self.assertEqual(code, 0, err)
        snap = json.loads((self.box.root / "live-example.com.json").read_text())
        got = snap["extras"]["social_networks"]
        self.assertGreater(got["social"], 0)
        self.assertEqual(sum(got["networks"].values()), got["social"])

    def test_a_day_from_before_2_34_is_filled_by_backfill_force(self):
        # A day stored before 2.34.0 has no social_networks: "Not recorded".
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("DELETE FROM day_extras WHERE kind = 'social_networks'")
        db.close()
        self.assertNotIn("social_networks", self.stored())
        code, out, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)            # not recorded is skipped, never 0
        # A plain backfill leaves a stored, verified day alone ...
        code, out, err = self.box.run("--today", TODAY, "backfill", "--days", "1")
        self.assertEqual(code, 0, err)
        self.assertIn("skipped 1", out)
        self.assertNotIn("social_networks", self.stored())
        # ... --force counts it again from the raw log, social_networks included.
        code, out, err = self.box.run("--today", TODAY, "backfill", "--days", "1", "--force")
        self.assertEqual(code, 0, err)
        self.assertIn("ok 1", out)
        got = self.stored()["social_networks"]
        self.assertTrue(same(got, want()))
        # The audit of the recounted day runs the second count, and matches.
        code, out, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)
        self.assertIn("all match", out)
        wrong = json.loads(json.dumps(got))
        wrong["networks"]["x"] = 99
        self.tamper(wrong)
        code, _, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertEqual(code, 1)
        self.assertIn("social_networks: x: history has 99, the recount finds 7", err)

    def test_campaigns_json_carries_it(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.box.run("--today", TODAY, "dashboard")
        self.assertEqual(code, 0, err)
        data = self.box.root / "www" / "example.com" / "data"
        got = json.loads((data / "campaigns.json").read_text())
        day = next(d for d in got["days"] if d["day"] == DAY.isoformat())
        self.assertTrue(same(day["social_networks"], want()))
        self.assertEqual(got["social_networks"]["names"]["x"], "X")
        self.assertEqual(got["social_networks"]["names"]["other"], "Social, network not named")
        # Hosts, tags, paths and counts only: no query value, no address.
        kept = json.dumps(day["social_networks"])
        for value in ("AbC123", "IwAR0abc", "203.0.113", "someone", "2abc"):
            self.assertNotIn(value, kept, value)


class TestIndependence(unittest.TestCase):

    def test_the_recount_shares_only_the_name_lists(self):
        tree = ast.parse(Path(audit_social.__file__).read_text())
        got = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level}
        self.assertEqual(got, {"social_names"})

    def test_the_name_lists_import_nothing(self):
        tree = ast.parse(Path(social_names.__file__).read_text())
        got = {n.module for n in ast.walk(tree) if isinstance(n, (ast.ImportFrom, ast.Import))
               and getattr(n, "module", None)}
        self.assertEqual(got, {"__future__"})
        self.assertFalse([n for n in ast.walk(tree) if isinstance(n, ast.Import)])


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestThePage(unittest.TestCase):

    def test_the_pages_reading_of_the_blobs(self):
        got = subprocess.run(["node", str(ROOT / "tests" / "js" / "social-networks.mjs")],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr + got.stdout)


if __name__ == "__main__":
    unittest.main()

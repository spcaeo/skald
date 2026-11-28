"""SKALD-52: Claude-User fetches from Anthropic's documented outbound addresses.

Found 23 Nov 2026: claude.ai fetched a page for a person as `Claude-User/1.0` from an address
in Anthropic's outbound range. Skald checked every Anthropic agent only against
claude.com/crawling/bots.json, which does not hold that range, so the real fetch was judged
"spoofed": moved to bots as "claims to be Claude-User", out of the AI figures, on every site.

Now Skald also keeps the outbound section of Anthropic's IP address page (bot_verify LISTS
"anthropic-outbound", read by parse_page) and it proves Claude-User only (AGENT_LISTS), on
both counting roads. A day stored before is audited as it was counted (audit_rules).

Test data: RFC 5737 addresses stand in for Anthropic's ranges (192.0.2.0/28 for bots.json,
198.51.100.0/24 for the outbound range).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_release2, audit_rules, bot_verify  # noqa: E402
from skald.classify import Classifier, Group  # noqa: E402

from support import UTC, Sandbox, line  # noqa: E402

LISTED = "192.0.2.5"                     # in bots.json (the "anthropic" list)
OUTBOUND = "198.51.100.7"                # in the outbound range only
ELSEWHERE = "203.0.113.9"                # in neither
CLAUDE_USER = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0)"
CLAUDEBOT = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0)"
SEARCHBOT = "Mozilla/5.0 (compatible; Claude-SearchBot/1.0)"
ANTHROPIC_AI = "anthropic-ai"
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"

# The page's shape on 26 Nov 2026 (HTML, as urllib gets it), cut down: a script that
# repeats the text, a contents list that names the sections, and the sections themselves.
PAGE_HTML = """<html><head><script>self.__next_f.push(["Outbound IP addresses 192.0.2.200/32"])
</script><style>h2::before{content:"#"}</style></head><body>
<nav><a href="#inbound">Inbound IP addresses</a><a href="#outbound">Outbound IP addresses</a></nav>
<h1>IP addresses</h1>
<h2 id="inbound"><a href="#inbound">Inbound IP addresses</a></h2>
<p>Where Anthropic services receive incoming connections. Unlike the outbound IP
addresses, these take your requests.</p>
<h3>IPv4</h3><p><code>203.0.113.0/26</code></p><p><code>203.0.113.64/26</code></p>
<h3>IPv6</h3><p><code>2001:db8:a::/48</code></p>
<h2 id="outbound"><a href="#outbound">Outbound IP addresses</a></h2>
<p>These are the stable IP addresses that Anthropic uses for outbound requests.</p>
<h3>IPv4</h3><p><code>198.51.100.0/24</code></p><p><code>192.0.2.128/25</code></p>
<h3>Phased out IP addresses</h3>
<pre><code>203.0.113.200/32
203.0.113.201/32</code></pre>
<h2>Cloud platforms</h2><p>Requests go to 203.0.113.250/32 instead.</p>
<footer><h3>Learn</h3></footer></body></html>"""

PAGE_MD = """---
title: IP addresses
---

## Inbound IP addresses

These are the IP addresses where Anthropic services receive incoming connections.

### IPv4

`203.0.113.0/26`

### IPv6

`2001:db8:a::/48`

## Outbound IP addresses

These are the stable IP addresses that Anthropic uses for outbound requests.

### IPv4

`198.51.100.0/24`

`192.0.2.128/25`

### IPv6

`2001:db8:b::/48`

### Phased out IP addresses

```text wrap
203.0.113.200/32
# not a heading
```

## Cloud platforms

On the following platforms, your API requests go to the cloud provider.
"""


def lists(folder: Path, when: datetime | None = None, outbound: bool = True,
          outbound_when: datetime | None = None) -> Path:
    """bots.json's list (192.0.2.0/28) and, unless told not to, the outbound range."""
    folder.mkdir(parents=True, exist_ok=True)
    now = when or datetime.now(timezone.utc)
    for name, nets, at in (("anthropic", ["192.0.2.0/28"], now),
                           ("anthropic-outbound", ["198.51.100.0/24"], outbound_when or now)):
        path = folder / f"{name}.json"
        if name == "anthropic-outbound" and not outbound:
            path.unlink(missing_ok=True)
            continue
        path.write_text(json.dumps({"source": "test", "fetched": at.isoformat(timespec="seconds"),
                                    "networks": nets, "error": None}))
    return folder


def hit(agent: str, address: str):
    from skald.parse import Hit
    return Hit(when=datetime(2026, 10, 5, 12, tzinfo=timezone.utc), address=address,
               host="example.com", method="GET", url="/", status="200", referrer="-",
               user_agent=agent, size=10)


class ThePage(unittest.TestCase):
    """parse_page reads the outbound section only, on either form of the page."""

    def test_the_outbound_section_of_the_html_page(self):
        self.assertEqual(bot_verify.parse_page(PAGE_HTML.encode(), "Outbound IP addresses"),
                         ["198.51.100.0/24", "192.0.2.128/25"])

    def test_the_outbound_section_of_the_markdown_page(self):
        self.assertEqual(bot_verify.parse_page(PAGE_MD.encode(), "Outbound IP addresses"),
                         ["198.51.100.0/24", "192.0.2.128/25", "2001:db8:b::/48"])

    def test_phased_out_inbound_scripts_and_contents_never_count(self):
        for page in (PAGE_HTML, PAGE_MD):
            got = bot_verify.parse_page(page.encode(), "Outbound IP addresses")
            for never in ("203.0.113.200/32", "203.0.113.201/32", "203.0.113.0/26",
                          "203.0.113.250/32", "192.0.2.200/32", "2001:db8:a::/48"):
                self.assertNotIn(never, got)

    def test_a_hash_line_in_an_html_page_is_no_heading(self):
        page = (b"<h2>Outbound IP addresses</h2><p>x</p>\n# not a heading\n"
                b"<p><code>198.51.100.0/24</code></p><h2>Next</h2>")
        self.assertEqual(bot_verify.parse_page(page, "Outbound IP addresses"),
                         ["198.51.100.0/24"])

    def test_an_address_heading_inside_phased_out_is_still_phased_out(self):
        md = (b"## Outbound IP addresses\n### IPv4\n`198.51.100.0/24`\n"
              b"### Phased out IP addresses\n#### IPv4\n`203.0.113.200/32`\n"
              b"#### IPv6\n`2001:db8:dead::/48`\n### IPv6\n`2001:db8:b::/48`\n## Next\n")
        self.assertEqual(bot_verify.parse_page(md, "Outbound IP addresses"),
                         ["198.51.100.0/24", "2001:db8:b::/48"])
        html = (b"<h2>Outbound IP addresses</h2><h3>IPv4</h3><code>198.51.100.0/24</code>"
                b"<h3>Phased out IP addresses</h3><h4>IPv4</h4><code>203.0.113.200/32</code>"
                b"<h2>Next</h2>")
        self.assertEqual(bot_verify.parse_page(html, "Outbound IP addresses"),
                         ["198.51.100.0/24"])

    def test_small_heading_changes_still_read(self):
        md = (b"## Outbound IP addresses \xc2\xb6\n### IPv4 addresses\n`198.51.100.0/24`\n"
              b"### #IPv6\n`2001:db8:b::/48`\n")
        self.assertEqual(bot_verify.parse_page(md, "Outbound IP addresses"),
                         ["198.51.100.0/24", "2001:db8:b::/48"])

    def test_a_prefix_too_wide_to_be_one_owners_is_refused(self):
        for wide in (b"0.0.0.0/0", b"10.0.0.0/8", b"2001:db8::/16"):
            with self.assertRaises(ValueError):
                bot_verify.parse_page(b"## Outbound IP addresses\n`" + wide + b"`\n",
                                      "Outbound IP addresses")

    def test_the_inbound_section_is_its_own(self):
        self.assertEqual(bot_verify.parse_page(PAGE_MD.encode(), "Inbound IP addresses"),
                         ["203.0.113.0/26", "2001:db8:a::/48"])

    def test_a_page_without_the_section_or_its_addresses_is_refused(self):
        with self.assertRaises(ValueError):
            bot_verify.parse_page(b"<html><h2>Something else</h2>192.0.2.0/24</html>",
                                  "Outbound IP addresses")
        with self.assertRaises(ValueError):
            bot_verify.parse_page(b"## Outbound IP addresses\n\nNone yet.\n## Next\n",
                                  "Outbound IP addresses")
        with self.assertRaises(ValueError):           # an error page
            bot_verify.parse_page(b"<html><title>404</title></html>", "Outbound IP addresses")

    def test_a_section_that_lists_too_many_is_a_page_misread(self):
        many = "\n".join(f"`198.51.100.{i}/32`" for i in range(bot_verify.PAGE_MAX + 1))
        with self.assertRaises(ValueError):
            bot_verify.parse_page(f"## Outbound IP addresses\n{many}\n".encode(),
                                  "Outbound IP addresses")

    def test_a_json_list_is_read_as_one(self):
        raw = json.dumps({"prefixes": [{"ipv4Prefix": "198.51.100.0/24"}]}).encode()
        self.assertEqual(bot_verify.parse_page(raw, "Outbound IP addresses"),
                         ["198.51.100.0/24"])


class TheFetch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def fetch(self, page):
        def get(url):
            if url == bot_verify.LISTS["anthropic-outbound"]:
                if isinstance(page, Exception):
                    raise page
                return page
            return json.dumps({"prefixes": [{"ipv4Prefix": "192.0.2.0/28"}]}).encode()
        return get

    def test_the_page_is_fetched_with_the_other_lists_and_stored_dated(self):
        done = bot_verify.refresh_lists(self.dir, fetch=self.fetch(PAGE_HTML.encode()),
                                        hosting=False)
        self.assertEqual(done["anthropic-outbound"], "ok")
        kept = bot_verify.load_list(self.dir, "anthropic-outbound")
        self.assertEqual(kept["networks"], ["198.51.100.0/24", "192.0.2.128/25"])
        self.assertEqual(kept["source"], bot_verify.LISTS["anthropic-outbound"])
        self.assertTrue(kept["fetched"])
        self.assertIn("anthropic-outbound", bot_verify.Verifier(self.dir).fresh)

    def test_a_changed_or_unreachable_page_keeps_the_last_good_copy(self):
        bot_verify.refresh_lists(self.dir, fetch=self.fetch(PAGE_MD.encode()), hosting=False)
        for bad in (b"<html><h2>Moved</h2></html>", OSError("unreachable")):
            done = bot_verify.refresh_lists(self.dir, fetch=self.fetch(bad), hosting=False)
            self.assertTrue(done["anthropic-outbound"].startswith("failed"))
            kept = bot_verify.load_list(self.dir, "anthropic-outbound")
            self.assertEqual(kept["networks"][0], "198.51.100.0/24")
            self.assertTrue(kept["error"])
            self.assertFalse(bot_verify.lists_current(self.dir, datetime.now(timezone.utc)))


class BothRoadsJudge(unittest.TestCase):
    """bot_verify.Verifier (the count) and audit_release2.Checks (the audit) give the same
    verdict for every Anthropic agent, address and state of the lists."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "ranges"

    def tearDown(self):
        self.tmp.cleanup()

    def both(self, name, address, agent=""):
        now = datetime.now(timezone.utc)
        mine = bot_verify.Verifier(self.dir, now).status(name, address, agent)
        theirs = audit_release2.Checks({"bots": {"ranges_dir": str(self.dir)}}, now).verdict(
            name, address, agent)
        self.assertEqual(mine, theirs, f"{name} from {address}: count {mine}, audit {theirs}")
        return mine

    def test_claude_user_from_the_outbound_range_is_verified(self):
        lists(self.dir)
        self.assertEqual(self.both("Claude-User", OUTBOUND), "verified")
        self.assertEqual(self.both("claude-user", "198.51.100.254"), "verified")

    def test_claude_user_from_elsewhere_is_still_spoofed(self):
        lists(self.dir)
        self.assertEqual(self.both("Claude-User", ELSEWHERE), "spoofed")

    def test_bots_json_still_verifies_every_agent(self):
        lists(self.dir)
        for name in ("Claude-User", "ClaudeBot", "Claude-SearchBot", "anthropic-ai"):
            self.assertEqual(self.both(name, LISTED), "verified", name)

    def test_the_outbound_range_proves_claude_user_only(self):
        # Claude's crawlers do not fetch from it; Claude-SearchBot's addresses are an open
        # question on the ticket, unchanged here.
        lists(self.dir)
        for name in ("ClaudeBot", "Claude-SearchBot", "anthropic-ai"):
            self.assertEqual(self.both(name, OUTBOUND), "spoofed", name)

    def test_without_the_outbound_list_claude_user_is_never_called_fake(self):
        # An unknown stays unknown: the real fetch may come from the list not at hand.
        lists(self.dir, outbound=False)
        self.assertEqual(self.both("Claude-User", OUTBOUND), "unverified")
        self.assertEqual(self.both("Claude-User", ELSEWHERE), "unverified")
        self.assertEqual(self.both("ClaudeBot", ELSEWHERE), "spoofed")   # its own list is fresh

    def test_a_stale_outbound_list_still_verifies_but_never_says_spoofed(self):
        lists(self.dir, outbound_when=datetime.now(timezone.utc) - timedelta(days=30))
        self.assertEqual(self.both("Claude-User", OUTBOUND), "verified")
        self.assertEqual(self.both("Claude-User", ELSEWHERE), "unverified")

    def test_claude_code_is_still_unchecked(self):
        lists(self.dir)
        self.assertEqual(self.both("Claude-User", ELSEWHERE,
                                   "Claude-User (claude-code/2.1.292; +https://support.anthropic.com/)"),
                         "unverified")

    def test_one_address_judged_for_two_agents_is_not_mixed_up(self):
        # The verdicts are kept per address: Claude-User's answer must not become ClaudeBot's.
        lists(self.dir)
        now = datetime.now(timezone.utc)
        verifier = bot_verify.Verifier(self.dir, now)
        checks = audit_release2.Checks({"bots": {"ranges_dir": str(self.dir)}}, now)
        for judge in (verifier.status, checks.verdict):
            self.assertEqual(judge("Claude-User", OUTBOUND, ""), "verified")
            self.assertEqual(judge("ClaudeBot", OUTBOUND, ""), "spoofed")
            self.assertEqual(judge("Claude-User", OUTBOUND, ""), "verified")

    def test_the_audit_can_judge_as_before_for_an_older_day(self):
        lists(self.dir)
        checks = audit_release2.Checks({"bots": {"ranges_dir": str(self.dir)}},
                                       datetime.now(timezone.utc))
        checks.agent_rule = False
        self.assertEqual(checks.verdict("Claude-User", OUTBOUND, ""), "spoofed")
        self.assertEqual(checks.verdict("Claude-User", LISTED, ""), "verified")

    def test_the_classifier_counts_the_real_fetch_as_claude(self):
        lists(self.dir)
        c = Classifier()
        c.verifier = bot_verify.Verifier(self.dir)
        real = c(hit(CLAUDE_USER, OUTBOUND))
        self.assertEqual((real.group, real.verified), (Group.ANSWER_ENGINE, "verified"))
        fake = c(hit(CLAUDE_USER, ELSEWHERE))
        self.assertEqual((fake.group, fake.engine), (Group.BOTS, "claims to be Claude-User"))

    def test_the_lists_counted_with_are_named(self):
        lists(self.dir)
        self.assertEqual(bot_verify.Verifier(self.dir).agent_lists(), ["anthropic-outbound"])
        lists(self.dir, outbound=False)
        self.assertEqual(bot_verify.Verifier(self.dir).agent_lists(), [])


ON = {"cdn": True, "agent_lists": True, "hidden": True}


class Rules(unittest.TestCase):
    """audit_rules: which rules a stored day or live snapshot was counted by."""

    def test_hidden_referral(self):
        # SKALD-69's switch rides with SKALD-52's (the release merge put them together).
        self.assertEqual(audit_rules.rules_of({"quality": {"cdn_lines": 0, "hidden_referral": True},
                                               "bots": {"agent_lists": []}}), ON)

    def test_a_snapshot(self):
        self.assertEqual(audit_rules.rules_of(None), {"cdn": False, "agent_lists": False, "hidden": False})
        self.assertEqual(audit_rules.rules_of({"quality": {"cdn_lines": 0},
                                               "bots": {"agent_lists": []}}),
                         {"cdn": True, "agent_lists": True, "hidden": False})
        self.assertEqual(audit_rules.rules_of({"quality": {"cdn_lines": None},
                                               "bots": {"verification": {}}}),
                         {"cdn": False, "agent_lists": False, "hidden": False})

    def test_a_stored_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.sqlite"
            self.assertEqual(audit_rules.stored_rules(path, "example.com", DAY),
                             ON, "no store: nothing to protect")
            db = sqlite3.connect(str(path))
            db.execute("CREATE TABLE day_extras (site TEXT, day TEXT, kind TEXT, data TEXT)")
            db.commit()
            self.assertEqual(audit_rules.stored_rules(path, "example.com", DAY),
                             ON, "day not stored")
            db.execute("INSERT INTO day_extras VALUES (?, ?, 'bots', ?)",
                       ("example.com", DAY.isoformat(), json.dumps({"verification": {}})))
            db.execute("INSERT INTO day_extras VALUES (?, ?, 'quality', ?)",
                       ("example.com", DAY.isoformat(), json.dumps({"cdn_lines": None})))
            db.commit()
            self.assertEqual(audit_rules.stored_rules(path, "example.com", DAY),
                             {"cdn": False, "agent_lists": False, "hidden": False}, "stored before all")
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'bots'",
                       (json.dumps({"verification": {}, "agent_lists": ["anthropic-outbound"]}),))
            db.execute("UPDATE day_extras SET data = 'not json' WHERE kind = 'quality'")
            db.commit()
            db.close()
            self.assertEqual(audit_rules.stored_rules(path, "example.com", DAY),
                             ON, "an unreadable quality row: on")
            self.assertEqual(audit_rules.stored_rules(path, "other.example", DAY), ON)


class CollectAndAudit(unittest.TestCase):
    """A day collected with the lists: counted right, and the audit's own road agrees."""

    def setUp(self):
        self.box = Sandbox()
        self.folder = lists(self.box.root / "ranges")
        self.box.config.write_text(self.box.config.read_text()
                                   + f"bots:\n  ranges_dir: {self.folder}\n")
        at = datetime(DAY.year, DAY.month, DAY.day, 9, tzinfo=UTC)
        self.box.log([line(at + timedelta(minutes=i), OUTBOUND, f"/p{i}", CLAUDE_USER)
                      for i in range(3)]
                     + [line(at + timedelta(hours=1), ELSEWHERE, "/x", CLAUDE_USER),
                        line(at + timedelta(hours=2), OUTBOUND, "/y", CLAUDEBOT),
                        line(at + timedelta(hours=3), LISTED, "/z", CLAUDEBOT),
                        line(at + timedelta(hours=4), OUTBOUND, "/s", SEARCHBOT)])

    def tearDown(self):
        self.box.close()

    def blob(self) -> dict:
        db = sqlite3.connect(str(self.box.db))
        try:
            return json.loads(db.execute(
                "SELECT data FROM day_extras WHERE site = ? AND day = ? AND kind = 'bots'",
                ("example.com", DAY.isoformat())).fetchone()[0])
        finally:
            db.close()

    def set_blob(self, blob: dict) -> None:
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE site = ? AND day = ? AND "
                       "kind = 'bots'", (json.dumps(blob), "example.com", DAY.isoformat()))
        db.close()

    def collect(self):
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)

    def audit(self):
        return self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())

    def test_the_real_fetches_count_as_claude_and_the_audit_agrees(self):
        self.collect()
        blob = self.blob()
        ver = blob["verification"]
        self.assertEqual((ver["Claude-User"]["verified"], ver["Claude-User"]["unverified"],
                          ver["Claude-User"]["spoofed"]), (3, 0, 1))
        self.assertEqual((ver["ClaudeBot"]["verified"], ver["ClaudeBot"]["spoofed"]), (1, 1))
        self.assertEqual(ver["Claude-SearchBot"]["spoofed"], 1)
        self.assertEqual(blob["agent_lists"], ["anthropic-outbound"])
        code, out, err = self.audit()
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def test_the_marker_never_reaches_bots_json(self):
        self.collect()
        code, _, err = self.box.run("--today", TODAY, "dashboard")
        self.assertEqual(code, 0, err)
        found = list(self.box.root.rglob("bots.json"))
        self.assertTrue(found)
        for path in found:
            self.assertNotIn("agent_lists", path.read_text())

    def test_a_day_stored_before_is_audited_as_it_was_counted(self):
        # The day as 2.58 counted it: no Claude-User lists, no "agent_lists" in its blob. Once
        # the outbound list is kept, its audit must still match.
        with mock.patch.dict(bot_verify.AGENT_LISTS, clear=True):
            self.collect()
        blob = self.blob()
        self.assertEqual(blob["verification"]["Claude-User"]["spoofed"], 4)
        del blob["agent_lists"]
        self.set_blob(blob)
        code, out, err = self.audit()
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        # The marker is what keeps it so: a day that says it had the lists is held to them.
        blob["agent_lists"] = ["anthropic-outbound"]
        self.set_blob(blob)
        code, out, err = self.audit()
        self.assertEqual(code, 1, err + out)
        self.assertIn("Claude-User", out + err)

    def test_a_day_counted_without_the_outbound_list_audits_too(self):
        lists(self.folder, outbound=False)
        self.collect()
        blob = self.blob()
        self.assertEqual(blob["agent_lists"], [])
        self.assertEqual(blob["verification"]["Claude-User"]["unverified"], 4)
        code, out, err = self.audit()
        self.assertEqual(code, 0, err + out)

    def test_the_live_snapshot_carries_the_marker_and_audits(self):
        stamp = datetime(DAY.year, DAY.month, DAY.day, 23, tzinfo=UTC).timestamp()
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))
        code, _, err = self.box.run("--today", DAY.isoformat(), "live")
        self.assertEqual(code, 0, err)
        snap = json.loads((self.box.root / "live-example.com.json").read_text())
        bots = snap["extras"]["bots"]
        self.assertEqual(bots["agent_lists"], ["anthropic-outbound"])
        self.assertEqual(bots["verification"]["Claude-User"]["verified"], 3)
        code, out, err = self.box.run("--today", DAY.isoformat(), "audit", "--live")
        self.assertEqual(code, 0, err + out)


if __name__ == "__main__":
    unittest.main()

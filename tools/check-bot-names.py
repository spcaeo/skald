#!/usr/bin/env python3
"""Dev-time check of Skald's bot name lists against a corpus of real user agents.

    tools/check-bot-names.py CRAWLERS.txt [DEVICES.txt] [--all]

CRAWLERS.txt holds real crawler and bot user agents, one per line; DEVICES.txt
real browser and device user agents. Crawler-Detect's test fixtures are the
corpus this was written for (tests/data/user_agent/crawlers.txt and
devices.txt in github.com/JayBizzle/Crawler-Detect); download them by hand
into a folder of their own. CLASSIFICATION-PATTERNS.md, "Checking the name lists",
gives the commands.

It prints:

  * every crawler agent classify.py files as PEOPLE: a bot the lists miss;
  * with DEVICES.txt, every device agent it files as anything but PEOPLE:
    a person the lists would count as a bot;
  * a count per group, so a change to the lists shows as a moved figure.

Each agent is classified as one request for "/" with no referrer, from a
documentation address: the name lists alone decide (no `ours` rules, no
address checks, no first-pass session rules). --all also lists the crawler
agents filed under bots, with the name each matched.

This is a tool for whoever edits the lists, never part of a run. Skald does
not read Crawler-Detect, or any other list, at runtime: the name lists in
classify.py are fixed data in the code, so a day recounted next year is
counted by the rules that were in force when it was counted, and the audit
(audit.py) recounts with the very same lists. A missed name found here is
added to classify.py by hand, in its right group, with a test.

Standard library only. Reads the files as data; runs nothing from them.
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skald.classify import Classifier, Group  # noqa: E402
from skald.parse import Hit  # noqa: E402

WHEN = datetime(2026, 1, 1, tzinfo=timezone.utc)
ADDRESS = "192.0.2.1"          # RFC 5737 documentation address


def agents(path: Path) -> list[str]:
    """The distinct non-empty lines of a corpus file, in file order."""
    seen, out = set(), []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            out.append(line)
    return out


def verdict(classify: Classifier, agent: str):
    hit = Hit(when=WHEN, address=ADDRESS, host="", method="GET", url="/",
              status="200", referrer="", user_agent=agent)
    return classify(hit)


def label(v) -> str:
    """group, or group/tier, plus the matched name when there is one."""
    name = v.group.value + (f"/{v.tier.value}" if v.tier else "")
    return f"{name} ({v.engine})" if v.engine else name


def main(argv: list[str]) -> int:
    show_all = "--all" in argv
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    classify = Classifier()

    crawlers = agents(Path(files[0]))
    groups: Counter = Counter()
    missed, filed = [], []
    for agent in crawlers:
        v = verdict(classify, agent)
        groups[v.group.value] += 1
        if v.group is Group.PEOPLE:
            missed.append(agent)
        else:
            filed.append((label(v), agent))
    print(f"crawler agents checked: {len(crawlers)}")
    for group, n in groups.most_common():
        print(f"  {group:16} {n}")
    print(f"\nfiled as people (a bot the lists miss): {len(missed)}")
    for agent in missed:
        print(f"  {agent}")
    if show_all:
        print("\nfiled as not people:")
        for name, agent in sorted(filed):
            print(f"  {name:40} {agent}")

    if len(files) > 1:
        devices = agents(Path(files[1]))
        wrong = []
        for agent in devices:
            v = verdict(classify, agent)
            if v.group is not Group.PEOPLE:
                wrong.append((label(v), agent))
        print(f"\ndevice agents checked: {len(devices)}")
        print(f"filed as not people (a person counted as a bot): {len(wrong)}")
        for name, agent in wrong:
            print(f"  {name:28} {agent}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Self-checks that run before anything is reported.

This module is the reason the package exists in this shape. The report it was
extracted from was correct in its plumbing and wrong in its arithmetic, and it
was wrong for days in front of its only reader:

  * three visitor categories summing to 51,763 under a stated total of 55,539
  * three answer-engine tiers summing to 34,495 under a stated group of 34,357
  * "56 people followed a citation" when it was one person in fifty seconds

None of those needed a clever test. Each needed one subtraction, done once,
by something that would refuse to send if it failed.

So: `check()` returns problems, and the command line exits non-zero when there
are any. Wire it into the send path. A report that cannot add up should not go
out, because the cost of a wrong number is not the number - it is that the
reader stops believing the right ones.
"""
from __future__ import annotations

from dataclasses import dataclass

from .aggregate import Totals
from .classify import Group


@dataclass
class Problem:
    what: str
    detail: str

    def __str__(self) -> str:
        return f"{self.what}: {self.detail}"


def check(totals: Totals) -> list[Problem]:
    """Every arithmetic invariant the cards depend on."""
    problems: list[Problem] = []

    # 1. The groups partition the log. This is the invariant that failed.
    summed = sum(s.hits for s in totals.groups.values())
    if summed != totals.hits:
        problems.append(Problem(
            "groups do not sum",
            f"{summed:,} across {len(totals.groups)} groups against "
            f"{totals.hits:,} parsed - a hit is in two groups or none",
        ))

    # 2. Answer-engine tiers partition that group. The old report added the
    #    citation count (people) into the engine group, and counted probes in
    #    the tiers while excluding them from the group total.
    engines = totals.groups.get(Group.ANSWER_ENGINE)
    if engines:
        tiered = sum(engines.tiers.values())
        if tiered != engines.hits:
            problems.append(Problem(
                "answer-engine tiers do not sum",
                f"{tiered:,} across tiers against {engines.hits:,} in the "
                f"group - off by {tiered - engines.hits:+,}",
            ))

    # 3. Nothing can exceed its own parent.
    for which, stats in totals.groups.items():
        if stats.views > stats.hits:
            problems.append(Problem(
                f"{which.value}: more views than hits",
                f"{stats.views:,} views of {stats.hits:,} hits",
            ))
        if stats.visits > stats.hits:
            problems.append(Problem(
                f"{which.value}: more visits than hits",
                f"{stats.visits:,} visits of {stats.hits:,} hits",
            ))
        if stats.probes > stats.hits:
            problems.append(Problem(
                f"{which.value}: more probes than hits",
                f"{stats.probes:,} probes of {stats.hits:,} hits",
            ))

        if stats.readers is not None and stats.readers > min(stats.visits, stats.views):
            problems.append(Problem(
                f"{which.value}: more readers than visits or page views",
                f"{stats.readers:,} readers against {stats.visits:,} visits and "
                f"{stats.views:,} page views",
            ))

    # 4. A citation is a visit by a person, so it cannot exceed their visits.
    #    This is the check that would have caught "56 people".
    people = totals.groups.get(Group.PEOPLE)
    if people and people.cited_visits > people.visits:
        problems.append(Problem(
            "more citations than visits",
            f"{people.cited_visits:,} cited against {people.visits:,} visits - "
            "citations are being counted per request again",
        ))

    # 5. A parse that yields nothing means the format is wrong, and every
    #    number below would be a confident zero.
    # Only meaningful once something was actually read. A Totals assembled by
    # hand - in a test, or by a caller feeding figures in directly - has no
    # parsed count, and flagging that would report a second problem for every
    # single defect and bury the real one.
    if totals.parsed and totals.hits > totals.parsed:
        problems.append(Problem(
            "more hits than lines read",
            f"{totals.hits:,} counted from {totals.parsed:,} parsed - the host "
            "filter has subtracted the wrong way",
        ))

    # 5. Lines no format could read. A few are normal - truncated writes,
    #    binary junk from scanners. Many mean the format changed under us,
    #    and every figure would be built from whatever still happened to match.
    if totals.lines_read and totals.max_unparsed_share is not None and \
            totals.unparsed / totals.lines_read > totals.max_unparsed_share:
        problems.append(Problem(
            "too many unreadable lines",
            f"{totals.unparsed:,} of {totals.lines_read:,} lines {totals.lines_scope} "
            f"({totals.unparsed / totals.lines_read:.1%}) matched no log format; "
            f"the limit is {totals.max_unparsed_share:.1%}",
        ))

    if totals.unfiltered > totals.hits:
        problems.append(Problem(
            "more unfiltered than counted",
            f"{totals.unfiltered:,} lines without a host against {totals.hits:,} "
            "counted - they are part of the count, so cannot exceed it",
        ))

    problems += _breakdowns(totals)
    from .visits import check as visits_check
    problems += visits_check(totals)
    from .extras import check as extras_check
    problems += extras_check(totals)

    if totals.parsed == 0:
        problems.append(Problem(
            "nothing parsed",
            "no line matched the configured log format; the report would be "
            "all zeroes and would look calm",
        ))

    return problems


def _breakdowns(totals: Totals) -> list[Problem]:
    """Every breakdown adds up to the figure it breaks down.

    Readers by country, browser, system, device, source, referrer, campaign,
    landing page and hour each sum to the readers; each group's requests by
    status sum to its requests; the paths behind a count sum to that count.
    A breakdown is a second count of the same people, so a gap means one of
    them is wrong - and the day is withheld like any other that does not add
    up.
    """
    if not totals.breakdowns:
        return []
    from .aggregate import READER_DIMS
    from .dimensions import SLOW
    problems: list[Problem] = []

    def differs(what: str, got: int, want: int, of: str) -> None:
        if got != want:
            problems.append(Problem(
                f"{what} does not sum",
                f"{got:,} against {want:,} {of} - off by {got - want:+,}"))

    errors = 0
    for which, stats in totals.groups.items():
        differs(f"{which.value}: requests by status", sum(stats.statuses.values()),
                stats.hits, "requests")
        differs(f"{which.value}: form posts by path", sum(stats.post_pages.values()),
                stats.posts, "posts")
        errors += stats.statuses.get("5xx", 0)
    differs("server errors by path", sum(totals.server_errors.values()), errors,
            "5xx responses")

    people = totals.groups.get(Group.PEOPLE)
    if people:
        if people.readers is not None:
            # City only where a city file counted it (logs.city_db).
            for name in READER_DIMS + (("city",) if "city" in people.by else ()):
                differs(f"readers by {name}", sum(people.by.get(name, {}).values()),
                        people.readers, "readers")
        differs("people's page views by speed", sum(people.speeds.values()),
                people.views, "page views")
        differs("slow pages", sum(people.slow_pages.values()),
                sum(people.speeds.get(s, 0) for s in SLOW), "slow page views")
        differs("pages not found", sum(people.not_found.values()),
                people.statuses.get("404", 0), "404s seen by people")
    return problems


def report_or_die(totals: Totals, *, strict: bool = True) -> list[Problem]:
    """Raise when the numbers do not hold, so a bad report cannot be sent."""
    problems = check(totals)
    if problems and strict:
        lines = "\n".join(f"  - {p}" for p in problems)
        raise AssertionError(
            "skald refused to report; the figures do not reconcile:\n"
            + lines
        )
    return problems

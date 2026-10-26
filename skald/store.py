"""Daily history in SQLite: one row per site per local day, aggregates only.

What is kept is exactly what the cards show, and nothing that identifies a
person. No address, no user agent of anyone in the people group, no session
key. Bots are named by the short name their own user agent announces
(aggregate._short_agent), assistants by the token the classifier matched;
people only ever appear as counts, pages they read and the country the
log line recorded. A history file can be copied, backed up or read by
anyone who may see the dashboard without it becoming a log of visitors.

Writing a day is idempotent: collecting the same day twice replaces the
first row, inside one transaction, so a re-run after a fix cannot leave two
versions of a day side by side.

A day whose figures failed verify is still written, with `verified = 0` and
the problems, so the dashboard can say "withheld" instead of drawing a gap
nobody can explain. Its numbers are never read back into a period:
`period()` sums verified days only and lists the rest.

Reading a period rebuilds an ordinary Totals, so the existing renderers and
verify.check run on history unchanged - one set of numbers, one set of
checks, whether they came from a log or from this file.

The schema only ever grows. Opening a file written by older code adds the
columns it lacks (ALTER TABLE ... ADD COLUMN, with a default that is true of
every old row) and stamps the new version, in one transaction, after copying
the file aside. Nothing is ever dropped or rewritten. Code older than the
file refuses to open it rather than misread it.
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import store_extras as sx
from . import store_visits as sv
from .aggregate import READER_DIMS, Totals
from .classify import AI_ASKED, Group, assistant_name
from .search.days import TABLE as SEARCH_DAYS
from .verify import Problem

# 1: the first release (01af148).
# 2: days.unfiltered - lines counted with no host to apply site.hosts to.
# 3: days.scope - NULL for the whole site; for a path view (config.View),
#    the rule it was computed with. A view's rows are filed under the key
#    view_key(site, view), so every query works on a view unchanged.
# 4: days.lines_read, days.unparsed - lines in the files a collect read, and
#    how many no format could parse. NULL for older rows: not recorded.
# 5: groups.readers - visits that read at least one page. NULL for older
#    rows: not recorded, never guessed from visits.
# 6: days.partial_from, days.partial_until - a day the logs did not wholly
#    cover (they began mid-day, or the day was not over). NULL = whole, which
#    is what older code assumed for every day; an older row is not re-judged.
# 7: days.breakdowns - 1 when the day's breakdowns were counted (readers by
#    country, browser, system, device, source, referrer, campaign, landing
#    page and hour; requests by status; posts; 404s; 5xx; response times),
#    in `counts` under the kinds in BREAKDOWN_KINDS. NULL for older rows:
#    not recorded, and a period containing one shows no breakdowns at all
#    rather than a sum of some of its days.
# 8: days.journeys - 1 when the day's visits were counted (visit metrics in
#    `counts` under store_visits.VISIT_KINDS, our own traffic by label under
#    "ours_label"); NULL for older rows. And the `journeys` table: one
#    anonymous row per visit, kept report.journey_days days (store_visits).
# 9: days.extras - 1 when the day's extras were counted (store_extras: hours,
#    our own health, 404s, pages, campaigns, returning visitors), in the
#    `day_extras` table; and `visitor_days`, 30 days of keyed visitor hashes
#    (visitors.py). NULL for older rows.
# 10: the `page_speed` table - Google PageSpeed Insights results per day, page
#    and strategy (pagespeed.py). A table, not a column: older days simply
#    have no rows.
# 11: the `page_milestones` table - each page's first times, kept for good
#    (lifecycle.py): Googlebot, Bingbot, each AI crawler and assistant, the
#    first person, the first from search and from each AI assistant.
# 12: indexes by day on day_extras, visitor_days and journeys (ADDED_INDEXES),
#    for the deletes that keep them to their windows; no row changes.
# 13: (2.4.0) no table change. A file upgraded from 12 or older gets the meta
#    row `privacy_legacy` (ADDED_META): this install predates "keep IPs and
#    emails", so it keeps today's behaviour - no address, no email kept -
#    until someone turns `privacy.keep_ips` / `conversions.identity` on
#    (people/policy.py). A new file has no such row: the owner's default, on.
# 14: the `search_days` table - Search Console and Bing Webmaster Tools
#    figures per day and kind, synced from their APIs (search/days.py). A
#    table, not a column: older days simply have no rows.
SCHEMA_VERSION = 14

# Meta rows an upgrade adds: (version, key, value). Written only when a file
# older than `version` is upgraded, never on a new file.
ADDED_META = [
    (13, "privacy_legacy", "kept off by the upgrade to 2.4.0"),
]

# Tables added after version 1: (version, name, CREATE statement). Created by
# an upgrade (after the backup copy), never by the plain open, so an older
# file is copied aside before it changes.
ADDED_TABLES = [
    (10, "page_speed", """
CREATE TABLE IF NOT EXISTS page_speed (
    site        TEXT NOT NULL,
    day         TEXT NOT NULL,           -- the local day the pages were picked from
    path        TEXT NOT NULL,
    strategy    TEXT NOT NULL,           -- mobile / desktop
    ok          INTEGER NOT NULL,        -- 1: Google answered and it was read
    error       TEXT,
    score       REAL,                    -- lab performance score, 0-100
    lab_json    TEXT,                    -- {"lcp_ms","cls","tbt_ms","fcp_ms","si_ms"}
    field_json  TEXT,                    -- the page's real-user data, or NULL
    origin_json TEXT,                    -- the whole site's real-user data, or NULL
    tested_at   TEXT NOT NULL,           -- UTC, ISO 8601
    PRIMARY KEY (site, day, path, strategy)
)"""),
    (11, "page_milestones", """
CREATE TABLE IF NOT EXISTS page_milestones (
    site TEXT NOT NULL,
    path TEXT NOT NULL,
    kind TEXT NOT NULL,                  -- googlebot, bingbot, ai_training, ai_asked,
                                         -- human, from_search, from_ai
    who  TEXT NOT NULL DEFAULT '',       -- the crawler or assistant ('' for one-only kinds)
    at   TEXT NOT NULL,                  -- the earliest time seen, UTC ISO 8601
    via  TEXT NOT NULL DEFAULT '',       -- from_search: the search site
    PRIMARY KEY (site, path, kind, who)
)"""),
    (14, "search_days", SEARCH_DAYS),
]

# Indexes added after version 1: (version, name, CREATE statement). Made by
# the upgrade, in its transaction, when missing (docs/PERFORMANCE.md).
# Every read keys on (site, day, ...), which the primary keys serve; these
# serve the daily prune ("WHERE day < ?"), which otherwise reads every row.
ADDED_INDEXES = [
    (12, "day_extras_day", "CREATE INDEX IF NOT EXISTS day_extras_day ON day_extras (day, kind)"),
    (12, "visitor_days_day", "CREATE INDEX IF NOT EXISTS visitor_days_day ON visitor_days (day)"),
    (12, "journeys_day", "CREATE INDEX IF NOT EXISTS journeys_day ON journeys (day)"),
]

# Joins a site and a view's slug into the key a view's rows are filed under.
# A config.View slug cannot contain it, and no real site name does.
VIEW_MARK = "::"


def view_key(site: str, view_slug: str | None) -> str:
    return f"{site}{VIEW_MARK}{view_slug}" if view_slug else site

# Every column added after version 1: (version, table, column, definition).
# A column that older code never measured is added as NULL for old rows -
# "not recorded" - never as a default that would claim a value. Order matters only for readability; each is applied if and
# only if the column is missing, so a file stamped with any older version -
# or stamped 1 while already having some of them - comes out the same.
ADDED_COLUMNS = [
    # Older code counted hostless lines without tallying them, so for its
    # rows the number is unknown, not zero. Every new row writes a value.
    (2, "days", "unfiltered", "INTEGER"),
    # Every row before version 3 is a whole-site row, which is what NULL
    # means. Here the default is the truth, not a guess.
    (3, "days", "scope", "TEXT"),
    (4, "days", "lines_read", "INTEGER"),
    (4, "days", "unparsed", "INTEGER"),
    (5, "groups", "readers", "INTEGER"),
    (6, "days", "partial_from", "TEXT"),
    (6, "days", "partial_until", "TEXT"),
    (7, "days", "breakdowns", "INTEGER"),
    (8, "days", "journeys", "INTEGER"),
    (9, "days", "extras", "INTEGER"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS days (
    site         TEXT NOT NULL,
    day          TEXT NOT NULL,          -- local calendar day, YYYY-MM-DD
    timezone     TEXT NOT NULL,          -- the zone that day was cut in
    collected_at TEXT NOT NULL,          -- UTC, ISO 8601
    verified     INTEGER NOT NULL,       -- 1 when verify.check found nothing
    problems     TEXT NOT NULL DEFAULT '',
    parsed       INTEGER NOT NULL,       -- hits in the window, every host
    hits         INTEGER NOT NULL,       -- hits for this site's hosts
    other_hosts  INTEGER NOT NULL,       -- excluded: sibling hosts, bare IP
    unfiltered   INTEGER,                -- counted, no host to filter on; NULL = not recorded (pre-v2 row)
    cited_visits INTEGER NOT NULL,       -- people visits that followed an AI citation
    first_seen   TEXT,
    last_seen    TEXT,
    scope        TEXT,                   -- NULL: whole site; else the view's rule
    lines_read   INTEGER,                -- the day's lines (NULL: pre-v4)
    unparsed     INTEGER,                -- of which no format parsed
    partial_from TEXT,                   -- data starts here, not at midnight
    partial_until TEXT,                  -- the day was not over when collected
    breakdowns   INTEGER,                -- 1: breakdowns counted (NULL: pre-v7)
    journeys     INTEGER,                -- 1: visits counted (NULL: pre-v8)
    extras       INTEGER,                -- 1: day extras counted (NULL: pre-v9)
    PRIMARY KEY (site, day)
);
CREATE TABLE IF NOT EXISTS groups (
    site   TEXT NOT NULL,
    day    TEXT NOT NULL,
    grp    TEXT NOT NULL,                -- classify.Group value
    hits   INTEGER NOT NULL,
    views  INTEGER NOT NULL,
    visits INTEGER NOT NULL,
    probes INTEGER NOT NULL,             -- scanner probes inside this group
    readers INTEGER,                     -- visits with a page view (NULL: pre-v5)
    PRIMARY KEY (site, day, grp)
);
CREATE TABLE IF NOT EXISTS counts (
    site TEXT NOT NULL,
    day  TEXT NOT NULL,
    kind TEXT NOT NULL,                  -- see KINDS
    name TEXT NOT NULL,
    n    INTEGER NOT NULL,
    PRIMARY KEY (site, day, kind, name)
);
CREATE TABLE IF NOT EXISTS journeys (
    site TEXT NOT NULL,
    day  TEXT NOT NULL,
    seq  INTEGER NOT NULL,               -- order of the visit's start that day
    data TEXT NOT NULL,                  -- JSON: labels, pages, times; no visitor
    PRIMARY KEY (site, day, seq)
);
"""

# Every breakdown kept per day. Each is a top list (up to window.HISTORY_TOP)
# except the tiers, which are complete because verify sums them.
KINDS = (
    "people_page",      # pages people read
    "people_country_visits",  # people's visits by country (log's cc= field).
                              # Before this, "people_country" held requests;
                              # those rows stay, and are never read as visits.
    "cited_by",        # which assistant's citation they followed (visits)
    "cited_page",       # pages they landed on from a citation
    "engine_tier",      # answer-engine requests by tier: training / asked
    "engine_training",  # answer engines that fetched to train, by name
    "engine_asked",     # answer engines fetching for a live question, by name
    "engine_page",      # pages answer engines fetched
    "search_engine",    # search crawlers by name
    "search_page",      # pages search crawlers fetched
    "bot_agent",        # monitors, SEO suites, unfurlers - not scanners
    "other_host",       # hosts excluded by site.hosts
)

# Schema 7. Each adds up to the figure it breaks down (verify._breakdowns),
# so a list longer than the history keeps is folded into "(all others)"
# rather than cut. Per group: "status_<group>", "post_page_<group>", and
# "post_total" named by group.
READER_KINDS = {name: f"reader_{name}" for name in READER_DIMS}
# People's visits (readers) by city, from the city file (logs.city_db):
# "Toronto, Ontario, CA", "Unknown" (not recorded) and "(all others)", adding
# up to the readers. Not a READER_DIMS kind: written only on days counted
# with a city file, so a period sums cities only when each of its days has
# them (History._sum), and days from before still add up.
CITY_KIND = "people_city_visits"
BREAKDOWN_KINDS = (
    *READER_KINDS.values(),
    "people_404_page",   # paths people asked for and got a 404
    "people_speed",      # people's page views by response-time bucket
    "people_slow_page",  # pages behind the slow (1 s or more) page views
    "server_error_page", # 5xx responses, every group, by path
    "post_total",        # POST requests per group (name = group)
    *(f"status_{g.value}" for g in Group),
    *(f"post_page_{g.value}" for g in Group),
    CITY_KIND,
)


@dataclass
class Period:
    """A run of days read back from history, and how complete it is."""

    first: date
    last: date
    totals: Totals
    recorded: list[date] = field(default_factory=list)   # verified, summed
    withheld: list[date] = field(default_factory=list)   # failed verify
    missing: list[date] = field(default_factory=list)    # never collected
    # recorded days collected by older code, which did not tally lines with
    # no host: totals.unfiltered leaves them out, so it is a lower bound
    unmeasured: list[date] = field(default_factory=list)
    # recorded days collected before unreadable lines were counted
    unmeasured_lines: list[date] = field(default_factory=list)
    # summed days collected before the breakdowns were counted (schema 7)
    unmeasured_breakdowns: list[date] = field(default_factory=list)
    # how many summed days were collected before visits were counted (schema 8)
    unmeasured_visits: int = 0
    # verified days the logs did not wholly cover: never in `recorded`, so
    # never in a comparison; summed only when a caller asks (the daily mail)
    partial: list[date] = field(default_factory=list)
    partial_from: dict = field(default_factory=dict)    # day -> datetime
    partial_until: dict = field(default_factory=dict)   # day -> datetime

    @property
    def length(self) -> int:
        return (self.last - self.first).days + 1

    @property
    def complete(self) -> bool:
        return len(self.recorded) == self.length


def _local(when, tz_name: str) -> str | None:
    """A partial day's edge, in the day's own zone, so every reader shows the
    reader's time without converting it again."""
    if when is None:
        return None
    try:
        return when.astimezone(ZoneInfo(tz_name)).isoformat()
    except (ValueError, KeyError):
        return when.isoformat()


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


class History:
    """The history file. Open once, use, close (or use as a context manager)."""

    def __init__(self, path: str | Path) -> None:
        path = Path(path)
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA + sx.SCHEMA)
        row = self.db.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        found = int(row[0]) if row else None
        if found is not None and found > SCHEMA_VERSION:
            self.db.close()
            raise RuntimeError(
                f"history file is schema {found}, this code understands "
                f"{SCHEMA_VERSION}; upgrade skald before reading it")
        try:
            self.migrated_from = self._upgrade(found)
        except BaseException:
            self.db.close()
            raise

    def _columns(self, table: str) -> set[str]:
        return {r[1] for r in self.db.execute(f"PRAGMA table_info({table})")}

    def _upgrade(self, found: int | None) -> int | None:
        """Bring an older file up to SCHEMA_VERSION. Returns the old version,
        or None when nothing needed doing.

        A new file was just created by SCHEMA at the current version, so it
        only needs stamping. An old one first gets a copy beside it
        (<file>.schema-v<N>.bak, never overwritten), then every missing
        column, then the new stamp - all or none.
        """
        missing = [(table, column, definition)
                   for _, table, column, definition in ADDED_COLUMNS
                   if column not in self._columns(table)]
        have = {r[0] for r in self.db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        tables = [sql for _, name, sql in ADDED_TABLES if name not in have]
        have = {r[0] for r in self.db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'")}
        indexes = [sql for _, name, sql in ADDED_INDEXES if name not in have]
        meta = [(key, value) for version, key, value in ADDED_META
                if found is not None and found < version]
        if found == SCHEMA_VERSION and not missing and not tables and not indexes:
            return None
        # An index changes no row (and can be dropped again), so an upgrade
        # that only adds indexes needs no copy.
        if (missing or (tables and found is not None)) and str(self.path) != ":memory:":
            backup = self.path.with_name(
                f"{self.path.name}.schema-v{found or 0}.bak")
            if not backup.exists():
                copy = sqlite3.connect(str(backup))
                try:
                    self.db.backup(copy)
                finally:
                    copy.close()
        self.db.execute("BEGIN")
        try:
            for table, column, definition in missing:
                self.db.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            for sql in tables:
                self.db.execute(sql)
            # After the tables: an index may be on one just made.
            for sql in indexes:
                self.db.execute(sql)
            for key, value in meta:
                self.db.execute("INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)",
                                (key, value))
            self.db.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(SCHEMA_VERSION),))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        return found

    @classmethod
    def reader(cls, path: str | Path) -> "History":
        """The file opened read-only, for the helper's compare and page
        answers: no table is created and nothing is upgraded."""
        made = cls.__new__(cls)
        made.path = Path(path)
        made.db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
        made.migrated_from = None
        try:
            row = made.db.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        except sqlite3.OperationalError:
            row = None                    # an empty or partial file: nothing to guard
        if row and int(row[0]) > SCHEMA_VERSION:
            made.db.close()
            raise RuntimeError(
                f"history file is schema {row[0]}, this code understands "
                f"{SCHEMA_VERSION}; upgrade skald before reading it")
        return made

    def prune_extras(self, today: date, days: int, kinds: tuple[str, ...],
                     per_site: dict | None = None, spare=None) -> int:
        """Delete the per-day blobs of `kinds` older than `days` days; a site
        in `per_site` ({site: days}, its own report.retention_days) by its own;
        a site `spare` names (keep_everything) keeps them all."""
        marks = ",".join("?" * len(kinds))
        return sv.prune_sites(self.db, "day_extras", (today - timedelta(days=days)).isoformat(),
                              {s: (today - timedelta(days=n)).isoformat()
                               for s, n in (per_site or {}).items()},
                              f" AND kind IN ({marks})", tuple(kinds), spare=spare)

    def milestones(self, site: str, path: str | None = None) -> list[tuple]:
        """(path, kind, who, at, via) rows, earliest first."""
        if path is None:
            return self.db.execute(
                "SELECT path, kind, who, at, via FROM page_milestones WHERE site = ? "
                "ORDER BY at", (site,)).fetchall()
        return self.db.execute(
            "SELECT path, kind, who, at, via FROM page_milestones WHERE site = ? AND path = ? "
            "ORDER BY at", (site, path)).fetchall()

    def __enter__(self) -> "History":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.db.close()

    @property
    def schema_version(self) -> int:
        return int(self.db.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0])

    # ------------------------------------------------------------------ write

    def record(self, site: str, day: date, totals: Totals, tz_name: str,
               problems: list[Problem], now: datetime | None = None,
               scope: str | None = None) -> None:
        """Write one day, replacing any earlier version of it.

        For a view, `site` is view_key(site, view.slug) and `scope` the
        view's rule in words, kept so a row says what it was computed with.
        """
        key = (site, day.isoformat())
        stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        people = totals.groups.get(Group.PEOPLE)
        rows: list[tuple[str, str, int]] = []

        def add(kind: str, counter) -> None:
            rows.extend((kind, str(name), int(n)) for name, n in counter.items() if n)

        if people:
            add("people_page", people.pages)
            add("people_country_visits", people.countries)
            add("cited_by", people.cited_by)
            add("cited_page", people.cited_pages)
        engines = totals.groups.get(Group.ANSWER_ENGINE)
        if engines:
            add("engine_tier", engines.tiers)
            add("engine_training", Counter(
                {k: v for k, v in engines.engines.items() if not AI_ASKED.fullmatch(k)}))
            add("engine_asked", Counter(
                {k: v for k, v in engines.engines.items() if AI_ASKED.fullmatch(k)}))
            add("engine_page", engines.pages)
        search = totals.groups.get(Group.SEARCH_ENGINE)
        if search:
            add("search_engine", search.engines)
            add("search_page", search.pages)
        bots = totals.groups.get(Group.BOTS)
        if bots:
            add("bot_agent", bots.agents)
        add("other_host", totals.other_host_names)
        breakdowns = 1 if totals.breakdowns else None
        if breakdowns:
            if people:
                for name in READER_DIMS:
                    add(READER_KINDS[name], people.by.get(name, Counter()))
                add("people_404_page", people.not_found)
                add("people_speed", people.speeds)
                add("people_slow_page", people.slow_pages)
                if "city" in people.by:
                    add(CITY_KIND, people.by["city"])
                    if not any(people.by["city"].values()):
                        # Counted with a city file, no reader: one 0 row, so
                        # the day still counts as a day with cities.
                        rows.append((CITY_KIND, "Unknown", 0))
            add("server_error_page", totals.server_errors)
            for g, stats in totals.groups.items():
                add(f"status_{g.value}", stats.statuses)
                add(f"post_page_{g.value}", stats.post_pages)
                if stats.posts:
                    rows.append(("post_total", g.value, stats.posts))
        counted = 1 if totals.visits is not None else None
        rows += sv.count_rows(totals)

        with self.db:
            for table in ("days", "groups", "counts"):
                self.db.execute(f"DELETE FROM {table} WHERE site = ? AND day = ?", key)
            self.db.execute(
                "INSERT INTO days (site, day, timezone, collected_at, verified, "
                "problems, parsed, hits, other_hosts, unfiltered, cited_visits, "
                "first_seen, last_seen, scope, lines_read, unparsed, partial_from, "
                "partial_until, breakdowns, journeys, extras) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*key, tz_name, stamp.isoformat(timespec="seconds"),
                 0 if problems else 1, "\n".join(str(p) for p in problems),
                 totals.parsed, totals.hits, totals.other_hosts, totals.unfiltered,
                 people.cited_visits if people else 0,
                 totals.first.isoformat() if totals.first else None,
                 totals.last.isoformat() if totals.last else None, scope,
                 totals.lines_read, totals.unparsed,
                 _local(totals.partial_from, tz_name), _local(totals.partial_until, tz_name),
                 breakdowns, counted, None))
            sv.write_journeys(self.db, key, totals)
            if sx.write(self.db, site, day, totals):
                self.db.execute("UPDATE days SET extras = 1 WHERE site = ? AND day = ?", key)
            self.db.executemany(
                "INSERT INTO groups (site, day, grp, hits, views, visits, probes, "
                "readers) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(*key, g.value, s.hits, s.views, s.visits, s.probes, s.readers)
                 for g, s in totals.groups.items()])
            self.db.executemany(
                "INSERT INTO counts (site, day, kind, name, n) VALUES (?, ?, ?, ?, ?)",
                [(*key, kind, name, n) for kind, name, n in rows])

    # ------------------------------------------------------------------- read

    def sites(self) -> list[str]:
        """Sites with whole-site rows. View rows are not sites."""
        return [r[0] for r in self.db.execute(
            "SELECT DISTINCT site FROM days WHERE scope IS NULL ORDER BY site")]

    def state(self, site: str, day: date) -> str | None:
        """"ok", "partial", "withheld", or None if never collected."""
        row = self.db.execute(
            "SELECT verified, partial_from, partial_until FROM days "
            "WHERE site = ? AND day = ?", (site, day.isoformat())).fetchone()
        if row is None:
            return None
        if not row[0]:
            return "withheld"
        return "partial" if (row[1] or row[2]) else "ok"

    def status(self, site: str, day: date) -> bool | None:
        """True verified, False withheld, None never collected."""
        row = self.db.execute(
            "SELECT verified FROM days WHERE site = ? AND day = ?",
            (site, day.isoformat())).fetchone()
        return None if row is None else bool(row[0])

    def first_day(self, site: str) -> date | None:
        """The earliest day ever stored for this site: where history starts."""
        row = self.db.execute(
            "SELECT MIN(day) FROM days WHERE site = ?", (site,)).fetchone()
        return date.fromisoformat(row[0]) if row and row[0] else None

    def last_collected(self, site: str) -> str | None:
        row = self.db.execute(
            "SELECT MAX(collected_at) FROM days WHERE site = ?", (site,)).fetchone()
        return row[0] if row else None

    def daily(self, site: str, first: date, last: date) -> list[dict]:
        """One entry per day in the range, recorded or not, oldest first.

        A withheld or missing day carries no figures: charts draw it as an
        absence with a reason, never as zero. Days before history starts are
        "before", which is not a gap and is drawn as nothing.
        """
        start = self.first_day(site)
        rows = {r[0]: r for r in self.db.execute(
            "SELECT day, verified, cited_visits, problems, partial_from, "
            "partial_until FROM days WHERE site = ? AND day BETWEEN ? AND ?",
            (site, first.isoformat(), last.isoformat()))}
        groups: dict[str, dict] = {}
        for day, grp, hits, views, visits, probes, readers in self.db.execute(
                "SELECT day, grp, hits, views, visits, probes, readers FROM groups "
                "WHERE site = ? AND day BETWEEN ? AND ?",
                (site, first.isoformat(), last.isoformat())):
            groups.setdefault(day, {})[grp] = {
                "hits": hits, "views": views, "visits": visits, "probes": probes,
                "readers": readers}
        out = []
        for day in _days(first, last):
            row = rows.get(day.isoformat())
            if row is None:
                state = "before" if start is None or day < start else "missing"
            elif not row[1]:
                state = "withheld"
            else:
                state = "partial" if (row[4] or row[5]) else "ok"
            entry = {"day": day, "state": state}
            if state == "partial":
                entry["partial_from"] = datetime.fromisoformat(row[4]) if row[4] else None
                entry["partial_until"] = datetime.fromisoformat(row[5]) if row[5] else None
            if state in ("ok", "partial"):
                got = groups.get(day.isoformat(), {})
                entry["groups"] = {
                    g: got.get(g.value, {"hits": 0, "views": 0, "visits": 0,
                                         "probes": 0, "readers": 0})
                    for g in Group}
                entry["cited_visits"] = row[2]
            elif state == "withheld":
                entry["problems"] = row[3]
            out.append(entry)
        return out

    def period(self, site: str, first: date, last: date,
               include_partial: bool = False) -> Period:
        """The verified days in [first, last], summed back into one Totals.

        Partial days are listed in `partial` and left out of the sum - so out
        of every KPI and comparison - unless `include_partial`, which only the
        daily mail for that very day uses, saying so in its subject.

        Visits are summed per day, so a session that runs across midnight is
        two visits. Top lists are sums of each day's top 50, so a page that
        never made a day's top 50 is missing from a month's list - the long
        tail undercounts, the head does not.
        """
        period = self._span(first, last, self._states(site, first, last))
        summed = period.recorded + (period.partial if include_partial else [])
        if not summed:
            return period
        days = sorted(d.isoformat() for d in summed)
        marks = ",".join("?" * len(days))
        day_rows = self.db.execute(
            f"SELECT day, parsed, hits, other_hosts, unfiltered, cited_visits, "
            f"first_seen, last_seen, lines_read, unparsed, breakdowns, journeys "
            f"FROM days WHERE site = ? AND day IN ({marks})", (site, *days)).fetchall()
        group_rows = self.db.execute(
            f"SELECT grp, SUM(hits), SUM(views), SUM(visits), SUM(probes), "
            f"SUM(readers), COUNT(readers), COUNT(*) "
            f"FROM groups WHERE site = ? AND day IN ({marks}) GROUP BY grp",
            (site, *days)).fetchall()
        count_rows = self.db.execute(
            f"SELECT kind, name, SUM(n) FROM counts WHERE site = ? "
            f"AND day IN ({marks}) GROUP BY kind, name", (site, *days)).fetchall()
        blobs = sx.read(self.db, site, date.fromisoformat(days[0]),
                        date.fromisoformat(days[-1]), ("returning",))
        city_days = self.db.execute(
            f"SELECT COUNT(DISTINCT day) FROM counts WHERE site = ? AND kind = ? "
            f"AND day IN ({marks})", (site, CITY_KIND, *days)).fetchone()[0]
        return self._sum(period, days, day_rows, group_rows, count_rows, blobs, city_days)

    def periods(self, site: str, first: date, last: date,
                include_partial: bool = False) -> dict[date, Period]:
        """{day: period(site, day, day, include_partial)} for every day in
        [first, last], from four queries instead of five per day. Each day's
        rows go through the same _sum as period(), in the same order (a
        GROUP BY of one day's rows is those rows, ordered by its key), so a
        day comes out exactly as period() makes it."""
        states = self._states(site, first, last)
        out = {d: self._span(d, d, states) for d in _days(first, last)}
        wanted = sorted(d.isoformat() for d, p in out.items()
                        if p.recorded or (include_partial and p.partial))
        if not wanted:
            return out
        marks = ",".join("?" * len(wanted))
        by_day: dict[str, list] = {d: [] for d in wanted}
        groups: dict[str, list] = {d: [] for d in wanted}
        counts: dict[str, list] = {d: [] for d in wanted}
        for row in self.db.execute(
                f"SELECT day, parsed, hits, other_hosts, unfiltered, cited_visits, "
                f"first_seen, last_seen, lines_read, unparsed, breakdowns, journeys "
                f"FROM days WHERE site = ? AND day IN ({marks})", (site, *wanted)):
            by_day[row[0]].append(row)
        for d, grp, hits, views, visits, probes, readers in self.db.execute(
                f"SELECT day, grp, hits, views, visits, probes, readers FROM groups "
                f"WHERE site = ? AND day IN ({marks}) ORDER BY day, grp", (site, *wanted)):
            groups[d].append((grp, hits, views, visits, probes, readers,
                              0 if readers is None else 1, 1))
        for d, kind, name, n in self.db.execute(
                f"SELECT day, kind, name, n FROM counts WHERE site = ? AND day IN ({marks}) "
                f"ORDER BY day, kind, name", (site, *wanted)):
            counts[d].append((kind, name, n))
        blobs = sx.read(self.db, site, date.fromisoformat(wanted[0]),
                        date.fromisoformat(wanted[-1]), ("returning",))
        for d in wanted:
            day = date.fromisoformat(d)
            out[day] = self._sum(out[day], [d], by_day[d], groups[d], counts[d],
                                 {d: blobs[d]} if d in blobs else {},
                                 int(any(row[0] == CITY_KIND for row in counts[d])))
        return out

    def _states(self, site: str, first: date, last: date) -> dict[str, tuple]:
        return {d: (v, pf, pu) for d, v, pf, pu in self.db.execute(
            "SELECT day, verified, partial_from, partial_until FROM days "
            "WHERE site = ? AND day BETWEEN ? AND ?",
            (site, first.isoformat(), last.isoformat()))}

    @staticmethod
    def _span(first: date, last: date, states: dict[str, tuple]) -> Period:
        """The days of [first, last] sorted by state; nothing summed yet."""
        period = Period(first, last, Totals())
        for day in _days(first, last):
            state = states.get(day.isoformat())
            if state is None:
                period.missing.append(day)
            elif not state[0]:
                period.withheld.append(day)
            elif state[1] or state[2]:
                period.partial.append(day)
                if state[1]:
                    period.partial_from[day] = datetime.fromisoformat(state[1])
                if state[2]:
                    period.partial_until[day] = datetime.fromisoformat(state[2])
            else:
                period.recorded.append(day)
        return period

    @staticmethod
    def _sum(period: Period, days: list[str], day_rows, group_rows, count_rows,
             blobs: dict, city_days: int = 0) -> Period:
        """Sum the rows of `days` (ISO, sorted) into period.totals.
        `city_days`: how many of them have people_city_visits rows."""
        totals = period.totals
        # Each day's unreadable share was checked against the configured limit
        # when it was collected, and a day over it is withheld, not here. A
        # sum must not be re-judged against a default it was never set to.
        totals.max_unparsed_share = None
        totals.lines_scope = "in the days collected"
        measured = visited = 0
        for (day, parsed, hits, other, unfiltered, cited, first_seen, last_seen,
             lines_read, unparsed, breakdowns, journeyed) in day_rows:
            visited += 1 if journeyed else 0
            if breakdowns:
                measured += 1
            else:
                period.unmeasured_breakdowns.append(date.fromisoformat(day))
            if lines_read is None:
                period.unmeasured_lines.append(date.fromisoformat(day))
            else:
                totals.lines_read += lines_read
                totals.unparsed += unparsed or 0
            totals.parsed += parsed
            totals.hits += hits
            totals.other_hosts += other
            if unfiltered is None:
                period.unmeasured.append(date.fromisoformat(day))
            else:
                totals.unfiltered += unfiltered
            totals.group(Group.PEOPLE).cited_visits += cited
            for seen in (first_seen, last_seen):
                if seen:
                    when = datetime.fromisoformat(seen)
                    if totals.first is None or when < totals.first:
                        totals.first = when
                    if totals.last is None or when > totals.last:
                        totals.last = when

        for grp, hits, views, visits, probes, readers, known, rows in group_rows:
            stats = totals.group(Group(grp))
            stats.hits, stats.views = hits, views
            stats.visits, stats.probes = visits, probes
            # Readers over a period are known only if every day recorded them.
            stats.readers = readers if known == rows else None

        summed: dict[str, Counter] = {kind: Counter() for kind in KINDS}
        for kind, name, n in count_rows:
            summed.setdefault(kind, Counter())[name] = n

        def ranked(counter: Counter) -> Counter:
            return Counter(dict(counter.most_common()))

        people = totals.group(Group.PEOPLE)
        people.pages = ranked(summed["people_page"])
        people.countries = ranked(summed["people_country_visits"])
        # Older rows may carry an assistant under another name of it.
        cited = Counter()
        for name, n in summed["cited_by"].items():
            cited[assistant_name(name)] += n
        people.cited_by = ranked(cited)
        people.cited_pages = ranked(summed["cited_page"])
        if Group.ANSWER_ENGINE in totals.groups:
            engines = totals.groups[Group.ANSWER_ENGINE]
            engines.tiers = ranked(summed["engine_tier"])
            engines.engines = ranked(summed["engine_training"] + summed["engine_asked"])
            engines.pages = ranked(summed["engine_page"])
        if Group.SEARCH_ENGINE in totals.groups:
            search = totals.groups[Group.SEARCH_ENGINE]
            search.engines = ranked(summed["search_engine"])
            search.pages = ranked(summed["search_page"])
        if Group.BOTS in totals.groups:
            totals.groups[Group.BOTS].agents = ranked(summed["bot_agent"])
        totals.other_host_names = ranked(summed["other_host"])
        # Breakdowns only when every day summed has them: a month's countries
        # from ten of its thirty days, beside thirty days of readers, would
        # be a total that does not add up and a share that is wrong.
        totals.breakdowns = measured == len(days)
        if totals.breakdowns:
            people.by = {name: ranked(summed.get(kind, Counter()))
                         for name, kind in READER_KINDS.items()}
            people.not_found = ranked(summed.get("people_404_page", Counter()))
            people.speeds = ranked(summed.get("people_speed", Counter()))
            people.slow_pages = ranked(summed.get("people_slow_page", Counter()))
            # Cities only when every day summed was counted with a city file.
            if city_days == len(days) and summed.get(CITY_KIND):
                people.by["city"] = ranked(summed[CITY_KIND])
            totals.server_errors = ranked(summed.get("server_error_page", Counter()))
            posts = summed.get("post_total", Counter())
            for g, stats in totals.groups.items():
                stats.statuses = ranked(summed.get(f"status_{g.value}", Counter()))
                stats.post_pages = ranked(summed.get(f"post_page_{g.value}", Counter()))
                stats.posts = posts.get(g.value, 0)
        # Visits only when every day summed counted them (schema 8).
        if visited == len(days):
            totals.visits = sv.period_stats(
                summed, people.readers or 0, people if totals.breakdowns else None)
            totals.ours_labels = Counter(dict(summed.get(sv.OURS_KIND, Counter()).most_common()))
        period.unmeasured_visits = len(days) - visited
        # Returning visitors: summed only when every day has the figure.
        got = [blobs.get(d, {}).get("returning") for d in days]
        if got and all(g is not None for g in got):
            totals.returning = {"readers": sum(g["readers"] for g in got),
                                "returning": sum(g["returning"] for g in got)}
        # A people group that never existed should not appear from nowhere
        # just because cited_visits was added to it above.
        if not people.hits and not people.cited_visits:
            totals.groups.pop(Group.PEOPLE, None)
        return period

    # ----------------------------------------------------- rows, for export

    def day_rows(self, site: str, first: date, last: date) -> list[tuple]:
        """(day, verified, cited_visits, partial) for every stored day."""
        return self.db.execute(
            "SELECT day, verified, cited_visits, "
            "(partial_from IS NOT NULL OR partial_until IS NOT NULL) FROM days "
            "WHERE site = ? AND day BETWEEN ? AND ? ORDER BY day",
            (site, first.isoformat(), last.isoformat())).fetchall()

    def group_rows(self, site: str, days: list[str]) -> list[tuple]:
        """(day, group, hits, views, visits, probes, readers) for these days."""
        if not days:
            return []
        marks = ",".join("?" * len(days))
        return self.db.execute(
            f"SELECT day, grp, hits, views, visits, probes, readers FROM groups "
            f"WHERE site = ? AND day IN ({marks}) ORDER BY day, grp",
            (site, *days)).fetchall()

    def count_rows(self, site: str, kinds: list[str], days: list[str]) -> list[tuple]:
        """(day, kind, name, n) for these kinds and days, largest first per day."""
        if not days or not kinds:
            return []
        dm, km = ",".join("?" * len(days)), ",".join("?" * len(kinds))
        return self.db.execute(
            f"SELECT day, kind, name, n FROM counts WHERE site = ? "
            f"AND day IN ({dm}) AND kind IN ({km}) ORDER BY day, kind, n DESC, name",
            (site, *days, *kinds)).fetchall()

    def engine_tiers(self, site: str, first: date, last: date) -> dict[str, Counter]:
        """Answer engines by name, split by tier, over the verified days."""
        out = {"training": Counter(), "asked": Counter()}
        for kind, name, n in self.db.execute(
                "SELECT c.kind, c.name, SUM(c.n) FROM counts c JOIN days d "
                "ON d.site = c.site AND d.day = c.day AND d.verified = 1 "
                "WHERE c.site = ? AND c.day BETWEEN ? AND ? "
                "AND c.kind IN ('engine_training', 'engine_asked') "
                "GROUP BY c.kind, c.name",
                (site, first.isoformat(), last.isoformat())):
            out[kind.split("_", 1)[1]][name] = n
        return {k: Counter(dict(v.most_common())) for k, v in out.items()}

    def visit_days(self, site: str, first: date, last: date) -> set[str]:
        """Days in the range whose visits were counted (schema 8 on)."""
        return {r[0] for r in self.db.execute(
            "SELECT day FROM days WHERE site = ? AND day BETWEEN ? AND ? "
            "AND journeys = 1", (site, first.isoformat(), last.isoformat()))}

    def journeys(self, site: str, first: date, last: date) -> list[dict]:
        """Stored anonymous journeys in the range, newest first."""
        return sv.journeys(self.db, site, first, last)

    def extras(self, site: str, first: date, last: date, kinds=sx.KINDS) -> dict[str, dict]:
        """{day: {kind: blob}} of the day extras stored in the range."""
        return sx.read(self.db, site, first, last, kinds)

    def prune_visitors(self, today: date, days: int | None = None,
                       per_site: dict | None = None, spare=None) -> int:
        from .visitors import REPEAT_DAYS, prune
        return prune(self.db, today, days or REPEAT_DAYS, per_site, spare)

    def prune_journeys(self, keep_from: date, per_site: dict | None = None,
                       spare=None) -> int:
        """Delete journeys from before `keep_from`, for every site (a site in
        `per_site`, {site: date}, from its own date; one `spare` names: none)."""
        return sv.prune(self.db, keep_from, per_site, spare)

    def breakdown_days(self, site: str, first: date, last: date) -> set[str]:
        """Days in the range whose breakdowns were counted (schema 7 on)."""
        return {r[0] for r in self.db.execute(
            "SELECT day FROM days WHERE site = ? AND day BETWEEN ? AND ? "
            "AND breakdowns = 1", (site, first.isoformat(), last.isoformat()))}

    def withhold(self, site: str, day: date, problems: list[str]) -> bool:
        """Mark a stored day withheld, adding why to its problems. False if
        the day is not stored. Its figures stay for whoever investigates;
        nothing reads them back as a recorded day."""
        key = (site, day.isoformat())
        with self.db:
            row = self.db.execute(
                "SELECT problems FROM days WHERE site = ? AND day = ?", key).fetchone()
            if row is None:
                return False
            text = "\n".join(p for p in [row[0], *problems] if p)
            self.db.execute(
                "UPDATE days SET verified = 0, problems = ? WHERE site = ? AND day = ?",
                (text, *key))
        return True

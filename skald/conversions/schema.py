"""conversions.sqlite's tables and the upgrades from each older schema
(store.py opens the file; split out of it in 2.32). store.py re-exports
every name here, so `store.SCHEMA`, `store.UPGRADES` and the rest still work.

An upgrade that changes a table's CHECK cannot ALTER it: the table is copied
into a new one, every row and column kept (schema 2, and schema 9 for the
stage "refunded"), a copy of the whole file kept first (store._upgrade).
"""
from __future__ import annotations

import hashlib

from . import ALIASES

SCHEMA_VERSION = 10

CONVERSIONS_V2 = """CREATE TABLE IF NOT EXISTS {name} (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, action TEXT NOT NULL,
  stage TEXT NOT NULL CHECK (stage IN ('started', 'completed', 'cancelled',
                                       'rescheduled', 'no_show', 'paid', 'won', 'lost')),
  at TEXT NOT NULL, vid TEXT, external_ref TEXT NOT NULL, tool TEXT NOT NULL,
  source_type TEXT, first_source TEXT, campaign TEXT, landing TEXT, country TEXT,
  device TEXT, first_touch_at TEXT, visits_before INTEGER, identity_id INTEGER
    REFERENCES identities(id) ON DELETE SET NULL,
  received_at TEXT NOT NULL,
  UNIQUE (site, tool, external_ref, stage));
"""
# Schema 4: `test` (1: kept and listed, never counted), added by ALTER to an
# older file, part of the table for a new one.
# Schema 7 (2.18): `label`, the lead hook's optional token (conversions.LABEL;
# NULL: none), added the same way.
CONVERSIONS_V8 = CONVERSIONS_V2.replace(
    "  received_at TEXT NOT NULL,\n",
    "  received_at TEXT NOT NULL, test INTEGER NOT NULL DEFAULT 0, label TEXT,\n")
# Schema 9 (2.32): the stage "refunded" in the CHECK (the table rebuilt), and
# money: `value_minor` (whole minor units of `currency`, ISO 4217), the
# sender's `customer_ref`, `tags` (canonical JSON, NULL: none) and `pay_ref`
# (Stripe's payment intent or invoice, to find the sale a refund is for).
# NULL: not sent, never 0.
CONVERSIONS_V9 = CONVERSIONS_V8.replace(
    "'paid', 'won', 'lost')),", "'paid', 'won', 'lost',\n"
    "                                       'refunded')),").replace(
    "label TEXT,\n",
    "label TEXT,\n  value_minor INTEGER, currency TEXT, customer_ref TEXT, tags TEXT, "
    "pay_ref TEXT,\n")
# Schema 10 (2.45): `filled`, the columns Skald filled from the visitor ID's
# page views (conversions.FILLABLE, comma-joined; NULL: none, every value is
# the sender's), and the ad click the touch's landing address carried
# (`click_kind`, one of conversions.CLICK_KINDS, and `click_id`), kept only
# while the site has `conversions.click_ids` on. Added by ALTER to an older
# file; NULL on every older row.
CONVERSIONS_V10 = CONVERSIONS_V9.replace(
    "pay_ref TEXT,\n", "pay_ref TEXT,\n  filled TEXT, click_kind TEXT, click_id TEXT,\n")
CONVERSIONS = CONVERSIONS_V10
INDEXES = """
CREATE INDEX IF NOT EXISTS conversions_at ON conversions (site, at);
CREATE INDEX IF NOT EXISTS conversions_vid ON conversions (site, vid);
"""
# Schema 7: a hook's rows in the order Skald got them (GET .../leads, reconcile.py).
RECEIVED_INDEX = ("CREATE INDEX IF NOT EXISTS conversions_received ON conversions "
                  "(site, tool, received_at, id)")
# Schema 9: a customer's sales (renewals, lifetime value) and the sale a refund
# is for. Made after the upgrade (store.connect): an older table has no such column.
MONEY_INDEXES = """
CREATE INDEX IF NOT EXISTS conversions_customer ON conversions (site, customer_ref);
CREATE INDEX IF NOT EXISTS conversions_pay ON conversions (site, tool, pay_ref);
"""

# Schema 9 (2.32): a refund's parts and Stripe's payment links.
# refund_parts: each rise of a refunded row's total (its first amount, then
#   each larger total's difference) with the time it arrived, so each part
#   counts on its own day (conversions_revenue.py); value_minor NULL: a whole
#   refund sent before its sale, its value filled in when the sale comes. The
#   parts of a row add up to its value_minor. Gone with their row (CASCADE).
# pay_links: Stripe's invoice_payment.paid (API 2025-03-31 "basil" took the
#   payment intent off the Invoice and the invoice off the Charge): which
#   payment intent paid which invoice, so a renewal's refund finds its sale.
MONEY_TABLES = """CREATE TABLE IF NOT EXISTS refund_parts (
  id INTEGER PRIMARY KEY, conversion_id INTEGER NOT NULL
    REFERENCES conversions(id) ON DELETE CASCADE,
  at TEXT NOT NULL, value_minor INTEGER, received_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS refund_parts_row ON refund_parts (conversion_id);
CREATE TABLE IF NOT EXISTS pay_links (
  site TEXT NOT NULL, tool TEXT NOT NULL, invoice TEXT NOT NULL, payment TEXT NOT NULL,
  received_at TEXT NOT NULL, PRIMARY KEY (site, tool, invoice, payment));
CREATE INDEX IF NOT EXISTS pay_links_payment ON pay_links (site, tool, payment);
"""

# Schema 4 (2.4.0): each reader's visit with its address and user agent
# (people/visits.py; written only while the site keeps them), the days
# written, and the rows a sync removed, kept whole.
PEOPLE_TABLES = """CREATE TABLE IF NOT EXISTS visits (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, day TEXT NOT NULL, seq INTEGER NOT NULL,
  ip TEXT NOT NULL, user_agent TEXT, start TEXT NOT NULL, end TEXT NOT NULL,
  source TEXT, via TEXT, referrer TEXT, campaign TEXT, landing TEXT, exit TEXT,
  country TEXT, device TEXT, browser TEXT, os TEXT, pages INTEGER NOT NULL,
  seconds INTEGER, trail TEXT NOT NULL, posts TEXT, city TEXT, UNIQUE (site, day, seq));
CREATE INDEX IF NOT EXISTS visits_ip ON visits (site, ip, start);
CREATE INDEX IF NOT EXISTS visits_day ON visits (day);
CREATE TABLE IF NOT EXISTS visit_days (
  site TEXT NOT NULL, day TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('whole', 'today')),
  visits INTEGER NOT NULL, pages INTEGER NOT NULL, written_at TEXT NOT NULL,
  PRIMARY KEY (site, day));
CREATE TABLE IF NOT EXISTS removed (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, removed_at TEXT NOT NULL, why TEXT NOT NULL,
  conversion_id INTEGER, tool TEXT, external_ref TEXT, vid TEXT, action TEXT, stage TEXT,
  at TEXT, row TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS removed_site ON removed (site, removed_at);
CREATE INDEX IF NOT EXISTS removed_ref ON removed (site, external_ref);
"""

# Schema 8 (2.21): the addresses behind Security's suspect rows (security_kept.py;
# written only while the site keeps addresses): one row per (day, seq) of the
# day kind `security`'s `who` list, and the days written.
SECURITY_TABLES = """CREATE TABLE IF NOT EXISTS security_rows (
  site TEXT NOT NULL, day TEXT NOT NULL, seq INTEGER NOT NULL, ip TEXT NOT NULL,
  user_agent TEXT, PRIMARY KEY (site, day, seq));
CREATE INDEX IF NOT EXISTS security_rows_ip ON security_rows (ip);
CREATE TABLE IF NOT EXISTS security_days (
  site TEXT NOT NULL, day TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('whole', 'today')),
  rows INTEGER NOT NULL, written_at TEXT NOT NULL, PRIMARY KEY (site, day));
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
""" + CONVERSIONS.format(name="conversions") + INDEXES + RECEIVED_INDEX + """;
CREATE TABLE IF NOT EXISTS journeys (
  vid TEXT NOT NULL, site TEXT NOT NULL, at TEXT NOT NULL, path TEXT NOT NULL,
  source_type TEXT, via TEXT, campaign TEXT, click_kind TEXT, click_id TEXT);
CREATE INDEX IF NOT EXISTS journeys_vid ON journeys (site, vid, at);
CREATE INDEX IF NOT EXISTS journeys_at ON journeys (at);
CREATE INDEX IF NOT EXISTS journeys_site_at ON journeys (site, at);
CREATE TABLE IF NOT EXISTS identities (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, email_hash TEXT NOT NULL,
  email TEXT, name TEXT, created_at TEXT NOT NULL, UNIQUE (site, email_hash));
CREATE TABLE IF NOT EXISTS deliveries (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, tool TEXT NOT NULL,
  received_at TEXT NOT NULL, outcome TEXT NOT NULL, http_status INTEGER NOT NULL,
  error TEXT, external_ref TEXT);
CREATE INDEX IF NOT EXISTS deliveries_tool ON deliveries (site, tool, id);
CREATE TABLE IF NOT EXISTS webhooks (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, url TEXT NOT NULL, events TEXT NOT NULL,
  created_at TEXT NOT NULL, created_by TEXT, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY, webhook_id INTEGER NOT NULL
    REFERENCES webhooks(id) ON DELETE CASCADE,
  site TEXT NOT NULL, event TEXT NOT NULL, ref TEXT NOT NULL, body TEXT NOT NULL,
  created_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_at TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'sent', 'failed')),
  http_status INTEGER, error TEXT, sent_at TEXT, UNIQUE (webhook_id, event, ref));
CREATE INDEX IF NOT EXISTS outbox_due ON outbox (state, next_at);
CREATE TABLE IF NOT EXISTS hook_replays (
  site TEXT NOT NULL, digest TEXT NOT NULL, received_at TEXT NOT NULL,
  PRIMARY KEY (site, digest));
""" + PEOPLE_TABLES + SECURITY_TABLES + MONEY_TABLES

# Schema 2 (Phase 4b step 3): the stages "won" and "lost" (a CHECK cannot be
# changed in place, so the table is copied into a new one), one name per
# action (ALIASES; Stripe's unpaid checkout is a payment started, HubSpot's
# deal won is "won"), and the outgoing webhooks' tables (made by SCHEMA).
_V2_COLUMNS = ("id, site, action, stage, at, vid, external_ref, tool, source_type, "
               "first_source, campaign, landing, country, device, first_touch_at, "
               "visits_before, identity_id, received_at")
_V8_COLUMNS = _V2_COLUMNS + ", test, label"
UPGRADES: dict[int, list[str]] = {2: [
    CONVERSIONS_V2.format(name="conversions_v2"),
    f"INSERT INTO conversions_v2 ({_V2_COLUMNS}) SELECT {_V2_COLUMNS} FROM conversions",
    "DROP TABLE conversions",
    "ALTER TABLE conversions_v2 RENAME TO conversions",
    "UPDATE conversions SET stage = 'started' WHERE tool = 'stripe' AND action = 'checkout' "
    "AND stage = 'completed'",
    "UPDATE conversions SET stage = 'won' WHERE tool = 'hubspot' AND action = 'deal' "
    "AND stage = 'paid'",
    *(f"UPDATE conversions SET action = '{new}' WHERE action = '{old}'"
      for old, new in ALIASES.items()),
    *INDEXES.strip().splitlines(),
],
    # 3: a site's journeys by time (pages before converting, the audit's
    # recount): a range in one site, not every journey of the site.
    3: ["CREATE INDEX IF NOT EXISTS journeys_site_at ON journeys (site, at)"],
    # 4: the test mark, the people's visits, the removed rows (PEOPLE_TABLES).
    4: ["ALTER TABLE conversions ADD COLUMN test INTEGER NOT NULL DEFAULT 0",
        *[sql.strip() + ";" for sql in PEOPLE_TABLES.split(";\n") if sql.strip()]],
    # 5: each kept visit's city, when a city file named one (logs.city_db).
    5: ["ALTER TABLE visits ADD COLUMN city TEXT"],
    # 6: the page view's referring host (the beacon's `r`; "" none, NULL a
    # row from before): a visitor ID's first touch (firsttouch.py).
    6: ["ALTER TABLE journeys ADD COLUMN via TEXT"],
    # 7 (2.18): a lead's label (NULL for every older row: none was sent), and
    # a hook's rows in the order received (GET /traffic-hooks/<site>/leads).
    7: ["ALTER TABLE conversions ADD COLUMN label TEXT", RECEIVED_INDEX],
    # 8 (2.21): the addresses behind Security's suspect rows (SECURITY_TABLES).
    8: [sql.strip() + ";" for sql in SECURITY_TABLES.split(";\n") if sql.strip()],
    # 9 (2.32): the stage "refunded" (a CHECK: the table is copied whole into a
    # new one, every row with its id, test, label and identity_id) and the
    # money columns, NULL on every older row (no money was sent).
    9: [CONVERSIONS_V9.format(name="conversions_v9"),
        f"INSERT INTO conversions_v9 ({_V8_COLUMNS}) SELECT {_V8_COLUMNS} FROM conversions",
        "DROP TABLE conversions",
        "ALTER TABLE conversions_v9 RENAME TO conversions",
        *INDEXES.strip().splitlines(), RECEIVED_INDEX],
    # 10 (2.45): what Skald filled of a lead's touches, and the ad click on a
    # conversion and on a page view (its campaign too: the script tag's
    # utm_ tags; NULL on a page view from before).
    10: ["ALTER TABLE conversions ADD COLUMN filled TEXT",
         "ALTER TABLE conversions ADD COLUMN click_kind TEXT",
         "ALTER TABLE conversions ADD COLUMN click_id TEXT",
         "ALTER TABLE journeys ADD COLUMN campaign TEXT",
         "ALTER TABLE journeys ADD COLUMN click_kind TEXT",
         "ALTER TABLE journeys ADD COLUMN click_id TEXT"]}

# The SCHEMA this code set a file up with (see accounts/db.py): a file
# stamped with it at SCHEMA_VERSION skips the script on connect.
SCHEMA_STAMP = hashlib.sha256(SCHEMA.encode()).hexdigest()[:16]

COLUMNS = ("action", "stage", "at", "vid", "external_ref", "tool", "source_type",
           "first_source", "campaign", "landing", "country", "device", "first_touch_at",
           "visits_before", "label", "value_minor", "currency", "customer_ref", "tags",
           "pay_ref", "filled", "click_kind", "click_id")

"""Settings people change from the dashboard, merged with config.yml.

config.yml stays the source for the install (paths, ports, folders). The
`settings` table in accounts.sqlite holds what people change from the
Settings pages (docs/SETTINGS.md). One value is read as:

    the site's row  >  its organisation's row  >  the install's row
                    >  config.yml  >  the default below

A key named in config.yml's `settings.locked` list ignores every row: the
page shows it read-only, with the reason. Every editable key is in SCHEMA,
with its check, who may change it and where it is saved:

    scope "site:<name>"  a site's page (retention, mail recipients, hosts, goals,
                         page assets)
          "org:<id>"     the organisation (security)
          "install"      the whole install (SMTP, backups, the PageSpeed key)

Every change writes an audit row: the key, the old and the new value; for a
secret only "set" or "cleared", never the value. Secrets (the SMTP password,
the PageSpeed key) never go into the table: they go to secrets.json beside
the history (conversions/secrets_store.py: 0600, written atomically), and
an environment variable of the same name wins, so /etc/skald/env
keeps working. No API answer carries a secret: only {"set": true}.

The daily run, `live`, the mails, backups, beacon pruning and the visitor
window read the merged view: cli.Context lays it over its config once
(`apply`), so code that reads `setting(config, "report", "retention_days")`
reads the merged value. With no accounts file, or no rows, `apply` changes
nothing.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .beacon import EVENTS, PAGE_VIEW
from .config import setting
from .rendering import ASSET_PREFIXES
from .site_logos import COLORS as LOGO_COLORS, SOURCES as LOGO_SOURCES

LOCK_WORDS = "Locked in config.yml (settings.locked) by whoever runs the server."
WHO_WORDS = {
    "admin": "Only an admin or an owner can change this.",
    "install": "Only an install admin can change this: it applies to every site of the install.",
    "owner": "Only an owner can change this.",
}
SMTP_PASSWORD_ENV = "SKALD_SMTP_PASSWORD"
HOST = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?"
                  r"(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)*(?::\d{1,5})?$")
COLOR = re.compile(r"^#[0-9a-f]{6}$")
ZONE = re.compile(r"^[A-Za-z0-9_+\-/]{1,64}$")
FILENAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,99}$")
NAME = re.compile(r"^[A-Za-z0-9 .'-]{1,40}$")      # mail.from_name (mailer.display_name)
GOAL_EVENTS = EVENTS + (PAGE_VIEW,)                 # what beacon.goals may name
MAX_GOALS = 10
MAX_PREFIXES = 10                                   # site.asset_prefixes


class Invalid(ValueError):
    """A value the key does not take, in plain words."""


@dataclass(frozen=True)
class Key:
    kind: str                       # int bool email emails text choice host hosts views zone
    #                                 path filename secret events prefixes searchprop bingsite
    #                                 ipmode
    who: str                        # admin, install or owner
    scopes: tuple                   # where it may be saved; the first is where the page saves
    config: tuple | None            # (section, key) in config.yml
    default: object = None
    lo: int | None = None
    hi: int | None = None
    choices: tuple = ()
    limit: int = 0
    shrink: bool = False            # a smaller value removes stored data (preview, typed name)
    env: str = ""                   # a secret's name: environment variable and secrets.json key
    label: str = ""
    extra: dict = field(default_factory=dict)


SITE_UP = ("site", "org", "install")
SCHEMA: dict[str, Key] = {
    "report.retention_days": Key("int", "admin", SITE_UP, ("report", "retention_days"), 400,
                                 30, 3650, shrink=True, label="Detail days"),
    "report.journey_days": Key("int", "admin", SITE_UP, ("report", "journey_days"), 7, 1, 90,
                               shrink=True, label="Journeys"),
    "visitors.repeat_days": Key("int", "admin", SITE_UP, ("visitors", "repeat_days"), 30, 1, 90,
                                shrink=True, label="Returning-visitor matching"),
    "beacon.keep_days": Key("int", "admin", SITE_UP, ("beacon", "keep_days"), 400, 30, 3650,
                            shrink=True, label="In-page events"),
    # 2.4.0: what is kept about people (people/policy.py). On an install
    # upgraded to 2.4.0 an unset keep_ips / identity reads as off ("upgrade").
    # 2.15.0: keep_ips is full, short or off; a row or config.yml that says
    # true or false still reads as full or off (policy.mode_of).
    "privacy.keep_ips": Key("ipmode", "admin", SITE_UP, ("privacy", "keep_ips"), "full",
                            choices=("full", "short", "off"),
                            label="Keep visitors' IP addresses"),
    "privacy.keep_days": Key("int", "admin", SITE_UP, ("privacy", "keep_days"), 395, 1, 3650,
                             shrink=True, label="Visits with addresses"),
    "conversions.identity": Key("choice", "admin", SITE_UP, ("conversions", "identity"), "full",
                                choices=("full", "anonymous"),
                                label="Leads' names and emails"),
    "beacon.goals": Key("events", "admin", ("site",), ("beacon", "goals"), [], label="Goals"),
    # 2.9.0: per site. The script tag keeps an anonymous visitor ID in the
    # browser, for journeys and lead matching (docs/BEACON.md); the site's
    # privacy notice must say so, and its consent banner gates the tag.
    "beacon.visitor_ids": Key("bool", "admin", ("site",), ("beacon", "visitor_ids"), False,
                              label="Visitor IDs (script tag)"),
    # Per site: a visit counts as people only when its browser fetched one of
    # the page's own assets (rendering.py; its recount audit_rendered.py reads
    # the same config["site"] keys, which `apply` writes). A dashboard site
    # takes nothing of the first site's site: section (multisite.tenant_base),
    # so a WordPress or static site sets its own folders here.
    "site.asset_prefixes": Key("prefixes", "admin", ("site",), ("site", "asset_prefixes"),
                               list(ASSET_PREFIXES), limit=MAX_PREFIXES,
                               label="Page asset paths"),
    "site.require_rendering": Key("bool", "admin", ("site",), ("site", "require_rendering"),
                                  True, label="Count a visit only when its page drew"),
    "backup.daily": Key("int", "install", ("install",), ("backup", "daily"), 14, 1, 60,
                        shrink=True, label="Daily backup copies"),
    "backup.weekly": Key("int", "install", ("install",), ("backup", "weekly"), 8, 0, 52,
                         shrink=True, label="Weekly backup copies"),
    "mail.daily": Key("bool", "admin", SITE_UP, ("mail", "daily"), True, label="Daily mail"),
    "mail.weekly": Key("bool", "admin", SITE_UP, ("mail", "weekly"), True, label="Weekly mail"),
    "mail.to": Key("emails", "admin", ("site", "org"), ("mail", "to"), [], label="Recipients"),
    "mail.from_name": Key("text", "admin", SITE_UP, ("mail", "from_name"), None, limit=40,
                          label="From name"),
    "mail.smtp.host": Key("host", "install", ("install",), ("mail", "host"), None,
                          label="SMTP server"),
    "mail.smtp.port": Key("int", "install", ("install",), ("mail", "port"), 587, 1, 65535,
                          label="SMTP port"),
    "mail.smtp.security": Key("choice", "install", ("install",), ("mail", "security"), None,
                              choices=("starttls", "ssl", "none"), label="SMTP security"),
    "mail.smtp.user": Key("text", "install", ("install",), ("mail", "user"), None, limit=254,
                          label="SMTP user"),
    "mail.from": Key("email", "install", ("install",), ("mail", "from"), None,
                     label="Sender address"),
    "mail.smtp.password": Key("secret", "install", ("install",), None, env=SMTP_PASSWORD_ENV,
                              label="SMTP password"),
    "pagespeed.api_key": Key("secret", "install", ("install",), None, env="PSI_API_KEY",
                             label="PageSpeed API key"),
    # P1-6: search figures (search/). The property and Bing site are per site
    # (checked against the site's hosts, search/props.py); the Bing key is the
    # install's. The Search Console key file is uploaded through
    # Settings > Integrations > Search (search/api.py), never through here.
    "search.google_property": Key("searchprop", "admin", ("site",),
                                  ("search_console", "property"), None,
                                  label="Search Console property"),
    "search.bing_site": Key("bingsite", "admin", ("site",), ("bing", "site_url"), None,
                            label="Bing Webmaster Tools site"),
    "search.bing_api_key": Key("secret", "install", ("install",), None,
                               env="BING_WEBMASTER_API_KEY", label="Bing API key"),
    # AI answers (answers/): each assistant's API key, install level.
    **{f"ai_answers.{p}_key": Key("secret", "install", ("install",), None,
                                  env=f"SKALD_{p.upper()}_API_KEY", label=label)
       for p, label in (("openai", "OpenAI API key (ChatGPT answers)"),
                        ("perplexity", "Perplexity API key"),
                        ("gemini", "Google Gemini API key"),
                        ("anthropic", "Anthropic API key (Claude answers)"))},
    "sites.hosts": Key("hosts", "admin", ("site",), ("site", "hosts"), [], label="Host names"),
    "sites.views": Key("views", "admin", ("site",), ("dashboard", "views"), [], label="Views"),
    "sites.timezone": Key("zone", "admin", ("site",), ("report", "timezone"), "UTC",
                          label="Time zone"),
    "sites.log_dir": Key("path", "install", ("site",), ("logs", "dir"), None, limit=300,
                         label="Log folder"),
    "sites.log_base": Key("filename", "install", ("site",), ("logs", "base"), None,
                          label="Log file name"),
    # 2.6.0: the site's logo (site_logos.py): from the site, uploaded, or a
    # letter on one of four colours (also the fallback while there is none).
    "site.logo.source": Key("choice", "admin", ("site",), ("site", "logo_source"), "auto",
                            choices=LOGO_SOURCES, label="Logo"),
    "site.logo.color": Key("choice", "admin", ("site",), ("site", "logo_color"), None,
                           choices=LOGO_COLORS, label="Letter colour"),
    # Settings > Integrations: the booking tools' event types this site keeps
    # (conversions/event_types.py); [] keeps every event.
    "hooks.calendly.event_types": Key("eventtypes", "admin", ("site",),
                                      ("hooks", "calendly_event_types"), [],
                                      label="Calendly event types"),
    "hooks.calcom.event_types": Key("eventtypes", "admin", ("site",),
                                    ("hooks", "calcom_event_types"), [],
                                    label="Cal.com event types"),
    # Settings > Reports (client_reports.py): the agency's name and colour on
    # every client report of the organisation; its logo is a file (logos/org-<id>/).
    "brand.agency_name": Key("text", "admin", ("org",), None, None, limit=60,
                             label="Agency name"),
    "brand.color": Key("color", "admin", ("org",), None, None, label="Brand colour"),
    "security.require_totp": Key("bool", "owner", ("org",), None, False,
                                 label="Require two-step sign-in"),
    "security.session_days": Key("int", "owner", ("org",), None, 14, 1, 90,
                                 label="Session length"),
}
# Site > Alerts (2.13.0): the master switch, mailing, and each rule's switch, by
# their names in config.yml's `alerts` section (alerts.py; alerts_ai.py, whose
# flat `ai_<rule>` names win over the nested `alerts.ai`; alerts_history.py).
# Thresholds stay in config.yml.
ALERT_RULES = {"site_down": "Site down", "logging_stopped": "Logging stopped",
               "server_errors": "Server errors", "not_found_surge": "Broken-link surge",
               "crawler_burst": "Crawl burst", "new_crawler": "New crawler",
               "traffic_drop": "Traffic drop", "ai_started_reading": "AI started reading",
               "ai_stopped_reading": "AI stopped reading",
               "ai_sending_people": "AI sending people",
               "first_citation": "First AI citation",
               "first_cited_page": "Page's first AI citation",
               "cited_visits": "Visits from AI answers", "crawler_silent": "Crawler gone silent"}
SCHEMA["alerts.enabled"] = Key("bool", "admin", ("site",), ("alerts", "enabled"), False,
                               label="Alerts")
SCHEMA["alerts.mail"] = Key("bool", "admin", ("site",), ("alerts", "mail"), True,
                            label="Mail alerts")
for _rule, _label in ALERT_RULES.items():
    SCHEMA[f"alerts.{_rule}"] = Key("bool", "admin", ("site",), ("alerts", _rule), True,
                                    label=f"Alert: {_label}")

# Keys that are not secrets, in SCHEMA order.
PLAIN = tuple(k for k, v in SCHEMA.items() if v.kind != "secret")
SECRETS = tuple(k for k, v in SCHEMA.items() if v.kind == "secret")


# ------------------------------------------------------------ validation

def _int(value, key: Key, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise Invalid(f"{key.label or name} is a whole number.")
    try:
        n = int(str(value).strip())
    except ValueError:
        raise Invalid(f"{key.label or name} is a whole number.") from None
    if (key.lo is not None and n < key.lo) or (key.hi is not None and n > key.hi):
        raise Invalid(f"{key.label or name} is from {key.lo} to {key.hi}.")
    return n


def _clean_text(value, name: str, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise Invalid(f"{name} is text.")
    text = " ".join(value.split())
    if any(ord(c) < 0x20 or ord(c) == 0x7f for c in value if c not in " \t"):
        raise Invalid(f"{name} cannot hold control characters.")
    if len(text) > limit:
        raise Invalid(f"{name} is at most {limit} characters.")
    return text or None


def _views(value) -> list[dict]:
    from .config import views
    if not isinstance(value, list) or len(value) > 20:
        raise Invalid("Views are a list of at most 20.")
    out = []
    for item in value:
        if not isinstance(item, dict):
            raise Invalid("Each view has a name and path prefixes.")
        name = _clean_text(item.get("name"), "A view's name", 60)
        if not name:
            raise Invalid("Each view needs a name.")
        prefix = str(item.get("path_prefix") or "").strip()
        exclude = item.get("exclude_prefix") or ""
        if isinstance(exclude, list):
            exclude = " ".join(str(x) for x in exclude)
        exclude = " ".join(str(exclude).split())
        for p in [prefix, *exclude.split()]:
            if p and (not p.startswith("/") or len(p) > 200 or ".." in p
                      or any(ord(c) <= 0x20 or ord(c) == 0x7f for c in p)):
                raise Invalid(f"A path prefix starts with / and has no spaces: {p[:40]!r}.")
        view = {"name": name}
        if prefix:
            view["path_prefix"] = prefix
        if exclude:
            view["exclude_prefix"] = exclude
        out.append(view)
    try:
        views({"dashboard": {"views": out}})
    except ValueError as why:
        raise Invalid(str(why)) from None
    return out


def _goals(value) -> list[str]:
    """beacon.goals: event names the beacon takes (beacon.EVENTS, page_view),
    each once, at most MAX_GOALS; [] means no goal, on purpose."""
    items = value.replace(",", " ").split() if isinstance(value, str) else value
    if not isinstance(items, list):
        raise Invalid("Goals are a list of event names.")
    out = []
    for item in items:
        if not isinstance(item, str) or item.strip() not in GOAL_EVENTS:
            raise Invalid(f"Not an event the beacon counts: {str(item)[:40]!r}.")
        if item.strip() not in out:
            out.append(item.strip())
    if len(out) > MAX_GOALS:
        raise Invalid(f"At most {MAX_GOALS} goals.")
    return out


def _prefixes(value, key: Key) -> list[str]:
    """site.asset_prefixes: 1 to MAX_PREFIXES path prefixes, each starting
    with / and naming a folder or file (a bare / would match every page)."""
    items = value.replace(",", " ").split() if isinstance(value, str) else value
    if not isinstance(items, list):
        raise Invalid(f"{key.label} are a list of path prefixes.")
    out = []
    for item in items:
        p = str(item).strip() if isinstance(item, str) else ""
        if (not p.startswith("/") or len(p) > 100 or ".." in p
                or any(ord(c) <= 0x20 or ord(c) == 0x7f for c in p)):
            raise Invalid(f"A path prefix starts with / and has no spaces: {str(item)[:40]!r}.")
        if p == "/":
            raise Invalid("A prefix of / alone matches every page. To count every visit, "
                          "turn the rendering rule off instead.")
        if p not in out:
            out.append(p)
    if not out or len(out) > key.limit:
        raise Invalid(f"Give from 1 to {key.limit} path prefixes.")
    return out


def capped(name: str, cap: int | None) -> int | None:
    """The most a retention key may hold under a plan's `cap` (saas/limits.py),
    never below the key's own floor; None when no cap applies to `name`."""
    key = SCHEMA.get(name)
    if cap is None or key is None or name not in SHRINKING:
        return None
    return max(int(cap), key.lo or 0)


def validate(name: str, value, cap: int | None = None):
    """The value as stored, or Invalid. None (or "" for text) clears the row.
    `cap`: the plan's retention_days_max, for the retention keys (SHRINKING)."""
    key = SCHEMA.get(name)
    if key is None:
        raise Invalid(f"{name!r} is not a setting that can be changed here.")
    if value is None:
        return None
    kind, label = key.kind, key.label or name
    if kind == "int":
        got = _int(value, key, name)
        most = capped(name, cap)
        if most is not None and got > most:
            raise Invalid(f"{label} is at most {most} days on this organisation's plan.")
        return got
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise Invalid(f"{label} is on or off.")
    if kind == "email":
        from .accounts.users import clean_email
        try:
            return clean_email(value)
        except (ValueError, TypeError):
            raise Invalid(f"{label} is one email address, and nothing else.") from None
    if kind == "emails":
        from .accounts.users import clean_email
        items = value if isinstance(value, list) else str(value).replace(",", " ").split()
        out = []
        for item in items:
            try:
                email = clean_email(item)
            except ValueError:
                raise Invalid(f"Not an email address: {str(item)[:60]!r}.") from None
            if email not in out:
                out.append(email)
        if not out:
            raise Invalid("Give at least one recipient. To stop the mails, turn them off.")
        if len(out) > 20:
            raise Invalid("At most 20 recipients.")
        return out
    if kind in ("text", "secret"):
        if kind == "secret":
            if not isinstance(value, str) or "\n" in value or "\r" in value or len(value) > 500:
                raise Invalid(f"{label} is one line of at most 500 characters.")
            return value or None
        got = _clean_text(value, label, key.limit)
        if name == "mail.from_name" and got and not NAME.match(got):
            raise Invalid(f"{label} is at most {key.limit} letters, digits, spaces and . - '.")
        return got
    if kind == "color":
        got = str(value or "").strip().lower()
        if not got:
            return None
        if not COLOR.match(got):
            raise Invalid(f"{label} is a colour like #1d4ed8.")
        return got
    if kind == "ipmode":
        from .people.policy import mode_of
        got = mode_of(value)
        if got is None:
            raise Invalid(f"{label} is one of: {', '.join(key.choices)}.")
        return got
    if kind == "choice":
        if value not in key.choices:
            raise Invalid(f"{label} is one of: {', '.join(key.choices)}.")
        return value
    if kind in ("searchprop", "bingsite"):
        if value in (None, ""):
            return None
        from .search import props
        try:
            return props.google_property(value) if kind == "searchprop" else props.bing_site(value)
        except props.Invalid as why:
            raise Invalid(str(why)) from None
    if kind == "host":
        host = str(value).strip().lower()
        if not HOST.match(host):
            raise Invalid(f"{label} is a host name: letters, digits, dots and dashes.")
        return host
    if kind == "hosts":
        items = value if isinstance(value, list) else str(value).replace(",", " ").split()
        out = []
        for item in items:
            host = str(item).strip().lower()
            if not HOST.match(host):
                raise Invalid(f"Not a host name: {host[:60]!r}.")
            if host not in out:
                out.append(host)
        if not out or len(out) > 50:
            raise Invalid("Give from 1 to 50 host names.")
        return out
    if kind == "views":
        return _views(value)
    if kind == "events":
        return _goals(value)
    if kind == "prefixes":
        return _prefixes(value, key)
    if kind == "eventtypes":
        from .conversions.event_types import validate as event_types
        try:
            return event_types(value) or None
        except ValueError as why:
            raise Invalid(str(why)) from None
    if kind == "zone":
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        zone = str(value).strip()
        try:
            if not ZONE.match(zone) or ".." in zone:
                raise ValueError
            ZoneInfo(zone)
        except (ValueError, ZoneInfoNotFoundError):
            raise Invalid(f"Not a time zone: {zone[:60]!r}. Use a name like Europe/London.") \
                from None
        return zone
    if kind == "path":
        path = str(value).strip()
        if (not path.startswith("/") or ".." in path.split("/") or len(path) > key.limit
                or any(ord(c) < 0x20 or ord(c) == 0x7f for c in path)):
            raise Invalid(f"{label} is a full path on the server, starting with /.")
        return path.rstrip("/") or "/"
    if kind == "filename":
        name_ = str(value).strip()
        if not FILENAME.match(name_):
            raise Invalid(f"{label} is a file name, like access.log.")
        return name_
    raise Invalid(f"{name!r} cannot be changed here.")


# ----------------------------------------------------------- who, where

def locked(config) -> frozenset:
    raw = ((config or {}).get("settings") or {}).get("locked") or []
    if isinstance(raw, str):
        raw = raw.replace(",", " ").split()
    return frozenset(str(k).strip() for k in raw if str(k).strip())


def may_edit(name: str, role: str | None, install_admin: bool, config) -> tuple[bool, str]:
    """(True, "") or (False, the reason the page shows)."""
    key = SCHEMA.get(name)
    if key is None:
        return False, f"{name!r} is not a setting that can be changed here."
    if name in locked(config):
        return False, LOCK_WORDS
    if key.who == "install":
        return (True, "") if install_admin else (False, WHO_WORDS["install"])
    if key.who == "owner":
        return (True, "") if role == "owner" else (False, WHO_WORDS["owner"])
    return (True, "") if role in ("owner", "admin") else (False, WHO_WORDS["admin"])


def scope_for(name: str, site: str | None, org_id) -> str:
    """Where the page saves `name` for this site."""
    kind = SCHEMA[name].scopes[0]
    if kind == "site":
        return f"site:{site}"
    if kind == "org":
        return f"org:{org_id}"
    return "install"


def parse_scope(scope: str) -> tuple[str, str]:
    kind, _, ident = str(scope).partition(":")
    if kind == "install" and not ident:
        return kind, ""
    if kind in ("site", "org") and ident:
        return kind, ident
    raise Invalid(f"Not a scope: {scope!r}.")


# --------------------------------------------------------------- storage

def _org_of(db, site: str | None):
    if not site:
        return None
    row = db.execute("SELECT org_id FROM sites WHERE name = ?", (site,)).fetchone()
    return row[0] if row else None


def get(db, scope: str, name: str):
    """The stored value of one row, or None when there is none."""
    row = db.execute("SELECT value FROM settings WHERE scope = ? AND key = ?",
                     (scope, name)).fetchone()
    return json.loads(row[0]) if row and row[0] is not None else None


def _shown(value) -> str:
    if value is None:
        return "(not set)"
    return json.dumps(value, separators=(",", ":"), sort_keys=True)[:200]


def _audit_org(db, scope: str):
    kind, ident = parse_scope(scope)
    if kind == "org":
        return int(ident) if ident.isdigit() else None
    if kind == "site":
        return _org_of(db, ident)
    return None


def put(db, scope: str, name: str, value, actor, secret: tuple | None = None) -> dict:
    """Save (or, with None, clear) one setting and write its audit row.
    {"old", "new"}. A secret needs `secret` = (secrets.json path, name);
    its old and new are only True/False (set or not)."""
    from .accounts import auditlog
    from .accounts import db as base
    key = SCHEMA.get(name)
    if key is None:
        raise Invalid(f"{name!r} is not a setting that can be changed here.")
    kind, _ = parse_scope(scope)
    if kind not in key.scopes:
        raise Invalid(f"{key.label or name} is set for the {key.scopes[0]}, not the {kind}.")
    value = validate(name, value)
    org_id = _audit_org(db, scope)
    if key.kind == "secret":
        if secret is None:
            raise Invalid("Secrets cannot be saved here: the server has no secrets file.")
        path, env = secret
        had = bool(_load_secrets(path).get(env))
        _put_secret(path, env, value or "")
        with base.tx(db):
            auditlog.record(db, org_id, actor, "setting.change", name,
                            f"{scope}: {'set' if value else 'cleared'}")
        return {"old": had, "new": bool(value)}
    with base.tx(db):
        old = get(db, scope, name)
        if value is None:
            db.execute("DELETE FROM settings WHERE scope = ? AND key = ?", (scope, name))
        else:
            db.execute("INSERT INTO settings (scope, key, value, updated_by, updated_at) "
                       "VALUES (?, ?, ?, ?, ?) ON CONFLICT(scope, key) DO UPDATE SET "
                       "value = excluded.value, updated_by = excluded.updated_by, "
                       "updated_at = excluded.updated_at",
                       (scope, name, json.dumps(value), str(actor), base.now()))
        if old != value:
            auditlog.record(db, org_id, actor, "setting.change", name,
                            f"{scope}: {_shown(old)} -> {_shown(value)}")
    return {"old": old, "new": value}


# The brief's names: get(db, scope, key) and set(db, scope, key, value, actor).
# Bound at the end of the module, so nothing here calls the builtin set().


# ---------------------------------------------------------- merged view

def history_folder(config, live_dir=None) -> Path | None:
    """The history's folder: `live_dir` when given, else the history file
    Context resolved, else an absolute history.db; None when not known."""
    if live_dir is not None:
        return Path(live_dir)
    made = ((config or {}).get("_resolved") or {}).get("history_db")
    raw = made or setting(config or {}, "history", "db")
    if raw and Path(str(raw)).expanduser().is_absolute():
        return Path(str(raw)).expanduser().parent
    return None


def accounts_file(config, live_dir=None) -> Path | None:
    """accounts.sqlite when it exists: `access.accounts`, else beside the history."""
    from .accounts.db import path_for
    path = path_for(config or {}, history_folder(config, live_dir))
    return path if path is not None and Path(path).is_file() else None


def _rows(db, site: str | None) -> tuple[dict, object]:
    org = _org_of(db, site)
    scopes = [s for s in ((f"site:{site}" if site else None),
                          (f"org:{org}" if org is not None else None), "install") if s]
    marks = ",".join("?" * len(scopes))
    got = {}
    for scope, name, value in db.execute(
            f"SELECT scope, key, value FROM settings WHERE scope IN ({marks})", scopes):
        if value is not None:
            got[(scope, name)] = json.loads(value)
    return got, org


def _from_config(config, key: Key):
    if key.config is None:
        return None
    if key.kind == "eventtypes":        # nested hooks.<tool>.event_types, or the flat key
        from .conversions.event_types import from_config
        return from_config(config, key.config[1].rsplit("_event_types", 1)[0]) or None
    raw = setting(config or {}, *key.config)
    if raw is None and key.config[0] == "alerts" and key.config[1].startswith("ai_"):
        nested = ((config or {}).get("alerts") or {}).get("ai")     # alerts_ai.settings
        raw = nested.get(key.config[1][3:]) if isinstance(nested, dict) else None
    if raw is None:
        return None
    if key.kind == "ipmode":                                        # true / false too
        from .people.policy import mode_of
        return mode_of(raw)
    if key.kind == "bool" and key.config[0] == "alerts":            # alerts._flag's words
        return raw is True or str(raw).strip().lower() in ("1", "true", "yes", "on")
    if key.kind == "int":
        try:
            return int(raw)
        except (TypeError, ValueError):
            return raw
    if key.kind == "bool":
        return raw is True or str(raw).lower() == "true"
    if key.kind in ("emails", "hosts") and isinstance(raw, str):
        return [raw]
    if key.kind in ("events", "prefixes") and isinstance(raw, str):
        return raw.replace(",", " ").split()
    return raw


def explain(config, site: str | None = None, db=None, live_dir=None) -> dict:
    """{key: {"value", "source", "locked"}} for every key that is not a
    secret. source: site, org, install, config, default, or upgrade (an
    unset privacy key on an install upgraded to 2.4.0: LEGACY_DEFAULTS)."""
    own = None
    if db is None:
        path = accounts_file(config, live_dir)
        if path is not None:
            from .accounts import connect
            db = own = connect(path)
    try:
        rows, org = _rows(db, site) if db is not None else ({}, None)
        cap = plan_cap(db, config, org)
    finally:
        if own is not None:
            own.close()
    locks = locked(config)
    order = (("site", f"site:{site}"), ("org", f"org:{org}"), ("install", "install"))
    out = {}
    for name in PLAIN:
        key = SCHEMA[name]
        lock = name in locks
        value, source = None, None
        if not lock:
            for kind, scope in order:
                if kind in key.scopes and (scope, name) in rows:
                    value, source = rows[(scope, name)], kind
                    if key.kind == "ipmode":    # a row saved as true / false
                        from .people.policy import mode_of
                        value = mode_of(value) or key.default
                    break
        if source is None:
            value = _from_config(config, key)
            source = "config" if value is not None else "default"
            if value is None:
                value = key.default
                if name in LEGACY_DEFAULTS and _legacy(config, live_dir):
                    value, source = LEGACY_DEFAULTS[name], "upgrade"
        out[name] = {"value": value, "source": source, "locked": lock}
        most = capped(name, cap)
        if most is not None and isinstance(value, int) and value > most:
            # The plan keeps less than the value says: the cap is what applies.
            out[name].update(value=most, capped=True, set_value=value)
    return out


# What an unset key reads as on an install upgraded to 2.4.0 (people/policy.py).
LEGACY_DEFAULTS = {"privacy.keep_ips": "off", "conversions.identity": "anonymous"}


def _legacy(config, live_dir=None) -> bool:
    from .people.policy import legacy
    return legacy(config or {}, history_folder(config, live_dir))


def plan_cap(db, config, org) -> int | None:
    """The organisation's plan's retention_days_max (saas/limits.py), or None:
    no accounts file, no organisation, saas off or no cap."""
    if db is None or org is None:
        return None
    from .saas import enabled
    if not enabled(config):
        return None
    from .saas.limits import retention_cap
    return retention_cap(db, org, config)


def _caps(db, config) -> dict:
    """{site: its organisation's retention cap} for every site with one."""
    from .saas import enabled
    if not enabled(config):
        return {}
    got, by_org = {}, {}
    for site, org in db.execute("SELECT name, org_id FROM sites"):
        if org not in by_org:
            by_org[org] = plan_cap(db, config, org)
        if by_org[org] is not None:
            got[site] = by_org[org]
    return got


def effective(config, site: str | None = None, db=None, live_dir=None) -> dict:
    """{key: value}: config.yml merged with the settings rows for `site`."""
    return {k: v["value"] for k, v in explain(config, site, db, live_dir).items()}


def _per_site(db, name: str) -> dict:
    """{site: value} for every site with its own or its organisation's row."""
    found, by_org = {}, {}
    for scope, value in db.execute("SELECT scope, value FROM settings WHERE key = ? AND "
                                   "(scope LIKE 'site:%' OR scope LIKE 'org:%')", (name,)):
        if value is None:
            continue
        kind, ident = scope.split(":", 1)
        if kind == "site":
            found[ident] = json.loads(value)
        elif ident.isdigit():
            by_org[int(ident)] = json.loads(value)
    for org, value in by_org.items():
        for (site,) in db.execute("SELECT name FROM sites WHERE org_id = ?", (org,)):
            found.setdefault(site, value)
    return found


SHRINKING = tuple(k for k in PLAIN if SCHEMA[k].shrink and "site" in SCHEMA[k].scopes)
# The per-day detail report.retention_days keeps (store_extras kinds); totals,
# page milestones and the rest are kept for good.
DETAIL_KINDS = ("pages", "visit_cube", "cube", "crawler_paths", "page_firsts",
                "not_found", "page_counts", "funnels", "crawler_cost",
                "crawl_health")


def apply(config: dict, site: str | None = None, live_dir=None) -> dict:
    """A copy of `config` with every value that comes from a settings row
    written into its config.yml place (report.retention_days, mail.to, ...),
    plus "_settings": what pruning needs (`prune_plan`). The config itself
    when there is no accounts file: nothing changes then."""
    path = accounts_file(config, live_dir)
    if path is None:
        return config
    from .accounts import connect
    db = connect(path)
    try:
        here = explain(config, site, db)
        waiting = _confirmed_only(db, config, site, here["mail.to"])
        install = explain(config, None, db)
        locks = locked(config)
        caps = _caps(db, config)
        plan = {name: _site_windows(db, name, install[name]["value"], name in locks, caps)
                for name in SHRINKING}
    finally:
        db.close()
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (config or {}).items()}
    for name, got in here.items():
        key = SCHEMA[name]
        if (got["source"] in ("site", "org", "install") or got.get("capped")) \
                and key.config is not None:
            section, ck = key.config
            if not isinstance(out.get(section), dict):
                out[section] = {}
            out[section][ck] = got["value"]
    if waiting:
        out["mail"]["to_waiting"] = waiting
    out["_settings"] = {"prune": plan}
    return out


def _site_windows(db, name: str, default, lock: bool, caps: dict) -> dict:
    """{"default", "sites"} for one retention key: each site's own window
    (none when config.yml locks the key), cut to its plan's cap."""
    sites = {} if lock else _per_site(db, name)
    for site, cap in caps.items():
        most = capped(name, cap)
        value = sites.get(site, default)
        if most is not None and isinstance(value, int) and value > most:
            sites[site] = most
    return {"default": default, "sites": sites}


def _confirmed_only(db, config, site, got: dict) -> int:
    """Drop page-set recipients (a site or organisation row) that have not
    confirmed (mail_confirm.py); config.yml's own count as confirmed. How
    many are still waiting."""
    if got["source"] not in ("site", "org") or not got["value"]:
        return 0
    from .mail_confirm import keep_confirmed
    own = _from_config(config, SCHEMA["mail.to"]) or []
    got["value"], waiting = keep_confirmed(db, _org_of(db, site), got["value"], own)
    return len(waiting)


def prune_plan(config, name: str, fallback: int) -> tuple[int, dict]:
    """(days for every site, {site: its own days}) for one retention key.
    Without settings rows: (`fallback`, {}), exactly today's pruning."""
    plan = (((config or {}).get("_settings") or {}).get("prune") or {}).get(name)
    if not plan:
        return int(fallback), {}
    return int(plan["default"]), {s: int(v) for s, v in (plan["sites"] or {}).items()}


# --------------------------------------------------------------- secrets

def secrets_path(config, live_dir=None) -> Path | None:
    """secrets.json beside the history (the file conversions/secrets_store.py
    keeps hook secrets in), or None when the history's folder is not known."""
    from .conversions.secrets_store import path_for
    folder = history_folder(config, live_dir)
    if folder is None and not ((config or {}).get("hooks") or {}).get("secrets"):
        return None
    return path_for(config or {}, folder if folder is not None else Path("."))


def secret_name(config, name: str) -> str:
    """The environment variable (and secrets.json key) of a secret. The SMTP
    password keeps the name config.yml gives (`mail.password_env`)."""
    if name == "mail.smtp.password":
        given = setting(config or {}, "mail", "password_env")
        if given:
            return str(given)
    return SCHEMA[name].env


def _load_secrets(path) -> dict:
    from .conversions.secrets_store import load
    return load(Path(path)) if path is not None else {}


def _put_secret(path, env: str, value: str) -> None:
    from .conversions.secrets_store import put as store
    store(Path(path), env, value)


def stored_secret(config, env: str, live_dir=None) -> str | None:
    """A secret by its name: the environment first, then secrets.json.
    Raises conversions.secrets_store.Exposed when the file is not 0600."""
    value = os.environ.get(env)
    if value:
        return value
    path = secrets_path(config, live_dir)
    got = _load_secrets(path).get(env) if path is not None else None
    return str(got) if got else None


def secret_value(config, name: str, live_dir=None) -> str | None:
    return stored_secret(config, secret_name(config, name), live_dir)


def secret_state(config, name: str, live_dir=None) -> dict:
    """{"set": bool, "env": bool}: never the value."""
    env = secret_name(config, name)
    in_env = bool(os.environ.get(env))
    try:
        path = secrets_path(config, live_dir)
        in_file = bool(path is not None and _load_secrets(path).get(env))
    except PermissionError:
        in_file = False
    return {"set": in_env or in_file, "env": in_env}


set = put  # noqa: A001 - the brief's name, set(db, scope, key, value, actor)

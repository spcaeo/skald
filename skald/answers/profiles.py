"""Tracking profiles: checked, saved, paused, deleted; never erased.

A profile's body (JSON):

  name             at most 60 characters
  city, region     the asker's place (at most 80 characters each)
  country          ISO 3166-1 alpha-2 (the providers' location fields take it)
  lat, lon         optional coordinates (Perplexity takes them)
  timezone         optional IANA zone (OpenAI and Anthropic take it)
  language         BCP-47, e.g. en, fr-CA
  questions        its own list, or [] with use_site_questions true
  brands           its own brand terms, or [] for the site's
  competitors      its own, or [] for the site's
  providers        which assistants to ask (answers.PROVIDERS)
  frequency        daily, weekly or monthly
  repeats          tries per question, 1 to 5
  cap              the daily spending cap, US dollars (0.10 to 100)
  gbp_location_id  a Google Business Profile location, kept for later; unused

The same rule as internal traffic (ours_store.py): a pause is a pair
[from, to] kept on the profile (to null while paused); delete sets
removed_at and the profile leaves the lists, its results stay; an edit is a
new version (profile_versions keeps each), and a run keeps the version it
used, so earlier results are never re-read under new settings.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone

from . import FREQUENCIES, PROFILE_LIMIT, PROVIDERS, QUESTION_LIMIT, run_hour
from .store import loads, now_iso

LANG = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,3}$")
COUNTRY = re.compile(r"^[A-Z]{2}$")
BRAND_LIMIT, COMPETITOR_LIMIT = 20, 30


class Invalid(ValueError):
    """A value the profile does not take, in plain words."""


def _text(value, label: str, most: int, need: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise Invalid(f"{label} is text.")
    if any(ord(c) < 0x20 or ord(c) == 0x7f for c in value):
        raise Invalid(f"{label} cannot hold control characters.")
    got = " ".join(value.split())
    if len(got) > most:
        raise Invalid(f"{label} is at most {most} characters.")
    if need and not got:
        raise Invalid(f"{label} is needed.")
    return got


def text_list(value, label: str, most_items: int, most_chars: int, least_chars: int = 1) -> list[str]:
    if value is None:
        return []
    items = value.splitlines() if isinstance(value, str) else value
    if not isinstance(items, list):
        raise Invalid(f"{label} are a list.")
    out = []
    for item in items:
        got = _text(item, f"Each of the {label.lower()}", most_chars)
        if not got:
            continue
        if len(got) < least_chars:
            raise Invalid(f"Each of the {label.lower()} is at least {least_chars} characters.")
        if got.lower() not in (x.lower() for x in out):
            out.append(got)
    if len(out) > most_items:
        raise Invalid(f"At most {most_items} {label.lower()}.")
    return out


def questions(value) -> list[str]:
    return text_list(value, "Questions", QUESTION_LIMIT, 300, 3)


def brands(value) -> list[str]:
    return text_list(value, "Brand terms", BRAND_LIMIT, 80)


def competitors(value) -> list[str]:
    return text_list(value, "Competitors", COMPETITOR_LIMIT, 80)


def _number(value, label: str, lo: float, hi: float, whole: bool = False):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise Invalid(f"{label} is a number.")
    try:
        got = int(str(value)) if whole else float(value)
    except (TypeError, ValueError):
        raise Invalid(f"{label} is a{' whole' if whole else ''} number.") from None
    if not lo <= got <= hi:
        raise Invalid(f"{label} is from {lo:g} to {hi:g}.")
    return got


def check(raw: dict) -> dict:
    """The body as stored, or Invalid."""
    if not isinstance(raw, dict):
        raise Invalid("A profile is a set of fields.")
    body = {"name": _text(raw.get("name"), "The profile's name", 60, need=True),
            "city": _text(raw.get("city"), "City", 80),
            "region": _text(raw.get("region"), "Region", 80)}
    country = _text(raw.get("country"), "Country", 2).upper()
    if country and not COUNTRY.match(country):
        raise Invalid("Country is a two-letter ISO code, like CA or US.")
    body["country"] = country
    lat = _number(raw.get("lat"), "Latitude", -90, 90)
    lon = _number(raw.get("lon"), "Longitude", -180, 180)
    if (lat is None) != (lon is None):
        raise Invalid("Give both latitude and longitude, or neither.")
    body.update(lat=lat, lon=lon)
    zone = _text(raw.get("timezone"), "Time zone", 64)
    if zone:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            if ".." in zone:
                raise ValueError
            ZoneInfo(zone)
        except (ValueError, ZoneInfoNotFoundError):
            raise Invalid(f"Not a time zone: {zone[:40]!r}. Use a name like America/Toronto.") \
                from None
    body["timezone"] = zone
    lang = _text(raw.get("language") or "en", "Language", 20)
    if not LANG.match(lang):
        raise Invalid("Language is a BCP-47 code, like en or fr-CA.")
    body["language"] = lang
    body["use_site_questions"] = raw.get("use_site_questions") in (True, "true", 1)
    body["questions"] = [] if body["use_site_questions"] else questions(raw.get("questions"))
    body["brands"] = brands(raw.get("brands"))
    body["competitors"] = competitors(raw.get("competitors"))
    chosen = raw.get("providers")
    if isinstance(chosen, str):
        chosen = chosen.replace(",", " ").split()
    if not isinstance(chosen, list) or any(p not in PROVIDERS for p in chosen):
        raise Invalid(f"Assistants are any of: {', '.join(PROVIDERS)}.")
    body["providers"] = [p for p in PROVIDERS if p in chosen]
    freq = raw.get("frequency") or "weekly"
    if freq not in FREQUENCIES:
        raise Invalid("How often is daily, weekly or monthly.")
    body["frequency"] = freq
    body["repeats"] = _number(raw.get("repeats", 1), "Tries per question", 1, 5, whole=True) or 1
    cap = _number(raw.get("cap", 2), "The daily spending cap", 0.1, 100)
    body["cap"] = round(cap if cap is not None else 2.0, 2)
    gbp = _text(raw.get("gbp_location_id"), "Google Business Profile location", 100)
    body["gbp_location_id"] = gbp or None
    return body


# --------------------------------------------------------------- storing

def _row(r) -> dict:
    return {"id": r["id"], "version": r["version"], **loads(r["body"], {}),
            "paused": loads(r["paused"], []), "created_at": r["created_at"],
            "updated_at": r["updated_at"], "removed_at": r["removed_at"],
            "run_requested_at": r["run_requested_at"], "copied_from": r["copied_from"]}


def listed(db, site: str, removed: bool = False) -> list[dict]:
    sql = "SELECT * FROM profiles WHERE site = ?" + ("" if removed else " AND removed_at IS NULL")
    return [_row(r) for r in db.execute(sql + " ORDER BY id", (site,))]


def one(db, site: str, pid) -> dict | None:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    r = db.execute("SELECT * FROM profiles WHERE site = ? AND id = ?", (site, pid)).fetchone()
    return _row(r) if r else None


def create(db, site: str, body: dict, who: str, now: datetime | None = None,
           copied_from: int | None = None) -> int:
    if len(listed(db, site)) >= PROFILE_LIMIT:
        raise Invalid(f"A site has at most {PROFILE_LIMIT} profiles. Delete one first.")
    at = now_iso(now)
    text = json.dumps(body, sort_keys=True)
    with db:
        cur = db.execute("INSERT INTO profiles (site, version, body, created_at, created_by, "
                         "updated_at, updated_by, copied_from) VALUES (?, 1, ?, ?, ?, ?, ?, ?)",
                         (site, text, at, who, at, who, copied_from))
        pid = int(cur.lastrowid)
        db.execute("INSERT INTO profile_versions VALUES (?, 1, ?, ?, ?)", (pid, text, at, who))
    return pid


def update(db, site: str, pid: int, body: dict, who: str, now: datetime | None = None) -> int:
    """A new version; the old one stays in profile_versions. The version."""
    got = one(db, site, pid)
    if got is None or got["removed_at"]:
        raise Invalid("No such profile.")
    old = {k: got.get(k) for k in body}
    if old == body:
        return got["version"]
    at, text, version = now_iso(now), json.dumps(body, sort_keys=True), got["version"] + 1
    with db:
        db.execute("UPDATE profiles SET version = ?, body = ?, updated_at = ?, updated_by = ? "
                   "WHERE id = ?", (version, text, at, who, got["id"]))
        db.execute("INSERT INTO profile_versions VALUES (?, ?, ?, ?, ?)",
                   (got["id"], version, text, at, who))
    return version


def duplicate(db, site: str, pid: int, who: str, now: datetime | None = None) -> int:
    got = one(db, site, pid)
    if got is None or got["removed_at"]:
        raise Invalid("No such profile.")
    body = check({**got, "name": (got["name"] + " (copy)")[:60]})
    return create(db, site, body, who, now, copied_from=got["id"])


def is_paused(p: dict, at: datetime) -> bool:
    for start, end in p.get("paused") or []:
        s = _when(start)
        e = _when(end) if end else None
        if s is not None and s <= at and (e is None or at < e):
            return True
    return False


def _when(raw):
    try:
        got = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def pause(db, site: str, pid: int, on: bool, who: str, now: datetime | None = None) -> bool:
    """Pause (on) or resume. False when nothing changed."""
    got = one(db, site, pid)
    if got is None or got["removed_at"]:
        raise Invalid("No such profile.")
    pairs, at = [list(x) for x in got["paused"]], now_iso(now)
    open_pair = bool(pairs) and pairs[-1][1] is None
    if on == open_pair:
        return False
    if on:
        pairs.append([at, None])
    else:
        pairs[-1][1] = at
    with db:
        db.execute("UPDATE profiles SET paused = ?, updated_at = ?, updated_by = ? WHERE id = ?",
                   (json.dumps(pairs), at, who, got["id"]))
    return True


def delete(db, site: str, pid: int, who: str, now: datetime | None = None) -> None:
    got = one(db, site, pid)
    if got is None or got["removed_at"]:
        raise Invalid("No such profile.")
    with db:
        db.execute("UPDATE profiles SET removed_at = ?, removed_by = ? WHERE id = ?",
                   (now_iso(now), who, got["id"]))


def request_run(db, site: str, pid: int, now: datetime | None = None) -> None:
    got = one(db, site, pid)
    if got is None or got["removed_at"]:
        raise Invalid("No such profile.")
    with db:
        db.execute("UPDATE profiles SET run_requested_at = ? WHERE id = ?", (now_iso(now), got["id"]))


# ------------------------------------------------------------- the plan

def resolved(p: dict, site_lists: dict) -> dict:
    """The questions, brand terms and competitors a profile asks with."""
    qs = site_lists["questions"] if p.get("use_site_questions") or not p.get("questions") \
        else p["questions"]
    return {"questions": list(qs), "brands": list(p.get("brands") or site_lists["brands"]),
            "competitors": list(p.get("competitors") or site_lists["competitors"])}


def next_run(p: dict, last_day: str | None, config, tz) -> str | None:
    """When the profile is next due, ISO, in the site's zone (None: paused)."""
    if p.get("paused") and p["paused"][-1][1] is None:
        return None
    hour = run_hour(config)
    if last_day is None:
        day = datetime.now(tz).date()
    else:
        day = date.fromisoformat(last_day) + timedelta(days=FREQUENCIES[p["frequency"]])
    return datetime(day.year, day.month, day.day, hour, tzinfo=tz).isoformat(timespec="minutes")


def due(p: dict, last_day: str | None, now: datetime, config) -> str | None:
    """"requested", "schedule" or None."""
    if p.get("removed_at") or is_paused(p, now.astimezone(timezone.utc)):
        return None
    if p.get("run_requested_at"):
        return "requested"
    if now.hour < run_hour(config):
        return None
    if last_day is None:
        return "schedule"
    gap = (now.date() - date.fromisoformat(last_day)).days
    return "schedule" if gap >= FREQUENCIES[p["frequency"]] else None

"""The audit's own city of a visit, and its check of the stored cities.

The main road's city is conversions/geo.py's Cities (city, city_label),
counted by aggregate.Tally into `people_city_visits` and onto each journey.
This is the second road: it shares only the city file itself (`logs.city_db`)
and the MaxMind-format reader that opens it, as the country recount shares
the country file. Everything after the raw record is its own: which keys hold
the city, the region and the country, how a name is cleaned, how the label
is built, and the rule that a line's own country wins over the city's.

  the label   "City, Region, CC": the city's English name (else its first
              name), the first subdivision's (left out when missing or the
              same as the city), the country code; commas in a name are
              spaces, runs of spaces one space. No city name: no city.
  the rule    a line whose country (its own, or the country file's) is not
              the city record's country has no city.
  the figure  readers (visits with a page) by the city of their first page,
              "Unknown" when not recorded, kept exactly; the stored folded
              "(all others)" against the recount's remainder.

A day stored without city rows was collected before cities, or without a
city file: there is nothing to compare, so it is skipped and said so.
"""
from __future__ import annotations

from collections import Counter

from .conversions.geo import reader as _open

KIND = "people_city_visits"          # the stored kind (store.py), by name
NONE = "Unknown"


def _path(config: dict) -> str:
    got = ((config or {}).get("logs") or {}).get("city_db")
    return "" if got in (None, "", []) else str(got)


def _name(part) -> str:
    if not isinstance(part, dict) or not isinstance(part.get("names"), dict):
        return ""
    names = part["names"]
    text = names.get("en") if isinstance(names.get("en"), str) else ""
    if not text.strip():
        for value in names.values():
            if isinstance(value, str) and value.strip():
                text = value
                break
    return " ".join(text.split())[:80]


def _label(record) -> tuple[str, str]:
    """(label, country code) of a raw city record; ("", "") for none."""
    if not isinstance(record, dict):
        return "", ""
    city = " ".join(_name(record.get("city")).replace(",", " ").split())
    if not city:
        return "", ""
    subs = record.get("subdivisions")
    region = ""
    if isinstance(subs, list) and len(subs) > 0:
        region = " ".join(_name(subs[0]).replace(",", " ").split())
    country = record.get("country")
    code = ""
    if isinstance(country, dict) and country.get("iso_code"):
        code = str(country["iso_code"]).upper()
    if len(code) != 2 or not code.isalpha() or code in ("XX", "ZZ"):
        code = ""
    words = [city] + ([region] if region and region != city else []) + ([code] if code else [])
    return ", ".join(words), code


def fill(config: dict):
    """address, line country -> the city label or "", one lookup per
    address; None without a city file."""
    path = _path(config)
    if not path:
        return None
    seen: dict[str, tuple[str, str]] = {}

    def city(address: str, country: str = "") -> str:
        if address not in seen:
            try:
                db = _open(path)
                record = db.lookup(address.strip()) if db is not None and address else None
            except (ValueError, KeyError, IndexError, TypeError):
                record = None
            except Exception:                  # struct.error: a damaged file
                record = None
            seen[address] = _label(record)
        label, code = seen[address]
        if label and code and country and country.upper() != code:
            return ""
        return label
    return city


def compare(stored: Counter | None, counted: Counter | None, readers: int, same,
            problems: list, compare_dim) -> None:
    """The stored cities against the recount (compare_dim: audit._compare_dim).
    No stored rows: a day from before cities, skipped."""
    if not stored:
        return
    compare_dim("city", stored, counted if counted is not None else Counter(), readers,
                same, problems)

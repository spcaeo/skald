"""A tool's record (adapters/) made into the row the store keeps.

Source, campaign and landing come from the touches by the same rules as a
reader's visit in the log (dimensions.py). Country: the two letters the
sender gave, else looked up from the visitor's address when the sender
passed one (`ip`: an address, or an X-Forwarded-For list whose first entry
is taken, geo.address); the address is then dropped. A visitor ID never
gives a lead its country: `vid` joins the lead to the pages read, `ip` (or
`country`) gives the country, and a lead may send both. Device: the sender's
Desktop/Mobile/Tablet, else worked out from the user agent, which is then
dropped. A figure the sender did not give stays NULL: never "Direct", never
"Desktop" by default.
"""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

from ..classify import AI_UTM, cited_by
from ..dimensions import DEVICES, SOURCE_TYPES, campaign, device, source_type
from . import FUTURE_SLACK, geo
from .adapters import Invalid
from .store import parse

TAGS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "gclid",
        "gbraid", "wbraid", "msclkid", "fbclid", "li_fat_id")


def _url(touch: dict) -> str:
    landing = str(touch.get("landing") or "/")
    if "://" in landing:
        landing = "/" + landing.split("://", 1)[1].partition("/")[2]
    extra = urlencode([(k, touch[k]) for k in TAGS if touch.get(k)])
    if not extra:
        return landing
    return landing + ("&" if "?" in landing else "?") + extra


def _path(touch: dict | None) -> str | None:
    if not touch or not touch.get("landing"):
        return None
    landing = str(touch["landing"])
    if "://" in landing:
        landing = "/" + landing.split("://", 1)[1].partition("/")[2]
    return landing.split("?", 1)[0].split("#", 1)[0][:300] or "/"


def touch_source(touch: dict | None, own_hosts: set[str]) -> str | None:
    if not touch:
        return None
    referrer = str(touch.get("referrer") or "")
    url = _url(touch)
    cited = bool(cited_by(referrer)) or bool(AI_UTM.search(url))
    return source_type(referrer, url, cited, own_hosts)


def touch_campaign(touch: dict | None) -> str | None:
    return campaign(_url(touch)) if touch else None


def row(rec: dict, site: str, tool: str, received_at: str, own_hosts: set[str],
        identity_full: bool, country_db=None) -> dict:
    """The store's row for one record. Invalid when `at` is more than a day
    after the record arrived."""
    at = rec.get("at") or received_at
    if parse(at) > parse(received_at) + timedelta(seconds=FUTURE_SLACK):
        raise Invalid("at is more than a day after it arrived")
    first, last = rec.get("first_touch"), rec.get("last_touch")
    given = rec.get("source_type")
    src = given if given in SOURCE_TYPES else touch_source(last or first, own_hosts)
    country = str(rec.get("country") or "").strip().upper()
    if not (len(country) == 2 and country.isalpha()) or country in ("XX", "ZZ"):
        ip = geo.address(rec.get("ip"))
        country = geo.country(country_db, ip) if ip else None
    said = str(rec.get("device") or "").strip().capitalize()
    dev = said if said in DEVICES else (device(rec["user_agent"])
                                        if rec.get("user_agent") else None)
    out = {"site": site, "tool": tool, "action": rec["action"], "stage": rec["stage"],
           "at": at, "vid": rec.get("vid"), "external_ref": rec["external_ref"],
           "source_type": src, "first_source": touch_source(first, own_hosts),
           "campaign": rec.get("campaign") or touch_campaign(last or first),
           "landing": _path({"landing": rec.get("landing")}) or _path(first) or _path(last),
           "country": country or None, "device": dev,
           "first_touch_at": rec.get("first_touch_at") or (first or {}).get("at"),
           "visits_before": rec.get("visits_before"), "received_at": received_at,
           "label": rec.get("label") or None, "test": rec.get("test") is True,
           # 2.32: money (conversions/money.py); pay_ref is Stripe's payment
           # intent (or invoice), to find the sale a refund is for.
           "value_minor": rec.get("value_minor"), "currency": rec.get("currency"),
           "customer_ref": rec.get("customer_ref"), "tags": rec.get("tags"),
           "pay_ref": rec.get("pay_ref"), "value_sent": rec.get("value_sent", True)}
    if rec.get("refund_of"):
        out["refund_of"] = list(rec["refund_of"])
    if identity_full and rec.get("email"):
        out["identity"] = {"email": rec["email"], "name": rec.get("name")}
    return out

"""Wording for a site's privacy notice, made from what the site's settings keep.

Settings > Data retention shows it ("Wording for your privacy notice") with a
Copy button. It is built from the same functions that decide what is kept,
so it can never say something the settings do not do:

    the log         always: the server's access log is read to count visits;
                    reading it sets no cookie and stores nothing on the device
    IP addresses    policy.ip_mode: kept in full, kept shortened (the rule
                    in plain words, policy.shorten) or not kept; for
                    policy.keep_days days
    names, emails   policy.identity_full: kept with a lead's conversions, or not
    the script tag  only when the site has the beacon on (events.enabled):
                    visitor IDs (beacon.visitor_ids) and where they are kept,
                    Do Not Track and Global Privacy Control, and the wait for
                    consent (data-consent="required", a tag attribute the
                    server cannot see: a marked line to keep or delete)
    deletion        how to ask, with the site's own contact as a marked
                    placeholder: Skald does not know it

A placeholder is in square brackets, and `placeholders` lists each one. A
starting point, not legal advice: the card says so (NOTE).
"""
from __future__ import annotations

from ..config import setting
from . import policy

NOTE = "A starting point, not legal advice. Your notice must match your own situation."
CONTACT = "[your contact email or page]"
LOG_DAYS = "[how long your web server keeps its logs]"
CONSENT = "[Keep this line only if your script tag has data-consent=\"required\":]"
SHARED_MARK = "[Keep this line only if your script tag has data-share-subdomains=\"true\":]"
SHARED = (f"{SHARED_MARK} It is also kept in a first-party cookie called skald_vid, for up to 400 days, "
          "so our subdomains see the same ID.")
INTRO = "How we measure visits to this site:"


def _days(n: int) -> str:
    return f"{n} day" if n == 1 else f"{n} days"


def _address(mode: str, days: int, city: bool) -> str:
    place = "country and city" if city else "country"
    if mode == policy.FULL:
        return (f"We keep each visit's IP address with its browser, the pages it read and "
                f"where it came from, for {_days(days)}, so that one visitor's visits can be "
                f"followed across days. The visit's {place} is looked up from the address.")
    if mode == policy.SHORT:
        return (f"We keep each visit's IP address shortened, with its last part removed: "
                f"203.0.113.57 is kept as 203.0.113.0, and an IPv6 address keeps only its "
                f"first 48 bits. A shortened address no longer points to one device. It is "
                f"kept with the visit's browser, the pages it read and where it came from, "
                f"for {_days(days)}. The visit's {place} is looked up from the full address "
                f"before it is shortened.")
    return ("We do not keep IP addresses with the visits we count. Each visit is counted "
            "without its address, and the totals hold no address.")


def _beacon(config: dict) -> list[str]:
    from ..beacon import visitor_ids
    out = ["Our pages also load a small script from our own site. It counts clicks and form "
           "steps, never what you type in a form."]
    if visitor_ids(config):
        out += ["The script keeps a random visitor ID in your browser's local storage, so "
                "visits from the same browser can be linked. It holds no name or email.",
                SHARED]
    else:
        out.append("The script keeps no ID and stores nothing in your browser.")
    out += ["If your browser sends Do Not Track or Global Privacy Control, the script does "
            "nothing at all.",
            f"{CONSENT} The script waits for your consent in our consent banner: until you "
            f"agree, it sends nothing and keeps no ID."]
    return out


def wording(config: dict, folder=None) -> dict:
    """{"intro", "items", "text", "placeholders", "note", "uses"} for this
    site (see the module). `uses` says which settings the text was made from."""
    from ..beacon import visitor_ids
    from ..events import enabled as beacon_on
    mode = policy.ip_mode(config, folder)
    days = policy.keep_days(config)
    full = policy.identity_full(config, folder)
    tag = bool(beacon_on(config))
    ids = tag and visitor_ids(config)
    city = bool(setting(config or {}, "logs", "city_db"))
    items = [
        "We count visits from our web server's own access log. Reading the log sets no "
        "cookie and stores nothing on your device.",
        f"The access log itself holds each request's full IP address and browser, and is "
        f"kept for {LOG_DAYS}. Our admins can see the last 6 hours of requests, and "
        f"today's AI activity, with their addresses; these are not kept longer.",
        _address(mode, days, city),
        ("When you send us a form or book a call, we keep your name and email with it, so "
         "we can see which visits led to it.") if full else
        ("When you send us a form or book a call, our analytics keep no name or email "
         "with it."),
    ]
    if tag:
        items += _beacon(config)
    ask = "your IP address" + (" or the email you used" if full else "")
    items.append(f"To ask us to delete what we keep about you, write to {CONTACT} with "
                 f"{ask}. We delete it everywhere our analytics keep it.")
    placeholders = [CONTACT, LOG_DAYS] + ([CONSENT] if tag else []) + \
        ([SHARED_MARK] if ids else [])
    return {"intro": INTRO, "items": items,
            "text": INTRO + "\n\n" + "\n".join(f"- {i}" for i in items),
            "placeholders": placeholders, "note": NOTE,
            "uses": {"ip_mode": mode, "keep_days": days,
                     "identity": "full" if full else "anonymous", "script_tag": tag,
                     "visitor_ids": ids}}

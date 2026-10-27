"""Wording for a site's privacy notice, made from what the site's settings keep.

Settings > Privacy shows it ("Wording for your privacy notice") with a
Copy button. It is built from the same functions that decide what is kept,
so it can never say something the settings do not do:

    the log         always: the server's access log is read to count visits;
                    reading it sets no cookie and stores nothing on the device
    IP addresses    policy.ip_mode: kept in full, kept shortened (the rule
                    in plain words, policy.shorten) or not kept; for
                    policy.keep_days days
    names, emails   policy.identity_full: kept with a lead's conversions, or not;
                    for conversions.retention_days days, or "until you ask us
                    to delete them" when it is 0 (kept for good, 2.29); for
                    the People days (privacy.keep_days) when those are
                    shorter, and then the lead is kept without them for its
                    own days (conversions/people_days.py)
    the script tag  only when the site has the beacon on (events.enabled):
                    where it loads from (the analytics server, or the site
                    when it passes the tag on: either way, "our analytics
                    server"), the visit's source it keeps in the tab's
                    session storage (skald.src, IDs on or off, SOURCE),
                    visitor IDs (beacon.visitor_ids) and where they are kept,
                    the pages read with one: journeys.vid_days days, then
                    kept with the lead once the visitor sends a form,
                    Do Not Track and Global Privacy Control, and the wait for
                    consent (data-consent="required", a tag attribute the
                    server cannot see: a marked line to keep or delete);
                    the shared cookie: a plain line when the site shares
                    the ID in Skald (beacon.share_subdomains), else a marked
                    line for the tag's data-share-subdomains="true"
    deletion        how to ask, with the site's own contact as a marked
                    placeholder: Skald does not know it
    keep everything a site that keeps everything (keep_everything.py:
                    internal or enterprise) deletes nothing by itself, so
                    every "for N days" reads "until you ask us to delete it"

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
SHARED_LINE = ("It is also kept in a first-party cookie called skald_vid, for up to 400 days, "
               "so our subdomains see the same ID.")
SHARED = f"{SHARED_MARK} {SHARED_LINE}"
# skald.js's src(): the referring site and utm_source, in sessionStorage, IDs on or off.
SOURCE = ("When you arrive from another site or a campaign link, the script keeps that site's "
          "name and the link's campaign source in your browser's session storage, so the "
          "visit's later pages carry the same source. Your browser deletes it when you close "
          "the tab.")
INTRO = "How we measure visits to this site:"


def _days(n: int) -> str:
    return f"{n} day" if n == 1 else f"{n} days"


def _address(mode: str, days: int, city: bool, keep: bool = False) -> str:
    place = "country and city" if city else "country"
    period = "until you ask us to delete it" if keep else f"for {_days(days)}"
    if mode == policy.FULL:
        return (f"We keep each visit's IP address with its browser, the pages it read and "
                f"where it came from, {period}, so that one visitor's visits can be "
                f"followed across days. The visit's {place} is looked up from the address.")
    if mode == policy.SHORT:
        return (f"We keep each visit's IP address shortened, with its last part removed: "
                f"203.0.113.57 is kept as 203.0.113.0, and an IPv6 address keeps only its "
                f"first 48 bits. A shortened address no longer points to one device. It is "
                f"kept with the visit's browser, the pages it read and where it came from, "
                f"{period}. The visit's {place} is looked up from the full address "
                f"before it is shortened.")
    return ("We do not keep IP addresses with the visits we count. Each visit is counted "
            "without its address, and the totals hold no address.")


def _kept(lead_days: int, what: str = "them") -> str:
    """How long a lead is kept, as the notice says it."""
    return f"until you ask us to delete {what}" if lead_days == 0 else f"for {_days(lead_days)}"


def _beacon(config: dict, lead_days: int, vid_days: int) -> list[str]:
    from ..beacon import share_subdomains, visitor_ids
    out = ["Our pages also load a small script from our analytics server. It counts clicks "
           "and form steps, never what you type in a form."]
    if visitor_ids(config):
        out += ["The script keeps a random visitor ID in your browser's local storage, so "
                "visits from the same browser can be linked. It holds no name or email.",
                f"We keep the pages read with a visitor ID {_kept(vid_days)}. When you "
                f"send us a form or book a call, the pages read with that ID are kept with "
                f"it, {_kept(lead_days)}.",
                # Shared in Skald: certain, so no "keep this line only if".
                SHARED_LINE if share_subdomains(config) else SHARED]
    else:
        out.append("The script keeps no ID.")
    out += [SOURCE,
            "If your browser sends Do Not Track or Global Privacy Control, the script does "
            "nothing at all.",
            f"{CONSENT} The script waits for your consent in our consent banner: until you "
            f"agree, it sends nothing, keeps no ID and stores nothing in your browser."]
    return out


def wording(config: dict, folder=None) -> dict:
    """{"intro", "items", "text", "placeholders", "note", "uses"} for this
    site (see the module). `uses` says which settings the text was made from."""
    from ..beacon import share_subdomains, visitor_ids
    from ..events import enabled as beacon_on
    mode = policy.ip_mode(config, folder)
    days = policy.keep_days(config)
    full = policy.identity_full(config, folder)
    from ..conversions.people_days import kept_days
    from ..conversions.store import keep_days, vid_days
    lead_days, page_days = keep_days(config), vid_days(config)
    name_days = kept_days(config)
    from ..config import site_name
    from ..keep_everything import Keeper
    keep = Keeper(config, folder)(site_name(config))
    if keep:                            # nothing goes by itself: kept until asked
        lead_days = page_days = name_days = 0
    tag = bool(beacon_on(config))
    ids = tag and visitor_ids(config)
    shared = bool(ids and share_subdomains(config))
    city = bool(setting(config or {}, "logs", "city_db"))
    items = [
        "We count visits from our web server's own access log. Reading the log sets no "
        "cookie and stores nothing on your device.",
        f"The access log itself holds each request's full IP address and browser, and is "
        f"kept for {LOG_DAYS}. Our admins can see the last 6 hours of requests, and "
        f"today's AI activity, with their addresses; these are not kept longer.",
        _address(mode, days, city, keep),
        (f"When you send us a form or book a call, we keep your name and email with it, so "
         f"we can see which visits led to it. We keep them {_kept(name_days)}."
         + (f" After that we keep the form or booking without your name and email, "
            f"{_kept(lead_days, 'it')}." if name_days != lead_days else "")) if full else
        ("When you send us a form or book a call, our analytics keep no name or email "
         "with it."),
    ]
    if tag:
        items += _beacon(config, lead_days, page_days)
    ask = "your IP address" + (" or the email you used" if full else "")
    items.append(f"To ask us to delete what we keep about you, write to {CONTACT} with "
                 f"{ask}. We delete it everywhere our analytics keep it.")
    placeholders = [CONTACT, LOG_DAYS] + ([CONSENT] if tag else []) + \
        ([SHARED_MARK] if ids and not shared else [])
    return {"intro": INTRO, "items": items,
            "text": INTRO + "\n\n" + "\n".join(f"- {i}" for i in items),
            "placeholders": placeholders, "note": NOTE,
            "uses": {"ip_mode": mode, "keep_days": days,
                     "identity": "full" if full else "anonymous", "script_tag": tag,
                     "visitor_ids": ids, "share_subdomains": shared,
                     "lead_days": lead_days, "name_days": name_days,
                     "keep_everything": keep,
                     "vid_days": page_days}}

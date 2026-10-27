"""Keep only some Calendly or Cal.com event types for a site.

One Calendly account often books for several businesses, and a Calendly
webhook subscription cannot be limited to some event types. So a site may
name the event types that are its own:

    hooks.calendly.event_types   event-type URIs (https://api.calendly.com/
                                 event_types/<uuid>), their uuids, or
                                 booking-page slugs ("demo", or the page's
                                 address https://calendly.com/acme/demo)
    hooks.calcom.event_types     event-type ids (1234) or slugs ("30min", or
                                 the page's address https://cal.com/acme/30min)

Set in Settings > Leads & tools (a settings row for the site, settings_store
"hooks.calendly.event_types"), or in config.yml: nested
`hooks: {calendly: {event_types: [...]}}` (PyYAML), or flat
`hooks: {calendly_event_types: [...]}` (the small parser). Empty or unset:
every event is kept, as before.

When set, an event of another type is answered 200 and logged in the
delivery log as "ignored: other event type" (with the type it named, so the
right one can be copied), and nothing else: no spool line, no row. An event
that names no type (Calendly's no-show names only the invitee) is kept when
its booking (the same external ref, for the same tool and site) is already
stored, else ignored the same way.

Calendly's webhook names the event type by its URI and its name, never the
booking page's slug: a slug is compared with the name written as a slug
("Acme demo" -> "acme-demo"). A renamed event type no longer matches its
old slug; its URI always does.
"""
from __future__ import annotations

import re

TOOLS = ("calendly", "calcom")
MAX_ITEMS = 50
ITEM = re.compile(r"^[\x21-\x7e]{1,300}$")
IGNORED = "ignored: other event type"


def setting_key(tool: str) -> str:
    return f"hooks.{tool}.event_types"


def _items(raw) -> list[str]:
    if raw in (None, "", []):
        return []
    if isinstance(raw, str):
        raw = raw.replace(",", " ").split()
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def from_config(config: dict, tool: str) -> list[str]:
    """The list config.yml gives: nested hooks.<tool>.event_types, else flat
    hooks.<tool>_event_types."""
    hooks = (config or {}).get("hooks")
    if not isinstance(hooks, dict):
        return []
    nested = hooks.get(tool)
    if isinstance(nested, dict) and nested.get("event_types") not in (None, "", []):
        return _items(nested.get("event_types"))
    return _items(hooks.get(f"{tool}_event_types"))


def validate(raw) -> list[str]:
    """The list as stored: each item one printable word (no spaces), at most
    300 characters, at most MAX_ITEMS, each once. ValueError in plain words."""
    if raw is not None and not isinstance(raw, (str, list, tuple)):
        raise ValueError("Event types are a list.")
    if isinstance(raw, (list, tuple)) and not all(isinstance(x, (str, int)) for x in raw):
        raise ValueError("Each event type is one word: a URI, an id or a slug.")
    out: list[str] = []
    for item in _items(raw):
        if not ITEM.match(item):
            raise ValueError(f"Not an event type: {item[:40]!r}. Use its URI, id or slug.")
        if item not in out:
            out.append(item)
    if len(out) > MAX_ITEMS:
        raise ValueError(f"At most {MAX_ITEMS} event types.")
    return out


def wanted(site_config: dict, site: str, tool: str, folder=None) -> list[str]:
    """The site's list for `tool`: its settings row, else config.yml; [] when
    every event is kept."""
    if tool not in TOOLS:
        return []
    try:
        from ..settings_store import explain
        got = explain(site_config, site, live_dir=folder).get(setting_key(tool))
        if got is not None:
            return _items(got["value"])
    except Exception:                  # noqa: BLE001 - no accounts file: the config alone
        pass
    return from_config(site_config, tool)


def slug(text) -> str:
    """"Acme demo" -> "acme-demo"."""
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").strip().lower()).strip("-")


def _forms(item: str) -> set[str]:
    """The ways one listed item may match: itself, and for an address its
    last path part (a uuid, an id or a slug)."""
    low = item.strip().lower().rstrip("/")
    out = {low}
    if "/" in low:
        out.add(low.rsplit("/", 1)[-1].split("?", 1)[0])
    return {x for x in out if x}


def named(tool: str, payload) -> tuple[set[str], str | None]:
    """(the identifiers the event gives for its type, a short label for the
    log). Empty when the event names no type."""
    if not isinstance(payload, dict) or not isinstance(payload.get("payload"), dict):
        return set(), None
    inner = payload["payload"]
    found: set[str] = set()
    label = None
    if tool == "calendly":
        event = inner.get("scheduled_event")
        event = event if isinstance(event, dict) else {}
        uri = event.get("event_type") or inner.get("event_type")
        if isinstance(uri, str) and uri.strip():
            found |= _forms(uri)
            label = uri.strip()[:200]
        name = event.get("name")
        if isinstance(name, str) and slug(name):
            found.add(slug(name))
            label = label or name.strip()[:80]
    elif tool == "calcom":
        ident = inner.get("eventTypeId")
        if ident not in (None, "") and not isinstance(ident, bool):
            found.add(str(ident).strip().lower())
            label = f"id {ident}"
        kind = inner.get("type") or inner.get("eventTypeSlug")
        if isinstance(kind, str) and kind.strip():
            found.add(kind.strip().lower())
            label = (label + f", slug {kind.strip()}" if label else kind.strip())[:200]
    return found, label


def decide(tool: str, payload, listed: list[str], booked=None) -> tuple[bool, str | None]:
    """(keep, why not) for one verified event. `booked(ref)` says whether the
    booking an event without a type belongs to is stored already."""
    if tool not in TOOLS or not listed:
        return True, None
    allowed: set[str] = set()
    for item in listed:
        allowed |= _forms(item)
    found, label = named(tool, payload)
    if found:
        if found & allowed:
            return True, None
        return False, f"{IGNORED} ({label})" if label else IGNORED
    ref = _booking_ref(tool, payload)
    if ref and booked is not None and booked(ref):
        return True, None
    return False, f"{IGNORED} (it names none, and its booking is not kept)"


def _booking_ref(tool: str, payload) -> str | None:
    """The external ref of the booking an event belongs to (what the adapter
    keeps as external_ref)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("payload"), dict):
        return None
    inner = payload["payload"]
    if tool == "calendly":
        who = inner.get("invitee") if isinstance(inner.get("invitee"), str) else inner.get("uri")
        return str(who).strip()[:300] if isinstance(who, str) and who.strip() else None
    uid = inner.get("uid")
    return str(uid).strip()[:120] if isinstance(uid, (str, int)) and str(uid).strip() else None

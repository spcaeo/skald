"""`lead`: a site's own server or CMS telling Skald a lead was made.

POST /traffic-hooks/<site>/lead, signed with Skald's scheme:

    X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">

with the hook's secret; refused when t is more than 5 minutes off. Body:

    external_ref  the lead's own id in the site (required)
    action        what was done: "demo", "signup", "contact" (required, a token;
                  "booking" is read as "demo", "checkout" as "paid": ALIASES)
    stage         one of conversions.STAGES (default "completed")
    at            when (ISO time or Unix seconds; default: when it arrived). A
                  time without an offset ("2026-09-25", "2026-09-25T08:00:00")
                  is read in the site's time zone; the delivery log says so
    vid           the visitor ID the page had
    first_touch, last_touch   {referrer, landing, utm_source, utm_medium,
                  utm_campaign, utm_content, utm_term, gclid, ..., at}
    landing, campaign, source  when the site worked them out itself
    country or ip             two letters, or the visitor's address: Skald
                              looks up the country and drops the address
    device or user_agent      Desktop/Mobile/Tablet, or the agent: Skald
                              works out the device and drops the agent
    visits_before             visits before this one, a whole number
    name, email               kept only when the site's identity is full
    label         optional: a short lowercase token that sorts the leads of
                  one action ("sales", "support"; conversions.LABEL), trimmed
                  and lower-cased first. Not one: the lead is kept without a
                  label and the delivery log says so (never refused for it)
    test          optional, a JSON boolean: true keeps this delivery's row
                  marked test (store.TEST_SENT: listed, never counted); false
                  or absent, a real lead. Each delivery says it for itself: an
                  earlier stage sent as test makes no later one test. Not a
                  boolean: ignored with a note, like a bad label

GET /traffic-hooks/<site>/leads (conversions/reconcile.py), the leads Skald
holds, is signed with the same secret over the method and the request target
(the path and the query exactly as sent; no "?" without a query):

    X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.GET <target>">

POST /traffic-hooks/<site>/leads/test (conversions/marks.py) marks every
stage of some refs as test, or not; signed exactly like the lead POST.
"""
from __future__ import annotations

from .. import ACTION, LABEL, SITE_VID, STAGES, action_name
from . import Invalid, naive, sign_timed, text, touch, verify_timed, when

HEADER = "x-skald-signature"
LABEL_NOTE = ("the label was not a short lowercase token (letters, digits, - or _, at most "
              "40): kept without a label")
TEST_NOTE = "test was not true or false: ignored, kept as a real lead"


def verify(headers: dict, body: bytes, secret: str, now: float) -> bool:
    return verify_timed(headers.get(HEADER, ""), body, secret, now)


def sign(body: bytes, secret: str, now: float, method: str = "POST", uri: str = "") -> dict:
    return {"X-Skald-Signature": sign_timed(body, secret, now)}


def _get_message(target: str) -> bytes:
    return b"GET " + target.encode("utf-8", "surrogateescape")


def verify_get(headers: dict, target: str, secret: str, now: float) -> bool:
    """A signed GET: the same scheme, window and constant-time compare as a
    POST, over "GET <target>" in place of the body."""
    return verify_timed(headers.get(HEADER, ""), _get_message(target), secret, now)


def sign_get(target: str, secret: str, now: float) -> dict:
    return {"X-Skald-Signature": sign_timed(_get_message(target), secret, now)}


def label_of(raw) -> tuple[str | None, bool]:
    """(the label or None, True when one was sent but is not a label)."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, False
    if not isinstance(raw, str):
        return None, True
    got = raw.strip().lower()
    return (got, False) if LABEL.match(got) else (None, True)


def test_of(raw) -> tuple[bool, bool]:
    """(sent as test, True when `test` was sent but is not a JSON boolean).
    null is as absent."""
    if raw is None or isinstance(raw, bool):
        return raw is True, False
    return False, True


def record(item: dict, tz=None) -> dict:
    """One lead object as a record. Invalid when it breaks the shape. Times
    without an offset are read in `tz`, the site's zone; `naive_at` is then
    True, for the delivery log."""
    if not isinstance(item, dict):
        raise Invalid("a lead is a JSON object")
    ref = text(item.get("external_ref"), 120)
    if not ref:
        raise Invalid("external_ref is required")
    action = action_name(item.get("action"))
    if not ACTION.match(action):
        raise Invalid("action must be a short lowercase token")
    stage = str(item.get("stage") or "completed").strip().lower()
    if stage not in STAGES:
        raise Invalid(f"stage must be one of {', '.join(STAGES)}")
    at = None
    if item.get("at") not in (None, ""):
        at = when(item.get("at"), tz)
        if at is None:
            raise Invalid("at is not a time")
    vid = text(item.get("vid"), 80)
    if vid and not SITE_VID.match(vid):
        vid = None
    visits = item.get("visits_before")
    if isinstance(visits, bool) or not isinstance(visits, int) or not 0 <= visits <= 100000:
        visits = None
    first = touch(item.get("first_touch"), tz)
    last = item.get("last_touch")
    times = [item.get("at"), item.get("first_touch_at"),
             *[t.get("at") for t in (item.get("first_touch"), last) if isinstance(t, dict)]]
    label, dropped = label_of(item.get("label"))
    test, test_dropped = test_of(item.get("test"))
    return {
        "label": label, "label_dropped": dropped, "test": test, "test_dropped": test_dropped,
        "action": action, "stage": stage, "external_ref": ref, "at": at, "vid": vid,
        "first_touch": first, "last_touch": touch(last, tz),
        "landing": text(item.get("landing"), 300), "campaign": text(item.get("campaign"), 120),
        "source_type": text(item.get("source"), 40), "country": text(item.get("country"), 2),
        "ip": text(item.get("ip"), 64), "device": text(item.get("device"), 20),
        "user_agent": text(item.get("user_agent"), 500), "name": text(item.get("name")),
        "email": text(item.get("email"), 320), "visits_before": visits,
        "first_touch_at": when(item.get("first_touch_at"), tz) or (first or {}).get("at"),
        "naive_at": any(naive(t) for t in times),
    }


def to_records(payload, site_config: dict | None = None, tz=None) -> list[dict]:
    return [record(payload, tz)]


def sample(site: str, now: float) -> dict:
    return {"external_ref": f"skald-test-{int(now)}", "action": "demo", "stage": "completed",
            "at": int(now), "vid": "skv_" + "A" * 22,
            "first_touch": {"referrer": "https://www.google.com/", "landing": "/",
                            "at": int(now) - 86400 * 3},
            "last_touch": {"landing": "/pricing/", "utm_source": "newsletter",
                           "utm_medium": "email", "utm_campaign": "october"},
            "country": "CA", "device": "Desktop", "visits_before": 2}


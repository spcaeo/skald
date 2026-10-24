"""Skald lead helper for __SITE__: one file, one function (Python 3.8 or later).

    from skald_lead import skald_lead
    skald_lead(entry_id, "contact", email=email, name=name)

It tells Skald a lead was made: a signed POST to
__URL__
Call it after your form is saved. It waits at most 3 seconds, never raises,
and returns True when Skald kept the lead (False otherwise: you can send it
again later, a repeat is never counted twice).

__SECRET_NOTE__

ref     your own id for the lead (the same lead always sends the same id)
action  a short lowercase word: "contact", "demo", "signup", "trial"
extra   any other field, such as label="sales", stage="won", test=True,
        vid=request.cookies.get("skald_vid"). See README.md.
        Money (Skald 2.32): value=49.99, currency="USD" (the amount in the
        currency's units), customer_ref="your-customer-id" (never an email),
        tags={"plan": "pro"}. A renewal: stage="paid" with the invoice's own
        ref and the same customer_ref. A refund: stage="refunded" on the
        sale's ref, value = the total refunded so far (no value: all of it).
"""
import hashlib
import hmac
import json
import os
import re
import time
import urllib.request

SKALD_URL = "__URL__"
EMBEDDED_SECRET = "__SECRET__"
VID = re.compile(r"^skv_[A-Za-z0-9_-]{22}$")


def skald_lead(ref, action, email=None, name=None, **extra):
    """Send one lead to Skald. True when it was kept."""
    try:
        secret = os.environ.get("SKALD_LEAD_SECRET") or EMBEDDED_SECRET
        if not secret or not ref or not action:
            return False
        lead = dict(extra, external_ref=str(ref), action=str(action))
        if email:
            lead["email"] = str(email)
        if name:
            lead["name"] = str(name)
        if "vid" in lead and not VID.match(str(lead["vid"] or "")):
            del lead["vid"]
        body = json.dumps(lead, default=str).encode("utf-8")   # a Decimal value as its text
        t = str(int(time.time()))
        sig = hmac.new(secret.encode("utf-8"), t.encode() + b"." + body,
                       hashlib.sha256).hexdigest()
        req = urllib.request.Request(SKALD_URL, data=body, method="POST", headers={
            "Content-Type": "application/json", "User-Agent": "skald-lead-python/1",
            "X-Skald-Signature": "t=%s,v1=%s" % (t, sig)})
        with urllib.request.urlopen(req, timeout=3) as res:
            return 200 <= res.status < 300
    except Exception:  # noqa: BLE001 - never break the caller's form
        return False

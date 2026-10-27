"""Settings > Billing and Stripe's webhook, on the refresh helper
(refresh_server.py). Only with saas.enabled (and access.mode: sessions);
otherwise every route answers 404.

  GET  <page>/billing            plan, status, usage this month against the
                                 limits, trial days left, the plans to choose
                                 from; the organisation's owners, and its
                                 admins to read (the usage alerts mail
                                 them and link here); `can_change` says which
  POST <page>/billing/checkout   {plan}: a Stripe Checkout Session -> {url}
  POST <page>/billing/portal     Stripe's customer portal -> {url}
  POST /traffic-hooks/_billing/stripe
                                 Stripe's signed events (stripe_events.py)

<page> is /traffic/<site>/[<view>/]. The page routes need a session, the
site's organisation's owner role (admin for the GET), and on a POST the same-origin check and
X-Skald-CSRF (team_api's rules). Checkout and the portal need
saas.billing: stripe. The return addresses start with the install's base
URL (accounts/links.py), never the request's Host header. The routes stay
open when the organisation is read-only: paying is how it ends.

The webhook is public (Stripe's servers call it): a body of at most 64 KiB,
the Stripe-Signature checked over the raw bytes BEFORE it is parsed (the
verifier conversions/adapters/stripe.py uses, 5 minutes' tolerance), with
the endpoint's signing secret. It sits under /traffic-hooks/ with a name no
site can have ("_billing"), served by this helper, not the beacon helper.

Secrets (never in the config, never in an answer):
  the secret key      env SKALD_STRIPE_KEY, else secrets.json "billing/stripe_key"
  the signing secret  env SKALD_STRIPE_WEBHOOK_SECRET, else "billing/stripe_webhook"
secrets.json is the file beside the history (conversions/secrets_store.py,
0600); `skald billing secret key|webhook` writes them.
"""
from __future__ import annotations

import json
import os
import re
import time

from . import billing_on, enabled, limits, plans, stripe_client, stripe_events
from .. import auth_api
from ..accounts import auditlog, links, sessions, users
from ..auth_api import answer, csrf_ok, read_json, text

PAGE = r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
PATH = re.compile(PAGE + r"(?P<act>billing(?:/(?:checkout|portal))?)$")
HOOK_PATH = "/traffic-hooks/_billing/stripe"
MAX_HOOK_BODY = 64 * 1024
KEY_NAME, KEY_ENV = "billing/stripe_key", "SKALD_STRIPE_KEY"
HOOK_NAME, HOOK_ENV = "billing/stripe_webhook", "SKALD_STRIPE_WEBHOOK_SECRET"
OWNER_WORDS = "Only an owner of the organisation can see and change billing."
CHANGE_WORDS = "Only an owner of the organisation can change billing."
STRIPE_HOSTS = ("https://checkout.stripe.com/", "https://billing.stripe.com/")


def match(path: str):
    path = path.split("?", 1)[0]
    return None if ".." in path else PATH.match(path)


def is_billing(path: str) -> bool:
    return match(path) is not None


def is_hook(path: str) -> bool:
    return path.split("?", 1)[0] == HOOK_PATH


def secret(config, live_dir, name: str, env: str) -> str | None:
    """A billing secret: the environment first, then secrets.json. None when
    not set (or when secrets.json is readable by others: refused)."""
    from .. import settings_store
    from ..conversions.secrets_store import Exposed, load
    value = os.environ.get(env)
    if value:
        return value
    path = settings_store.secrets_path(config, live_dir)
    if path is None:
        return None
    try:
        got = load(path).get(name)
    except Exposed:
        auth_api.note("billing: secrets.json is readable by others; it is not used")
        return None
    return str(got) if got else None


# ------------------------------------------------------------- the page

def handle(h, write: bool, config, live_dir, allowed: set[str], same_origin,
           history_path=None) -> None:
    if not enabled(config):
        return answer(h, 404, {"ok": False, "error": "not found"})
    m = match(h.path)
    act = m.group("act")
    if write == (act == "billing"):
        return answer(h, 405, {"ok": False, "error": "wrong method"})
    if write and not same_origin(h.headers, allowed):
        return answer(h, 403, {"ok": False, "error": "same-origin requests only"})
    db = auth_api.open_db(config, live_dir)
    if db is None:
        return answer(h, 503, {"ok": False, "error": "accounts are not set up here"})
    try:
        session = sessions.resolve(db, auth_api.cookie_of(h.headers))
        if session is None:
            return answer(h, 401, {"ok": False, "error": "Sign in first."})
        if write and not csrf_ok(session, h.headers):
            return answer(h, 403, {"ok": False, "error": "The page is out of date. "
                                                         "Reload it and try again."})
        role, org = users.site_role(db, session["user_id"], m.group("site"))
        if role is None:
            return answer(h, 403, {"ok": False, "error": "You are not a member here."})
        if role not in ("owner", "admin"):
            return answer(h, 403, {"ok": False, "error": OWNER_WORDS, "role": role})
        if role != "owner" and act != "billing":
            return answer(h, 403, {"ok": False, "error": CHANGE_WORDS, "role": role})
        form = {}
        if write:
            form = read_json(h)
            if form is None:
                return None
        hist = history_path or limits.history_path(config, live_dir)
        if act == "billing":
            return _overview(h, db, org, config, hist, role)
        return _stripe(h, db, act, form, session, org, m.group("site"), config, live_dir,
                       allowed)
    finally:
        db.close()


def _overview(h, db, org, config, hist, role: str = "owner") -> None:
    state = plans.org_state(db, org["id"])
    table = plans.plans(config)
    return answer(h, 200, {
        "ok": True, "org": org["name"], "plan": limits.summary(db, org["id"], config, hist),
        "status": state["plan_status"], "billing": billing_on(config),
        "has_customer": bool(state["stripe_customer"]), "can_change": role == "owner",
        "plans": [{**{k: p[k] for k in ("name", "label", "trial_days", *plans.LIMITS)},
                   "can_buy": bool(p["price_id"]), "current": p["name"] == state["plan"]}
                  for p in table.values()]})


def _stripe(h, db, act, form, session, org, site, config, live_dir, allowed) -> None:
    if not billing_on(config):
        return answer(h, 400, {"ok": False, "error": "Billing is not switched on here."})
    key = secret(config, live_dir, KEY_NAME, KEY_ENV)
    if not key:
        return answer(h, 503, {"ok": False, "error": "Billing is not set up yet: the Stripe "
                                                     "key is missing on the server."})
    base = links.base_url(config, allowed=allowed)
    if base is None:
        return answer(h, 503, {"ok": False, "error": "The server has no base address "
                                                     "(access.base_url) for the way back."})
    back = f"{base}/traffic/{site}/#settings/org/billing"
    state = plans.org_state(db, org["id"])
    try:
        if act == "billing/checkout":
            name = text(form, "plan", 80)
            plan = plans.plans(config).get(name)
            if plan is None or not plan["price_id"]:
                return answer(h, 400, {"ok": False, "error": "That plan cannot be chosen here."})
            got = stripe_client.checkout_session(
                key, org_id=org["id"], plan=name, price_id=plan["price_id"],
                email=session["email"], customer=state["stripe_customer"],
                success_url=back + "?checkout=done", cancel_url=back + "?checkout=cancelled")
            auditlog.record(db, org["id"], session["user_id"], "billing.checkout", name)
        else:
            if not state["stripe_customer"]:
                return answer(h, 400, {"ok": False, "error": "There is no billing account "
                                                             "yet: choose a plan first."})
            got = stripe_client.portal_session(key, customer=state["stripe_customer"],
                                               return_url=back)
            auditlog.record(db, org["id"], session["user_id"], "billing.portal", "")
    except stripe_client.StripeError as why:
        auth_api.note(f"billing: {act} failed")
        return answer(h, 502, {"ok": False, "error": str(why)})
    url = got.get("url")
    if not isinstance(url, str) or not url.startswith(STRIPE_HOSTS):
        return answer(h, 502, {"ok": False, "error": "Stripe's answer had no address."})
    return answer(h, 200, {"ok": True, "url": url})


# ----------------------------------------------------------- the webhook

def _reply(h, code: int, body: dict) -> None:
    data = json.dumps(body, separators=(",", ":")).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json")
    h.send_header("Cache-Control", "no-store")
    h.send_header("Content-Length", str(len(data)))
    if code in (411, 413):
        h.send_header("Connection", "close")
        h.close_connection = True
    h.end_headers()
    h.wfile.write(data)


def hook(h, config, live_dir, now=None) -> None:
    """POST /traffic-hooks/_billing/stripe."""
    from ..conversions.adapters import stripe as signature
    if not billing_on(config):
        return _reply(h, 404, {"error": "not found"})
    raw_length = h.headers.get("Content-Length")
    if raw_length is None:
        return _reply(h, 411, {"error": "length required"})
    try:
        length = int(raw_length)
    except ValueError:
        return _reply(h, 400, {"error": "bad length"})
    if length < 0 or length > MAX_HOOK_BODY:
        return _reply(h, 413, {"error": "too large"})
    body = h.rfile.read(length) if length else b""
    key = secret(config, live_dir, HOOK_NAME, HOOK_ENV)
    if not key:
        auth_api.note("billing: a Stripe event came but the signing secret is not set")
        return _reply(h, 503, {"error": "not set up"})
    headers = {k.lower(): v for k, v in h.headers.items()}
    if not signature.verify(headers, body, key, time.time() if now is None else now):
        return _reply(h, 401, {"error": "bad signature"})
    try:
        event = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _reply(h, 400, {"error": "not JSON"})
    db = auth_api.open_db(config, live_dir)
    if db is None:
        return _reply(h, 503, {"error": "accounts are not set up here"})
    try:
        outcome = stripe_events.apply(db, event, config)
    except stripe_events.Invalid as why:
        return _reply(h, 400, {"error": str(why)})
    finally:
        db.close()
    return _reply(h, 200, {"ok": True, "outcome": outcome})

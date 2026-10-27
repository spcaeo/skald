"""Phase 5a billing and limits over real HTTP (saas/billing_api.py,
stripe_client.py, stripe_events.py; the small checks in team_api.py and
settings_api.py): the Stripe requests built right (a fake opener, never the
network), Settings > Billing for owners, the signed webhook with its state
changes and idempotency, the grace period's read-only state, the member and
retention limits, /me's plan block, and saas off -> 404 and no limit.

Secrets are made up ("sk_test_..." is not a real key); addresses example.com.
"""
from __future__ import annotations

import io
import json
import sys
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, ORIGIN, SAME, Server  # noqa: E402

from skald import accounts  # noqa: E402
from skald.conversions import secrets_store  # noqa: E402
from skald.conversions.adapters import stripe as signature  # noqa: E402
from skald.saas import plans, stripe_client  # noqa: E402

T = f"/traffic/{A}/"
HOOK = "/traffic-hooks/_billing/stripe"
KEY, WHSEC = "sk_test_madeup", "whsec_madeup"
PLANS = {"free": {"sites": 1, "members": 3, "retention_days_max": 90},
         "pro": {"sites": 5, "members": 10, "retention_days_max": 400,
                 "price_id": "price_pro_test", "trial_days": 14, "label": "Pro"}}


class FakeOpener:
    """Records each request; answers `reply` (a dict) or raises `error`."""

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.requests = reply, error, []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        if self.error is not None:
            raise self.error
        return io.BytesIO(json.dumps(self.reply).encode())

    def form(self, n=-1) -> dict:
        return {k: v[0] for k, v in parse_qs(self.requests[n].data.decode()).items()}


class Client(unittest.TestCase):
    def test_flatten(self):
        self.assertEqual(stripe_client.flatten({"a": {"b": 1}, "l": [{"x": 2}], "n": None,
                                                "t": True}),
                         [("a[b]", "1"), ("l[0][x]", "2"), ("t", "true")])

    def test_checkout_request(self):
        opener = FakeOpener({"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/cs_1"})
        got = stripe_client.checkout_session(
            KEY, org_id=7, plan="pro", price_id="price_pro_test", email="o@example.com",
            customer=None, success_url="https://www.example.com/ok",
            cancel_url="https://www.example.com/no", opener=opener)
        self.assertEqual(got["id"], "cs_1")
        req = opener.requests[0]
        self.assertEqual(req.full_url, "https://api.stripe.com/v1/checkout/sessions")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Authorization"), f"Bearer {KEY}")
        self.assertEqual(req.get_header("Content-type"), "application/x-www-form-urlencoded")
        self.assertEqual(opener.form(), {
            "mode": "subscription", "line_items[0][price]": "price_pro_test",
            "line_items[0][quantity]": "1", "client_reference_id": "7",
            "success_url": "https://www.example.com/ok", "cancel_url": "https://www.example.com/no",
            "metadata[org_id]": "7", "metadata[plan]": "pro",
            "subscription_data[metadata][org_id]": "7",
            "subscription_data[metadata][plan]": "pro", "customer_email": "o@example.com"})
        stripe_client.checkout_session(
            KEY, org_id=7, plan="pro", price_id="p", email="o@example.com", customer="cus_1",
            success_url="s", cancel_url="c", opener=opener)
        self.assertEqual(opener.form()["customer"], "cus_1")
        self.assertNotIn("customer_email", opener.form())

    def test_portal_request(self):
        opener = FakeOpener({"url": "https://billing.stripe.com/p/session/x"})
        stripe_client.portal_session(KEY, customer="cus_1", return_url="https://w.example.com/",
                                     opener=opener)
        self.assertEqual(opener.requests[0].full_url,
                         "https://api.stripe.com/v1/billing_portal/sessions")
        self.assertEqual(opener.form(), {"customer": "cus_1",
                                         "return_url": "https://w.example.com/"})

    def test_errors_never_carry_the_key(self):
        def refused():
            return urllib.error.HTTPError("https://api.stripe.com/x", 400, "Bad", {}, io.BytesIO(
                b'{"error": {"message": "No such price"}}'))
        for error in (refused(), urllib.error.URLError("down"), OSError("reset")):
            with self.assertRaises(stripe_client.StripeError) as got:
                stripe_client.call(KEY, "/v1/x", {}, FakeOpener(error=error))
            self.assertNotIn(KEY, str(got.exception))
        with self.assertRaises(stripe_client.StripeError) as got:
            stripe_client.call(KEY, "/v1/x", {}, FakeOpener(error=refused()))
        self.assertIn("No such price", str(got.exception))


class Case(Server):
    SAAS = {"enabled": True, "billing": "stripe", "plans": PLANS, "default_plan": "pro"}

    def setUp(self):
        super().setUp()
        self.config["saas"] = json.loads(json.dumps(self.SAAS))
        self.opener = FakeOpener({"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/cs_1"})
        never = mock.patch.object(stripe_client, "OPENER", self.opener)
        never.start()
        self.addCleanup(never.stop)
        secrets_store.put(self.live / "secrets.json", "billing/stripe_key", KEY)
        secrets_store.put(self.live / "secrets.json", "billing/stripe_webhook", WHSEC)
        self.org = self.alpha["id"]

    def state(self, org=None):
        db = self.db()
        try:
            return plans.org_state(db, org or self.org)
        finally:
            db.close()

    def set_plan(self, plan, status, **kw):
        db = self.db()
        try:
            plans.set_plan(db, self.org, plan, status, "cli", **kw)
        finally:
            db.close()

    def event(self, kind, obj, eid="evt_1", created=None, secret=WHSEC, raw=None):
        body = raw if raw is not None else json.dumps(
            {"id": eid, "object": "event", "type": kind,
             "created": created or int(time.time()), "data": {"object": obj}}).encode()
        headers = {"Content-Type": "application/json",
                   **signature.sign(body, secret, time.time())}
        return self.call("POST", HOOK, headers=headers, raw=body)


class Page(Case):
    def test_owner_sees_the_plans_and_usage(self):
        self.set_plan("pro", "trialing", trial_ends_at="2026-10-25T14:00:00Z")
        cookie, _ = self.session()
        got = self.call("GET", T + "billing", cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["plan"]["name"], "pro")
        self.assertEqual(got.json["plan"]["trial_days_left"], 14)
        self.assertEqual([p["name"] for p in got.json["plans"]], ["free", "pro"])
        self.assertEqual([p["can_buy"] for p in got.json["plans"]], [False, True])
        self.assertNotIn("price_pro_test", got.raw.decode())
        self.assertNotIn(KEY, got.raw.decode())

    def test_only_owners_change_admins_read(self):
        # Admins get the usage alerts, so they may read the page; only owners change it.
        cookie, csrf = self.session("admin@example.com")
        got = self.call("GET", T + "billing", cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        self.assertFalse(got.json["can_change"])
        self.assertEqual(self.post(T + "billing/checkout", {"plan": "pro"}, cookie, csrf).status,
                         403)
        self.assertEqual(self.post(T + "billing/portal", {}, cookie, csrf).status, 403)
        cookie, _ = self.session("viewer@example.com")
        self.assertEqual(self.call("GET", T + "billing", cookie=cookie).status, 403)
        cookie, _ = self.session()
        self.assertTrue(self.call("GET", T + "billing", cookie=cookie).json["can_change"])
        self.assertEqual(self.call("GET", T + "billing").status, 401)

    def test_checkout(self):
        cookie, csrf = self.session()
        self.assertEqual(self.post(T + "billing/checkout", {"plan": "pro"}, cookie, None).status,
                         403)
        got = self.post(T + "billing/checkout", {"plan": "pro"}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["url"], "https://checkout.stripe.com/c/pay/cs_1")
        form = self.opener.form()
        self.assertEqual(form["success_url"],
                         f"{ORIGIN}/traffic/{A}/#settings/org/billing?checkout=done")
        self.assertEqual(form["client_reference_id"], str(self.org))
        self.assertEqual(form["customer_email"], "owner@example.com")
        self.assertEqual(self.post(T + "billing/checkout", {"plan": "free"}, cookie,
                                   csrf).status, 400)          # no price: not for sale
        self.opener.reply = {"url": "https://evil.example.com/"}
        self.assertEqual(self.post(T + "billing/checkout", {"plan": "pro"}, cookie,
                                   csrf).status, 502)

    def test_portal_needs_a_customer(self):
        cookie, csrf = self.session()
        self.assertEqual(self.post(T + "billing/portal", {}, cookie, csrf).status, 400)
        self.set_plan("pro", "active", customer="cus_1")
        self.opener.reply = {"url": "https://billing.stripe.com/p/session/x"}
        got = self.post(T + "billing/portal", {}, cookie, csrf)
        self.assertEqual((got.status, got.json["url"]),
                         (200, "https://billing.stripe.com/p/session/x"))
        self.assertEqual(self.opener.form()["customer"], "cus_1")

    def test_no_key_no_billing(self):
        (self.live / "secrets.json").unlink()
        cookie, csrf = self.session()
        self.assertEqual(self.post(T + "billing/checkout", {"plan": "pro"}, cookie,
                                   csrf).status, 503)
        self.config["saas"]["billing"] = ""
        self.assertEqual(self.post(T + "billing/checkout", {"plan": "pro"}, cookie,
                                   csrf).status, 400)
        self.assertEqual(self.opener.requests, [])


class Webhook(Case):
    def test_a_bad_or_missing_signature_changes_nothing(self):
        obj = {"id": "cs_1", "client_reference_id": str(self.org), "customer": "cus_1",
               "subscription": "sub_1", "metadata": {"plan": "pro"}}
        self.assertEqual(self.event("checkout.session.completed", obj, secret="whsec_other")
                         .status, 401)
        self.assertEqual(self.call("POST", HOOK, raw=b"{}",
                                   headers={"Content-Type": "application/json"}).status, 401)
        self.assertIsNone(self.state()["plan"])

    def test_checkout_then_failure_then_cancel(self):
        got = self.event("checkout.session.completed",
                         {"id": "cs_1", "client_reference_id": str(self.org),
                          "customer": "cus_1", "subscription": "sub_1",
                          "metadata": {"plan": "pro", "org_id": str(self.org)}}, "evt_1",
                         created=100)
        self.assertEqual(got.status, 200, got.json)
        state = self.state()
        self.assertEqual((state["plan"], state["plan_status"], state["stripe_customer"],
                          state["stripe_subscription"]), ("pro", "active", "cus_1", "sub_1"))
        got = self.event("invoice.payment_failed", {"id": "in_1", "customer": "cus_1"},
                         "evt_2", created=200)
        self.assertEqual(self.state()["plan_status"], "past_due")
        self.assertEqual(self.state()["past_due_since"], "2026-10-11T14:00:00Z")
        self.event("customer.subscription.updated",
                   {"id": "sub_1", "customer": "cus_1", "status": "active",
                    "items": {"data": [{"price": {"id": "price_pro_test"}}]}}, "evt_3",
                   created=300)
        self.assertEqual(self.state()["plan_status"], "active")
        self.assertIsNone(self.state()["past_due_since"])
        self.event("customer.subscription.deleted",
                   {"id": "sub_1", "customer": "cus_1", "status": "canceled"}, "evt_4",
                   created=400)
        self.assertEqual((self.state()["plan"], self.state()["plan_status"]),
                         ("pro", "canceled"))
        db = self.db()
        try:
            rows = accounts.auditlog.recent(db, self.org, action="billing.plan")
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(r["actor"] == "stripe" for r in rows))
        finally:
            db.close()

    def test_the_same_event_twice_is_applied_once(self):
        obj = {"id": "cs_1", "client_reference_id": str(self.org), "customer": "cus_1",
               "metadata": {"plan": "pro"}}
        first = self.event("checkout.session.completed", obj, "evt_9")
        again = self.event("checkout.session.completed", obj, "evt_9")
        self.assertEqual((first.status, again.status), (200, 200))
        self.assertEqual(again.json["outcome"], "duplicate")
        db = self.db()
        try:
            self.assertEqual(len(accounts.auditlog.recent(db, self.org, action="billing.plan")),
                             1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM billing_events").fetchone()[0], 1)
        finally:
            db.close()

    def test_an_older_event_does_not_undo_a_newer_one(self):
        self.set_plan("pro", "active", subscription="sub_1", customer="cus_1")
        self.event("customer.subscription.updated",
                   {"id": "sub_1", "customer": "cus_1", "status": "active"}, "evt_new",
                   created=500)
        got = self.event("customer.subscription.updated",
                         {"id": "sub_1", "customer": "cus_1", "status": "past_due"}, "evt_old",
                         created=400)
        self.assertIn("newer", got.json["outcome"])
        self.assertEqual(self.state()["plan_status"], "active")

    def test_unknown_org_and_other_events_are_noted_not_applied(self):
        got = self.event("invoice.payment_failed", {"id": "in_1", "customer": "cus_nobody"})
        self.assertEqual(got.status, 200)
        self.assertIn("no organisation", got.json["outcome"])
        got = self.event("charge.refunded", {"id": "ch_1"}, "evt_x")
        self.assertIn("ignored", got.json["outcome"])
        self.assertEqual(self.event("x", {}, raw=b"[1]").status, 400)

    def test_no_secret_or_billing_off(self):
        (self.live / "secrets.json").unlink()
        self.assertEqual(self.event("invoice.payment_failed", {"customer": "c"}).status, 503)
        self.config["saas"]["billing"] = "none"
        self.assertEqual(self.event("invoice.payment_failed", {"customer": "c"}).status, 404)

    def test_too_large(self):
        got = self.call("POST", HOOK, raw=b"x" * (64 * 1024 + 1),
                        headers={"Content-Type": "application/json"})
        self.assertEqual(got.status, 413)


class Limits(Case):
    def test_members_limit_on_invite(self):
        self.set_plan("free", "active")            # 3 members: Alpha has three already
        cookie, csrf = self.session()
        got = self.post(T + "team/invite", {"email": "new@example.com", "role": "viewer"},
                        cookie, csrf)
        self.assertEqual(got.status, 402)
        self.assertIn("3 members", got.json["error"])
        self.set_plan("pro", "active")
        got = self.post(T + "team/invite", {"email": "new@example.com", "role": "viewer"},
                        cookie, csrf)
        self.assertEqual(got.status, 200, got.json)

    def test_retention_max(self):
        self.set_plan("free", "active")            # at most 90 days
        cookie, csrf = self.session()
        got = self.call("GET", T + "settings", cookie=cookie).json
        self.assertEqual(got["settings"]["report.retention_days"]["hi"], 90)
        got = self.post(T + "settings/save", {"report.retention_days": 120, "confirm": A},
                        cookie, csrf)
        self.assertEqual(got.status, 400)
        self.assertIn("at most 90", got.json["error"])
        got = self.post(T + "settings/save", {"report.retention_days": 90, "confirm": A},
                        cookie, csrf)
        self.assertEqual(got.status, 200, got.json)

    def test_grace_period_then_read_only_but_still_readable(self):
        self.set_plan("pro", "past_due")
        cookie, csrf = self.session()
        invite = {"email": "new@example.com", "role": "viewer"}
        self.assertEqual(self.post(T + "team/invite", invite, cookie, csrf).status, 200)
        self.tick(8 * 86400)
        cookie, csrf = self.session()
        got = self.post(T + "team/invite", {"email": "b@example.com", "role": "viewer"},
                        cookie, csrf)
        self.assertEqual(got.status, 402)
        self.assertTrue(got.json["read_only"])
        got = self.post(T + "settings/save", {"mail.daily": False}, cookie, csrf)
        self.assertEqual(got.status, 402)
        self.assertEqual(self.post(T + "tokens/create", {"name": "x"}, cookie, csrf).status,
                         402)
        # Still readable, and billing still open so it can be paid.
        me = self.call("GET", T + "me", cookie=cookie)
        self.assertEqual(me.status, 200)
        self.assertTrue(me.json["plan"]["read_only"])
        self.assertEqual(self.call("GET", T + "api/v1/overview", cookie=cookie).status, 200)
        self.assertEqual(self.call("GET", T + "settings", cookie=cookie).status, 200)
        self.assertEqual(self.post(T + "billing/checkout", {"plan": "pro"}, cookie,
                                   csrf).status, 200)
        # Your own account still works (a password change is not the org's).
        self.assertEqual(self.post(T + "account/name", {"name": "O"}, cookie, csrf).status, 200)

    def test_me_has_the_plan_block(self):
        self.set_plan("free", "active")
        cookie = self.login().cookie
        me = self.call("GET", T + "me", cookie=cookie).json
        self.assertTrue(me["saas"])
        plan = me["plan"]
        self.assertEqual((plan["name"], plan["status"], plan["over"]), ("free", "active", []))
        self.assertEqual(plan["limits"], {"sites": 1, "requests_month": None,
                                          "retention_days_max": 90, "members": 3})
        self.assertEqual(plan["used"], {"sites": 1, "members": 3})
        self.assertIsNone(plan["usage"]["requests"])        # no history: not known, not 0


class Off(Server):
    def test_every_billing_route_is_404_and_no_limit_applies(self):
        db = self.db()
        try:
            plans.set_plan(db, self.alpha["id"], "free", "past_due", "cli")
        finally:
            db.close()
        self.config["saas"] = {"enabled": False, "billing": "stripe", "plans": PLANS}
        cookie, csrf = self.session()
        self.assertEqual(self.call("GET", T + "billing", cookie=cookie).status, 404)
        self.assertEqual(self.post(T + "billing/checkout", {"plan": "pro"}, cookie,
                                   csrf).status, 404)
        self.assertEqual(self.post(T + "billing/portal", {}, cookie, csrf).status, 404)
        body = b"{}"
        got = self.call("POST", HOOK, raw=body, headers={
            "Content-Type": "application/json", **signature.sign(body, WHSEC, time.time())})
        self.assertEqual(got.status, 404)
        self.tick(30 * 86400)
        cookie, csrf = self.session()
        got = self.post(T + "team/invite", {"email": "new@example.com", "role": "viewer"},
                        cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        got = self.post(T + "settings/save", {"report.retention_days": 500}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)

    def test_basic_mode_ignores_saas(self):
        self.config["access"]["mode"] = "basic"
        self.config["saas"] = {"enabled": True, "signup": True, "billing": "stripe"}
        self.assertEqual(self.call("GET", "/traffic-auth/signup").status, 404)
        self.assertEqual(self.call("POST", HOOK, raw=b"{}",
                                   headers={"Content-Type": "application/json"}).status, 404)
        self.assertEqual(self.call("POST", "/traffic-auth/signup", {"email": "a@example.com"},
                                   SAME).status, 404)


if __name__ == "__main__":
    unittest.main()

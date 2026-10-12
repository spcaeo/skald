"""Settings > Integrations over real HTTP (integrations_api.py, sessions
mode): who may see and change it, a hook's secret shown once, the signed
test delivery logged as a test, a tool's own signing secret pasted (Stripe,
HubSpot) and never shown, an incoming hook removed (its secret gone, its
deliveries kept), outgoing webhooks added, tested, rotated and removed, the
audit log without secrets, and 404 in basic mode. Hosts
are example.com; the secrets are made up."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B, Server  # noqa: E402
from test_conversions_outgoing import Catcher  # noqa: E402

from skald import accounts  # noqa: E402
from skald.accounts import auditlog  # noqa: E402
from skald.conversions import secrets_store, store  # noqa: E402

T = f"/traffic/{A}/"
STRIPE = "whsec_" + "Test0Signing0Secret0Made0Up"       # made up
HUBSPOT = "0a1b2c3d-made-up-client-secret"


class Base(Server):
    def setUp(self):
        super().setUp()
        self.config["site"] = {"name": A}
        self.config["integrations"] = {"allow_private_urls": True}

    def get(self, email="owner@example.com", query=""):
        cookie, _ = self.session(email)
        return self.call("GET", T + "integrations" + query, cookie=cookie)

    def do(self, act, body, email="owner@example.com"):
        cookie, csrf = self.session(email)
        return self.post(T + "integrations/" + act, body, cookie, csrf)

    def audit(self):
        db = self.db()
        try:
            return auditlog.recent(db, None)
        finally:
            db.close()


class Reading(Base):
    def test_admins_read_viewers_and_strangers_do_not(self):
        got = self.get("admin@example.com")
        self.assertEqual(got.status, 200, got.json)
        j = got.json
        self.assertEqual((j["site"], j["sites"]), (A, [A]))
        self.assertIn('data-site="alpha.example"', j["script"]["tag"])
        self.assertFalse(j["script"]["visitor_ids"])
        lead = next(t for t in j["tools"] if t["tool"] == "lead")
        self.assertEqual(lead["url"], f"https://www.example.com/traffic-hooks/{A}/lead")
        self.assertEqual((lead["set"], lead["deliveries"]), (False, []))
        self.assertEqual(j["webhooks"], [])
        self.assertIn("lead.won", j["events"])
        self.assertEqual(self.get("viewer@example.com").status, 403)
        cookie, _ = self.session()
        self.assertEqual(self.call("GET", f"/traffic/{B}/integrations", cookie=cookie).status,
                         403)
        self.assertEqual(self.get(query=f"?site={B}").status, 403)
        self.assertEqual(self.call("GET", T + "integrations").status, 401)

    def test_install_admin_sees_every_site(self):
        db = self.db()
        try:
            accounts.set_install_admin(db, self.uids["owner@example.com"], True, "cli")
        finally:
            db.close()
        got = self.get(query=f"?site={B}")
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["sites"], [A, B])
        self.assertFalse(got.json["takes_hooks"])

    def test_post_needs_csrf_and_same_origin(self):
        cookie, csrf = self.session()
        body = {"tool": "lead"}
        self.assertEqual(self.post(T + "integrations/secret", body, cookie, None).status, 403)
        got = self.call("POST", T + "integrations/secret", body, {"Sec-Fetch-Site": "cross-site"},
                        cookie=cookie, csrf=csrf)
        self.assertEqual(got.status, 403)
        self.assertEqual(self.call("GET", T + "integrations/secret", cookie=cookie).status, 405)


class Hooks(Base):
    def test_secret_once_then_a_signed_test(self):
        self.assertEqual(self.do("test", {"tool": "lead"}).status, 409, "no secret yet")
        got = self.do("secret", {"tool": "lead"})
        self.assertEqual(got.status, 200, got.json)
        value = got.json["secret"]
        self.assertTrue(value.startswith("skh_"))
        kept = secrets_store.load(self.live / "secrets.json")
        self.assertEqual(kept[f"hooks/{A}/lead"], value)
        again = self.get().json
        lead = next(t for t in again["tools"] if t["tool"] == "lead")
        self.assertTrue(lead["set"])
        self.assertNotIn(value, json.dumps(again))
        self.assertEqual(self.do("hooks/paste", {"tool": "hubspot",
                                                 "secret": HUBSPOT}).status, 200)
        for tool in ("lead", "calendly", "hubspot"):
            if tool == "calendly":
                self.do("secret", {"tool": tool})
            got = self.do("test", {"tool": tool})
            self.assertEqual(got.status, 200, got.json)
            self.assertEqual(got.json["status"], 200, got.json)
            self.assertTrue(got.json["answer"]["test"])
        lead = next(t for t in self.get().json["tools"] if t["tool"] == "lead")
        self.assertEqual(lead["deliveries"][0]["outcome"], "test")
        db = store.connect(self.live / "conversions.sqlite")
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM conversions").fetchone()[0], 0)
        finally:
            db.close()
        rotated = self.do("secret", {"tool": "lead"}).json
        self.assertTrue(rotated["rotated"])
        log = self.audit()
        self.assertIn("hook.secret", [e["action"] for e in log])
        self.assertNotIn(value, json.dumps(log))
        self.assertEqual(self.do("secret", {"tool": "nope"}).status, 400)

    def test_an_env_secret_cannot_be_rotated_here(self):
        self.config["hooks"] = {f"{A}/stripe": "SKALD_TEST_NOT_SET"}
        got = self.do("secret", {"tool": "stripe"})
        self.assertEqual(got.status, 409)
        self.assertIn("SKALD_TEST_NOT_SET", got.json["error"])


class OwnSecrets(Base):
    """Stripe and HubSpot sign with a secret they make: it is pasted, never
    made here. Calendly, Cal.com and Typeform take one made here or theirs."""

    def tool(self, name):
        return next(t for t in self.get().json["tools"] if t["tool"] == name)

    def test_stripe_and_hubspot_take_a_pasted_secret_not_a_made_one(self):
        for name in ("stripe", "hubspot"):
            t = self.tool(name)
            self.assertEqual((t["make"], t["paste"], t["set"]), (False, True, False))
            self.assertIn(t["secret_from"], ("Stripe", "HubSpot"))
            refused = self.do("secret", {"tool": name})
            self.assertEqual(refused.status, 409)
            self.assertIn("Paste", refused.json["error"])
        got = self.do("hooks/paste", {"tool": "stripe", "secret": f"  {STRIPE}\n"})
        self.assertEqual(got.status, 200, got.json)
        self.assertNotIn(STRIPE, json.dumps(got.json))
        self.assertEqual(secrets_store.load(self.live / "secrets.json")[f"hooks/{A}/stripe"],
                         STRIPE)
        self.assertTrue(self.tool("stripe")["set"])
        self.assertNotIn(STRIPE, json.dumps(self.get().json))
        self.assertTrue(self.do("hooks/paste", {"tool": "stripe", "secret": STRIPE})
                        .json["replaced"])
        log = json.dumps(self.audit())
        self.assertIn("pasted", log)
        self.assertNotIn(STRIPE, log)
        tried = self.do("test", {"tool": "stripe"})
        self.assertEqual(tried.json["status"], 200, tried.json)

    def test_a_pasted_secret_is_checked(self):
        for body, code in (({"tool": "stripe", "secret": ""}, 400),
                           ({"tool": "stripe", "secret": "not-a-stripe-secret-at-all"}, 400),
                           ({"tool": "hubspot", "secret": "has a space in it"}, 400),
                           ({"tool": "hubspot", "secret": "two\nlines-of-secret"}, 400),
                           ({"tool": "hubspot", "secret": "short"}, 400),
                           ({"tool": "hubspot", "secret": "x" * 501}, 400),
                           ({"tool": "lead", "secret": STRIPE}, 400),
                           ({"tool": "json", "secret": STRIPE}, 400),
                           ({"tool": "nope", "secret": STRIPE}, 400)):
            got = self.do("hooks/paste", body)
            self.assertEqual(got.status, code, (body, got.json))
        self.assertEqual(secrets_store.load(self.live / "secrets.json"), {})
        self.assertEqual(self.do("hooks/paste", {"tool": "hubspot", "secret": HUBSPOT},
                                 "viewer@example.com").status, 403)
        cookie, _ = self.session()
        self.assertEqual(self.post(T + "integrations/hooks/paste",
                                   {"tool": "hubspot", "secret": HUBSPOT}, cookie, None).status,
                         403)

    def test_chosen_secret_tools_offer_both_and_skald_signed_only_make(self):
        for name in ("calendly", "calcom", "typeform"):
            t = self.tool(name)
            self.assertEqual((t["make"], t["paste"]), (True, True), name)
        for name in ("lead", "json"):
            t = self.tool(name)
            self.assertEqual((t["make"], t["paste"]), (True, False), name)
        got = self.do("hooks/paste", {"tool": "calendly", "secret": "calendly-made-up-signing-key"})
        self.assertEqual(got.status, 200, got.json)

    def test_an_env_secret_cannot_be_pasted_or_removed_here(self):
        self.config["hooks"] = {f"{A}/stripe": "SKALD_TEST_NOT_SET"}
        for act, body in (("hooks/paste", {"tool": "stripe", "secret": STRIPE}),
                          ("hooks/remove", {"tool": "stripe"})):
            got = self.do(act, body)
            self.assertEqual(got.status, 409, got.json)
            self.assertIn("SKALD_TEST_NOT_SET", got.json["error"])


class RemoveHook(Base):
    def test_remove_drops_the_secret_and_keeps_the_deliveries(self):
        self.assertEqual(self.do("hooks/remove", {"tool": "lead"}).status, 404, "nothing set")
        value = self.do("secret", {"tool": "lead"}).json["secret"]
        self.assertEqual(self.do("test", {"tool": "lead"}).json["status"], 200)
        self.assertEqual(self.do("hooks/remove", {"tool": "lead"}, "viewer@example.com").status,
                         403)
        cookie, _ = self.session()
        self.assertEqual(self.post(T + "integrations/hooks/remove", {"tool": "lead"}, cookie,
                                   None).status, 403)
        got = self.do("hooks/remove", {"tool": "lead"})
        self.assertEqual(got.status, 200, got.json)
        self.assertNotIn(f"hooks/{A}/lead", secrets_store.load(self.live / "secrets.json"))
        lead = next(t for t in self.get().json["tools"] if t["tool"] == "lead")
        self.assertFalse(lead["set"])
        self.assertEqual(lead["deliveries"][0]["outcome"], "test", "the history stays")
        # Further deliveries are refused: the receiver has no secret for it.
        from skald.conversions import hooks as hooks_mod
        receiver = hooks_mod.Receiver(self.config, self.live)
        self.assertIsNone(receiver.secret(A, "lead"))
        self.assertEqual(self.do("test", {"tool": "lead"}).status, 409)
        self.assertEqual(self.do("hooks/remove", {"tool": "lead"}).status, 404)
        self.assertEqual(self.do("hooks/remove", {"tool": "nope"}).status, 400)
        log = self.audit()
        self.assertIn("hook.remove", [e["action"] for e in log])
        self.assertNotIn(value, json.dumps(log))


class Webhooks(Base):
    def setUp(self):
        super().setUp()
        self.catcher = Catcher()
        self.addCleanup(self.catcher.stop)

    def test_add_test_rotate_remove(self):
        bad = self.do("webhooks/add", {"url": "ftp://example.com", "events": ["lead.won"]})
        self.assertEqual(bad.status, 400)
        self.assertEqual(self.do("webhooks/add", {"url": self.catcher.url, "events": []}).status,
                         400)
        got = self.do("webhooks/add", {"url": self.catcher.url,
                                       "events": ["conversion.completed", "lead.won"]})
        self.assertEqual(got.status, 200, got.json)
        wid, value = got.json["webhook"]["id"], got.json["secret"]
        self.assertTrue(value.startswith("skw_"))
        tried = self.do("webhooks/test", {"id": wid})
        self.assertEqual(tried.json["result"]["state"], "sent", tried.json)
        self.assertEqual(len(self.catcher.got), 1)
        listed = self.get().json["webhooks"]
        self.assertEqual([w["id"] for w in listed], [wid])
        self.assertEqual(listed[0]["deliveries"][0]["state"], "sent")
        self.assertNotIn(value, json.dumps(listed))
        new = self.do("webhooks/rotate", {"id": wid}).json["secret"]
        self.assertNotEqual(new, value)
        self.assertEqual(self.do("webhooks/rotate", {"id": 99}).status, 404)
        self.assertEqual(self.do("webhooks/remove", {"id": wid}).status, 200)
        self.assertEqual(self.do("webhooks/remove", {"id": wid}).status, 404)
        self.assertEqual(self.get().json["webhooks"], [])
        actions = [e["action"] for e in self.audit()]
        for a in ("webhook.add", "webhook.test", "webhook.rotate", "webhook.remove"):
            self.assertIn(a, actions)
        self.assertNotIn(new, json.dumps(self.audit()))
        self.assertEqual(self.do("webhooks/add", {"url": self.catcher.url, "events": [
            "lead.won"]}, "viewer@example.com").status, 403)


class Basic(Base):
    MODE = "basic"

    def test_404_in_basic_mode(self):
        self.assertEqual(self.call("GET", T + "integrations").status, 404)


if __name__ == "__main__":
    unittest.main()

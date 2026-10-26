"""Phase 5a pages: signup.html and signup-finish.html follow the sign-in
pages' rules (no inline script or handler, nothing from elsewhere, a POST
form, auth.js and auth.css only), and Settings > Billing & usage is a tab that is
hidden unless /me says the server sells plans to this owner.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import webapp  # noqa: E402

APP = Path(webapp.__file__).resolve().parent
AUTH = APP / "auth"
PAGES = ("signup", "signup-finish")


class SignUpPages(unittest.TestCase):
    def test_same_rules_as_the_sign_in_pages(self):
        for name in PAGES:
            text = (AUTH / f"{name}.html").read_text(encoding="utf-8")
            for attrs, body in re.findall(r"<script([^>]*)>(.*?)</script>", text, re.S):
                self.assertIn("src=", attrs, name)
                self.assertEqual(body.strip(), "", name)
            self.assertNotRegex(text, r"\son[a-z]+\s*=", name)
            self.assertNotRegex(text, r"javascript:", name)
            for url in re.findall(r"(?:src|href|action)=\"([^\"]*)\"", text):
                self.assertFalse(re.match(r"(?:https?:)?//", url), f"{name}.html: {url}")
            self.assertIn('src="/traffic-auth/auth.js"', text)
            self.assertIn('href="/traffic-auth/auth.css"', text)
            self.assertIn(f'data-page="{name}"', text)
            self.assertIn('name="robots" content="noindex, nofollow, noarchive"', text)
            for form in re.findall(r"<form[^>]*>", text):
                self.assertIn('method="post"', form, name)

    def test_auth_js_runs_both_pages(self):
        js = (AUTH / "auth.js").read_text(encoding="utf-8")
        self.assertIn('signup, "signup-finish": signupFinish', js)
        self.assertIn('post("/traffic-auth/signup-finish"', js)


class BillingTab(unittest.TestCase):
    def test_registered_and_hidden_unless_saas(self):
        # 2.40: Settings › Organisation › Billing & usage (js/settings-menu.js).
        menu = (APP / "js" / "settings-menu.js").read_text(encoding="utf-8")
        self.assertIn('route: "settings/org/billing", name: "Billing & usage"', menu)
        pages = (APP / "js" / "tabs" / "settings-pages.js").read_text(encoding="utf-8")
        self.assertIn('"settings/org/billing": billing', pages)
        icons = (APP / "js" / "tabs" / "icons.js").read_text(encoding="utf-8")
        self.assertIn('"settings/org/billing": I(', icons)
        access = (APP / "js" / "access.js").read_text(encoding="utf-8")
        # Owners, and admins to read it (they get the usage alerts); never viewers.
        self.assertIn('if (!ME.saas || !["owner", "admin"].includes(ME.role)) '
                      'HIDDEN.add("settings/org/billing");', access)

    def test_goes_only_to_stripe(self):
        js = (APP / "js" / "tabs" / "billing.js").read_text(encoding="utf-8")
        self.assertIn(r"/^https:\/\/(?:checkout|billing)\.stripe\.com\//", js)
        self.assertRegex(js, r"!STRIPE\.test\(r\.url")
        self.assertNotRegex(js, r"(?:localStorage|sessionStorage)\.setItem")


if __name__ == "__main__":
    unittest.main()

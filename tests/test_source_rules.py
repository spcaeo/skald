"""Source, citation and campaign rules for app referrers, tags and click ids.

Each case is labelled by both roads - the package's labels (classify,
dimensions) and the audit's own (audit_labels, audit._cited) - and the two
must agree, or stored days stop reconciling.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skald import audit, audit_labels, campaigns, classify  # noqa: E402
from skald import dimensions as dim  # noqa: E402

OWN = {"example.com", "www.example.com"}


def main_road(referrer: str, url: str = "/") -> tuple[str, str, str]:
    """(assistant, source type, campaign) as the package labels a reader."""
    cited = classify.cited_by(referrer)
    return cited, dim.source_type(referrer, url, bool(cited), OWN), dim.campaign(url)


def audit_road(referrer: str, url: str = "/") -> tuple[bool, str, str]:
    """(cited?, source type, campaign) as the audit labels the same line."""
    line = SimpleNamespace(referrer=referrer, url=url)
    cited = audit._cited(line)
    return cited, audit_labels.source_of(line, cited, OWN), audit_labels.campaign_of(url)


class BothRoads(unittest.TestCase):
    def check(self, referrer, url, source, campaign=dim.NO_CAMPAIGN, assistant=""):
        with self.subTest(referrer=referrer, url=url):
            self.assertEqual(main_road(referrer, url), (assistant, source, campaign))
            self.assertEqual(audit_road(referrer, url), (bool(assistant), source, campaign))
            line = SimpleNamespace(referrer=referrer, url=url)
            self.assertEqual(audit_labels.referrer_of(line, OWN),
                             dim.referrer_label(referrer, OWN))


class TestAssistantApps(BothRoads):
    """An assistant's phone app sends android-app://<package>/; that is a
    citation, named as the assistant's website is."""

    def test_assistant_apps_are_citations(self):
        for ref, name in (("android-app://com.openai.chatgpt/", "chatgpt.com"),
                          ("android-app://ai.perplexity.app.android/", "perplexity.ai"),
                          ("android-app://com.anthropic.claude/", "claude.ai"),
                          ("android-app://com.google.android.apps.bard/",
                           "gemini.google.com"),
                          ("android-app://com.microsoft.copilot/",
                           "copilot.microsoft.com")):
            self.check(ref, "/", "AI assistant", assistant=name)

    def test_every_app_id_has_its_assistant_name(self):
        for app in ("com.openai.chatgpt", "ai.perplexity.app.android", "com.anthropic.claude",
                    "com.google.android.apps.bard", "com.microsoft.copilot"):
            self.assertIn(app, classify.AI_REFERRER_HOSTS)
            self.assertIn(classify.assistant_name(app), classify.AI_REFERRER_HOSTS)


class TestGoogleApps(BothRoads):
    """Only Google's web search and its search app are a search engine; its
    other Android apps are not."""

    def test_google_web_search_stays_search(self):
        for ref in ("https://www.google.com/", "https://www.google.ca/",
                    "https://www.google.co.uk/", "https://www.google.com.au/",
                    "https://google.de/", "android-app://com.google.android.googlequicksearchbox/"):
            self.check(ref, "/", "Search engine")

    def test_gmail_app_stays_email(self):
        self.check("android-app://com.google.android.gm/", "/", "Email")

    def test_youtube_whatsapp_telegram_apps_are_social(self):
        for ref in ("android-app://com.google.android.youtube/", "android-app://com.whatsapp/",
                    "android-app://org.telegram.messenger/",
                    "android-app://com.linkedin.android/"):
            self.check(ref, "/", "Social media")

    def test_other_google_apps_are_other_websites(self):
        for ref in ("android-app://com.google.android.apps.maps/",
                    "android-app://com.google.android.apps.docs/",
                    "https://docs.google.com.example.org/"):
            self.check(ref, "/", "Other website")


class TestUtmSourceFirst(BothRoads):
    """utm_source names the place; utm_medium only says how, so it decides
    only when the source names none."""

    def test_paid_social_is_social(self):
        self.check("", "/?utm_source=linkedin&utm_medium=cpc", "Social media",
                   "linkedin / cpc / -")
        self.check("", "/?utm_source=facebook&utm_medium=ppc&utm_campaign=q4",
                   "Social media", "facebook / ppc / q4")

    def test_paid_search_stays_search(self):
        self.check("", "/?utm_source=google&utm_medium=cpc", "Search engine",
                   "google / cpc / -")

    def test_medium_decides_when_the_source_names_nothing(self):
        self.check("", "/?utm_source=partner&utm_medium=cpc", "Search engine",
                   "partner / cpc / -")
        self.check("", "/?utm_source=acme&utm_medium=social", "Social media",
                   "acme / social / -")
        self.check("", "/?utm_medium=email", "Email", "- / email / -")
        self.check("", "/?utm_source=partner&utm_medium=banner", "Tagged link",
                   "partner / banner / -")


class TestClickIds(BothRoads):
    def test_every_click_id_has_a_source_and_a_campaign(self):
        self.assertEqual(set(classify.CLICK_ID_PARAMS), set(campaigns.CLICK_IDS))
        for key in classify.CLICK_ID_PARAMS:
            url = f"/?{key}=abc"
            with self.subTest(key=key):
                self.assertNotEqual(dim.source_type("", url, False, OWN), "Direct or unknown")
                self.assertNotEqual(dim.campaign(url), dim.NO_CAMPAIGN)
                self.assertEqual(audit_road("", url)[1:], main_road("", url)[1:])

    def test_new_click_ids(self):
        self.check("", "/?gbraid=abc", "Search engine", "google / cpc / (gbraid)")
        self.check("", "/?wbraid=abc", "Search engine", "google / cpc / (wbraid)")
        self.check("", "/?ttclid=abc", "Social media", "tiktok / (ttclid) / -")
        self.check("", "/?twclid=abc", "Social media", "x / (twclid) / -")
        self.check("", "/?gclid=abc", "Search engine", "google / cpc / (gclid)")
        self.check("", "/?fbclid=abc", "Social media", "facebook / (fbclid) / -")

    def test_tags_win_over_click_ids(self):
        self.check("", "/?utm_source=newsletter&gbraid=abc", "Email",
                   "newsletter / - / -")


if __name__ == "__main__":
    unittest.main()

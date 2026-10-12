"""Own-address traffic and certificate validation are not readers."""
import unittest
from datetime import datetime, timezone

from skald.classify import Classifier, Group
from skald.parse import Hit

CHROME = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/150.0 Safari/537.36"


def hit(address="192.0.2.10", url="/", agent=CHROME, referrer=""):
    return Hit(datetime(2026, 10, 6, 12, tzinfo=timezone.utc), address, "example.com", "GET", url, "200", referrer, agent)


class OurAddresses(unittest.TestCase):
    def test_listed_address_is_ours(self):
        c = Classifier(our_addresses=["192.0.2.10"])
        self.assertEqual(c(hit()).group, Group.OURS)

    def test_cidr_range_is_ours(self):
        c = Classifier(our_addresses=["198.51.100.0/24"])
        self.assertEqual(c(hit(address="198.51.100.77")).group, Group.OURS)

    def test_other_address_is_still_a_person(self):
        c = Classifier(our_addresses=["198.51.100.0/24"])
        self.assertEqual(c(hit(address="203.0.113.5")).group, Group.PEOPLE)

    def test_unparsable_address_is_not_ours(self):
        c = Classifier(our_addresses=["192.0.2.10"])
        self.assertEqual(c(hit(address="-")).group, Group.PEOPLE)

    def test_no_addresses_configured_changes_nothing(self):
        self.assertEqual(Classifier()(hit()).group, Group.PEOPLE)


class CertificateValidation(unittest.TestCase):
    def test_acme_challenge_path_is_a_bot_even_with_a_browser_agent(self):
        self.assertEqual(Classifier()(hit(url="/.well-known/acme-challenge/abc123")).group, Group.BOTS)

    def test_lets_encrypt_agent_is_a_bot(self):
        agent = "Mozilla/5.0 (compatible; Let's Encrypt validation server; +https://www.letsencrypt.org)"
        self.assertEqual(Classifier()(hit(agent=agent)).group, Group.BOTS)


if __name__ == "__main__":
    unittest.main()

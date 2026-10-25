"""One accounts file per install (2.35): every site's run opens the one beside the
history, never a new empty one in a second site's own folder (sites/<slug>/), where
security mail and the to-do marks found no team."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald.accounts.db import path_for  # noqa: E402


class OneAccountsFile(unittest.TestCase):
    def test_a_second_site_uses_the_file_beside_the_history(self):
        config = {"_resolved": {"history_db": "/srv/skald/history.sqlite",
                                "live_dir": "/srv/skald/sites/example.org"}}
        got = path_for(config, Path("/srv/skald/sites/example.org"))
        self.assertEqual(got, Path("/srv/skald/accounts.sqlite"))

    def test_the_first_site_is_unchanged(self):
        config = {"_resolved": {"history_db": "/srv/skald/history.sqlite"}}
        self.assertEqual(path_for(config, Path("/srv/skald")), Path("/srv/skald/accounts.sqlite"))

    def test_access_accounts_still_wins(self):
        config = {"access": {"accounts": "/data/accounts.sqlite"},
                  "_resolved": {"history_db": "/srv/skald/history.sqlite"}}
        self.assertEqual(path_for(config, Path("/srv/skald/sites/x")), Path("/data/accounts.sqlite"))

    def test_without_a_history_the_live_folder_is_used(self):
        self.assertEqual(path_for({}, Path("/srv/skald")), Path("/srv/skald/accounts.sqlite"))
        self.assertIsNone(path_for({}, None))


if __name__ == "__main__":
    unittest.main()

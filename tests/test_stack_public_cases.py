"""The public check on a corpus of sites (tests/fixtures/stack_public/<case>/case.json).

Each case is one kind of site or combination (WordPress behind Cloudflare, a headless
WordPress behind Next.js on Vercel, Shopify with a WordPress blog, a Cloudflare challenge
...): the answers its pages gave, as headers and trimmed HTML with example.com names, and
the cards the check must give, exactly, in order. Every card must carry evidence.

To see what a case gives now:  python3 tests/test_stack_public_cases.py <case>
"""
from __future__ import annotations

import json
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import advisories, site_fetch, stack_public as sp  # noqa: E402
from test_stack_public import CONFIG, NOW, PUBLIC, doc_refused, evidenced  # noqa: E402

CASES = Path(__file__).resolve().parent / "fixtures" / "stack_public"


class Pages:
    """lookup and open_pinned from a case: every host named in its pages resolves to a
    documentation address; a page not in the case answers 404."""

    def __init__(self, case: dict, folder: Path):
        self.pages = {}
        for key, page in case["pages"].items():
            method, url = key.split(" ", 1)
            body = page.get("body", "")
            if page.get("body_file"):
                body = (folder / page["body_file"]).read_text()
            headers = {k.lower(): (v if isinstance(v, list) else [v])
                       for k, v in (page.get("headers") or {}).items()}
            self.pages[(method, url)] = (page["status"], headers, body.encode())
        self.names = case.get("names")
        if self.names is None:
            self.names = {site_fetch.urlsplit(url).hostname: [PUBLIC] for _m, url in self.pages}
            self.names[sp.target(case["typed"])[1]] = [PUBLIC]

    def lookup(self, host, port):
        if host not in self.names:
            raise socket.gaierror("no such name")
        return list(self.names[host])

    def open(self, scheme, host, address, port, method, target, timeout, max_bytes, agent=None):
        url = f"{scheme}://{host}{target}"
        status, headers, body = self.pages.get((method, url)) or (404, {}, b"Not Found")
        return site_fetch.Answer(status, headers, body if method == "GET" else b"", url, address)

    def run(self, typed: str) -> dict:
        with mock.patch.object(site_fetch, "lookup", self.lookup), \
                mock.patch.object(site_fetch, "open_pinned", self.open), \
                mock.patch.object(site_fetch, "address_refused", doc_refused):
            return sp.check(typed, CONFIG, advisories.load(), NOW)


def load(name: str) -> tuple[dict, dict]:
    folder = CASES / name
    case = json.loads((folder / "case.json").read_text())
    return case, Pages(case, folder).run(case["typed"])


class Corpus(unittest.TestCase):
    def test_every_case_gives_its_cards_with_evidence(self):
        names = sorted(p.name for p in CASES.iterdir() if (p / "case.json").exists())
        self.assertGreaterEqual(len(names), 20)
        for name in names:
            with self.subTest(name):
                case, got = load(name)
                want = case["expect"]
                self.assertTrue(want["cards"], f"{name}: no expectation written")
                self.assertEqual([[c["kind"], c["title"]] for c in got["cards"]], want["cards"])
                self.assertEqual(got["summary"], want["summary"])
                if "products" in want:
                    self.assertEqual(sorted(f"{p['name']} {p['shown']}".strip() + f" @{p['host']}"
                                            for p in got["products"]), sorted(want["products"]))
                evidenced(self, got)
                self.assertLessEqual(got["fetches"], sp.MAX_FETCHES)


if __name__ == "__main__":
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        for name in sys.argv[1:]:
            _case, got = load(name)
            print(f"== {name}\nsummary: {got['summary']}")
            print("cards:", json.dumps([[c["kind"], c["title"]] for c in got["cards"]], indent=1))
            print("products:", json.dumps(sorted(f"{p['name']} {p['shown']}".strip() + f" @{p['host']}"
                                                 for p in got["products"]), indent=1))
            for c in got["cards"]:
                print(f"  [{c['kind']}] {c['title']}")
                for s in c["saw"]:
                    print(f"      {s['text'][:150]}")
                print(f"      -> {c['means'][:160]}")
            print("fetched:", [(f["method"], f["url"], f["status"] or f["error"]) for f in got["fetched"]])
    else:
        unittest.main()

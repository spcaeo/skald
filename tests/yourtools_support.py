"""Shared parts of the "From your tools" tests (not a test module): a fake tool,
registered by hand, that answers from a canned body. No test calls a real tool.

The fake's answer is shaped like a small API's: {"total": {"visits": "120",
"signups": null}, "rows": [{"page": "/pricing", "visits": "40"}, ...]}. Its
key is a token "fk_" + 20 letters; "fk_bad..." is refused by the tool.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import yourtools  # noqa: E402
from skald.yourtools.base import (Adapter, Answer, BadKey, Figure, Option,  # noqa: E402
                                         Unreachable, plain_key_words, pointer)

KEY = "fk_" + "AbCdEfGhIjKlMnOpQrSt"
OTHER = "fk_" + "ZyXwVuTsRqPoNmLkJiHg"
BODY = {"total": {"visits": "120", "signups": None},
        "rows": [{"page": "/pricing", "visits": "40"}, {"page": "/", "visits": "35"}]}


class Fake(Adapter):
    id = "fake"
    name = "Fake Tool"
    key_words = "a Fake Tool API token (fk_...)"
    permission = "read-only (Fake Tool > Tokens > Read)"
    make_key = "Fake Tool > Settings > Tokens > New token, read-only"
    env_names = ("FAKE_TOOL_TOKEN",)
    options = {"account": Option("Account", r"[a-z0-9-]{1,40}", "Its account's name, from "
                                 "its settings page.", env=("FAKE_ACCOUNT",), example="acme")}

    def __init__(self):
        self.body = dict(BODY)
        self.fail = None
        self.asked = []

    def check_key(self, text):
        got = plain_key_words(text, self.key_most)
        if not got.startswith("fk_") or len(got) != 23 or got.startswith("fk_bad"):
            raise BadKey("That is not a Fake Tool token: it starts with fk_.")
        return {"who": f"token ...{got[-4:]}"}

    def fetch(self, key, options, now, opener=None, sleep=None):
        self.asked.append((key, dict(options)))
        if self.fail:
            raise Unreachable(self.fail, 403)
        day = now.date().isoformat()
        return [Answer("totals", day, day, day, {"account": options.get("account")},
                       self.body, flags={"sampled": False}, note="the tool's own day")]

    def figures(self, answer):
        out = []
        for name in ("visits", "signups"):
            value = (answer.body.get("total") or {}).get(name)
            out.append(Figure(name=name, value=None if value is None else int(value),
                              label=name.title(), src=None if value is None
                              else pointer("total", name)))
        for i, row in enumerate(answer.body.get("rows") or []):
            out.append(Figure(name="visits", value=int(row["visits"]), label="Visits",
                              dim=row["page"], src=pointer("rows", i, "visits"),
                              dim_src=pointer("rows", i, "page"), rank=i))
        return out


def install() -> Fake:
    """A fresh fake tool, registered; the caller unregisters it (cleanup)."""
    fake = Fake()
    yourtools.register(fake)
    return fake


def remove() -> None:
    yourtools.unregister("fake")

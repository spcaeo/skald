"""The demo's AI answers (tools/demo.py): made-up answers through the real road.

AI & bots > AI answers needs runs that asked ChatGPT, Perplexity, Gemini and
Claude. The demo never calls a provider: its runs go through answers/run.py
with a seeded fake transport (the same shape as tests/test_ai_answers.py's),
so every answer is read, stored, figured and recounted by audit_ai_answers.py
as on a real install. The texts are made up and say so; the brand is
"Example Analytics" on example.com, the competitors are made-up names on
example.net / example.org. The API keys are made-up values set only in this
process while the demo builds, never sent anywhere (no transport but the fake).

Three tracking profiles (New York weekly, London weekly, Montréal in fr-CA
monthly), five questions, three tries each, one run a week up to yesterday.
The share of answers naming the site rises a little over the weeks, as it
would after an llms.txt and a pricing page that answers the question.

Standard library only.
"""
from __future__ import annotations

import json
import os
import random
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SEED = 20261018
BRANDS = ["Example Analytics", "example.com"]
COMPETITORS = ["Northwind Analytics", "Contoso Metrics", "fabrikam.example.net"]
QUESTIONS = ["What is the best web analytics tool that works from server logs?",
             "Privacy-friendly analytics without cookies for a small SaaS",
             "How can I see which AI assistants send visitors to my website?",
             "Google Analytics alternatives for B2B lead tracking",
             "Does server-log analytics count bots as visitors?"]
PROFILES = [
    {"name": "New York", "city": "New York", "region": "New York", "country": "US", "language": "en",
     "timezone": "America/New_York", "frequency": "weekly"},
    {"name": "London", "city": "London", "region": "England", "country": "GB", "language": "en-GB",
     "timezone": "Europe/London", "frequency": "weekly"},
    {"name": "Montréal", "city": "Montréal", "region": "Québec", "country": "CA", "language": "fr-CA",
     "timezone": "America/Toronto", "frequency": "monthly"},
]
# How often each assistant names the site in week 0, and how much that rises a week.
NAMED = {"api.openai.com": (0.52, 0.03), "api.perplexity.ai": (0.44, 0.03),
         "generativelanguage.googleapis.com": (0.18, 0.02), "api.anthropic.com": (0.34, 0.025)}
# The site's pages an answer cites (the pages the demo's assistants read and send to).
CITED = [("/pricing/", 5), ("/guides/getting-started", 3), ("/features/", 2), ("/guides/webhooks", 1)]
OTHERS = ["https://northwind.example.org/compare", "https://contoso.example.net/blog/analytics",
          "https://fabrikam.example.net/", "https://news.example.org/a/small-team-tools"]
KEYS = ("SKALD_OPENAI_API_KEY", "SKALD_PERPLEXITY_API_KEY", "SKALD_GEMINI_API_KEY",
        "SKALD_ANTHROPIC_API_KEY")
NOTE = " (A made-up answer for the Skald demo.)"


def _pick(rnd, pairs):
    total = sum(w for _, w in pairs)
    x = rnd.random() * total
    for item, w in pairs:
        x -= w
        if x <= 0:
            return item
    return pairs[-1][0]


class Fake:
    """A transport: a made-up answer in each provider's own shape. `week` is set
    before each run; nothing here touches the network."""

    def __init__(self, seed: int = SEED) -> None:
        self.rnd = random.Random(seed)
        self.week = 0
        self.calls = 0

    def text(self, host: str, french: bool) -> tuple[str, list[str]]:
        rnd = self.rnd
        base, rise = NAMED[host]
        named = rnd.random() < min(0.9, base + rise * self.week) - (0.12 if french else 0)
        comps = [c for c in ("Northwind Analytics", "Contoso Metrics") if rnd.random() < 0.55]
        if rnd.random() < 0.3:
            comps.append("fabrikam.example.net")
        parts = []
        if comps:
            parts.append("Popular choices include " + ", ".join(comps) + ".")
        if named:
            parts.append("Example Analytics reads your server logs directly, so it also counts the "
                         "visitors an ad blocker hides and tells AI crawlers from people.")
        else:
            parts.append("Most tools count visits from a script on the page; check how each one "
                         "handles bots and consent.")
        urls = []
        if named and rnd.random() < 0.75:
            urls.append("https://example.com" + _pick(rnd, CITED))
        urls += rnd.sample(OTHERS, rnd.randint(1, 2))
        rnd.shuffle(urls)
        return " ".join(parts) + NOTE, urls

    def __call__(self, method, url, headers, body, timeout):
        self.calls += 1
        host = url.split("/")[2]
        if method == "HEAD":            # Gemini's grounding redirect, resolved by its Location
            return 302, {"Location": "https://example.com" + _pick(self.rnd, CITED)}, b""
        sent = json.dumps(json.loads(body) if body else {})
        text, urls = self.text(host, "fr-CA" in sent or "fr-CA" in url)
        if host == "api.openai.com":
            got = {"output": [{"type": "message", "content": [{"type": "output_text", "text": text,
                    "annotations": [{"type": "url_citation", "url": u, "title": u.split("/")[2]}
                                    for u in urls]}]}]}
        elif host == "api.perplexity.ai":
            marks = "".join(f" [{i}]" for i in range(1, len(urls) + 1))
            got = {"object": "response", "status": "completed", "output": [
                {"type": "search_results", "results": [{"id": i, "url": u, "title": u.split("/")[2]}
                                                       for i, u in enumerate(urls, 1)]},
                {"type": "message", "role": "assistant", "content": [
                    {"type": "output_text", "text": text + marks, "annotations": []}]}]}
        elif host == "api.anthropic.com":
            got = {"stop_reason": "end_turn", "content": [{"type": "text", "text": text, "citations": [
                {"type": "web_search_result_location", "url": u, "title": u.split("/")[2],
                 "cited_text": text[:40]} for u in urls]}]}
        else:
            chunks = [{"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/demo",
                               "title": "example.com"}}] if any("example.com" in u for u in urls) else []
            chunks += [{"web": {"uri": u, "title": u.split("/")[2]}} for u in urls if "example.com" not in u]
            got = {"candidates": [{"content": {"parts": [{"text": text}]},
                                   "groundingMetadata": {"groundingChunks": chunks}}]}
        return 200, {}, json.dumps(got).encode()


@contextmanager
def made_up_keys():
    """The four API keys, made-up, for this process only; put back after."""
    was = {k: os.environ.get(k) for k in KEYS}
    os.environ.update({k: "demo-made-up-key" for k in KEYS})
    try:
        yield
    finally:
        for k, v in was.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def seed(folder: Path, cfg: dict, site: str, tz_name: str, first, today, say=print) -> dict:
    """Profiles and their runs in folder/ai_answers.sqlite, from `first` to the day
    before `today` (one run a week, the monthly profile once every four). Needs
    made_up_keys() around it, and around the dashboard build that follows."""
    from skald.answers import profiles, run, store
    tz = ZoneInfo(tz_name)
    days, d = [], today - timedelta(days=1)
    while d >= first:
        days.append(d)
        d -= timedelta(days=7)
    days.reverse()
    at = [datetime.combine(day, time(9, 30), tz).astimezone(timezone.utc) for day in days]
    made = (at[0] if at else datetime.combine(today, time(9), tz)) - timedelta(hours=1)
    with store.opened(folder) as db:
        store.save_lists(db, site, {"questions": QUESTIONS, "brands": BRANDS,
                                    "competitors": COMPETITORS, "keep_days": None}, "demo", made)
        for body in PROFILES:
            profiles.create(db, site, profiles.check({
                **body, "use_site_questions": True, "repeats": 3, "cap": 5,
                "providers": ["openai", "perplexity", "gemini", "anthropic"]}), "demo", made)
    fake = Fake()
    tally = {"runs": 0, "asked": 0, "withheld": 0}
    for week, when in enumerate(at):
        fake.week = week
        got = run.run_site(folder, site, cfg, tz, when, None, transport=fake, sleep=lambda s: None,
                           out=lambda *a: None, err=lambda *a: None)
        for k in tally:
            tally[k] += got.get(k if k != "runs" else "done", 0)
    if tally["withheld"]:
        raise SystemExit(f"demo: {tally['withheld']} AI-answer runs did not recount")
    say(f"demo: {tally['runs']} AI-answer runs, {tally['asked']} made-up answers")
    return tally

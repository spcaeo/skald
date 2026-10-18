"""AI answers: what AI assistants SAY about the site, joined with what they
READ (their user fetchers in the log) and SENT (visits, leads).

A site keeps 1 to PROFILE_LIMIT tracking profiles (profiles.py). A profile is
a place and a language (city, region, ISO country, optional lat/lon and time
zone; a BCP-47 language), its questions (or the site's list), brand terms and
competitors (or the site's), the assistants to ask, how often (daily, weekly
or monthly), how many tries per question (1-5, to see how much the answers
vary) and a daily spending cap in US dollars. A future Google Business
Profile link has its place (`gbp_location_id`), unused for now.

The run (run.py, `skald ai-answers --due`, every 15 minutes in the container)
asks each due profile's questions of each chosen assistant through its
documented HTTP API (providers.py), with its own key (Settings >
Integrations, install admins; secrets.json or the environment). Every answer
is stored (store.py, ai_answers.sqlite beside the history): its text
(trimmed), the URLs it cited, whether a brand term is named (word boundary)
and where, which own pages it cited and which competitors it names
(match.py). When a run is complete its figures are written per provider and
recounted at once by audit_ai_answers.py, a second road that shares only the
name lists; a figure that does not match is withheld (data.py).

Nothing is asked unless an install admin saved a provider's key and a site
admin made a profile that names it. The questions are sent to the providers.
"""
from __future__ import annotations

import math

PROVIDERS = ("openai", "perplexity", "gemini", "anthropic")
NAMES = {"openai": "ChatGPT", "perplexity": "Perplexity", "gemini": "Gemini",
         "anthropic": "Claude"}
# The assistant each provider's answers stand for, by the name the log gives it
# (classify.ASSISTANT_ALIASES): its user fetcher's reads and the visits it sends.
ASSISTANT = {"openai": "chatgpt.com", "perplexity": "perplexity.ai",
             "gemini": "gemini.google.com", "anthropic": "claude.ai"}
# Settings > Integrations: each provider's key (settings_store, kind secret, install).
SECRET = {p: f"ai_answers.{p}_key" for p in PROVIDERS}
ENV = {"openai": "SKALD_OPENAI_API_KEY", "perplexity": "SKALD_PERPLEXITY_API_KEY",
       "gemini": "SKALD_GEMINI_API_KEY", "anthropic": "SKALD_ANTHROPIC_API_KEY"}
LABEL = {"openai": "OpenAI API key (ChatGPT answers)",
         "perplexity": "Perplexity API key", "gemini": "Google Gemini API key",
         "anthropic": "Anthropic API key (Claude answers)"}
# config.yml `ai_answers: {openai_model: ...}` overrides these.
MODEL = {"openai": "gpt-4.1-mini", "perplexity": "fast", "gemini": "gemini-2.5-flash",
         "anthropic": "claude-haiku-4-5"}
# A rough cost of one answer in US dollars (tokens and the web search the
# provider bills), for the estimate and the cap; `ai_answers: {openai_price: ...}`.
PRICE = {"openai": 0.03, "perplexity": 0.01, "gemini": 0.04, "anthropic": 0.03}
# How each provider is told where the asker is (providers.py says why).
API_LOCATION, IN_QUESTION = "api", "question"
LOCATION = {"openai": API_LOCATION, "perplexity": API_LOCATION, "gemini": IN_QUESTION,
            "anthropic": API_LOCATION}
LOCATION_WORDS = {
    "openai": "Location passed to the API (web search user_location)",
    "perplexity": "Location passed to the API (web search user_location, language_preference)",
    "gemini": "Place and language written into the question (the API has no location field)",
    "anthropic": "Location passed to the API (web search user_location)",
}
PROFILE_LIMIT = 10
QUESTION_LIMIT = 50
TEXT_MAX = 8000             # characters of an answer kept
RUN_HOUR = 6                # a due profile starts from this hour, in the site's zone
KEEP_DAYS = 400             # answers and their figures kept, per site (lists.keep_days)
FREQUENCIES = {"daily": 1, "weekly": 7, "monthly": 30}
RUNS_PER_MONTH = {"daily": 30, "weekly": 4.3, "monthly": 1}


def section(config: dict | None) -> dict:
    got = (config or {}).get("ai_answers")
    return got if isinstance(got, dict) else {}


def model(config: dict | None, provider: str) -> str:
    return str(section(config).get(f"{provider}_model") or MODEL[provider])


def price(config: dict | None, provider: str) -> float:
    raw = section(config).get(f"{provider}_price")
    try:
        got = float(raw)
    except (TypeError, ValueError):
        return PRICE[provider]
    return got if 0 <= got <= 10 else PRICE[provider]


def run_hour(config: dict | None) -> int:
    try:
        got = int(section(config).get("run_hour", RUN_HOUR))
    except (TypeError, ValueError):
        return RUN_HOUR
    return got if 0 <= got <= 23 else RUN_HOUR


def key(config: dict | None, provider: str, live_dir=None) -> str | None:
    """The provider's key: its environment variable, else secrets.json. Never
    printed, logged or sent anywhere but to that provider."""
    from ..settings_store import secret_value
    try:
        return (secret_value(config, SECRET[provider], live_dir) or "").strip() or None
    except PermissionError:             # secrets.json readable by others: refused
        import os
        return os.environ.get(ENV[provider], "").strip() or None


def keys_set(config: dict | None, live_dir=None) -> dict:
    """{provider: True/False}: whether a key is set. Never the key."""
    from ..settings_store import secret_state
    return {p: bool(secret_state(config, SECRET[p], live_dir)["set"]) for p in PROVIDERS}


def estimate(profile: dict, questions: int, config: dict | None, keyed=None) -> dict:
    """What one profile costs: answers a run (questions x tries x assistants),
    US dollars a run and a month (runs a month by frequency), and whether a
    run fits under the daily cap. Only assistants with a key are counted when
    `keyed` is given."""
    chosen = [p for p in profile.get("providers") or [] if p in PROVIDERS
              and (keyed is None or keyed.get(p))]
    tries = int(profile.get("repeats") or 1)
    per_run = sum(questions * tries * price(config, p) for p in chosen)
    month = per_run * RUNS_PER_MONTH.get(profile.get("frequency") or "weekly", 4.3)
    cap = float(profile.get("cap") or 0)
    return {"answers": questions * tries * len(chosen), "questions": questions, "tries": tries,
            "assistants": len(chosen), "per_run": round(per_run, 4), "per_month": round(month, 2),
            "cap": cap, "fits": per_run <= cap + 1e-9,
            "days": max(1, math.ceil(per_run / cap - 1e-9)) if cap and per_run > cap else 1,
            "prices": {p: price(config, p) for p in chosen}}

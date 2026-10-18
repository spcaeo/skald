# AI answers

What ChatGPT, Perplexity, Gemini and Claude **say** when asked the questions
buyers ask, the way Profound, Peec AI or Otterly track it, joined with what
only Skald sees: what the same assistant then **read** on the site (its user
fetcher in the log) and the visitors and leads it **sent**. Code:
`skald/answers/`; second count: `audit_ai_answers.py`; data:
[DATA-CONTRACT-AI-ANSWERS.md](DATA-CONTRACT-AI-ANSWERS.md); page: AI &
bots › AI answers; settings: Settings › AI answers.

**These are a sample of API answers, not what every user sees.** Each
provider answers people differently by account, history, place and wording,
and its API can differ from its app. The page says so above every figure.

## Turn it on

1. **A key per assistant (install admin).** Settings › Integrations › "AI
   answers: assistants' API keys". Each is write-only, kept 0600 in
   `secrets.json` beside the history (`conversions/secrets_store.py`); an
   environment variable of the same name wins and is never shown:
   `SKALD_OPENAI_API_KEY`, `SKALD_PERPLEXITY_API_KEY`, `SKALD_GEMINI_API_KEY`,
   `SKALD_ANTHROPIC_API_KEY`. A key is never printed, logged, stored anywhere
   else or sent anywhere but to its provider.
2. **The site's lists (site admin).** Settings › AI answers: the questions
   buyers ask (at most 50), the brand terms (names, and the site's domains),
   the competitors (names or domains), how many days answers are kept (400).
3. **A tracking profile (site admin).** Settings › AI answers › Tracking
   profiles, or the panel beside AI & bots › AI answers. At most 10 per site:
   a name; a place (city, region, ISO country, optional latitude, longitude
   and time zone) and a language (BCP-47: `en`, `fr-CA`); its own questions,
   brand terms and competitors, or the site's; the assistants to ask; how
   often (daily, weekly, monthly); tries per question (1 to 5, to see how much
   the answers vary); a daily spending cap in US dollars. A place for a
   future Google Business Profile link is kept (`gbp_location_id`), unused.
   Profiles are duplicated, paused, resumed and deleted there; nothing is
   erased (the same rule as internal traffic): a pause is kept as a
   [from, to] pair, a deleted profile leaves the list and its results stay,
   an edit is a new version and each run keeps the version it asked with.
4. **The runs.** In the container the scheduler runs `skald ai-answers --due`
   every `SKALD_AI_ANSWERS_MINUTES` (15; 0 stops it). Outside Docker add
   `*/15 * * * * ... skald --config ... ai-answers --due` to cron. A profile
   is due from 06:00 in the site's zone (`ai_answers.run_hour`) when its
   last run is a day, 7 days or 30 days old, or when an admin chose **Run
   now**. `skald ai-answers --profile ID --now` runs one at once;
   `skald ai-answers --show ID` prints one stored answer in full.

## What each provider is sent, and how the place reaches it

Each question is sent as written, with the place and language as below,
to the provider's documented HTTP API (standard library `urllib`), checked
on 2026-10-18:

| Assistant | API | Model (config) | The place | Cited URLs read from |
| --- | --- | --- | --- | --- |
| ChatGPT | OpenAI Responses, `POST /v1/responses`, tool `web_search` | `gpt-4.1-mini` (`ai_answers.openai_model`) | the tool's `user_location` (`approximate`: city, region, country, timezone) | the message's `output_text` `annotations` of type `url_citation` |
| Perplexity | Agent API, `POST /v1/agent` (it replaces Sonar chat completions), tool `web_search` | preset `fast` (`ai_answers.perplexity_model`; a `provider/model` name selects a model) | the tool's `user_location` (city, region, country, latitude, longitude) and `language_preference` | the `search_results` item's `results` that the text's `[n]` / `[web:n]` markers name, in that order |
| Gemini | `POST /v1beta/models/<model>:generateContent`, tool `google_search` | `gemini-2.5-flash` (`ai_answers.gemini_model`) | none in the API: "I am in <city>, <region>, <country>." is added to the question | `groundingMetadata.groundingChunks[].web.uri`; Google's grounding redirect is resolved by reading its `Location` header (no page fetched), else its title is kept as the source's domain, page unknown |
| Claude | Anthropic Messages, `POST /v1/messages`, tool `web_search_20250305` (`max_uses` 3) | `claude-haiku-4-5` (`ai_answers.anthropic_model`) | the tool's `user_location` (`approximate`: city, region, country, timezone) | the `text` blocks' `citations` of type `web_search_result_location` |

A language other than English is asked for in a last line of the question
("Answer in fr-CA.") for every assistant but Perplexity, which takes it in
`language_preference`. The page names the method beside each assistant
("API location" or "In question").

Rate limits and errors: 429, 408, 409, 425 and 5xx are tried again 3 times,
with backoff from 4 s (a `Retry-After` is honoured, at most 60 s); a timeout
is 90 s; 400, 401, 403 and 404 are not tried again. A failed try is stored
with its reason (never the key) and counts as asked, not answered.

## Cost, the cap and the estimate

Every answer costs on **your** provider account: tokens plus the web search
the provider bills. Skald works out an estimate before anything runs, on the
profile's panel: questions × tries × assistants with a key × each one's price
an answer, × runs a month (30, 4.3 or 1). The prices are rough defaults in US
dollars (ChatGPT 0.03, Perplexity 0.01, Gemini 0.04, Claude 0.03), set in
config.yml as `ai_answers: {openai_price: 0.03, ...}` to match your contract.
Before each ask the profile's estimated spending that day plus the ask's must
stay under its **daily cap**; past it, the run stops and goes on the next day
(the page says how many days a run will take). The estimate is not a bill:
check each provider's own usage page.

## What is stored, and privacy

`ai_answers.sqlite` beside the history: the lists, the profiles and every
version, each run's plan (frozen when it starts), and each try: the question
as sent, the answer's text (trimmed to 8,000 characters), the cited URLs,
the model, the estimated cost, and what was read in it. Kept `keep_days`
(400) per site, then removed by the next run. Nothing about visitors is sent
to a provider: only the questions, the profile's place and language.
**The questions are sent to the providers you choose**, under their terms:
do not write anything private into a question.

## What is counted (and checked twice)

Per answer (`answers/match.py`): **named** when a brand term appears as a
whole word, any case; the **rank** of the brand among the competitors named
(1 = named first); the **own pages** cited (citations on the site's hosts or
the brand terms written as domains, `www.` ignored, query and fragment cut);
the **citation rank** (the first own citation's place among the cited URLs);
the **competitors** named (a name in the text, or a competitor domain in the
text or the citations). Per run and assistant, once every try is in: asked,
answered, named, cited, competitor mentions, citation rank's sum and count.
`audit_ai_answers.py` reads the same raw text and URLs with its own code,
sharing only the run's name lists, and recounts every answer's reading and
every figure; it runs as each run finishes and again in run-daily's
recounts (`audit_more.DAILY`, the last 35 days). A run that does not match
is **withheld**: the page lists it, with no figures.

The page's chain (**cited → read → sent → converted**) puts four counts side
by side for one assistant and own page over the last 30 days: answers that
cited the page (the sample), that assistant's user-fetcher reads of it
(`ai_fetches`), visits it sent landing on it (the cube), and leads whose first
visit came from an AI answer landing on it (`conversions.sqlite`, any
assistant). Likely-AI visits (`ai_likely`, inferred) are said apart. They are
different counts from different roads, joined by page and days, never added
together.

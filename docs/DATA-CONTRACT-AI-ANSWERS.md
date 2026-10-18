# Data contract: ai_answers.json

Built by `skald/answers/data.py` beside every page (the whole site's; a
view gets the same), from `ai_answers.sqlite` beside the history and, for the
chain, history's day kinds and `conversions.sqlite`. Read by AI & bots › AI
answers (`webapp/js/tabs/ai-answers*.js`). The envelope is the usual one
(`schema_version` 1, `generated_at`, `site`, `view`, `timezone`). Nothing in it
is a key: `setup.keys` and `providers[].key` only say whether one is set.

**A sample of API answers, not what every user sees.** Every figure here is a
count of answers the providers' APIs gave to Skald's questions.

## Top level

| Field | What |
| --- | --- |
| `state` | `"ok"` once a key, the brand terms and a profile exist, or a run is done; else `"not set up"` |
| `setup.keys` | `{provider: true/false}` |
| `setup.steps` | `[{id, done, words}]`: `key`, `lists`, `profile`, `run`, in order |
| `providers` | `[{id, name, model, location, how, price, key, assistant}]`: `id` one of `openai`, `perplexity`, `gemini`, `anthropic`; `location` `"api"` (passed in the API's location field) or `"question"` (written into the question); `price` the US dollars an answer the estimate uses; `assistant` the log's name for it (`chatgpt.com`, ...) |
| `lists` | the site's `{questions, brands, competitors, keep_days}` (`keep_days` null: 400) |
| `profiles` | the listed profiles (not deleted), below |
| `trend` | per done run, below |
| `last` | `{profile id: its last done and verified run}`, below |
| `competitors` | `{profile id: [{name, answers, by: {provider: n}, of: {provider: answers}}]}`, last `competitor_days` (90) days, verified runs only |
| `chain`, `chain_first`, `chain_last` | below; the last `chain_days` (30) days ending yesterday |

## profiles[]

`id`, `version`, `name`, `city`, `region`, `country` (ISO alpha-2), `lat`,
`lon`, `timezone`, `language` (BCP-47), `use_site_questions`, `questions`,
`brands`, `competitors` (the profile's own; [] means the site's), `providers`,
`frequency` (`daily`, `weekly`, `monthly`), `repeats` (tries per question,
1-5), `cap` (US dollars a day), `gbp_location_id` (kept for later, unused),
`asks` (`{questions, brands, competitors}` it asks with), `state` (`active`,
`paused`), `estimate` (`{answers, questions, tries, assistants, per_run,
per_month, cap, fits, days, prices}`: only assistants with a key; `days` how
many days a run takes under the cap), `last_run` (`{id, day, finished_at}` or
null), `open_run` (a run still going: `{id, day, planned}` or null),
`next_run` (ISO in the site's zone, null while paused), `run_requested`.

## trend[]

One entry per done run in the last 180 days: `run`, `profile`, `day` (the
day it started, site's zone), `withheld` (true when the second count did not
match: then `providers` is `{}` and `problems` says why), `providers`:
`{provider: {asked, answered, mentioned, cited, competitor_mentions, avg_rank}}`.

- `asked`: tries made; `answered`: tries with an answer (a failed try is
  asked, not answered).
- `mentioned`: answered tries naming a brand term as a whole word. Share of
  voice is `mentioned / answered`; with repeats it is shown as "x of N tries".
- `cited`: answered tries citing at least one own page.
- `competitor_mentions`: the competitors each answered try named, summed.
- `avg_rank`: the mean place of the first own citation among an answer's
  cited URLs, over the tries that cited one; null when none did.

## last{}

`{run, day, providers, repeats, questions: [{qi, question, by: {provider:
{tries, answered, mentioned, pages, competitors, answer_id, line, failed}}}]}`.
`pages`: own pages cited (`"(page not known)"` for a citation known only by
its domain); `line`: `{pre, mark, post}`, a line of one answer around the
first brand term (`mark` empty when none is named); `answer_id` opens the
full answer (`GET <page>/ai-answers/answer?id=`, sessions mode, members of
the site); `failed`: up to 3 reasons of failed tries.

## chain[]

Per assistant and own page cited in the window, most cited first: `provider`,
`page`, `cited` (answers that cited it), `of` (that assistant's answered tries
in the window), `read` (that assistant's user-fetcher requests for the page:
`ai_fetches`), `sent` (visits from that assistant landing on the page: the
cube, source "AI assistant"), `likely` (visits likely sent by any AI answer
landing on it: `ai_likely`, inferred), `leads` (completed conversions, tests
left out, whose first touch was an AI answer and landed on it: any
assistant). Pages are compared without query, fragment or trailing "/". A
part not recorded in the window is null, never 0. Five counts, never added.

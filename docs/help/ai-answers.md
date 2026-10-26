# AI answers: what assistants say about you

See what ChatGPT, Perplexity, Gemini and Claude answer when someone asks the questions your buyers ask, whether they name you, which of your pages they cite and which competitors they name. Then follow one citation through what only Skald sees: the assistant reading your page, the visitors it sent, and the leads that followed. This guide covers setting it up, tracking profiles, what each figure means, and what it costs.

## Read this first

**These are a sample of API answers, not what every user sees.** Each provider answers people differently by account, history, place and wording, and its API can differ from its app. Read the figures as a direction over weeks, never as a count of people. Every answer is kept, so you can read exactly what was said.

## Where to find it

- [AI & bots › AI answers](#ai/answers): the figures, the chain, the questions and the profile's settings beside them.
- [Settings › This site › AI answers](#settings/site/aianswers): the site's questions, brand terms and competitors, and the tracking profiles (tab **Questions & profiles**).
- [Settings › This site › AI answers › API keys](#settings/site/aianswers?sub=keys): the assistants' API keys (install admins).

## Set it up

1. **Add a key** for at least one assistant: Settings › This site › AI answers › API keys. Each key is your own account with that provider (OpenAI, Perplexity, Google Gemini, Anthropic). It is write-only: the page only says set or not.
2. **Write the lists**: Settings › This site › AI answers. The questions your buyers ask (at most 50, written as a customer would), your brand terms (your name and your domain) and your competitors (names or domains).
3. **Make a tracking profile**: a place and a language, the assistants to ask, how often, how many tries per question, and a daily spending cap. The panel shows the cost estimate before you save.
4. **Wait for the first run**, from 06:00 in the site's time zone, or choose **Run now**. The figures appear once every answer of the run is in and has been checked.

Nothing is asked, and nothing costs, until a key and a profile exist. The questions are sent to the providers you choose: do not write anything private into a question.

## Tracking profiles

A profile asks as if from one place, in one language: Toronto in English, Montréal in French, New York. Make one per market you care about; at most 10 per site.

| Setting | What it does |
|---|---|
| Location | City, region and country, with optional coordinates and time zone. ChatGPT, Perplexity and Claude take it in their API's location field (**API location**). Gemini's API has none, so "I am in ..." is written into the question (**In question**). |
| Language | Asked for in the question ("Answer in fr-CA."), and passed to Perplexity as its language. Write the questions in that language too. |
| Questions | Its own list, or the site's. |
| Brand terms, competitors | Its own, or the site's when left empty. |
| Assistants | Which to ask. An assistant without a key is left out and said. |
| How often | Daily, weekly or monthly. |
| Tries per question | 1 to 5. Answers vary from one try to the next: with 5 tries you see "named you in 3 of 5", never a single yes or no. |
| Daily spending cap | In US dollars. A run that would pass it stops and goes on the next day. |

Pause, resume, duplicate and delete are in Settings › This site › AI answers. Nothing is erased: a deleted profile leaves the list and its results stay; an edit makes a new version and earlier runs keep theirs.

## What the page shows

- **From an answer to a lead**: for one assistant and one of your pages, over the last 30 days, four counts side by side: answers that **cited** the page (the sample), the times that assistant's fetcher **read** it for people asking (your server log), the visitors it **sent** to it (your log), and the leads whose first visit came from an AI answer and landed on it (your forms and booking tool). They are counted on their own roads and joined by page and day, not by person: a path, not one buyer. They are never added together.
- **How often each assistant names you**: the share of answered tries that named a brand term, per run of the profile, one line per assistant, each named at its end. Hover or focus a run for its figures.
- **Every profile, every assistant**: one question across all profiles: "3 of 5" tries, a filled dot for each try that named you. Pick a question in the table below to change it. Select another profile's name to open that profile; **Export what you see** downloads the grid as a CSV.
- **Questions**: each question of the profile's last run: tries that named you over all assistants, the pages cited, the competitors named, and a line from one answer. **Full answer** opens the whole answer and its cited links. A cited page opens that page's detail, as anywhere in Skald.
- **Competitors in the answers**: how many answers named each competitor, per assistant.

The Questions and Competitors tables work like every table in Skald: sort by any column, filter each column, choose the columns, search, and export what you see. A profile's place is shown as its flag and the three-letter country code (CAN, GBR), the full name in the tooltip. The page keeps its own period, each profile's runs, so the date range does not apply here.

## What counts as named and cited

- **Named**: a brand term appears as a whole word, any case. "Contoso" counts in "Contoso's plan", not in "Contosoville".
- **Cited**: the answer links to a page on your site's hosts (or a brand term written as a domain). Gemini sometimes hides the address behind Google's redirect; Skald reads where it leads, and when it cannot, the page shows "(page not known)".
- **Citation rank**: where your first link sits among the answer's links (1 = first).

Every figure is counted twice: once when the answer is read, and again by a separate count from the stored answer text and links. A run where the two disagree is **withheld**: the page says so and shows no figures for it.

## What it costs

Each answer costs on your provider account: the model's tokens and its web search. The estimate on the profile's panel is questions × tries × assistants × a price an answer × runs a month. The prices are rough defaults (about 1 to 4 US cents an answer) that your server's admin can match to your contract. The estimate is not a bill: check each provider's own usage page.

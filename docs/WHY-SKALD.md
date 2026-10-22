# Why "Skald"

In the Viking Age and the centuries after it, the best-known poets of the North were **skalds**,
and most of the skalds whose names we still know were **Icelanders**. They travelled from Iceland
to the halls of kings and chieftains in Norway, Denmark and beyond. Their craft was to **watch what
happened, remember it, and tell it back**: who came, what they did, what changed.

A skald's verses were how a court knew its own history. Much of what we know about that age comes from
their poems, many of them written down in Iceland in the 1200s, by Snorri Sturluson and others.

Two things about the skalds fit this tool:

- **They reported only what they had seen.** Skaldic verse was valued as a record. Snorri wrote that
  no skald would dare tell a king about deeds that everyone present knew to be false, because that
  would be mockery, not praise. This tool works the same way. Every number is
  recounted a second, independent way. A day that doesn't add up is **withheld**, never guessed, and
  a missing day is never drawn as zero.
- **They needed no one's permission to watch.** A skald stood in the hall and saw everyone who
  entered: the guests, the strangers, the spies. This tool reads the server's own access log, so it
  sees what a JavaScript tracker can't: AI assistants fetching pages to answer someone's question,
  crawlers collecting pages for training, search engines, and bots. It needs no cookie and no script
  in the visitor's browser; a small tag is there for sites that want in-page events too.

Why the tool exists at all, and how it compares with Google Analytics, Search Console and the
others: [WHY-WE-BUILT-SKALD.md](WHY-WE-BUILT-SKALD.md) and [COMPARISON.md](COMPARISON.md)
(as a page: [comparison.html](comparison.html)).

## What it does now

The log is still the main record. Since 2026-10-11 Skald can also hear what the site's own tools
report: a booking in Calendly or Cal.com, a payment in Stripe, a form in Typeform or HubSpot. Every
figure is still counted twice, and a day that does not add up is withheld. Since 2.4.0 (the owner's
decision, 2026-10-12) Skald can keep each visit with its IP address and leads' emails, so a person
can be followed across days, and it hides nothing: spam, test, cancelled and removed rows are
listed. Keeping IPs and emails is a setting (`privacy.keep_ips`, `conversions.identity`): on for a
new install, off on an install upgraded from before 2.4.0 until it is turned on. Since 2.5.0 leads
and demo bookings show on every page where they help. People sign in with their own accounts, and
AI agents can ask it questions through MCP, read-only. Since 2026-10-12 it also estimates which "Direct" visits and leads an AI assistant
very likely sent (it fetched the page minutes before), labelled as an estimate, and it takes logs
from Vercel and Netlify drains and a Cloudflare Worker for cached pages. Since 2.16 a site is
connected in a few guided steps with a test at the end, and Skald looks at the site first to suggest
the way in. Since 2.20 every lead is in one list, and Overview shows what the newest visitors are
doing now. Since 2.21 it also tells of the spies at the door: Security shows who probes the server,
whether any probe got a real file, what attacks were tried and which advisories apply to the site's
stack, all from the same log and counted twice. Most new parts are off until an install switches
them on. The list, part by part:
[WHY-WE-BUILT-SKALD.md](WHY-WE-BUILT-SKALD.md), "What it does now". How to use each part, in plain
words: the Help pages, starting with [getting started](help/getting-started.md).

## Tagline

> **Every visit, truly told.**

Four words: *every visit* (it sees all of them, bots and AI included) and *truly told* (the skald's
promise: only what really happened, checked twice).

## The name in one line

> **Skald: your website's own storyteller. It watches every visitor at the door and tells you the
> true story of your traffic, every morning.**

## The icon

A simple **quill crossing a rune-like stroke**, set in a square with soft corners. The quill is the
skald writing the record. The stroke echoes a rune carved in stone, the oldest kind of log in the
North. It is one colour, works at 16 px, and draws no historical symbol in particular. That is on
purpose: it shouldn't borrow or misuse any real rune's meaning.

## Pronunciation

**Skald** is said "skawld" (/skɔːld/): one syllable, rhyming with *called* or *bald* (Old Norse *skáld*, "poet").


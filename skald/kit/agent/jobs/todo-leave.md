## Step __N__. Pages people leave at once: draft a next step, the user approves

These to-dos name a page where many visits started and nearly every one left after that one
page, with no form sent:

__LEAVE_LIST__

For each, the rows: __ROWS__. Each row has `source` (where those visits came from) and
`visits`.

This is a content change: **you draft, the user decides.** Never publish or deploy a page
change without their yes.

**Check first:** find the page's source in the repository (or in the CMS: ask the user how to
reach it), and read it as a visitor would: `curl -s 'https://__SITE__<page>'`. Does it already
have a clear next step above the fold (a link to what they came for, a form, a call to act)?
Does what the top sources promise (a search result's title, an AI answer's link, a campaign)
match what the page says first?

Then draft, at most three small changes per page, each one sentence of why:

- a clear next step near the top: the link or form the page is for;
- a title and first line that say what the sources promised;
- a link to the page people most likely wanted next (another page of the site).

Show the user the draft as a diff (or the words, for a CMS) and ask: "Shall I make these
changes?" With a yes, make them as a normal change (rule 4). With a no, or no answer, change
nothing: the state is `left`, and the draft goes in the report as `change`, so the user finds
it in Skald later.

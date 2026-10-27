## Step __N__. Connect Google Search Console (and say what Bing needs)

Skald can show the Google searches that bring people to __SITE__: the queries, clicks and
positions. It reads them, read-only, through a Google service account (a robot address).
Bing works the same way with a Bing API key.

**Check first.** What Skald had when this line was made:

__SEARCH_NOW__

If Google's line says connected, this part is done already. Change only what is missing.

### 1. Find the site's Search Console property

Ask the user, in one message, and wait for the answer:

"Does __SITE__ have a Google Search Console property? It is either a domain property
(`sc-domain:__SITE__`) or an address property (`https://__SITE__/`). If you are not sure, open
https://search.google.com/search-console and look at the property list."

If it has none, the user makes one there (a domain property needs one DNS TXT record): give
them those clicks and report this job as `left`.

### 2. The robot address

__SEARCH_ROBOT__

### 3. The one click left for the user

Skald cannot do this one: only an owner of the property can give access. Give the user these
clicks, with the robot address filled in, and put them in the report's `left_for_user`:

1. Open https://search.google.com/search-console/users and pick the property of __SITE__.
2. Settings > Users and permissions > Add user.
3. Paste the robot address. Permission: **Restricted** (it can only read figures). Add.

### 4. Bing (by hand)

Bing gives an API key only on its own page; there is no API that makes one. If the user wants
Bing too, put these clicks in `left_for_user`: Bing Webmaster Tools
(https://www.bing.com/webmasters), Settings > API access > API Key, copy it, and paste it in
Skald (__DASHBOARD__#settings/site/leads?tool=search: Settings > Leads & tools > Search
Console & Bing, Bing). Only whoever runs their Skald can paste it there. Bing can also import the sites from Search Console (Add a site > Import).

Change nothing in Skald. Put the property in the report as `search` (`google_property`,
`robot_added`: true once the user says they added it, and `bing_site` when you know the
site's address in Bing): the user connects it in Skald with one click, and the set-up list
ticks once Search Console answers.

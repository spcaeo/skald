"""Search figures from the engines themselves (ROADMAP P1-6): Google Search
Console and Bing Webmaster Tools, synced into history by their APIs.

The log cannot see a search: no query, no impression, no position. Only the
engine holds them. This package keeps a copy, per site and day, beside the
log's own figures, and puts them side by side without ever mixing them:

  rsa.py       RS256 in pure Python (the stdlib has no RSA), for Google's token
  http.py      one HTTPS call with retries and backoff, keys scrubbed
  google.py    the service-account key, its token, sites() and query()
  bing.py      the Bing API key, GetUserSites, traffic and top tables
  days.py      the history table `search_days` (schema 14) and its blobs
  state.py     each site's sync state file and its lock
  sync.py      the sync: newest day, the last days again, backfill; the CLI
  data.py      search.json for the Search tab, with the cross-check
  api.py       Settings > Leads & tools > Search: the connect wizard's routes

Second roads: audit_search.py (stored figures re-added by SQL, one day's
totals fetched again) and audit_search_landing.py (Skald's own side of the
cross-check, recounted from the raw log). docs/INTEGRATIONS.md has the setup.
"""

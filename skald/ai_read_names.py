"""The name lists of an assistant's reads (ai_reads.py, and its second count
audit_ai_reads.py). Names and one window only: each road reads a log line
and applies these with its own code, so this is all the two share.

When someone adds a page to a Google NotebookLM notebook, its fetcher asks
for the page twice within about 3 seconds (a fetch and a render), then the
page's own stylesheet and scripts with the page as referrer. One read, four
requests (COUNTING-TRAPS.md, trap 21). So an assistant's user-fetch request
(classify.AI_ASKED) is one of:

  file    a file the page loaded: its path ends in FILE_EXTENSIONS, starts
          with FILE_FOLDERS or one of the site's asset prefixes
          (site.asset_prefixes), or carries a FILE_QUERY payload; or its
          referrer is on the same site and names a page the same assistant
          read in the last WINDOW_SECONDS
  read    the first request for a page by an assistant, or the first after
          WINDOW_SECONDS since that assistant's read of it began
  repeat  a request for the same page by the same assistant inside that window

Content an assistant asks for on purpose stays a page: PDFs, JSON, XML,
text and Markdown are not here.
"""
from __future__ import annotations

# One assistant, one page: requests within this many seconds of the read's
# first request are the same read. The longest gap seen in the NotebookLM
# pattern (page, page again, its CSS and JS) was 5 seconds; a browser's own
# page assets land within 30 (rendering.RENDER_SECONDS, the same reason).
WINDOW_SECONDS = 30

# Styles, scripts, images, fonts, media and the like: what a page loads.
FILE_EXTENSIONS = (".css", ".js", ".mjs", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg",
                   ".webp", ".avif", ".ico", ".bmp", ".woff", ".woff2", ".ttf", ".otf",
                   ".eot", ".mp4", ".webm", ".mov", ".mp3", ".wav", ".ogg", ".m4a",
                   ".wasm", ".webmanifest")
# A framework's own folders: never a page someone reads.
FILE_FOLDERS = ("/_next/", "/_nuxt/")
# A framework payload in the query string: only a page's running script asks.
FILE_QUERY = ("_rsc", "__flight__", "_data")
# The site's asset prefixes when it sets none (rendering.ASSET_PREFIXES).
DEFAULT_PREFIXES = ("/_next/static/",)

"""When a same-site referrer is not a move: the numbers both roads share (trail rule 2, #62).

A visit's trail is its pages in order. A site that navigates in the browser
loads nothing for a click, so a request whose same-site referrer names
another page than the trail's last one shows the visitor was there: an
"in-app" step (visits.py, the dashed node "seen in the browser"). Rule 1
took every such referrer as a move.

Pages loaded ahead of a click broke it. Chrome's speculation rules
(`<script type="speculationrules">`, prerender or prefetch, eagerness
"moderate") request a linked page and its files when the pointer rests on
the link for about 200 ms. Checked in Chrome on 16 Nov 2026 (issue #62):

  * hover only            the page and its image requested, never shown
  * hover, then a click   the same lines, and nothing at the click
  * pass over one link and click another
                          two pages from the same page, 0.2 s apart

On one live visit that gave "pricing, consulting, implementation, pricing,
consulting, implementation" with three dashed steps and "under 1 s"
between them: the second page's request and the first page's files arrived
after one another, and each one's referrer read as a move back.

Rule 2 keeps rule 1 and adds two cases that are not a move:

  OWN_FILES_SECONDS   a request that is not a page, whose referrer names a
                      page the visit loaded at most this many seconds
                      before (or after: lines can arrive a moment out of
                      order): that page's own files, fetched as it loaded
  TOGETHER_SECONDS    a page whose referrer is the same page as the last
                      page loaded's, at most this many seconds apart: the
                      two were opened together (one loaded ahead, or a new
                      tab), not a move back

A move back (the Back button, then a click elsewhere) is still seen: the
next page's referrer names the page gone back to, and it is not one of
these two cases. A move inside a site that navigates in the browser, to a
page loaded as a document more than OWN_FILES_SECONDS before, is still seen
by any request made from it.

The server log cannot tell a page loaded ahead and never shown from one
the person opened: both carry `Sec-Purpose: prefetch`, and the click
itself makes no request. So both stay page views, as the log has them.
The script tag (skald.js) waits until a page loaded ahead is shown.

visits.py and audit_visits.py (with audit_funnels.py) each apply this by
their own code; only these numbers are shared.
"""

OWN_FILES_SECONDS = 30
TOGETHER_SECONDS = 2

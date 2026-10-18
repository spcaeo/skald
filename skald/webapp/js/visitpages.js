// A visit's pages in words, the same everywhere a visit is shown (grid, latest
// visits, the visitor drawer and its journey diagram).
//
// A visit's `pages` are the pages its browser loaded from the server: the page
// views it added to the figures. Its trail can hold more steps: moves seen in
// the browser (a page from the cache, or a click inside a site that navigates
// in the browser), found from the referrer of the next request (visits.py).
// Saying "1 page" beside a trail of three is not honest, so both are stated:
//
//   pages 1, two browser steps  ->  "3 pages (2 seen in the browser)"
//   pages 3, none               ->  "3 pages"
//
// The stored `pages` keeps its meaning (both counting roads add it up); the
// browser steps come from the journey's own `in_app` count, or its trail.

const nf = new Intl.NumberFormat("en-US");
const num = (v) => nf.format(Math.round(v));

/* Steps seen only in the browser: the journey's in_app count, else its trail's. */
export function browserSteps(j) {
  if (!j) return 0;
  if (Number.isFinite(j.in_app)) return Math.max(0, j.in_app);
  return (j.trail || []).filter((p) => (Array.isArray(p) ? p[1] === "app" : p && p.page === false)).length;
}

/* {loaded, browser, all}: all = loaded from the server + seen in the browser. */
export function visitPages(j) {
  const loaded = Number.isFinite(j?.pages) ? j.pages : null;
  const browser = browserSteps(j);
  return { loaded, browser, all: loaded == null ? null : loaded + browser };
}

/* "3 pages (2 seen in the browser)", "1 page", "-" when not known. */
export function pagesWords(j, { soFar = false } = {}) {
  const { loaded, browser, all } = visitPages(j);
  if (loaded == null) return "-";
  const tail = soFar ? " so far" : "";
  const main = `${num(all)} page${all === 1 ? "" : "s"}${tail}`;
  return browser ? `${main} (${num(browser)} seen in the browser)` : main;
}

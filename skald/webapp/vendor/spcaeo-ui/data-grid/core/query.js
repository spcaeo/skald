/* spcaeo/ui (data-grid/core/query.js), from github.com/spcaeo/ui at ad51155, vendored by Skald.
   Changes and the reason for each: VERSION.md beside this folder.

   MIT License. Copyright (c) 2026 spcaeo.
   Permission is hereby granted, free of charge, to any person obtaining a copy of this software
   and associated documentation files (the "Software"), to deal in the Software without
   restriction, including without limitation the rights to use, copy, modify, merge, publish,
   distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
   Software is furnished to do so, subject to the following conditions:
   The above copyright notice and this permission notice shall be included in all copies or
   substantial portions of the Software.
   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
   BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
   NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
   DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE. */
/**
 * The grid query: what the user is asking for, independent of any framework,
 * any router, and any UI library.
 *
 * Zero dependencies and no build step — this file runs as-is in a browser, in
 * Node, and on a server. That matters because the SAME parsing and validation
 * has to happen in both places: the client reads the URL to render, the server
 * reads it to build a database query, and if those two disagree about what
 * `page=0` or an unknown sort field means, you get bugs that only appear on a
 * shared link.
 */

import { EMPTY_FILTER } from "./filter-model.js";

export { EMPTY_FILTER };

/** @typedef {"asc" | "desc"} SortDirection */
/** @typedef {{ field: string, direction: SortDirection }} SortSpec */
/** @typedef {"table" | "cards"} DisplayMode */

/**
 * @typedef {object} GridQuery
 * @property {string}      q         free-text search
 * @property {string=}     segment   a named built-in subset
 * @property {FilterGroup} filter    the typed filter model
 * @property {SortSpec[]}  sort      ordered; first entry is primary
 * @property {number}      page      ONE-based, because it is user-visible
 * @property {number}      pageSize
 * @property {DisplayMode} display
 */

export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 200];

export const MAX_PAGE_SIZE = 200;

/** Sorting by more than a few columns is unreadable and slow to index. */
export const MAX_SORT_FIELDS = 3;

/** @type {GridQuery} */
export const DEFAULT_QUERY = {
  q: "",
  segment: undefined,
  filter: EMPTY_FILTER,
  sort: [],
  page: 1,
  pageSize: 25,
  display: "table",
};

/**
 * Clamp anything into a usable query. Never throws.
 *
 * A URL is untrusted input — it can be hand-edited, truncated by a chat client,
 * or five versions out of date in someone's bookmarks. The rule everywhere in
 * this file is that malformed input DEGRADES to a sensible default rather than
 * producing an error page, because an old link showing the default view is a
 * minor annoyance and an old link showing a crash is a support ticket.
 */
export function normalizeQuery(input = {}) {
  const size = Number(input.pageSize);
  const page = Number(input.page);
  return {
    q: typeof input.q === "string" ? input.q : "",
    segment: typeof input.segment === "string" && input.segment ? input.segment : undefined,
    filter: input.filter && Array.isArray(input.filter.conditions) ? input.filter : EMPTY_FILTER,
    sort: Array.isArray(input.sort) ? input.sort.slice(0, MAX_SORT_FIELDS) : [],
    page: Number.isFinite(page) && page >= 1 ? Math.floor(page) : 1,
    pageSize: PAGE_SIZE_OPTIONS.includes(size) ? size : DEFAULT_QUERY.pageSize,
    display: input.display === "cards" ? "cards" : "table",
  };
}

/**
 * Which query concerns changed. The caller says WHAT happened, not what should
 * follow from it — the reset rules and the history mode are decided in one
 * place from this, so no feature has to remember to clear the page itself.
 *
 * @typedef {"search"|"filter"|"segment"|"sort"|"page"|"pageSize"|"display"|"reset"} GridChange
 */

/**
 * Changing the result SET must return to page 1 — otherwise a search that
 * matches three rows while you are on page 7 shows an empty grid, and the
 * emptiness looks like "no matches" rather than "wrong page".
 * @param {GridChange} change
 */
export const changeResetsPage = (change) =>
  change === "search" ||
  change === "filter" ||
  change === "segment" ||
  change === "sort" ||
  change === "pageSize" ||
  change === "reset";

/**
 * An "everything matching this query" selection is a PREDICATE, not a list of
 * ids. The moment the predicate changes, the selection means something the user
 * did not agree to, so it must be dropped rather than reinterpreted.
 * @param {GridChange} change
 */
export const changeDropsSelection = (change) =>
  change === "search" || change === "filter" || change === "segment" || change === "reset";

/**
 * PUSH for navigation the user expects Back to undo; REPLACE for refinement.
 *
 * Every keystroke of a search box pushing history is the classic mistake: Back
 * then has to be pressed once per character to escape the grid.
 * @param {GridChange} change
 * @returns {"push"|"replace"}
 */
export const historyModeFor = (change) =>
  change === "page" || change === "segment" ? "push" : "replace";

/** Deep-ish equality, enough to decide whether a URL write is needed at all. */
export function sameQuery(a, b) {
  return (
    a.q === b.q &&
    a.segment === b.segment &&
    a.page === b.page &&
    a.pageSize === b.pageSize &&
    a.display === b.display &&
    JSON.stringify(a.sort) === JSON.stringify(b.sort) &&
    JSON.stringify(a.filter) === JSON.stringify(b.filter)
  );
}

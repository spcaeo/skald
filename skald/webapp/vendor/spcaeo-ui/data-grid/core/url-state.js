/* spcaeo/ui (data-grid/core/url-state.js), from github.com/spcaeo/ui at ad51155, vendored by Skald.
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
 * The URL is the state. This file is the whole contract, and it is the reason
 * this component exists — there are many good React tables and almost none of
 * them can be linked to.
 *
 * Router-agnostic on purpose: it takes and returns `URLSearchParams` and knows
 * nothing about Next.js, React Router, or the History API. The same functions
 * run on a server reading an incoming request. Bind it to your router in about
 * ten lines; see react/use-grid-url-state.mjs for one binding.
 *
 * THE PARAMETER SHAPE
 *
 *   <namespace>_<suffix>        ten_q, ten_page, ten_sort
 *
 * The namespace prefix means two grids can share one route without fighting
 * over `page`. The suffixes are fixed, so someone who learns one grid's URL can
 * read every other grid's URL in the same product.
 */
import {
  DEFAULT_QUERY,
  MAX_SORT_FIELDS,
  PAGE_SIZE_OPTIONS,
  changeResetsPage,
  changeDropsSelection,
  normalizeQuery,
} from "./query.js";
import { decodeFilter, encodeFilter, isEmptyFilter } from "./filter-model.js";

export const URL_SUFFIX = {
  query: "q",
  segment: "seg",
  filter: "fx",
  sort: "sort",
  page: "page",
  pageSize: "size",
  display: "view",
  /** The open row or drawer, by STABLE id — never a row index. */
  selected: "sel",
};

/** @returns {string} e.g. `param("ten", "page")` -> `"ten_page"` */
export const param = (namespace, suffix) => `${namespace}_${URL_SUFFIX[suffix]}`;

/** `field:dir,field2:dir` — compact, and still readable in a pasted link. */
const encodeSort = (sort) => sort.map((s) => `${s.field}:${s.direction}`).join(",");

function decodeSort(raw, allowed) {
  if (!raw) return [];
  return raw
    .split(",")
    .slice(0, MAX_SORT_FIELDS)
    .map((chunk) => {
      const [field, dir] = chunk.split(":");
      if (!field) return null;
      // A sort field this grid no longer has is DROPPED, not an error: the
      // column was probably renamed since the link was saved.
      if (allowed && !allowed.has(field)) return null;
      return { field, direction: dir === "desc" ? "desc" : "asc" };
    })
    .filter(Boolean);
}

/**
 * Serialise a query into search params, OMITTING every value that equals its
 * default.
 *
 * This is not tidiness. A parameter written into a URL becomes part of your
 * product's public navigation API — it will be in bookmarks, in tickets, in
 * emails — and every one you write down is one you have to keep supporting.
 * Writing `page=1&size=25&view=table&dir=asc` on a fresh grid commits you to
 * four parameters that carry no information.
 *
 * `base` preserves unrelated parameters, so a grid never clobbers another
 * grid's state or the rest of the page's query string.
 */
export function writeGridParams(namespace, query, base) {
  const p = new URLSearchParams(base ?? undefined);
  const set = (suffix, value) => {
    const key = param(namespace, suffix);
    if (value === null || value === undefined || value === "") p.delete(key);
    else p.set(key, String(value));
  };

  set("query", query.q?.trim() || null);
  set("segment", query.segment ?? null);
  set("filter", isEmptyFilter(query.filter) ? null : encodeFilter(query.filter));
  set("sort", query.sort?.length ? encodeSort(query.sort) : null);
  set("page", query.page > 1 ? query.page : null);
  set("pageSize", query.pageSize !== DEFAULT_QUERY.pageSize ? query.pageSize : null);
  set("display", query.display !== DEFAULT_QUERY.display ? query.display : null);
  return p;
}

/**
 * Read a query out of search params, validating every one.
 *
 * @param {string} namespace
 * @param {URLSearchParams} search
 * @param {{sortableFields?: Set<string>, filterFields?: Map<string,string>, segmentIds?: string[]}} [opts]
 * @returns {{query: import("./query.js").GridQuery, droppedFilterFields: string[]}}
 */
export function readGridParams(namespace, search, opts = {}) {
  const get = (suffix) => search.get(param(namespace, suffix));

  const { filter, dropped } = decodeFilter(get("filter"), opts.filterFields);

  const rawSegment = get("segment");
  // A segment this grid does not declare is dropped, so a stale link shows the
  // default view rather than an empty one that looks like "no records".
  const segment =
    rawSegment && (!opts.segmentIds || opts.segmentIds.includes(rawSegment))
      ? rawSegment
      : undefined;

  const size = Number(get("pageSize"));
  const page = Number(get("page"));

  return {
    query: normalizeQuery({
      q: get("query") ?? "",
      segment,
      filter,
      sort: decodeSort(get("sort"), opts.sortableFields),
      page: Number.isFinite(page) && page >= 1 ? page : 1,
      pageSize: PAGE_SIZE_OPTIONS.includes(size) ? size : DEFAULT_QUERY.pageSize,
      display: get("display") === "cards" ? "cards" : "table",
    }),
    droppedFilterFields: dropped,
  };
}

/**
 * Apply a change and let the consequences follow automatically.
 *
 * Reset rules live HERE, in one place, rather than as `delete("page")` calls
 * scattered through every feature. Scattered resets are how you end up with a
 * grid where changing the filter resets the page but changing the segment does
 * not, and nobody can say whether that was deliberate.
 *
 * @returns {{query, history: "push"|"replace", dropSelection: boolean}}
 */
export function applyChange(next, change) {
  const query = normalizeQuery(next);
  return {
    query: changeResetsPage(change) ? { ...query, page: 1 } : query,
    history: change === "page" || change === "segment" ? "push" : "replace",
    dropSelection: changeDropsSelection(change),
  };
}

/**
 * Clear only THIS grid's parameters. Anything else on the query string — a
 * second grid, a drawer, a campaign tag — is left alone. Resetting a grid by
 * clearing the whole query string is a bug that only shows up on the one page
 * that has two grids.
 */
export function clearNamespace(namespace, base) {
  const p = new URLSearchParams(base ?? undefined);
  for (const suffix of Object.keys(URL_SUFFIX)) p.delete(param(namespace, suffix));
  return p;
}

/** Build a shareable link to an exact view, for a "Copy link" button. */
export function buildGridUrl(pathname, namespace, query, base) {
  const qs = writeGridParams(namespace, query, base).toString();
  return qs ? `${pathname}?${qs}` : pathname;
}

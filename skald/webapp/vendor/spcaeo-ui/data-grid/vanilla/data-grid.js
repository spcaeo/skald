/* spcaeo/ui (data-grid/vanilla/data-grid.js), from github.com/spcaeo/ui at ad51155, vendored by Skald.
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
 * DATA GRID — no framework, no dependencies.
 *
 * Popovers use the native `popover` attribute and dialogs use `<dialog>`, so
 * this imports nothing from your app and cannot collide with your button, your
 * dialog, or your version of anything. Drop the stylesheet and this file into a
 * page and it works.
 *
 *   import { createDataGrid } from "./vanilla/data-grid.js";
 *
 *   const grid = createDataGrid(document.querySelector("#people"), {
 *     namespace: "ppl",
 *     columns: [
 *       { id: "name",   label: "Name",   sortable: true },
 *       { id: "status", label: "Status", render: (row) => badge(row.status) },
 *       { id: "seats",  label: "Seats",  align: "right", sortable: true },
 *     ],
 *     filters: [{ id: "status", label: "Status", type: "enum", options: [...] }],
 *     segments: [{ id: "active", label: "Active" }],
 *     getRowId: (row) => row.id,
 *     async load(query, signal) {
 *       const res = await fetch(`/api/people?${query.searchParams}`, { signal });
 *       if (!res.ok) throw await gridError(res);
 *       return res.json();                     // { rows, total }
 *     },
 *   });
 */
import {
  applyChange,
  clearNamespace,
  readGridParams,
  writeGridParams,
} from "../core/url-state.js";
import { PAGE_SIZE_OPTIONS } from "../core/query.js";
import { describeCondition, encodeFilter } from "../core/filter-model.js";

const h = (tag, props = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2).toLowerCase(), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
};

const ICON = {
  search:
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  x: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  sort: '<svg class="dg-sort-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m6 9 6 6 6-6"/></svg>',
  filter:
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 5h18M6 12h12M10 19h4"/></svg>',
  alert:
    '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5v.01"/></svg>',
  empty:
    '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16v12H4z"/><path d="M4 11h16"/></svg>',
};

let popoverSeq = 0;

/* Skald patch 1: where the grid's state lives. Upstream read and wrote
   location.search directly; a host whose state is in the hash passes
   `params: { read(), write(params, { push }) }`. This default keeps upstream's
   behaviour, except that writing (and Reset) never drops the page's hash. */
const SEARCH_PARAMS = {
  read: () => new URLSearchParams(location.search),
  write(params, { push = false } = {}) {
    const qs = params.toString();
    const url = `${location.pathname}${qs ? `?${qs}` : ""}${location.hash}`;
    if (push) history.pushState(null, "", url);
    else history.replaceState(null, "", url);
  },
};

/* Skald patch 5: a column can be centred. Upstream knew only `align: "right"`
   (class dg-num); `align: "center"` gives dg-center, for a yes/no or a small tag. */
const alignClass = (col) =>
  col.align === "right" ? "dg-num" : col.align === "center" ? "dg-center" : null;

export function createDataGrid(host, config) {
  const {
    namespace,
    columns,
    filters = [],
    segments = [],
    getRowId = (row) => row.id,
    selectable = false,
    load,
    emptyMessage = "Nothing here yet.",
    searchPlaceholder = "Search…",
    params = SEARCH_PARAMS,
  } = config;

  const sortable = new Set(columns.filter((c) => c.sortable).map((c) => c.id));
  const filterFields = new Map(filters.map((f) => [f.id, f.type ?? "enum"]));
  const segmentIds = segments.map((s) => s.id);

  /** @type {{status:string, rows:any[], total:number|null, error:any}} */
  let state = { status: "loading", rows: [], total: null, error: null };
  let selection = new Set();
  let inflight = null;
  let searchTimer = 0;

  const readUrl = () =>
    readGridParams(namespace, params.read(), {
      sortableFields: sortable,
      filterFields,
      segmentIds,
    });

  let { query, droppedFilterFields } = readUrl();

  host.classList.add("dg");
  const el = {
    toolbar: h("div", { class: "dg-toolbar" }),
    segments: h("div", { class: "dg-segments", role: "tablist" }),
    chips: h("div", { class: "dg-chips" }),
    selection: h("div", { class: "dg-selection", hidden: true, role: "status" }),
    frame: h("div", { class: "dg-frame" }),
    pagination: h("div", { class: "dg-pagination" }),
    live: h("div", {
      class: "dg-sr-only",
      role: "status",
      "aria-live": "polite",
      style: "position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)",
    }),
  };
  host.append(el.segments, el.toolbar, el.chips, el.selection, el.frame, el.pagination, el.live);

  // --- url ----------------------------------------------------------------

  function commit(next, change) {
    const result = applyChange(next, change);
    query = result.query;
    if (result.dropSelection) selection.clear();

    // Native history writes rather than a router call: rapid refinement should
    // not re-render the whole page, and it must not stack one history entry per
    // keystroke or Back becomes unusable.
    params.write(writeGridParams(namespace, query, params.read()), {
      push: result.history === "push",
    });

    render();
    fetchRows();
  }

  /* Skald patch 2: a grid that has left the page stops answering Back, and
     destroy() removes the listener, so redraws do not pile them up. */
  const onPopState = () => {
    if (!host.isConnected) return;
    ({ query, droppedFilterFields } = readUrl());
    selection.clear();
    render();
    fetchRows();
  };
  addEventListener("popstate", onPopState);

  // --- data ---------------------------------------------------------------

  async function fetchRows() {
    inflight?.abort();
    const controller = new AbortController();
    inflight = controller;

    // Keep rows on screen while refreshing. Replacing them with a spinner
    // throws away whatever the person was reading.
    state.status = state.rows.length ? "refreshing" : "loading";
    render();

    try {
      const params = writeGridParams(namespace, query);
      const result = await load({ ...query, searchParams: params.toString() }, controller.signal);
      if (controller.signal.aborted) return;
      state = {
        status: "ready",
        rows: result.rows ?? [],
        total: result.total ?? null,
        error: null,
      };
      announce(`${state.total ?? state.rows.length} results`);
    } catch (error) {
      if (controller.signal.aborted || error?.name === "AbortError") return;
      state = { ...state, status: "error", error };
    }
    render();
  }

  const announce = (text) => {
    el.live.textContent = text;
  };

  // --- toolbar ------------------------------------------------------------

  function renderToolbar() {
    // Skald patch 3: the search box is rebuilt on every render; keep the
    // reader's focus and caret in it, or typing stops after each pause.
    const typing = el.toolbar.contains(document.activeElement) && document.activeElement.type === "search"
      ? [document.activeElement.selectionStart, document.activeElement.selectionEnd]
      : null;
    el.toolbar.replaceChildren();

    const input = h("input", {
      type: "search",
      value: query.q,
      placeholder: searchPlaceholder,
      "aria-label": searchPlaceholder,
      onInput: (e) => {
        clearTimeout(searchTimer);
        const value = e.target.value;
        // Debounced, because one request per keystroke is how you rate-limit
        // yourself. 250ms is long enough to batch typing, short enough to feel
        // immediate.
        searchTimer = setTimeout(() => commit({ ...query, q: value }, "search"), 250);
      },
      onKeydown: (e) => {
        if (e.key === "Escape" && e.target.value) {
          e.target.value = "";
          commit({ ...query, q: "" }, "search");
        }
      },
    });
    const search = h(
      "div",
      { class: "dg-search" },
      h("span", { class: "dg-search-icon", html: ICON.search }),
      input,
      query.q
        ? h("button", {
            class: "dg-search-clear",
            type: "button",
            "aria-label": "Clear search",
            html: ICON.x,
            onClick: () => commit({ ...query, q: "" }, "search"),
          })
        : null,
    );
    el.toolbar.append(search);
    if (typing) {
      input.focus({ preventScroll: true });
      input.setSelectionRange(...typing);
    }

    for (const field of filters) el.toolbar.append(filterMenu(field));

    el.toolbar.append(h("div", { class: "dg-toolbar-spacer" }));

    const active = query.filter.conditions.length || query.q || query.segment;
    if (active) {
      el.toolbar.append(
        h("button", {
          class: "dg-btn",
          type: "button",
          text: "Reset",
          onClick: () => {
            // Skald patch 1: only this grid's keys go; the rest of the address stays.
            params.write(clearNamespace(namespace, params.read()), { push: false });
            ({ query, droppedFilterFields } = readUrl());
            selection.clear();
            render();
            fetchRows();
          },
        }),
      );
    }
  }

  /** A filter menu built on the native popover API — no library, no portal. */
  function filterMenu(field) {
    const id = `dg-pop-${++popoverSeq}`;
    const current = query.filter.conditions.find((c) => c.field === field.id);
    const chosen = new Set(current?.values ?? []);

    const pop = h(
      "div",
      { class: "dg-pop", id, popover: "auto" },
      h("div", { class: "dg-pop-title", text: field.label }),
      ...(field.options ?? []).map((opt) =>
        h(
          "label",
          { class: "dg-opt" },
          h("input", {
            type: "checkbox",
            checked: chosen.has(opt.value),
            onChange: (e) => {
              e.target.checked ? chosen.add(opt.value) : chosen.delete(opt.value);
            },
          }),
          opt.label ?? opt.value,
        ),
      ),
      h(
        "div",
        { class: "dg-pop-actions" },
        h("button", {
          class: "dg-btn dg-btn-primary",
          type: "button",
          text: "Apply",
          onClick: () => {
            pop.hidePopover();
            const others = query.filter.conditions.filter((c) => c.field !== field.id);
            const next = chosen.size
              ? [...others, { field: field.id, operator: "in", values: [...chosen] }]
              : others;
            commit({ ...query, filter: { conjunction: "and", conditions: next } }, "filter");
          },
        }),
        h("button", {
          class: "dg-btn",
          type: "button",
          text: "Clear",
          onClick: () => {
            pop.hidePopover();
            commit(
              {
                ...query,
                filter: {
                  conjunction: "and",
                  conditions: query.filter.conditions.filter((c) => c.field !== field.id),
                },
              },
              "filter",
            );
          },
        }),
      ),
    );

    const trigger = h(
      "button",
      { class: "dg-btn", type: "button", popovertarget: id, "aria-expanded": "false" },
      h("span", { html: ICON.filter }),
      field.label,
      chosen.size ? h("span", { class: "dg-segment-count", text: String(chosen.size) }) : null,
    );

    // The native popover has no anchoring in Safari/Firefox yet, so position it
    // ourselves. Cheap, and avoids a positioning dependency.
    pop.addEventListener("beforetoggle", (e) => {
      trigger.setAttribute("aria-expanded", String(e.newState === "open"));
      if (e.newState !== "open") return;
      const r = trigger.getBoundingClientRect();
      pop.style.left = `${Math.min(r.left, innerWidth - 240)}px`;
      pop.style.top = `${r.bottom + 6}px`;
    });

    return h("span", {}, trigger, pop);
  }

  function renderSegments() {
    el.segments.replaceChildren();
    if (!segments.length) {
      el.segments.hidden = true;
      return;
    }
    el.segments.hidden = false;
    for (const seg of segments) {
      const on = (query.segment ?? segments[0]?.id) === seg.id;
      el.segments.append(
        h(
          "button",
          {
            class: "dg-segment",
            role: "tab",
            type: "button",
            "aria-selected": String(on),
            // Skald patch 4 (VERSION.md): roving tabindex, one tab stop for the strip.
            tabindex: on ? "0" : "-1",
            onClick: () =>
              commit(
                { ...query, segment: seg.id === segments[0]?.id ? undefined : seg.id },
                "segment",
              ),
          },
          seg.label,
          seg.count !== undefined
            ? h("span", { class: "dg-segment-count", text: String(seg.count) })
            : null,
        ),
      );
    }
    // Skald patch 4: arrows, Home and End move between segments and pick one (WAI-ARIA tabs).
    el.segments.onkeydown = (e) => {
      const tabs = [...el.segments.querySelectorAll('[role="tab"]')];
      const at = tabs.indexOf(document.activeElement);
      if (at < 0) return;
      const to = { ArrowRight: at + 1, ArrowLeft: at - 1, Home: 0, End: tabs.length - 1 }[e.key];
      if (to === undefined) return;
      e.preventDefault();
      const next = tabs[(to + tabs.length) % tabs.length];
      next.focus();
      next.click();
    };
  }

  function renderChips() {
    el.chips.replaceChildren();
    const chips = query.filter.conditions.map((condition) =>
      h(
        "span",
        { class: "dg-chip" },
        describeCondition(
          condition,
          filters.find((f) => f.id === condition.field),
        ),
        h("button", {
          type: "button",
          "aria-label": `Remove filter ${condition.field}`,
          html: ICON.x,
          onClick: () =>
            commit(
              {
                ...query,
                filter: {
                  conjunction: "and",
                  conditions: query.filter.conditions.filter((c) => c !== condition),
                },
              },
              "filter",
            ),
        }),
      ),
    );

    // A link whose filters no longer exist must SAY so. Silently showing an
    // unfiltered grid means the recipient sees different data than the sender
    // and neither of them knows.
    if (droppedFilterFields.length) {
      chips.push(
        h("span", {
          class: "dg-chip dg-chip-warn",
          role: "status",
          text: `${droppedFilterFields.length} filter${droppedFilterFields.length > 1 ? "s" : ""} from this link no longer exist`,
        }),
      );
    }
    el.chips.hidden = !chips.length;
    el.chips.append(...chips);
  }

  // --- body ---------------------------------------------------------------

  function stateBlock(kind, { title, body, actions = [], meta }) {
    return h(
      "div",
      { class: `dg-state dg-state-${kind}` },
      h("div", { class: "dg-state-icon", html: kind === "error" ? ICON.alert : ICON.empty }),
      h("div", { class: "dg-state-title", text: title }),
      body ? h("div", { class: "dg-state-body", text: body }) : null,
      actions.length ? h("div", { class: "dg-state-actions" }, ...actions) : null,
      meta ? h("div", { class: "dg-state-meta", text: meta }) : null,
    );
  }

  const retryButton = () =>
    h("button", { class: "dg-btn", type: "button", text: "Try again", onClick: fetchRows });

  function renderBody() {
    el.frame.replaceChildren();
    el.frame.classList.toggle("dg-refreshing", state.status === "refreshing");

    if (state.status === "loading") {
      el.frame.append(skeleton());
      return;
    }

    if (state.status === "error") {
      const err = state.error ?? {};
      const offline = !navigator.onLine || err.code === "NETWORK_OFFLINE";
      el.frame.append(
        stateBlock("error", {
          title: offline ? "You are offline" : "This list could not be loaded",
          // The distinction that matters: a failed request is not a count of zero.
          body: offline
            ? "The rows below could not be refreshed. Your filters are still saved."
            : "This is not a count of zero — the result is unknown. Your filters and sorting are still saved.",
          actions: [retryButton(), err.requestId || err.code ? copyButton(err) : null].filter(
            Boolean,
          ),
          meta: [err.code, err.requestId].filter(Boolean).join(" · ") || undefined,
        }),
      );
      return;
    }

    if (!state.rows.length) {
      const filtered = query.q || query.filter.conditions.length || query.segment;
      el.frame.append(
        filtered
          ? // "No records exist" and "nothing matched your filter" are different
            // facts and need different words and different actions.
            stateBlock("nomatch", {
              title: "No results match",
              body: "No rows match the current search and filters.",
              actions: [
                h("button", {
                  class: "dg-btn",
                  type: "button",
                  text: "Clear search and filters",
                  onClick: () =>
                    commit(
                      {
                        ...query,
                        q: "",
                        filter: { conjunction: "and", conditions: [] },
                        segment: undefined,
                      },
                      "reset",
                    ),
                }),
              ],
            })
          : stateBlock("empty", { title: "Nothing here yet", body: emptyMessage }),
      );
      return;
    }

    el.frame.append(
      h("div", { class: "dg-scroll" }, query.display === "cards" ? cards() : table()),
    );
  }

  function copyButton(err) {
    return h("button", {
      class: "dg-btn",
      type: "button",
      text: "Copy error details",
      onClick: async (e) => {
        // Deliberately narrow: a code, an id, where and when. No tokens, no row
        // data, no stack — a diagnostic a user can paste into a ticket safely.
        const lines = [
          `Error: ${err.code ?? "UNKNOWN"}`,
          `Request ID: ${err.requestId ?? "not available"}`,
          `Page: ${location.pathname}`,
          `Grid: ${namespace}`,
          `Time: ${new Date().toISOString()}`,
          `Online: ${navigator.onLine ? "yes" : "no"}`,
        ];
        try {
          await navigator.clipboard.writeText(lines.join("\n"));
          e.target.textContent = "Copied";
        } catch {
          e.target.textContent = "Press Ctrl+C";
        }
        setTimeout(() => {
          e.target.textContent = "Copy error details";
        }, 1800);
      },
    });
  }

  function skeleton() {
    const body = h("tbody");
    for (let r = 0; r < 6; r++) {
      body.append(
        h(
          "tr",
          { class: "dg-skeleton-row" },
          ...columns.map(() =>
            h(
              "td",
              {},
              h("span", {
                class: "dg-skeleton-cell",
                style: `width:${40 + Math.round(((r * 37) % 5) * 12)}%`,
              }),
            ),
          ),
        ),
      );
    }
    return h(
      "div",
      { class: "dg-scroll", "aria-busy": "true" },
      h("table", { class: "dg-table" }, headRow(), body),
    );
  }

  function headRow() {
    return h(
      "thead",
      {},
      h(
        "tr",
        {},
        selectable
          ? h(
              "th",
              { class: "dg-checkbox" },
              h("input", {
                type: "checkbox",
                "aria-label": "Select all rows on this page",
                checked:
                  state.rows.length > 0 && state.rows.every((r) => selection.has(getRowId(r))),
                onChange: (e) => {
                  for (const row of state.rows)
                    e.target.checked
                      ? selection.add(getRowId(row))
                      : selection.delete(getRowId(row));
                  render();
                },
              }),
            )
          : null,
        ...columns.map((col) => {
          // Skald patch 6: the order shown may be the host's default (no sort in the
          // address), and a click may cycle asc, desc, default (config.nextSort).
          const active = (config.shownSort ? config.shownSort(query) : query.sort).find((s) => s.field === col.id);
          return h(
            "th",
            {
              class: alignClass(col),
              scope: "col",
              "aria-sort": active
                ? active.direction === "asc"
                  ? "ascending"
                  : "descending"
                : col.sortable
                  ? "none"
                  : null,
            },
            col.sortable
              ? h(
                  "button",
                  {
                    class: "dg-sort",
                    type: "button",
                    onClick: () =>
                      commit(
                        {
                          ...query,
                          sort: config.nextSort
                            ? config.nextSort(col.id, query)
                            : [
                                {
                                  field: col.id,
                                  direction: active?.direction === "asc" ? "desc" : "asc",
                                },
                              ],
                        },
                        "sort",
                      ),
                  },
                  col.label,
                  // Skald patch 7: the shared tables' marks (js/table.js): ▲ ascending,
                  // ▼ descending (biggest first), a faint ↕ on a sortable column not sorted.
                  h("span", { class: "dir", "aria-hidden": "true" },
                    active ? (active.direction === "asc" ? "▲" : "▼") : "↕"),
                )
              : col.label,
          );
        }),
      ),
      // Skald patch 6: a row of the host's own under the headers (the column filters).
      config.headExtra ? config.headExtra() : null,
    );
  }

  function table() {
    const body = h(
      "tbody",
      {},
      ...state.rows.map((row) => {
        const id = getRowId(row);
        return h(
          "tr",
          { "aria-selected": selectable ? String(selection.has(id)) : null },
          selectable
            ? h(
                "td",
                { class: "dg-checkbox" },
                h("input", {
                  type: "checkbox",
                  checked: selection.has(id),
                  "aria-label": `Select ${String(row[columns[0].id] ?? id)}`,
                  onChange: () => {
                    selection.has(id) ? selection.delete(id) : selection.add(id);
                    render();
                  },
                }),
              )
            : null,
          ...columns.map((col) => {
            const cell = h("td", { class: alignClass(col) });
            const value = col.render ? col.render(row) : row[col.id];
            if (value?.nodeType) cell.append(value);
            else
              cell.textContent =
                value === null || value === undefined || value === "" ? "—" : String(value);
            return cell;
          }),
        );
      }),
    );
    return h("table", { class: "dg-table" }, headRow(), body);
  }

  function cards() {
    return h(
      "div",
      { class: "dg-cards" },
      ...state.rows.map((row) =>
        h(
          "dl",
          { class: "dg-card" },
          ...columns.flatMap((col) => [
            h("dt", { text: col.label }),
            h("dd", { text: String(col.render ? "" : (row[col.id] ?? "—")) }),
          ]),
        ),
      ),
    );
  }

  function renderSelection() {
    el.selection.replaceChildren();
    el.selection.hidden = selection.size === 0;
    if (!selection.size) return;
    el.selection.append(
      // Say the scope out loud. "Selected" that silently means "on this page"
      // is how a bulk action surprises someone.
      h("span", {}, h("strong", { text: String(selection.size) }), ` selected on this page`),
      h("button", {
        class: "dg-btn",
        type: "button",
        text: "Clear",
        onClick: () => {
          selection.clear();
          render();
        },
      }),
    );
  }

  function renderPagination() {
    el.pagination.replaceChildren();
    if (state.status === "error") return;
    const total = state.total;
    const from = (query.page - 1) * query.pageSize + 1;
    const to =
      total === null ? from + state.rows.length - 1 : Math.min(query.page * query.pageSize, total);
    const pages = total === null ? null : Math.max(1, Math.ceil(total / query.pageSize));

    el.pagination.append(
      h(
        "span",
        { class: "dg-count" },
        state.rows.length ? `${from}–${to}` : "0",
        total === null ? " shown" : ` of ${total.toLocaleString()}`,
      ),
      h("div", { class: "dg-toolbar-spacer" }),
      h(
        "label",
        {},
        "Rows ",
        h(
          "select",
          {
            "aria-label": "Rows per page",
            onChange: (e) => commit({ ...query, pageSize: Number(e.target.value) }, "pageSize"),
          },
          ...PAGE_SIZE_OPTIONS.map((n) =>
            h("option", { value: n, selected: n === query.pageSize }, String(n)),
          ),
        ),
      ),
      h(
        "div",
        { class: "dg-page-buttons" },
        h("button", {
          class: "dg-btn",
          type: "button",
          text: "Previous",
          disabled: query.page <= 1,
          onClick: () => commit({ ...query, page: query.page - 1 }, "page"),
        }),
        h("button", {
          class: "dg-btn",
          type: "button",
          text: "Next",
          disabled: pages !== null ? query.page >= pages : state.rows.length < query.pageSize,
          onClick: () => commit({ ...query, page: query.page + 1 }, "page"),
        }),
      ),
      pages ? h("span", { text: `Page ${query.page} of ${pages}` }) : null,
    );
  }

  function render() {
    renderSegments();
    renderToolbar();
    renderChips();
    renderSelection();
    renderBody();
    renderPagination();
  }

  render();
  fetchRows();

  return {
    refresh: fetchRows,
    get query() {
      return query;
    },
    /* Skald patch 6: the host changes the query as a control of the grid's own would
       (its column filters: page 1 again, written to the address). */
    change(patch, kind = "filter") {
      commit({ ...query, ...patch }, kind);
    },
    get selection() {
      return [...selection];
    },
    destroy() {
      inflight?.abort();
      clearTimeout(searchTimer);
      removeEventListener("popstate", onPopState);
      host.replaceChildren();
    },
  };
}

export default createDataGrid;

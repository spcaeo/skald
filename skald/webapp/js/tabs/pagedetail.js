// The page leaderboard: the last 30 whole days with change, or today's pages.
// Selecting a page opens its story (pagestory.js).

import { h, change } from "../ui.js";
import { pathMatch } from "../data.js";
import { table } from "../table.js";
import * as S from "../state.js";


export function leaderboard(m, s, r) {
  const f = m.x.pages;
  const keep = pathMatch(s);
  // Today, or before 30 whole days exist: today's pages, without a comparison.
  if (r?.kind === "today" || !(f.pages || []).length) {
    const rows = (f.today?.pages || []).filter((p) => keep(p.path)).map((p) => ({ ...p, __k: p.path }));
    const cols = [{ key: "path", label: "Page", path: true }, { key: "views", label: "Views", num: true }, { key: "readers", label: "Visitors", num: true },
      { key: "entries", label: "Entries", num: true }, { key: "ai_asked", label: "AI asked", num: true }, { key: "ai_training", label: "AI training", num: true }, { key: "search", label: "Search", num: true }];
    return h("div", null, table(cols, { caption: "Page leaderboard, today so far", rows, file: `pages-today-${m.today}.csv`, sortKey: "views", limit: 15,
      rowClass: () => "go", onRow: (row) => S.set({ page: row.path }), empty: "No page read yet today." }),
    h("p", { class: "note" }, (f.pages || []).length ? "Today so far, live and partial." : "Today so far. The 30-day leaderboard, with change against the 30 days before, appears once 30 whole days are recorded."));
  }
  const rows = (f.pages || []).filter((p) => keep(p.path)).map((p) => ({ ...p, __k: p.path }));
  const cols = [
    { key: "path", label: "Page", path: true },
    { key: "views", label: "Views", num: true },
    { key: "readers", label: "Visitors", num: true },
    { key: "entries", label: "Entries", num: true },
    { key: "exits", label: "Exits", num: true },
    // Exit rate: the share of the page's visits that ended on it (pages.json, null under 10 visits).
    { key: "exit_rate", label: "Exit rate", num: true, sort: (row) => row.exit_rate ?? -1, fmt: (v) => (v == null ? "too few" : `${Math.round(v * 100)}%`), csv: (row) => row.exit_rate ?? "" },
    { key: "change_pct", label: "Change", num: true, fmt: (v, row) => { const [a, w] = change(row.views, row.prev?.views ?? null); return v == null ? "not comparable" : `${a}${a ? " " : ""}${w}`; }, csv: (row) => row.change_pct ?? "" },
    { key: "ai_asked", label: "AI asked", num: true },
  ];
  const el = table(cols, { caption: "Page leaderboard", rows, file: `pages-${f.period?.first}-to-${f.period?.last}.csv`, sortKey: "views", limit: 15,
    rowClass: () => "go", onRow: (row) => S.set({ page: row.path }), empty: "No page matches." });
  const p = f.period || {};
  return h("div", null, el, h("p", { class: "note" }, `Last ${p.days || 30} whole days (${p.first} to ${p.last}). Change is against the ${p.days || 30} days before, only when both are complete. Select a page for its detail.`));
}

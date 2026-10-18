// Live mode (2.7.0): "Today · Live" in the top bar (js/modes.js). On, the period
// is Today (range=today in the address, so every today-path in data.js stays as
// it is) on every section; off, the period goes back to the one before.
//
// ---------------------------------------------------- for section builders
//   import { isLive } from "../mode-live.js";
//   if (isLive(s)) ...   // draw the tab's Live view: today so far (the map's "Live mode" column)
//
// Nothing else to do: while Live is on, main.js redraws the open tab every 2
// minutes, when the live snapshot (app.json `live`) is rewritten. A tab that
// refreshes itself says `polls: true` in its registry entry (js/tabs/s-*.js),
// and the redraw leaves it alone (a redraw would close its detail panel).
// Live and Compare are never on together: today is partial, never compared.

import * as S from "./state.js";

export const isLive = (s) => s.range === "today";

const KEY = "ti-live-back";            // the period to go back to, this tab of the browser only
const FALLBACK = { range: "30d", from: "", to: "" };   // where Live goes back to when it kept no period (the default is Today since 2.10.1)

// The period Live leaves for: the one it was turned on from, else the default.
export function backRange() {
  let b = null;
  try { b = JSON.parse(sessionStorage.getItem(KEY) || "null"); } catch { /* storage blocked */ }
  if (!b || typeof b.range !== "string" || b.range === "today") return { ...FALLBACK };
  return { range: b.range, from: b.from || "", to: b.to || "" };
}

// Live on: Today, Compare off, the period kept to go back to. Off: back to it.
export function setLive(on, s = S.read()) {
  if (on) {
    if (s.range !== "today") {
      try { sessionStorage.setItem(KEY, JSON.stringify({ range: s.range, from: s.from, to: s.to })); } catch { /* storage blocked */ }
    }
    S.set({ range: "today", cmp: "" });
  } else S.set(backRange());
}

// How fresh the live count is: {fresh, at} (at: when it was written, ISO).
// Fresh when written today and within the last ten minutes (it runs every two).
export function liveState(m, now = Date.now()) {
  const L = m?.live;
  const at = L?.generated_at && L.day === m.today ? L.generated_at : null;
  return { at, fresh: !!at && now - Date.parse(at) < 10 * 60000 };
}

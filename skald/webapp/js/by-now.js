// "Vs yesterday at this hour" (Overview > Summary in Live mode): today so far
// against yesterday counted up to the same time of day. Pure: no DOM, so node
// can test it (tests/js/by-now.mjs).
//
// Nothing is counted here. The figures come from two files, each recounted by
// its own audit:
//   * visitors, pages read, visitors from AI: the live snapshot's `by_now`
//     (by_now.py; app.json live.by_now), yesterday from midnight to the same
//     local time as today's count, by the same tally; audit_by_now.py
//   * leads: conversions.json today.by_now (conversions_leads.by_now), finished
//     forms and bookings to the same local time; audit_conversions_leads.py
// Yesterday withheld, partial, not recorded or not counted: the comparison says
// "not recorded", never a fall to zero. A day's series by hour is drawn only when
// its hours add up to the figure shown beside it.

export const KEYS = ["visitors", "pages", "leads", "ai"];
const FIELD = { visitors: "visitors", pages: "pages", ai: "ai_visitors" };
const SMALL = 10;   // under this many yesterday, the change is said as a count, not a percent

const WHY = {
  withheld: "yesterday's count was withheld: the second count disagreed",
  partial: "yesterday is only partly in the log",
  empty: "yesterday has no line in the log up to this time",
  not_recorded: "leads were not recorded yesterday",
};

const sum = (a) => (a || []).reduce((x, y) => x + (y || 0), 0);
const hhmm = (iso) => String(iso || "").slice(11, 16);

/* The four comparisons. live: app.json `live`; conv: conversions.json (or null);
   today: {visitors, pages, leads, ai} as the tiles show them (null when not counted).
   Each: {key, today, yesterday, at ("14:33"), why (when yesterday is not recorded),
   hoursToday, hoursYesterday (24 numbers, or null)} */
export function comparisons(live, conv, today) {
  const bn = live?.state === "ok" ? live.by_now || null : null;
  const cb = conv?.today?.state === "ok" ? conv.today.by_now || null : null;
  return KEYS.map((key) => {
    const part = key === "leads" ? cb : bn;
    const field = key === "leads" ? "leads" : FIELD[key];
    const ok = part?.state === "ok" && part[field] != null;
    const t = today?.[key] ?? null;
    const ht = part?.today_hours ? (key === "leads" ? part.today_hours : part.today_hours[field]) : null;
    const hy = ok && part.hours ? (key === "leads" ? part.hours : part.hours[field]) : null;
    return {
      key, today: t, yesterday: ok ? part[field] : null, at: part ? hhmm(part.until) : "",
      why: ok ? "" : !part ? (key === "leads" ? "no leads file for yesterday" : "not counted for this page") : WHY[part.state] || "not recorded",
      // A series is drawn only when it adds up to its figure.
      hoursToday: ht && t != null && sum(ht) === t ? ht : null,
      hoursYesterday: hy && sum(hy) === part[field] ? hy : null,
    };
  });
}

/* The change in words: {dir: "up"|"down"|"same", text: "+18%" | "+2" | "same"},
   or null when either side is not recorded. A percent only over SMALL or more
   yesterday; under that, the difference as a count. */
export function delta(today, yesterday) {
  if (today == null || yesterday == null) return null;
  const d = today - yesterday;
  if (d === 0) return { dir: "same", text: "same" };
  const dir = d > 0 ? "up" : "down";
  if (yesterday < SMALL) return { dir, text: `${d > 0 ? "+" : "−"}${Math.abs(d)}` };
  const p = Math.round((d / yesterday) * 100);
  if (p === 0) return { dir: "same", text: "about the same" };
  return { dir, text: `${p > 0 ? "+" : "−"}${Math.abs(p)}%` };
}

/* A day's running total as points [hour, total] from midnight to `at` ("14:33"):
   one point at each whole hour, the last at the time itself. */
export function running(hours, at) {
  if (!hours || !/^\d\d:\d\d$/.test(at || "")) return null;
  const [hh, mm] = at.split(":").map(Number);
  const pts = [[0, 0]];
  let c = 0;
  for (let i = 0; i < hh; i++) { c += hours[i] || 0; pts.push([i + 1, c]); }
  c += hours[hh] || 0;
  if (mm > 0 || c !== pts[pts.length - 1][1]) pts.push([hh + mm / 60, c]);
  // Nothing may be counted after the time itself.
  for (let i = hh + 1; i < 24; i++) if (hours[i]) return null;
  return pts;
}

/* Visitors who arrived in the last k minutes (Real time's per-minute `started`). */
export function arrived(perMinute, k = 5) {
  const rows = perMinute || [];
  return rows.slice(-k).reduce((a, r) => a + (r.started || 0), 0);
}

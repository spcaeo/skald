// "Direct, likely <reason>" as the page reads it (direct_likely.py): an inferred split of
// the Direct visits, never a count. Pure, no DOM (tests/js/direct-likely.mjs).
// campaigns.json carries the day kind as days[].direct_likely and today.direct_likely,
// null on a day it was not recorded, and the method as direct_likely.

export const REASONS = ["checkout", "in_app", "shared"];
export const WORDS = { checkout: "checkout or payment return", in_app: "in-app browser", shared: "shared link" };
export const reasonLabel = (k) => `Direct, likely ${WORDS[k] || k}`;

// The range's blobs: verified days only (a withheld day is left out), or today's.
export function rangeBlobs(f, r) {
  if (!f || !r) return { blobs: [], days: 0 };
  const days = r.kind === "today" ? (f.today ? [f.today] : [])
    : (f.days || []).filter((d) => d.state === "ok" && d.day >= r.first && d.day <= r.last);
  return { blobs: days.map((d) => d.direct_likely).filter(Boolean), days: days.length };
}

const addTo = (into, obj) => { for (const [k, v] of Object.entries(obj || {})) into[k] = (into[k] || 0) + (v || 0); };

// The blobs summed. `ok` is false when a sum the server promises does not hold, and the
// page then withholds the split rather than show figures that do not add up.
export function sumDirect(blobs) {
  const t = { visits: 0, direct: 0, likely: 0, plain: 0, reasons: {}, details: {}, windows: new Set(), ok: true };
  for (const k of REASONS) { t.reasons[k] = 0; t.details[k] = {}; }
  for (const b of blobs || []) {
    t.visits += b.visits || 0; t.direct += b.direct || 0; t.likely += b.likely || 0; t.plain += b.plain || 0;
    addTo(t.reasons, b.reasons);
    for (const k of REASONS) addTo(t.details[k], (b.details || {})[k]);
    if (b.share_window_minutes != null) t.windows.add(b.share_window_minutes);
  }
  const sum = (o) => Object.values(o).reduce((a, v) => a + v, 0);
  t.ok = sum(t.reasons) === t.likely && t.likely + t.plain === t.direct && t.direct <= t.visits
    && REASONS.every((k) => sum(t.details[k]) === t.reasons[k]) && Object.keys(t.reasons).length === REASONS.length;
  return t;
}

// What a detail says, in words.
const DETAIL = { "(return page)": "a checkout's end page", "(share tag)": "a share tag on the link",
  "(more than one)": "more than one app's preview" };
export const detailWords = (d) => DETAIL[d] || d;

// "Stripe 3, a checkout's end page 1": a reason's details, largest first.
export function detailLine(details) {
  return Object.entries(details || {}).filter(([, v]) => v)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([k, v]) => `${detailWords(k)} ${v.toLocaleString("en-US")}`).join(", ");
}

// The method in one sentence, with the window the days used.
export function method(f, windows) {
  const w = windows && windows.size === 1 ? [...windows][0] : f?.direct_likely?.share_window_minutes ?? 30;
  const base = f?.direct_likely?.method || `Inferred, not counted: a Direct visit is shown as likely from a checkout or payment return, an in-app browser or a shared link (a share marker, or a link preview of the page up to ${w} minutes before), at most one reason a visit. Likely, never certain.`;
  const mixed = windows && windows.size > 1 ? ` The days in this range used different preview windows (${[...windows].sort((a, b) => a - b).join(", ")} minutes).` : "";
  return base + mixed;
}

// One visit's line: "Direct, likely in-app browser (Instagram app)".
export function visitWords(l) {
  if (!l || !WORDS[l.reason]) return "";
  if (l.reason === "shared" && l.minutes != null) {
    const when = l.minutes ? `${l.minutes} min before` : "in the same minute";
    const who = l.detail === "(more than one)" ? "more than one app" : l.detail;
    return `${reasonLabel(l.reason)} (${who} fetched a preview of this page ${when})`;
  }
  return `${reasonLabel(l.reason)} (${detailWords(l.detail)})`;
}

// The completion rate, one rule on every Leads & sales tab (#32, item 4; 2.46.3 on Summary
// first). A rate puts completions over starts, so it is shown only where both come from the
// same place: the page's script tag, the only thing that sees a start. A completion your
// site's server, the lead database or a booking tool reported has no start to match it (#26:
// 84 sign-ups against 25 starts read 100%), so the rate then says "not comparable", with one
// line why. No DOM here: tests/js/sales-rate.mjs runs it in node.
//
//   rateOf({started, done, tools}, min)   {rate, words, why}
//     rate    the share (0..1), or null when none is given
//     words   what the cell says: "38%", "<1%", "not comparable", "no starts seen", "too few to say (4)"
//     why     the one line behind it (title, screen reader), or ""
//   mixedTools(tools)                     true when a completion came from anywhere but the script
//
// tools: the completions' "Reported by" breakdown ({beacon: 3, lead: 2}) or a list of tool keys.

export const NOT_COMPARABLE = "not comparable";
export const WHY_NOT = "Starts are seen only by the page's script; some completions came from your site's server, the lead database or a booking tool, with no start to match. A rate would mix the two.";

export function mixedTools(tools) {
  const keys = Array.isArray(tools) ? tools : Object.entries(tools || {}).filter(([, v]) => v).map(([k]) => k);
  return keys.some((k) => k !== "beacon");
}

// The same words as ui.js pct1 (kept here so node runs this file alone).
const pct = (a, b) => {
  const x = (a / b) * 100;
  return x > 0 && x < 1 ? "<1%" : `${Math.round(x)}%`;
};

export function rateOf({ started = 0, done = 0, tools = [] } = {}, min = 10) {
  if (!started) return { rate: null, words: "no starts seen", why: "The page's script saw no start of this action." };
  if (mixedTools(tools)) return { rate: null, words: NOT_COMPARABLE, why: WHY_NOT };
  if (started < min) return { rate: null, words: `too few to say (${started})`, why: `A rate is given over at least ${min} starts.` };
  const k = Math.min(done, started);
  return { rate: k / started, words: pct(k, started), why: "" };
}

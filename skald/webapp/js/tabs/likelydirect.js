// "Direct, likely <reason>": an inferred split of the Direct visits, never a count
// (direct_likely.py, read by ../direct-likely.js). Shown under the Direct row on Traffic >
// Sources and on a visit in the visitor drawer, always as "likely" with an (i) saying how,
// as the likely-AI figures are (likelyai.js).

import { h, n, pct1 } from "../ui.js";
import { table } from "../table.js";
import { info } from "./tiles.js";
import { REASONS, reasonLabel, rangeBlobs, sumDirect, detailLine, method, visitWords } from "../direct-likely.js";

const MIN_SHARE = 10;   // a share of fewer than this many is not given, only the counts
const off = (f) => f?.direct_likely && f.direct_likely.on === false;

// Traffic > Sources: under the grid, beside the Direct row, never added to it.
export function directPanel(m, r) {
  const f = m.x?.campaigns;
  const { blobs, days } = rangeBlobs(f, r);
  const t = sumDirect(blobs);
  const text = method(f, t.windows);
  const box = h("div", { class: "sheet" }, h("h3", null, "Direct, likely (inferred) ", info(text, "Direct, likely")),
    h("p", { class: "sub" }, "Direct visits whose own request, or the log just before them, points to a likely cause. An estimate: the Direct row keeps every one of these visits."));
  if (off(f)) { box.append(h("p", { class: "empty" }, "Turned off (attribution.direct_likely).")); return box; }
  if (!blobs.length) { box.append(h("p", { class: "empty" }, "Not recorded for this range: it is counted from this release on.")); return box; }
  if (!t.ok) { box.append(h("p", { class: "empty" }, "Withheld: these days' figures do not add up.")); return box; }
  const share = (v) => (t.direct >= MIN_SHARE ? pct1(v, t.direct) : h("span", { class: "few" }, "too few to say"));
  const rows = [...REASONS.map((k) => ({ k, label: reasonLabel(k), v: t.reasons[k], what: detailLine(t.details[k]) })),
    { k: "plain", label: "Direct, no likely cause", v: t.plain, what: "" }];
  box.append(table([{ key: "label", label: "Direct visits" },
    { key: "v", label: "Visits", num: true },
    { key: "share", label: "Of Direct", num: true, sort: (x) => (t.direct ? x.v / t.direct : null), fmt: (_, x) => share(x.v), csv: (x) => (t.direct ? (x.v / t.direct).toFixed(4) : "") },
    { key: "what", label: "What it showed", fmt: (v) => v || "-" }],
  { caption: "Direct, likely (inferred)", rows, file: `direct-likely-${r.first}-to-${r.last}.csv`, ns: "dlk", search: false, tools: false, sortKey: "v", empty: "No Direct visit in this range." }),
  h("p", { class: "note" }, `${n(t.likely)} likely of ${n(t.direct)} Direct visits${t.direct >= MIN_SHARE ? ` (${pct1(t.likely, t.direct)} of them)` : ""}${blobs.length < days ? `, over ${n(blobs.length)} of ${n(days)} recorded days` : ""}. ${text}`));
  return box;
}

// The visitor drawer's line: "Direct, likely in-app browser (Instagram app)".
export function visitDirect(j) {
  const words = visitWords(j?.likely_direct);
  if (!words) return "";
  return h("span", null, `${words} `,
    info("This visit came with no referrer and no campaign tag. Its own request or the log just before it points to a likely cause: a payment provider's return, an app's own browser, a share marker on the link, or an app's link preview of this page. Likely, never certain.", "Direct, likely"));
}

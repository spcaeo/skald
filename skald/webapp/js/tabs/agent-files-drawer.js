// One agent file in a drawer (SKALD-56): Traffic › Agent files, a row of "Every file
// fetched". Its address: afile=<path> (afile=/okf/index.md), so a link, a reload and
// Back land on it, over the tab's period.
//
//   the head     what kind of file it is, the page a Markdown copy stands for, and the
//                file on the site
//   the figures  its requests over the period, how many came from AI, when it was last
//                fetched, its answers by status
//   by day       its requests on each day of the period that kept it
//   who          its requests by group and by name
//
// The same sums as the tab (agent-files-sum.js) from the same file (agent_files.json).

import { h, n, pct1, short } from "../ui.js";
import { rangeOf } from "../data.js";
import { openDrawer } from "../drawer.js";
import { table } from "../table.js";
import { link } from "../drill.js";
import { time as tzTime } from "../tz.js";
import { pageOf } from "../ai-ready.js";
import { KIND_ONE, KIND_SAYS, WHO, WHO_WORDS, sumRange, aiOf } from "./agent-files-sum.js";

const NOT_HERE = "That file was not fetched in this period, or it is not kept (files are kept for the last 30 days).";

function siteUrl(m, path) {
  const host = String(m.site || "").trim();
  // Only a path from the site's root: a logged target such as "@other.example/a.md" or
  // "//other.example/a.md" would make the link go to another host.
  const p = String(path || "");
  return /^[a-z0-9.-]+$/i.test(host) && p.startsWith("/") && !p.startsWith("//")
    ? `https://${host}${p}` : null;
}

const part = (title, body) => (body ? h("div", { class: "af-part" }, h("h3", null, title), body) : null);

function fact(label, value) {
  return h("div", { class: "af-fact" }, h("div", { class: "k-l" }, label), h("div", { class: "af-fv" }, value));
}

export function fileBody(m, x) {
  const url = siteUrl(m, x.path);
  const statusRows = Object.entries(x.status).map(([code, k]) => ({ code, k, __k: code }));
  const whoRows = WHO.filter((w) => x.who[w]).map((w) => ({ who: WHO_WORDS[w], k: x.who[w], __k: w }));
  const nameRows = Object.entries(x.names).map(([name, k]) => ({ name, k, __k: name }));
  const dayRows = x.days.map(([day, k]) => ({ day, k, __k: day }));
  return h("div", { class: "af-dw" },
    h("p", null, h("b", null, KIND_ONE[x.kind] || x.kind), ". ", KIND_SAYS[x.kind] || ""),
    x.kind === "markdown" ? h("p", null, "The copy of ", link("path", pageOf(x.path)), ".") : null,
    url ? h("p", null, h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, "Open the file on the site ↗")) : null,
    h("div", { class: "af-facts" },
      fact("Requests", n(x.requests)),
      fact("From AI", pct1(aiOf(x.who), x.requests)),
      fact("Last fetched", x.last ? tzTime(x.last, { date: true }) : "-")),
    part("Answers", table([{ key: "code", label: "Answer" }, { key: "k", label: "Requests", num: true }],
      { caption: "Answers", rows: statusRows, sortKey: "k", search: false, limit: 20 })),
    part("Who asked", table([{ key: "who", label: "Who" }, { key: "k", label: "Requests", num: true }],
      { caption: "Who asked", rows: whoRows, sortKey: "k", search: false, limit: 10 })),
    part("By name", table([{ key: "name", label: "Name" }, { key: "k", label: "Requests", num: true }],
      { caption: "By name", rows: nameRows, sortKey: "k", search: false, limit: 20,
        note: "Each day keeps the file's 5 busiest names; the rest are \"(all others)\"." })),
    dayRows.length > 1 ? part("By day", table([{ key: "day", label: "Day", fmt: (v) => short(v) }, { key: "k", label: "Requests", num: true }],
      { caption: "By day", rows: dayRows, sortKey: "day", dir: "desc", search: false, limit: 31 })) : null);
}

/* Open it for a row already summed (a click on the tab). */
export function openFileDrawer(m, s, x) {
  return openDrawer({ title: x.path, subtitle: KIND_ONE[x.kind] || "", size: "md", key: "afile", className: "af-drawer",
    body: fileBody(m, x), route: { key: "afile", value: x.path } });
}

/* Open it from the address (overlays.js): the file summed over the tab's period first. */
export async function openFileKey(m, s, v) {
  if (typeof v !== "string" || !v.startsWith("/") || v.length > 200) return NOT_HERE;
  const { loadFile } = await import("./tr-agentfiles.js");
  const f = await loadFile(m, s);
  if (!f || f.missing || f.whole_site_only || f.state === "error") return NOT_HERE;
  const x = sumRange(f, rangeOf(m, s)).files.find((y) => y.path === v);
  return x ? openFileDrawer(m, s, x) : NOT_HERE;
}

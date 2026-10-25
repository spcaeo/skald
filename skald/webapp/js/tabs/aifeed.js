// The latest AI activity today: every assistant fetch and every reader an
// assistant sent, newest first, with the address it came from (the owner's
// decision: this private page only, read from today's raw log, never kept in
// history), whether that visitor has been seen before, and how often.

import { time as tzTime, label as tzLabel } from "../tz.js";
import { h, n, clock, short, ICON } from "../ui.js";
import { csv, download } from "../table.js";
import { withFlag, country } from "./readers.js";
import { link } from "../drill.js";
import { assistantName } from "../labels.js";
import { mark } from "../icons.js";
import { withUrl, copyIf } from "../urlactions.js";

const KIND = { asked: "asked", training: "training", referred: "referred visitor" };
const KIND_LONG = { asked: "Fetched to answer a question someone just asked", training: "Fetched to train or index", referred: "A visitor who came from this assistant" };
// A larger mark per assistant family, from the shared icon set.
function chip(name) {
  const el = mark("assistant", name || "?");
  el?.classList.add("big");
  return el;
}

function row(e) {
  return h("li", null,
    h("span", { class: "f-t" }, tzTime(e.at, { seconds: true, label: false })),
    chip(e.name || "?"),
    h("div", { class: "f-w" },
      h("b", null, e.name ? (e.kind === "referred" ? link("referrer", e.name, { bare: true, text: assistantName(e.name) }) : link("bot", e.name, { bare: true })) : "not recorded"), " ", h("span", { class: "kind", title: KIND_LONG[e.kind] || "" }, KIND[e.kind] || e.kind),
      h("span", { class: "f-p" }, withUrl(h("span", null, e.path), e.path, { cls: "ua-after" })),
      h("div", { class: "f-m" },
        e.country ? link("country", e.country) : h("span", null, "country not recorded"),
        e.status ? h("span", { class: e.status >= 400 ? "status-bad" : null }, `status ${e.status}`) : null,
        e.ip ? h("span", { class: "ip" }, copyIf("ip", link("ip", e.ip, { bare: true }), e.ip, { label: "address" })) : null,
        ...Object.entries(e.utm || {}).map(([k, v]) => copyIf("text", h("span", { class: "utm", title: `utm_${k}` }, `${k}: ${v}`), String(v), { label: `utm_${k}` })))),
    h("div", { class: "f-r" },
      e.repeat == null ? h("span", { class: "rep", title: "Repeat visits are not counted: the visitor key is not set" }, "repeat: -")
        : h("span", { class: `rep${e.repeat ? " yes" : ""}` }, e.repeat ? "Repeat" : "First time"),
      e.times_seen_30d != null ? h("span", null, `seen ${n(e.times_seen_30d)}× in 30 days`) : null,
      e.first_seen ? h("span", null, `first ${short(e.first_seen)}`) : null));
}

/* The feed, with its own filters (assistant, kind, country) and a CSV of
   what they leave. `globalCountry` comes from the filter bar. */
export function aiFeed(m, { limit = 12, globalCountry = "" } = {}) {
  const file = m.x.ai_activity;
  if (!file?.today) {
    return h("p", { class: "empty" }, "The detailed feed (address, country, repeat visits) is coming with the next data update. The Live tab's list shows the latest fetches meanwhile.");
  }
  const events = file.today.events || [];
  const names = [...new Set(events.map((e) => e.name))].sort();
  const countries = [...new Set(events.map((e) => e.country).filter(Boolean))].sort();
  const st = { name: "", kind: "", country: globalCountry, shown: limit };
  const sel = (label, opts, key, fmt = (x) => x) => {
    const el = h("select", { "aria-label": label }, h("option", { value: "" }, `Any ${label.toLowerCase()}`),
      opts.map((o) => h("option", { value: o, selected: st[key] === o }, fmt(o))));
    el.addEventListener("change", () => { st[key] = el.value; st.shown = limit; draw(); });
    return el;
  };
  const list = h("ul", { class: "feed" });
  const more = h("button", { type: "button", class: "btn more-rows" });
  const count = h("span", { class: "tbl-count", "aria-live": "polite" });
  const dl = h("button", { type: "button", class: "btn", html: ICON.download, "aria-label": "Download the AI activity as CSV" }, "CSV");
  let rows = events;
  const draw = () => {
    rows = events.filter((e) => (!st.name || e.name === st.name) && (!st.kind || e.kind === st.kind) && (!st.country || e.country === st.country));
    list.replaceChildren(...rows.slice(0, st.shown).map(row));
    if (!rows.length) list.append(h("li", { class: "empty" }, events.length ? "Nothing matches these filters." : "No assistant activity yet today."));
    count.textContent = `${n(rows.length)} of ${n(events.length)} latest${file.today.total > events.length ? ` (${n(file.today.total)} today in all)` : ""}`;
    more.hidden = rows.length <= st.shown;
    more.textContent = `Show ${n(Math.min(20, rows.length - st.shown))} more`;
  };
  more.addEventListener("click", () => { st.shown += 20; draw(); });
  const cols = [{ key: "at", label: "at" }, { key: "time", label: `time (${tzLabel()})`, csv: (e) => tzTime(e.at, { seconds: true, date: true, label: false }) }, ...["name", "kind", "path", "status", "country", "ip", "repeat", "times_seen_30d", "first_seen"].map((k) => ({ key: k, label: k, ...(k === "country" ? { country: (e) => e.country } : {}) }))];
  cols.push({ key: "utm", label: "utm", csv: (e) => Object.entries(e.utm || {}).map(([a, b]) => `${a}=${b}`).join(" ") });
  dl.addEventListener("click", () => download(`ai-activity-${m.today}.csv`, csv(cols, rows)));
  draw();
  return h("div", null,
    h("div", { class: "feed-tools" }, sel("Assistant", names, "name", assistantName), sel("Kind", Object.keys(KIND), "kind", (k) => KIND[k]),
      sel("Country", countries, "country", (c) => withFlag(c, country(c))), h("span", { class: "grow", style: { flex: "1" } }), count, dl),
    list, more,
    h("p", { class: "note" }, "Addresses are shown on this private page only. They are read from today's log and never stored in history. Repeat means the same visitor (a keyed hash of the address and the assistant's name) was seen on an earlier day in the last 30."));
}

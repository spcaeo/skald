// Requests: the recent request log (the last few hours, newest first) -
// every line the server wrote, with the group it landed in and the rule that
// put it there. The live run rewrites the file every two minutes; the tab
// checks for it every 30 seconds while it is on screen. Pause stops that.
//
// The file is fetched here, not at boot: it is the largest one, and only
// this tab needs it.

import { time as tzTime, label as tzLabel } from "../tz.js";
import { h, n, clock, ICON, reduced } from "../ui.js";
import { base, getJSON, pathMatch, color, GROUPS } from "../data.js";
import { band } from "../charts.js";
import { csv, download } from "../table.js";
import * as S from "../state.js";
import { link } from "../drill.js";
import { withFlag } from "./readers.js";
import { info } from "./tiles.js";
import { mark } from "../icons.js";
import { call } from "./ipmanager.js";
import { isViewer, sessions } from "../access.js";
import { detail, statusTone, GROUP_NAME, copyButton, FLAG_WORDS, norm } from "./reqdetail.js";

const POLL = 30;     // seconds between checks
const PAGE = 100;    // rows drawn at a time
const CRAWLERS = ["bots", "answer_engines", "search_engines", "excluded"];
const TOGGLES = [
  ["mine", "Only mine", (r) => r.group === "ours"],
  ["nobots", "Hide bots and crawlers", (r) => !CRAWLERS.includes(r.group)],
  ["people", "Only real people", (r) => r.group === "people"],
  ["errors", "Only errors", (r) => r.status >= 400],
  ["ai", "Only AI", (r) => !!r.assistant || r.group === "answer_engines"],
];

// Kept between draws: the file, the clock, what is new since the last check.
const st = { file: null, view: null, state: "idle", error: "", fetchedAt: 0, paused: false, query: "", shown: PAGE, fresh: new Set(), ours: null, timer: 0 };
const key = (r) => `${r.at}|${r.ip}|${r.method}|${r.path}|${r.status}`;

async function fetchLog(view, listed = true) {
  // app.json lists the files beside it: one not there yet is not asked for (no failed request).
  if (!listed) { st.file = null; st.view = view; st.state = "missing"; st.fetchedAt = Date.now(); return; }
  st.state = st.file ? "polling" : "loading";
  try {
    const prev = st.view === view && st.file ? new Set(st.file.rows.map(key)) : null;
    const tail = st.file?.api?.tail;
    let file;
    if (tail && prev && st.file.rows.length) {
      const res = await fetch(`${tail}?after=${encodeURIComponent(st.file.rows[0].at)}`, { credentials: "same-origin", cache: "no-store" });
      const body = res.ok ? await res.json() : null;
      file = body?.ok ? { ...st.file, rows: [...(body.rows || []), ...st.file.rows].slice(0, Math.max(st.file.limit || 2000, 2000)), until: body.until || st.file.until, total: body.total ?? st.file.total } : await getJSON(`${base(view)}requests.json`, true);
    } else file = await getJSON(`${base(view)}requests.json`, true);
    if (file) file.rows = (Array.isArray(file.rows) ? file.rows : []).map(norm);
    st.fresh = prev && file ? new Set(file.rows.map(key).filter((k) => !prev.has(k))) : new Set();
    st.file = file;
    st.view = view;
    st.state = file ? "ok" : "missing";
    st.error = "";
  } catch (e) {
    st.state = st.file ? "ok" : "error";
    st.error = e && e.message ? e.message : String(e);
  }
  st.fetchedAt = Date.now();
}

async function loadOurs(m) {
  if (st.ours || !m.x.ours?.api) return;
  st.ours = new Map();
  // With accounts the address list is for admins: a viewer is not asked for it (403).
  if (sessions() && isViewer()) return;
  const r = await call(m.x.ours.api.list);
  if (r.ok) for (const e of r.entries || []) st.ours.set(e.ip, e.label);
}

function matches(s) {
  const on = (s.rq || "").split(",").filter(Boolean);
  const tests = TOGGLES.filter(([k]) => on.includes(k)).map(([, , t]) => t);
  const keep = pathMatch(s);
  const q = st.query.trim().toLowerCase();
  const campaign = (r) => [r.utm?.source, r.utm?.medium, r.utm?.campaign].filter(Boolean).join(" / ");
  return (r) => tests.every((t) => t(r))
    && (!s.ip || r.ip === s.ip)
    && keep(r.path)
    && (!s.country || r.country === s.country)
    && (!s.device || r.device === s.device)
    && (!s.browser || r.agent === s.browser)
    && (!s.source || r.source === s.source)
    && (!s.campaign || campaign(r) === s.campaign || r.utm?.campaign === s.campaign)
    && (!s.referrer || r.ref_host === s.referrer || r.referrer.startsWith(s.referrer))
    && (!q || [r.ip, r.host, r.path, r.query, r.rule, r.agent, r.referrer, r.assistant, r.country, r.country_name, r.os, r.device, r.kind, String(r.status), r.method, ...(r.flags || [])]
      .some((v) => v && String(v).toLowerCase().includes(q)));
}

function row(r, onOpen) {
  const tr = h("tr", { tabindex: "0", class: `rq-row${st.fresh.has(key(r)) ? " fresh" : ""}`, style: { "--g": color(r.group) },
    "aria-label": `${tzTime(r.at, { seconds: true })}, ${r.method || "GET"} ${r.path}, status ${r.status}, ${GROUP_NAME[r.group] || r.group}: ${r.rule || ""}` },
  h("td", { class: "rq-t" }, tzTime(r.at, { seconds: true, label: false })),
  h("td", { class: "rq-s" }, h("span", { class: `st ${statusTone(r.status)}` }, String(r.status))),
  h("td", { class: "rq-p" }, r.method && r.method !== "GET" ? h("b", { class: "meth" }, r.method) : null, h("span", null, r.path), r.query ? h("small", null, `?${r.query}`) : null),
  h("td", { class: "rq-g" }, h("span", { class: "rule" }, r.rule || GROUP_NAME[r.group] || r.group),
    r.verified && r.verified !== "verified" ? h("span", { class: `vb ${r.verified}` }, r.verified === "unverified" ? "not verifiable" : r.verified) : null,
    r.page_view ? h("span", { class: "pv", title: "Counted as a page view" }, "page view") : null,
    (r.flags || []).filter((f) => FLAG_WORDS[f] && f !== "probe").map((f) => h("span", { class: "flag-chip", title: FLAG_WORDS[f][1] }, FLAG_WORDS[f][0]))),
  h("td", { class: "rq-ip" }, r.country ? h("span", { class: "cc", title: r.country_name || r.country }, link("country", r.country, { text: r.country })) : null,
    r.ip && r.ip !== "(removed)" ? h("span", { class: "ip" }, link("ip", r.ip, { bare: true }), copyButton(r.ip)) : h("span", { class: "muted" }, r.ip || "-")),
  h("td", { class: "rq-r", title: r.referrer || null }, r.assistant && r.group === "people" ? h("span", { class: "ai-tag" }, r.assistant) : null,
    r.referrer ? h("span", { class: "ref" }, r.ref_host, r.ref_path && r.ref_path !== "/" ? h("small", null, r.ref_path) : null) : r.assistant ? "" : "-",
    ...Object.entries(r.utm || {}).map(([k, v]) => h("span", { class: "utm", title: `utm_${k}` }, `${k}: ${v}`))),
  h("td", { class: "rq-d" }, h("span", { class: "named" }, mark(r.group === "people" || r.group === "ours" ? "browser" : "bot", r.agent), mark("os", r.os), mark("device", r.device),
    h("span", { class: "nm" }, [r.agent, r.os !== "Other" ? r.os : "", r.device].filter(Boolean).join(", ") || "-"))),
  h("td", { class: "rq-ms n" }, r.ms == null ? "-" : `${n(r.ms)} ms`));
  tr.addEventListener("click", (e) => { if (!e.target.closest("button")) onOpen(r); });
  tr.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target === tr) { e.preventDefault(); onOpen(r); } });
  return tr;
}

export default function requests(m, s, { changed } = {}) {
  const hours = st.file?.window_hours;
  const badge = h("span", { class: "period" }, h("span", { class: "pulse", "aria-hidden": "true" }), hours ? `Last ${hours} hours` : "Recent", h("span", { class: "muted" }, " · the date range above does not apply to this log"));
  const out = [h("div", { class: "head" }, h("h1", null, "Requests"),
    info("Every request the server logged in the last few hours, newest first: who asked for what, what the server answered, and the rule that put each one in its group. Addresses show on this private page only; they are never stored in history.", "Requests"), badge)];
  const root = h("div", { class: "rq" });
  const mix = h("div", { class: "rq-mix" });
  out.push(root);
  loadOurs(m);
  const listed = !Array.isArray(m.files) || m.files.includes("requests");
  const on = (s.rq || "").split(",").filter(Boolean);
  const setToggles = (k) => S.set({ rq: (on.includes(k) ? on.filter((x) => x !== k) : [...on, k]).join(",") }, { replace: true });

  // ------------------------------------------------------------- toolbar
  const search = h("input", { type: "search", class: "rq-search", value: st.query, placeholder: "Search address, path, rule, referrer", "aria-label": "Search the requests", "aria-keyshortcuts": "/" });
  const ring = h("span", { class: "ring", "aria-hidden": "true" });
  const clockEl = h("span", { class: "rq-clock" });
  const pause = h("button", { type: "button", class: "btn", "aria-pressed": String(st.paused) });
  const count = h("span", { class: "tbl-count", "aria-live": "polite" });
  const dl = h("button", { type: "button", class: "btn", html: ICON.download, "aria-label": "Download the requests shown as CSV" }, "CSV");
  const tog = h("div", { class: "rq-togs", role: "group", "aria-label": "Quick filters" }, TOGGLES.map(([k, label]) =>
    h("button", { type: "button", class: "qt", "aria-pressed": String(on.includes(k)), onclick: () => setToggles(k) }, label)));
  const ipChip = s.ip ? h("span", { class: "chip" }, "Address ", h("b", null, s.ip),
    h("button", { type: "button", "aria-label": "Show every address again", onclick: () => S.set({ ip: "" }) }, "×")) : null;
  const tableBody = h("tbody");
  const more = h("button", { type: "button", class: "btn more-rows" });
  const notes = h("div");
  const table = h("div", { class: "scroll rq-scroll" }, h("table", { class: "rq-table" }, h("caption", { class: "vh" }, "Requests today, newest first"),
    h("thead", null, h("tr", null, [[`Time (${tzLabel()})`, "rq-t"], ["Status", "rq-s"], ["Request", "rq-p"], ["Group, and the rule that decided it", "rq-g"], ["From", "rq-ip"],
      ["Referrer and tags", "rq-r"], ["Device", "rq-d"], ["Server time", "rq-ms n"]].map(([c, cls]) => h("th", { scope: "col", class: cls }, c)))), tableBody));
  root.append(
    mix,
    h("div", { class: "rq-bar" },
      h("div", { class: "rq-live" }, ring, h("div", null, clockEl, h("small", null, "Checks for new lines every 30 seconds while this tab is on screen.")), pause),
      h("div", { class: "rq-filters" }, search, tog, ipChip)),
    h("div", { class: "tbl-tools" }, count, h("span", { class: "grow" }), dl),
    table, more, notes);

  let filtered = [];
  const open = (row) => detail(m, row, st.ours || new Map());
  function fill() {
    if (st.state === "loading" || (st.state === "idle")) {
      tableBody.replaceChildren(h("tr", null, h("td", { colspan: 8, class: "muted" }, "Loading today's requests…")));
      count.textContent = ""; more.hidden = true; dl.disabled = true;
      return;
    }
    root.classList.toggle("absent", st.state === "missing");
    if (st.state === "missing" || st.state === "error") {
      tableBody.replaceChildren();
      table.hidden = true; more.hidden = true; dl.disabled = true; count.textContent = "";
      notes.replaceChildren(h("div", { class: "state", html: ICON.info }, h("div", null,
        st.state === "missing" ? "The request log has not been written beside this page yet. It comes with the next data update; until then the Live tab has today's figures."
          : `The request log could not be loaded: ${st.error}. It will be tried again in 30 seconds.`)));
      return;
    }
    table.hidden = false;
    const all = st.file.rows;
    badge.childNodes[1].textContent = st.file.window_hours ? `Last ${st.file.window_hours} hours` : "Recent";
    drawMix(st.file);
    filtered = all.filter(matches(s));
    tableBody.replaceChildren(...filtered.slice(0, st.shown).map((x) => row(x, open)));
    if (!all.length) tableBody.append(h("tr", null, h("td", { colspan: 8, class: "muted" }, `No request reached the server in the last ${st.file.window_hours || "few"} hours.`)));
    else if (!filtered.length) {
      const why = [...TOGGLES.filter(([k]) => on.includes(k)).map(([, l]) => l.toLowerCase()), ...(s.ip ? [`address ${s.ip}`] : []), ...S.activeFilters(s).map(([k, v]) => `${k} ${k === "country" ? withFlag(v) : v}`), ...(st.query ? [`search "${st.query}"`] : [])];
      tableBody.append(h("tr", null, h("td", { colspan: 8, class: "muted" }, `No request among the ${n(all.length)} latest matches ${why.join(", ") || "these filters"}. `,
        h("button", { type: "button", class: "btn", onclick: () => { st.query = ""; S.set({ rq: "", ip: "" }); } }, "Clear the quick filters"))));
    }
    const total = st.file.total;
    count.textContent = `${n(filtered.length)} of the ${n(all.length)} latest${total > all.length ? ` (${n(total)} in the window)` : ""}`;
    more.hidden = filtered.length <= st.shown;
    more.textContent = `Show ${n(Math.min(PAGE, filtered.length - st.shown))} more`;
    dl.disabled = !filtered.length;
    notes.replaceChildren(
      st.file.state === "stale" ? h("div", { class: "state bad", html: ICON.info }, h("div", null, `The live run has not written this log since ${tzTime(st.file.until, { seconds: true })}, so these rows are as they were then. The Data quality tab shows when each job last ran.`)) : "",
      h("p", { class: "note" }, st.file.truncated || total > all.length
        ? `The newest ${n(all.length)} requests are here; the other ${n(total - all.length)} of the window are in the server log. ` : "",
      "Group colours are the Overview's. A Next.js payload (_rsc) is the site fetching a page's data ahead of or after a click; it is not a page read."));
  }

  // The whole window by group (not only the rows kept): the Overview's band, small.
  function drawMix(f) {
    const by = f.by_group || {};
    const parts = [...GROUPS, ["excluded", "Other hosts"]].map(([g, name]) => ({ g, name, value: by[g] || 0, color: color(g) })).filter((x) => x.value);
    const sum = parts.reduce((a, x) => a + x.value, 0);
    if (!sum) { mix.replaceChildren(); return; }
    mix.replaceChildren(h("div", { class: "rq-mix-top" }, h("b", null, n(f.total ?? sum)), ` requests from ${tzTime(f.from, { label: false })} to ${tzTime(f.until)}`),
      band(parts, sum, false),
      h("ul", { class: "legend" }, parts.map((x) => h("li", null, h("span", { class: "sw", style: { background: x.color } }), `${x.name} ${n(x.value)}`))));
  }

  function tick() {
    if (!root.isConnected) { clearInterval(st.timer); st.timer = 0; return; }
    const left = Math.max(0, POLL - Math.round((Date.now() - st.fetchedAt) / 1000));
    const hidden = document.visibilityState !== "visible";
    pause.textContent = st.paused ? "Resume" : "Pause";
    pause.setAttribute("aria-pressed", String(st.paused));
    pause.setAttribute("aria-label", st.paused ? "Resume checking for new requests" : "Pause checking for new requests");
    root.classList.toggle("paused", st.paused);
    ring.style.setProperty("--k", st.paused ? 0 : (POLL - left) / POLL);
    const at = st.file?.until || st.file?.generated_at;
    clockEl.textContent = st.paused ? `Paused${at ? `. Showing the log up to ${tzTime(at, { seconds: true })}` : ""}`
      : st.state === "polling" ? "Checking for new requests…"
        : hidden ? "Waiting: this tab is not on screen" : `${at ? `Log up to ${tzTime(at, { seconds: true })}. ` : ""}Next check in ${left} s`;
    if (!st.paused && !hidden && left === 0 && st.state !== "polling" && st.state !== "loading") {
      fetchLog(s.view, listed).then(() => { if (root.isConnected) { fill(); tick(); } });
    }
  }

  let typing = 0;
  search.addEventListener("input", () => { clearTimeout(typing); typing = setTimeout(() => { st.query = search.value; st.shown = PAGE; fill(); }, 150); });
  pause.addEventListener("click", () => { st.paused = !st.paused; if (!st.paused) st.fetchedAt = 0; tick(); });
  more.addEventListener("click", () => { st.shown += PAGE; fill(); });
  dl.addEventListener("click", () => {
    const cols = [{ key: "at", label: "at" }, { key: "time", label: `time (${tzLabel()})`, csv: (x) => tzTime(x.at, { seconds: true, date: true, label: false }) }, ...["ip", "country", "host", "method", "path", "query", "status", "kind", "group", "rule", "agent", "verified", "page_view", "ref_host", "ref_path", "assistant", "device", "os", "ms", "bytes"].map((k) => ({ key: k, label: k }))];
    cols.push({ key: "utm", label: "utm", csv: (x) => Object.entries(x.utm || {}).map(([a, b]) => `${a}=${b}`).join(" ") });
    cols.push({ key: "flags", label: "flags", csv: (x) => (x.flags || []).join(" ") });
    download(`requests-${m.today}.csv`, csv(cols, filtered));
  });

  // A recount (Refresh now), a new view or the first visit fetches the file; otherwise draw what is held.
  if (!st.file || changed || st.view !== s.view) {
    st.shown = PAGE;
    fetchLog(s.view, listed).then(() => { if (root.isConnected) { fill(); tick(); } });
  }
  fill();
  // One clock, owned by the latest draw: an older draw's clock would stop at its own (detached) root.
  clearInterval(st.timer);
  st.timer = setInterval(tick, 1000);
  requestAnimationFrame(tick);
  if (reduced()) root.classList.add("still");
  return out;
}

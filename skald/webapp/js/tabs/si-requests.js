// Site > Requests (2.7.0): the recent request log as a Data Grid (js/grid.js).
// Every line the server wrote in the last few hours, with the group it landed in
// and the rule that put it there. The live run rewrites the file every two
// minutes; the tab checks for it every 30 seconds while it is on screen, and
// Pause stops that. New lines go into the same grid: its search, filters, sort
// and page stay as they were (they live in the address: req_q, req_fx, ...).
//
// The quick filters (rq), the address (ip) and the global filters narrow the
// rows before the grid sees them, as they did before 2.7.0, so old links keep
// their meaning. One place for this log: Live lists visits, not log lines.
//
// The file is fetched here, not at boot: it is the largest one, and only this
// tab needs it. Same file, same rows, same CSV as the page before (requests.js).

import { time as tzTime, label as tzLabel } from "../tz.js";
import { h, n, ICON, reduced } from "../ui.js";
import { base, getJSON, pathMatch, color, GROUPS } from "../data.js";
import { band } from "../charts.js";
import { csv, download, REGISTRY } from "../table.js";
import * as S from "../state.js";
import { link } from "../drill.js";
import { withFlag } from "./readers.js";
import { info } from "./tiles.js";
import { mark } from "../icons.js";
import { call } from "./ipmanager.js";
import { isViewer, sessions } from "../access.js";
import { detail, statusTone, GROUP_NAME, copyButton, FLAG_WORDS, norm } from "./reqdetail.js";
import { grid } from "../grid.js";

const POLL = 30;     // seconds between checks
const CRAWLERS = ["bots", "answer_engines", "search_engines", "excluded"];
const TOGGLES = [
  ["mine", "Only mine", (r) => r.group === "ours"],
  ["nobots", "Hide bots and crawlers", (r) => !CRAWLERS.includes(r.group)],
  ["people", "Only real people", (r) => r.group === "people"],
  ["errors", "Only errors", (r) => r.status >= 400],
  ["ai", "Only AI", (r) => !!r.assistant || r.group === "answer_engines"],
];
const STATUS_CLASS = [["2xx", "2xx answered"], ["3xx", "3xx redirected"], ["404", "404 or 410 not found"], ["4xx", "Other 4xx"], ["5xx", "5xx server error"]];
const classOf = (st) => ({ s2: "2xx", s3: "3xx", s404: "404", s4: "4xx", s5: "5xx" })[statusTone(st)];

// Kept between draws: the file, the clock, what is new since the last check.
const st = { file: null, view: null, state: "idle", error: "", fetchedAt: 0, paused: false, fresh: new Set(), ours: null, timer: 0 };
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

// The quick filters, the address and the global filters: what the grid is given.
function matches(s) {
  const on = (s.rq || "").split(",").filter(Boolean);
  const tests = TOGGLES.filter(([k]) => on.includes(k)).map(([, , t]) => t);
  const keep = pathMatch(s);
  const campaign = (r) => [r.utm?.source, r.utm?.medium, r.utm?.campaign].filter(Boolean).join(" / ");
  return (r) => tests.every((t) => t(r))
    && (!s.ip || r.ip === s.ip)
    && keep(r.path)
    && (!s.country || r.country === s.country)
    && (!s.device || r.device === s.device)
    && (!s.browser || r.agent === s.browser)
    && (!s.source || r.source === s.source)
    && (!s.campaign || campaign(r) === s.campaign || r.utm?.campaign === s.campaign)
    && (!s.referrer || r.ref_host === s.referrer || r.referrer.startsWith(s.referrer));
}

// ---- the grid's columns: the old table's cells, each with the value it sorts by ----

const columns = () => [
  { key: "at", label: `Time (${tzLabel()})`, csv: (r) => r.at,
    fmt: (_, r) => h("span", { class: `si-rq-t${st.fresh.has(key(r)) ? " fresh" : ""}` }, tzTime(r.at, { seconds: true, label: false })) },
  { key: "status", label: "Status", num: true, fmt: (v) => h("span", { class: `st ${statusTone(v)}` }, String(v)) },
  { key: "path", label: "Request", csv: (r) => `${r.method || ""} ${r.path}${r.query ? `?${r.query}` : ""}`.trim(),
    fmt: (_, r) => h("span", { class: "si-rq-p" }, r.method && r.method !== "GET" ? h("b", { class: "meth" }, r.method) : null, h("span", null, r.path), r.query ? h("small", null, `?${r.query}`) : null,
      // Words the search finds that the cells do not show (the old log's search covered them).
      h("span", { class: "vh", "aria-hidden": "true" }, ` ${[r.host, r.kind, r.country_name, r.assistant, r.method].filter(Boolean).join(" ")}`)) },
  { key: "rule", label: "Group, and the rule that decided it", csv: (r) => r.rule || GROUP_NAME[r.group] || r.group, sort: (r) => `${r.group}|${r.rule || ""}`,
    fmt: (_, r) => h("span", { class: "si-rq-g", style: { "--g": color(r.group) }, title: GROUP_NAME[r.group] || r.group },
      h("span", { class: "rule" }, r.rule || GROUP_NAME[r.group] || r.group),
      r.verified && r.verified !== "verified" ? h("span", { class: `vb ${r.verified}` }, r.verified === "unverified" ? "not verifiable" : r.verified) : null,
      r.page_view ? h("span", { class: "pv", title: "Counted as a page view" }, "page view") : null,
      (r.flags || []).filter((f) => FLAG_WORDS[f] && f !== "probe").map((f) => h("span", { class: "flag-chip", title: FLAG_WORDS[f][1] }, FLAG_WORDS[f][0]))) },
  { key: "ip", label: "From", csv: (r) => r.ip,
    fmt: (_, r) => h("span", { class: "si-rq-ip" }, r.country ? h("span", { class: "cc", title: r.country_name || r.country }, link("country", r.country, { text: r.country })) : null,
      r.ip && r.ip !== "(removed)" ? h("span", { class: "ip" }, link("ip", r.ip, { bare: true }), copyButton(r.ip)) : h("span", { class: "muted" }, r.ip || "-")) },
  { key: "referrer", label: "Referrer and tags", csv: (r) => r.referrer,
    fmt: (_, r) => h("span", { class: "si-rq-r", title: r.referrer || null }, r.assistant && r.group === "people" ? h("span", { class: "ai-tag" }, r.assistant) : null,
      r.referrer ? h("span", { class: "ref" }, r.ref_host, r.ref_path && r.ref_path !== "/" ? h("small", null, r.ref_path) : null) : r.assistant ? "" : "-",
      ...Object.entries(r.utm || {}).map(([k, v]) => h("span", { class: "utm", title: `utm_${k}` }, `${k}: ${v}`))) },
  { key: "agent", label: "Device", csv: (r) => [r.agent, r.os, r.device].filter(Boolean).join(", "),
    fmt: (_, r) => h("span", { class: "si-rq-d" }, h("span", { class: "named" }, mark(r.group === "people" || r.group === "ours" ? "browser" : "bot", r.agent), mark("os", r.os), mark("device", r.device),
      h("span", { class: "nm" }, [r.agent, r.os !== "Other" ? r.os : "", r.device].filter(Boolean).join(", ") || "-"))) },
  { key: "ms", label: "Server time", num: true, fmt: (v) => (v == null ? "-" : `${n(v)} ms`) },
];

// The CSV (and the ZIP export) hold every field of each line, as before 2.7.0.
// Both are built per draw: the time zone's name is known only once the page has set it.
const csvCols = () => [{ key: "at", label: "at" }, { key: "time", label: `time (${tzLabel()})`, csv: (x) => tzTime(x.at, { seconds: true, date: true, label: false }) },
  ...["ip", "country", "host", "method", "path", "query", "status", "kind", "group", "rule", "agent", "verified", "page_view", "ref_host", "ref_path", "assistant", "device", "os", "ms", "bytes"].map((k) => ({ key: k, label: k })),
  { key: "utm", label: "utm", csv: (x) => Object.entries(x.utm || {}).map(([a, b]) => `${a}=${b}`).join(" ") },
  { key: "flags", label: "flags", csv: (x) => (x.flags || []).join(" ") }];

export default function requests(m, s, { changed } = {}) {
  const hours = st.file?.window_hours;
  const badgeWords = h("span", null, hours ? `Last ${hours} hours` : "Recent");
  const badge = h("span", { class: "period" }, h("span", { class: "pulse", "aria-hidden": "true" }), badgeWords, h("span", { class: "muted" }, " · the date range above does not apply to this log"));
  const out = [h("div", { class: "head" }, h("h1", null, "Requests"),
    info("Every request the server logged in the last few hours, newest first: who asked for what, what the server answered, and the rule that put each one in its group. Addresses show on this private page only; they are never stored in history.", "Requests"), badge)];
  const root = h("div", { class: "rq si-rq" });
  const mix = h("div", { class: "rq-mix" });
  out.push(root);
  loadOurs(m);
  const listed = !Array.isArray(m.files) || m.files.includes("requests");
  const on = (s.rq || "").split(",").filter(Boolean);
  const setToggles = (k) => S.set({ rq: (on.includes(k) ? on.filter((x) => x !== k) : [...on, k]).join(",") }, { replace: true });

  // ------------------------------------------------------------- the live bar
  const ring = h("span", { class: "ring", "aria-hidden": "true" });
  const clockEl = h("span", { class: "rq-clock" });
  const pause = h("button", { type: "button", class: "btn", "aria-pressed": String(st.paused) });
  const count = h("span", { class: "tbl-count", "aria-live": "polite" });
  const dl = h("button", { type: "button", class: "btn", html: ICON.download, "aria-label": "Download the requests shown as CSV" }, "CSV");
  const tog = h("div", { class: "rq-togs", role: "group", "aria-label": "Quick filters" }, TOGGLES.map(([k, label]) =>
    h("button", { type: "button", class: "qt", "aria-pressed": String(on.includes(k)), onclick: () => setToggles(k) }, label)));
  const ipChip = s.ip ? h("span", { class: "chip" }, "Address ", h("b", null, s.ip),
    h("button", { type: "button", "aria-label": "Show every address again", onclick: () => S.set({ ip: "" }) }, "×")) : null;
  const holder = h("div", { class: "si-rq-grid" });
  const none = h("div");
  const notes = h("div");
  root.append(
    mix,
    h("div", { class: "rq-bar" },
      h("div", { class: "rq-live" }, ring, h("div", null, clockEl, h("small", null, "Checks for new lines every 30 seconds while this tab is on screen.")), pause),
      h("div", { class: "rq-filters" }, tog, ipChip)),
    h("div", { class: "tbl-tools" }, count, h("span", { class: "grow" }), dl),
    none, holder, notes);

  let g = null;
  let given = [];
  const open = (row) => detail(m, row, st.ours || new Map());
  const why = () => [...TOGGLES.filter(([k]) => on.includes(k)).map(([, l]) => l.toLowerCase()), ...(s.ip ? [`address ${s.ip}`] : []),
    ...S.activeFilters(s).map(([k, v]) => `${k} ${k === "country" ? withFlag(v) : v}`)];

  function fill() {
    if (st.state === "loading" || st.state === "idle") {
      holder.replaceChildren(h("p", { class: "muted si-rq-wait" }, "Loading today's requests…"));
      count.textContent = ""; dl.disabled = true;
      return;
    }
    root.classList.toggle("absent", st.state === "missing");
    if (st.state === "missing" || st.state === "error") {
      holder.replaceChildren(); none.replaceChildren(); dl.disabled = true; count.textContent = "";
      notes.replaceChildren(h("div", { class: "state", html: ICON.info }, h("div", null,
        st.state === "missing" ? "The request log has not been written beside this page yet. It comes with the next data update; until then Overview has today's figures."
          : `The request log could not be loaded: ${st.error}. It will be tried again in 30 seconds.`)));
      return;
    }
    const all = st.file.rows;
    badgeWords.textContent = st.file.window_hours ? `Last ${st.file.window_hours} hours` : "Recent";
    drawMix(st.file);
    given = all.filter(matches(s));
    // Nothing left before the grid's own search: say which quick filter did it.
    none.replaceChildren(all.length && !given.length ? h("p", { class: "muted si-rq-none" }, `No request among the ${n(all.length)} latest matches ${why().join(", ") || "these filters"}. `,
      h("button", { type: "button", class: "btn", onclick: () => S.set({ rq: "", ip: "" }) }, "Clear the quick filters")) : "");
    if (!g) {
      g = grid({
        ns: "req", caption: "Requests, newest first", columns: columns(), rows: given,
        filters: [
          { key: "group", label: "Group", options: [...GROUPS, ["excluded", GROUP_NAME.excluded]] },
          { key: "sclass", label: "Status", value: (r) => classOf(r.status), options: STATUS_CLASS },
          { key: "method", label: "Method", value: (r) => r.method || "(none)" },
        ],
        sortKey: "at", dir: "desc", placeholder: "Search address, path, rule, referrer",
        empty: all.length ? "No request matches the quick filters above." : `No request reached the server in the last ${st.file.window_hours || "few"} hours.`,
        onFiltered: (rows) => {
          const total = st.file?.total;
          count.textContent = `${n(rows.length)} of the ${n(all.length)} latest${total > all.length ? ` (${n(total)} in the window)` : ""}`;
          dl.disabled = !rows.length;
        },
        onRow: open,
      });
      // The export takes every field of each line, not only the columns on screen.
      const reg = REGISTRY.find((x) => x.caption === "Requests, newest first");
      if (reg) Object.assign(reg, { file: `requests-${m.today}.csv`, columns: csvCols() });
      holder.replaceChildren(g);
    } else g.update(given);
    const total = st.file.total;
    notes.replaceChildren(
      st.file.state === "stale" ? h("div", { class: "state bad", html: ICON.info }, h("div", null, `The live run has not written this log since ${tzTime(st.file.until, { seconds: true })}, so these rows are as they were then. The Data quality tab shows when each job last ran.`)) : "",
      h("p", { class: "note" }, st.file.truncated || total > all.length
        ? `The newest ${n(all.length)} requests are here; the other ${n(total - all.length)} of the window are in the server log. ` : "",
      "Group colours are the Overview's. A Next.js payload (_rsc) is the site fetching a page's data ahead of or after a click; it is not a page read. Click a row for every field of that line."));
  }

  // The whole window by group (not only the rows kept): the Overview's band, small.
  function drawMix(f) {
    const by = f.by_group || {};
    const parts = [...GROUPS, ["excluded", "Other hosts"]].map(([gr, name]) => ({ g: gr, name, value: by[gr] || 0, color: color(gr) })).filter((x) => x.value);
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

  pause.addEventListener("click", () => { st.paused = !st.paused; if (!st.paused) st.fetchedAt = 0; tick(); });
  dl.addEventListener("click", () => download(`requests-${m.today}.csv`, csv(csvCols(), g ? g.filtered() : [])));

  // A recount (Refresh now), a new view or the first visit fetches the file; otherwise draw what is held.
  if (!st.file || changed || st.view !== s.view) {
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

// "Watch it connect", the Add a site wizard's step 5 on the AI agent's way
// (site-wizard.js): a checklist that ticks itself while the step is open. The agent
// read the steps, took the keys, sent its report (shown in plain words, with "Use
// these" for page assets that differ from the site's own), the first log lines
// arrived (conn-send.js testPanel), the script tag is seen (sites/tagcheck) and a
// test lead arrived (integrations), the last two only when the report says the agent
// added them. Done is the first log lines, as on the by-hand way.
//
// POST <page>/sites/agentstatus {site, link_id} every POLL_MS for 15 minutes, then
// every 30 seconds. It stops when the step or the dialog closes (the list leaves the
// page), when the line runs out, is cancelled or is not known, on a 401 or 403, and once
// everything is ticked. After the line's expiry nothing on it can change: with the log
// lines in it stops; without, it asks once a minute for 30 minutes, then offers Check again.
// A newer report replaces the one shown. Every URL in the report has its copy and open icons.
// Before the keys are taken the line can be cancelled here; once they are, it says when, that
// the code is used up, and what to do if it was not your agent (with Cancel this line).
//
// 2.39, every set-up dialog (agent-first.js): st.jobs, the line's jobs. The first log lines
// (and the log test) are on the list only when they include logs; without, done is the
// report. The report's page assets and privacy answers are recommendations with Apply
// (agent-recs.js), and its jobs and lead tools a short list (agent-words.js reportLines).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { why } from "./forms.js";
import { time } from "../tz.js";
import { answerBox } from "./conn-ui.js";
import { testPanel, troubleTable, POLL_MS } from "./conn-send.js";
import { tagVerdict } from "./conn-tagcheck.js";
import { withUrl } from "../urlactions.js";
import { agentOf, watchItems, stopWords, reportLines, keysWords, expired, hasLogs, REPORT_NOTE, CANCELLED_WORDS, TOKENS_AT } from "./agent-words.js";
import { lineFor, cancelButton } from "./agent-setup.js";
import { recsBox, siteCall } from "./agent-recs.js";

export { siteCall };

// How often it asks: every POLL_MS (5 s) for 15 minutes, then every 30 s; after the line's
// expiry once a minute, for 30 minutes (the tests make it quicker).
export const WATCH = { every: POLL_MS, slowAfter: 15 * 60000, slow: 30000, late: 60000, lateFor: 30 * 60000 };

const TICK = "✓";

// Words with each web address in them given its copy and open icons.
const URL_IN = /https?:\/\/[^\s<>"']+[^\s<>"'.,;:!?)]/g;
function linked(words) {
  const s = String(words);
  const out = [];
  let at = 0;
  for (const m of s.matchAll(URL_IN)) {
    if (m.index > at) out.push(s.slice(at, m.index));
    out.push(withUrl(h("span", null, m[0]), m[0], { cls: "ua-after" }));
    at = m.index + m[0].length;
  }
  if (at < s.length) out.push(s.slice(at));
  return out;
}

function itemEl(x) {
  return h("li", { class: x.done ? "ok" : x.bad ? "bad" : "wait" },
    h("span", { class: "cn-tick", "aria-hidden": "true" }, x.done ? TICK : x.bad ? "!" : "…"),
    h("span", null, x.words, x.done && x.at ? h("small", null, ` at ${time(x.at, { label: false })}`) : null),
    h("span", { class: "vh" }, x.done ? " (done)" : x.bad ? " (needs a fix)" : " (waiting)"));
}

/* The agent's report in plain words, a line that the agent wrote it, and under it what it
   recommends for Skald's own settings, each with Apply (agent-recs.js). */
function reportBox(report, site) {
  const rows = reportLines(report).map((x) => h("div", { class: `ag-rep-row${x.kind === "warn" ? " warn" : ""}` }, h("dt", null, x.name),
    h("dd", null, x.kind === "url" ? withUrl(h("span", null, x.value), x.value, { cls: "ua-after" })
      : x.kind === "noted" ? [h("span", null, linked(x.value[0])), h("small", { class: "ag-rep-note" }, x.value[1])]
      : Array.isArray(x.value) ? h("ul", null, x.value.map((v) => h("li", null, linked(v)))) : linked(x.value))));
  return [h("section", { class: "ag-report", "aria-label": "What your agent reported" }, h("h4", null, "What your agent did"),
    rows.length ? h("dl", null, rows) : h("p", { class: "note" }, "The report was empty.")),
    h("p", { class: "note ag-rep-who" }, REPORT_NOTE), recsBox(report, site)];
}

/* Step 5. onDone() once the first log lines arrived (a line without logs: once the report
   came). statusOf, tagOf and leadsOf are the calls, replaceable for the tests. */
export function watchPanel(st, { onDone = null, statusOf = (site, link) => call("sites/agentstatus", { site, link_id: link }),
  tagOf = (site) => call("sites/tagcheck", { site }), leadsOf = (site) => siteCall(site, `integrations?site=${encodeURIComponent(site)}`) } = {}) {
  const site = st.site;
  const done = h("div");
  const seen = {};
  let status = null;
  const list = h("ol", { class: "ag-watch", "aria-label": "What has happened so far", "aria-live": "polite" });
  const report = h("div");
  const tagOut = h("div");
  const keysOut = h("div");
  const waitOut = h("div");
  const lateOut = h("div");
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const jobs = st.jobs || null;
  const logs = hasLogs(jobs);
  const draw = () => list.replaceChildren(...watchItems(status, seen, jobs).map(itemEl));
  const test = !logs ? null : testPanel(st.send, { auto: true, onResult: (v) => {
    if (v.kind !== "ok" || seen.lines) return;
    seen.lines = true;
    draw();
    done.replaceChildren(answerBox("ok", `Done: ${site} is receiving visits.`,
      h("div", { class: "acts" }, h("a", { class: "btn primary", href: `/traffic/${site}/` }, "Open its dashboard"))));
    if (onDone) onDone();
  } });
  const a = agentOf(st.agent);
  // A chat-only agent ran no line: the log test alone, as on the by-hand way.
  if (a && !a.shell) return [test, done, troubleTable()];
  const link = st.link || lineFor(site, jobs)?.link_id || "";
  if (!link) {
    return [h("p", { class: "note" }, `This page has no line to watch: Skald shows the agent's steps only for a line made here. Go Back to make one.${logs ? " The log test below works either way." : ""}`),
      test, done, logs ? troubleTable() : null];
  }
  const lookTag = async () => {
    tagOut.replaceChildren(h("p", { class: "empty" }, "Looking at your home page..."));
    const v = tagVerdict(await Promise.resolve(tagOf(site)).catch(() => null));
    seen.tag = v.kind === "ok" ? true : v.kind === "bad" ? false : null;      // null: it could not tell
    draw();
    const again = h("button", { type: "button", class: "btn" }, "Look again");
    again.addEventListener("click", lookTag);
    tagOut.replaceChildren(answerBox(v.kind, v.head, v.fix ? h("p", null, v.fix) : null, v.kind !== "ok" ? h("div", { class: "acts" }, again) : null));
  };
  const lookLead = async () => {
    const tools = new Set((status?.report?.leads || []).map((l) => l && l.tool).filter(Boolean));
    const r = await Promise.resolve(leadsOf(site)).catch(() => null);
    // integrations' state (conversions/roads.py hook_states): ready (a test passed) or received.
    const got = (r?.ok ? r.tools || [] : []).some((t) => (!tools.size || tools.has(t.tool)) && (t.state === "ready" || (t.state === "received" && !t.attention)));
    if (got) { seen.lead = true; draw(); }
  };
  // The keys taken: when, the code used up, and a way out if it was not your agent.
  const drawKeys = (r) => {
    const [head, notMe] = keysWords(time(r.keys_at, { label: false }));
    const out = h("div");
    const stop = r.state === "cancelled" ? null : cancelButton(site, link, out, () => {
      keysOut.replaceChildren(answerBox("ok", CANCELLED_WORDS, h("p", null, `Remove its key in ${TOKENS_AT}, then go Back to make a new line.`)));
    });
    keysOut.replaceChildren(answerBox("ok", head, h("p", null, notMe), stop ? h("div", { class: "acts" }, stop) : null, out));
  };
  // Before the keys are taken (waiting, opened): the line can still be cancelled from here.
  let cancelled = false;
  const drawWait = (r) => {
    if (cancelled) return;
    if (!["waiting", "opened"].includes(r.state)) { waitOut.replaceChildren(); return; }
    if (waitOut.firstChild) return;
    const out = h("div");
    waitOut.replaceChildren(h("p", { class: "note" }, "Sent it to the wrong place, or changed your mind? ",
      cancelButton(site, link, out, () => { cancelled = true; waitOut.replaceChildren(answerBox("ok", CANCELLED_WORDS, h("p", null, "Go Back to make a new line."))); })), out);
  };
  const started = Date.now();
  let lateSince = 0;          // when the watch first saw the line past its expiry
  const finished = () => status?.reported_at && (seen.lines || !logs) && (seen.tag !== undefined || !status.report?.script_tag)
    && (seen.lead || !status.report?.leads?.length);
  async function once() {
    if (list.isConnected === false) return;        // the step or the dialog closed: stop
    const before = status;
    const r = await statusOf(site, link);
    if (list.isConnected === false) return;
    if (r && (r.status === 401 || r.status === 403)) {         // signed out, or no right: asking again will not help
      said.className = "msg err";
      said.textContent = `${why(r, "Skald refused to show the agent's progress.")} Sign in again, then reload this page.`;
      return;
    }
    if (r && r.status === 402) {                               // the organisation is read only: asking again will not help
      said.className = "msg err";
      said.textContent = why(r, "This organisation is read only, so the agent's progress cannot be shown.");
      return;
    }
    if (!r || !r.ok) {
      said.className = "msg err";
      said.textContent = `${why(r || {}, "The agent's progress could not be read.")} Trying again.`;
    } else {
      said.textContent = "";
      status = r;
      // The agent moved on: the 2-minute log test looks again from now.
      if (test && ((r.keys_at && !before?.keys_at) || (r.reported_at && r.reported_at !== before?.reported_at))) test.start();
      if (r.keys_at && !before?.keys_at) drawKeys(r);
      drawWait(r);
      if (r.reported_at && r.reported_at !== before?.reported_at) {        // the first report, or a newer one
        // agentstatus answers the report's jobs and tools at its top level too (2.39).
        report.replaceChildren(...reportBox({ ...(r.report || {}), ...(r.jobs ? { jobs: r.jobs } : {}), ...(r.tools ? { tools: r.tools } : {}) }, site));
        if (r.report?.script_tag) lookTag();
        // A line without logs: the report is the end of it.
        if (!logs && !before?.reported_at) {
          done.replaceChildren(answerBox("ok", "Done: your agent sent its report.", h("p", null, "Read it below. Skald changes none of its own settings by itself: press Apply on what you want.")));
          if (onDone) onDone();
        }
      }
      if (r.report?.leads?.length && !seen.lead) await lookLead();
      draw();
      const stop = stopWords(r);
      if (stop) { said.className = "msg err"; said.textContent = stop; return; }
      if (r.state === "expired" || finished()) return;
      // Past the expiry the agent can send nothing more: with the log lines in, it is done.
      if (expired(r.expires_at)) {
        if (seen.lines || (!logs && status.reported_at)) return;
        lateSince = lateSince || Date.now();
        if (Date.now() - lateSince >= WATCH.lateFor) { lateOut.replaceChildren(stillWaiting()); return; }
        setTimeout(once, WATCH.late);
        return;
      }
    }
    setTimeout(once, Date.now() - started < WATCH.slowAfter ? WATCH.every : WATCH.slow);
  }
  // After 30 minutes past the expiry: asked again only on request.
  function stillWaiting() {
    const again = h("button", { type: "button", class: "btn" }, "Check again");
    again.addEventListener("click", () => { lateSince = Date.now(); lateOut.replaceChildren(); if (test) test.start(); once(); });
    return h("p", { class: "note" }, "Still waiting? Press Check again. ", again);
  }
  draw();
  setTimeout(once, 0);       // once the step is on the page
  return [h("p", null, "Skald ticks each step as your agent does it. This page checks every few seconds while it is open."),
    list, said, lateOut, waitOut, keysOut, logs ? null : done, report, tagOut, test, logs ? done : null, logs ? troubleTable() : null];
}

// Recorded journeys (2.43; docs/JOURNEYS.md): the sessions a website sends itself, after the
// visitor agreed to analytics, through its own signed relay. Labelled "Recorded by your site"
// everywhere and never added to the log's figures: they are counted on their own, and
// withheld when their recount from the raw events does not match (journeys_api.py).
//
//   recordedCard(m, s, r)   Traffic › Visitors: the period's sessions and their own figures.
//                           Not drawn for a site that never connected and sent nothing
//   openSession(ref, m)     a session's drawer (rj=<s + 12 hex>): its pages, its actions, and
//                           for owners and admins the log's own visit linked to it
//   visitRecorded(d, j)     the visitor drawer, owners and admins: the sessions linked to that
//                           log visit, and how (the script tag's visitor ID, or the address)
//   journeysRow(m, status)  Settings › Leads & tools: one row, from the doctor's line
//   openConnect(site)       Connect (rjc=connect): Who will do it? Me / My developer / My AI
//                           agent (the agent job connect-journeys)
//
// The address holds the session's opaque ref only: never an address, an email or an ID the
// site made.

import { h, n, duration } from "../ui.js";
import { stamp, ago } from "../tz.js";
import { openDrawer } from "../drawer.js";
import { withCopy, withUrl } from "../urlactions.js";
import { pill } from "../ui/pill.js";
import { help } from "../ui/help.js";
import { fold, urlFold } from "../ui/fold.js";
import { DEMO } from "../demo.js";
import { ME, sessions } from "../access.js";
import { call } from "./ipmanager.js";
import { statusRow, quietButton } from "./set-ui.js";
import { connectCard, mayConnect, sourceLink } from "../ui/connect.js";
import { arrivedBox } from "../ui/live.js";

export const LABEL = "Recorded by your site";
const GUIDE = "recorded-journeys";
const REF = /^s[0-9a-f]{12}$/;
const FIRST = 10;                       // rows shown before "Show the other N"
export const ACTIONS = { cta_click: "Clicked", form_sent: "Sent a form", signup: "Signed up", booking_opened: "Opened a booking",
  booking_made: "Booked", download: "Downloaded" };
const ABOUT = "Sessions your website sent itself, only after the visitor agreed to analytics. Counted on their own: never added to the visits Skald reads from the server's log.";
const admin = () => ["owner", "admin"].includes(ME.role) || !!ME.install_admin;
let PAGE = null;                         // the page's model, for a drawer opened from another drawer
const tag = () => pill("info", "From your site", { title: LABEL });
// The demo: its own sample sessions (tools/demo_recorded.py), read from files, as a viewer sees them.
const demoRec = () => DEMO.on && Object.keys(DEMO.api.recorded || {}).length > 0;
const reads = () => (DEMO.on ? demoRec() : sessions());

/* "Google / cpc / spring" or the referring site, else unknown (never "direct": the site did not say). */
export function cameFrom(t) {
  const utm = [t?.source, t?.medium, t?.campaign].filter(Boolean);
  if (utm.length) return utm.join(" / ");
  return t?.referrer || "Not known";
}
const endWords = (x) => (x.ended ? ACTIONS[x.ended] || x.ended : x.pages > 1 ? `Read ${n(x.pages)} pages` : "Read one page");

/* One session as a row that opens its drawer. */
export function sessionRow(x, m, { why = "" } = {}) {
  const b = h("button", { type: "button", class: "rj-row", "data-ref": x.ref, "aria-label": `${LABEL}: session of ${stamp(x.start)}. Open it` },
    h("span", { class: "rj-when" }, stamp(x.start)),
    h("span", { class: "rj-main" }, h("b", null, x.landing || "/"), h("small", null, `${n(x.pages)} page${x.pages === 1 ? "" : "s"} · ${duration(x.seconds)} · ${cameFrom(x.touch)}${why ? ` · ${why}` : ""}`)),
    x.ended ? pill("good", endWords(x)) : h("span", { class: "rj-end muted" }, endWords(x)));
  b.addEventListener("click", () => openSession(x.ref, m));
  return b;
}

function figures(f) {
  const kpi = (label, v, note) => h("div", { class: "kpi" }, h("span", { class: "k-l" }, label), h("span", { class: "k-n" }, note), h("span", { class: "k-v" }, n(v)));
  return h("div", { class: "kpis tight rj-kpis" },
    kpi("Sessions", f.sessions, "Started in the period"),
    kpi("Visitors", f.visitors, "Browsers, by the site's own ID"),
    kpi("Pages read", f.page_views, "Page views the site sent"),
    kpi("Actions", f.actions, "Clicks, forms, sign-ups, bookings"));
}

// ------------------------------------------------------------ Traffic › Visitors

/* The card, filled when its answer comes; removed for a site that never connected. */
export function recordedCard(m, s, r) {
  if (!reads() || !r?.first || !r?.last) return null;
  PAGE = m;
  const body = h("div", { class: "rj-body" }, h("p", { class: "empty" }, "Loading what your site sent..."));
  const box = h("section", { class: "s vs-card rj-card", "aria-labelledby": "rj-h" },
    h("div", { class: "vs-card-h rj-h" }, h("h3", { id: "rj-h" }, LABEL), tag(), help(LABEL, { text: ABOUT, guide: GUIDE }), DEMO.on ? null : sourceLink("journeys")), body);
  call(`recorded?first=${encodeURIComponent(r.first)}&last=${encodeURIComponent(r.last)}`).then((got) => {
    if (!got.ok) {
      if (got.missing || got.demo) box.remove();      // the demo: a period it has no answer for
      else body.replaceChildren(h("p", { class: "note" }, got.error || "What your site sent could not be read."));
      return;
    }
    const list = got.sessions || [];
    // Never connected: nothing for a viewer; for whoever may connect it, one quiet line with
    // Connect (2.43, js/ui/connect.js), the Visitors page itself is not empty.
    if (!got.connected && !list.length) {
      if (!mayConnect()) { box.remove(); return; }
      box.replaceWith(connectCard(m, "journeys", { s, mode: "line", title: "Recorded journeys: not connected", line: "Your site can send the sessions people agreed to." }));
      return;
    }
    const parts = [];
    if (got.state === "withheld") parts.push(h("div", { class: "state bad", role: "status" }, h("div", null, h("b", null, "Figures withheld. "), got.why || "They did not match their recount.")));
    else parts.push(figures(got.figures || {}));
    if (!list.length) parts.push(h("p", { class: "empty" }, "Your site sent no session in this period."));
    else {
      parts.push(h("div", { class: "rj-list" }, list.slice(0, FIRST).map((x) => sessionRow(x, m))));
      if (list.length > FIRST) parts.push(urlFold("rjall", `Show the other ${n(list.length - FIRST)}`, () => [h("div", { class: "rj-list" }, list.slice(FIRST).map((x) => sessionRow(x, m)))]));
    }
    body.replaceChildren(...parts);
  });
  return box;
}

// ------------------------------------------------------------ one session

const fact = (label, value) => (value == null || value === "" ? null : h("div", { class: "rj-fact" }, h("dt", null, label), h("dd", null, value)));

function sessionBody(got, m, d) {
  const x = got.session;
  const kept = got.private;
  const facts = h("dl", { class: "rj-facts" }, ...[
    fact("Started", stamp(x.start)),
    fact("Length", duration(x.seconds)),
    fact("Landed on", withUrl(h("code", null, x.landing || "/"), x.landing || "/", { label: "the landing page" })),
    fact("Came from", cameFrom(x.touch)),
    fact("This visitor", x.visitor_sessions > 1 ? `${n(x.visitor_sessions)} sessions kept${x.returning ? ", came back" : ""}` : "First session kept"),
    fact("Script tag", x.script_id ? "Sent with the script tag's visitor ID" : "No script tag visitor ID"),
    kept ? fact("Address", x.ip ? withCopy(h("code", null, x.ip), x.ip, { label: "the address" }) : "Not kept") : null,
    kept && x.email ? fact("Email", withCopy(h("span", null, x.email), x.email, { label: "the email" })) : null,
  ].filter(Boolean));
  const pages = x.trail?.length ? h("ol", { class: "rj-trail" }, x.trail.map(([p, sec]) => h("li", null, withUrl(h("code", null, p), p, { label: "the page" }), h("small", null, sec ? `+${duration(sec)}` : "start")))) : h("p", { class: "empty" }, "No page view was sent.");
  const acts = x.actions?.length ? h("ul", { class: "rj-acts" }, x.actions.map((a) => h("li", null, pill(a.event === x.ended ? "good" : "info", ACTIONS[a.event] || a.event),
    a.label ? withCopy(h("span", null, ` ${a.label}`), a.label, { label: "the label" }) : null, h("small", null, ` on ${a.path}${a.at ? `, +${duration(a.at)}` : ""}`)))) : h("p", { class: "empty" }, "No action was sent.");
  let log;
  if (!kept) log = h("p", { class: "note" }, "Admins and owners see the server log's own visit here.");
  else if (!(got.visits || []).length) log = h("p", { class: "note" }, "No visit from the server's log is linked. Skald links one only by the same kept address inside the session's time, never by a guess.");
  else {
    log = h("div", { class: "rj-list" }, got.visits.map((v) => {
      const b = h("button", { type: "button", class: "rj-row", "aria-label": `The log's visit of ${stamp(v.start)}. Open it` },
        h("span", { class: "rj-when" }, stamp(v.start)), h("span", { class: "rj-main" }, h("b", null, v.landing || "/"), h("small", null, `${n(v.pages)} page${v.pages === 1 ? "" : "s"} in the log · ${v.source || "source not known"} · same address`)));
      b.addEventListener("click", async () => {
        const key = `${v.day}.${v.seq}`;
        d.close();
        const got2 = await (await import("./visitor.js")).openVisitKey(m, key);
        if (typeof got2 === "string") (await import("../overlays.js")).say?.(got2);
      });
      return b;
    }));
  }
  return [h("p", { class: "rj-lede" }, tag(), " ", ABOUT),
    facts,
    h("section", { class: "dw-sec" }, h("h3", null, `Pages read (${n(x.pages)})`), pages),
    h("section", { class: "dw-sec" }, h("h3", null, `Actions (${n(x.actions?.length || 0)})`), acts),
    h("section", { class: "dw-sec" }, h("h3", null, "The server log's own visit"), log)];
}

export async function openSession(ref, m) {
  if (!REF.test(String(ref))) return "That session is not one Skald keeps.";
  if (DEMO.on && !demoRec()) return "In the demo, recorded journeys need a running Skald.";
  m = m || PAGE;
  PAGE = m;
  if (!reads()) return "Not available on this install.";
  const d = openDrawer({ title: "Recorded session", subtitle: LABEL, key: "recorded", scope: "page", className: "rj-dw", size: "md",
    body: h("p", { class: "empty" }, "Loading the session..."), route: { key: "rj", value: ref } });
  const got = await call(`recorded/session?ref=${encodeURIComponent(ref)}`);
  if (!d.el.isConnected) return d;
  if (!got.ok) { d.body.replaceChildren(h("p", { class: "note" }, got.error || "That session could not be read.")); return d; }
  d.body.replaceChildren(...sessionBody(got, m, d));
  return d;
}
export const openSessionKey = (v, m) => openSession(v, m);

// ------------------------------------------------------------ the visitor drawer

const LINKED = { visitor_id: "linked by the script tag's visitor ID", address: "linked by the same address inside this visit's time" };

/* Owners and admins: the sessions the site sent for this log visit, kept on the drawer (d.recorded)
   so a redraw of the drawer keeps it. */
export async function visitRecorded(d, j, m) {
  if (DEMO.on || !sessions() || !admin() || !j?.day || j.seq == null) return null;
  const got = await call(`recorded/visit?day=${encodeURIComponent(j.day)}&seq=${encodeURIComponent(j.seq)}`);
  if (!d.el.isConnected || !got.ok) return null;
  const list = got.sessions || [];
  if (!got.connected && !list.length) return null;
  const sec = fold(`${LABEL} (${n(list.length)})`, () => [
    h("p", { class: "note" }, tag(), " Sent by the site after consent; shown beside this visit, never counted in it."),
    list.length ? h("div", { class: "rj-list" }, list.map((x) => sessionRow(x, m, { why: LINKED[x.linked_by] || "" })))
      : h("p", { class: "empty" }, "No session your site sent is linked to this visit. Skald links one only by the script tag's visitor ID or the same address inside the visit's time.")],
  { open: list.length > 0, cls: "vz-more rj-fold" });
  d.recorded = sec;
  d.body.append(sec);
  return sec;
}

// ------------------------------------------------------------ Settings › Leads & tools

const WHEN = /the last event came (.+)$/;
/* One row from the doctor's line (doctor.integration_checks "journeys"): none until connected. */
export function journeysRow(m, status) {
  PAGE = m;
  const rec = (status || []).find((x) => x.id === "journeys");
  const open = () => openConnect(m.site);
  const base = { iconName: "people", title: "Recorded journeys" };
  if (!rec) return statusRow({ ...base, line: "Your site sends the sessions people agreed to", kind: "off", word: "Not set up", action: quietButton("Connect", open) });
  if (rec.state === "OK") return statusRow({ ...base, line: `Last event ${WHEN.exec(rec.says || "")?.[1] || "lately"}`, kind: "good", word: "Working", onOpen: open });
  if (rec.state === "OFF") return statusRow({ ...base, line: "Connected. Waiting for the first session", kind: "warn", word: "Waiting", onOpen: open });
  return statusRow({ ...base, line: rec.says ? rec.says.replace(/^./, (c) => c.toUpperCase()) : "Not working", kind: "bad", word: "Stopped", onOpen: open });
}

// ------------------------------------------------------------ Connect

const code = (text, label) => withCopy(h("code", null, text), text, { label, tag: "div", cls: "rj-code" });

function statusTop(st) {
  if (!st?.ok) return h("p", { class: "note" }, st?.error || "The status could not be read.");
  const word = !st.connected ? pill("off", "Not set up") : st.last_received ? pill("good", "Working") : pill("warn", "Waiting");
  const last = st.last_received ? `Last event ${ago(st.last_received)}. ${n(st.events_30d)} event${st.events_30d === 1 ? "" : "s"} in 30 days.` : st.connected ? "No event has come yet." : "Your site sends nothing yet.";
  return h("div", { class: "rj-top" }, word, h("span", null, ` ${last}`), st.where === "env" ? h("small", { class: "muted" }, " The secret is set in the server's environment.") : null);
}

function meSteps(site, st, onMade = () => {}) {
  const out = h("div", { class: "rj-made" });
  const make = h("button", { type: "button", class: "btn" }, st.connected ? "Make a new secret" : "Make the secret");
  make.addEventListener("click", async () => {
    make.disabled = true;
    const got = await call("recorded/connect", {});
    make.disabled = false;
    if (!got.ok) { out.replaceChildren(h("p", { class: "msg err" }, got.error || "The secret could not be made.")); return; }
    make.remove();
    onMade();
    out.replaceChildren(h("p", { class: "state ok" }, h("div", null, h("b", null, "Shown once. "), "Put both in your site's server settings now (never in the page's code).")),
      h("p", { class: "rj-k" }, "SKALD_JOURNEY_SECRET"), code(got.secret, "the secret"),
      h("p", { class: "rj-k" }, "SKALD_JOURNEY_URL"), code(got.url, "the address"));
  });
  const warn = st.connected && st.where !== "env" ? h("p", { class: "note" }, "A new secret stops the old one at once: your site's relay sends nothing until it has the new one.") : null;
  return [
    h("ol", { class: "rj-steps" },
      h("li", null, h("b", null, "The secret. "), "Your site's server signs what it sends with it.", st.where === "env" ? h("p", { class: "note" }, "It is set in Skald's server environment: ask whoever runs Skald.") : h("div", null, warn, make, out)),
      h("li", null, h("b", null, "The page helper. "), "One line in your pages' shared <head>. It sends nothing until the visitor agrees.",
        code(`<script src="${st.helper}" data-relay="/api/skald-journey" defer></script>`, "the script line")),
      h("li", null, h("b", null, "The relay. "), "Two small routes on your site sign each event and pass it to Skald. The guide has them for Next.js, ready to copy.", help("The relay", { guide: GUIDE })),
      h("li", null, h("b", null, "Your consent banner. "), "On a yes, and on a no:", code("window.skaldJourneys?.consent(true)", "the yes line"), code("window.skaldJourneys?.consent(false)", "the no line"))),
    h("p", { class: "note" }, "Then accept analytics on your site and open two pages: the session shows in Traffic › Visitors within a minute.")];
}

function devMessage(site, st) {
  return [`Please connect Skald's recorded journeys on ${site}. It sends only the sessions visitors agree to in our consent banner.`,
    `1. Add this line to the shared <head>: <script src="${st.helper}" data-relay="/api/skald-journey" defer></script>`,
    `2. Add two server routes, /api/skald-journey and /api/skald-journey/withdraw, that sign each event (HMAC-SHA256) and pass it to ${st.url}. Skald's guide has them for Next.js: ${st.helper.replace(/\/traffic-js\/journeys\.js$/, "")}/traffic/${site}/#help?part=${GUIDE}`,
    "3. Set SKALD_JOURNEY_URL to that address and SKALD_JOURNEY_SECRET to the secret I send you separately, in the server's settings only.",
    "4. Call window.skaldJourneys.consent(true) on a yes in the banner, consent(false) on a no, and withdraw() where people take consent back."].join("\n");
}

export async function openConnect(site, { onClose = null } = {}) {
  if (DEMO.on) return "In the demo, connecting needs a running Skald.";
  if (!sessions() || !admin()) return "Not available to your role.";
  const { whoDialog, agentPath, devPath, mePath } = await import("../ui/who.js");
  const route = { key: "rjc", value: "connect" };
  const st = await call("recorded/status");
  const ready = st.ok ? st : { connected: false, helper: "", url: "" };
  // 2.44: connected and waiting for the first session: said by itself, with Test (sites/arrived journeys).
  const live = () => arrivedBox(site, "journeys", { intro: "Waiting: no recorded session has arrived yet." });
  const top = h("div", null, statusTop(st), ...(st.ok && st.connected && !st.last_received ? [live()] : []));
  // A secret just made: the site is connected and waits for its first event.
  const made = () => { ready.connected = true; ready.where = "file"; top.replaceChildren(statusTop(ready), live()); };
  const paths = st.ok ? {
    me: mePath(() => meSteps(site, ready, made)),
    dev: async () => devPath({ site, message: devMessage(site, ready) })(),
    agent: agentPath({ site, jobs: ["connect-journeys"], route }),
  } : {};
  return whoDialog({ title: "Recorded journeys", subtitle: `${LABEL}, for ${site}`, route, paths, drawerKey: "rj-connect",
    top: h("div", null, top, h("p", { class: "note" }, ABOUT, " ", help("Recorded journeys", { guide: GUIDE }))), onClose });
}
export const openConnectKey = (v, m) => (v === "connect" ? openConnect(m.site) : "That dialog is not in this version of the page.");

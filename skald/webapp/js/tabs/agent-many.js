// "Lines for your sites" (2.40): set up many sites with your AI agents, one site at a time
// or all at once, each in its own session (docs/plans/2026-10-26-agent-everywhere.md, "Many
// sites, one line each"). The words and the address: agent-many-words.js.
//
//   every site of the organisation (GET sites/agentleft, kit_left.py): what is left on it,
//   the jobs an agent can do, and its newest line; per site "Make its line" (POST
//   sites/agentlink {site, jobs}: a line of its own, its own code), Copy, and its watch;
//   "Make a line for each site" makes one separate line per site, one after another;
//   "Two lines (MCP)" for a site: an MCP token with the mcp and setup scopes for that one
//   site (POST tokens/create, team_api.py), the first line for Claude Code or Codex with it,
//   and the second line, "Set up Skald for this site";
//   "Add several sites": names typed at once, each added with POST sites/add (the same
//   checks, plan limits and "verify your domain first" as Add a site), then each one's own
//   line.
//
// The lines and the token are kept in this page's memory only (agent-setup.js LINES, and
// TOKENS below), never in the address: lines=<value> names the view only. One button opens
// it (sitesadmin.js, Settings › Organisation › Sites, #settings/org/sites), and the address does
// (overlays.js, openLinesKey).

import { h } from "../ui.js";
import { openDrawer } from "../drawer.js";
import { renamed } from "../overlays.js";
import { call } from "./ipmanager.js";
import { why } from "./forms.js";
import { ME, sessions } from "../access.js";
import { DEMO } from "../demo.js";
import { stamp } from "../tz.js";
import { withCopy } from "../urlactions.js";
import { answerBox, codeBlock, helpLink } from "./conn-ui.js";
import { sendState } from "./conn-send.js";
import { makeLine, lineFor, forgetLine, cancelButton, lineBox, safetyBox } from "./agent-setup.js";
import { watchPanel } from "./agent-watch.js";
import { jobsWords, timeLeft, expired } from "./agent-words.js";
import * as W from "./agent-many-words.js";

const TOKENS = new Map();          // site -> the MCP + set-up token made in this page (shown once)
const POLL_MS = 10000;
const admin = () => ["owner", "admin"].includes(ME.role) || ME.install_admin;

/* lines=<value> from a link: the view, or the plain line why not. */
export async function openLinesKey(value) {
  if (DEMO.on) return "Setting up needs a running Skald: not available in the demo.";
  if (!sessions() || !admin()) return "Not available to your role.";
  const want = W.parseLines(value);
  if (!want) return "That view is not one this page offers.";
  return openLines(want);
}

/* The view. want: {view, site} (agent-many-words.js parseLines). */
export function openLines(want = { view: "all", site: "" }) {
  const route = { key: W.KEY, value: W.linesValue(want) };
  const st = { ...want, rows: null, data: null, timer: 0 };
  const list = h("div", { class: "am-list" }, h("p", { class: "empty" }, "Loading your sites..."));
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const addSlot = h("div");
  const many = h("button", { type: "button", class: "btn primary" }, "Make a line for each site");
  const addBtn = h("button", { type: "button", class: "btn", "aria-expanded": "false" }, "Add several sites");
  const body = h("div", { class: "am" },
    h("p", null, "Each site gets its own line with its own one-time code. Paste each line into the AI agent that works on that site, in that site's own folder or on its server. Lines for different sites never end each other, so they can all run at once."),
    h("div", { class: "acts" }, many, addBtn), said, addSlot, list,
    h("p", { class: "note" }, "Prefer to talk to your assistant? Each site's \"Two lines\" connects one Claude Code or Codex session to Skald for that site, then you say \"", W.LINE_TWO, "\". ",
      helpLink("mcp", "How the MCP connection works")));
  const d = openDrawer({ title: "Lines for your sites", subtitle: ME.org ? `Set up ${ME.org}'s sites with your AI agents.` : "Set up your sites with your AI agents.",
    size: "lg", key: "agent-many", scope: "page", body, route });

  const go = (next) => {
    Object.assign(st, next);
    const v = W.linesValue(st);
    if (v !== route.value) { renamed(route.key, route.value, v); route.value = v; }
    draw();
  };
  const load = async () => {
    const r = await call("sites/agentleft");
    if (!r.ok) { list.replaceChildren(answerBox("bad", why(r, "Your sites could not be loaded."), h("p", null, "Open this again in a minute."))); return; }
    st.data = r;
    st.rows = r.sites || [];
    draw();
    poll();
  };
  many.addEventListener("click", () => makeAll());
  addBtn.addEventListener("click", () => go({ view: st.view === "add" ? "all" : "add", site: "" }));

  function draw() {
    addBtn.setAttribute("aria-expanded", st.view === "add" ? "true" : "false");
    // The box is made once, so a redraw (the list after adding) keeps what it said.
    if (st.view === "add" && !st.addEl) st.addEl = addBox();
    addSlot.replaceChildren(st.view === "add" ? st.addEl : "");
    if (!st.rows) return;
    many.disabled = !W.lineSites(st.rows).length;
    if (!st.rows.length) { list.replaceChildren(h("p", { class: "empty" }, "No sites yet. Add several sites above, or one with Add a site.")); return; }
    list.replaceChildren(...st.rows.map(siteCard));
  }

  function siteCard(row) {
    const site = row.site;
    const open = st.site === site && (st.view === "site" || st.view === "mcp");
    const got = lineFor(site, row.jobs);
    const line = got && !expired(got.expires_at) ? got : null;
    const head = h("div", { class: "am-head" }, h("h3", null, withCopy(h("span", null, site), site, { label: site, cls: "ua-after" })),
      h("span", { class: `am-state${W.live(row.line) ? " live" : ""}` }, W.lineWords(row.line)));
    const acts = [];
    if (!row.pending && row.jobs.length) {
      const make = h("button", { type: "button", class: line ? "btn" : "btn primary", "aria-label": `${line ? "Make a new line" : "Make its line"} for ${site}` }, line ? "Make a new line" : "Make its line");
      make.addEventListener("click", async () => { make.disabled = true; if (line) forgetLine(site, row.jobs); await makeOne(row); go({ view: "site", site }); });
      acts.push(make);
    }
    if (line) {
      const show = h("button", { type: "button", class: "btn", "aria-expanded": open && st.view === "site" ? "true" : "false" }, open && st.view === "site" ? "Hide its line" : "Show its line");
      show.addEventListener("click", () => go(open && st.view === "site" ? { view: "all", site: "" } : { view: "site", site }));
      acts.push(show);
    } else if (row.line && W.live(row.line)) {
      const watch = h("button", { type: "button", class: "btn" }, open && st.view === "site" ? "Hide the watch" : "Watch it");
      watch.addEventListener("click", () => go(open && st.view === "site" ? { view: "all", site: "" } : { view: "site", site }));
      acts.push(watch);
    }
    const two = h("button", { type: "button", class: "btn", "aria-expanded": open && st.view === "mcp" ? "true" : "false" }, "Two lines (MCP)");
    two.addEventListener("click", () => go(open && st.view === "mcp" ? { view: "all", site: "" } : { view: "mcp", site }));
    acts.push(two);
    const more = open && st.view === "site" ? linePart(row, line) : open && st.view === "mcp" ? mcpPart(row) : null;
    return h("section", { class: `am-site${open ? " open" : ""}`, "data-site": site, "aria-label": site },
      head, h("p", { class: "sub" }, W.leftWords(row)),
      row.jobs.length && !row.pending ? h("p", { class: "note" }, `An agent can do: ${jobsWords(row.jobs)}.`) : null,
      h("div", { class: "acts" }, acts), more);
  }

  // A site's own line (made in this page) and its watch, or the watch of a line made before.
  function linePart(row, line) {
    const site = row.site;
    const out = h("div");
    const parts = [];
    if (line) {
      const [box, show] = lineBox(line);
      const left = timeLeft(line.expires_at);
      parts.push(h("p", null, `Paste this into the AI agent working on ${site} (in its own folder or on its server). It works once${line.expires_at ? `, until ${stamp(line.expires_at)}${left ? ` (${left})` : ""}` : ""}.`),
        box, h("div", { class: "acts" }, show, cancelButton(site, line.link_id, out, () => { forgetLine(site, row.jobs); load(); })), out, safetyBox());
    }
    const link = line?.link_id || row.line?.link_id || "";
    if (link) {
      const jobs = line ? row.jobs : row.line?.line_jobs || row.jobs;
      parts.push(h("h4", null, "Watch its agent work"),
        ...[].concat(watchPanel({ site, jobs, link, agent: "claude-code", send: sendState(site, st.data || {}) })));
    }
    return h("div", { class: "am-more" }, parts.length ? parts : h("p", { class: "note" }, "No line for this site in this page yet: press Make its line."));
  }

  // The two lines for one site: its own MCP token with the setup scope, then the words.
  function mcpPart(row) {
    const site = row.site;
    const url = st.data?.mcp?.url || `${location.origin}/traffic-mcp`;
    const box = h("div");
    const drawToken = (token) => {
      const two = W.twoLines(site, url, token);
      box.replaceChildren(
        h("p", null, h("strong", null, "Line 1. "), `In a terminal, in ${site}'s own project folder. Claude Code:`), codeBlock(two.claude, "line 1 for Claude Code"),
        h("p", null, "Or Codex (one server per site in its settings):"), codeBlock(two.codex, "line 1 for Codex"),
        h("p", null, h("strong", null, "Line 2. "), "Start the assistant there, and type:"), codeBlock(two.two, "line 2"),
        h("p", { class: "note" }, "The token is shown only this once. Copy line 1 now."));
    };
    const made = TOKENS.get(site);
    if (made) drawToken(made);
    else {
      const mk = h("button", { type: "button", class: "btn primary", "aria-label": `Make the MCP token for ${site}` }, `Make the token for ${site}`);
      mk.addEventListener("click", async () => {
        mk.disabled = true;
        const r = await call("tokens/create", { name: W.TOKEN_NAME(site), sites: [site], scopes: ["mcp", "setup"] });
        mk.disabled = false;
        if (!r.ok || !r.token) { box.replaceChildren(answerBox("bad", why(r, "The token was not made."), h("p", null, "Only an owner or admin can make it. Try again in a moment.")), mk); return; }
        TOKENS.set(site, r.token);
        drawToken(r.token);
      });
      box.replaceChildren(h("p", null, `One token for ${site} only: it reads this site's figures and can make its set-up lines. Then two lines: one connects your assistant, one asks it to set the site up.`), mk);
    }
    return h("div", { class: "am-more" },
      st.data?.mcp?.on === false ? answerBox("warn", "MCP is switched off on this Skald server.", h("p", null, "Whoever runs your Skald turns it on (mcp.enabled; Docker: SKALD_MCP=true). Until then, use the site's line above.")) : null,
      box, h("ul", { class: "am-safe" }, W.TWO_SAFE.map((x) => h("li", null, x))),
      h("p", { class: "note" }, "See or revoke it in ", h("a", { href: "#settings/ai/tokens" }, "Tokens & links"), ". More on assistants: ",
        h("a", { href: "#settings/ai/mcp" }, "AI assistant (MCP)"), ". No MCP? The site's own line (Make its line) does the same in one paste."));
  }

  // Several new sites at once: each added as Add a site adds it, then each one's own line.
  function addBox() {
    const area = h("textarea", { rows: "4", spellcheck: "false", "aria-label": "New sites, one per line", placeholder: "shop.example.com\nblog.example.org" });
    const go1 = h("button", { type: "button", class: "btn primary" }, "Add these sites");
    const out = h("div", { role: "status", "aria-live": "polite" });
    go1.addEventListener("click", async () => {
      const { names, bad, more } = W.siteNames(area.value);
      if (!names.length) { out.replaceChildren(answerBox("bad", "Type at least one site name, like shop.example.com.")); return; }
      go1.disabled = true;
      const done = [];
      for (const name of names) {
        out.replaceChildren(h("p", { class: "empty" }, `Adding ${name}...`));
        const r = await call("sites/add", { host: name, token: false });
        done.push({ name, ok: r.ok, words: r.ok ? (r.verify?.state === "pending" ? "added; verify its domain first (Settings › Sites)" : "added") : why(r, "not added") });
        if (!r.ok && r.status === 403) break;       // the plan's limit or the role: the rest would be refused too
      }
      go1.disabled = false;
      out.replaceChildren(...[h("ul", { class: "am-added" }, done.map((x) => h("li", { class: x.ok ? "ok" : "bad" }, h("b", null, x.name), `: ${x.words}`))),
        bad.length ? h("p", { class: "note" }, `Not site names, left out: ${bad.join(", ")}.`) : null,
        more ? h("p", { class: "note" }, `${more} more were left out: at most ${W.MOST_NEW} at once.`) : null,
        done.some((x) => x.ok) ? h("p", null, "Each new site is in the list below, with its own Make its line.") : null].filter(Boolean));
      if (done.some((x) => x.ok)) load();
    });
    return h("section", { class: "am-add" }, h("h3", null, "Add several sites"),
      h("p", { class: "sub" }, `One per line, at most ${W.MOST_NEW}. Each is added as Add a site adds it: the same checks and plan limits, and a domain to verify first where your Skald asks for it.`),
      area, h("div", { class: "acts" }, go1), out);
  }

  async function makeOne(row) {
    const r = await makeLine(row.site, row.jobs);
    if (!r.ok) said.replaceChildren(`${row.site}: ${why(r, "the line was not made.")}`);
    // The card's own state at once (a new line waits for its agent), not after the next load.
    else row.line = { link_id: r.link_id, state: "waiting", expires_at: r.expires_at, opened_at: null, keys_at: null, reported_at: null };
    return r;
  }
  async function makeAll() {
    const sites = W.lineSites(st.rows);
    many.disabled = true;
    let ok = 0;
    for (const site of sites) {
      said.textContent = `Making ${site}'s line...`;
      const row = st.rows.find((x) => x.site === site);
      if (lineFor(site, row.jobs) && !expired(lineFor(site, row.jobs).expires_at)) { ok += 1; continue; }
      const r = await makeOne(row);
      if (r.ok) ok += 1;
    }
    many.disabled = false;
    said.className = "msg ok";
    said.textContent = `${ok} of ${sites.length} lines made, one per site. Show each one's line, and paste it into that site's own session.`;
    await load();
  }

  // While the view is open, ask how far each live line got (every 10 seconds).
  function poll() {
    clearTimeout(st.timer);
    st.timer = setTimeout(async () => {
      if (!d.el.isConnected) return;
      const live = (st.rows || []).filter((r) => W.live(r.line) && !(st.view === "site" && st.site === r.site));
      for (const row of live) {
        const r = await call("sites/agentstatus", { site: row.site, link_id: row.line.link_id });
        if (r.ok) row.line = { ...row.line, ...r };
      }
      if (live.length && d.el.isConnected) {
        for (const row of live) d.el.querySelector?.(`section[data-site="${row.site}"] .am-state`)?.replaceChildren(W.lineWords(row.line));
      }
      poll();
    }, POLL_MS);
  }

  draw();
  load();
  return d;
}

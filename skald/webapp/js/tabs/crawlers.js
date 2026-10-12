// The crawler policy editor and the suggested llms.txt, used by AI & bots >
// Crawler rules and llms.txt (ai-rules.js; once Settings > AI crawlers).
// The editor: let each AI company's crawlers in, keep them out,
// or keep out only the ones that collect for training (AI search and answers
// stay). A crawler can be set on its own. Saved through the helper
// (GET/POST <page>/bot-policy, admins only); nginx applies it a few seconds
// later and the page waits until it is live. Beside each crawler: how often
// it was refused (403) in the last 30 days and today. Skald never writes the
// site's robots.txt; it only suggests what to put there. Below: a suggested
// llms.txt (llms_txt.json, llms_txt.py) to preview, copy or download; Skald
// never writes it to the website either.

import { h, n } from "../ui.js";
import { call, installOnly, INSTALL_ONLY } from "./ipmanager.js";
import { isViewer, VIEWER } from "../access.js";
import { getJSON, base } from "../data.js";
import { download } from "../table.js";
// The policy applies to every site of the install: with accounts only an install admin saves it.
const lockWhy = () => (isViewer() ? VIEWER : INSTALL_ONLY);

const MODES = [["allow", "Allow"], ["block_training", "Block training only (keeps AI search and answers)"], ["block", "Block"]];
const TIER = { training: "collects for training", index: "indexes for AI search", asked: "fetches for someone's question" };
let DRAFT = null;   // the policy being edited: {owners, crawlers}, sent whole on save

function refused(m) {
  const out = {};
  const add = (b) => { if (b) for (const [k, v] of Object.entries(b)) out[k] = (out[k] || 0) + v; };
  for (const d of (m.x.bots?.days || []).slice(-30)) if (d.state === "ok") add(d.blocked);
  add(m.x.bots?.today?.blocked);
  return out;
}

function copyBtn(text) {
  const btn = h("button", { type: "button", class: "btn cp" }, "Copy");
  btn.addEventListener("click", async () => { try { await navigator.clipboard.writeText(text); btn.textContent = "Copied"; } catch { btn.textContent = "Select and copy"; } setTimeout(() => { btn.textContent = "Copy"; }, 1600); });
  return btn;
}

function copyBox(text) {
  return h("div", { class: "bp-sugg" }, h("div", { class: "bp-sugg-h" }, h("b", null, "robots.txt suggestion"), h("span", null, "Skald never writes your robots.txt"), copyBtn(text)), h("pre", null, text));
}

// Suggested llms.txt: the site's pages people and AI assistants read most (90 recorded days).
// What the file says, never a guess.
export function llmsBox(m) {
  const box = h("div", { class: "bp-sugg ai-llms", "aria-live": "polite" }, h("p", { class: "note ai-llms-say" }, "Loading the suggested llms.txt…"));
  getJSON(base(m.view) + "llms_txt.json").then((r) => box.replaceChildren(...llmsParts(r)), () => box.replaceChildren(...llmsParts({ state: "error", error: "it could not be loaded" })));
  return box;
}

function llmsParts(r) {
  const top = (...btns) => h("div", { class: "bp-sugg-h" }, h("b", null, "Suggested llms.txt"), h("span", null, "Skald never writes to your website"), ...btns);
  const say = (text) => [top(), h("p", { class: "note ai-llms-say" }, text)];
  if (r?.state === "error") return say(`It could not be built: ${r.error || "no reason given"}.`);
  if (!r || r.schema_version !== 1) return say("Not built yet. It appears after the next dashboard update.");
  if (!r.ok) return say(r.why || "There is nothing to suggest yet.");
  const p = r.period || {};
  const left = (p.left_out || []).length ? ` Days not recorded are left out: ${p.left_out.map((d) => d.day).join(", ")}.` : "";
  const titles = r.titles === "website" ? "Titles come from your website's page list." : "Your website gives no page list, so each link is named by its path: put the page titles in.";
  return [top(copyBtn(r.text), h("button", { type: "button", class: "btn cp", onclick: () => download("llms.txt", r.text, "text/markdown;charset=utf-8") }, "Download")),
    h("p", { class: "note ai-llms-say" }, `The pages people and AI assistants read most, ${p.first} to ${p.last} (${p.counted} recorded days), by section.${left} ${titles} Write the summary line yourself, check the links, then publish it at /llms.txt.`),
    h("pre", null, r.text)];
}

/* The policy editor alone (no title, no llms.txt): the nodes to put in a section. */
export function editor(m) {
  const api = m.x.bots?.api?.bot_policy;
  DRAFT = null;
  if (!api) return [h("div", { class: "state" }, h("div", null, "AI crawler settings are not set up on this server yet. Once they are, each AI company's crawlers can be allowed or blocked here; until then every crawler is allowed."))];
  const body = h("div", { class: "bp" }, h("p", { class: "empty" }, "Loading the settings…"));
  const viewer = isViewer() || installOnly();
  const counts = refused(m);
  let poll = null;
  const draw = (r, note) => {
    if (!r.ok) { body.replaceChildren(h("div", { class: "state bad" }, h("div", null, r.missing ? "AI crawler settings are not set up on this server yet." : `The settings could not be read: ${r.error}`))); return; }
    DRAFT ||= { owners: { ...(r.policy?.owners || {}) }, crawlers: { ...(r.policy?.crawlers || {}) } };
    const pending = r.applied && r.policy?.updated_at && r.applied.policy_updated_at !== r.policy.updated_at;
    const status = r.applied?.error ? h("p", { class: "bp-status bad" }, `Not applied: ${r.applied.error}`)
      : pending ? h("p", { class: "bp-status wait" }, "Saved. Being applied to the site…")
        : r.applied ? h("p", { class: "bp-status ok" }, `Live on the site${r.blocked?.length ? `: ${r.blocked.length} crawler${r.blocked.length === 1 ? "" : "s"} blocked` : ": every crawler allowed"}.`) : null;
    const changed = JSON.stringify(DRAFT) !== JSON.stringify({ owners: r.policy?.owners || {}, crawlers: r.policy?.crawlers || {} });
    const save = h("button", { type: "button", class: "btn primary", disabled: viewer || !changed, title: viewer ? lockWhy() : null, onclick: async () => {
      save.disabled = true;
      const res = await call(api, DRAFT);
      if (res.ok) { DRAFT = null; draw(res); watch(); } else draw(r, res.error === "admins only" ? VIEWER : `Not saved: ${res.error}${/429/.test(res.error || "") ? " Wait two seconds and save again." : ""}`);
    } }, "Save");
    const undo = changed ? h("button", { type: "button", class: "linkish", onclick: () => { DRAFT = null; draw(r); } }, "Undo changes") : null;
    body.replaceChildren(...[
      h("div", { class: "bp-bar" }, status, changed ? h("span", { class: "bp-unsaved" }, "Unsaved changes") : null, h("span", { class: "grow" }), undo, save),
      note ? h("p", { class: "note bad-note", role: "alert" }, note) : null,
      viewer ? h("p", { class: "note viewer-note" }, lockWhy()) : null,
      h("div", { class: "bp-list" }, (r.assistants || []).map((a) => owner(a, counts, viewer, () => draw(r)))),
      r.robots_suggestion ? copyBox(r.robots_suggestion) : null,
      h("p", { class: "note" }, "Blocking answers the crawler with 403 before the page is served; robots.txt is only a request, which some crawlers ignore. A crawler marked robots.txt only cannot be told apart by the server, so only a robots.txt line can ask it to stay away.")].filter(Boolean));
  };
  // After a save nginx applies the change within seconds: ask again until it is live.
  const watch = () => {
    clearTimeout(poll);
    let tries = 0;
    const again = async () => {
      if (!body.isConnected || ++tries > 15) return;
      const r = await call(api);
      draw(r);
      if (r.ok && r.applied && r.applied.policy_updated_at !== r.policy?.updated_at && !r.applied.error) poll = setTimeout(again, 2000);
    };
    poll = setTimeout(again, 1500);
  };
  call(api).then((r) => draw(r));
  return [body];
}

function owner(a, counts, viewer, redraw) {
  const mode = DRAFT.owners[a.owner] || "allow";
  const seg = h("div", { class: "seg plain bp-seg", role: "radiogroup", "aria-label": `${a.owner}: crawlers` }, MODES.map(([k, w]) =>
    h("button", { type: "button", role: "radio", "aria-checked": String(mode === k), "aria-pressed": String(mode === k), disabled: viewer, title: viewer ? lockWhy() : w,
      onclick: () => { if (k === "allow") delete DRAFT.owners[a.owner]; else DRAFT.owners[a.owner] = k; redraw(); } }, k === "block_training" ? "Block training only" : w)));
  const would = (c) => DRAFT.crawlers[c.name] || (mode === "block" || (mode === "block_training" && c.tier === "training") ? "block" : "allow");
  return h("section", { class: "bp-owner" },
    h("div", { class: "bp-oh" }, h("h3", null, a.owner), seg),
    mode === "block_training" ? h("p", { class: "bp-hint" }, "Training crawlers are kept out; AI search and answers to people's questions still reach the site.") : null,
    h("table", { class: "bp-t" }, h("caption", { class: "vh" }, `${a.owner}'s crawlers`),
      h("colgroup", null, h("col", { class: "c1" }), h("col", { class: "c2" }), h("col", { class: "c3" }), h("col", { class: "c4" }), h("col", { class: "c5" })),
      h("thead", null, h("tr", null, h("th", { scope: "col" }, "Crawler"), h("th", { scope: "col" }, "What it does"), h("th", { scope: "col" }, "Set on its own"), h("th", { scope: "col" }, "Result"), h("th", { scope: "col", class: "num" }, "Refused (403), 30 days"))),
      h("tbody", null, a.crawlers.map((c) => {
        const own = h("select", { "aria-label": `${c.name}: set on its own`, disabled: viewer, title: viewer ? lockWhy() : null, onchange: (e) => { if (e.target.value) DRAFT.crawlers[c.name] = e.target.value; else delete DRAFT.crawlers[c.name]; redraw(); } },
          h("option", { value: "", selected: !DRAFT.crawlers[c.name] }, `As ${a.owner}`), h("option", { value: "allow", selected: DRAFT.crawlers[c.name] === "allow" }, "Always allow"), h("option", { value: "block", selected: DRAFT.crawlers[c.name] === "block" }, "Always block"));
        const eff = would(c);
        return h("tr", null, h("th", { scope: "row" }, c.name, c.robots_only ? h("span", { class: "bp-ro", title: "The server cannot block it: only a robots.txt line can ask it to stay away" }, "robots.txt only") : null),
          h("td", null, TIER[c.tier] || c.tier), h("td", null, own),
          h("td", null, h("span", { class: `rb ${eff === "block" ? (c.robots_only ? "warn" : "bad") : "ok"}` }, eff === "block" ? (c.robots_only ? "Ask in robots.txt" : "Blocked") : "Allowed")),
          h("td", { class: "num" }, counts[c.name] ? n(counts[c.name]) : "0"));
      }))));
}

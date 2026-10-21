// "What Skald found": the site check's card, in step 1 of the "Add a site"
// wizard (site-wizard.js) and of Settings > Connections' "Send this site's
// visits" dialog (conn-send.js).
//
// POST <page>/sites/detect {address, name?} (connections_api.py, site_detect.py)
// looks at the site from outside and answers plain facts: its server, the
// platform in front of it, what its pages are built with, its host names, and
// a suggested way for its visits to reach Skald, with the reason. Every line is
// a suggestion: "Use these" (on by default) lets the owner keep or drop them.
//
//   const card = detectCard(st, { address: () => "www.example.com", name, auto });
//   card.run()  checks now; card.later() checks after DETECT_WAIT_MS of quiet typing
//   st.found    the last answer's facts; st.useFound: the toggle
//   recommendFor(st) -> {id, reason, site} or null, for the chooser (conn-send.js)

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { why } from "./forms.js";
import { methodOf } from "./conn-words.js";

export const DETECT_WAIT_MS = 700;

const TICK = "✓";

/* The card's lines, with no DOM so tests/js/connections.mjs can read them:
   [{name, value, known}] for the server, the platform, the framework, the
   host names; value is "could not tell" when the check did not see it. */
export function foundLines(f) {
  if (!f || !f.reachable) return [];
  const tell = "could not tell";
  const server = f.server && f.server !== "unknown"
    ? `${f.server_label || f.server}${f.os ? `, on ${f.os}` : ""}` : "";
  const platform = f.platform_label
    || (server ? "none in front: the site answers from its own server" : "");
  const hosts = (f.hosts || []).join(" and ");
  const moves = (f.redirects || []).map((r) => `${r.from} sends visitors to ${r.to}`).join("; ");
  return [
    { name: "Server", value: server || tell, known: Boolean(server) },
    { name: "Platform", value: platform || tell, known: Boolean(platform) },
    { name: "Built with", value: f.framework_label || tell, known: Boolean(f.framework_label) },
    { name: "Host names", value: hosts ? `${hosts}${moves ? ` (${moves})` : ""}` : tell, known: Boolean(hosts) },
  ];
}

// The suggested way, when the toggle is on and the check named one.
export function recommendFor(st) {
  const f = st.found;
  if (!f || st.useFound === false || !f.recommended_method || !methodOf(f.recommended_method)) return null;
  return { id: f.recommended_method, reason: f.reason || "", site: f.site || st.site || "" };
}

// What the add-site and settings paths take from the check: {hosts, asset_prefixes}.
export function suggestionsFor(st, site) {
  const f = st.found;
  if (!f || st.useFound === false || !f.reachable || (site && f.site && f.site !== site)) return {};
  const out = {};
  if (Array.isArray(f.hosts) && f.hosts.length) out.hosts = f.hosts;
  if (Array.isArray(f.asset_prefixes) && f.asset_prefixes.length) out.asset_prefixes = f.asset_prefixes;
  return out;
}

function lineEl(x) {
  return h("li", { class: x.known ? "ok" : "unsure" }, h("span", { class: "cn-tick", "aria-hidden": "true" }, x.known ? TICK : "?"),
    h("span", null, h("b", null, `${x.name}: `), x.value));
}

function body(st) {
  const f = st.found;
  if (!f) return [];
  if (!f.reachable) {
    return [h("div", { class: "state cn-answer warn", role: "status" }, h("div", null,
      h("p", null, h("strong", null, `Skald could not reach ${f.site} from here.`)),
      f.reason ? h("p", null, f.reason) : null,
      h("p", null, "Nothing is wrong with adding it: choose how its visits reach Skald by hand.")))];
  }
  const way = methodOf(f.recommended_method);
  const out = [h("ul", { class: "cn-found-list" }, foundLines(f).map(lineEl))];
  if (f.asset_prefixes?.length) out.push(h("p", { class: "note" }, `Page assets: ${f.asset_prefixes.join(", ")}. ${f.assets_note || ""}`.trim()));
  else if (f.assets_note) out.push(h("p", { class: "note" }, f.assets_note));
  // A Next.js site on its own nginx or Apache: the one log_format field (site_detect.LOG_NOTE).
  if (f.log_note) out.push(h("p", { class: "note cn-log-note" }, f.log_note));
  if (f.hosted_builder) out.push(h("p", { class: "cn-builder" }, h("strong", null, `${f.platform_label} keeps its server log to itself. `), "Skald cannot read it, so the script tag is the way."));
  out.push(h("p", { class: "cn-found-why" }, way ? h("b", null, `Suggested: ${way.title}. `) : h("b", null, "No way suggested. "), f.reason || ""));
  return out;
}

export function detectCard(st, { address, name = null, auto = false, onFound = null } = {}) {
  if (st.useFound === undefined) st.useFound = true;
  const slot = h("div", { class: "cn-found-body" });
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const toggle = h("input", { type: "checkbox", name: "use-found" });
  toggle.checked = st.useFound !== false;
  toggle.addEventListener("change", () => { st.useFound = toggle.checked; if (onFound) onFound(st.found, "toggle"); });
  const again = h("button", { type: "button", class: "btn" }, "Check again");
  const use = h("label", { class: "cn-use" }, toggle, h("span", null, "Use these"));
  const card = h("section", { class: "cn-found", "aria-label": "What Skald found" },
    h("div", { class: "cn-found-top" }, h("h4", null, "What Skald found"), use, again), said, slot,
    h("p", { class: "note" }, "Skald looked at the site from outside, like a browser. These are suggestions: you can change each one."));
  let timer = null, asked = "", running = 0;
  const draw = () => {
    use.hidden = !st.found || !st.found.reachable;
    again.hidden = !st.found && !asked;
    slot.replaceChildren(...body(st));
  };
  card.run = async () => {
    clearTimeout(timer);
    const where = String((address && address()) || "").trim();
    if (!where) return null;
    asked = where;
    const mine = ++running;
    said.className = "msg";
    said.textContent = `Looking at ${where}...`;
    again.disabled = true;
    const r = await call("sites/detect", name ? { address: where, name } : { address: where });
    if (mine !== running) return null;       // a newer check started
    again.disabled = false;
    if (!r.ok) {
      said.className = "msg err";
      said.textContent = `${why(r, "The site could not be checked.")} You can choose by hand.`;
      draw();
      return null;
    }
    said.textContent = "";
    st.found = r.found;
    draw();
    if (onFound) onFound(st.found, "found");
    return st.found;
  };
  card.later = (where) => {
    clearTimeout(timer);
    if (!where || where === asked) return;
    timer = setTimeout(() => card.run(), DETECT_WAIT_MS);
  };
  again.addEventListener("click", () => card.run());
  draw();
  if (auto && !st.found) queueMicrotask(() => card.run());
  return card;
}

/* Connections: put the found host names (added to the site's own) and page
   assets in this site's settings (POST settings/save, as Settings > Sites
   saves them). Returns the words to show. */
export async function saveFound(st, site) {
  const got = suggestionsFor(st, site);
  if (!got.hosts && !got.asset_prefixes) return { ok: false, words: "Nothing found to save." };
  const now = await call("settings");
  if (!now.ok) return { ok: false, words: why(now, "The site's settings could not be read.") };
  const body = {};
  const hostsNow = now.settings?.["sites.hosts"];
  if (got.hosts && hostsNow?.editable !== false) body["sites.hosts"] = [...new Set([...(hostsNow?.value || []), ...got.hosts])];
  if (got.asset_prefixes && now.settings?.["site.asset_prefixes"]?.editable !== false) body["site.asset_prefixes"] = got.asset_prefixes;
  if (!Object.keys(body).length) return { ok: false, words: "You cannot change these settings here." };
  const r = await call("settings/save", body);
  return r.ok ? { ok: true, words: "Saved in this site's settings (Settings > Sites)." } : { ok: false, words: why(r, "It was not saved.") };
}

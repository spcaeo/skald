// "Add a site", step by step (Settings > Add or remove sites, and "+ Add a
// site" in the site picker): 1 your site, 2 prove it's yours, 3 how Skald gets
// its visits, 4 install, 5 test and finish. Steps 3 to 5 are the ones of
// Settings > Connections' "Send this site's visits to Skald" (conn-send.js).
//
// The progress is kept on the server per site (POST <page>/sites/setup,
// accounts/site_setup.py): the step reached, the way chosen, the sending
// token's id (never the token). Closing the dialog or the browser loses
// nothing; the site's row and the picker offer "Setup: step 3 of 5, continue".
//
// Step 1 also looks at the site (conn-detect.js, POST <page>/sites/detect) once
// the address is typed: its server, platform, framework and host names. With
// "Use these" on, the site is added with the found host names and page assets,
// step 3 chooses the suggested way, and the facts are kept in the progress
// (sites/setup `found`), so a resumed wizard shows them again.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { input, field, why } from "./forms.js";
import { wizard, codeBlock, answerBox, helpLink } from "./conn-ui.js";
import { sendState, methodChooser, chooseCheck, tokenPanel, testPanel, troubleTable, shareFor, preselect } from "./conn-send.js";
import { detectCard, recommendFor, suggestionsFor } from "./conn-detect.js";
import { installFor } from "./conn-install.js";
import { methodOf } from "./conn-words.js";
import { withUrl } from "../urlactions.js";

export const STEPS = 5;
const NAME = /^(?=.{3,100}$)[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)+$/;
const BAD = "That is not a site's address. Type it like www.example.com.";

/* "https://WWW.Example.com/pricing" -> {name: "www.example.com"}, as the server
   makes it (saas/signups.py clean_host, accounts/site_configs.py clean_name). */
export function siteFrom(raw) {
  const typed = String(raw || "").trim().toLowerCase();
  if (!typed) return { error: "Type the site's address, like www.example.com." };
  if (/\s/.test(typed)) return { error: "An address has no spaces. Type it like www.example.com." };
  let host = "";
  try { host = new URL(`https://${typed.replace(/^[a-z][a-z0-9+.-]*:\/\//, "").replace(/^\/\//, "")}`).hostname; } catch { return { error: BAD }; }
  host = host.replace(/\.$/, "");
  if (!NAME.test(host) || /^[\d.]+$/.test(host)) return { error: BAD };
  return { name: host };
}

// sites/setup, quietly: the wizard goes on even if a save fails, and says so.
async function save(w, body) {
  if (!w.state.site) return;
  const r = await call("sites/setup", { name: w.state.site, ...body });
  if (!r.ok) w.say(`Your progress was not saved: ${why(r)}`);
}

// The found facts as the progress keeps them, with the toggle.
const kept = (st) => ({ ...st.found, use: st.useFound !== false });

function stepSite(w, data) {
  const st = w.state;
  if (st.site) {
    const card = detectCard(st, { address: () => st.site, name: st.site, auto: !st.found,
      onFound: (f, why) => { if (why === "toggle" && f) save(w, { found: kept(st) }); } });
    return [h("p", null, "The site: ", h("strong", null, st.site), ". It is made already; press Next to go on."), card,
      h("p", { class: "note" }, "Its host names can be changed in Settings > Sites.")];
  }
  if (data.can_add === false) return [answerBox("bad", data.add_refused || "Adding sites is not available here.")];
  const addr = input({ name: "site-address", autocomplete: "off", inputmode: "url", maxlength: "200", placeholder: "www.example.com" });
  addr.value = st.typed || "";
  const zone = input({ name: "timezone", autocomplete: "off", maxlength: "64" });
  try { zone.value = st.zone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; } catch { zone.value = "UTC"; }
  const shown = h("p", { class: "note" });
  const card = detectCard(st, { address: () => siteFrom(addr.value).name || "" });
  const say = () => {
    st.typed = addr.value;
    st.zone = zone.value;
    const got = siteFrom(addr.value);
    shown.textContent = addr.value.trim() ? (got.error || `The site will be ${got.name}: visits to ${got.name} count for it.`) : "";
    if (got.name && got.name !== st.found?.site) card.later(got.name);
  };
  addr.addEventListener("input", say);
  zone.addEventListener("input", say);
  say();
  return [h("p", null, "The address of the site, as people type it. A whole link works too."),
    field("Site address", addr, "For example https://www.example.com/. Its host name becomes the site's name here."), shown, card,
    field("Time zone", zone, "Days are counted in this zone, like Europe/London.")];
}

async function makeSite(w) {
  const st = w.state;
  if (st.site) return true;
  const got = siteFrom(st.typed);
  if (got.error) { w.say(got.error); return false; }
  const r = await call("sites/add", { host: got.name, timezone: String(st.zone || "").trim(), format: "auto", token: false, ...suggestionsFor(st, got.name) });
  if (!r.ok) { w.say(why(r, "The site was not added.")); return false; }
  st.site = r.site;
  st.verify = r.verify || null;
  Object.assign(st.send, sendState(r.site, st.data));
  if (st.found && st.found.site !== r.site) st.found = null;     // a check of another address
  await save(w, st.found ? { step: 2, found: kept(st) } : { step: 2 });
  if (st.onChange) st.onChange();
  return true;
}

function stepProve(w) {
  const st = w.state;
  const v = st.verify;
  if (!v) return [answerBox("ok", "No proof needed.", h("p", null, "This server does not ask an admin to prove a site is theirs before it collects for it. Press Next."))];
  if (v.state === "verified") return [answerBox("ok", `${st.site} is verified.`, h("p", null, "Press Next."))];
  const out = h("div");
  const btn = h("button", { type: "button", class: "btn primary" }, "Check now");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const r = await call("sites/verify", { name: st.site });
    btn.disabled = false;
    if (!r.ok) { out.replaceChildren(answerBox("bad", why(r, "Not found yet."), h("p", null, "A new DNS record can take a few minutes to show. Try again soon."))); return; }
    st.verify = { state: "verified" };
    out.replaceChildren(answerBox("ok", `${st.site} is verified. Skald collects for it from now on.`));
    await save(w, { step: 3 });
  });
  return [h("p", null, "Show that the domain is yours. Nothing is collected for the site until then. Do one of these:"),
    h("p", null, h("b", null, "A DNS TXT record"), ` on ${st.site}:`), codeBlock(v.txt, "the TXT record"),
    h("p", null, h("b", null, "Or this tag"), ` in the <head> of https://${st.site}/:`), codeBlock(v.meta, "the meta tag"),
    h("div", { class: "acts" }, btn), out,
    h("p", { class: "note" }, "You can go on and install now; the check can wait. Lines sent before it are refused and sent again by the shipper later.")];
}

// Step 3: the ways, the check's one chosen (conn-send.js preselect) and marked.
function stepHow(wz) {
  const st = wz.state;
  const rec = recommendFor(st);
  preselect(st.send, rec);
  const lost = st.found && !st.found.reachable
    ? h("p", { class: "note" }, `Skald could not reach ${st.found.site} to suggest a way. Choose it by hand.`) : null;
  return [h("p", null, "Where does the site run? Choose the way its visits reach Skald."), lost, methodChooser(st.send, () => wz.say(""), rec)].filter(Boolean);
}

// In the address as setup=new or setup=<site>, with its step (js/overlays.js; on Settings >
// Add or remove sites: tabs/sitesadmin.js openSiteKey reopens it from a link).
export function siteWizard({ data = {}, name = null, start = 0, method = "", verify = null, found = null, onChange = null } = {}) {
  const send = sendState(name || "", data);
  send.method = method || "";
  const state = { site: name, verify, data, send, onChange, typed: "", zone: "", found: found || null, useFound: found ? found.use !== false : true };
  const w = wizard({
    title: name ? `Set up ${name}` : "Add a site", subtitle: "Five short steps. You can close this and continue later: nothing is lost.",
    key: "site-wizard", state, start, done: "Finish later", route: { key: "setup", value: name || "new" },
    onStep: (i, wz) => { if (wz.state.site && i > 0) save(wz, { step: i + 1 }); },
    onClose: () => { if (onChange) onChange(); },
    steps: [
      { name: "Your site", draw: (wz) => stepSite(wz, data), next: makeSite },
      { name: "Prove it's yours", draw: stepProve },
      { name: "How visits reach Skald", draw: stepHow,
        check: (wz) => chooseCheck(wz.state.send), next: async (wz) => { await save(wz, { step: 4, method: wz.state.send.method }); return true; } },
      { name: "Install", draw: (wz) => {
        const st = wz.state.send;
        return [h("p", { class: "sub" }, `${methodOf(st.method)?.title || ""}. The send address: `, withUrl(h("code", null, st.url), st.url, { cls: "ua-after" })),
          ...tokenPanel(st, { onMade: (r) => save(wz, { token_id: r.id || "" }) }),
          h("h4", null, "Install"), ...installFor(st.method, st), shareFor(st)];
      } },
      { name: "Test and finish", draw: (wz) => {
        const st = wz.state.send;
        const done = h("div");
        return [testPanel(st, { onResult: async (v) => {
          if (v.kind !== "ok") return;
          await save(wz, { step: STEPS, done: true });
          done.replaceChildren(answerBox("ok", `Done: ${st.site} is receiving visits.`,
            h("div", { class: "acts" }, h("a", { class: "btn primary", href: `/traffic/${st.site}/` }, "Open its dashboard"))));
        } }), done, troubleTable(),
        h("p", { class: "note" }, "Not connected yet? Finish later: the site's row says how far it got, and ", helpLink("troubleshooting-connections", "the troubleshooting guide"), " has the common fixes.")];
      } },
    ],
  });
  return w;
}

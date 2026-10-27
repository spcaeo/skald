// Settings › Site › Internal traffic (v2): the addresses that count as our own traffic, as
// rows: the label, the address with its copy icon, since when, a pill (Active, Paused, or
// Always on for a config-file line). "Add an address" is the page's one button (edit=ip-add);
// a row's Change opens its drawer (edit=ip-<code>: a code of the address, never the address)
// with Pause or Resume, Edit and Delete. The figures (ours.js) wait behind a fold.
// The helper behind <page>/ours checks who asks; with accounts only an install admin changes
// the list (it applies to every site of the install), an organisation's admin reads it.

import { h, long, toast } from "../ui.js";
import { time as tzTime } from "../tz.js";
import { isViewer, sessions } from "../access.js";
import { call, installOnly, INSTALL_ONLY } from "./ipmanager.js";
import { copyIf } from "../urlactions.js";
import { field, input, status } from "./forms.js";
import { primary, rowsCard, help, fold, quietLine, pill, ic } from "./set-ui.js";
import { editPart, openEdit } from "./set-edit.js";
import ours from "./ours.js";

const API = { list: "ours", add: "ours/add", remove: "ours/remove", add_mine: "ours/add-mine", pause: "ours/pause", resume: "ours/resume", edit: "ours/edit" };
const ABOUT = "Requests from these addresses count as our own traffic, not as visitors: the office, home connections and test machines. Changes apply from now on; days already counted are not recounted. Pause an address while you test the site as a visitor, and turn it back on when you are done. Lines from the config file always apply and cannot be paused here.";
const VIEWER_WORDS = "The address list is for admins: it holds the addresses of the people who work on the site.";

const st = { api: API, entries: [], limit: 0, can: true, loaded: false, redraw: () => {} };

/* An address's code for the address bar: a hash, never the address itself. */
export function ipCode(ip) {
  let x = 2166136261;
  for (const c of String(ip)) { x ^= c.charCodeAt(0); x = Math.imul(x, 16777619) >>> 0; }
  return x.toString(36);
}
const fixedOf = (e) => e.editable === false || e.source === "config";
export const pillOf = (e) => (fixedOf(e) ? ["info", "Always on"] : e.active !== false ? ["good", "Active"] : ["off", "Paused"]);
const sinceOf = (e) => (e.added_at ? `added ${long(String(e.added_at).slice(0, 10))}` : fixedOf(e) ? "from the config file" : "");
const mayRead = () => !(sessions() && isViewer());
const mayChange = () => mayRead() && !installOnly() && st.can;

async function load() {
  const r = await call(st.api.list);
  if (r.ok) { st.entries = r.entries || []; st.limit = r.limit || 0; st.can = r.can_add !== false; st.loaded = true; }
  return r;
}
const after = (r, words) => { if (!r.ok) return r.error || "Refused."; toast(words); st.redraw(); return ""; };

/* One address: label, address (copy icon), since; its pill; Change opens its drawer. */
function row(e, m) {
  const [kind, word] = pillOf(e);
  const go = h("button", { type: "button", class: "btn set-chg", "aria-label": `Change ${e.label}` }, ic("more"));
  go.addEventListener("click", () => openEdit(`ip-${ipCode(e.ip)}`, m));
  const since = sinceOf(e);
  return h("div", { class: "set-row" }, h("span", { class: "grow sr-t" }, h("b", null, copyIf("text", e.label || "", null, { label: "label", cls: "" })),
    h("small", null, copyIf("ip", e.ip || "", e.ip, { label: "address", cls: "" }), since ? ` · ${since}` : "",
      e.active === false && e.paused_since ? ` · paused since ${tzTime(e.paused_since, { date: true })}` : "")), pill(kind, word), go);
}

export function internalTab(m, s, opts = {}) {
  st.api = { ...API, ...(m.x?.ours?.api || {}) };
  const figures = fold("Our own traffic, in figures", () => ours(m, s, opts), { cls: "set-figs" });
  if (!m.x?.ours?.api) return [quietLine("Internal addresses", "Managing internal addresses here is coming with the next data update. Until then they are set in the config file."), figures];
  if (!mayRead()) return [quietLine("Internal addresses", VIEWER_WORDS), figures];
  const go = installOnly() ? null : primary("Add an address", () => openEdit("ip-add", m), { iconName: "plus" });
  const slot = h("div", null, h("p", { class: "empty" }, "Loading the address list..."));
  const draw = (r) => {
    if (!r.ok) {
      slot.replaceChildren(r.missing ? quietLine("Internal addresses", "Managing internal addresses here is coming: the server part is being added. Until then they are set in the config file.")
        : h("p", { class: "msg err" }, r.error || "The address list could not be loaded."));
      return;
    }
    const q = help("Internal addresses", { text: ABOUT, guide: "internal-traffic" });
    const notes = [installOnly() && st.entries.length ? h("p", { class: "note" }, INSTALL_ONLY) : null,
      st.can ? null : h("p", { class: "note" }, "Adding addresses here is not set up on this server: it has no folder to keep the list in. Until it does, they are set in the config file."),
      st.limit && st.entries.length ? h("p", { class: "set-foot muted" }, `${st.entries.length} of at most ${st.limit} entries.`) : null];
    slot.replaceChildren(st.entries.length ? rowsCard(`Internal addresses (${st.entries.length})`, st.entries.map((e) => row(e, m)), { help: q })
      : quietLine("No internal addresses yet", installOnly() ? INSTALL_ONLY : "Add this computer's address, so your own visits are not counted as visitors."), ...notes.filter(Boolean));
  };
  st.redraw = () => load().then(draw);
  st.redraw();
  return [go, slot, figures];
}

/* Add an address (edit=ip-add): this computer's, or any address or range, with a label. */
function addBody(ctx) {
  const msg = status();
  const mineLabel = input({ placeholder: "e.g. Office Mac", maxlength: "60", "aria-label": "Label for this computer's address" });
  const mine = h("button", { type: "button", class: "btn primary" }, "Add my current address");
  mine.addEventListener("click", async () => {
    if (!mineLabel.value.trim()) { msg.say("Give it a label first, so the list says whose address it is."); mineLabel.focus(); return; }
    mine.disabled = true;
    const r = await call(st.api.add_mine, { label: mineLabel.value.trim() });
    mine.disabled = false;
    const bad = after(r, "Added this computer's address. Its visits count as our own traffic from now on.");
    if (bad) msg.say(bad); else ctx.close();
  });
  const ip = input({ class: "addr", placeholder: "203.0.113.7 or 203.0.113.0/24", spellcheck: "false", autocomplete: "off" });
  const label = input({ placeholder: "Label", maxlength: "60" });
  const add = h("button", { type: "submit", class: "btn" }, "Add address");
  const form = h("form", { class: "af-col", novalidate: true }, field("Address or range", ip), field("Label", label), h("div", null, add));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!ip.value.trim() || !label.value.trim()) { msg.say("Both an address (or range) and a label are needed."); return; }
    add.disabled = true;
    const r = await call(st.api.add, { ip: ip.value.trim(), label: label.value.trim() });
    add.disabled = false;
    const bad = after(r, `Added ${ip.value.trim()}.`);
    if (bad) msg.say(bad); else ctx.close();
  });
  return [h("section", { class: "set-sec" }, h("h3", null, "This computer"), h("div", { class: "af-row" }, field("Label", mineLabel), mine)),
    h("section", { class: "set-sec" }, h("h3", null, "Another address or range"), form), msg];
}
editPart("ip-add", { title: "Add an address", body: (m, s, ctx) => {
  if (!mayRead()) return "Not available to your role.";
  if (installOnly()) return INSTALL_ONLY;
  return addBody(ctx);
} });

/* One address (edit=ip-<code>): Pause or Resume, Edit, Delete; a config line is locked. */
async function entryBody(m, ctx, id) {
  if (!mayRead()) return "Not available to your role.";
  if (!st.loaded) { st.api = { ...API, ...(m.x?.ours?.api || {}) }; await load(); }
  const e = st.entries.find((x) => `ip-${ipCode(x.ip)}` === id);
  if (!e) return "That address is no longer on the list.";
  const [kind, word] = pillOf(e);
  const msg = status();
  const head = h("div", { class: "set-row" }, h("span", { class: "grow sr-t" }, h("b", null, copyIf("text", e.label || "", null, { label: "label", cls: "" })),
    h("small", null, copyIf("ip", e.ip, e.ip, { label: "address", cls: "" }), sinceOf(e) ? ` · ${sinceOf(e)}` : "")), pill(kind, word));
  if (fixedOf(e)) return [head, h("p", { class: "note" }, "Set in the config file: it always applies and cannot be paused, edited or deleted here. Change it there.")];
  if (!mayChange()) return [head, h("p", { class: "note" }, INSTALL_ONLY)];
  const on = e.active !== false;
  const sw = h("button", { type: "button", class: "btn primary" }, on ? "Pause it" : "Count it again");
  sw.addEventListener("click", async () => {
    sw.disabled = true;
    const r = await call(on ? st.api.pause : st.api.resume, { ip: e.ip });
    sw.disabled = false;
    const bad = after(r, on ? `Paused ${e.label}. From now on its visits count as visitors.` : `${e.label} is active again. From now on its visits count as our own traffic.`);
    if (bad) msg.say(bad); else ctx.close();
  });
  const ipIn = input({ class: "addr", value: e.ip, spellcheck: "false", autocomplete: "off" });
  const labelIn = input({ value: e.label, maxlength: "60" });
  const save = h("button", { type: "submit", class: "btn" }, "Save");
  const form = h("form", { class: "af-col", novalidate: true }, field("Address or range", ipIn), field("Label", labelIn, "The change applies from now on. Days before keep the old label and address."), h("div", null, save));
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const body = { ip: e.ip };
    if (ipIn.value.trim() !== e.ip) body.new_ip = ipIn.value.trim();
    if (labelIn.value.trim() !== e.label) body.label = labelIn.value.trim();
    if (!body.new_ip && !body.label) { msg.say("Nothing changed."); return; }
    save.disabled = true;
    const r = await call(st.api.edit, body);
    save.disabled = false;
    const bad = after(r, `Saved. From now on it counts as ${body.label || e.label}.`);
    if (bad) msg.say(bad); else ctx.close();
  });
  const del = h("button", { type: "button", class: "btn danger" }, "Delete");
  const confirm = h("div");
  del.addEventListener("click", () => {
    const yes = h("button", { type: "button", class: "btn danger" }, "Yes, delete");
    const no = h("button", { type: "button", class: "btn" }, "Keep it");
    confirm.replaceChildren(h("div", { class: "state warn", role: "alert" }, h("div", null,
      h("p", null, `Delete ${e.label}? It stops applying to days not yet collected; stored days keep their figures. To stop it only for a while, pause it instead.`), h("div", { class: "acts" }, yes, no))));
    no.addEventListener("click", () => confirm.replaceChildren());
    yes.addEventListener("click", async () => {
      yes.disabled = true;
      const bad = after(await call(st.api.remove, { ip: e.ip }), `Deleted ${e.label}. From now on its visits count as visitors.`);
      if (bad) msg.say(bad); else ctx.close();
    });
    no.focus();
  });
  return [head, h("div", { class: "acts" }, sw), h("section", { class: "set-sec" }, h("h3", null, "Change it"), form),
    h("section", { class: "set-sec" }, h("h3", null, "Delete it"), del, confirm), msg];
}
editPart("ip-", { prefix: true, title: "Internal address", body: (m, s, ctx, id) => entryBody(m, ctx, id) });

// Internal addresses: the addresses and ranges that count as our own traffic.
// Entries from the config file are locked here; the rest can be added,
// paused and resumed (Active / Paused), edited and deleted. The helper behind <page>/ours checks the password (nginx) and
// that the request came from this page; it never rewrites a stored day.

import { h, long } from "../ui.js";
import { time as tzTime } from "../tz.js";
import { lockForViewer, isViewer, sessions, ME } from "../access.js";
import { howTo } from "./help.js";
import { DEMO, demoAnswer } from "../demo.js";
import { copyIf } from "../urlactions.js";

const LOCK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3.5" y="7" width="9" height="6.5" rx="1.5"/><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2"/></svg>';
const ERRORS = { 400: "That is not a valid address or range.", 403: "Refused: changes only work from this page.", 409: "The list is full. Remove an entry first." };

// With accounts (access.mode: sessions) every POST also carries the session's
// CSRF value, which the page reads from <page>/me. Without it nothing is sent.
let csrf = "";
export function setCsrf(value) { csrf = typeof value === "string" ? value : ""; }
export const csrfHeaders = () => (csrf ? { "X-Skald-CSRF": csrf } : {});

export async function call(path, body) {
  // The demo has no helper: nothing is asked or posted; a list the demo build
  // wrote is read from its file, anything else says why.
  if (DEMO.on) return demoAnswer(path, body);
  let res;
  try {
    res = await fetch(path, body ? { method: "POST", credentials: "same-origin", cache: "no-store", headers: { "Content-Type": "application/json", ...csrfHeaders() }, body: JSON.stringify(body) }
      : { credentials: "same-origin", cache: "no-store", headers: csrfHeaders() });   // a read of names (people/leads) needs it too
  } catch {
    return { ok: false, error: "The server could not be reached." };
  }
  let data = null;
  try { data = await res.json(); } catch { /* not JSON: the helper does not answer this yet */ }
  if (!data) return { ok: false, status: res.status, missing: res.status === 404 || res.status === 405 || res.status === 502, error: `The address list is not available yet (${res.status}).` };
  if (!res.ok || !data.ok) return { ...data, ok: false, status: res.status, error: data.error || ERRORS[res.status] || `Refused (${res.status}).` };
  return data;
}

// With accounts the list applies to every site of the install, so only an install
// admin changes it (refresh_server.py); an organisation's admin reads it, with the reason.
export const INSTALL_ONLY = "Only an install admin can change this: it applies to every site of the install.";
export const installOnly = () => sessions() && !isViewer() && !ME.install_admin;
function lockForInstall(root) {
  if (!installOnly()) return root;
  root.querySelectorAll("button, input, select, textarea").forEach((el) => { el.disabled = true; el.title = INSTALL_ONLY; });
  if (root.classList.contains("ipm") && !root.querySelector(".viewer-note")) root.prepend(h("p", { class: "note viewer-note" }, INSTALL_ONLY));
  return root;
}

const API = { list: "ours", add: "ours/add", remove: "ours/remove", add_mine: "ours/add-mine", pause: "ours/pause", resume: "ours/resume", edit: "ours/edit" };

export function ipManager(given = API) {
  // A data file written before 2026-10-18 names no pause/resume/edit paths: the defaults fill them.
  const api = { ...API, ...given };
  const box = h("div", { class: "ipm" });
  const msg = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const list = h("div");
  const say = (text, ok = false) => { msg.textContent = text || ""; msg.className = `msg ${ok ? "ok" : "err"}`; };

  // One row: the address, its label, since when, Active / Paused (a switch), Edit and Delete.
  // A config-file entry always applies: it shows "Always on" and a lock, no switch.
  function row(e, entries, limit) {
    const tr = h("tr");
    const fixed = e.editable === false || e.source === "config";
    const since = e.added_at ? `added ${long(String(e.added_at).slice(0, 10))}` : fixed ? "config" : "";
    const state = h("td");
    const acts = h("td", { class: "n" });
    const redraw = (r, words) => { if (r.ok) { say(words, true); draw(r.entries || [], limit); } else say(r.error); };
    if (fixed) {
      state.append(h("span", { class: "muted" }, "Always on"));
      acts.append(h("span", { class: "lock", html: LOCK, title: "Set in the config file: it always applies and cannot be paused, edited or deleted here. Change it there." }, "locked"));
    } else {
      const on = e.active !== false;
      const sw = h("button", { type: "button", role: "switch", class: "ipm-sw", "aria-checked": String(on),
        "aria-label": `Count ${e.label} as our own traffic`,
        title: on ? "Active: its visits count as our own traffic. Turn off to pause." : "Paused: its visits count as visitors. Turn on to count them as ours again." },
      h("span", { class: "trk", "aria-hidden": "true" }),
      h("span", null, on ? "Active" : "Paused"),
      !on && e.paused_since ? h("span", { class: "when" }, `since ${tzTime(e.paused_since, { date: true })}`) : null);
      sw.addEventListener("click", async () => {
        sw.disabled = true;
        const r = await call(on ? api.pause : api.resume, { ip: e.ip });
        sw.disabled = false;
        redraw(r, on ? `Paused ${e.label}. From now on its visits count as visitors.` : `${e.label} is active again. From now on its visits count as our own traffic.`);
      });
      state.append(sw);
      const edit = h("button", { type: "button", class: "btn" }, "Edit");
      edit.setAttribute("aria-label", `Edit ${e.label}`);
      const del = h("button", { type: "button", class: "btn danger" }, "Delete");
      del.setAttribute("aria-label", `Delete ${e.label}`);
      edit.addEventListener("click", () => {
        const ipIn = h("input", { type: "text", class: "addr", value: e.ip, "aria-label": "Address or range", spellcheck: "false", autocomplete: "off" });
        const labelIn = h("input", { type: "text", value: e.label, "aria-label": "Label", maxlength: "60" });
        const save = h("button", { type: "button", class: "btn primary" }, "Save");
        const cancel = h("button", { type: "button", class: "btn" }, "Cancel");
        tr.replaceChildren(h("td", { class: "path" }, ipIn), h("td", null, labelIn),
          h("td", { class: "muted", colspan: "2" }, "The change applies from now on. Days before keep the old label and address."),
          h("td", { class: "n" }, h("span", { class: "acts" }, save, cancel)));
        labelIn.focus();
        cancel.addEventListener("click", () => draw(entries, limit));
        save.addEventListener("click", async () => {
          const body = { ip: e.ip };
          if (ipIn.value.trim() !== e.ip) body.new_ip = ipIn.value.trim();
          if (labelIn.value.trim() !== e.label) body.label = labelIn.value.trim();
          if (!body.new_ip && !body.label) { draw(entries, limit); return; }
          save.disabled = true;
          const r = await call(api.edit, body);
          save.disabled = false;
          redraw(r, `Saved. From now on it counts as ${body.label || e.label}.`);
        });
      });
      del.addEventListener("click", () => {
        const yes = h("button", { type: "button", class: "btn danger" }, "Yes, delete");
        const no = h("button", { type: "button", class: "btn" }, "Keep it");
        acts.replaceChildren(h("span", { class: "confirm" },
          `Delete ${e.label}? It stops applying to days not yet collected; stored days keep their figures. To stop it only for a while, pause it instead.`, yes, no));
        no.focus();
        no.addEventListener("click", () => draw(entries, limit));
        yes.addEventListener("click", async () => {
          yes.disabled = true;
          redraw(await call(api.remove, { ip: e.ip }), `Deleted ${e.label}. From now on its visits count as visitors.`);
        });
      });
      acts.append(h("span", { class: "acts" }, edit, del));
    }
    tr.append(h("td", { class: "path" }, copyIf("ip", e.ip || "", e.ip, { label: "address", cls: "" })), h("td", null, copyIf("text", e.label || "", null, { label: "label", cls: "" })), h("td", { class: "muted" }, since), state, acts);
    return tr;
  }

  function draw(entries, limit) {
    if (!entries.length) { list.replaceChildren(h("p", { class: "empty" }, installOnly() ? "No internal addresses yet." : "No internal addresses yet. Add this computer's address below.")); return; }
    list.replaceChildren(h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "Internal addresses"),
      h("thead", null, h("tr", null, h("th", { scope: "col" }, "Address or range"), h("th", { scope: "col" }, "Label"), h("th", { scope: "col" }, "Since"), h("th", { scope: "col" }, "Status"), h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Actions")))),
      h("tbody", null, entries.map((e) => row(e, entries, limit))))), limit ? h("p", { class: "note" }, `${entries.length} of at most ${limit} entries.`) : "");
    lockForInstall(list);
  }

  const mineLabel = h("input", { type: "text", placeholder: "e.g. Office Mac", "aria-label": "Label for this computer's address", maxlength: "60" });
  const mine = h("button", { type: "button", class: "btn primary" }, "Add my current address");
  mine.addEventListener("click", async () => {
    if (!mineLabel.value.trim()) { say("Give it a label first, so the list says whose address it is."); mineLabel.focus(); return; }
    mine.disabled = true;
    const r = await call(api.add_mine, { label: mineLabel.value.trim() });
    mine.disabled = false;
    if (r.ok) { say("Added this computer's address. Its visits count as our own traffic from now on.", true); mineLabel.value = ""; draw(r.entries || [], r.limit); } else say(r.error);
  });
  const ip = h("input", { type: "text", class: "addr", placeholder: "203.0.113.7 or 203.0.113.0/24", "aria-label": "Address or range", spellcheck: "false", autocomplete: "off" });
  const label = h("input", { type: "text", placeholder: "Label", "aria-label": "Label", maxlength: "60" });
  const form = h("form", null,
    h("label", null, "Address or range", ip), h("label", null, "Label", label),
    h("button", { type: "submit", class: "btn" }, "Add address"));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!ip.value.trim() || !label.value.trim()) { say("Both an address (or range) and a label are needed."); return; }
    const r = await call(api.add, { ip: ip.value.trim(), label: label.value.trim() });
    if (r.ok) { say(`Added ${ip.value.trim()}.`, true); ip.value = ""; label.value = ""; draw(r.entries || [], r.limit); } else say(r.error);
  });

  box.append(list,
    h("div", { style: { display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center", marginTop: "14px" } }, mineLabel, mine),
    form, msg,
    h("p", { class: "note" }, "Changes apply from now on. Days already counted are not recounted, so a past visit from a newly added address stays where it was counted. Pause an address while you test the site as a visitor, and turn it back on when you are done. Lines from the config file always apply and cannot be paused here."),
    howTo("internal-traffic", "How do I keep my team's own visits out of the figures?"));
  // With accounts the list itself is for admins (it holds addresses): a viewer is not asked for it.
  if (sessions() && isViewer()) {
    list.append(h("p", { class: "empty" }, "The address list is for admins: it holds the addresses of the people who work on the site."));
    return lockForViewer(box);
  }
  list.append(h("p", { class: "empty" }, "Loading the address list..."));
  call(api.list).then((r) => {
    if (r.ok && r.can_add === false) {
      // The server has nowhere to keep the list: say so instead of a form that is refused.
      draw(r.entries || [], r.limit);
      box.replaceChildren(list, h("p", { class: "note" }, "Adding addresses here is not set up on this server: it has no folder to keep the list in. Until it does, they are set in the config file."));
    } else if (r.ok) { draw(r.entries || [], r.limit); lockForViewer(box); lockForInstall(box); }
    else if (r.missing) {
      box.replaceChildren(h("p", { class: "empty" }, "Managing internal addresses here is coming: the server part is being added. Until then they are set in the config file."));
    } else { list.replaceChildren(); say(r.error); }
  });
  return lockForInstall(lockForViewer(box));
}

// Internal addresses: the addresses and ranges that count as our own traffic.
// Entries from the config file are locked here; the rest can be added and
// removed. The helper behind <page>/ours checks the password (nginx) and
// that the request came from this page; it never rewrites a stored day.

import { h, long } from "../ui.js";
import { lockForViewer, isViewer, sessions, ME } from "../access.js";
import { howTo } from "./help.js";
import { DEMO, DEMO_SAYS } from "../demo.js";

const LOCK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3.5" y="7" width="9" height="6.5" rx="1.5"/><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2"/></svg>';
const ERRORS = { 400: "That is not a valid address or range.", 403: "Refused: changes only work from this page.", 409: "The list is full. Remove an entry first." };

// With accounts (access.mode: sessions) every POST also carries the session's
// CSRF value, which the page reads from <page>/me. Without it nothing is sent.
let csrf = "";
export function setCsrf(value) { csrf = typeof value === "string" ? value : ""; }
export const csrfHeaders = () => (csrf ? { "X-Skald-CSRF": csrf } : {});

export async function call(path, body) {
  // The demo has no helper: nothing is asked or posted, and the caller shows why.
  if (DEMO.on) return { ok: false, demo: true, error: DEMO_SAYS };
  let res;
  try {
    res = await fetch(path, body ? { method: "POST", credentials: "same-origin", cache: "no-store", headers: { "Content-Type": "application/json", ...csrfHeaders() }, body: JSON.stringify(body) }
      : { credentials: "same-origin", cache: "no-store" });
  } catch {
    return { ok: false, error: "The server could not be reached." };
  }
  let data = null;
  try { data = await res.json(); } catch { /* not JSON: the helper does not answer this yet */ }
  if (!data) return { ok: false, missing: res.status === 404 || res.status === 405 || res.status === 502, error: `The address list is not available yet (${res.status}).` };
  if (!res.ok || !data.ok) return { ...data, ok: false, error: data.error || ERRORS[res.status] || `Refused (${res.status}).` };
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

export function ipManager(api = { list: "ours", add: "ours/add", remove: "ours/remove", add_mine: "ours/add-mine" }) {
  const box = h("div", { class: "ipm" });
  const msg = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const list = h("div");
  const say = (text, ok = false) => { msg.textContent = text || ""; msg.className = `msg ${ok ? "ok" : "err"}`; };

  function draw(entries, limit) {
    if (!entries.length) { list.replaceChildren(h("p", { class: "empty" }, installOnly() ? "No internal addresses yet." : "No internal addresses yet. Add this computer's address below.")); return; }
    const rows = entries.map((e) => {
      const cell = h("td", { class: "n" });
      if (e.editable === false || e.source === "config") cell.append(h("span", { class: "lock", html: LOCK, title: "Set in the config file; change it there" }, "locked"));
      else {
        const rm = h("button", { type: "button", class: "btn danger" }, "Remove");
        rm.setAttribute("aria-label", `Remove ${e.ip} (${e.label})`);
        rm.addEventListener("click", () => {
          const yes = h("button", { type: "button", class: "btn danger" }, "Yes, remove");
          const no = h("button", { type: "button", class: "btn" }, "Keep it");
          const ask = h("span", { class: "confirm" }, `Stop counting ${e.ip} as ours?`, yes, no);
          cell.replaceChildren(ask);
          no.focus();
          no.addEventListener("click", () => { draw(entries, limit); });
          yes.addEventListener("click", async () => {
            yes.disabled = true;
            const r = await call(api.remove, { ip: e.ip });
            if (r.ok) { say(`Removed ${e.ip}. From now on it counts as an ordinary visitor.`, true); draw(r.entries || [], limit); } else say(r.error);
          });
        });
        cell.append(rm);
      }
      return h("tr", null, h("td", { class: "path" }, e.ip), h("td", null, e.label || ""),
        h("td", { class: "muted" }, e.added_at ? `added ${long(String(e.added_at).slice(0, 10))}` : e.source === "config" ? "config" : ""), cell);
    });
    list.replaceChildren(h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "Internal addresses"),
      h("thead", null, h("tr", null, h("th", { scope: "col" }, "Address or range"), h("th", { scope: "col" }, "Label"), h("th", { scope: "col" }, "Since"), h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Action")))),
      h("tbody", null, rows))), limit ? h("p", { class: "note" }, `${entries.length} of at most ${limit} entries.`) : "");
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
    h("p", { class: "note" }, "Changes apply from now on. Days already counted are not recounted, so a past visit from a newly added address stays where it was counted."),
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

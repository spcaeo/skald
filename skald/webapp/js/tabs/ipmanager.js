// The helper's caller for every page (call): GET or POST <page>/<path>, with the session's
// CSRF value. The internal addresses' list itself is set-internal.js's (v2 rows); the helper
// behind <page>/ours checks the password (nginx) and that the request came from this page;
// it never rewrites a stored day.

import { isViewer, sessions, ME } from "../access.js";
import { DEMO, demoAnswer } from "../demo.js";

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

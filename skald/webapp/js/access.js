// Who is looking, and what they may change. The helper says (GET <page>/me):
// an admin may change internal addresses and funnels; a viewer reads only, and
// sees those controls disabled with a reason. A server without /me (before
// release 3) is never asked, and everyone there keeps today's controls.
//
// With accounts (access.mode: sessions) /me also gives the name, the org, the
// mode and the CSRF value every POST must carry; Settings then shows Team and
// Your account instead of Users. In basic mode nothing changes.

import { call, setCsrf, csrfHeaders } from "./tabs/ipmanager.js";
import { HIDDEN, ACCOUNT_TABS } from "./state.js";
import { DEMO } from "./demo.js";

export const ME = { user: null, role: null, name: null, org: null, mode: "basic", install_admin: false, totp_on: false, saas: false, plan: null, update: null };
export const VIEWER = "Only an admin can change this. You are signed in as a viewer.";
export const isViewer = () => ME.role === "viewer";
export const sessions = () => ME.mode === "sessions";

export async function loadMe(model) {
  // The demo has no helper to ask: every settings page is in the menu, each saying it needs one.
  if (DEMO.on) {
    HIDDEN.clear();
    ["settings/users", "settings/billing"].forEach((k) => HIDDEN.add(k));
    return ME;
  }
  if (!model?.x?.funnels) return ME;
  const r = await call("me");
  if (r.ok && r.role) {
    ME.user = r.user || null; ME.role = r.role;
    ME.name = r.name || null; ME.org = r.org || null;
    ME.mode = r.mode === "sessions" ? "sessions" : "basic";
    ME.install_admin = !!r.install_admin; ME.totp_on = !!r.totp_on;
    ME.saas = !!r.saas; ME.plan = r.plan || null;          // saas: the plan and its banner
    ME.update = r.update || null;                          // a newer release (owners, admins)
    setCsrf(r.csrf);
  }
  HIDDEN.clear();
  if (sessions()) HIDDEN.add("settings/users");
  else ACCOUNT_TABS.forEach((k) => HIDDEN.add(k));
  if (!ME.saas || ME.role !== "owner") HIDDEN.add("settings/billing");
  // What the reader's role cannot open stays out of the menu, the palette and the reports.
  if (ME.role !== "owner") HIDDEN.add("settings/security");
  if (isViewer()) ["settings/users", "settings/integrations", "settings/audit"].forEach((k) => HIDDEN.add(k));
  return ME;
}

// Disable every control under `root` for a viewer, saying why on hover and to a screen reader.
export function lockForViewer(root) {
  if (!isViewer() || !root) return root;
  root.querySelectorAll("button, input, select, textarea").forEach((el) => {
    el.disabled = true;
    el.title = VIEWER;
  });
  if (!root.querySelector(".viewer-note")) root.prepend(Object.assign(document.createElement("p"), { className: "note viewer-note", textContent: VIEWER }));
  return root;
}

// Sign out of this browser: the helper ends the session and clears the cookie.
export async function signOut() {
  try {
    await fetch("/traffic-auth/logout", { method: "POST", credentials: "same-origin", cache: "no-store", redirect: "manual", headers: csrfHeaders() });
  } catch { /* the sign-in page is the next stop either way */ }
  location.assign("/traffic-auth/login");
}

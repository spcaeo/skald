// Settings > Your account (accounts, access.mode: sessions): your name, your
// password, two-step sign-in and where you are signed in. Everyone has this
// page, viewers too: it changes only your own account. Passwords go in a POST
// body and nowhere else; the recovery codes are shown once and never kept here.

import { h, toast } from "../ui.js";
import { call } from "./ipmanager.js";
import { download } from "../table.js";
import { ME, sessions, signOut } from "../access.js";
import { head1, copyable, field, input, status, when, why, passwordProblem, POLICY } from "./forms.js";
import { copyIf } from "../urlactions.js";

const pw = (auto) => input({ type: "password", autocomplete: auto, required: true, maxlength: "1024" });
const card = (title, sub, ...body) => h("section", { class: "sheet acct-card" }, h("h2", null, title), sub ? h("p", { class: "sub" }, sub) : null, ...body);

// "Firefox on Mac" from a user agent; the raw string when nothing matches.
function device(agent) {
  if (!agent) return "Device not recorded";
  const b = /Edg\//.test(agent) ? "Edge" : /Firefox\//.test(agent) ? "Firefox" : /Chrome\//.test(agent) ? "Chrome" : /Safari\//.test(agent) ? "Safari" : "";
  const os = /iPhone|iPad/.test(agent) ? "iPhone or iPad" : /Android/.test(agent) ? "Android" : /Mac OS X|Macintosh/.test(agent) ? "Mac" : /Windows/.test(agent) ? "Windows" : /Linux/.test(agent) ? "Linux" : "";
  return b && os ? `${b} on ${os}` : b || os || agent;
}

function nameCard(acc) {
  const name = input({ name: "name", value: acc.name || "", autocomplete: "name", maxlength: "100" });
  const msg = status();
  const save = h("button", { type: "submit", class: "btn primary" }, "Save name");
  const form = h("form", { class: "af-row", novalidate: true }, field("Name", name), save);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!name.value.trim()) { msg.say("Type a name first."); name.focus(); return; }
    save.disabled = true;
    const r = await call("account/name", { name: name.value.trim() });
    save.disabled = false;
    if (r.ok) { ME.name = name.value.trim(); msg.say("Saved.", true); } else msg.say(why(r));
  });
  return card("You", null, h("p", { class: "u-me" }, "Signed in as ", h("b", null, acc.email || ME.user || ""), ME.role ? ` (${ME.role})` : ""), form, msg);
}

function passwordCard() {
  const cur = pw("current-password"), next = pw("new-password"), again = pw("new-password");
  const msg = status();
  const save = h("button", { type: "submit", class: "btn primary" }, "Change password");
  const form = h("form", { class: "af-col", novalidate: true }, field("Current password", cur), field("New password", next, POLICY), field("New password again", again), h("div", null, save));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!cur.value) { msg.say("Type your current password first."); cur.focus(); return; }
    const bad = passwordProblem(next.value, again.value);
    if (bad) { msg.say(bad); next.focus(); return; }
    save.disabled = true;
    const r = await call("account/password", { current: cur.value, new: next.value });
    save.disabled = false;
    cur.value = ""; next.value = ""; again.value = "";
    if (r.ok) msg.say("Password changed. Your other sessions may ask you to sign in again.", true); else msg.say(why(r));
  });
  return card("Password", null, form, msg);
}

// What is on screen once (the new key, the recovery codes) survives a redraw of the tab,
// in this page's memory only, until it is confirmed or put away.
let pending = null;

// Two-step sign-in: off -> start (secret and otpauth address) -> confirm with a code -> recovery codes, once.
function twoStepCard(acc) {
  const body = h("div");
  const msg = status();
  const sec = card("Two-step sign-in", "A 6-digit code from an app on your phone (any authenticator app), asked after your password.", body, msg);

  const drawOff = () => {
    const pass = pw("current-password");
    const start = h("button", { type: "submit", class: "btn primary" }, "Turn on two-step sign-in");
    const form = h("form", { class: "af-row", novalidate: true }, field("Your password, to turn it on", pass), start);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!pass.value) { msg.say("Type your password first."); pass.focus(); return; }
      start.disabled = true;
      const r = await call("account/totp/start", { password: pass.value });
      start.disabled = false;
      pass.value = "";
      if (r.ok && r.secret) drawSetup(r); else msg.say(why(r));
    });
    body.replaceChildren(h("p", null, "Two-step sign-in is ", h("b", null, "off"), "."), form);
  };

  const drawSetup = (r) => {
    const code = input({ inputmode: "numeric", autocomplete: "one-time-code", pattern: "[0-9]{6}", maxlength: "6", required: true, class: "code-in" });
    const ok = h("button", { type: "submit", class: "btn primary" }, "Confirm");
    const back = h("button", { type: "button", class: "btn" }, "Cancel");
    pending = { setup: r };
    back.addEventListener("click", () => { pending = null; msg.say(""); drawOff(); });
    const form = h("form", { class: "af-row", novalidate: true }, field("Code from the app", code), ok, back);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const c = code.value.replace(/\s+/g, "");
      if (!/^\d{6}$/.test(c)) { msg.say("Type the 6 digits the app shows."); code.focus(); return; }
      ok.disabled = true;
      const res = await call("account/totp/confirm", { code: c });
      ok.disabled = false;
      if (res.ok) { msg.say("Two-step sign-in is on.", true); ME.totp_on = true; drawCodes(Array.isArray(res.recovery_codes) ? res.recovery_codes : []); } else { msg.say(why(res)); code.select(); }
    });
    const grouped = String(r.secret).replace(/\s+/g, "").replace(/(.{4})/g, "$1 ").trim();
    body.replaceChildren(
      h("ol", { class: "steps" },
        h("li", null, "In your authenticator app, add an account and choose to type a key. Use this key (time based, 6 digits):", copyable(grouped, "the key")),
        h("li", null, "Or, if your app takes an address, use this one:", r.uri ? copyable(r.uri, "the otpauth address") : null),
        h("li", null, "Type the code the app shows, to check it works.")),
      form);
    code.focus();
  };

  const drawCodes = (codes) => {
    pending = { codes };
    const text = `${ME.org ? `${ME.org}: ` : ""}recovery codes for ${acc.email || ME.user || "your account"}\nEach works once, in place of a code from the app.\n\n${codes.join("\n")}\n`;
    const copy = h("button", { type: "button", class: "btn" }, "Copy all");
    copy.addEventListener("click", async () => { try { await navigator.clipboard.writeText(text); copy.textContent = "Copied"; } catch { copy.textContent = "Select and copy"; } });
    const save = h("button", { type: "button", class: "btn" }, "Download as text");
    save.addEventListener("click", () => download("skald-recovery-codes.txt", text, "text/plain;charset=utf-8"));
    const done = h("button", { type: "button", class: "btn primary" }, "I have saved them");
    done.addEventListener("click", () => { pending = null; msg.say(""); drawOn(); });
    body.replaceChildren(
      h("div", { class: "state warn", role: "alert" }, h("div", null, h("strong", null, "Save these 10 recovery codes now. "), "They are shown only this once. If you lose your phone, each one lets you sign in once.")),
      h("ol", { class: "rcodes", "aria-label": "Recovery codes" }, codes.map((c) => h("li", null, h("code", null, c)))),
      h("div", { class: "acts" }, copy, save, done));
    done.focus();
  };

  const drawOn = () => {
    const pass = pw("current-password");
    const off = h("button", { type: "submit", class: "btn danger" }, "Turn off");
    const form = h("form", { class: "af-row", novalidate: true }, field("Your password, to turn it off", pass), off);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!pass.value) { msg.say("Type your password first."); pass.focus(); return; }
      off.disabled = true;
      const r = await call("account/totp/off", { password: pass.value });
      off.disabled = false;
      pass.value = "";
      if (r.ok) { ME.totp_on = false; msg.say("Two-step sign-in is off.", true); drawOff(); } else msg.say(why(r));
    });
    body.replaceChildren(h("p", null, "Two-step sign-in is ", h("b", null, "on"), ". Signing in asks for a code from your app, or a recovery code."), form);
  };

  if (pending?.codes) drawCodes(pending.codes);
  else if (pending?.setup && !acc.totp_on) drawSetup(pending.setup);
  else if (acc.totp_on) drawOn(); else drawOff();
  return sec;
}

function sessionsCard(acc) {
  const list = acc.sessions || [];
  const msg = status();
  const others = list.filter((s) => !s.current).length;
  const rows = list.map((s) => h("tr", null,
    h("td", null, copyIf("ua", device(s.agent), s.agent || "", { label: "user agent", cls: "ua-after" }), s.current ? h("span", { class: "you" }, " (this browser)") : null),
    h("td", { class: "muted n" }, when(s.created_at, "")), h("td", { class: "muted n" }, when(s.last_seen, ""))));
  const all = h("button", { type: "button", class: "btn danger" }, "Sign out everywhere else");
  const slot = h("div", { class: "acts" }, all);
  const reset = () => slot.replaceChildren(all);
  all.addEventListener("click", () => {
    const yes = h("button", { type: "button", class: "btn danger" }, "Yes, sign them out");
    const no = h("button", { type: "button", class: "btn" }, "Cancel");
    no.addEventListener("click", reset);
    yes.addEventListener("click", async () => {
      yes.disabled = true;
      const r = await call("account/signout-all", {});
      if (r.ok) { toast("Every other session is signed out."); load(); } else { msg.say(why(r)); reset(); }
    });
    slot.replaceChildren(h("span", { class: "confirm" }, "Sign out every other browser and device?", yes, no));
    no.focus();
  });
  const me = h("button", { type: "button", class: "btn" }, "Sign out of this browser");
  me.addEventListener("click", signOut);
  return card("Where you are signed in", "A session lasts 14 days from its last use.",
    list.length ? h("div", { class: "scroll" }, h("table", null, h("caption", { class: "vh" }, "Your sessions"),
      h("thead", null, h("tr", null, [["Browser"], ["Signed in", "n"], ["Last seen", "n"]].map(([t, cls]) => h("th", { scope: "col", class: cls }, t)))), h("tbody", null, rows)))
      : h("p", { class: "empty" }, "No sessions listed."),
    h("div", { class: "acts" }, others || !list.length ? slot : null, me), msg);
}

let box = null;
function load() {
  call("account").then((r) => {
    if (!box) return;
    if (!r.ok) { box.replaceChildren(h("div", { class: "state" }, h("div", null, why(r, "Your account could not be loaded.")))); return; }
    box.replaceChildren(h("div", { class: "cols tops" }, nameCard(r), passwordCard()), h("div", { class: "cols tops" }, twoStepCard(r), sessionsCard(r)));
  });
}

export default function account() {
  const title = head1("Your account", "Your name, password, two-step sign-in and sessions.");
  if (!sessions()) {
    return [title, h("div", { class: "state" }, h("div", null, "Your account comes with accounts. This server uses one shared login, set on the server; see ",
      h("a", { href: "#settings/users" }, "Settings > Users"), "."))];
  }
  box = h("div", { class: "acct" }, h("p", { class: "empty" }, "Loading your account..."));
  load();
  return [title, box];
}

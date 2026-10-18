// Small pieces the Settings pages share: a page head, a copy row, a labelled
// field, a status line, a two-step "are you sure", and a moment as words.
// Every value from the server goes in as text, never as markup.

import { h } from "../ui.js";
import { ago as tzAgo } from "../tz.js";

export const POLICY = "At least 12 characters. Not your email address, and not a common password.";
export const MIN_PASSWORD = 12;

// A settings page's head: its title, shown (the data pages leave theirs to the
// top bar), and one sentence under it saying what the page is for.
export function head1(title, lede) {
  return h("div", { class: "page-head" }, h("div", { class: "head" }, h("h1", null, title)), lede ? h("p", { class: "lede" }, lede) : null);
}

export function copyable(text, label) {
  const btn = h("button", { type: "button", class: "btn cp", "aria-label": `Copy ${label}` }, "Copy");
  btn.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(text); btn.textContent = "Copied"; } catch { btn.textContent = "Select and copy"; }
    setTimeout(() => { btn.textContent = "Copy"; }, 1600);
  });
  return h("div", { class: "cp-row" }, h("code", null, text), btn);
}

// A label around its control, so the words name it for a screen reader too.
export function field(label, control, hint) {
  const secret = control?.tagName === "INPUT" && control.type === "password";
  const words = h("span", null, label);
  if (secret) {   // named by these words only, not "... Show" from the button beside it
    words.id = `f-${Math.random().toString(36).slice(2, 9)}`;
    control.setAttribute("aria-labelledby", words.id);
  }
  return h("label", { class: "af" }, words, secret ? withShow(control) : control, hint ? h("small", null, hint) : null);
}

// A Show / Hide button inside a password field's right edge. The field goes
// back to hidden when its form is sent.
export function withShow(field) {
  const btn = h("button", { type: "button", class: "pw-toggle", "aria-pressed": "false", "aria-label": "Show password" }, "Show");
  const set = (shown) => {
    field.type = shown ? "text" : "password";
    btn.textContent = shown ? "Hide" : "Show";
    btn.setAttribute("aria-pressed", String(shown));
    btn.setAttribute("aria-label", shown ? "Hide password" : "Show password");
  };
  btn.addEventListener("click", (e) => { e.preventDefault(); set(field.type === "password"); field.focus(); });
  queueMicrotask(() => field.form?.addEventListener("submit", () => set(false), true));
  return h("span", { class: "pw" }, field, btn);
}

export function input(attrs) {
  return h("input", { type: "text", spellcheck: "false", ...attrs });
}

// A polite status line under a form: say(text) for a refusal, say(text, true) for done.
export function status() {
  const el = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  el.say = (text, ok = false) => { el.textContent = text || ""; el.className = `msg ${ok ? "ok" : "err"}`; };
  return el;
}

// Replace `cell`'s contents with a question and two buttons; `redraw` puts it back.
export function confirmIn(cell, question, yesText, onYes, redraw) {
  const yes = h("button", { type: "button", class: "btn danger" }, yesText);
  const no = h("button", { type: "button", class: "btn" }, "Keep it");
  cell.replaceChildren(h("span", { class: "confirm" }, question, yes, no));
  no.focus();
  no.addEventListener("click", redraw);
  yes.addEventListener("click", async () => { yes.disabled = true; no.disabled = true; await onYes(); });
}

// "3 h ago (11 Oct 14:05 EDT)" in the chosen zone (tz.js, the one date family); an empty value is "never".
export function when(ts, never = "never") {
  return Date.parse(ts || "") ? tzAgo(ts) : never;
}

// The words a refused change shows: the server's own, else a plain fallback.
export const why = (r, fallback = "That did not work.") => (r.missing ? "The server does not offer this yet." : r.error || fallback);

// The two new-password boxes agree and meet the length rule; "" when fine.
export function passwordProblem(pw, again) {
  if (pw.length < MIN_PASSWORD) return `The new password is too short: it needs at least ${MIN_PASSWORD} characters.`;
  if (pw !== again) return "The two new passwords are not the same.";
  return "";
}

export const ROLE_NAME = { owner: "Owner", admin: "Admin", viewer: "Viewer" };

// What the "Set up this site" dialogs share (setup-dialogs.js and setup-*.js):
// a choice of ways drawn like Settings > Collect data > Send logs' (cn-ways), a mail to the
// developer or the server admin (a mailto: link: the reader's own mail program
// sends it, Skald sends nothing), a Copy button for a block of words, and the
// fold with the technical words for whoever runs the server.

import { h, toast } from "../ui.js";

// The doctor's text as written, a command between backticks as <code>.
const codeSpans = (text) => String(text).split("`").map((part, i) => (i % 2 ? h("code", null, part) : part)).filter((x) => x !== "");
export function adminFold(tech, summary = "For your server admin") {
  if (!tech) return null;
  const body = typeof tech === "string" ? tech.split("\n").map((line) => h("p", null, ...codeSpans(line))) : tech;
  return h("details", { class: "fold su-tech" }, h("summary", null, summary), body);
}

// A mailto: address. Line breaks as CRLF, as RFC 6068 asks; everything encoded.
export function mailtoHref({ to = "", subject = "", body = "" }) {
  const q = [subject ? `subject=${encodeURIComponent(subject)}` : "", body ? `body=${encodeURIComponent(String(body).replace(/\r?\n/g, "\r\n"))}` : ""].filter(Boolean).join("&");
  return `mailto:${encodeURIComponent(to).replace(/%40/g, "@")}${q ? `?${q}` : ""}`;
}

// "Send these steps to your developer": a link that opens the reader's mail program.
export function mailButton(words, mail) {
  return h("a", { class: "btn primary su-mail", href: mailtoHref(mail) }, words);
}

// A Copy button for words that are not shown as a block (the steps of a mail).
export function copyButton(words, text, label) {
  const btn = h("button", { type: "button", class: "btn", "aria-label": `Copy ${label}` }, words);
  btn.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(typeof text === "function" ? text() : text); toast(`Copied ${label}`); } catch { toast("Copy is not allowed here; select the text instead"); }
  });
  return btn;
}

/* Radio cards: [{id, title, sub}], the one chosen in st[key]; onPick(id) after a change. */
export function choices(st, key, list, legend, onPick = null) {
  const name = `su-${key}-${Math.random().toString(36).slice(2, 8)}`;
  return h("fieldset", { class: "cn-ways" }, h("legend", { class: "vh" }, legend),
    list.map((x) => {
      const radio = h("input", { type: "radio", name, value: x.id });
      radio.checked = st[key] === x.id;
      radio.addEventListener("change", () => { st[key] = x.id; if (onPick) onPick(x.id); });
      return h("label", { class: "cn-way" }, radio, h("span", null, h("b", null, x.title, x.best ? h("em", null, " Recommended") : null), x.sub ? h("small", null, x.sub) : null));
    }));
}

// A loading line, then the answer of `load()` drawn by `draw(answer)`.
export function loading(words, load, draw) {
  const box = h("div", null, h("p", { class: "empty" }, words));
  load().then((r) => box.replaceChildren(...[].concat(draw(r) || [])));
  return box;
}

// The steps as plain text, numbered, for a mail or the clipboard.
export const numbered = (lines) => lines.filter(Boolean).map((l, i) => `${i + 1}. ${l}`).join("\n");

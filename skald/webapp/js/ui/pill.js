// Status pills (2.41, docs/UI-RULES.md rule 13): one look for every status in the app, a
// dot and a word on a soft tint of its colour. Five kinds only:
//
//   good   working, live, done, closed         (--good)
//   warn   waiting, worth a look, re-checking  (--warn)
//   bad    broken, urgent, not answering       (--bad)
//   off    off, paused, not set up             (--ink-3 on --sunk)
//   info   new, tracked, compared              (--g-people)
//
//   pill(kind, words, { title })  -> <span class="ui-pill <kind>">words</span>
//   kindOf(state)                 -> the kind for a state word Skald already uses

import { h } from "../ui.js";

export const KINDS = ["good", "warn", "bad", "off", "info"];
const STATES = {
  good: ["good", "ok", "done", "working", "live", "on", "closed", "active", "connected", "fixed"],
  warn: ["warn", "waiting", "wait", "todo", "pending", "medium", "worth", "stale", "late", "rechecking"],
  bad: ["bad", "broken", "error", "failed", "high", "urgent", "down", "open", "exposed"],
  off: ["off", "paused", "unknown", "not set up", "never", "none", "disabled"],
  info: ["info", "low", "new", "tracked"],
};
const BY = new Map(Object.entries(STATES).flatMap(([k, v]) => v.map((w) => [w, k])));

/* A state word (a severity, an item's state) as a pill kind; "off" for one it does not know. */
export const kindOf = (state) => BY.get(String(state ?? "").trim().toLowerCase()) || "off";

export function pill(kind, words, { title = null } = {}) {
  const k = KINDS.includes(kind) ? kind : kindOf(kind);
  return h("span", { class: `ui-pill ${k}`, title }, words);
}

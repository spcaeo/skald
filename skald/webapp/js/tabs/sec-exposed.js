// Security > Is anything exposed? (2.21): every scanner probe the server answered 2xx, each
// set against its host's own fallback page (what it sends for any path it does not have) (security.py). The verdict at the top in
// one line: nothing exposed, N possible exposures to check now, or can't tell (no size).
//
//   sxv   Show: "" both possible and can't tell, "possible", "nosize" (can't tell)
//
// The log records a size, never the content: a size unlike the shell is a reason to look,
// never proof of a leak, and a size like it is no proof of safety. The (i) says so.

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { table } from "../table.js";
import { tiles } from "./tiles.js";
import { optionsRow, choice, emptyState } from "./sa-options.js";
import { verdictOf } from "../sec-data.js";
import { secTab, at, adviceOf, LOOKED, missingNote } from "./sec-common.js";

export const HELP_TEXT = "Skald reads each probe's status and the size of the answer from the log. A single-page app or a default server page answers every path it does not have with the same page (its fallback page), so a 2xx with that size is harmless. A 2xx of another size may be a real file: check it. The log never shows the content, so this is a reason to look, not proof; and the size is the size sent after compression, so the same page can show as two sizes through two doors (the host name and the bare IP). Each host has its own.";

const SHOW = [["", "Both"], ["possible", "Possible exposures"], ["nosize", "Can't tell"]];
const VERDICT = { possible: "possible", nosize: "unknown" };     // the address's word -> the file's

export function why(row) {
  if (row.verdict === "unknown") return "The log has no size for this answer, so Skald cannot tell a page from a file.";
  if (row.shell_size == null) return `${n(row.size)} bytes, and no other probe path on ${row.host} got a page that day: nothing harmless to compare with.`;
  return `${n(row.size)} bytes; this host's fallback page is ${n(row.shell_size)} bytes.`;
}

/* The verdict banner: the first thing the tab says. */
export function banner(t) {
  const v = verdictOf(t);
  const e = t.exposure;
  const sub = {
    ok: e.answered ? `${n(e.answered)} probe${e.answered === 1 ? " was" : "s were"} answered with a page; every one was the host's harmless fallback page${e.empty ? " or empty" : ""}.`
      : `${n(t.probes)} scanner probe${t.probes === 1 ? "" : "s"}, none answered with a page (2xx).`,
    bad: "Each is a 2xx answer with a size unlike the host's harmless page. Open the path yourself and check what it returns.",
    warn: "The log records no response size for these, so Skald cannot tell a page from a file. Add the body size ($body_bytes_sent) to the log format.",
    none: "Security is counted from 2.21 on, for days the raw log still held.",
  }[v.tone];
  return h("div", { class: `sec-verdict ${v.tone}`, role: v.tone === "bad" ? "alert" : "status" },
    h("span", { class: "sec-v-mark", "aria-hidden": "true" }, v.tone === "ok" ? "✓" : v.tone === "none" ? "–" : "!"),
    h("div", null, h("strong", null, v.words), h("p", null, sub)));
}

function rowsTable(t, s) {
  const rows = t.exposure.rows.filter((r) => !VERDICT[s.sxv] || r.verdict === VERDICT[s.sxv]);
  return table([
    { key: "at", label: "When", type: "date", fmt: (v) => at(v) },
    { key: "host", label: "Host", fmt: (v, r) => h("span", null, v || "(no host)", r.host && /^[\d.:[\]]+$/.test(r.host) ? h("span", { class: "sec-tag" }, "bare IP") : "") },
    { key: "path", label: "Path", path: true },
    { key: "status", label: "Status" },
    { key: "size", label: "Size (bytes)", num: true, fmt: (v) => (v == null ? "Not recorded" : n(v)) },
    { key: "verdict", label: "Why it is listed", fmt: (v, r) => why(r), sort: (r) => r.verdict },
    { key: "category", label: "What to do", fmt: (v) => { const [words, code] = adviceOf(v); return h("span", null, words, code ? h("code", { class: "sec-code" }, code) : ""); }, csv: (r) => adviceOf(r.category).join(" ") },
  ], { caption: "Possible exposures", ns: "sx", file: "possible-exposures.csv", rows, sortKey: "at", dir: -1, limit: 20,
    empty: s.sxv === "nosize" ? "No answer without a size." : "No possible exposure in this period." });
}

function hostsTable(t) {
  const rows = Object.values(t.exposure.hosts);
  return table([
    { key: "host", label: "Host", fmt: (v) => v || "(no host)" },
    { key: "bare_ip", label: "Sent to", fmt: (v) => (v ? "the bare IP" : "the site's name"), csv: (r) => (r.bare_ip ? "bare IP" : "host name") },
    { key: "answered", label: "Answered 2xx", num: true },
    { key: "sizes", label: "Its fallback page", fmt: (v) => (v?.length ? v.map((x) => `${n(x)} bytes`).join(", ") : "None found"), sort: (r) => r.sizes?.[0] ?? -1, csv: (r) => (r.sizes || []).join(" ") },
    { key: "shell", label: "Harmless", num: true },
    { key: "empty", label: "Empty", num: true, hide: true },
    { key: "possible", label: "Possible", num: true },
    { key: "unknown", label: "Can't tell", num: true },
  ], { caption: "Each host's answers", ns: "sxh", file: "answers-by-host.csv", rows, sortKey: "answered", dir: -1, search: false, limit: 12,
    empty: "No probe was answered with a page." });
}

/* An alert's link (#threats/exposed?item=<id>): the item it names, first, wherever it is in the
   file's days; or a line that it is no longer listed. */
export function itemPart(f, s) {
  if (!s.item) return null;
  const all = [...(f.days || []).map((d) => [d.day, d.security]), [f.today ? "today" : null, f.today?.security]];
  for (const [day, b] of all) {
    const row = (b?.exposure?.rows || []).find((r) => r.item === s.item);
    if (row) {
      const [words, code] = adviceOf(row.category);
      return h("div", { class: "sec-verdict bad sec-item", role: "alert" }, h("span", { class: "sec-v-mark", "aria-hidden": "true" }, "!"),
        h("div", null, h("strong", null, `From your alert: ${row.host}${row.path}`),
          h("p", null, `${at(row.at)}: answered ${row.status} with ${row.size == null ? "no recorded size" : `${n(row.size)} bytes`}. ${why(row)}`),
          h("p", null, words, code ? h("code", { class: "sec-code" }, code) : "")));
    }
  }
  return h("p", { class: "note sec-item" }, "The item in this link is no longer listed: the answer it named has left the days this page keeps.");
}

export default function exposed(m, s) {
  return secTab(m, s, {
    title: "Is anything exposed?",
    question: "Did the server hand a scanner a real file? Every probe answered with a page, set against the host's own harmless page.",
    help: HELP_TEXT,
    draw: ({ f, t, p }) => {
      const e = t.exposure;
      const parts = [itemPart(f, s), banner(t)];
      if (!t.days) return [...parts, missingNote(p, t)];
      parts.push(tiles([
        { label: "Scanner probes", value: t.probes, info: "Requests for paths no real site serves (.env, wp-login.php, phpinfo.php, ...) or with attack strings in the query, filed under bots. Each request stays in its group: Security is a view across them." },
        { label: "Answered with a page", value: e.answered, info: "Probes the server answered 2xx." },
        { label: "Harmless page", value: e.shell + e.empty, info: "The host's fallback page (what it sends for any path it does not have), or an empty body." },
        { label: "Possible exposures", value: e.possible, info: "A 2xx with a size unlike the host's harmless page." },
        { label: "Can't tell", value: e.unknown, info: "A 2xx whose line has no size: never called safe." },
      ]));
      parts.push(...optionsRow("Show", [choice("Show", s.sxv || "", SHOW, (v) => S.set({ sxv: v }))], {
        notes: [`A probe is filed by what it looked for: ${Object.values(LOOKED).join(", ")}.`] }));
      if (e.possible || e.unknown) parts.push(rowsTable(t, s));
      else parts.push(emptyState(e.answered ? "Every probe answered with a page got the host's harmless page." : "No probe was answered with a page in this period."));
      if (e.folded) parts.push(h("p", { class: "note" }, `${n(e.folded)} more such answers are counted above but not listed (each day lists 200).`));
      parts.push(h("h2", { class: "sec-h2" }, "Each host's answers"), hostsTable(t), missingNote(p, t));
      return parts;
    },
  });
}

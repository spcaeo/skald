// Security > Is anything exposed? (2.21): every scanner probe the server answered 2xx, each
// set against its host's own fallback page (what it sends for any path it does not have) (security.py). The verdict at the top in
// one line: nothing exposed, N possible exposures to check now, or can't tell (no size).
//
//   sxv   Show: "" both possible and can't tell, "possible", "nosize" (can't tell)
//
// 2.42 (the UX audit, answer first): the verdict, with the screen's one primary button when
// there is a possible exposure (Fix, fixit=exposed: Me or My developer, tabs/fixit.js); the
// figures and the list; each host's answers under a fold kept in the address (sxx_view=open).
//
// The log records a size, never the content: a size unlike the shell is a reason to look,
// never proof of a leak, and a size like it is no proof of safety. The (i) says so.
//
// SKALD-59: exposure rule 3 calls a static file, the site's own cron call and an answer
// the size of the home page harmless (counted under "Harmless page"); an owner or admin marks
// a possible exposure "Not a problem" (security_marks.py), on a row or from the alert's link:
// the verdict leaves it out while the answer stays the same, and "Check it again" takes it back.

import { h, n, toast } from "../ui.js";
import * as S from "../state.js";
import { table } from "../table.js";
import { tiles } from "./tiles.js";
import { optionsRow, choice, emptyState } from "./sa-options.js";
import { verdictOf, applyMarks, harmlessOf } from "../sec-data.js";
import { copyIf } from "../urlactions.js";
import { secTab, at, adviceOf, LOOKED, missingNote, keepMarks } from "./sec-common.js";
import { call } from "./ipmanager.js";
import { primary } from "../ui/primary.js";
import { urlFold } from "../ui/fold.js";

export const HELP_TEXT = "Skald reads each probe's status and the size of the answer from the log. A single-page app or a default server page answers every path it does not have with the same page (its fallback page), so a 2xx with that size is harmless. So are an image, stylesheet, script or font, WordPress calling its own cron, and an answer the size of the host's home page. A 2xx of another size may be a real file: check it. The log never shows the content, so this is a reason to look, not proof; and the size is the size sent after compression, so the same page can show as two sizes through two doors (the host name and the bare IP). Each host has its own. An owner or admin who has checked one can mark it Not a problem: it stays off the alerts while the path is answered the same way.";

const SHOW = [["", "Both"], ["possible", "Possible exposures"], ["nosize", "Can't tell"]];
const VERDICT = { possible: "possible", nosize: "unknown" };     // the address's word -> the file's

export function why(row) {
  if (row.marked) return `Marked not a problem${row.marked.by ? ` by ${row.marked.by}` : ""} on ${at(row.marked.marked_at)}. It is judged again if the answer changes.`;
  if (row.verdict === "unknown") return "The log has no size for this answer, so Skald cannot tell a page from a file.";
  if (row.shell_size == null) return `${n(row.size)} bytes, and no other probe path on ${row.host} got a page that day: nothing harmless to compare with.`;
  return `${n(row.size)} bytes; this host's fallback page is ${n(row.shell_size)} bytes.`;
}

/* The verdict banner: the first thing the tab says. fix: the screen's one primary button,
   given only when there is something to fix (a possible exposure). */
export function banner(t, fix = null) {
  const v = verdictOf(t);
  const e = t.exposure;
  const sub = {
    ok: e.marked ? `${n(e.marked)} answer${e.marked === 1 ? " was" : "s were"} checked and marked not a problem by an owner or admin; every other answer was harmless.`
      : e.answered ? `${n(e.answered)} probe${e.answered === 1 ? " was" : "s were"} answered with a page; every one was harmless (the host's fallback page, an empty body, a static file, the site's own call or its home page).`
      : `${n(t.probes)} scanner probe${t.probes === 1 ? "" : "s"}, none answered with a page (2xx).`,
    bad: "Each is a 2xx answer with a size unlike the host's harmless page. Open the path yourself and check what it returns.",
    warn: "The log records no response size for these, so Skald cannot tell a page from a file. Add the body size ($body_bytes_sent) to the log format.",
    none: "Security is counted from 2.21 on, for days the raw log still held.",
  }[v.tone];
  return h("div", { class: `sec-verdict ${v.tone}`, role: v.tone === "bad" ? "alert" : "status" },
    h("span", { class: "sec-v-mark", "aria-hidden": "true" }, v.tone === "ok" ? "✓" : v.tone === "none" ? "–" : "!"),
    h("div", null, h("strong", null, v.words), h("p", null, sub)), fix ? h("span", { class: "sec-v-act" }, fix) : null);
}

/* "Not a problem" or "Check it again" on a possible exposure, for an owner or admin. */
const MAY = ["owner", "admin"];
export function markButton(row, mk) {
  if (!mk || !MAY.includes(mk.role) || row.verdict !== "possible" || !row.item) return null;
  const undo = !!row.marked;
  const send = () => call("settings/security-mark", undo ? { item: row.item, undo: true } : { item: row.item, status: String(row.status), size: row.size ?? null })
    .then((r) => {
      if (!r.ok) return toast(r.error || "Not saved.");
      keepMarks(r.marks, mk.role);
      toast(undo ? "It is checked again from the next run." : "Marked not a problem. It comes back if the answer changes.");
      S.emit(true);
    });
  return h("button", { type: "button", class: "btn", onclick: send, "aria-label": `${undo ? "Check again" : "Mark not a problem"}: ${row.host}${row.path}` }, undo ? "Check it again" : "Not a problem");
}

// The Fix: "Who will do it?", then that person's steps (tabs/fixit.js).
const fixButton = (m) => primary("Fix", () => import("./fixit.js").then((x) => x.openFixit("exposed", m)), { label: "Fix the possible exposures" });

function rowsTable(t, s, mk) {
  const rows = t.exposure.rows.filter((r) => !VERDICT[s.sxv] || r.verdict === VERDICT[s.sxv]);
  return table([
    { key: "at", label: "When", type: "date", fmt: (v) => at(v) },
    { key: "host", label: "Host", copyValue: (r) => r.host || "", fmt: (v, r) => h("span", null, v || "(no host)", r.host && /^[\d.:[\]]+$/.test(r.host) ? h("span", { class: "sec-tag" }, "bare IP") : "") },
    { key: "path", label: "Path", path: true },
    { key: "status", label: "Status" },
    { key: "size", label: "Size (bytes)", num: true, fmt: (v) => (v == null ? "Not recorded" : n(v)) },
    { key: "verdict", label: "Why it is listed", fmt: (v, r) => why(r), sort: (r) => r.verdict },
    { key: "category", label: "What to do", fmt: (v) => { const [words, code] = adviceOf(v); return h("span", null, words, code ? copyIf("text", h("code", { class: "sec-code" }, code), code, { label: "line" }) : ""); }, csv: (r) => adviceOf(r.category).join(" ") },
    ...(mk && MAY.includes(mk.role) ? [{ key: "marked", label: "Checked", fmt: (v, r) => markButton(r, mk), sort: (r) => (r.marked ? 1 : 0), csv: (r) => (r.marked ? "not a problem" : "") }] : []),
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
    { key: "shell", label: "Harmless", num: true, fmt: (v, r) => n(harmlessOf(r) - (r.empty || 0)), sort: (r) => harmlessOf(r) - (r.empty || 0), csv: (r) => harmlessOf(r) - (r.empty || 0) },
    { key: "empty", label: "Empty", num: true, hide: true },
    { key: "possible", label: "Possible", num: true },
    { key: "unknown", label: "Can't tell", num: true },
  ], { caption: "Each host's answers", ns: "sxh", file: "answers-by-host.csv", rows, sortKey: "answered", dir: -1, search: false, limit: 12,
    empty: "No probe was answered with a page." });
}

/* An alert's link (#threats/exposed?item=<id>): the item it names, first; or a line that it is
   no longer listed. Today first, then the newest day: of its answers, the newest one nobody
   marked "Not a problem" (an item opened again because the file changed), else the newest. */
export function itemPart(f, s, marks = null, mk = null) {
  if (!s.item) return null;
  const days = [[f.today ? "today" : null, f.today?.security], ...(f.days || []).map((d) => [d.day, d.security]).reverse()];
  const rows = [];
  for (const [, b] of days) {
    for (const r of (b?.exposure?.rows || []).filter((x) => x.item === s.item).sort((x, y) => (x.at < y.at ? 1 : x.at > y.at ? -1 : 0))) {
      rows.push({ ...r, tol: Number(b?.rules?.tolerance ?? 16) });
    }
  }
  if (rows.length) {
    applyMarks({ exposure: { rows } }, marks);
    const row = rows.find((r) => !r.marked) || rows[0];
    const [words, code] = adviceOf(row.category);
    const tone = row.marked ? "ok" : "bad";
    const act = markButton(row, mk);
    return h("div", { class: `sec-verdict ${tone} sec-item`, role: row.marked ? "status" : "alert" }, h("span", { class: "sec-v-mark", "aria-hidden": "true" }, row.marked ? "✓" : "!"),
      h("div", null, h("strong", null, `From your alert: ${row.host}${row.path}`),
        h("p", null, `${at(row.at)}: answered ${row.status} with ${row.size == null ? "no recorded size" : `${n(row.size)} bytes`}. ${why(row)}`),
        row.marked ? null : h("p", null, words, code ? h("code", { class: "sec-code" }, code) : "")),
      act ? h("span", { class: "sec-v-act" }, act) : null);
  }
  return h("p", { class: "note sec-item" }, "The item in this link is no longer listed: the answer it named has left the days this page keeps.");
}

export default function exposed(m, s) {
  return secTab(m, s, {
    title: "Is anything exposed?",
    question: "Did the server hand a scanner a real file? Every probe answered with a page, set against the host's own harmless page.",
    help: HELP_TEXT,
    marks: true,
    draw: ({ f, t, p, mk }) => {
      applyMarks(t, mk?.marks);
      const e = t.exposure;
      const open = Math.max(0, e.possible - e.marked);
      const parts = [itemPart(f, s, mk?.marks, mk), banner(t, t.days && open ? fixButton(m) : null)];
      if (!t.days) return [...parts, missingNote(p, t)];
      parts.push(tiles([
        { label: "Scanner probes", value: t.probes, info: "Requests for paths no real site serves (.env, wp-login.php, phpinfo.php, ...) or with attack strings in the query, filed under bots. Each request stays in its group: Security is a view across them." },
        { label: "Answered with a page", value: e.answered, info: "Probes the server answered 2xx." },
        { label: "Harmless page", value: harmlessOf(e), info: "The host's fallback page (what it sends for any path it does not have), an empty body, an image, stylesheet, script or font, WordPress calling its own cron, or an answer the size of the host's home page." },
        { label: "Possible exposures", value: open, info: `A 2xx with a size unlike the host's harmless page.${e.marked ? ` Not counted here: ${n(e.marked)} marked not a problem.` : ""}` },
        { label: "Can't tell", value: e.unknown, info: "A 2xx whose line has no size: never called safe." },
      ]));
      parts.push(...optionsRow("Show", [choice("Show", s.sxv || "", SHOW, (v) => S.set({ sxv: v }))], {
        notes: [`A probe is filed by what it looked for: ${Object.values(LOOKED).join(", ")}.`] }));
      if (e.possible || e.unknown) parts.push(rowsTable(t, s, mk));
      else parts.push(emptyState(e.answered ? "Every probe answered with a page got the host's harmless page." : "No probe was answered with a page in this period."));
      if (e.folded) parts.push(h("p", { class: "note" }, `${n(e.folded)} more such answers are counted above but not listed (each day lists 200).`));
      parts.push(urlFold("sxx", "Open the details: each host's answers and its harmless page", () => hostsTable(t)), missingNote(p, t));
      return parts;
    },
  });
}

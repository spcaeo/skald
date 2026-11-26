// Traffic › Agent files, one section per kind of file (SKALD-65). The owner asked for the
// page "section wise": Markdown copies, llms.txt, Sitemaps, robots.txt (then agent cards
// and the OKF bundle), each with its own figures, who asked, what needs a look and its
// files, instead of one mixed list narrowed by chips.
//
//   the head       the kind, what it is; its requests and AI share (the whole range), its
//                  files listed and how many of them need a look
//   who asked      the kind's group band and its busiest names (the whole range)
//   needs a look   the kind's listed files that answered 4xx/5xx or moved elsewhere (3xx)
//   files          the kind's listed files, busiest first; a row opens the file's drawer
//   robots.txt     when it is one file listed for every day of the range: a single line
//                  (file, requests, answers, last fetched) and a note when it needs a look;
//                  otherwise (two spellings, days older than the files kept) the two tables
//
// Honest figures (review, 2026-11-26): files are kept for the last 30 days and each day's
// 50 busiest, so "files" and "need a look" count the files listed, never more; a range
// with no file listed says "not listed", never 0; and a look is raised only from a file's
// own status codes, never from the kind's buckets ("3xx" holds 304s, which are fine).
//
// Every file's address has Copy and Open at its end, as every page link has
// (urlactions.js): the File columns are URL columns, so Copy writes https://<site>/<path>,
// not the path alone, and Open opens the file in a new tab. Only a path from the site's
// root gets them (sitePath): a logged absolute target ("GET http://other.example/llms.txt")
// would make the link go to another host, as agent-files-drawer.js's siteUrl says.
//
// The sums are agent-files-sum.js's for one kind (sumRange(file, r, kind)), so a
// section's figures are the kind's card's, and the kinds' sections add up to the page.

import { h, n, pct1 } from "../ui.js";
import { band, legend } from "../charts.js";
import { table } from "../table.js";
import { link } from "../drill.js";
import { withUrl } from "../urlactions.js";
import { fileName } from "./common.js";
import { time as tzTime } from "../tz.js";
import { pageOf } from "../ai-ready.js";
import { WHO, KIND_WORDS, KIND_SAYS, WHO_WORDS, WHO_SAYS, WHO_COLOR, answers, attention, aiOf } from "./agent-files-sum.js";

/* The sections' order: the owner's (Markdown, llms.txt, Sitemaps, robots.txt), then the rest. */
export const SECTION_ORDER = ["markdown", "llms_txt", "sitemap", "robots_txt", "agent_card", "okf"];
export const sectionId = (k) => `af-${k.replace(/_/g, "-")}`;

const plural = (k, one, many = `${one}s`) => `${n(k)} ${k === 1 ? one : many}`;
const BUSIEST = 5;

/* The kinds that get a section: those someone fetched in the range, in SECTION_ORDER. */
export function sectionKinds(all) {
  return SECTION_ORDER.filter((k) => all.kinds[k]?.requests);
}

/* A path from the site's root, or null: only those get Copy and Open. */
export const sitePath = (p) => (typeof p === "string" && p.startsWith("/") && !p.startsWith("//") && !p.includes("\\") ? p : null);

/* How many of a kind's listed files need a look (its card and its head say the same). */
export const looksOf = (got) => attention(got.files).length;

/* The file's address with Copy and Open at its end (urlactions.js), a URL column. */
const pathCol = { key: "path", label: "File", path: true, href: (x) => sitePath(x.path), fmt: (v) => h("code", { class: "af-path", title: v }, v) };

export function answerCell(st) {
  const a = answers(st);
  const bits = [];
  if (a.ok) bits.push(h("span", { class: "af-ok" }, `${n(a.ok)} ok`));
  if (a.moved) bits.push(h("span", { class: "af-mv" }, `${n(a.moved)} moved`));
  if (a.failed) bits.push(h("span", { class: "af-bad" }, `${n(a.failed)} failed`));
  return h("span", { class: "af-ans", title: Object.entries(st).map(([c, k]) => `${c}: ${n(k)}`).join(", ") }, ...bits.flatMap((b, i) => (i ? [" · ", b] : [b])));
}

export function todo(x) {
  if (x.a.failed) {
    if (x.kind === "llms_txt" || x.kind === "agent_card") return "Agents ask for it and the site has none. Publish one, or leave it if you do not want to.";
    return "Agents asked and got nothing: fix the file, or remove the link that points to it.";
  }
  return "It sends agents elsewhere. Fine when on purpose; else link the final address.";
}

const answered = (st) => Object.entries(st).filter(([c]) => c[0] !== "2" && c !== "304").map(([c, k]) => `${c} × ${n(k)}`).join(", ");
const askedBy = (who) => WHO.filter((w) => who[w]).map((w) => `${WHO_WORDS[w]} ${n(who[w])}`).join(", ");
const restOf = (got) => Object.values(got.rest).reduce((a, v) => ({ requests: a.requests + v.requests, files: a.files + v.files }), { requests: 0, files: 0 });

function headOf(k, got, looks) {
  const fact = (v, words, cls = "", title = null) => h("div", { class: `af-hf${cls}`, ...(title ? { title } : {}) }, h("b", null, v), h("span", null, words));
  const listed = got.files.length;
  // Files listed: none listed while the kind had requests (days older than the files
  // kept, or only beyond each day's busiest 50) is "not listed", never 0; more beyond
  // the busiest 50 a day is "N+".
  const files = !listed
    ? fact("-", "files listed", "", "Not listed: files are kept for the last 30 days, and each day's 50 busiest.")
    : fact(`${n(listed)}${restOf(got).files ? "+" : ""}`, listed === 1 && !restOf(got).files ? "file listed" : "files listed");
  return h("div", { class: "af-sh" },
    h("div", { class: "af-st" }, h("h2", { tabindex: "-1" }, KIND_WORDS[k]), h("p", { class: "sub" }, KIND_SAYS[k])),
    h("div", { class: "af-hfs" },
      fact(n(got.shown), got.shown === 1 ? "request" : "requests"),
      fact(pct1(aiOf(got.who), got.shown), "from AI"),
      files,
      looks ? fact(n(looks), looks === 1 ? "needs a look" : "need a look", " af-hf-w") : null));
}

function whoAsked(got) {
  const parts = WHO.map((w) => ({ name: WHO_WORDS[w], value: got.who[w] || 0, color: WHO_COLOR[w] }));
  const busy = got.names.filter((x) => !x.folded).slice(0, BUSIEST);
  return h("div", { class: "af-who" },
    h("div", null, h("h3", null, "Who asked"),
      got.shown ? band(parts, got.shown) : null,
      got.shown ? legend(parts.filter((p) => p.value).map((p) => [`${p.name} ${pct1(p.value, got.shown)}`, p.color])) : null),
    busy.length ? h("div", null, h("h3", null, "Busiest"),
      h("ul", { class: "af-busy" }, ...busy.map((x) => h("li", { title: WHO_SAYS[x.who] },
        x.who === "people" ? x.name : link("bot", x.name), " ", h("b", null, n(x.requests)))))) : null);
}

const short = (k) => sectionId(k).slice(3);

function needsALook(k, r, rows) {
  if (!rows.length) return null;
  const cols = [
    pathCol,
    { key: "answers", label: "Answered", sortable: false, fmt: (_, x) => answered(x.status), csv: (x) => answered(x.status) },
    { key: "who", label: "Asked by", sortable: false, fmt: (_, x) => askedBy(x.who), csv: (x) => askedBy(x.who) },
    { key: "todo", label: "What to do", sortable: false, fmt: (_, x) => todo(x), csv: (x) => todo(x) },
  ];
  return h("div", { class: "af-part af-look" },
    h("h3", null, h("span", { class: "af-dot", "aria-hidden": "true" }), "Needs a look ", h("span", { class: "muted" }, n(rows.length))),
    h("p", { class: "sub" }, "Files that answered an error (an agent asked and got nothing) or sent the agent to another address."),
    table(cols, { caption: `${KIND_WORDS[k]} that need a look`, ns: `af${short(k).replace(/-/g, "")}look`, rows: rows.map((x) => ({ ...x, __k: x.path })),
      file: fileName(`agent-files-${short(k)}-attention`, r), sortKey: "requests", limit: 10, search: false }));
}

function filesNote(got) {
  const notes = ["Select a file for its days, answers and who fetched it."];
  if (got.filesDays < got.days) notes.push(`Files are kept for the last 30 days: they are listed for ${plural(got.filesDays, "day")} of the ${plural(got.days, "day")} counted, and so are their answers and what needs a look; the requests, AI share and who asked above cover every day.`);
  const rest = restOf(got);
  if (rest.requests) notes.push(`Beyond each day's 50 busiest files: ${plural(rest.requests, "more request")} (${plural(rest.files, "file")}, counted per day), in the requests above but not listed.`);
  return notes.join(" ");
}

function filesPart(m, s, r, k, got, openRow) {
  const cols = [
    pathCol,
    ...(k === "markdown" ? [{ key: "page", label: "Copy of", sort: (x) => pageOf(x.path), fmt: (_, x) => link("path", pageOf(x.path)),
      csv: (x) => pageOf(x.path), title: "The page a Markdown copy belongs to" }] : []),
    { key: "requests", label: "Requests", num: true },
    { key: "ai", label: "From AI", num: true, sort: (x) => aiOf(x.who) / (x.requests || 1), fmt: (_, x) => pct1(aiOf(x.who), x.requests), csv: (x) => aiOf(x.who), title: "AI assistants and AI crawlers" },
    { key: "answers", label: "Answers", sortable: false, fmt: (_, x) => answerCell(x.status), csv: (x) => Object.entries(x.status).map(([c, v]) => `${c}:${v}`).join(" ") },
    { key: "last", label: "Last fetched", type: "date", fmt: (v) => (v ? tzTime(v, { date: true, label: false }) : "-") },
  ];
  return h("div", { class: "af-part af-files" },
    h("h3", null, "Files ", h("span", { class: "muted" }, got.files.length ? n(got.files.length) : "not listed")),
    table(cols, { caption: `${KIND_WORDS[k]} fetched`, ns: `af${short(k).replace(/-/g, "")}files`, rows: got.files.map((x) => ({ ...x, __k: x.path })),
      file: fileName(`agent-files-${short(k)}`, r), sortKey: "requests", limit: 10,
      empty: got.filesDays < got.days ? "Files are listed for the last 30 days only." : "No file of this kind among each day's 50 busiest files in this range.",
      rowClass: () => "go", onRow: (x) => openRow(m, s, x), note: filesNote(got) }));
}

/* robots.txt as one line: only when it is one file listed on every day of the range,
   so its requests and its answers cover the same days. */
export const oneLine = (k, got) => k === "robots_txt" && got.files.length === 1 && got.filesDays === got.days && !restOf(got).files;

function oneFile(m, s, k, got, openRow) {
  const x = got.files[0];
  const a = answers(x.status);
  const at = sitePath(x.path);
  const cell = (label, value) => h("div", { class: "af-one-c" }, h("div", { class: "k-l" }, label), h("div", { class: "af-one-v" }, value));
  const name = h("code", { class: "af-path" }, x.path);
  // The line opens the drawer on a click; a real button does it for the keyboard (no
  // role="button" around Copy and Open: buttons inside a button are not announced).
  const line = h("div", { class: "af-one go", title: "Open this file's days, answers and who fetched it", onclick: () => openRow(m, s, x) },
    cell("File", at ? withUrl(name, at, { cls: "ua-after" }) : name),
    cell("Requests", n(x.requests)),
    cell("Answers", answerCell(x.status)),
    cell("Last fetched", x.last ? tzTime(x.last, { date: true, label: false }) : "-"));
  const look = a.failed || a.moved
    ? h("div", { class: "af-note", role: "note" }, h("span", { class: "af-dot", "aria-hidden": "true" }),
      h("div", null, h("b", null, `Needs a look: ${answered(x.status)}.`), " ", todo({ kind: k, a }), ` Asked by ${askedBy(x.who)}.`))
    : null;
  return h("div", { class: "af-part" }, line, look,
    h("p", { class: "af-small" }, h("button", { type: "button", class: "linkish", onclick: () => openRow(m, s, x) }, "Its days, answers and who fetched it ›")));
}

/* One kind's section: got is sumRange(file, r, k). */
export function kindSection(m, s, r, k, got, openRow) {
  const body = oneLine(k, got) ? [oneFile(m, s, k, got, openRow)] : [needsALook(k, r, attention(got.files)), filesPart(m, s, r, k, got, openRow)];
  return h("section", { class: "s af-sec", id: sectionId(k), "data-kind": k },
    headOf(k, got, looksOf(got)),
    h("div", { class: "af-sb" }, whoAsked(got), ...body.filter(Boolean)));
}

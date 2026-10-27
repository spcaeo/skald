// One Fix per screen outside Site › Alerts (2.42, docs/UI-RULES.md rules 1 and 2): the
// primary button of AI & bots › Assistants ("Let AI read the site better"), Security › Is
// anything exposed? ("Fix") and Security › Block list ("Block them") opens "Who will do it?"
// (ui/who.js), then only that person's path.
//
// The address: fixit=<what> (a fixed word: airead, exposed, block), by=me|dev|agent inside it.
//
// My AI agent is offered only where a job the agent already has does the work (the Insights
// to-dos' jobs: lost pages, server errors, Markdown copies; docs/plans/2026-10-26-todos-to-agents.md).
// AI readiness reaches it through those to-dos; an exposed file and the block list have no
// agent job yet, so they offer Me and My developer only. No new kit job is made here.

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { rangeOf } from "../data.js";
import { withCopy, withUrl } from "../urlactions.js";
import { say } from "../overlays.js";
import { primary } from "../ui/primary.js";
import { whoDialog, mePath, devPath } from "../ui/who.js";
import { fold } from "../ui/fold.js";

export const KEY = "fixit";
const here = (patch = {}) => `${location.origin || ""}${location.pathname}${location.search || ""}${S.hashFor({ ...S.read(), ...patch, [KEY]: "", by: "" })}`;
const done = (words) => { let d = null; const b = primary("I have done it", () => { d?.close(); say(words); }); return [b, (x) => { d = x; }]; };
const paths = (list, k = 5) => h("ul", { class: "ui-list" }, list.slice(0, k).map((p) => h("li", null, withUrl(h("code", null, p), p))));
const more = (list, k = 5) => (list.length > k ? fold(`The other ${n(list.length - k)}`, () => paths(list.slice(k), list.length)) : null);

// ---- AI & bots: the pages AI can't read well (ai_ready.json) --------------------------------

/* The list's rows by what to do, worst cause first: [id, title, what to do, paths, short words]. */
export function causesOf(f) {
  const rows = f?.attention?.rows || [];
  const of = (keep) => rows.filter(keep).map((r) => r.path);
  return [
    ["copy", "Markdown copies that do not answer", "Make each Markdown copy answer (page.md or page/index.md), or stop sending AI to it.", of((r) => r.copy_errors > 0), "with a Markdown copy that does not answer"],
    ["404", "Pages AI asks for that answer 404", "Bring each page back, or redirect it to the page that replaced it.", of((r) => r.not_found > 0), "answer 404"],
    ["errors", "Pages that fail for AI", "Find why these pages give AI a server error or a refusal (a firewall, a rate limit) and fix it.", of((r) => r.server_errors + r.blocked > 0), "fail for AI"],
    ["robots", "Pages robots.txt shuts AI out of", "Allow the crawlers you want in robots.txt. Whether to let one in is your choice.", of((r) => (r.robots || []).length > 0), "shut out by robots.txt"],
    ["slow", "Slow pages", "Speed these pages up: AI gives up on a slow answer.", of((r) => r.slow > 0), "slow"],
  ].filter((c) => c[3].length);
}

// The to-dos whose jobs the agent already has, for these causes.
const READ_KINDS = ["markdown", "errors", "lost"];
const agentTodos = (m) => (m.x?.todos?.todos || []).filter((t) => READ_KINDS.includes(t.kind) && !t.done && (t.agent ?? true));

async function airead(m) {
  const { loadReady } = await import("./aiready.js");
  const f = await loadReady(m, S.read()).catch(() => null);
  const causes = causesOf(f);
  if (!f || f.failed || !causes.length) return "Nothing to fix: AI gets what it asks for on every page Skald checked.";
  const total = f.attention?.total ?? (f.attention?.rows || []).length;
  const site = m.site || "";
  const me = () => causes.map(([id, title, what, list]) => h("section", { class: "ui-card quiet ui-stack", "data-cause": id },
    h("h4", null, `${title}: ${n(list.length)}`), h("p", null, what), paths(list), more(list)));
  const message = [`Skald found ${n(total)} page${total === 1 ? "" : "s"} on ${site || "our site"} that AI crawlers and assistants can't read well:`,
    ...causes.map(([, title, what, list]) => `- ${title} (${list.length}): ${list.slice(0, 5).join(", ")}${list.length > 5 ? ", …" : ""}. ${what}`),
    "Skald checks again every day; a page leaves the list once AI gets what it asks for."].join("\n");
  const p = { me: mePath(me), dev: devPath({ site, message, link: here({ tab: "ai/assistants" }) }) };
  const todos = agentTodos(m);
  if (todos.length) {
    p.agent = () => [h("p", null, `Your AI agent fixes the Markdown copies, the server errors and the lost pages through Insights' to-dos (${n(todos.length)} open). robots.txt and slow pages stay with you or your developer.`),
      h("p", null, h("button", { type: "button", class: "btn", onclick: () => S.set({ tab: "overview/insights", ...(todos.length === 1 ? { todo: todos[0].id, fix: "1" } : { fix: "all", todo: "" }), by: "agent", fixby: "", link: "", [KEY]: "" }) },
        todos.length === 1 ? "Open Fix this with my AI agent" : `Open Fix all (${n(todos.length)}) with my AI agent`))];
  }
  const [btn, set] = done("Skald checks again with the next daily run. A page leaves the list once AI gets what it asks for.");
  const d = await whoDialog({ title: "Let AI read the site better", subtitle: `${n(total)} page${total === 1 ? "" : "s"} AI can't read well`, route: { key: KEY, value: "airead" }, paths: p, fallback: "me", footer: [btn] });
  set(d);
  return d;
}

// ---- Security: possible exposures and the block list (security.json) ----------------------

async function period(m) {
  const [{ loadFile }, { periodOf, sumOf }] = await Promise.all([import("./sec-common.js"), import("../sec-data.js")]);
  const s = S.read();
  const f = await loadFile(s);
  if (!f || f.state === "error") return null;
  return sumOf(periodOf(f, rangeOf(m, s)).blobs);
}

async function exposed(m) {
  const t = await period(m);
  const rows = (t?.exposure?.rows || []).filter((r) => r.verdict === "possible");
  if (!rows.length) return "Nothing to fix: no possible exposure in this period.";
  const { adviceOf } = await import("./sec-common.js");
  const site = m.site || "";
  const cats = [...new Set(rows.map((r) => r.category))];
  const me = () => [h("p", null, "Open each path yourself and check what it returns. If it is a real file, do what its line says, then rotate any secret it held."),
    ...cats.map((c) => {
      const [what, code] = adviceOf(c);
      const list = rows.filter((r) => r.category === c).map((r) => `${r.host || ""}${r.path}`);
      return h("section", { class: "ui-card quiet ui-stack" }, h("p", null, what),
        code ? withCopy(h("pre", { class: "ui-code" }, code), code, { label: "the line for nginx", tag: "div" }) : null, paths(list), more(list));
    })];
  const message = [`Skald found ${n(rows.length)} possible exposure${rows.length === 1 ? "" : "s"} on ${site || "our site"}: a scanner asked for a file and got an answer unlike the host's harmless page.`,
    ...cats.map((c) => { const [what, code] = adviceOf(c); return `- ${rows.filter((r) => r.category === c).map((r) => `${r.host || ""}${r.path}`).slice(0, 5).join(", ")}: ${what}${code ? ` (nginx: ${code})` : ""}`; }),
    "Rotate any secret such a file held. The log records the size, never the content, so check each one."].join("\n");
  const [btn, set] = done("Skald checks every scanner probe again with each live run.");
  const d = await whoDialog({ title: "Fix the possible exposures", subtitle: `${n(rows.length)} answer${rows.length === 1 ? "" : "s"} to check`, route: { key: KEY, value: "exposed" },
    paths: { me: mePath(me), dev: devPath({ site, message, link: here({ tab: "threats/exposed" }) }) }, fallback: "me", footer: [btn] });
  set(d);
  return d;
}

async function block(m) {
  const site = m.site || "";
  const me = () => [h("p", null, "Download the list under the Block list (nginx deny lines, a Cloudflare IP list or a plain list), review it, then add it where your site blocks traffic:"),
    h("ol", { class: "ui-list" },
      h("li", null, "nginx: include the file in the server block, run ", withCopy(h("code", null, "nginx -t"), "nginx -t", { label: "the command" }), ", then reload."),
      h("li", null, "Cloudflare: Settings › Lists, Create new list (IP), Add items › Upload CSV, then use the list in a WAF rule."),
      h("li", null, "fail2ban or ipset: feed them the plain list.")),
    h("p", { class: "note" }, "A shared address (an office, a mobile network, a VPN) or a CDN can carry real visitors too: review before you block.")];
  const message = [`Skald lists the addresses and networks that scanned or attacked ${site || "our site"} in this period. Please review the list and block it at the web server or at Cloudflare.`,
    "The list is on Security › Block list, with downloads for nginx, Cloudflare and a plain list. Review before blocking: a shared address or a CDN can carry real visitors."].join("\n");
  const [btn, set] = done("Blocking stops the requests from those addresses. A scanner moves on within days, so check the list again now and then.");
  const d = await whoDialog({ title: "Block the scanners", subtitle: "From the list on this page", route: { key: KEY, value: "block" },
    paths: { me: mePath(me), dev: devPath({ site, message, link: here({ tab: "threats/block" }) }) }, fallback: "me", footer: [btn] });
  set(d);
  return d;
}

const OPEN = { airead, exposed, block };
export function openFixit(v, m) {
  return OPEN[v] ? OPEN[v](m) : Promise.resolve("That Fix is not one Skald has.");
}
export const openFixitKey = (v, m) => openFixit(v, m);

// Security > Attack attempts (2.21): what was tried beyond looking around. Path tricks and
// injection in the URL (by kind), login and form hammering (many POSTs to a login or form
// path from one address in a short time) and unusually fast bursts from one address. Each
// one: who, when, how many, and what the server answered. The thresholds are the
// install's (config `security:`), said in the (i).
//
//   sxa   Show: "" all three, "injection", "login", "burst"

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { table } from "../table.js";
import { tiles } from "./tiles.js";
import { blist } from "./common.js";
import { ranked } from "../data.js";
import { optionsRow, choice, emptyState } from "./sa-options.js";
import { secTab, loadAddresses, spanOf, at, answered, addressWords, missingNote } from "./sec-common.js";
import { signsOf, SIGN_FACTOR, SIGN_DAYS, SIGN_NEED, SIGN_MIN } from "../sec-data.js";

const SIGN = { gateway: "Gateway errors (502, 503, 504): PHP workers or an upstream may be crashing", php: "Requests for .php paths" };
const LENGTH_LINE = "request_length=$request_length";

/* "Log signs worth a look": never "attack detected", only what stands out from the usual. */
export function signsPart(f, r) {
  const got = signsOf(f, r);
  const items = got.rows.map((x) => h("li", null, h("strong", null, `${SIGN[x.kind]}: ${n(x.n)} on ${x.day}`),
    ` (usual ${n(x.usual)} a day${x.peak ? `; the most, ${n(x.peak[1])}, in the hour from ${x.peak[0].slice(11)}:00 UTC` : ""}).`));
  const posts = got.posts == null
    ? h("p", { class: "note" }, "Large POST bodies: not recorded. The log has no request size; add ", h("code", null, LENGTH_LINE), " to the log format (docs: Getting your log in).")
    : h("p", { class: got.posts.large ? "sec-login bad" : "note" }, got.posts.large
      ? `${n(got.posts.large)} POST${got.posts.large === 1 ? "" : "s"} of ${n(f.rules?.large_post_bytes || 1000000)} bytes or more (the largest ${n(got.posts.max)} bytes), to ${Object.keys(got.posts.paths).filter((k) => k !== "(all others)").join(", ")}.`
      : `No POST of ${n(f.rules?.large_post_bytes || 1000000)} bytes or more (${n(got.posts.recorded)} POSTs with a recorded size).`);
  return h("div", { class: "card sec-signs" }, h("h2", null, "Log signs worth a look"),
    items.length ? h("ul", { class: "sec-hits" }, items)
      : h("p", { class: "note" }, got.days ? "Nothing stands out: gateway errors and .php requests stayed near the usual." : "Not recorded for this period."),
    posts,
    h("p", { class: "note" }, `Worth a look, never proof of an attack: a day at ${SIGN_FACTOR} times the median of the ${SIGN_DAYS} days before it (with ${SIGN_NEED} of them recorded) and at least ${SIGN_MIN}.`));
}

export const KINDS = { traversal: "Path traversal (../, /etc/passwd)", log4shell: "Log4Shell (${jndi:)", xss: "Script injection (<script)",
  sql: "SQL injection (union select)", php: "PHP settings and debugger", other: "Other injection" };

const mins = (s) => (s % 60 ? `${s} seconds` : `${s / 60} minute${s === 60 ? "" : "s"}`);
export const rulesWords = (rules) => `Login and form hammering: ${rules.login_posts} or more POSTs to a login or form path (login, sign-in, password, sign-up, contact...) from one address within ${mins(rules.login_seconds)}. A burst: ${rules.burst_requests} or more requests from one address within ${mins(rules.burst_seconds)}, people and bots only (search and AI crawlers are left out). Set in the config's security: section.`;

/* Who a row is: its addresses when the helper gave them, else the row numbers of the day. */
export function whoOf(row, map) {
  const list = Array.isArray(row.who) ? row.who : row.who == null ? [] : [row.who];
  if (!list.length) return "Not listed";
  return list.map((q) => { const x = map.get(`${row.day}|${q}`); return x?.ip || `#${q}`; }).join(", ");
}

function part(title, rows, cols, opts) {
  return [h("h2", { class: "sec-h2" }, title), table(cols, { limit: 12, ...opts, rows })];
}

export default function attacks(m, s) {
  return secTab(m, s, {
    title: "Attack attempts",
    question: "What did they try beyond looking around: tricks in the address, hammering a login form, or flooding the server?",
    help: "Path tricks and injection: an attack string in the address (../, /etc/passwd, ${jndi:, <script, union select). Each is a scanner probe too, and is in Who is scanning us. Login hammering and bursts are found per address over the whole day.",
    draw: ({ f, r, p, t }) => {
      if (!t.days) return [emptyState("Not recorded for this period."), missingNote(p, t)];
      const show = s.sxa || "";
      const parts = [tiles([
        { label: "Injection attempts", value: t.injection.requests, info: "Requests with an attack string in the address." },
        { label: "Login and form posts", value: t.login.posts, info: `POSTs inside a hammering episode (${t.login.episodes} episode${t.login.episodes === 1 ? "" : "s"}).` },
        { label: "Burst requests", value: t.bursts.requests, info: `Requests inside a burst (${t.bursts.episodes} burst${t.bursts.episodes === 1 ? "" : "s"}).` },
      ])];
      parts.push(signsPart(f, r));
      parts.push(...optionsRow("Show", [choice("Show", show, [["", "All"], ["injection", "Injection"], ["login", "Login hammering"], ["burst", "Bursts"]], (v) => S.set({ sxa: v }))],
        { notes: [rulesWords(f.rules || {})] }));
      const holder = h("div", { class: "sec-attacks" }, h("p", { class: "empty" }, "Loading…"));
      parts.push(holder, missingNote(p, t));
      const [first, last] = spanOf(m, r);
      loadAddresses(first, last).then((ans) => {
        const map = new Map((ans?.ok ? ans.rows : []).map((x) => [`${x.day}|${x.seq}`, x]));
        const out = [];
        if (!show || show === "injection") {
          out.push(h("h2", { class: "sec-h2" }, "Path tricks and injection, by kind"),
            blist(ranked(t.injection.kinds), { color: "var(--bad)", total: t.injection.requests, label: (k) => KINDS[k] || k, empty: "No injection attempt." }));
          if (t.injection.rows.length) out.push(table([
            { key: "first", label: "When", type: "date", fmt: (v) => at(v) },
            { key: "who", label: "Address", fmt: (v, row) => whoOf(row, map), sort: (row) => whoOf(row, map) },
            { key: "kind", label: "Kind", fmt: (v) => KINDS[v] || v },
            { key: "requests", label: "Requests", num: true },
            { key: "status", label: "Answered", fmt: (v) => answered(v), sort: (row) => row.status?.["2xx"] || 0 },
          ], { caption: "Injection attempts", ns: "sxi", file: "injection-attempts.csv", rows: t.injection.rows, sortKey: "requests", dir: -1, limit: 12 }));
        }
        if (!show || show === "login") {
          out.push(...part("Login and form hammering", t.login.rows, [
            { key: "start", label: "From", type: "date", fmt: (v) => at(v) },
            { key: "end", label: "To", type: "date", fmt: (v) => at(v) },
            { key: "who", label: "Address", fmt: (v, row) => whoOf(row, map), sort: (row) => whoOf(row, map) },
            { key: "posts", label: "POSTs", num: true },
            { key: "path", label: "Path", path: true },
            { key: "status", label: "Answered", fmt: (v) => answered(v), sort: (row) => row.status?.["2xx"] || 0 },
          ], { caption: "Login and form hammering", ns: "sxl", file: "login-hammering.csv", sortKey: "posts", dir: -1, empty: "No address hammered a login or form in this period." }));
        }
        if (!show || show === "burst") {
          out.push(...part("Bursts", t.bursts.rows, [
            { key: "start", label: "From", type: "date", fmt: (v) => at(v) },
            { key: "end", label: "To", type: "date", fmt: (v) => at(v) },
            { key: "who", label: "Address", fmt: (v, row) => whoOf(row, map), sort: (row) => whoOf(row, map) },
            { key: "requests", label: "Requests", num: true },
            { key: "path", label: "Most asked", path: true },
            { key: "status", label: "Answered", fmt: (v) => answered(v), sort: (row) => row.status?.["2xx"] || 0 },
          ], { caption: "Bursts", ns: "sxb", file: "bursts.csv", sortKey: "requests", dir: -1, empty: "No burst in this period." }));
        }
        const words = addressWords(ans, f);
        if (words) out.push(h("p", { class: "note" }, words));
        holder.replaceChildren(...out);
      });
      return parts;
    },
  });
}

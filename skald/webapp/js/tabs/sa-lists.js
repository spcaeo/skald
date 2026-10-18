// Leads & sales (2.7.0): what the figures leave out, listed in full on the page
// as a Data Grid (search, filters, sort and paging kept in the address):
//   * the lead database's spam, duplicate and test leads (people/left-out)
//   * the tools' cancelled and no-show, removed and test conversions
//     (people/conversions?kind=)
// The same answers person.js's drawers show (openLeftOut, openConversionList);
// here they open from a toggle beside the figures instead of a drawer only.
//
// Listings, never figures: nothing here is summed into a count, and a lead from
// the lead database and a conversion from the tools never share one list.
// Names, emails and visitor IDs come only to admins and owners (the helper decides).

import { h } from "../ui.js";
import { time as tzTime } from "../tz.js";
import { call } from "./ipmanager.js";
import { mayFind, openPerson } from "./person.js";
import { openDrawer } from "../drawer.js";
import { grid } from "../grid.js";
import { actionName, toolName, STAGE } from "./leadfigs.js";

export const LEAD_SHOW = [["spam", "Spam"], ["duplicate", "Duplicates"], ["test", "Test"]];
export const CONV_SHOW = [["cancelled", "Cancelled or no-show"], ["removed", "Removed"], ["test", "Test"]];
const KIND = { spam: "Spam", duplicate: "Duplicate", test: "Test", cancelled: "Cancelled or no-show", removed: "Removed by a sync" };

// One answer per address for a minute: a redraw (every 2 minutes today) does not ask again.
const asked = new Map();
function fetchList(path) {
  const got = asked.get(path);
  if (got && Date.now() - got.at < 60000) return got.p;
  const p = call(path).catch((e) => ({ ok: false, error: String(e?.message || e) }));
  asked.set(path, { at: Date.now(), p });
  p.then((r) => { if (!r?.ok) asked.delete(path); });
  return p;
}

const at = (ts) => (ts ? tzTime(ts, { date: true, label: false }) : "-");
const dash = (v) => (v == null || v === "" ? "-" : String(v));
const mono = (v) => (v == null || v === "" ? "-" : h("span", { class: "mono" }, v));
// A value that finds its person (admins and owners): an email, a lead, a reference.
const key = (v, words = v) => (v == null || v === "" ? "-" : v === "(removed)" ? "removed on request" : mayFind()
  ? h("button", { type: "button", class: "pp-link", title: `Find ${v}`, onclick: (e) => { e.stopPropagation(); openPerson(String(v)); } }, words) : words);

// The section that holds a list: a heading, its words, and the grid once the answer is in.
function holder(title, words) {
  const body = h("div", { class: "sa-list-body" }, h("p", { class: "empty" }, "Loading…"));
  const sec = h("section", { class: "s sa-list" }, h("h2", null, title), h("p", { class: "sub" }, words), body);
  return [sec, body];
}

// Put the grid in once the section is on the page (the answer may be in before the redraw is).
function fill(body, make) {
  let tries = 0;
  const go = () => {
    if (!body.isConnected) { if (++tries < 30) requestAnimationFrame(go); return; }
    body.replaceChildren(...[make()].flat().filter(Boolean));
  };
  go();
}
// A filter's choices: the values the rows hold, in words.
const seen = (rows, k, words) => [...new Set(rows.map((r) => r[k]).filter(Boolean))].sort().map((v) => [v, words(v)]);
const failed = (got) => h("div", { class: "state bad", role: "alert" }, h("div", null, got?.error || "The list could not be loaded."));

/* The lead database's left-out leads, of the kinds asked for (spam, duplicate, test). */
export function leadList(kinds, { ns = "lo", only = null } = {}) {
  const [sec, body] = holder("Left out of the lead figures",
    "Leads your team marked spam or duplicate in the lead database, and leads marked test: kept and listed here, never counted.");
  fetchList("people/left-out").then((got) => fill(body, () => {
    if (!got?.ok) return failed(got);
    const kindOf = (r) => (r.test ? "test" : r.status);
    const rows = (got.leads || []).filter((r) => kinds.includes(kindOf(r)) && (!only || only(r.type))).map((r) => ({ ...r, kind: kindOf(r) }));
    const named = rows.some((r) => r.email || r.name);
    const cols = [
      { key: "created_at", label: "Made", type: "date", fmt: (v) => at(v) },
      { key: "id", label: "Lead", fmt: (v) => key(v, `#${v}`), csv: (r) => r.id },
      { key: "kind", label: "Left out as", fmt: (v) => h("b", { class: "pp-bad" }, KIND[v] || v), csv: (r) => KIND[r.kind] || r.kind },
      { key: "type", label: "Type", fmt: dash },
      { key: "page", label: "Page", fmt: mono },
      { key: "first_source", label: "First touch", fmt: dash },
      { key: "last_source", label: "Last touch", fmt: dash },
      ...(named ? [{ key: "email", label: "Email", fmt: (v) => key(v) }, { key: "name", label: "Name", fmt: dash }] : []),
    ];
    return [grid({ ns, caption: "Leads left out of the figures", file: "leads-left-out.csv", columns: cols, rows, sortKey: "created_at", dir: "desc",
      filters: kinds.length > 1 ? [{ key: "kind", label: "Left out as", options: kinds.map((k) => [k, KIND[k]]) }] : [],
      empty: kinds.length ? "None of these." : "Choose what to show above." }),
    h("p", { class: "note" }, `Spam and duplicates are as your team marked them in the lead database; test is set on the server.${got.private ? "" : " Emails and names show to admins and owners only."}`)];
  }));
  return sec;
}

// One conversion row, the same shape whichever list it came from.
function convRow(kind, r) {
  if (kind === "removed") {
    const was = r.row || {};
    return { kind, at: r.at || was.at, action: r.action || was.action, stage: r.stage || was.stage, tool: r.tool || was.tool, source: was.source_type ?? null,
      landing: was.landing ?? null, ref: r.external_ref, vid: null, email: null, why: [r.why, r.removed_at ? `removed ${at(r.removed_at)}` : ""].filter(Boolean).join(", "), journey: r.journey || [] };
  }
  return { kind, at: r.at, action: r.action, stage: r.stage, tool: r.tool, source: r.source_type, landing: r.landing, ref: r.external_ref, vid: r.vid || null,
    email: r.email || null, why: kind === "test" ? "marked test (kept, never counted)" : "", journey: r.journey || [] };
}

function convDetail(r) {
  const dl = h("dl", { class: "dw-dl" }, [["List", KIND[r.kind]], ["When", at(r.at)], ["Action", actionName(r.action || "")], ["Stage", STAGE[r.stage] || dash(r.stage)],
    ["Reported by", toolName(r.tool)], ["Source (last touch)", dash(r.source)], ["Landing", dash(r.landing)], ["Lead or reference", key(r.ref)], ["Visitor ID", key(r.vid)], ["Why", dash(r.why)]]
    .flatMap(([t, v]) => [h("dt", null, t), h("dd", null, v)]));
  const trail = r.journey.length ? h("section", { class: "dw-sec" }, h("h3", null, `Pages before (${r.journey.length})`),
    h("ol", { class: "pp-trail" }, r.journey.map((j) => h("li", null, at(j.at), " ", h("span", { class: "mono" }, j.path))))) : h("p", { class: "note" }, "No journey: this conversion carries no visitor ID.");
  openDrawer({ title: `${actionName(r.action || "")}, ${STAGE[r.stage] || r.stage || ""}`, subtitle: KIND[r.kind], key: "sa-conv", scope: "page", size: "md", body: [dl, trail] });
}

/* The tools' cancelled, removed and test conversions, of the kinds asked for.
   only: (action) => bool, to keep one tab's actions (Bookings). */
export function convList(kinds, { ns = "lo", only = null, title = "Cancelled, removed and test conversions" } = {}) {
  const [sec, body] = holder(title,
    "Every conversion stays visible: cancelled bookings and no-shows as the tool reported them, rows a lead-database sync took away (with when and why), and conversions marked test (kept, never counted). A row opens its journey.");
  Promise.all(kinds.map((k) => fetchList(`people/conversions?kind=${encodeURIComponent(k)}`).then((got) => [k, got]))).then((answers) => fill(body, () => {
    const bad = answers.find(([, got]) => !got?.ok);
    if (bad) return failed(bad[1]);
    const rows = answers.flatMap(([k, got]) => (got.rows || []).map((r) => convRow(k, r))).filter((r) => !only || only(r.action));
    const named = rows.some((r) => r.email || r.vid);
    const cols = [
      { key: "at", label: "When", type: "date", fmt: (v) => at(v) },
      { key: "kind", label: "List", fmt: (v) => KIND[v] || v, csv: (r) => KIND[r.kind] || r.kind },
      { key: "action", label: "Action", fmt: (v) => (v ? actionName(v) : "-"), csv: (r) => r.action },
      { key: "stage", label: "Stage", fmt: (v) => STAGE[v] || dash(v) },
      { key: "tool", label: "Reported by", fmt: (v) => (v ? toolName(v) : "-"), csv: (r) => r.tool },
      { key: "source", label: "Source", fmt: dash },
      // A booking tool's reference is a long address: its end, the whole on hover (and in the CSV).
      { key: "ref", label: "Lead or reference", fmt: (v) => h("span", { class: "sa-ref", title: v || null }, key(v, v && v.length > 28 ? `…${v.slice(-26)}` : v)), csv: (r) => r.ref, sortable: false },
      ...(named ? [{ key: "email", label: "Email", fmt: (v) => key(v) }] : []),
      { key: "why", label: "Why", fmt: dash, sortable: false },
    ];
    return [grid({ ns, caption: title, file: "conversions-left-out.csv", columns: cols, rows, sortKey: "at", dir: "desc", onRow: convDetail,
      filters: [...(kinds.length > 1 ? [{ key: "kind", label: "List", options: kinds.map((k) => [k, KIND[k]]) }] : []),
        { key: "action", label: "Action", options: seen(rows, "action", actionName) }, { key: "tool", label: "Reported by", options: seen(rows, "tool", toolName) }],
      empty: kinds.length ? "None of these." : "Choose what to show above." }),
    h("p", { class: "note" }, `Cancelled and no-shows are counted under their own stage, never as completed. A removed row is kept whole; only a deletion request (skald forget) deletes for good.${answers.some(([, got]) => got.private) ? "" : " Emails and visitor IDs show to admins and owners only."}`)];
  }));
  return sec;
}

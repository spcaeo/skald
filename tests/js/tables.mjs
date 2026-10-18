// Every table's sort, column filters, column chooser and "Export what you see"
// (js/tablestate.js, js/table.js): the order (numbers by size, dates by time, not
// recorded last either way, asc / desc / the table's own again), the filters
// (contains, a range, picked values), the address they are kept in, and the CSV of
// what is on screen. The whole-row drill still opens the right row after a sort.
//
//   node tests/js/tables.mjs
import assert from "node:assert/strict";
import { install, Ev } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const T = await import(new URL("tablestate.js", JS));
const { table, csv, REGISTRY } = await import(new URL("table.js", JS));
const S = await import(new URL("state.js", JS));
S.addSections([{ key: "traffic", name: "Traffic", tabs: [{ route: "traffic/sources", name: "Sources" }, { route: "traffic/pages", name: "Pages" }] }]);

// ---- order
{
  const rows = [{ n: 3 }, { n: null }, { n: 10 }, { n: "Not recorded" }, { n: 2 }];
  const asc = T.sortRows(rows, [{ get: (r) => r.n, dir: 1 }]).map((r) => r.n);
  const desc = T.sortRows(rows, [{ get: (r) => r.n, dir: -1 }]).map((r) => r.n);
  assert.deepEqual(asc, [2, 3, 10, null, "Not recorded"], "numbers by size, not recorded last");
  assert.deepEqual(desc, [10, 3, 2, null, "Not recorded"], "not recorded last the other way too");
  const words = T.sortRows([{ p: "/page10" }, { p: "/page2" }, { p: "" }, { p: "/About" }], [{ get: (r) => r.p, dir: 1 }]).map((r) => r.p);
  assert.deepEqual(words, ["/About", "/page2", "/page10", ""], "natural order, any case; empty last");
  const days = T.sortRows([{ d: "2026-10-02T09:00" }, { d: "2026-09-30T23:59" }, { d: "2026-10-02T08:59" }], [{ get: (r) => r.d, type: "date", dir: -1 }]).map((r) => r.d);
  assert.deepEqual(days, ["2026-10-02T09:00", "2026-10-02T08:59", "2026-09-30T23:59"], "dates by time");
  const stable = T.sortRows([{ k: 1, i: "a" }, { k: 1, i: "b" }, { k: 0, i: "c" }], [{ get: (r) => r.k, dir: -1 }]).map((r) => r.i);
  assert.deepEqual(stable, ["a", "b", "c"], "ties keep their order");
}
// The click cycle: first way, the other, the table's own again.
{
  const num = { key: "v", num: true }, word = { key: "w" };
  const def = { key: "v", dir: -1 };
  let s = null;
  s = T.nextSort(s, word, def); assert.deepEqual(s, { key: "w", dir: 1 }, "words A to Z first");
  s = T.nextSort(s, word, def); assert.deepEqual(s, { key: "w", dir: -1 });
  s = T.nextSort(s, word, def); assert.equal(s, null, "then the table's own order");
  s = T.nextSort(null, num, def); assert.deepEqual(s, { key: "v", dir: 1 }, "the default column turns the other way at once");
  s = T.nextSort(s, num, def); assert.equal(s, null);
  assert.deepEqual(T.readSort(T.sortParam({ key: "v", dir: 1 }), ["v"]), { key: "v", dir: 1 });
  assert.equal(T.readSort("gone:asc", ["v"]), null, "a column that is not there: the default");
}

// ---- filters and their address form
{
  assert.equal(T.parseAmount("1 min"), 60);
  assert.equal(T.parseAmount("2:30"), 150);
  assert.equal(T.parseAmount("1h 5m"), 3900);
  assert.equal(T.parseAmount("12%"), 12);
  assert.equal(T.parseAmount("1,234"), 1234);
  assert.equal(T.parseAmount("lots"), null);
  assert.equal(T.testFilter({ op: "has", value: "PRIC" }, { text: "/pricing/" }), true);
  assert.equal(T.testFilter({ op: "range", value: [3, null] }, { num: 3 }), true);
  assert.equal(T.testFilter({ op: "range", value: [null, 2] }, { num: 3 }), false);
  assert.equal(T.testFilter({ op: "range", value: [0, null] }, { num: null }), false, "not recorded is never in a range");
  assert.equal(T.testFilter({ op: "in", value: ["Mobile", "Tablet"] }, { text: "Tablet" }), true);
  const list = [{ key: "a", op: "has", value: "x;y:z|w" }, { key: "b", op: "range", value: [1.5, null] }, { key: "c", op: "in", value: ["P|Q", "R"] }, { key: "d", op: "has", value: "  " }];
  const text = T.writeFilters(list);
  assert.deepEqual(T.readFilters(text, ["a", "b", "c", "d"]), list.slice(0, 3), "round trip; an empty filter is not kept");
  assert.deepEqual(T.readFilters(text, ["a"]), [list[0]], "a column that is not there: its filter is dropped");
  assert.equal(T.filterKind({ key: "x", num: true }), "num");
  assert.equal(T.filterKind({ key: "x", type: "badge" }), "enum");
  assert.equal(T.filterKind({ key: "x" }, 3), "enum", "few values: pick some");
  assert.equal(T.filterKind({ key: "x" }, 40), "text");
  assert.equal(T.filterKind({ key: "x", filter: false }), null);
  assert.equal(T.nsOf("Each visit"), "eachvisit");
  assert.equal(T.nsOf("Each visit", ["eachvisit"]), "eachvisit2");
  assert.equal(T.nsOf("404s"), "t404s");
  assert.ok(T.TABLE_KEY.test("eachvisit_cf") && T.TABLE_KEY.test("pg_hide") && T.TABLE_KEY.test("pg_sort") && !T.TABLE_KEY.test("country"));
}

// ---- the table itself
const hashKey = (k) => new URLSearchParams(location.hash.split("?")[1] || "").get(k);
const cols = [
  { key: "page", label: "Page", drill: "path" },
  { key: "views", label: "Views", num: true },
  { key: "kind", label: "Kind" },
  { key: "when", label: "Last seen", type: "date" },
];
const rows = [
  { page: "/pricing/", views: 40, kind: "Product", when: "2026-10-02" },
  { page: "/blog/a", views: 12, kind: "Blog", when: "2026-10-05" },
  { page: "/", views: null, kind: "Home", when: "" },
  { page: "/blog/b", views: 90, kind: "Blog", when: "2026-09-12" },
];
const cellsOf = (t, i) => t.querySelectorAll("tbody tr").map((tr) => tr.children[i].textContent);
const header = (t, label) => t.querySelectorAll("thead th").find((th) => th.textContent.startsWith(label)).querySelector("button");
{
  location.hash = "#traffic/pages";
  REGISTRY.length = 0;
  const t = table(cols, { caption: "Pages read", rows, file: "pages.csv" });
  assert.deepEqual(cellsOf(t, 0), ["/blog/b", "/pricing/", "/blog/a", "/"], "the default: the first number, biggest first, not recorded last");
  header(t, "Page").click();
  assert.deepEqual(cellsOf(t, 0), ["/", "/blog/a", "/blog/b", "/pricing/"], "A to Z");
  assert.equal(hashKey("pagesread_sort"), "page:asc", "the order is kept in the address");
  header(t, "Page").click();
  assert.deepEqual(cellsOf(t, 0), ["/pricing/", "/blog/b", "/blog/a", "/"]);
  header(t, "Page").click();
  assert.deepEqual(cellsOf(t, 0), ["/blog/b", "/pricing/", "/blog/a", "/"], "the third click: the table's own order");
  assert.equal(hashKey("pagesread_sort"), null);
  header(t, "Last seen").click();
  assert.deepEqual(cellsOf(t, 0), ["/blog/a", "/pricing/", "/blog/b", "/"], "dates newest first, not recorded last");
  assert.equal(t.querySelector("thead th[aria-sort]") != null, true);

  // The whole-row drill opens the row now in that place.
  const first = t.querySelectorAll("tbody tr")[0];
  assert.ok(first.classList.contains("drow"), "rows still drill after a sort");
  first.children[1].click();
  assert.match(location.hash, /dd=path(%3A|:)%2Fblog%2Fa|dd=path:\/blog\/a/, "the row clicked is the row opened");
  location.hash = "#traffic/pages?pagesread_sort=when:desc";

  // Filter columns: the row under the headers, a range on a number.
  const tog = t.querySelectorAll(".tbl-tools button").find((b) => b.textContent.startsWith("Filter columns"));
  tog.click();
  const frow = t.querySelector("thead tr.tt-frow");
  assert.ok(frow, "the filter row opens under the headers");
  const [min] = frow.querySelectorAll("input.tt-num");
  min.value = "20";
  min.dispatchEvent(new Ev("input"));
  await new Promise((r) => setTimeout(r, 250));
  assert.deepEqual(cellsOf(t, 0), ["/pricing/", "/blog/b"], "views at least 20; not recorded is never in a range");
  assert.equal(hashKey("pagesread_cf"), "views:range:20..", "the filter is kept in the address");
  assert.match(t.querySelector(".tbl-count").textContent, /2 of 4 rows/);

  // The column chooser, and the CSV of what is on screen: these rows, these columns, this order.
  const box = t.querySelectorAll(".tt-pop input").find((x) => x.parentNode.textContent.includes("Kind"));
  box.checked = false;
  box.dispatchEvent(new Ev("change"));
  assert.equal(hashKey("pagesread_hide"), "kind");
  assert.deepEqual(t.querySelectorAll("thead tr")[0].children.map((th) => th.textContent.replace(/[▲▼↕]/g, "")), ["Page", "Views", "Last seen"]);
  const reg = REGISTRY.find((x) => x.ns === "pagesread");
  assert.ok(reg, "the table is in the registry, by its name");
  assert.equal(csv(cols.filter((c) => c.key !== "kind"), reg.rows()), "Page,Views,Last seen\r\n/pricing/,40,2026-10-02\r\n/blog/b,90,2026-09-12\r\n");
  const ex = t.querySelector(".tt-export");
  assert.match(ex.textContent, /CSV, 2 rows, 3 columns/, "the button says what it will write");

  // A redraw (a reload, a link) brings the same table back.
  REGISTRY.length = 0;
  const again = table(cols, { caption: "Pages read", rows, file: "pages.csv" });
  assert.deepEqual(cellsOf(again, 0), ["/pricing/", "/blog/b"]);
  assert.equal(again.querySelectorAll("thead tr")[0].children.length, 3);
  assert.ok(again.querySelector("thead tr.tt-frow"), "a table with filters on opens with its filter row");
}
// A table kept out of the address, and a table with no tools.
{
  location.hash = "#traffic/pages";
  const t = table(cols, { caption: "In a card", rows, ns: false, tools: false, file: "x.csv" });
  header(t, "Page").click();
  assert.equal(location.hash, "#traffic/pages", "ns: false writes nothing");
  assert.equal(t.querySelector(".tt-export"), null);
  assert.ok(t.querySelectorAll(".tbl-tools button").some((b) => b.textContent === "CSV"), "tools: false keeps the plain CSV button");
}
// state.js carries a table's keys while the tab stays, and drops them on another tab.
{
  location.hash = "#traffic/pages?range=7d&pagesread_cf=views%3Arange%3A20..&pagesread_hide=kind";
  assert.match(S.hashFor({ ...S.read(), tab: "traffic/pages" }), /pagesread_cf=/);
  assert.doesNotMatch(S.hashFor({ ...S.read(), tab: "traffic/sources" }), /pagesread_/);
  S.set({ rules: "all(device:is:Mobile)" }, { replace: true });
  assert.equal(S.read().rules, "all(device:is:Mobile)", "the advanced rules are a key of the address");
  assert.match(S.hashFor({ ...S.read(), tab: "traffic/sources" }), /rules=/, "and stay on every tab");
}

// A cell's visible words (2.13): the screen reader's hidden full name is not part of what a
// column filter matches ("USA" must not match "AUS" + "Australia"), but the search box finds it.
{
  const { cellWords } = await import(new URL("table.js", JS));
  const { h } = await import(new URL("ui.js", JS));
  const aus = h("span", { class: "named", title: "Australia" }, h("span", { class: "nm", "aria-hidden": "true" }, "AUS"), h("span", { class: "vh" }, "Australia"));
  assert.deepEqual(cellWords(aus), { shown: "AUS", all: "AUS Australia" });
  assert.equal(T.testFilter({ op: "has", value: "usa" }, { text: cellWords(aus).shown }), false, "USA does not match AUS");
  assert.deepEqual(cellWords(h("span", null, "12", h("small", null, "%"))), { shown: "12%", all: "12%" }, "drawn words joined as drawn");
  REGISTRY.length = 0;
  location.hash = "#traffic/pages";
  const ccols = [{ key: "c", label: "Country", type: "text", fmt: (v) => h("span", null, h("span", { "aria-hidden": "true" }, v === "AU" ? "AUS" : "USA"), h("span", { class: "vh" }, v === "AU" ? "Australia" : "United States")) }];
  const t = table(ccols, { caption: "Countries", rows: [{ c: "US" }, { c: "AU" }], file: "c.csv", ns: false });
  const q = t.querySelector(".tbl-tools input");
  q.value = "australia";
  q.dispatchEvent(new Ev("input"));
  await new Promise((r) => setTimeout(r, 250));
  assert.equal(t.querySelectorAll("tbody tr").length, 1, "the search box still finds the full name");
  // A country column is written as two in the CSV (name and code): the button counts both.
  const { csvWidth } = await import(new URL("table.js", JS));
  assert.equal(csvWidth([{ key: "c", country: (r) => r.c }, { key: "v" }]), 3);
  assert.equal(csvWidth([{ key: "c", country: (r) => r.c, city: (r) => r.x }]), 3);
}

console.log("tables: all passed");

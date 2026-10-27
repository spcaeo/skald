// Overview's set-up line (2.41, js/tabs/ov-setup.js): it reads the checklist's own words
// ("2 of 7 left", its first open line that is not optional), says nothing once all is set
// or while the checklist is hidden, and its one button opens Settings › Set-up checklist.
//
//   node tests/js/ov-setup.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const O = await import(new URL("tabs/ov-setup.js", JS));
const { row } = await import(new URL("tabs/checklist.js", JS));

const box = (left, items, hidden = false) => {
  const b = document.createElement("section");
  b.hidden = hidden;
  const l = document.createElement("span");
  l.className = "su-left";
  l.textContent = left;
  const ol = document.createElement("ol");
  ol.append(...items.map((i) => row(i)));
  b.append(l, ol);
  return b;
};
const items = [
  { id: "logs", title: "Logs arriving", state: "done", says: "Skald reads the log." },
  { id: "search", title: "Search Console connected", state: "todo", optional: true, says: "Optional." },
  { id: "mail", title: "Get the daily mail", state: "todo", says: "One mail a day." },
  { id: "rsc", title: "Next.js pages", state: "todo", says: "Count the pages." },
];
assert.deepEqual(O.lineOf(box("2 of 7 left", items)), { left: "2 left", next: "Get the daily mail" }, "the first open line that is not optional");
assert.equal(O.lineOf(box("All set", items)), null, "all set: no line");
assert.equal(O.lineOf(box("2 of 7 left", items, true)), null, "hidden until its answers come: no line");
assert.equal(O.lineOf(null), null);
assert.equal(O.ROUTE, "settings/site/setup");

console.log("ov-setup: all passed");
process.exit(0);

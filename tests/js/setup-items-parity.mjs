// The checklist's lines from js/setup-items.js for the answers in a JSON file, so
// tests/test_setup_items.py can hold skald/setup_items.py to the same lines.
// Each case: {app (app.json's shape), status, tools, settings, waiting}; a part left
// out is passed as the page passes a failed answer (null). The model is made as
// js/adapt.js makes it (byDay from app.days).
//
//   node tests/js/setup-items-parity.mjs cases.json   -> [[{id, title, ...}, ...], ...]
import { readFileSync } from "node:fs";
import { setupItems, setupDone } from "../../skald/webapp/js/setup-items.js";

const cases = JSON.parse(readFileSync(process.argv[2], "utf8"));
const out = cases.map((c) => {
  const app = c.app || {};
  const m = { ...app, byDay: new Map((app.days || []).map((d) => [d.day, d])) };
  const items = setupItems(m, { status: c.status ?? null, tools: c.tools ?? null, settings: c.settings ?? null, waiting: c.waiting || [] });
  return { done: setupDone(items), items };
});
process.stdout.write(JSON.stringify(out));

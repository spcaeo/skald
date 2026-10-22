// Settings > Sites > Views (js/tabs/prefs.js, js/tabs/viewsfill.js): a save that
// adds page groups starts "Fill past days for the new groups" by default and
// shows its progress until it ends; with the box unticked it offers the fill
// with a button. Every answer is mocked (tests/test_views_fill.py checks the
// server's), in the shapes views_fill_api.py sends.
//
//   node tests/js/views-fill.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const REACH = { days: 9, first: "2026-10-13", last: "2026-10-21", kept_days: 10, oldest_line: "2026-10-13" };
const VIEWS = [{ slug: "security-pages", name: "Security pages" }, { slug: "free-check", name: "Free check" }];
const setting = (kind, value, label) => ({ value, kind, label, editable: true, source: "site", scope: "site", who: "admin" });
const SETTINGS = { "sites.hosts": setting("hosts", ["example.com"], "Host names"), "sites.views": setting("views", [], "Views"), "sites.timezone": setting("text", "UTC", "Time zone") };
const FILL = { site: "example.com", views: VIEWS, days: 9, done: 0, filled: 0, withheld: 0, empty: 0, first: "2026-10-13", last: "2026-10-21" };

const asked = [];
let progress = [];      // the answers GET settings/views-fill gives, one per read
let deny = false;       // a viewer: the fill's routes answer 403
globalThis.fetch = async (path, opts) => {
  const body = opts?.method === "POST" ? JSON.parse(opts.body) : null;
  asked.push([path, body]);
  const ok = (x) => ({ ok: true, status: 200, json: async () => ({ ok: true, ...x }) });
  if (path === "settings") return ok({ role: "owner", settings: SETTINGS });
  if (path === "settings/save") {
    const settings = { ...SETTINGS, "sites.views": { ...SETTINGS["sites.views"], value: body["sites.views"] } };
    return ok({ saved: ["sites.views"], settings, views: { changed: VIEWS, removed: [], can_fill: true, reach: REACH, fill: null } });
  }
  if (path === "settings/views-fill-start") return ok({ fill: { ...FILL, state: "queued" }, reach: REACH });
  if (deny && path.startsWith("settings/views-fill")) return { ok: false, status: 403, json: async () => ({ ok: false, error: "Only an admin can do this." }) };
  if (path === "settings/views-fill") return ok({ fill: progress.length > 1 ? progress.shift() : progress[0] || null, reach: REACH });
  return { ok: false, status: 404, json: async () => ({ ok: false, error: "not here" }) };
};
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const { sites } = await import(new URL("tabs/prefs.js", JS));
const vf = await import(new URL("tabs/viewsfill.js", JS));
vf.timing.poll = 5;
const tick = (ms = 30) => new Promise((r) => setTimeout(r, ms));

// The words, alone.
assert.equal(vf.reachWords(REACH), `Days before 13 Oct can't be filled: the raw log is kept 10 days. They show as "not recorded for this group", never as 0.`);
assert.ok(vf.reachWords({ days: 0 }).includes("nothing to fill"));
assert.equal(vf.stateWords({ ...FILL, state: "running", done: 4 })[0], "Filling 9 days… 4 of 9");
assert.equal(vf.stateWords({ ...FILL, state: "done", done: 9, filled: 9 })[0], "Done: 9 days filled, all audited.");
assert.equal(vf.stateWords({ ...FILL, state: "done", done: 9, filled: 8, withheld: 1 })[0],
  "Done: 8 days filled and audited; 1 day withheld: the audit's recount did not match, so it is not shown.");
assert.equal(vf.stateWords({ state: "busy" })[0], "Another fill is running on this server. Try again when it ends.");
assert.ok(vf.stateWords({ ...FILL, state: "failed", done: 3, error: "OSError: disk full" })[0].startsWith("The fill stopped after 3 of 9 days: OSError"));

async function page() {
  const root = document.createElement("div");
  document.body.append(root);
  root.append(...sites({ site: "example.com" }));
  await tick();
  return root;
}
async function saveViews(root, text) {
  const area = root.querySelectorAll("textarea").find((t) => t.id === "set-sites-views");
  assert.ok(area, "the Views box");
  area.value = text;
  const form = area.closest("form");
  for (const el of form.querySelectorAll("textarea")) el.value ??= el.textContent;
  for (const el of form.querySelectorAll("input")) el.value ??= el.getAttribute("value") ?? "";
  form.dispatchEvent(new Event("submit"));
  await tick();
}
const box = (root) => root.querySelector("section.vf");

// 1. Ticked (the default): the save starts the fill, and the page follows it.
{
  const root = await page();
  const choice = root.querySelector("label.vf-choice");
  assert.ok(choice, "the tick box sits under Views");
  assert.ok(choice.textContent.includes("Fill past days for the new groups"));
  assert.ok(choice.querySelector("input").hasAttribute("checked"), "ticked by default");
  assert.ok(box(root).hidden, "nothing to say before a save");
  progress = [{ ...FILL, state: "running", done: 4, current: "2026-10-17" }, { ...FILL, state: "running", done: 4, current: "2026-10-17" }];
  await saveViews(root, "Security pages | /security/\nFree check | /check/");
  const posted = asked.filter(([p]) => p === "settings/save").map(([, b]) => b);
  assert.deepEqual(posted.at(-1), { "sites.views": [{ name: "Security pages", path_prefix: "/security/", exclude_prefix: "" }, { name: "Free check", path_prefix: "/check/", exclude_prefix: "" }] });
  const started = asked.filter(([p]) => p === "settings/views-fill-start");
  assert.deepEqual(started.map(([, b]) => b), [{ views: ["security-pages", "free-check"] }], "started at once, for the new groups");
  const b = box(root);
  assert.ok(!b.hidden);
  assert.ok(b.textContent.includes("New groups: Security pages, Free check."), b.textContent);
  assert.ok(b.textContent.includes("Filling 9 days… 4 of 9"), b.textContent);
  assert.ok(b.textContent.includes("(counting 17 Oct)"));
  assert.ok(b.textContent.includes("Days before 13 Oct can't be filled: the raw log is kept 10 days."));
  assert.ok(!b.querySelector("progress").hidden, "a progress bar while it runs");
  progress = [{ ...FILL, state: "done", done: 9, filled: 9, finished_at: "2026-10-22T16:00:00+00:00" }];
  await tick(60);
  assert.ok(b.textContent.includes("Done: 9 days filled, all audited."), b.textContent);
  assert.ok(b.querySelector("progress").hidden, "no bar once done");
  const reads = asked.filter(([p]) => p === "settings/views-fill").length;
  await tick(40);
  assert.equal(asked.filter(([p]) => p === "settings/views-fill").length, reads, "no more reads once done");
  root.remove();
}

// 2. Unticked: the page offers the fill with a button, and starts it on a press.
{
  asked.length = 0;
  progress = [];
  const root = await page();
  const tickBox = root.querySelector("label.vf-choice input");
  tickBox.checked = false;
  tickBox.dispatchEvent(new Event("change"));
  await saveViews(root, "Security pages | /security/\nFree check | /check/");
  assert.equal(asked.filter(([p]) => p === "settings/views-fill-start").length, 0, "not started");
  const b = box(root);
  assert.ok(b.textContent.includes("The raw log holds 9 whole days (13 Oct to 21 Oct) to fill them from."), b.textContent);
  const btn = b.querySelector("button.vf-start");
  assert.equal(btn?.textContent, "Fill past days for the new groups");
  progress = [{ ...FILL, state: "done", done: 9, filled: 9 }];
  btn.dispatchEvent(new Event("click"));
  await tick(60);
  assert.equal(asked.filter(([p]) => p === "settings/views-fill-start").length, 1);
  assert.ok(b.textContent.includes("Done: 9 days filled, all audited."), b.textContent);
  root.remove();
}

// 3. Opening the page while a fill runs shows it; a viewer (403) sees nothing.
{
  progress = [{ ...FILL, state: "running", done: 2 }];
  const root = await page();
  assert.ok(box(root).textContent.includes("Filling 9 days… 2 of 9"));
  progress = [{ ...FILL, state: "done", done: 9, filled: 9 }];
  await tick(60);
  root.remove();
  deny = true;
  const seen = await page();
  assert.ok(box(seen).hidden, "a viewer sees no fill box");
  seen.remove();
}
console.log("views-fill: all passed");

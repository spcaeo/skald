// Settings › To do's list (js/settings-todo.js): which sources make a row, the order (broken,
// then waiting on you, then nice to have; the site's before the organisation's), the count's
// words ("2 left, 1 optional", "All set, 2 optional") and the one button's words.
//
//   node tests/js/settings-todo.mjs
import assert from "node:assert/strict";

const T = await import(new URL("../../skald/webapp/js/settings-todo.js", import.meta.url));
const NOW = Date.parse("2099-06-01T12:00:00Z");
const ago = (days) => new Date(NOW - days * 86400000).toISOString();

const setup = [
  { id: "logs", act: "logs", state: "todo", title: "Your server's log", says: "Your server's log cannot be read now." },
  { id: "script", act: "script", state: "done", title: "The script tag", says: "Working." },
  { id: "lead", act: "lead", state: "todo", title: "Leads", says: "No lead has arrived yet." },
  { id: "privacy", act: "privacy", state: "todo", optional: true, title: "Privacy", says: "Review what is kept." },
  { id: "note", state: "todo", title: "No dialog", says: "Nothing to open." },
];

// ---- the count and the button
assert.deepEqual(T.openLines(setup).map((i) => i.id), ["logs", "lead", "privacy"], "open lines with a dialog");
assert.equal(T.leftWords(setup), "3 left, 1 optional");
assert.equal(T.finishWords(setup), "Finish set-up (3 left)");
const onlyOptional = setup.map((i) => (i.optional ? i : { ...i, state: "done" }));
assert.equal(T.leftWords(onlyOptional), "All set, 1 optional");
assert.equal(T.finishWords(onlyOptional), "Add the optional (1)");
assert.equal(T.leftWords([]), "All set");
assert.equal(T.verbOf(setup[0]), "Fix", "a log that cannot be read: Fix");
assert.equal(T.verbOf(setup[2]), "Set up");
assert.equal(T.verbOf(setup[3]), "Review");

// ---- every source, and the order
const rows = T.todoItems({
  setup, manage: true, saas: true, accounts: true, totpOn: false, now: NOW,
  sites: [
    { name: "example.com", status: "active", verify: { state: "pending" } },
    { name: "example.org", status: "paused" },
    { name: "example.net", status: "removed", verify: { state: "pending" } },
  ],
  plan: { usage: { percent: 85 } },
  invites: [{ email: "new@example.com" }, { email: "two@example.com" }],
  tokens: [
    { name: "old", last_used: ago(120), created_at: ago(400) },
    { name: "never used", created_at: ago(30) },
    { name: "fresh", last_used: ago(2), created_at: ago(30) },
    { name: "revoked", revoked_at: ago(1), created_at: ago(400) },
  ],
});
assert.deepEqual(rows.map((x) => x.id), [
  "setup-logs", "proof-example.com",              // broken: the site's first
  "setup-lead", "paused-example.org", "usage", "totp",  // waiting on you
  "setup-privacy", "invites", "tokens",             // nice to have
]);
assert.equal(rows.find((x) => x.id === "invites").says, "2 invites are not accepted yet.");
assert.equal(rows.find((x) => x.id === "tokens").says.startsWith("2 tokens have"), true, "the unused and the never-used token");
assert.equal(rows.find((x) => x.id === "usage").says, "85% of this month's requests are used.");
assert.ok(!rows.some((x) => x.id.includes("example.net")), "a removed site is not a to do");

// a plan used up is broken; under 80% is nothing; not the paid service: no usage row
assert.equal(T.todoItems({ manage: true, saas: true, plan: { usage: { percent: 100 } } })[0].level, "bad");
assert.equal(T.todoItems({ manage: true, saas: true, plan: { usage: { percent: 79 } } }).length, 0);
assert.equal(T.todoItems({ manage: true, saas: false, plan: { usage: { percent: 99 } } }).length, 0);

// a reader who may not manage: only their own two-step sign-in
assert.deepEqual(T.todoItems({ setup, manage: false, accounts: true, totpOn: false, invites: [{}] }).map((x) => x.id), ["totp"]);
// nothing left: an empty list (the page says "Nothing needs you.")
assert.deepEqual(T.todoItems({ setup: onlyOptional.map((i) => ({ ...i, state: "done" })), manage: true, accounts: true, totpOn: true }), []);

console.log("settings-todo: all passed");

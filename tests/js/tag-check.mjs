// The script tag's set-up dialog pieces (conn-install.js, conn-tagcheck.js,
// conn-send.js testPanel): the plain tag loads from Skald; the first-party way
// is in "Advanced: serve it from your own domain" with nginx, Apache and Caddy;
// the Test, while nothing has arrived, looks at the page once per press and
// shows what is wrong in plain words; once connected the page check goes.
//
//   node tests/js/tag-check.mjs   (tests/test_tag_check.py runs it too)
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://skald.example.net", href: "https://skald.example.net/traffic/example.com/" });
const posted = [];
globalThis.fetch = async (path, opts = {}) => {
  posted.push([path, opts.body ? JSON.parse(opts.body) : null]);
  return { ok: true, status: 200, json: async () => ({ ok: true, check: { state: "problem",
    words: "The tag is on your page but posts to www.example.com/traffic-beacon, which answers 308.",
    fix: "Update to the latest tag in step 2.", facts: {} } }) };
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const install_ = await import(new URL("tabs/conn-install.js", JS));
const tc = await import(new URL("tabs/conn-tagcheck.js", JS));
const send = await import(new URL("tabs/conn-send.js", JS));
const tag = await import(new URL("tabs/setup-tag.js", JS));
const SK = "https://skald.example.net";

// ---- the plain tag and the advanced lines
{
  assert.equal(install_.plainTag(SK, "example.com"), `<script src="${SK}/traffic-js/skald.js" data-site="example.com" defer></script>`);
  const lines = install_.proxyLines(SK);
  for (const [name, text] of Object.entries(lines)) {
    assert.ok(text.includes("/traffic-beacon") && text.includes("/traffic-js/"), name);
    assert.ok(/Cookie/.test(text), `${name} drops the visitor's cookies`);
  }
  assert.match(lines.nginx, /proxy_set_header Host skald\.example\.net;/);
  assert.match(lines.nginx, /X-Forwarded-For \$remote_addr/);
  assert.match(lines.apache, /ProxyPass "https:\/\/skald\.example\.net\/traffic-beacon"/);
  assert.match(lines.caddy, /tls_server_name skald\.example\.net/);
  const fold = install_.proxyFold(SK, "example.com");
  assert.equal(fold.tagName.toLowerCase(), "details");
  assert.equal(fold.open, undefined, "folded by default");
  assert.match(fold.textContent, /Advanced: serve it from your own domain/);
  assert.match(fold.textContent, /<script src="\/traffic-js\/skald\.js" data-site="example\.com" defer><\/script>/);
  // the Connections dialog's script way: the plain tag first, nothing to change on the server
  const st = { site: "example.com", base: SK };
  const box = document.createElement("div");
  box.append(...install_.installFor("script", st));
  const text = box.textContent;
  assert.ok(text.indexOf(`src="${SK}/traffic-js/skald.js"`) < text.indexOf("Advanced: serve it"));
  assert.match(text, /Nothing changes on your web server/);
}

// ---- the mail to the developer
{
  const mail = tag.tagMail("example.com", install_.plainTag(SK, "example.com"), SK);
  assert.match(mail, /no change on the web server/);
  assert.match(mail, /skald\.example\.net and sends its events there/);
  assert.doesNotMatch(mail, /pass \/traffic-js\//);
  assert.equal(tag.skaldOf({ script: { src: `${SK}/traffic-js/skald.js` } }), SK);
}

// ---- the page check's answer in the Test's words
{
  assert.deepEqual(tc.tagVerdict({ ok: true, check: { state: "problem", words: "W", fix: "F" } }), { kind: "bad", head: "W", fix: "F" });
  assert.equal(tc.tagVerdict({ ok: true, check: { state: "ok", words: "W", fix: "" } }).kind, "ok");
  assert.equal(tc.tagVerdict({ ok: true, check: { state: "unknown", words: "W" } }).kind, "wait");
  assert.deepEqual(tc.tagVerdict({ ok: false, error: "Too many page checks. Try again in an hour." }),
    { kind: "wait", head: "Too many page checks. Try again in an hour.", fix: "" });
  assert.equal(tc.tagVerdict(null).head, "Skald could not look at your page just now.");
}

// ---- the Test: waiting -> the page is looked at once per press; connected -> it goes
{
  let answer = { ok: true, beacon: { events: 0, day: null, updated_at: null, last_open_at: null } };
  const st = { site: "example.com", method: "script" };
  const panel = send.testPanel(st, { statusOf: async () => answer });
  document.body.append(panel);
  assert.equal(posted.length, 0, "nothing is checked before Test is pressed");
  const btn = panel.querySelectorAll("button").find((b) => b.textContent === "Test connection");
  btn.click();
  await tick();
  assert.deepEqual(posted, [["sites/tagcheck", { site: "example.com" }]]);
  const page = panel.querySelectorAll("div").find((d) => d.className === "cn-test-page");
  assert.match(page.textContent, /What Skald found on your home page:/);
  assert.match(page.textContent, /posts to www\.example\.com\/traffic-beacon, which answers 308\./);
  assert.match(page.textContent, /What to do: Update to the latest tag in step 2\./);
  btn.disabled = false;
  btn.click();               // a new press: one more look (a poll never looks again)
  await tick();
  assert.equal(posted.length, 2);
  // connected: the page check is gone
  answer = { ok: true, beacon: { events: 3, day: "2026-10-22", updated_at: "2026-10-22T10:00:00Z", last_open_at: null } };
  btn.disabled = false;
  btn.click();
  await tick();
  assert.equal(page.textContent, "");
  assert.equal(posted.length, 2);
  // other ways (a log shipper) never look at the page; nor does a shared page (pageCheck: null)
  const other = send.testPanel({ site: "example.com", method: "docker" }, { statusOf: async () => ({ ok: true }) });
  other.querySelectorAll("button")[0].click();
  const shared = send.testPanel(st, { statusOf: async () => ({ ok: true, beacon: { events: 0 } }), pageCheck: null });
  shared.querySelectorAll("button")[0].click();
  await tick();
  assert.equal(posted.length, 2);
  document.body.childNodes = [];
}
console.log("tag-check: all passed");
process.exit(0);

// Behaviour of webapp/snippet/journeys.js (recorded journeys, docs/JOURNEYS.md) in a tiny
// fake page: nothing before consent, then session_started and page_view, links inside
// the page, track, consent withdrawn, Do Not Track. Every event sent is checked by
// Skald's own contract (skald/recorded/contract.py) so the two cannot drift.
// Run: node tests/js/journeys-snippet.mjs (tests/test_recorded_journeys_js.py runs it too).
// Hosts are example.com / example.org only.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { webcrypto } from "node:crypto";
import vm from "node:vm";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const SOURCE = readFileSync(`${ROOT}skald/webapp/snippet/journeys.js`, "utf8");
const UUID4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const SENT = [];          // every event body any page sent, for the contract check

function storage(start = {}) {
  const m = new Map(Object.entries(start));
  return {
    m,
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
  };
}

function page(opts = {}) {
  const loc = {};
  const go = (u) => {
    const x = new URL(u, loc.href || "https://www.example.com/");
    Object.assign(loc, { href: x.href, hostname: x.hostname, pathname: x.pathname, search: x.search });
  };
  go(opts.url || "https://www.example.com/pricing/?utm_source=News&utm_medium=email");
  const posts = [], timers = [], listeners = {};
  const attrs = { "data-relay": "/api/skald-journey", ...(opts.attrs || {}) };
  const ls = opts.ls || storage();
  const ctx = {
    document: { currentScript: { getAttribute: (k) => attrs[k] ?? null }, referrer: opts.referrer ?? "https://news.example.org/story/today?x=1" },
    navigator: { doNotTrack: opts.dnt ? "1" : undefined, globalPrivacyControl: !!opts.gpc },
    history: { state: null, pushState(_s, _t, u) { go(u); }, replaceState(_s, _t, u) { go(u); } },
    location: loc, URL, URLSearchParams, Uint8Array, Promise, JSON,
    crypto: opts.noRandomUUID ? { getRandomValues: (a) => webcrypto.getRandomValues(a) } : webcrypto,
    localStorage: ls,
    setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
    fetch: (url, init) => {
      const body = JSON.parse(init.body);
      posts.push({ url, init, body });
      if (url.endsWith("/api/skald-journey")) SENT.push(body);
      const status = (opts.statuses || []).shift() ?? 201;
      if (status === "down") return Promise.reject(new TypeError("network"));
      return Promise.resolve({ status, ok: status < 300 });
    },
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(SOURCE, ctx);
  const fire = (type, ev) => (listeners[type] || []).forEach((fn) => fn(ev));
  return { ctx, api: ctx.skaldJourneys, posts, timers, ls, loc, fire, names: () => posts.map((p) => p.body.event_name) };
}

const tick = () => new Promise((r) => setImmediate(r));

const tests = {
  "before consent: nothing stored, nothing sent"() {
    const p = page();
    p.ctx.history.pushState({}, "", "/features/");
    assert.equal(p.api.track("cta_click", { label: "Hero" }), false);
    assert.equal(p.posts.length, 0);
    assert.equal(p.ls.m.size, 0);
    assert.equal(p.api.state().consent, false);
  },
  "consent: session_started with the touch, then page_view, the same ids"() {
    const p = page();
    p.api.consent(true);
    assert.deepEqual(p.names(), ["session_started", "page_view"]);
    const [s, v] = p.posts.map((x) => x.body);
    assert.deepEqual(s.touch, { landing_path: "/pricing", referrer: { host: "news.example.org", path: "/story/today" },
      utm_source: "News", utm_medium: "email" });
    assert.equal(v.touch, undefined);
    for (const e of [s, v]) {
      assert.equal(e.schema_version, 1);
      assert.match(e.event_id, UUID4);
      assert.match(e.visitor_id, UUID4);
      assert.match(e.session_id, UUID4);
      assert.match(e.occurred_at, /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/);
      assert.ok(Math.abs(Date.parse(e.occurred_at) - Date.now()) < 5000);
      assert.equal(e.path, "/pricing");
      assert.deepEqual(e.consent, { analytics: "granted" });
      assert.equal(e.ip, undefined);
    }
    assert.notEqual(s.event_id, v.event_id);
    assert.equal(s.visitor_id, v.visitor_id);
    assert.equal(s.session_id, v.session_id);
    const init = p.posts[0].init;
    assert.equal(p.posts[0].url, "/api/skald-journey");
    assert.deepEqual([init.method, init.keepalive, init.credentials, init.headers["Content-Type"]],
      ["POST", true, "same-origin", "application/json"]);
    assert.equal(p.ls.getItem("skald.j.v"), s.visitor_id);
    assert.equal(p.ls.getItem("skald.j.c"), "1");
    assert.equal(p.ls.getItem("skald.j.s").split("|")[0], s.session_id);
    assert.deepEqual({ ...p.api.state() }, { consent: true, visitor_id: s.visitor_id, session_id: s.session_id, notice: null });
  },
  "a referrer on the same site is not a touch; the notice version is sent"() {
    const p = page({ referrer: "https://example.com/blog/", attrs: { "data-notice": "v2" }, url: "https://www.example.com/" });
    p.api.consent(true);
    assert.deepEqual(p.posts[0].body.touch, { landing_path: "/" });
    assert.deepEqual(p.posts[1].body.consent, { analytics: "granted", notice_version: "v2" });
    assert.equal(p.ls.getItem("skald.j.c"), "v2");
  },
  "a part of the path that may name a person becomes -"() {
    const p = page({ url: "https://www.example.com/orders/12345678/view?id=9" });
    p.api.consent(true);
    assert.equal(p.posts[1].body.path, "/orders/-/view");
  },
  "links inside the page: one page_view per new path"() {
    const p = page({ noRandomUUID: true });
    p.api.consent(true);
    p.ctx.history.pushState({}, "", "/features/?a=1");
    p.ctx.history.replaceState({}, "", "/features");      // same path: nothing new
    p.loc.pathname = "/pricing/";
    p.fire("popstate", {});
    assert.deepEqual(p.posts.map((x) => [x.body.event_name, x.body.path]),
      [["session_started", "/pricing"], ["page_view", "/pricing"], ["page_view", "/features"], ["page_view", "/pricing"]]);
    assert.ok(p.posts.every((x) => UUID4.test(x.body.event_id)));
  },
  "track: known names only, the email on the allowed events only"() {
    const p = page();
    p.api.consent(true);
    assert.equal(p.api.track("cta_click", { label: "Pricing hero" }), true);
    assert.equal(p.api.track("page_view"), false);
    assert.equal(p.api.track("session_started"), false);
    assert.equal(p.api.track("purchase"), false);
    p.api.track("download", { label: "Guide", email: "pat@example.com" });
    p.api.track("form_sent", { label: "Contact", email: " pat@example.com " });
    p.api.track("signup", { label: "call me on 5550100200", email: "not an email" });
    const got = p.posts.slice(2).map((x) => x.body);
    assert.deepEqual(got.map((e) => [e.event_name, e.label, e.email]),
      [["cta_click", "Pricing hero", undefined], ["download", "Guide", undefined],
       ["form_sent", "Contact", "pat@example.com"], ["signup", undefined, undefined]]);
  },
  "the script tag's visitor ID goes with each event when it is valid"() {
    const p = page({ ls: storage({ "skald.vid": "skv_" + "a".repeat(22) }) });
    p.api.consent(true);
    assert.ok(p.posts.every((x) => x.body.skald_vid === "skv_" + "a".repeat(22)));
    const q = page({ ls: storage({ "skald.vid": "skv_short" }) });
    q.api.consent(true);
    assert.ok(q.posts.every((x) => x.body.skald_vid === undefined));
  },
  "consent remembered: the next page sends page_view in the same session"() {
    const p = page();
    p.api.consent(true);
    const first = p.posts[1].body;
    const q = page({ ls: p.ls, url: "https://www.example.com/docs/" });
    assert.deepEqual(q.names(), ["page_view"]);
    assert.equal(q.posts[0].body.visitor_id, first.visitor_id);
    assert.equal(q.posts[0].body.session_id, first.session_id);
  },
  "a new notice version asks again; data-consent starts at once"() {
    const p = page({ attrs: { "data-notice": "v1" } });
    p.api.consent(true);
    const q = page({ ls: p.ls, attrs: { "data-notice": "v2" } });
    assert.equal(q.posts.length, 0);
    const r = page({ attrs: { "data-consent": "granted" } });
    assert.deepEqual(r.names(), ["session_started", "page_view"]);
  },
  "30 minutes idle: a new session"() {
    const p = page();
    p.api.consent(true);
    const old = p.posts[0].body.session_id;
    p.ls.setItem("skald.j.s", `${old}|${Date.now() - 31 * 60 * 1000}`);
    p.api.track("cta_click", { label: "Later" });
    const [s, c] = p.posts.slice(2).map((x) => x.body);
    assert.equal(s.event_name, "session_started");
    assert.deepEqual(s.touch, { landing_path: "/pricing" });
    assert.notEqual(s.session_id, old);
    assert.equal(c.session_id, s.session_id);
    assert.equal(c.visitor_id, p.posts[0].body.visitor_id);
  },
  "consent(false) clears every key it wrote and stops"() {
    const p = page({ ls: storage({ "skald.vid": "skv_" + "b".repeat(22) }) });
    p.api.consent(true);
    p.api.consent(false);
    assert.deepEqual([...p.ls.m.keys()], ["skald.vid"]);
    const before = p.posts.length;
    p.ctx.history.pushState({}, "", "/other");
    p.api.track("cta_click");
    assert.equal(p.posts.length, before);
    assert.equal(p.api.state().consent, false);
  },
  async "withdraw posts the visitor ID to the withdraw route and clears"() {
    const p = page();
    p.api.consent(true);
    const vid = p.posts[0].body.visitor_id;
    assert.equal(await p.api.withdraw(), true);
    const last = p.posts.at(-1);
    assert.equal(last.url, "/api/skald-journey/withdraw");
    assert.deepEqual(last.body, { visitor_id: vid });
    assert.equal(p.ls.m.size, 0);
    p.ctx.history.pushState({}, "", "/after");
    assert.equal(p.posts.length, 3);
    const q = page({ attrs: { "data-withdraw": "/elsewhere" }, statuses: [201, 201, 500] });
    q.api.consent(true);
    assert.equal(await q.api.withdraw(), false);
    assert.equal(q.posts.at(-1).url, "/elsewhere");
  },
  async "429, 5xx or no network: once more with the same body; other 4xx never"() {
    const p = page({ statuses: [429, "down", 400] });
    p.api.consent(true);
    p.api.track("cta_click", { label: "Hero" });
    await tick();
    assert.equal(p.timers.length, 2);
    assert.ok(p.timers.every((t) => t.ms >= 1000));
    p.timers.forEach((t) => t.fn());
    assert.equal(p.posts[3].init.body, p.posts[0].init.body);
    assert.equal(p.posts[4].init.body, p.posts[1].init.body);
    const q = page({ statuses: [503, 503, 503, 503] });
    q.api.consent(true);
    await tick();
    q.timers.splice(0).forEach((t) => t.fn());
    await tick();
    assert.equal(q.timers.length, 0);               // a retry is never retried
  },
  async "Do Not Track or Global Privacy Control: nothing at all"() {
    for (const o of [{ dnt: true }, { gpc: true }]) {
      const p = page({ ...o, attrs: { "data-consent": "granted" } });
      p.api.consent(true);
      p.api.track("cta_click");
      p.ctx.history.pushState({}, "", "/x");
      assert.equal(await p.api.withdraw(), false);
      assert.equal(p.posts.length, 0);
      assert.equal(p.ls.m.size, 0);
    }
  },
  "calls queued before the script loaded run after it"() {
    const ctxQ = { q: [["consent", true], ["track", "download", { label: "Guide" }]] };
    const loc = {};
    // A page that queued before load: skaldJourneys.q is set; no script attributes at all.
    const posts = [];
    const ctx = {
      skaldJourneys: ctxQ, document: { currentScript: null, referrer: "" }, navigator: {},
      history: { pushState() {}, replaceState() {} }, location: Object.assign(loc, { href: "https://www.example.com/", hostname: "www.example.com", pathname: "/", search: "" }),
      URL, URLSearchParams, Uint8Array, crypto: webcrypto, localStorage: storage(), setTimeout: () => 0,
      fetch: (url, init) => { posts.push({ url, body: JSON.parse(init.body) }); SENT.push(JSON.parse(init.body)); return Promise.resolve({ status: 201, ok: true }); },
      addEventListener() {},
    };
    ctx.window = ctx;
    vm.createContext(ctx);
    vm.runInContext(SOURCE, ctx);
    assert.deepEqual(posts.map((x) => [x.url, x.body.event_name]),
      [["/api/skald-journey", "session_started"], ["/api/skald-journey", "page_view"], ["/api/skald-journey", "download"]]);
  },
};

// Skald's own contract on every body sent above.
function contractCheck() {
  const code = [
    "import json, sys",
    "from datetime import datetime, timezone",
    "from skald.recorded.contract import validate, Invalid",
    "now = datetime.now(timezone.utc)",
    "bad = []",
    "for i, e in enumerate(json.load(sys.stdin)):",
    "    try:",
    "        validate(e, now)",
    "    except Invalid as why:",
    "        bad.append(f'{i} {e.get(\"event_name\")} {why.field}: {why}')",
    "print('\\n'.join(bad)); sys.exit(1 if bad else 0)",
  ].join("\n");
  const got = spawnSync("python3", ["-c", code], { cwd: ROOT, input: JSON.stringify(SENT), encoding: "utf8" });
  assert.equal(got.status, 0, got.stdout + got.stderr);
  assert.ok(SENT.length > 20, `only ${SENT.length} events were checked`);
}

let failed = 0;
for (const [name, fn] of Object.entries(tests)) {
  try { await fn(); console.log(`ok   ${name}`); } catch (e) { failed++; console.log(`FAIL ${name}\n${e.stack}`); }
}
try { contractCheck(); console.log(`ok   every event sent (${SENT.length}) passes contract.validate`); }
catch (e) { failed++; console.log(`FAIL the contract check\n${e.stack}`); }
console.log(failed ? `${failed} failed` : `all ${Object.keys(tests).length + 1} passed`);
process.exitCode = failed ? 1 : 0;

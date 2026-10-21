// Behaviour of beacon/skald.js (beacon-only mode, docs/BEACON.md) in a tiny fake DOM:
// one page view per page opening - on load, on a link inside the page (pushState and
// replaceState), on back/forward (popstate) and on a page restored from the
// back-forward cache (pageshow, persisted). Run: node tests/js/skald-beacon-only.mjs
// (tests/test_beacon.py runs it too). Hosts are example.com / example.org only.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const SOURCE = readFileSync(fileURLToPath(new URL("../../beacon/skald.js", import.meta.url)), "utf8");

function page(opts = {}) {
  const loc = {};
  const go = (u) => {
    const x = new URL(u, loc.href || "https://www.example.com/pricing/");
    Object.assign(loc, { href: x.href, hostname: x.hostname, pathname: x.pathname, search: x.search });
  };
  go(opts.url || "https://www.example.com/pricing/");
  const sent = [], listeners = {};
  const ctx = {
    document: { currentScript: { dataset: opts.endpoint ? { endpoint: opts.endpoint } : {} }, referrer: opts.referrer || "" },
    navigator: { doNotTrack: opts.dnt ? "1" : undefined, sendBeacon(u, blob) { sent.push({ url: u, body: JSON.parse(blob.text) }); return true; } },
    history: { state: null, pushState(_s, _t, u) { go(u); }, replaceState(_s, _t, u) { go(u); } },
    location: loc, innerWidth: 1200, URL, URLSearchParams,
    Blob: class { constructor(parts, o) { this.text = parts.join(""); this.type = o.type; } },
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(SOURCE, ctx);
  const fire = (type, ev) => (listeners[type] || []).forEach((fn) => fn(ev));
  return { ctx, sent, loc, fire, paths: () => sent.map((s) => s.body.p) };
}

const tests = {
  "a page view on load, with the source"() {
    const p = page({ url: "https://www.example.com/pricing/?utm_source=News", referrer: "https://www.example.org/a" });
    assert.equal(p.sent.length, 1);
    assert.equal(p.sent[0].url, "/traffic-beacon");
    assert.deepEqual({ e: p.sent[0].body.e, p: p.sent[0].body.p, r: p.sent[0].body.r, u: p.sent[0].body.u },
      { e: "page_view", p: "/pricing/", r: "example.org", u: "news" });
  },
  "links inside the page and back/forward: one page view per new path"() {
    const p = page({ endpoint: "/beacon-here" });
    p.ctx.history.pushState({}, "", "/features/");
    p.ctx.history.replaceState({}, "", "/features/");     // same path: nothing new
    p.ctx.history.replaceState({}, "", "/docs/");         // a router that replaces: a new page
    p.loc.pathname = "/pricing/";
    p.fire("popstate", {});
    assert.deepEqual(p.paths(), ["/pricing/", "/features/", "/docs/", "/pricing/"]);
    assert.ok(p.sent.every((s) => s.url === "/beacon-here"));
  },
  "a page restored from the back-forward cache is opened again"() {
    const p = page();
    p.fire("pageshow", { persisted: false });             // the ordinary load: counted already
    assert.equal(p.sent.length, 1);
    p.fire("pageshow", { persisted: true });
    assert.deepEqual(p.paths(), ["/pricing/", "/pricing/"]);
    assert.equal(p.sent[1].body.t, 0);
  },
  "Do Not Track: nothing at all"() {
    const p = page({ dnt: true });
    p.ctx.history.pushState({}, "", "/features/");
    p.fire("pageshow", { persisted: true });
    assert.equal(p.sent.length, 0);
  },
};

let failed = 0;
for (const [name, fn] of Object.entries(tests)) {
  try { fn(); console.log(`ok   ${name}`); } catch (e) { failed++; console.log(`FAIL ${name}\n${e.stack}`); }
}
console.log(failed ? `${failed} failed` : `all ${Object.keys(tests).length} passed`);
process.exitCode = failed ? 1 : 0;

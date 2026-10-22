// Behaviour of skald/webapp/snippet/skald.js in a tiny fake DOM.
// Run: node tests/js/skald-snippet.mjs  (tests/test_snippet.py runs it too).
// Hosts are example.com / example.org; nothing here is real.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const FILE = fileURLToPath(new URL("../../skald/webapp/snippet/skald.js", import.meta.url));
const SOURCE = readFileSync(FILE, "utf8");
const VID = /^skv_[A-Za-z0-9_-]{22}$/;

class Store {
  constructor() { this.m = new Map(); }
  getItem(k) { return this.m.has(k) ? this.m.get(k) : null; }
  setItem(k, v) { this.m.set(k, String(v)); }
  removeItem(k) { this.m.delete(k); }
}

function el(tag, attrs = {}, parent = null) {
  return {
    tagName: tag.toUpperCase(), attrs, parentNode: parent, nodeType: 1,
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    setAttribute(k, v) { this.attrs[k] = String(v); },
  };
}

function page(opts = {}) {
  const url = new URL(opts.url || "https://www.example.com/pricing/");
  const loc = {};
  const go = (u) => {
    const x = new URL(u, loc.href || url.href);
    Object.assign(loc, { href: x.href, hostname: x.hostname, pathname: x.pathname,
      search: x.search, hash: x.hash, protocol: x.protocol, origin: x.origin });
  };
  go(url.href);
  const sent = [], fetched = [], cookies = new Map(), cookieWrites = [];
  const listeners = { doc: {}, win: {} };
  const add = (where) => (type, fn) => { (listeners[where][type] ||= []).push(fn); };
  const embeds = opts.embeds || [];
  const script = el("script", { src: opts.src || "/traffic-js/skald.js", ...(opts.attrs || {}) });
  // As in a browser: the element's src property is the absolute address.
  script.src = new URL(script.attrs.src, url.href).href;
  const document = {
    currentScript: script, referrer: opts.referrer || "", readyState: "complete",
    documentElement: Object.assign(el("html"), { scrollHeight: opts.height || 4000 }),
    addEventListener: add("doc"),
    querySelectorAll: () => embeds,
    // Only the not-found marker is asked for one at a time.
    querySelector: (sel) => (sel === '[data-skald="404"]' && opts.notFound ? el("body") : null),
    get cookie() { return [...cookies].map(([k, v]) => `${k}=${v}`).join("; "); },
    set cookie(text) {
      cookieWrites.push(text);
      const [pair] = text.split(";");
      const [k, v] = pair.split("=");
      if (/max-age=0(;|$)/.test(text)) cookies.delete(k); else cookies.set(k, v);
    },
  };
  for (const [k, v] of Object.entries(opts.cookies || {})) cookies.set(k, v);
  const navigator = {
    doNotTrack: opts.dnt ? "1" : undefined, globalPrivacyControl: !!opts.gpc,
    sendBeacon(u, blob) {
      if (opts.noBeacon) return false;
      sent.push({ url: u, type: blob.type, body: JSON.parse(blob.text) });
      return true;
    },
  };
  const replaced = [];
  const history = {
    state: null,
    pushState(_s, _t, u) { go(u); }, replaceState(_s, _t, u) { replaced.push(u); go(u); },
  };
  const ctx = {
    document, navigator, history, location: loc, innerWidth: 1200, innerHeight: 800, scrollY: 0,
    localStorage: new Store(), sessionStorage: new Store(),
    URL, URLSearchParams, btoa, crypto: globalThis.crypto,
    Blob: class { constructor(parts, o) { this.text = parts.join(""); this.type = o.type; } },
    fetch: (u, init) => { fetched.push({ url: u, init, body: JSON.parse(init.body) });
      return Promise.resolve(); },
    MutationObserver: class { constructor(fn) { this.fn = fn; } observe() {} },
    setTimeout: (fn) => { fn(); return 1; }, clearTimeout: () => {},
    addEventListener: add("win"),
  };
  ctx.window = ctx;
  if (opts.queue) ctx.skald = Object.assign(() => {}, { q: opts.queue });
  if (opts.storage) for (const [k, v] of Object.entries(opts.storage)) ctx.localStorage.setItem(k, v);
  vm.createContext(ctx);
  vm.runInContext(opts.source || SOURCE, ctx);
  const fire = (where, type, ev) => (listeners[where][type] || []).forEach((fn) => fn(ev));
  return {
    ctx, sent, fetched, cookies, cookieWrites, loc, replaced,
    names: () => sent.map((s) => s.body.e),
    last: () => sent[sent.length - 1].body,
    doc: (type, target) => fire("doc", type, { target }),
    message: (origin, data) => fire("win", "message", { origin, data }),
    scroll: (y) => { ctx.scrollY = y; fire("win", "scroll", {}); },
    copy: () => fire("doc", "copy", {}),
    popstate: () => fire("win", "popstate", {}),
    pageshow: (persisted) => fire("win", "pageshow", { persisted }),
  };
}

const tests = {
  "page view on load, with the ID and the visit's source"() {
    const p = page({ url: "https://www.example.com/pricing/?utm_source=Newsletter&x=1",
      referrer: "https://www.google.com/search" });
    assert.deepEqual(p.names(), ["page_view"]);
    const b = p.last();
    assert.equal(p.sent[0].url, "/traffic-beacon");
    assert.equal(p.sent[0].type, "text/plain");
    assert.equal(b.p, "/pricing/");
    assert.equal(b.r, "google.com");
    assert.equal(b.u, "newsletter");
    assert.equal(b.vw, "lg");
    assert.match(b.v, VID);
    assert.equal(p.ctx.localStorage.getItem("skald.vid"), b.v);
    assert.equal(p.cookieWrites.length, 0);
    assert.equal(p.ctx.skald("id"), b.v);
  },
  "an existing ID is kept"() {
    const old = "skv_" + "Z".repeat(22);
    const p = page({ storage: { "skald.vid": old } });
    assert.equal(p.last().v, old);
  },
  "SPA navigation sends one page view per new path"() {
    const p = page({ referrer: "https://news.example.org/" });
    p.ctx.history.pushState({}, "", "/features/");
    p.ctx.history.replaceState({}, "", "/features/");
    p.ctx.history.pushState({}, "", "/features/?tab=2");
    p.loc.pathname = "/pricing/";
    p.popstate();
    assert.deepEqual(p.sent.map((s) => s.body.p), ["/pricing/", "/features/", "/pricing/"]);
    assert.ok(p.sent.every((s) => s.body.r === "news.example.org"));
    assert.equal(new Set(p.sent.map((s) => s.body.v)).size, 1);
  },
  "a page restored from the back-forward cache is a page opening again"() {
    const p = page();
    p.pageshow(false);                  // an ordinary load: already counted
    assert.deepEqual(p.names(), ["page_view"]);
    p.pageshow(true);                   // back to it from the cache: no load, no HTML request
    assert.deepEqual(p.names(), ["page_view", "page_view"]);
    assert.deepEqual(p.sent.map((s) => s.body.p), ["/pricing/", "/pricing/"]);
    assert.equal(p.last().t, 0);        // its time on the page starts again
    p.ctx.history.pushState({}, "", "/features/");
    p.pageshow(true);
    assert.deepEqual(p.sent.map((s) => s.body.p), ["/pricing/", "/pricing/", "/features/", "/features/"]);
  },
  "no page opening from the cache without consent or with Do Not Track"() {
    const p = page({ attrs: { "data-consent": "required" } });
    p.pageshow(true);
    assert.equal(p.sent.length, 0);
    const q = page({ dnt: true });
    q.pageshow(true);
    assert.equal(q.sent.length, 0);
  },
  "forms: start once per form per page, submit, never a value"() {
    const p = page();
    const form = el("form", { id: "Contact Us" });
    const input = Object.assign(el("input", { name: "email" }, form), { form,
      value: "person@example.com" });
    const signup = el("form", { name: "trial", "data-skald": "signup" });
    const search = el("form", { role: "search" });
    const off = el("form", { "data-skald": "off" });
    p.doc("focusin", input);
    p.doc("focusin", input);
    p.doc("submit", form);
    p.doc("focusin", el("input", {}, el("div", {}, signup)));
    p.doc("submit", signup);
    p.doc("focusin", el("input", {}, search));
    p.doc("focusin", el("input", {}, off));
    p.doc("focusin", el("input", {}, el("div")));
    p.ctx.history.pushState({}, "", "/other/");
    p.doc("focusin", input);
    assert.deepEqual(p.names(), ["page_view", "form_start", "form_submit", "signup_start",
      "signup_submit", "page_view", "form_start"]);
    assert.deepEqual(p.sent.slice(1, 5).map((s) => s.body.id),
      ["contact_us", "contact_us", "trial", "trial"]);
    const all = JSON.stringify(p.sent);
    assert.ok(!all.includes("person@example.com"));
    for (const s of p.sent) {
      for (const k of Object.keys(s.body)) assert.ok(["e", "p", "vw", "t", "id", "r", "u", "v"].includes(k), k);
    }
  },
  "clicks: tel, mailto, outbound, CTA, IDs on links"() {
    const p = page({ attrs: { "data-link-domains": "app.example.net, shop.example.org" } });
    const v = p.ctx.skald("id");
    const a = (href, attrs = {}, parent = null) => Object.assign(el("a", attrs, parent), { href });
    p.doc("click", a("tel:+15550100"));
    p.doc("click", a("mailto:hello@example.com"));
    const out = a("https://www.other.example.org/page");
    p.doc("click", out);
    const app = a("https://app.example.net/signup?plan=pro");
    p.doc("click", el("span", {}, app));
    const cal = a("https://calendly.com/acme/demo");
    p.doc("click", cal);
    const tagged = a("https://calendly.com/acme/demo?utm_content=spring");
    p.doc("click", tagged);
    p.doc("click", el("span", {}, el("button", { "data-skald-cta": "Book Demo Header" })));
    p.doc("click", a("https://www.example.com/pricing/"));
    assert.deepEqual(p.names(), ["page_view", "tel_click", "mailto_click", "outbound_click",
      "outbound_click", "outbound_click", "outbound_click", "cta_click"]);
    assert.equal(p.sent[1].body.id, undefined);
    assert.equal(p.sent[3].body.id, "other.example.org");
    assert.equal(p.sent[7].body.id, "book_demo_header");
    assert.equal(out.href, "https://www.other.example.org/page");
    assert.equal(new URL(app.href).searchParams.get("skv"), v);
    assert.equal(new URL(app.href).searchParams.get("plan"), "pro");
    assert.equal(new URL(cal.href).searchParams.get("utm_content"), v);
    assert.equal(new URL(tagged.href).searchParams.get("utm_content"), "spring");
  },
  "embed messages only from their own origins"() {
    const p = page();
    p.message("https://calendly.com", { event: "calendly.event_type_viewed" });
    p.message("https://calendly.com", { event: "calendly.date_and_time_selected" });
    p.message("https://calendly.com", { event: "calendly.event_scheduled", payload: {} });
    p.message("https://calendly.com", { event: "calendly.page_height" });
    p.message("https://calendly.com", "a string");
    p.message("https://evil.example.org", { event: "calendly.event_scheduled" });
    p.message("https://app.cal.com", { type: "linkReady" });
    p.message("https://app.cal.com", { type: "bookingSuccessfulV2", data: {} });
    p.message("https://app.cal.com", { type: "__dimensionChanged" });
    p.message("https://meetings.hubspot.com", { meetingBookSucceeded: true, meetingsPayload: {} });
    p.message("https://meetings.hubspot.com", { height: 600 });
    p.message("https://meetings.hubspot.com.evil.example.org", { meetingBookSucceeded: true });
    p.message("https://example.com", null);
    assert.deepEqual(p.names(), ["page_view", "calendly_open", "calendly_time_selected",
      "calendly_booked", "cal_open", "cal_booked", "hubspot_meeting_booked"]);
  },
  "Calendly embeds get the ID as utm_content"() {
    const frame = el("iframe", { src: "https://calendly.com/acme/demo?hide_gdpr_banner=1" });
    const widget = el("div", { "data-url": "https://calendly.com/acme/demo" });
    const own = el("iframe", { src: "https://calendly.com/acme/demo?utm_content=spring" });
    const p = page({ embeds: [frame, widget, own] });
    const v = p.ctx.skald("id");
    assert.equal(new URL(frame.attrs.src).searchParams.get("utm_content"), v);
    assert.equal(new URL(frame.attrs.src).searchParams.get("hide_gdpr_banner"), "1");
    assert.equal(new URL(widget.attrs["data-url"]).searchParams.get("utm_content"), v);
    assert.equal(own.attrs.src, "https://calendly.com/acme/demo?utm_content=spring");
  },
  "contact and early-access forms send their own submit"() {
    const p = page();
    const contact = el("form", { id: "contact", "data-skald": "contact" });
    const wait = el("form", { id: "early", "data-skald": "waitlist" });
    p.doc("focusin", el("input", {}, contact));
    p.doc("submit", contact);
    p.doc("focusin", el("input", {}, wait));
    p.doc("submit", wait);
    assert.deepEqual(p.names(), ["page_view", "form_start", "contact_submit", "form_start",
      "waitlist_submit"]);
    assert.deepEqual(p.sent.slice(1).map((s) => s.body.id), ["contact", "contact", "early", "early"]);
  },
  "read three quarters and copied text: once per page, never the text"() {
    const p = page({ height: 4000 });
    p.scroll(1000);                        // 1000 + 800 < 3000
    p.scroll(2300);                        // 2300 + 800 >= 3000
    p.scroll(3200);
    p.copy();
    p.copy();
    assert.deepEqual(p.names(), ["page_view", "scroll_75", "copy_text"]);
    p.ctx.history.pushState({}, "", "/next/");
    p.scroll(3200);
    p.copy();
    assert.deepEqual(p.names().slice(3), ["page_view", "scroll_75", "copy_text"]);
    assert.ok(p.sent.every((s) => !("id" in s.body)));
  },
  "a page marked data-skald=404 sends 404_view once"() {
    const p = page({ notFound: true });
    assert.deepEqual(p.names(), ["page_view", "404_view"]);
    p.ctx.history.replaceState({}, "", "/pricing/");
    assert.deepEqual(p.names(), ["page_view", "404_view"]);
    assert.deepEqual(page().names(), ["page_view"]);
  },
  "an ID from another of your domains is adopted and taken out of the address"() {
    const theirs = "skv_" + "A".repeat(22);
    const old = "skv_" + "Z".repeat(22);
    // data-accept-id="true": adopted, even over an ID this browser had here.
    let p = page({ url: `https://app.example.net/signup?plan=pro&skv=${theirs}#top`,
      attrs: { "data-accept-id": "true" }, storage: { "skald.vid": old } });
    assert.equal(p.last().v, theirs);
    assert.equal(p.ctx.localStorage.getItem("skald.vid"), theirs);
    assert.equal(p.loc.href, "https://app.example.net/signup?plan=pro#top");
    assert.deepEqual(p.names(), ["page_view"]);
    // The referrer is one of the tag's own data-link-domains.
    p = page({ url: `https://app.example.net/?skv=${theirs}`, referrer: "https://www.example.com/pricing/",
      attrs: { "data-link-domains": "example.com" } });
    assert.equal(p.last().v, theirs);
    assert.equal(p.loc.href, "https://app.example.net/");
    // Neither: the ID is not taken, the address is left alone.
    p = page({ url: `https://app.example.net/?skv=${theirs}`, referrer: "https://news.example.org/" });
    assert.notEqual(p.last().v, theirs);
    assert.equal(p.replaced.length, 0);
    // Not an ID: ignored.
    p = page({ url: "https://app.example.net/?skv=skv_short", attrs: { "data-accept-id": "true" } });
    assert.notEqual(p.last().v, "skv_short");
    assert.equal(p.replaced.length, 0);
    // Waiting for consent: nothing kept until consent, then the adopted ID.
    p = page({ url: `https://app.example.net/?skv=${theirs}`,
      attrs: { "data-accept-id": "true", "data-consent": "required" } });
    assert.equal(p.sent.length + p.ctx.localStorage.m.size, 0);
    assert.equal(p.loc.search, "");
    p.ctx.skald("consent", true);
    assert.equal(p.last().v, theirs);
    p.ctx.skald("consent", false);
    p.ctx.skald("consent", true);
    assert.notEqual(p.last().v, theirs);
    // Visitor IDs off: the address is cleaned, nothing is kept.
    p = page({ source: SOURCE.replace("IDS=1", "IDS=0"), url: `https://app.example.net/?skv=${theirs}`,
      attrs: { "data-accept-id": "true" } });
    assert.ok(!("v" in p.last()));
    assert.equal(p.ctx.localStorage.m.size, 0);
  },
  "Do Not Track and GPC: no ID, no beacon"() {
    for (const o of [{ dnt: true }, { gpc: true }]) {
      const frame = el("iframe", { src: "https://calendly.com/acme/demo" });
      const p = page({ ...o, embeds: [frame] });
      p.ctx.skald("track", "cta_click", { id: "x" });
      p.ctx.skald("consent", true);
      p.message("https://calendly.com", { event: "calendly.event_scheduled" });
      assert.equal(p.sent.length, 0);
      assert.equal(p.ctx.skald("id"), null);
      assert.equal(p.ctx.localStorage.m.size, 0);
      assert.equal(p.ctx.sessionStorage.m.size, 0);
      assert.equal(p.cookieWrites.length, 0);
      assert.equal(frame.attrs.src, "https://calendly.com/acme/demo");
    }
  },
  "consent required: nothing until consent, everything gone on withdrawal"() {
    const a = (href) => Object.assign(el("a"), { href });
    const p = page({ attrs: { "data-consent": "required", "data-share-subdomains": "true" },
      referrer: "https://www.google.com/" });
    p.doc("focusin", el("input", {}, el("form", { id: "contact" })));
    const link = a("https://calendly.com/acme/demo");
    p.doc("click", link);
    assert.equal(p.sent.length, 0);
    assert.equal(p.ctx.skald("id"), null);
    assert.equal(link.href, "https://calendly.com/acme/demo");
    assert.equal(p.ctx.localStorage.m.size + p.ctx.sessionStorage.m.size + p.cookies.size, 0);
    p.ctx.skald("consent", true);
    assert.deepEqual(p.names(), ["page_view"]);
    const v = p.ctx.skald("id");
    assert.match(v, VID);
    assert.equal(p.cookies.get("skald_vid"), v);
    p.ctx.skald("consent", false);
    assert.equal(p.ctx.localStorage.getItem("skald.vid"), null);
    assert.equal(p.cookies.has("skald_vid"), false);
    p.ctx.skald("track", "cta_click");
    assert.equal(p.sent.length, 1);
  },
  "shared cookie on the registrable domain"() {
    for (const [url, site, want] of [
      ["https://www.example.com/", "", "domain=example.com"],
      ["https://app.example.com/", "", "domain=example.com"],
      ["https://www.example.co.uk/", "", "domain=example.co.uk"],
      ["https://shop.example.com.au/", "", "domain=example.com.au"],
      ["https://a.b.example.org/", "b.example.org", "domain=b.example.org"],
      ["https://www.example.com/", "other.example.org", "domain=example.com"],
    ]) {
      const attrs = { "data-share-subdomains": "true" };
      if (site) attrs["data-site"] = site;
      const p = page({ url, attrs });
      assert.ok(p.cookieWrites[0].includes(";" + want + ";"), url + " " + p.cookieWrites[0]);
      assert.ok(p.cookieWrites[0].includes("samesite=lax"));
    }
    const shared = "skv_" + "S".repeat(22);
    const p = page({ url: "https://app.example.com/", attrs: { "data-share-subdomains": "true" },
      cookies: { skald_vid: shared }, storage: { "skald.vid": "skv_" + "L".repeat(22) } });
    assert.equal(p.last().v, shared);
    assert.equal(p.ctx.localStorage.getItem("skald.vid"), shared);
  },
  "queued calls, the public API, the older call form"() {
    const p = page({ queue: [["track", "signup_submit", { id: "Hero Form" }]] });
    p.ctx.skald("cta_click", "pricing_top");
    p.ctx.skald("track", "Calendly Booked");
    assert.deepEqual(p.names(), ["page_view", "signup_submit", "cta_click", "calendly_booked"]);
    assert.equal(p.sent[1].body.id, "hero_form");
    assert.equal(p.sent[2].body.id, "pricing_top");
    assert.equal(p.ctx.skald("consent", true), undefined);
  },
  "other endpoint, and fetch keepalive when sendBeacon says no"() {
    const p = page({ noBeacon: true, attrs: { "data-endpoint": "/stats/beacon" } });
    assert.equal(p.sent.length, 0);
    assert.equal(p.fetched.length, 1);
    assert.equal(p.fetched[0].url, "/stats/beacon");
    assert.equal(p.fetched[0].init.keepalive, true);
    assert.equal(p.fetched[0].body.e, "page_view");
  },
  "loaded from Skald's own address: posts there, beside the script"() {
    const p = page({ src: "https://skald.example.net/traffic-js/skald.js" });
    assert.deepEqual(p.sent.map((s) => [s.url, s.type]),
      [["https://skald.example.net/traffic-beacon", "text/plain"]]);
    // the ID stays the page's own: its storage, no cookie unless shared subdomains
    assert.match(p.last().v, VID);
    assert.equal(p.ctx.localStorage.getItem("skald.vid"), p.last().v);
    assert.equal(p.cookieWrites.length, 0);
    const q = page({ src: "https://skald.example.net/traffic-js/skald.js",
      attrs: { "data-share-subdomains": "true" } });
    assert.ok(q.cookieWrites[0].includes("domain=example.com"), "the cookie is the page's domain");
    // fetch, when sendBeacon says no: same address, a simple text body, no credentials asked for
    const f = page({ src: "https://skald.example.net/traffic-js/skald.js", noBeacon: true });
    assert.equal(f.fetched[0].url, "https://skald.example.net/traffic-beacon");
    assert.equal(f.fetched[0].init.credentials, undefined);
    assert.equal(f.fetched[0].init.headers, undefined);
  },
  "loaded from the page's own address: the same relative /traffic-beacon as always"() {
    for (const src of ["/traffic-js/skald.js", "https://www.example.com/traffic-js/skald.js?v=2"]) {
      assert.equal(page({ src }).sent[0].url, "/traffic-beacon", src);
    }
    // a proxy under a folder keeps it
    assert.equal(page({ src: "/stats/traffic-js/skald.js" }).sent[0].url, "/stats/traffic-beacon");
    assert.equal(page({ src: "https://skald.example.net/eu/traffic-js/skald.js" }).sent[0].url,
      "https://skald.example.net/eu/traffic-beacon");
    // a copy served from somewhere else (not .../traffic-js/): the page's own, as before
    assert.equal(page({ src: "https://cdn.example.net/js/skald.min.js" }).sent[0].url, "/traffic-beacon");
  },
  "data-endpoint still wins over the script's address"() {
    const p = page({ src: "https://skald.example.net/traffic-js/skald.js",
      attrs: { "data-endpoint": "/stats/beacon" } });
    assert.equal(p.sent[0].url, "/stats/beacon");
    const q = page({ attrs: { "data-endpoint": "https://skald.example.net/traffic-beacon" } });
    assert.equal(q.sent[0].url, "https://skald.example.net/traffic-beacon");
  },
  "the tag twice on a page (first-party and Skald's): one page view, not two"() {
    const p = page({ src: "https://skald.example.net/traffic-js/skald.js" });
    vm.runInContext(SOURCE, p.ctx);
    assert.deepEqual(p.names(), ["page_view"]);
    p.ctx.history.pushState({}, "", "/features/");
    assert.deepEqual(p.names(), ["page_view", "page_view"]);
  },
  "served with visitor IDs off: no ID anywhere"() {
    const p = page({ source: SOURCE.replace("IDS=1", "IDS=0"),
      attrs: { "data-share-subdomains": "true" },
      embeds: [el("iframe", { src: "https://calendly.com/acme/demo" })] });
    p.doc("submit", el("form", { id: "contact" }));
    assert.deepEqual(p.names(), ["page_view", "form_submit"]);
    assert.ok(p.sent.every((s) => !("v" in s.body)));
    assert.equal(p.ctx.localStorage.m.size + p.cookies.size, 0);
    assert.equal(p.ctx.skald("id"), null);
  },
};

let failed = 0;
for (const [name, fn] of Object.entries(tests)) {
  try {
    fn();
    console.log("ok   " + name);
  } catch (err) {
    failed++;
    console.log("FAIL " + name + "\n" + (err && err.stack || err));
  }
}
console.log(failed ? `${failed} failed` : `all ${Object.keys(tests).length} passed`);
process.exit(failed ? 1 : 0);

// Behaviour of deploy/cloudflare-worker/skald-edge.js with a fake fetch and ctx.
// Run: node tests/js/skald-edge-worker.mjs  (tests/test_edge.py runs it too).
// Hosts are example.com; addresses RFC 5737; nothing here is real.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const FILE = fileURLToPath(new URL("../../deploy/cloudflare-worker/skald-edge.js", import.meta.url));
const SOURCE = readFileSync(FILE, "utf8");
const worker = (await import("data:text/javascript," + encodeURIComponent(SOURCE))).default;

const INGEST = "https://stats.example.com/traffic-ingest/example.com";
const ENV = { SKALD_TOKEN: "test-token-not-real", SKALD_INGEST_URL: INGEST };

let unhandled = 0;
process.on("unhandledRejection", () => { unhandled += 1; });

function request(path = "/guides/alpha?x=1", headers = {}) {
  return {
    url: `https://example.com${path}`,
    method: "GET",
    headers: new Headers({
      "cf-connecting-ip": "203.0.113.10",
      "cf-ray": "8c0000000000abcd-AMS",
      "user-agent": "Mozilla/5.0 Test",
      referer: "https://chatgpt.com/",
      ...headers,
    }),
  };
}

// A fake world: the origin answers at once; Skald's answer is held until
// release() (or fails, or throws at once).
function world({ skald = "hold", cache = "HIT", length = "5" } = {}) {
  const posts = [];
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  const origin = new Response("hello", {
    status: 200,
    headers: { "cf-cache-status": cache, ...(length === null ? {} : { "content-length": length }) },
  });
  globalThis.fetch = (input, init) => {
    const url = typeof input === "string" ? input : input.url;
    if (url.startsWith("https://stats.example.com/")) {
      posts.push({ url, init });
      if (skald === "reject") return Promise.reject(new Error("network down"));
      if (skald === "throw") throw new Error("thrown at once");
      if (skald === "ok") return Promise.resolve(new Response("{}", { status: 200 }));
      return held.then(() => new Response("{}", { status: 200 }));
    }
    return Promise.resolve(origin);
  };
  const waits = [];
  const ctx = {
    passed: 0,
    waitUntil(p) { waits.push(p); },
    passThroughOnException() { this.passed += 1; },
  };
  return { posts, origin, ctx, waits, release };
}

const tests = [];
const test = (name, fn) => tests.push([name, fn]);

test("the response comes back while Skald's post is still pending", async () => {
  const w = world({ skald: "hold" });
  const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error("blocked")), 500));
  const got = await Promise.race([worker.fetch(request(), ENV, w.ctx), timeout]);
  assert.equal(got, w.origin, "the origin's response, unchanged");
  assert.equal(w.posts.length, 1, "the post was started");
  assert.equal(w.waits.length, 1, "and handed to waitUntil");
  let settled = false;
  w.waits[0].then(() => { settled = true; });
  await new Promise((r) => setTimeout(r, 20));
  assert.equal(settled, false, "the post had not finished when the response was returned");
  w.release();
  await w.waits[0];
  assert.equal(w.ctx.passed, 1, "fails open");
});

test("the record", async () => {
  const w = world({ skald: "ok" });
  await worker.fetch(request(), ENV, w.ctx);
  await Promise.all(w.waits);
  const { url, init } = w.posts[0];
  assert.equal(url, `${INGEST}?format=edge`);
  assert.equal(init.method, "POST");
  assert.equal(init.headers.authorization, "Bearer test-token-not-real");
  const rec = JSON.parse(init.body);
  assert.deepEqual(Object.keys(rec).sort(),
    ["bytes", "cache", "host", "id", "ip", "method", "path", "referer", "status", "ts", "ua"]);
  assert.equal(rec.ip, "203.0.113.10");
  assert.equal(rec.host, "example.com");
  assert.equal(rec.path, "/guides/alpha?x=1");
  assert.equal(rec.status, 200);
  assert.equal(rec.bytes, 5);
  assert.equal(rec.cache, "HIT");
  assert.equal(rec.id, "8c0000000000abcd-AMS");
  assert.equal(rec.referer, "https://chatgpt.com/");
  assert.match(rec.ts, /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/);
});

test("no content-length, no cf-ray", async () => {
  const w = world({ skald: "ok", length: null });
  const req = request("/");
  req.headers.delete("cf-ray");
  await worker.fetch(req, ENV, w.ctx);
  await Promise.all(w.waits);
  const rec = JSON.parse(w.posts[0].init.body);
  assert.equal(rec.bytes, null);
  assert.match(rec.id, /^[0-9a-f-]{36}$/);
});

test("a failed post is dropped silently", async () => {
  for (const skald of ["reject", "throw"]) {
    const w = world({ skald });
    const got = await worker.fetch(request(), ENV, w.ctx);
    assert.equal(got, w.origin, skald);
    await Promise.all(w.waits);
  }
});

test("what is not sent", async () => {
  const cases = [
    [request("/traffic-beacon"), ENV, {}],
    [request("/traffic-js/skald.js"), ENV, {}],
    [request("/assets/app.CSS"), { ...ENV, SKALD_SKIP_EXTENSIONS: "css, .js" }, {}],
    [request("/"), { ...ENV, SKALD_CACHE_HITS_ONLY: "true" }, { cache: "MISS" }],
    [request("/"), { ...ENV, SKALD_SAMPLE: "0" }, {}],
    [request("/"), { SKALD_INGEST_URL: INGEST }, {}],
    [request("/"), { SKALD_TOKEN: "x" }, {}],
  ];
  for (const [req, env, opts] of cases) {
    const w = world({ skald: "ok", ...opts });
    const got = await worker.fetch(req, env, w.ctx);
    assert.equal(got, w.origin);
    assert.equal(w.posts.length, 0, req.url);
    assert.equal(w.waits.length, 0, req.url);
  }
});

test("by default everything is sent, assets and misses too", async () => {
  for (const [path, cache] of [["/assets/app.css", "HIT"], ["/", "MISS"], ["/", "DYNAMIC"]]) {
    const w = world({ skald: "ok", cache });
    await worker.fetch(request(path), { ...ENV, SKALD_CACHE_HITS_ONLY: "false" }, w.ctx);
    await Promise.all(w.waits);
    assert.equal(w.posts.length, 1, path + cache);
  }
});

test("sampling", async () => {
  const random = Math.random;
  try {
    for (const [roll, sent] of [[0.2, 1], [0.7, 0]]) {
      Math.random = () => roll;
      const w = world({ skald: "ok" });
      await worker.fetch(request(), { ...ENV, SKALD_SAMPLE: "0.5" }, w.ctx);
      assert.equal(w.posts.length, sent, String(roll));
    }
    Math.random = () => 0.999999;
    const w = world({ skald: "ok" });
    await worker.fetch(request(), { ...ENV, SKALD_SAMPLE: "nonsense" }, w.ctx);
    assert.equal(w.posts.length, 1, "a bad sample setting sends everything");
  } finally {
    Math.random = random;
  }
});

let failed = 0;
for (const [name, fn] of tests) {
  try {
    await fn();
    console.log(`ok   ${name}`);
  } catch (err) {
    failed += 1;
    console.log(`FAIL ${name}\n     ${err && err.stack}`);
  }
}
await new Promise((r) => setTimeout(r, 20));
if (unhandled) {
  failed += 1;
  console.log(`FAIL ${unhandled} unhandled rejection(s)`);
}
process.exit(failed ? 1 : 0);

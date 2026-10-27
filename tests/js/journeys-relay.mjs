// The Next.js relay example (skald/kit/journeys/): the routes run in plain Node 24
// (type stripping), fetch is stubbed to catch what they forward. The signature is checked
// twice: by HMAC here and by Skald's own receiver (recorded/receive.py signed()), and the
// withdraw body by contract.validate_withdraw. The secret is made up and protects nothing.
// Run: node tests/js/journeys-relay.mjs (tests/test_recorded_journeys_js.py runs it too).
// Addresses are RFC 5737; hosts example.com.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHmac } from "node:crypto";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const KIT = `${ROOT}skald/kit/journeys/`;
const relay = await import(`${KIT}route.ts`);
const withdraw = await import(`${KIT}withdraw/route.ts`);

const SECRET = "journey-relay-test-secret-not-real";
const SKALD = "https://skald.example.com/traffic-hooks/example.com/journey";
const SITE = "https://www.example.com";
const EVENT = {
  schema_version: 1, event_id: "11111111-1111-4111-8111-111111111111", event_name: "page_view",
  occurred_at: new Date().toISOString().slice(0, 19) + "Z",
  visitor_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", session_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  path: "/pricing", consent: { analytics: "granted" },
};

let forwarded = [];
let skaldSays = { status: 201, body: { ok: true, event_id: EVENT.event_id, duplicate: false } };
globalThis.fetch = async (url, init) => {
  forwarded.push({ url, init });
  return new Response(JSON.stringify(skaldSays.body), { status: skaldSays.status, headers: skaldSays.headers });
};

function env(more = {}) {
  for (const k of ["SKALD_JOURNEY_URL", "SKALD_JOURNEY_SECRET", "SKALD_SITE_ORIGIN", "SKALD_JOURNEY_SEND_IP"]) delete process.env[k];
  Object.assign(process.env, { SKALD_JOURNEY_URL: SKALD, SKALD_JOURNEY_SECRET: SECRET }, more);
}

function request(body, { origin = SITE, type = "application/json", headers = {}, url = `${SITE}/api/skald-journey` } = {}) {
  const h = { "content-type": type, "x-forwarded-for": "203.0.113.7, 198.51.100.2", ...headers };
  if (origin) h.origin = origin;
  return new Request(url, { method: "POST", headers: h, body: typeof body === "string" ? body : JSON.stringify(body) });
}

function python(code, input) {
  const got = spawnSync("python3", ["-c", code], { cwd: ROOT, input, encoding: "utf8" });
  assert.equal(got.status, 0, got.stdout + got.stderr);
  return got.stdout.trim();
}

// Skald's own receiver on one forwarded request.
function receiverAccepts(f) {
  const h = f.init.headers;
  const input = JSON.stringify({ secret: SECRET, body: f.init.body,
    headers: { "x-skald-timestamp": h["X-Skald-Timestamp"], "x-skald-signature": h["X-Skald-Signature"] } });
  return python([
    "import json, sys, time",
    "from skald.recorded.receive import signed",
    "x = json.load(sys.stdin)",
    "print(signed(x['secret'], x['headers'], x['body'].encode(), time.time()))",
  ].join("\n"), input) === "True";
}

const tests = {
  async "signed as Skald checks it; the address is the first forwarded hop"() {
    env();
    forwarded = [];
    const res = await relay.POST(request({ ...EVENT, ip: "192.0.2.99" }));
    assert.equal(res.status, 201);
    assert.deepEqual(await res.json(), { ok: true, duplicate: false });
    assert.equal(forwarded.length, 1);
    const f = forwarded[0];
    assert.equal(f.url, SKALD);
    assert.equal(f.init.method, "POST");
    assert.ok(f.init.signal, "a timeout is set");
    const sent = JSON.parse(f.init.body);
    assert.equal(sent.ip, "203.0.113.7");
    assert.equal(sent.event_id, EVENT.event_id);
    const h = f.init.headers;
    assert.match(h["X-Skald-Timestamp"], /^\d{10}$/);
    assert.ok(Math.abs(Number(h["X-Skald-Timestamp"]) - Date.now() / 1000) < 5);
    const want = createHmac("sha256", SECRET).update(`${h["X-Skald-Timestamp"]}.${f.init.body}`).digest("hex");
    assert.equal(h["X-Skald-Signature"], want);
    assert.ok(receiverAccepts(f), "Skald's receiver refused the signature");
    assert.ok(!JSON.stringify(Object.fromEntries(res.headers)).includes(SECRET));
  },
  async "x-real-ip when there is no forwarded hop; SKALD_JOURNEY_SEND_IP=0 sends none"() {
    env();
    forwarded = [];
    await relay.POST(request({ ...EVENT }, { headers: { "x-forwarded-for": "", "x-real-ip": "198.51.100.4" } }));
    assert.equal(JSON.parse(forwarded[0].init.body).ip, "198.51.100.4");
    env({ SKALD_JOURNEY_SEND_IP: "0" });
    forwarded = [];
    await relay.POST(request({ ...EVENT, ip: "192.0.2.99" }));
    assert.equal(JSON.parse(forwarded[0].init.body).ip, undefined);
  },
  async "refused before anything is sent: origin, type, size, JSON, settings"() {
    env();
    forwarded = [];
    assert.equal((await relay.POST(request(EVENT, { origin: "https://evil.example.org" }))).status, 403);
    assert.equal((await relay.POST(request(EVENT, { origin: null }))).status, 403);
    assert.equal((await relay.POST(request(EVENT, { type: "text/plain" }))).status, 415);
    assert.equal((await relay.POST(request({ ...EVENT, label: "x".repeat(17 * 1024) }))).status, 413);
    assert.equal((await relay.POST(request("{not json"))).status, 400);
    assert.equal((await relay.POST(request("[1]"))).status, 400);
    assert.equal((await withdraw.POST(request({ visitor_id: "nope" }, { url: `${SITE}/api/skald-journey/withdraw` }))).status, 400);
    env({ SKALD_JOURNEY_SECRET: "" });
    const res = await relay.POST(request(EVENT));
    assert.equal(res.status, 503);
    assert.equal(forwarded.length, 0);
  },
  async "SKALD_SITE_ORIGIN: the site's own origin behind a proxy"() {
    env({ SKALD_SITE_ORIGIN: "https://www.example.com/" });
    forwarded = [];
    const inner = "http://localhost:3000/api/skald-journey";
    assert.equal((await relay.POST(request(EVENT, { url: inner }))).status, 201);
    assert.equal((await relay.POST(request(EVENT, { url: inner, origin: "http://localhost:3000" }))).status, 403);
    assert.equal(forwarded.length, 1);
  },
  async "Skald's answer passes on: status, the field, Retry-After"() {
    env();
    skaldSays = { status: 400, body: { error: "path must be the page's path only", field: "path" } };
    let res = await relay.POST(request(EVENT));
    assert.equal(res.status, 400);
    assert.deepEqual(await res.json(), { ok: false, error: "path must be the page's path only", field: "path" });
    skaldSays = { status: 429, body: { error: "too many" }, headers: { "Retry-After": "60" } };
    res = await relay.POST(request(EVENT));
    assert.equal(res.status, 429);
    assert.equal(res.headers.get("retry-after"), "60");
    skaldSays = { status: 201, body: { ok: true } };
  },
  async "withdraw: a body Skald's contract accepts, signed, to <url>/withdraw"() {
    env({ SKALD_JOURNEY_URL: SKALD + "/" });
    forwarded = [];
    skaldSays = { status: 200, body: { ok: true, removed: 3 } };
    const res = await withdraw.POST(request({ visitor_id: EVENT.visitor_id }, { url: `${SITE}/api/skald-journey/withdraw` }));
    assert.equal(res.status, 200);
    assert.deepEqual(await res.json(), { ok: true, removed: 3 });
    const f = forwarded[0];
    assert.equal(f.url, SKALD + "/withdraw");
    assert.ok(receiverAccepts(f), "Skald's receiver refused the signature");
    const got = python([
      "import json, sys",
      "from datetime import datetime, timezone",
      "from skald.recorded.contract import loads, validate_withdraw",
      "print(json.dumps(validate_withdraw(loads(sys.stdin.read().encode()), datetime.now(timezone.utc))))",
    ].join("\n"), f.init.body);
    assert.equal(JSON.parse(got).visitor_id, EVENT.visitor_id);
    skaldSays = { status: 201, body: { ok: true } };
  },
  async "Skald not answering: 504, nothing echoed"() {
    env();
    const real = globalThis.fetch;
    globalThis.fetch = async () => { throw new TypeError("network"); };
    try {
      const res = await relay.POST(request(EVENT));
      assert.equal(res.status, 504);
      assert.ok(!(await res.text()).includes(SECRET));
    } finally {
      globalThis.fetch = real;
    }
  },
};

let failed = 0;
for (const [name, fn] of Object.entries(tests)) {
  try { await fn(); console.log(`ok   ${name}`); } catch (e) { failed++; console.log(`FAIL ${name}\n${e.stack}`); }
}
console.log(failed ? `${failed} failed` : `all ${Object.keys(tests).length} passed`);
process.exitCode = failed ? 1 : 0;

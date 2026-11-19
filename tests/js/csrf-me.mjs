// SKALD-40: who is reading (<page>/me: role, menu, the CSRF value every save carries) is
// asked whether or not the site's funnels file exists yet, and a save the helper refuses
// as "out of date" asks /me again and tries once more (js/access.js, js/tabs/ipmanager.js).
//
//   node tests/js/csrf-me.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });

const STALE = "The page is out of date. Reload it and try again.";
const server = { csrf: "token-1", me: "sessions", user: "ann@example.com", refuseAlways: false, otherRefusal: false };
const seen = [];                                  // [path, method, csrf header]
globalThis.fetch = async (path, init = {}) => {
  const p = String(path).split("?")[0];
  const sent = (init.headers || {})["X-Skald-CSRF"] || "";
  seen.push([p, init.method || "GET", sent]);
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => data });
  if (p === "me") {
    if (server.me === "none") return { ok: false, status: 404, json: async () => { throw new Error("not JSON"); } };
    return answer({ ok: true, role: "admin", mode: "sessions", user: server.user, org: "Example Ltd", csrf: server.csrf });
  }
  if (p === "settings/save") {
    if (server.otherRefusal) return answer({ ok: false, error: "Refused: changes only work from this page." }, 403);
    if (server.refuseAlways || sent !== server.csrf) return answer({ ok: false, error: STALE }, 403);
    return answer({ ok: true, saved: true });
  }
  return answer({ ok: false, error: "not found" }, 404);
};

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { HIDDEN, ACCOUNT_TABS } = await import(new URL("state.js", JS));
const { ME, loadMe } = await import(new URL("access.js", JS));
const { call, setCsrf } = await import(new URL("tabs/ipmanager.js", JS));
const posts = () => seen.filter(([p]) => p === "settings/save");
const asks = () => seen.filter(([p]) => p === "me");
const reset = () => { seen.length = 0; Object.assign(server, { refuseAlways: false, otherRefusal: false }); };

// ---- a site with no funnels file yet (new or just restored): /me is still asked
{
  await loadMe({ site: "example.com", x: {} });
  assert.equal(asks().length, 1, "/me is asked without a funnels file");
  assert.equal(ME.role, "admin");
  assert.equal(ME.mode, "sessions");
  assert.ok(!HIDDEN.has("settings/org/people"), "the account pages are in the menu");
  reset();
  const r = await call("settings/save", { a: 1 });
  assert.equal(r.ok, true, "the save goes through");
  assert.deepEqual(posts().map(([, , c]) => c), ["token-1"], "the save carried the token");
}

// ---- the token went stale (a new session in another tab): ask /me again, try once more
{
  reset();
  server.csrf = "token-2";
  const r = await call("settings/save", { a: 2 });
  assert.equal(r.ok, true, "the second try goes through");
  assert.deepEqual(posts().map(([, , c]) => c), ["token-1", "token-2"]);
  assert.equal(asks().length, 1, "/me asked once, between the two tries");
  const r2 = await call("settings/save", { a: 3 });
  assert.equal(r2.ok, true, "the next save uses the new token at once");
  assert.equal(posts().length, 3);
  assert.equal(asks().length, 1);
}

// ---- refused again after the new token: say so, never a third try or a loop
{
  reset();
  server.refuseAlways = true;
  const r = await call("settings/save", { a: 4 });
  assert.equal(r.ok, false);
  assert.equal(r.status, 403);
  assert.equal(r.error, STALE, "the helper's own words");
  assert.equal(posts().length, 2, "two tries, no more");
  assert.equal(asks().length, 1);
}

// ---- any other refusal is shown at once: no /me, no second try
{
  reset();
  server.otherRefusal = true;
  const r = await call("settings/save", { a: 5 });
  assert.equal(r.ok, false);
  assert.equal(posts().length, 1);
  assert.equal(asks().length, 0);
}

// ---- someone else signed in, in another tab: never save as them; the page's own refusal
{
  reset();
  server.csrf = "token-carol";
  server.user = "carol@example.com";
  const r = await call("settings/save", { a: 7 });
  assert.equal(r.ok, false);
  assert.equal(r.error, STALE, "reload, and see who is signed in");
  assert.equal(posts().length, 1, "no second try as another person");
  assert.equal(asks().length, 1);
  assert.equal(ME.user, "ann@example.com", "the page still is Ann's");
  server.user = "ann@example.com";
}

// ---- no helper at all (a plain static install): basic mode, the menu as before
{
  reset();
  server.me = "none";
  Object.assign(ME, { role: null, mode: "basic", user: null });
  setCsrf("");
  await loadMe({ site: "example.com", x: {} });
  assert.equal(ME.role, null);
  assert.equal(ME.mode, "basic");
  ACCOUNT_TABS.forEach((k) => assert.ok(HIDDEN.has(k), `${k} stays out of the menu`));
  server.refuseAlways = true;
  const r = await call("settings/save", { a: 6 });
  assert.equal(r.ok, false);
  assert.equal(posts().length, 1, "no new token from /me: no second try");
}

console.log("csrf-me: ok");

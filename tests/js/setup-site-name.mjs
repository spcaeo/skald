// SKALD-57: the set-up steps name the site exactly as it was added. A site added as
// www.example.com is never told about www.www.example.com, and a site added as
// example.com is never told about www.example.com.
//
//   node tests/js/setup-site-name.mjs   (tests/test_setup_site_name.py runs it too)
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://skald.example.net", href: "https://skald.example.net/traffic/example.com/" });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { installFor } = await import(new URL("tabs/conn-install.js", JS));

const text = (method, site) => {
  const st = { site, url: `https://skald.example.net/traffic-ingest/${site}`, base: "https://skald.example.net", kit: {} };
  const box = document.createElement("div");
  box.append(...installFor(method, st));
  return box.textContent;
};

for (const method of ["cloudflare", "docker", "systemd"]) {
  const www = text(method, "www.example.com");
  assert.ok(!www.includes("www.www."), `${method}, www site: ${www}`);
  assert.ok(www.includes("www.example.com"), `${method} names the site`);
  const bare = text(method, "example.com");
  assert.ok(!bare.includes("www.example.com"), `${method}, bare site: no www added: ${bare}`);
  assert.ok(bare.includes("example.com"), `${method} names the site`);
}
assert.ok(text("cloudflare", "www.example.com").includes("Add > Route, with www.example.com/*."));
assert.ok(text("cloudflare", "example.com").includes("Add > Route, with example.com/*."));
assert.ok(text("docker", "www.example.com").includes("give the access log of www.example.com. Then"));
assert.ok(text("systemd", "example.com").includes("It asks for the access log of example.com and the token"));

console.log("setup-site-name: all passed");

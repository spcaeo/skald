// Security (2.21, js/sec-data.js and js/tabs/sec-*.js): the period's sums, the verdict of
// "Is anything exposed?", rows joined to their addresses, the block list and its three
// exports in every privacy mode, and each tab drawn from a security.json with the helper's
// answer for an admin and none for a viewer. dom-lite throws on a null child, so every tab
// must append nothing for a missing value.
//
//   node tests/js/security.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
S.addSections([{ key: "threats", name: "Security", tabs: [
  { route: "threats/exposed", name: "Is anything exposed?", keep: ["sxv"] },
  { route: "threats/scanners", name: "Who is scanning us?", keep: ["sxc", "sxk"] }] }]);
const D = await import(new URL("sec-data.js", JS));
const { ME } = await import(new URL("access.js", JS));
const C = await import(new URL("tabs/sec-common.js", JS));
const X = await import(new URL("tabs/sec-exposed.js", JS));
const SC = await import(new URL("tabs/sec-scanners.js", JS));
const A = await import(new URL("tabs/sec-attacks.js", JS));
const F = await import(new URL("tabs/sec-fake.js", JS));
const B = await import(new URL("tabs/sec-block.js", JS));
const AL = await import(new URL("tabs/sec-alerts.js", JS));
const ST = await import(new URL("tabs/sec-stack.js", JS));
const section = (await import(new URL("tabs/s-security.js", JS))).default;
const text = (el) => (el == null ? "" : typeof el === "string" ? el : el.textContent);
const tick = () => new Promise((r) => setTimeout(r, 5));

// ---- one day as security.py writes it: an SPA shell, a bare IP, one leak, attacks, a fake
const who = [
  { seq: 0, kinds: ["scanner"], first: "2026-10-20T08:00:00+00:00", last: "2026-10-20T08:00:04+00:00", requests: 5, probes: 5,
    categories: { secrets: 2, php: 2, admin: 1 }, status: { "2xx": 5 }, probe_status: { "2xx": 5 }, forged: false, bare_ip: 0,
    country: "SG", hosting: true, fake: null, fake_requests: 0, injection: 0, login: 0, burst: 0, paths: { "/.env": 1, "/phpinfo.php": 1 }, pages: {} },
  { seq: 1, kinds: ["scanner"], first: "2026-10-20T08:01:00+00:00", last: "2026-10-20T08:01:02+00:00", requests: 2, probes: 2,
    categories: { secrets: 2 }, status: { "2xx": 1, "4xx": 1 }, probe_status: { "2xx": 1, "4xx": 1 }, forged: true, bare_ip: 0,
    country: "HK", hosting: false, fake: null, fake_requests: 0, injection: 0, login: 0, burst: 0, paths: { "/.env.production": 1 }, pages: {} },
  { seq: 2, kinds: ["attack"], first: "2026-10-20T08:10:00+00:00", last: "2026-10-20T08:12:00+00:00", requests: 25, probes: 0,
    categories: {}, status: { "4xx": 25 }, probe_status: {}, forged: false, bare_ip: 0, country: "US", hosting: null, fake: null,
    fake_requests: 0, injection: 0, login: 25, burst: 0, paths: {}, pages: {} },
  { seq: 3, kinds: ["fake"], first: "2026-10-20T09:00:00+00:00", last: "2026-10-20T09:05:00+00:00", requests: 9, probes: 0,
    categories: {}, status: { "2xx": 9 }, probe_status: {}, forged: false, bare_ip: 0, country: "DE", hosting: true,
    fake: "claims:Googlebot", fake_requests: 9, injection: 0, login: 0, burst: 0, paths: {}, pages: { "/pricing/": 4, "/": 3 } },
];
const blob = (extra = {}) => ({
  probes: 7, probes_other: 0, scanners: 2, addresses: 2, requests: 7, forged: 1, bare_ip: 0, hosting: 5,
  categories: { secrets: 4, php: 2, admin: 1 }, status: { "2xx": 6, "4xx": 1 }, countries: { SG: 5, HK: 2 }, paths: { "/.env": 1 },
  exposure: { answered: 6, shell: 5, empty: 0, possible: 1, unknown: 0, folded: 0,
    hosts: { "app.example.com": { bare_ip: false, shell_size: 392, shell_paths: 5, answered: 5, shell: 5, empty: 0, possible: 0, unknown: 0 },
      "example.com": { bare_ip: false, shell_size: null, shell_paths: 0, answered: 1, shell: 0, empty: 0, possible: 1, unknown: 0 } },
    rows: [{ host: "example.com", path: "/.env.production", at: "2026-10-20T08:01:00+00:00", status: "200", size: 1873, verdict: "possible", category: "secrets", shell_size: null, who: 1, item: "x0123456789ab" }] },
  attacks: { injection: { requests: 0, kinds: {}, rows: [] },
    login: { posts: 25, episodes: 1, rows: [{ start: "2026-10-20T08:10:00+00:00", end: "2026-10-20T08:12:00+00:00", posts: 25, status: { "4xx": 25 }, path: "/login", paths: 1, who: [2] }] },
    bursts: { requests: 0, episodes: 0, rows: [] } },
  fake: { requests: 9, pairs: 1, kinds: { "claims:Googlebot": 9 }, pages: { "/pricing/": 4, "/": 3 } },
  who, who_folded: 0, who_kept: true, ...extra });
const quiet = blob({ probes: 3, exposure: { answered: 3, shell: 3, empty: 0, possible: 0, unknown: 0, folded: 0, hosts: {}, rows: [] } });
const file = {
  schema_version: 1, rules: { shell_paths: 3, tolerance: 16, login_posts: 20, login_seconds: 300, burst_requests: 300, burst_seconds: 60 },
  requests_hours: 6, who_days: 31,
  alerts: [{ cause: "security_exposure", on: true, threshold: "a scanner probe answered 2xx…" }, { cause: "scan_wave", on: false, threshold: "probes 3x…" }],
  days: [{ day: "2026-10-18", state: "ok", security: null }, { day: "2026-10-19", state: "ok", security: quiet }, { day: "2026-10-20", state: "ok", security: blob() }],
  today: null,
  stack: { day: "2026-10-21", checked_at: "2026-10-21T11:00:00+00:00", list_updated: "2026-10-21",
    hosts: [{ host: "example.com", role: "site", error: null, login: 403 }, { host: "app.example.com", role: "site", error: null },
      { host: "media.example.com", role: "content origin", error: null, login: 200 }],
    products: [{ product: "php", version: "8.1.2", host: "example.com", how: "X-Powered-By header" },
      { product: "wordpress", version: "6.4.2", host: "example.com", how: "generator tag" },
      { product: "nginx", version: null, host: "example.com", how: "Server header" },
      { product: "nodejs", version: null, host: "app.example.com", how: "Next.js runs on Node.js" },
      { product: "php", version: "8.3.10", host: "media.example.com", how: "X-Powered-By header" }],
    logins: [{ host: "example.com", status: 403, open: false }, { host: "media.example.com", status: 200, open: true }],
    matches: [{ advisory: "php", product: "php", host: "media.example.com", version: "8.3.10", state: "update_needed", item: "a0123456789ab" },
      { advisory: "php", product: "php", host: "example.com", version: "8.1.2", state: "no_fix" },
      { advisory: "node", product: "nodejs", host: "app.example.com", version: null, state: "check_version" }],
    advisories: [{ id: "php", product: "php", title: "PHP: unauthenticated remote code execution", severity: "critical", score: "CVSS v4 9.2", published: "2026-10-21",
      branch: "minor", fixed: { "8.5": "8.5.12", "8.4": "8.4.27", "8.3": "8.3.36", "8.2": "8.2.35" }, no_fix_words: "PHP 8.1 and older have no official release with the fix.",
      summary: "Anyone can run code.", action: "Update PHP.", mitigations: ["Set post_max_size to 8M."], mitigations_note: "These reduce the exposure.", sources: ["https://www.php.net/archive/2026.php"], cves: ["CVE-2026-109618"] },
      { id: "node", product: "nodejs", title: "Node.js October 2026 security releases", severity: "high", score: "High", published: "2026-10-21",
      branch: "major", fixed: { 22: "22.23.4", 24: "24.22.1", 26: "26.12.1" }, summary: "A Brotli flaw.", action: "Update Node.js.", mitigations: [], sources: ["https://nodejs.org/en/blog"], cves: [] }],
    commands: { php: "php -v", nodejs: "node -v", nginx: "nginx -v" }, names: { php: "PHP", nodejs: "Node.js", nginx: "nginx", wordpress: "WordPress" } } };
const R = { kind: "history", first: "2026-10-18", last: "2026-10-20", length: 3, days: [] };

// ---- the period: a day without the figure is not recorded, never 0
{
  const p = D.periodOf(file, R);
  assert.deepEqual(p.missing, ["2026-10-18"]);
  assert.equal(p.blobs.length, 2);
  const t = D.sumOf(p.blobs);
  assert.equal(t.probes, 10);
  assert.equal(t.exposure.answered, 9);
  assert.equal(t.exposure.possible, 1);
  assert.equal(t.who.length, 8, "each day's rows, with its day");
  assert.equal(t.categories.secrets, 8);
  const r2 = { ...R, first: "2026-10-16" };
  assert.deepEqual(D.periodOf(file, r2).missing, ["2026-10-16", "2026-10-17", "2026-10-18"], "days the file does not list are missing too");
}

// ---- the verdict: possible beats can't tell beats nothing
{
  const t = D.sumOf([["2026-10-20", blob()]]);
  assert.equal(D.verdictOf(t).tone, "bad");
  assert.equal(D.verdictOf(t).words, "1 possible exposure: check it now");
  const ok = D.sumOf([["2026-10-19", quiet]]);
  assert.equal(D.verdictOf(ok).tone, "ok");
  assert.equal(D.verdictOf(ok).words, "Nothing exposed in this period");
  const unknown = D.sumOf([["d", blob({ exposure: { answered: 2, shell: 0, empty: 0, possible: 0, unknown: 2, folded: 0, hosts: {}, rows: [] } })]]);
  assert.equal(D.verdictOf(unknown).tone, "warn", "no size is can't tell, never safe");
  assert.equal(D.verdictOf(D.sumOf([])).tone, "none");
  const el = X.banner(t);
  assert.equal(el.getAttribute("role"), "alert");
  assert.match(text(el), /1 possible exposure: check it now/);
  assert.match(text(X.banner(ok)), /Nothing exposed in this period/);
}

// ---- rows joined to their addresses: merged by address and agent across days
const answer = { ok: true, mode: "full", keep_days: 395, kept_from: "2026-10-01", days: [], rows: [
  { day: "2026-10-19", seq: 0, ip: "198.51.100.7", user_agent: "curl/8.7.1" },
  { day: "2026-10-20", seq: 0, ip: "198.51.100.7", user_agent: "curl/8.7.1" },
  { day: "2026-10-20", seq: 1, ip: "198.51.100.8", user_agent: "Mozilla/5.0" },
  { day: "2026-10-20", seq: 2, ip: "198.51.100.10", user_agent: "python-requests/2.31" },
  { day: "2026-10-20", seq: 3, ip: "203.0.113.9", user_agent: "Googlebot/2.1" }] };
{
  const t = D.sumOf(D.periodOf(file, R).blobs);
  const rows = D.merge(t.who, answer);
  const curl = rows.find((x) => x.ip === "198.51.100.7");
  assert.equal(curl.probes, 10, "two days of one scanner, one row");
  assert.deepEqual(curl.days, ["2026-10-19", "2026-10-20"]);
  const none = D.merge(t.who, null);
  assert.equal(none.length, 8, "without addresses each day's row stands alone");
  assert.ok(none.every((x) => x.ip === null));
  assert.equal(SC.label(none[0]).startsWith("Not shown"), true);
}

// ---- the block list and its exports, by privacy mode
{
  const t = D.sumOf(D.periodOf(file, R).blobs);
  const full = D.blockList(D.merge(t.who, answer), "full");
  assert.deepEqual(full.addresses.map((x) => x.ip), ["198.51.100.7", "198.51.100.8", "198.51.100.10"], "probes first, then attack attempts; a fake browser alone is not on it");
  assert.deepEqual(full.networks.map((x) => x.cidr), ["198.51.100.0/24"], "a network holding two or more of them");
  const ng = D.nginx(full, { site: "example.com", first: "2026-10-18", last: "2026-10-20" });
  assert.match(ng, /^# Skald block list for example\.com, 2026-10-18 to 2026-10-20\./);
  assert.match(ng, /Review before you use it/);
  assert.match(ng, /^deny 198\.51\.100\.0\/24;  # 12 probes, 25 attack attempts$/m);
  assert.match(ng, /^deny 198\.51\.100\.7;  # 10 probes$/m);
  assert.equal(ng.split("\n").filter((l) => l.startsWith("deny ")).length, 4);
  const cf = D.cloudflare(full).trim().split("\n");
  assert.equal(cf[0], "198.51.100.0/24,Skald: 12 probes, 25 attack attempts".replace(/^(.*?),(.*)$/, (_, a, b) => `${a},"${b}"`));
  assert.equal(cf[1], "198.51.100.7,Skald: 10 probes");
  assert.equal(cf.length, 4, "no header");
  assert.deepEqual(D.plain(full).trim().split("\n"), ["198.51.100.0/24", "198.51.100.7", "198.51.100.8", "198.51.100.10"]);
  const shortAns = { ...answer, mode: "short", rows: answer.rows.map((x) => ({ ...x, ip: x.ip.replace(/\.\d+$/, ".0") })) };
  const short = D.blockList(D.merge(t.who, shortAns), "short");
  assert.deepEqual(short.addresses, [], "a site that shortens: networks only");
  assert.deepEqual(short.networks.map((x) => x.cidr), ["198.51.100.0/24"]);
  assert.doesNotMatch(D.plain(short), /198\.51\.100\.7/);
  assert.deepEqual(D.blockList(D.merge(t.who, answer), "off"), { addresses: [], networks: [] });
  assert.equal(D.networkOf("2001:db8:85a3:8d3:1319:8a2e:370:7348"), "2001:db8:85a3::/48");
  assert.equal(D.networkOf("(removed)"), "");
}

// ---- the tabs, drawn
assert.deepEqual(section.map((x) => x[1]), ["Is anything exposed?", "Your stack", "Who is scanning us?", "Attack attempts", "Fake browsers", "Block list", "Alerts"]);
const asked = [];
globalThis.fetch = async (url) => {
  asked.push(String(url));
  if (/security\.json/.test(url)) return { ok: true, status: 200, json: async () => file };
  if (/people\/security/.test(url)) return { ok: true, status: 200, json: async () => answer };
  return { ok: false, status: 404, json: async () => null, body: { cancel() {} } };
};
const m = { today: "2026-10-21", anchor: "2026-10-20", site: "example.com", byDay: new Map(), days: [], x: { alerts: { enabled: true, mail: true, open: [
  { id: "a1", cause: "security_exposure", title: "Possible exposure: example.com/.env.production answered 200 (1,873 bytes)", opened_at: "2026-10-20T08:03:00+00:00", closed_at: null, mailed: 1 }], closed: [] } } };
const s = { range: "custom", from: "2026-10-18", to: "2026-10-20" };
async function draw(fn, role, extra = {}) {
  ME.role = role;
  C.forget();
  document.body.replaceChildren();
  const out = [fn(m, { ...s, ...extra })].flat(Infinity).filter(Boolean);
  document.body.append(...out);
  for (let i = 0; i < 12; i++) await tick();
  return text(document.body);
}
{
  const shown = await draw(X.default, "viewer");
  assert.match(shown, /Is anything exposed\?/);
  assert.match(shown, /1 possible exposure: check it now/, "the verdict at the top");
  assert.match(shown, /\/\.env\.production/);
  assert.match(shown, /no other probe path on example\.com got a page/);
  assert.match(shown, /location ~ \/\\\. \{ deny all; \}/, "one line of advice with the fix");
  assert.match(shown, /Not recorded: 18 Oct/, "a day without the figure is said, never 0");
  assert.match(shown, /Open the details: each host's answers/, "each host's answers under a fold (2.42)");
  const fold = document.body.querySelector("details");
  fold.open = true; fold.setAttribute("open", ""); fold.dispatchEvent(new Event("toggle"));
  for (let i = 0; i < 4; i++) await tick();
  assert.match(text(document.body), /392 bytes/, "the host's shell, inside the fold");
  assert.equal(document.body.querySelectorAll(".ui-primary").length, 1, "one primary: Fix");
  assert.ok(!asked.some((u) => /people\/security/.test(u)), "this tab never asks for addresses");
}
{
  const shown = await draw(SC.default, "viewer");
  assert.match(shown, /Who is scanning us\?/);
  assert.match(shown, /Addresses show to owners and admins only/);
  assert.ok(!asked.some((u) => /people\/security/.test(u)), "a viewer never asks for addresses");
  assert.doesNotMatch(shown, /198\.51\.100\./);
  assert.match(shown, /Secret files \(\.env, keys\)/);
}
{
  const shown = await draw(SC.default, "admin");
  assert.ok(asked.some((u) => /people\/security\?first=2026-10-18&last=2026-10-20/.test(u)), "an admin asks for the period's addresses");
  assert.match(shown, /198\.51\.100\.7/);
  assert.match(shown, /Forged referrer/);
  assert.match(shown, /Hosting network/);
  const all = await draw(SC.default, "admin", { sxk: "all" });
  assert.match(all, /198\.51\.100\.10/, "every suspect: the attacker too");
}
{
  const shown = await draw(A.default, "admin");
  assert.match(shown, /Login and form hammering/);
  assert.match(shown, /198\.51\.100\.10/);
  assert.match(A.rulesWords(file.rules), /20 or more POSTs to a login or form path .* from one address within 5 minutes/);
  const labels = [];
  const walk = (el) => { if (el.getAttribute?.("aria-label")) labels.push(el.getAttribute("aria-label")); for (const c of el.childNodes || []) walk(c); };
  walk(document.body);
  assert.ok(labels.some((l) => /within 5 minutes/.test(l)), "the thresholds are said behind the options row's (i)");
  assert.match(shown, /No burst in this period/);
}
{
  const shown = await draw(F.default, "admin");
  assert.match(shown, /Claims to be Googlebot/);
  assert.match(shown, /\/pricing\//);
  assert.match(shown, /AI & bots > Crawlers/);
}
{
  const viewer = await draw(B.default, "viewer");
  assert.match(viewer, /Only owners and admins see addresses/);
  const shown = await draw(B.default, "owner");
  assert.match(shown, /Review before blocking/);
  assert.match(shown, /nginx deny lines/);
  assert.match(shown, /Cloudflare IP list \(CSV\)/);
  assert.match(shown, /198\.51\.100\.0\/24/);
  answer.mode = "off";
  const off = await draw(B.default, "owner");
  assert.match(off, /does not keep addresses/);
  answer.mode = "full";
}
{
  const shown = await draw(AL.default, "admin");
  assert.match(shown, /Possible exposure/);
  assert.match(shown, /New scan wave/);
  assert.match(shown, /On: shown and mailed/);
  assert.match(shown, /Off/);
  assert.match(shown, /example\.com\/\.env\.production answered 200/);
}
{
  const shown = await draw(ST.default, "viewer");
  assert.match(shown, /Your stack/);
  assert.match(shown, /As of 21 Oct/);
  assert.match(shown, /PHP 8\.3\.10 on media\.example\.com: Update needed\. Update PHP\. The fixed release for 8\.3 is 8\.3\.36\./);
  assert.match(shown, /PHP 8\.1\.2 on example\.com: No official fix: upgrade the branch/);
  assert.match(shown, /Node\.js not shown by the server on app\.example\.com: Check your version/);
  assert.match(shown, /Login page open to the internet/);
  assert.match(shown, /Login page not open to the internet \(\/wp-login\.php answered 403\)/);
  assert.match(shown, /nginx -v/, "the command, folded for the server admin");
  assert.match(shown, /Mitigations while you update/);
  assert.match(shown, /does not detect or block an exploit/);
  assert.doesNotMatch(shown, /unknown/i);
}
{
  // Log signs worth a look: against the median of the days before, never "attack detected".
  const sday = (day, gw, php, posts = null) => ({ day, state: "ok", security: { signs: { gateway: { requests: gw, hours: { [`${day}T08`]: gw } }, php: { requests: php, hours: {} }, posts } } });
  const days = [];
  for (let i = 1; i <= 10; i++) days.push(sday(`2026-10-${String(i).padStart(2, "0")}`, 4, 10));
  days.push(sday("2026-10-11", 90, 12, { recorded: 5, large: 1, max: 2400000, paths: { "/upload": 1 } }));
  const got = D.signsOf({ days }, { kind: "history", first: "2026-10-11", last: "2026-10-11" });
  assert.deepEqual(got.rows.map((x) => [x.kind, x.n, x.usual]), [["gateway", 90, 4]]);
  assert.equal(got.posts.large, 1);
  const early = D.signsOf({ days: days.slice(5) }, { kind: "history", first: "2026-10-11", last: "2026-10-11" });
  assert.deepEqual(early.rows, [], "too few days before: no usual, nothing flagged");
  const el = A.signsPart({ days, rules: { large_post_bytes: 1000000 } }, { kind: "history", first: "2026-10-11", last: "2026-10-11" });
  assert.match(text(el), /Gateway errors .*: 90 on 2026-10-11 \(usual 4 a day; the most, 90, in the hour from 08:00 UTC\)/);
  assert.match(text(el), /1 POST of 1,000,000 bytes or more \(the largest 2,400,000 bytes\), to \/upload/);
  assert.doesNotMatch(text(el), /attack detected/i);
  const none = A.signsPart({ days: days.slice(0, 10).map((d) => ({ ...d, security: { signs: { ...d.security.signs, posts: null } } })), rules: {} },
    { kind: "history", first: "2026-10-10", last: "2026-10-10" });
  assert.match(text(none), /not recorded\. The log has no request size; add request_length=\$request_length/);
}
{
  // An alert's link opens its item: #threats/exposed?item=<id>, #threats/stack?item=<id>.
  const x = await draw(X.default, "viewer", { item: "x0123456789ab" });
  assert.match(x, /From your alert: example\.com\/\.env\.production/);
  const gone = await draw(X.default, "viewer", { item: "x000000000000" });
  assert.match(gone, /no longer listed/);
  const st = await draw(ST.default, "viewer", { item: "a0123456789ab" });
  assert.match(st, /From your alert/);
  assert.equal(document.body.querySelectorAll(".sec-card.focus").length, 1);
  const al = await draw(AL.default, "owner");
  assert.match(al, /Your security alerts/);
  assert.match(al, /needs sign-in with accounts/, "basic mode: no personal mail, said so");
}
console.log("security: all passed");

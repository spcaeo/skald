// The advanced filters (js/rules.js): every operator on every kind of dimension, AND
// and OR with a group, the honest rule for values nobody recorded, the address form
// (round trip, garbled input), and the single filters older links carry.
//
//   node tests/js/rules.mjs
import assert from "node:assert/strict";

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const R = await import(new URL("rules.js", JS));

const j = (x) => ({ day: "2026-10-15", start: "2026-10-15T12:00", trail: [], flags: [], ...x });
const visits = [
  j({ country: "US", city: "Seattle, US", source: "AI assistant", via: "ChatGPT", device: "Desktop", browser: "Chrome", os: "macOS", landing: "/blog/a", trail: [{ path: "/blog/a", page: true }, { path: "/pricing/", page: true }, { path: "/signup/", page: true }], pages: 3, seconds: 242, returning: false, first_touch: { by: "none" }, flags: ["posted"], ref_host: "chatgpt.com", utm: { source: "chatgpt.com" } }),
  j({ country: "CA", city: "Toronto, CA", source: "Search engine", via: "google.com", device: "Mobile", browser: "Safari", os: "iOS", landing: "/", trail: [{ path: "/", page: true }], pages: 1, seconds: 20, returning: true, first_touch: { by: "vid", via: "ChatGPT", source: "AI assistant", day: "2026-10-10" }, ref_host: "google.com" }),
  j({ country: "Unknown", source: "Direct or unknown", via: "", device: "Desktop", browser: "Firefox", os: "Windows", landing: "/pricing/", trail: [{ path: "/pricing/", page: true }, { path: "/docs/", page: false }], pages: 1, in_app: 1, seconds: null, returning: null }),
  j({ country: "US", source: "Email", via: "", campaign: "newsletter / email / october-update", utm: { campaign: "october-update" }, device: "Tablet", browser: "Chrome", landing: "/features/", trail: [{ path: "/features/", page: true }], pages: 1, seconds: 75, returning: false }),
];
const keep = (tree) => visits.map((v, i) => (R.matcher(tree)(v) ? i : null)).filter((x) => x != null);
const rule = (dim, op, ...vals) => ({ dim, op, vals });
const all = (...items) => ({ mode: "all", items });
const any = (...items) => ({ mode: "any", items });

// ---- operators
assert.deepEqual(keep(all(rule("country", "is", "US", "CA"))), [0, 1, 3], "is: any of the values");
assert.deepEqual(keep(all(rule("country", "not", "US"))), [1], "is not: never a value not recorded (it could have been US)");
assert.deepEqual(keep(all(rule("country", "is", R.NR))), [2], "Not recorded is a value a rule can name");
assert.deepEqual(keep(all(rule("page", "has", "pric"))), [0, 2], "contains: any page read");
assert.deepEqual(keep(all(rule("landing", "starts", "/blog/"))), [0], "starts with");
assert.deepEqual(keep(all(rule("pages", "ge", "2"))), [0, 2], "at least: browser steps count (2nd visit: 1 loaded + 1 in the browser)");
assert.deepEqual(keep(all(rule("pages", "le", "1"))), [1, 3]);
assert.deepEqual(keep(all(rule("seconds", "ge", "60"))), [0, 3], "time on site in seconds; not recorded never in a range");
assert.deepEqual(keep(all(rule("form", "is", "Yes"))), [0], "sent a form");
assert.deepEqual(keep(all(rule("visitor", "is", "New"))), [0, 3]);
assert.deepEqual(keep(all(rule("first", "has", "chatgpt"))), [0, 1], "first came from: this visit when it was the first, else the first touch");
assert.deepEqual(keep(all(rule("assistant", "is", "ChatGPT"))), [0]);
assert.deepEqual(keep(all(rule("assistant", "not", "ChatGPT"))), [1, 2, 3], "no assistant is an answer: is not ChatGPT keeps them");
assert.deepEqual(keep(all(rule("assistant", "is", R.NONE))), [1, 2, 3], "None is a value where having none is an answer");
assert.deepEqual(keep(all(rule("campaign", "is", "october-update"))), [3], "a campaign by its tag");
assert.deepEqual(keep(all(rule("campaign", "has", "news"))), [3]);
assert.deepEqual(keep(all(rule("referrer", "is", "GOOGLE.com"))), [1], "words match in any case");
assert.deepEqual(keep(all(rule("city", "is", "Toronto, CA"))), [1]);
assert.deepEqual(keep(all(rule("os", "is", "iOS", "Windows"))), [1, 2]);

// ---- AND, OR, one group
assert.deepEqual(keep(all(rule("country", "is", "US"), rule("device", "is", "Desktop"))), [0]);
assert.deepEqual(keep(any(rule("country", "is", "CA"), rule("device", "is", "Tablet"))), [1, 3]);
assert.deepEqual(keep(all(rule("browser", "is", "Chrome"), any(rule("source", "is", "Email"), rule("pages", "ge", "3")))), [0, 3]);
assert.equal(R.matcher(all()) (visits[0]), true, "no rule keeps everything");

// ---- what a list cannot apply
assert.equal(R.matcher(all(rule("crawler", "is", "GPTBot")), "visit"), null, "a visit has no crawler: the rule cannot apply");
assert.deepEqual(R.cannot(all(rule("crawler", "is", "GPTBot"), rule("pages", "ge", "2")), "request").map((x) => x.dim), ["pages"]);
assert.deepEqual(R.without(all(rule("crawler", "is", "GPTBot"), rule("country", "is", "US")), "visit"), all(rule("country", "is", "US")));
const req = { group: "answer_engines", agent: "GPTBot", path: "/pricing/", country: "US", device: "Desktop", assistant: "ChatGPT", utm: {} };
assert.equal(R.matcher(all(rule("crawler", "is", "gptbot"), rule("page", "starts", "/pri")), "request")(req), true);
assert.equal(R.matcher(all(rule("browser", "is", "Chrome")), "request")(req), false, "a crawler is not a browser");

// ---- tidy
assert.deepEqual(R.tidy(all(rule("country", "is"), rule("bogus", "is", "x"), rule("country", "ge", "1"), rule("pages", "ge", "lots"))), all(), "no value, no dimension, a wrong operator or a non-number: left out");
assert.deepEqual(R.tidy(all(any(rule("country", "is", "US")))), all(rule("country", "is", "US")), "a group of one is its rule");
assert.deepEqual(R.tidy(all(any(rule("a", "is", "x")), any(rule("country", "is", "US"), all(rule("device", "is", "Mobile"), rule("os", "is", "iOS"))))),
  all(any(rule("country", "is", "US"), rule("device", "is", "Mobile"), rule("os", "is", "iOS"))), "one level of groups: deeper rules join their group");

// ---- the address
const tree = all(rule("country", "is", "US", "CA"), rule("source", "not", "Direct or unknown"), rule("pages", "ge", "3"),
  any(rule("page", "has", "a,b;c:(d)"), rule("assistant", "is", "Perplexity")));
const text = R.encode(tree);
assert.equal(text, "all(country:is:US,CA;source:not:Direct%20or%20unknown;pages:ge:3;any(page:has:a%2Cb%3Bc%3A%28d%29;assistant:is:Perplexity))");
assert.deepEqual(R.decode(text), R.tidy(tree), "round trip");
assert.deepEqual(R.decode(new URLSearchParams(new URLSearchParams({ rules: text }).toString()).get("rules")), R.tidy(tree), "survives the hash's own encoding");
for (const bad of ["", "all(", "nonsense", "all(country:is:%E0%A4%A)", "any(country:zz:US)", "all(country:is:US"]) {
  assert.doesNotThrow(() => R.decode(bad), bad);
}
assert.deepEqual(R.decode("all(country:is:US"), all(), "unclosed: nothing guessed");
assert.equal(R.encode(all()), "", "no rule: no key in the address");

// ---- the single filters older links carry
assert.deepEqual(R.fromState({ country: "CA", path: "/pricing", pathmode: "starts", rules: "" }), all(rule("country", "is", "CA"), rule("page", "starts", "/pricing")));
assert.deepEqual(R.fromState({ device: "Mobile", rules: "any(country:is:US;country:is:CA)" }), all(rule("device", "is", "Mobile"), any(rule("country", "is", "US"), rule("country", "is", "CA"))));
{
  const p = R.toState(all(rule("country", "is", "CA"), rule("page", "has", "/blog"), rule("country", "is", "US"), rule("device", "is", "Mobile", "Tablet"), rule("source", "not", "Email")));
  assert.equal(p.country, "CA", "the first one-value rule of a breakdown is its single filter");
  assert.equal(p.path, "/blog"); assert.equal(p.pathmode, "contains");
  assert.equal(p.device, "", "two values: a rule, not a single filter");
  assert.equal(p.rules, "all(country:is:US;device:is:Mobile,Tablet;source:not:Email)");
  assert.equal(R.leaves(R.fromState(p)).length, 5, "read back: every rule, none lost or doubled");
  const q = R.toState(any(rule("country", "is", "CA"), rule("device", "is", "Mobile")));
  assert.equal(q.country, "", "OR: nothing is a single filter (those are always AND)");
  assert.equal(q.rules, "any(country:is:CA;device:is:Mobile)");
  assert.deepEqual(R.toState(any(rule("country", "is", "CA"))).country, "CA", "one rule: AND and OR are the same");
}
// The same visits kept, read either way.
{
  const t = all(rule("country", "is", "US"), rule("browser", "is", "Chrome"), rule("pages", "le", "1"));
  assert.deepEqual(keep(R.fromState(R.toState(t))), keep(t));
}

// ---- words
assert.deepEqual(R.ruleWords(rule("country", "is", "US", "CA"), (d, v) => `[${v}]`), { field: "Country", op: "is", val: "[US], [CA]" });
assert.equal(R.ruleWords(rule("seconds", "ge", "90")).val, "1 min 30 s");
assert.equal(R.ruleWords(rule("assistant", "is", R.NONE)).val, "None");
assert.equal(R.treeWords(all(rule("pages", "ge", "3"), any(rule("device", "is", "Mobile"), rule("os", "is", "iOS")))), "Pages read ≥ 3; (Device is Mobile or Operating system is iOS)");

console.log("rules: all passed");

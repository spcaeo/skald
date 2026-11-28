// SKALD-51: Google's fetch proxy wears Google's mark, never Gemini's: it is not credited
// to Gemini. A Gemini name keeps its own.
//
//   node tests/js/google-proxy-icon.mjs   (tests/test_google_fetch_proxy.py runs it too)
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const { mark } = await import(new URL("../../skald/webapp/js/icons.js", import.meta.url));
const NAME = "Google fetch proxy (Gemini, Sheets, Apps Script)";
assert.equal(mark("bot", NAME).textContent, "G");
assert.equal(mark("bot", "claims to be " + NAME).textContent, "G");
assert.equal(mark("bot", "Gemini-User").textContent, "Ge");
assert.equal(mark("bot", "Googlebot").textContent, "G");
console.log("google-proxy-icon: all passed");

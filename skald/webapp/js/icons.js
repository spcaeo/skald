// Small marks beside known names: assistants, crawlers, search engines,
// social networks, mail, browsers, systems, devices, statuses, groups, kinds
// of source and kinds of page. All drawn here as simple glyphs or letter
// marks - no artwork copied, nothing fetched from elsewhere. A referring
// site shows its own favicon when the server cached one beside the page
// (favicons.json lists them); otherwise an initial.
// Every mark is decorative (aria-hidden): the name beside it stays as text.

import { h } from "./ui.js";

const S = (d, extra = "") => `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"${extra}>${d}</svg>`;
const GLYPH = {
  desktop: S('<rect x="1.8" y="2.5" width="12.4" height="8.5" rx="1.2"/><path d="M5.5 13.5h5M8 11v2.5"/>'),
  mobile: S('<rect x="4.5" y="1.5" width="7" height="13" rx="1.6"/><path d="M7.2 12.2h1.6"/>'),
  tablet: S('<rect x="2.5" y="1.8" width="11" height="12.4" rx="1.6"/><path d="M7.2 12h1.6"/>'),
  bot: S('<rect x="3" y="5" width="10" height="8" rx="2"/><path d="M8 2.5V5M6 9h.01M10 9h.01"/>'),
  windows: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="currentColor"><rect x="2" y="2" width="5.5" height="5.5" rx=".6"/><rect x="8.5" y="2" width="5.5" height="5.5" rx=".6"/><rect x="2" y="8.5" width="5.5" height="5.5" rx=".6"/><rect x="8.5" y="8.5" width="5.5" height="5.5" rx=".6"/></svg>',
  command: S('<path d="M6 6V4.5A1.5 1.5 0 1 0 4.5 6H11.5A1.5 1.5 0 1 0 10 4.5v7a1.5 1.5 0 1 0 1.5-1.5h-7A1.5 1.5 0 1 0 6 11.5z"/>'),
  sparkle: S('<path d="M8 1.8l1.4 4.2 4.3 1.5-4.3 1.5L8 13.2 6.6 9 2.3 7.5 6.6 6z"/>'),
  search: S('<circle cx="7" cy="7" r="4.3"/><path d="M10.2 10.2l3.6 3.6"/>'),
  people: S('<circle cx="5.5" cy="6" r="2.2"/><circle cx="11" cy="6.5" r="1.8"/><path d="M1.8 13.5c.4-2.2 1.9-3.4 3.7-3.4s3.3 1.2 3.7 3.4M9.6 10.3c1.9-.3 3.8.7 4.4 3.2"/>'),
  mail: S('<rect x="1.8" y="3.5" width="12.4" height="9" rx="1.4"/><path d="M2.3 4.5L8 8.8l5.7-4.3"/>'),
  link: S('<path d="M6.8 9.2l2.4-2.4M7.3 4.6l1-1a2.8 2.8 0 0 1 4 4l-1 1M8.7 11.4l-1 1a2.8 2.8 0 0 1-4-4l1-1"/>'),
  home: S('<path d="M2.5 7.2L8 2.5l5.5 4.7v6.3h-11z"/><path d="M6.5 13.5V10h3v3.5"/>'),
  tag: S('<path d="M2 2.5h5.3l6.7 6.7-4.8 4.8L2.5 7.3z"/><circle cx="5.2" cy="5.3" r=".9"/>'),
  arrow: S('<path d="M2.5 8h9M8.5 4.5L12 8l-3.5 3.5"/>'),
  page: S('<path d="M4 1.8h5.5L13 5.3v8.9H4z"/><path d="M9.5 1.8v3.5H13"/>'),
  book: S('<path d="M2.5 3c2-.8 3.8-.6 5.5.6 1.7-1.2 3.5-1.4 5.5-.6v10c-2-.8-3.8-.6-5.5.6-1.7-1.2-3.5-1.4-5.5-.6z"/><path d="M8 3.6v10"/>'),
  scales: S('<path d="M8 2.5v11M4.5 13.5h7M3 5h10M3 5l-1.5 4h3zM13 5l-1.5 4h3z"/>'),
  plug: S('<path d="M5.5 1.8v3M10.5 1.8v3M3.8 4.8h8.4v2.5a4.2 4.2 0 0 1-8.4 0zM8 11.5v2.7"/>'),
  shield: S('<path d="M8 1.8l5 2v4c0 3-2.2 5.3-5 6.4-2.8-1.1-5-3.4-5-6.4v-4z"/>'),
  person: S('<circle cx="6.5" cy="5.5" r="2.5"/><path d="M2 13.5c.5-2.5 2.3-4 4.5-4s4 1.5 4.5 4M12.5 6v4M10.5 8h4"/>'),
  money: S('<circle cx="8" cy="8" r="6"/><path d="M10 6c-.4-.8-1.1-1.1-2-1.1-1.1 0-2 .6-2 1.5 0 2 4 1.1 4 3.2 0 .9-.9 1.5-2 1.5-1 0-1.7-.4-2.1-1.2M8 3.6v1.3M8 11.1v1.3"/>'),
  play: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="currentColor"><path d="M5.5 3.8v8.4L12.5 8z"/></svg>',
  bubble: S('<path d="M2.5 7.5c0-2.8 2.5-4.8 5.5-4.8s5.5 2 5.5 4.8-2.5 4.8-5.5 4.8c-.8 0-1.5-.1-2.2-.4L2.8 13.2l.8-2.4c-.7-.9-1.1-2-1.1-3.3z"/>'),
  globe: S('<circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c2 2.2 2 9.8 0 12M8 2c-2 2.2-2 9.8 0 12"/>'),
  clock: S('<circle cx="8" cy="8" r="6"/><path d="M8 4.5V8l2.5 1.5"/>'),
  address: S('<rect x="2" y="3.5" width="12" height="9" rx="1.5"/><path d="M4.5 6.5h3M4.5 9.5h7"/>'),
};

// Known names: [pattern, letters or glyph, tone]. First match wins, so the
// specific come before the general.
const KNOWN = [
  [/chatgpt|openai|gptbot|oai-?(?:search|ads)|^gpt/i, "O", "#10a37f"],
  [/deepseek/i, "Ds", "#4d6bfe"],
  [/grok/i, "Gk", "#14171a"],
  [/claude|anthropic/i, "A", "#c96442"],
  [/perplexity/i, "P", "#20808d"],
  [/gemini|bard/i, "Ge", "#4285f4"],
  [/google|googlebot|adsbot/i, "G", "#4285f4"],
  [/copilot/i, "Co", "#0078d4"],
  [/bing|msnbot|microsoft/i, "B", "#0078d4"],
  [/outlook|hotmail|live\.com/i, "Ou", "#0078d4"],
  [/teams/i, "T", "#6264a7"],
  [/facebook|fb\.com|facebookexternalhit/i, "f", "#1877f2"],
  [/instagram/i, "Ig", "#d6249f"],
  [/whatsapp/i, "W", "#25d366"],
  [/meta/i, "M", "#0866ff"],
  [/applebot|apple/i, "Ap", "#555555"],
  [/bytespider|bytedance|tiktok/i, "By", "#333333"],
  [/you\.com|youbot/i, "Y", "#7a5af5"],
  [/duckduck|duckassist/i, "D", "#de5833"],
  [/yandex/i, "Ya", "#fc3f1d"],
  [/baidu/i, "Ba", "#2932e1"],
  [/linkedin/i, "in", "#0a66c2"],
  [/^x$|twitter|t\.co$|x\.com/i, "X", "#14171a"],
  [/reddit/i, "r", "#ff4500"],
  [/youtube|youtu\.be/i, "play", "#ff0000"],
  [/gmail|mail\.google/i, "Gm", "#ea4335"],
  [/slack/i, "S", "#4a154b"],
  [/imessage/i, "bubble", "#34c759"],
  [/discord/i, "Di", "#5865f2"],
  [/telegram/i, "Tg", "#27a7e7"],
  [/pinterest/i, "Pi", "#e60023"],
  [/skype/i, "Sk", "#00aff0"],
  [/ahrefs/i, "ah", "#ff8800"],
  [/semrush/i, "Se", "#ff642d"],
  [/mistral/i, "Mi", "#fa520f"],
  [/cohere/i, "Ch", "#39594d"],
  [/amazon/i, "Am", "#ff9900"],
];
const BROWSER = [
  [/samsung/i, "Sa", "#1428a0"], [/edge/i, "E", "#0c8f8f"], [/opera/i, "Op", "#ff1b2d"], [/firefox/i, "F", "#e66000"],
  [/chrome|chromium|brave/i, "C", "#1a73e8"], [/safari/i, "S", "#006cff"], [/\bapp\b|in-app|webview/i, "bubble", "#6e7c89"],
];
const OS = [
  [/windows/i, "windows", "#0078d4"], [/mac/i, "command", "#555555"], [/ios|ipad|iphone/i, "i", "#555555"], [/android/i, "An", "#3ddc84"],
  [/chrome ?os/i, "C", "#1a73e8"], [/linux|ubuntu/i, "L", "#333333"],
];
const SOURCE = { "AI assistant": "sparkle", "Search engine": "search", "Social media": "people", Email: "mail", "Other website": "link", "This site": "home", "Tagged link": "tag", "Direct or unknown": "arrow" };
const DEVICE = { desktop: "desktop", mobile: "mobile", tablet: "tablet", bot: "bot" };
const PAGE = [
  [/^\/?$|^\/ca\/?$|^\/ca\/fr\/?$/, "home"], [/pricing|credits|plans?\b/i, "money"], [/compare|alternative|-vs-|\/vs\//i, "scales"],
  [/guide|blog|docs|learn|how-it-works/i, "book"], [/privacy|terms|legal|security|cookie|dpa/i, "shield"], [/contact/i, "mail"],
  [/signup|sign-up|register|early-access|demo/i, "person"], [/integration|alert|notification|monitor|-to-text|scada|alarm/i, "plug"],
];

let FAVICONS = {}, FAVBASE = "data/";
export function setFavicons(file, base) { FAVICONS = file?.hosts || {}; FAVBASE = base || "data/"; }

function chip(letters, tone) {
  if (GLYPH[letters]) return h("span", { class: "ic ic-chip", style: { "--t": tone }, html: GLYPH[letters], "aria-hidden": "true" });
  return h("span", { class: `ic ic-chip${letters.length > 1 ? " two" : ""}`, style: { "--t": tone }, "aria-hidden": "true" }, letters);
}
const glyph = (name, cls = "") => h("span", { class: `ic ic-g ${cls}`, html: GLYPH[name], "aria-hidden": "true" });
const initial = (name) => {
  const ch = (String(name).replace(/^(https?:\/\/)?(www\.)?/i, "").match(/[a-z0-9]/i) || ["?"])[0].toUpperCase();
  return h("span", { class: "ic ic-chip plain", "aria-hidden": "true" }, ch);
};
const find = (list, v) => list.find(([re]) => re.test(v));

function favicon(host) {
  // "google.com (AI Mode)" (dimensions.AI_MODE) is google.com's icon.
  const bare = String(host || "").replace(/ \(AI Mode\)$/, "").replace(/\/.*$/, "");
  const path = FAVICONS[bare] || FAVICONS[bare.replace(/^www\./, "")];
  if (!path) return null;
  const img = h("img", { class: "ic ic-fav", src: FAVBASE + path, alt: "", width: "14", height: "14", loading: "lazy", "aria-hidden": "true" });
  img.addEventListener("error", () => img.replaceWith(initial(bare)), { once: true });
  return img;
}

/* The mark for a value of a dimension: country flags stay as they are (the
   caller draws them). dim: assistant, bot, referrer, browser, os, device,
   source, status, group, path, ip, hour, campaign. */
export function mark(dim, value) {
  const v = String(value ?? "");
  if (!v || v === "(none)" || v === "(all others)") return null;
  switch (dim) {
    case "browser": { const k = find(BROWSER, v) || find(KNOWN, v); return k ? chip(k[1], k[2]) : initial(v); }
    case "os": { const k = find(OS, v); return k ? chip(k[1], k[2]) : null; }
    case "device": { const k = DEVICE[v.toLowerCase()]; return k ? glyph(k) : null; }
    case "source": return SOURCE[v] ? glyph(SOURCE[v]) : null;
    case "status": { const c = Number(v) || 0; const cls = c >= 500 || v === "5xx" ? "s5" : c === 404 || v === "404" ? "s404" : c >= 400 || v === "4xx" ? "s4" : c >= 300 || v === "3xx" ? "s3" : "s2"; return h("span", { class: `ic ic-dot ${cls}`, "aria-hidden": "true" }); }
    case "group": return h("span", { class: "ic ic-sq", style: { background: `var(--g-${v})` }, "aria-hidden": "true" });
    case "path": case "landing": { const k = find(PAGE, v); return glyph(k ? k[1] : "page", "pg"); }
    case "ip": return glyph("address", "pg");
    case "hour": return glyph("clock", "pg");
    case "campaign": return glyph("tag", "pg");
    case "referrer": { const k = find(KNOWN, v); return favicon(v) || (k ? chip(k[1], k[2]) : initial(v)); }
    case "assistant": case "bot": default: { const k = find(KNOWN, v); return k ? chip(k[1], k[2]) : dim === "bot" || dim === "assistant" ? initial(v) : null; }
  }
}

// A name with its mark before it: [mark, text] in one span.
export function named(dim, value, text = value) {
  return h("span", { class: "named" }, mark(dim, value), h("span", { class: "nm" }, text));
}

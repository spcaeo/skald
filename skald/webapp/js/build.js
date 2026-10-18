// What is deployed: the tool's name, version, release and commit, from the
// build.json the deploy writes at the dashboard's root (tools/build-info.sh).
// The name is never written in the app itself: it comes from the repo's NAME
// file through this, so a rename is one file.

import { h } from "./ui.js";
import { when } from "./tz.js";
import { DEMO } from "./demo.js";

export let BUILD = null;

// Skald's own home: the public repository (source, releases, issues). Every install links
// to it from About, the footer and the account menu, so people can star it and report.
export const REPO = "https://github.com/spcaeo/skald";

export async function loadBuild() {
  try {
    const res = await fetch("../build.json", { cache: "no-store", credentials: "same-origin" });
    if (res.ok) BUILD = await res.json();
    else { BUILD = null; res.body?.cancel(); }  // no build file yet: the footer stays blank
  } catch { BUILD = null; }
  return BUILD;
}

// Without a build.json (a fresh install, a preview), the name the page itself carries.
export const toolName = () => BUILD?.name || document.querySelector('meta[name="application-name"]')?.content || "";

// Has a newer release reached the server since this page loaded? (The page's modules stay the ones it loaded.)
export async function newerBuild() {
  if (!BUILD) return false;
  try {
    const res = await fetch("../build.json", { cache: "no-store", credentials: "same-origin" });
    if (!res.ok) { res.body?.cancel(); return false; }
    const now = await res.json();
    return now.commit && now.commit !== BUILD.commit ? now : false;
  } catch { return false; }
}
export const toolTagline = () => BUILD?.tagline || "";

// "7 Oct 2026 16:07 EDT" in the zone the reader picked (the one date family, tz.js).
function deployed(ts) {
  const w = when(ts);
  return w ? `${w.date} ${w.day.slice(0, 4)} ${w.hour}:${w.minute} ${w.label}` : "";
}

// "Skald v1.0.0 · release 58 · 888ea90 · deployed 7 Oct 2026 16:07 EDT"
export function buildLine() {
  if (!BUILD) return "";
  return [`${BUILD.name} v${BUILD.version}`, `release ${BUILD.release}`, BUILD.commit,
    BUILD.deployed_at ? `deployed ${deployed(BUILD.deployed_at)}` : ""].filter(Boolean).join(" · ");
}

// A zone's everyday short name: "EDT", "IST", "BST" (en-US alone says "GMT+5:30" for India).
function zoneName(t, tz) {
  for (const loc of ["en-US", "en-IN", "en-GB", "en-AU"]) {
    try {
      const n = new Intl.DateTimeFormat(loc, { timeZone: tz, timeZoneName: "short" }).formatToParts(new Date(t)).find((p) => p.type === "timeZoneName")?.value;
      if (n && !/^(GMT|UTC)[+-]/.test(n)) return n;
    } catch { return ""; }
  }
  return tz;
}

// "11 Oct 2026 14:51 EDT" in one zone, the app's one date family (tz.js); withDate false: "00:21 IST".
function parts(t, tz) {
  return Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: tz, year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(t)).map((x) => [x.type, x.value]));
}
function stamp(t, tz, withDate = true) {
  try {
    const p = parts(t, tz);
    return `${withDate ? `${p.day} ${p.month} ${p.year} ` : ""}${p.hour}:${p.minute} ${zoneName(t, tz)}`;
  } catch { return ""; }
}
const dayIn = (t, tz) => { try { const p = parts(t, tz); return `${p.year}-${p.month}-${p.day}`; } catch { return ""; } };

// The footer's line: "Live · v2.0.0 · released 11 Oct 2026 14:51 EDT (00:21 IST)".
// The release number and commit stay in its tooltip.
export function releaseLine(zones) {
  if (!BUILD) return { text: "", title: "" };
  const t = Date.parse(BUILD.deployed_at || "");
  const list = (zones && zones.length ? zones : [Intl.DateTimeFormat().resolvedOptions().timeZone]);
  let when = "";
  if (!Number.isNaN(t)) {
    const [first, ...more] = list;
    when = ` · released ${stamp(t, first)}${more.length ? ` (${more.map((z) => stamp(t, z, dayIn(t, z) !== dayIn(t, first))).join(", ")})` : ""}`;
  }
  return { text: `${DEMO.on ? "Demo" : "Live"} · v${BUILD.version}${when}`,
    title: [`${BUILD.name} v${BUILD.version}`, `release ${BUILD.release}`, BUILD.commit].filter(Boolean).join(" · ") };
}

export function buildFooter() {
  const line = buildLine();
  return line ? h("p", { class: "build" }, line) : null;
}

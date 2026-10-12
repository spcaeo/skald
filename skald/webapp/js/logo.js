// Each site's own logo (2.6.0): in the sidebar's site button, the site
// switcher, the phone's top bar and the browser tab. sites.json carries
// each site's `logo` (site_logos.py): the image's address (relative to the
// dashboard's root, served by the helper at <site>/logo) or null, and the
// letter and colour shown while there is none. An image that does not load
// leaves the letter showing. The tab's icon is the site's logo with a small
// Skald badge, drawn on a canvas; the page's own Skald icon stays when the
// canvas cannot be drawn.

import { h } from "./ui.js";

const COLORS = ["#1d4ed8", "#0f766e", "#9a6400", "#17212b"];
const ROOT = "../";                        // the dashboard's root, from a site's page

export function letterOf(name) {
  const bare = String(name || "").toLowerCase().replace(/^www\./, "");
  return (bare.match(/[\p{L}\p{N}]/u) || ["?"])[0].toUpperCase();
}

// The same colour for a name every time when the server sent none (the
// server's choice wins: Settings > Sites > Logo).
function colorOf(name) {
  let n = 0;
  for (const ch of String(name)) n = (n * 31 + ch.codePointAt(0)) >>> 0;
  return COLORS[n % COLORS.length];
}

/* The logo for `name` from a sites.json entry (or none): {url, letter, color}. */
export function logoOf(entry, name) {
  const l = entry?.logo || {};
  return { url: typeof l.url === "string" && l.url ? ROOT + l.url : null, letter: l.letter || letterOf(name),
    color: COLORS.includes(l.color) ? l.color : colorOf(name) };
}

/* A square tile: the letter on the colour, the image over it when there is one. */
export function tile(logo, size, cls = "") {
  const img = logo.url ? h("img", { src: logo.url, alt: "", width: size, height: size, decoding: "async", draggable: "false" }) : null;
  img?.addEventListener("error", () => img.remove());
  return h("span", { class: `logo-t ${cls}`.trim(), "aria-hidden": "true", style: { "--lt": `${size}px`, background: logo.color } },
    h("span", { class: "logo-l" }, logo.letter), img);
}

// --------------------------------------------------------- the tab's icon
let skald = null;                          // the page's own icon, kept for the badge
function load(src) {
  return new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = src; });
}
function rounded(c, x, y, w, r) {
  c.beginPath();
  c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + w, r); c.arcTo(x + w, y + w, x, y + w, r);
  c.arcTo(x, y + w, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
}

/* The tab shows the site's logo (or its letter) with a small Skald badge. */
export async function setTabIcon(logo) {
  const link = document.querySelector('link[rel~="icon"]');
  if (!link) return;
  skald = skald || link.getAttribute("href");
  const S = 64, cv = document.createElement("canvas");
  cv.width = cv.height = S;
  const c = cv.getContext("2d");
  if (!c) return;
  let img = null;
  if (logo.url) { try { img = await load(logo.url); } catch { img = null; } }
  rounded(c, 0, 0, 56, 12);
  c.save();
  c.clip();
  if (img) {
    c.fillStyle = "#ffffff";
    c.fillRect(0, 0, 56, 56);
    const k = Math.min(56 / (img.naturalWidth || 56), 56 / (img.naturalHeight || 56));
    const w = (img.naturalWidth || 56) * k, ht = (img.naturalHeight || 56) * k;
    c.drawImage(img, (56 - w) / 2, (56 - ht) / 2, w, ht);
  } else {
    c.fillStyle = logo.color;
    c.fillRect(0, 0, 56, 56);
    c.fillStyle = "#ffffff";
    c.font = "700 34px system-ui, -apple-system, 'Segoe UI', sans-serif";
    c.textAlign = "center"; c.textBaseline = "middle";
    c.fillText(logo.letter, 28, 30);
  }
  c.restore();
  // The badge: Skald's mark, bottom right, with a light ring so it reads on any logo.
  c.fillStyle = "#fbfcfd";
  rounded(c, 34, 34, 30, 8);
  c.fill();
  try {
    const mark = await load(skald);
    c.drawImage(mark, 37, 37, 24, 24);
  } catch {
    c.fillStyle = "#17212b";
    rounded(c, 37, 37, 24, 6);
    c.fill();
  }
  try { link.setAttribute("href", cv.toDataURL("image/png")); } catch { /* a canvas the browser will not read: keep Skald's icon */ }
}

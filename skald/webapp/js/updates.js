// The "a newer Skald is out" line over every page, for owners and admins only.
// The helper's /me answers `update` (updates.py) from the daily check it keeps on
// the server: this page never asks GitHub itself. Dismissed per version, in this
// browser (localStorage); a newer release shows again. A security release is
// drawn as important.

import { h, ICON } from "./ui.js";
import { ME } from "./access.js";

const KEY = "ti-update-dismissed";
const RELEASE = /^https:\/\/github\.com\//;

// What to show, or null: pure, so a test can run it without a page.
export function updateNotice(me, dismissed) {
  const u = me?.update;
  if (!u || !["owner", "admin"].includes(me.role) || !u.latest || !u.current) return null;
  if (dismissed === u.latest) return null;
  return {
    version: u.latest, security: !!u.security, url: RELEASE.test(u.url || "") ? u.url : null,
    title: `${u.product || "Skald"} ${u.latest} is available`,
    words: ` You run ${u.current}.${u.security ? " This is a security release: upgrade soon." : ""}`,
    notes: (u.notes || []).slice(0, 2),
  };
}

function dismissed() {
  try { return localStorage.getItem(KEY); } catch { return null; }
}

export function updateBanner() {
  const n = updateNotice(ME, dismissed());
  if (!n) return null;
  const box = h("div", { class: `state update-banner${n.security ? " bad" : " warn"}`, role: n.security ? "alert" : "status", html: ICON.info });
  const close = h("button", { class: "update-close", type: "button", "aria-label": `Hide until the release after ${n.version}`, title: "Hide until the next release",
    onclick: () => { try { localStorage.setItem(KEY, n.version); } catch { /* storage blocked: hidden until reload */ } box.remove(); } }, "×");
  box.append(h("div", { class: "update-words" }, h("strong", null, `${n.title}.`), n.words,
    n.notes.length ? h("span", { class: "update-notes" }, ` ${n.notes.join(" · ")}`) : null,
    n.url ? [" ", h("a", { href: n.url, target: "_blank", rel: "noopener noreferrer" }, "What's new →")] : null,
    h("span", { class: "update-how" }, " Upgrade: sudo skald upgrade, or pull the new image (Docker).")), close);
  return box;
}

// Overview's set-up line (2.41, the UX audit's task 2, docs/UI-RULES.md rule 10): the set-up
// checklist (checklist.js, the Settings builder's, drawn as it is) folded under one line,
//
//   Set-up: 2 left · Get the daily mail          [Show the list]   [Finish set-up]
//
// so the day's figures come first. The line reads the checklist's own words ("2 of 7 left",
// its first open line that is not optional) and follows it: hidden until its answers come,
// gone when the checklist says everything is done or the reader hides it. Finish set-up
// opens Settings › Set-up checklist. Nothing here decides what is left: checklist.js does.

import { h } from "../ui.js";
import * as S from "../state.js";
import { setupChecklist } from "./checklist.js";
import { fold } from "../ui/fold.js";
import { primary } from "../ui/primary.js";

export const ROUTE = "settings/site/setup";

/* What the line says, from the checklist's box: {left, next} or null when it is not shown. */
export function lineOf(box) {
  if (!box || box.hidden) return null;
  const left = (box.querySelector(".su-left")?.textContent || "").trim();
  if (!left || /^all set$/i.test(left)) return null;
  const open = [...box.querySelectorAll("li.su-i")].find((li) => !li.classList.contains("su-done") && !li.querySelector(".su-opt"));
  return { left: left.replace(/ of \d+ left$/, " left"), next: open?.querySelector("b")?.textContent || "" };
}

export function setupStrip(m) {
  const box = setupChecklist(m);
  if (!box) return null;
  const words = h("span", { class: "ui-grow" });
  const finish = primary("Finish set-up", () => S.set({ tab: ROUTE }));
  const list = fold("Show the list", [box], { cls: "ov-setup-list" });
  list.fill();
  const wrap = h("section", { class: "ov-setup", "aria-label": "Set-up" },
    h("div", { class: "ui-strip" }, h("b", null, "Set-up:"), words, finish), list);
  const sync = () => {
    const got = box.parentNode ? lineOf(box) : null;
    wrap.hidden = !got;
    if (got) words.textContent = [got.left, got.next].filter(Boolean).join(" · ");
  };
  sync();
  // The checklist redraws itself when its answers come and after each Set up; it removes
  // itself once done or hidden. The line follows it.
  if (typeof MutationObserver === "function") {
    new MutationObserver(sync).observe(box, { attributes: true, attributeFilter: ["hidden"], childList: true, subtree: true, characterData: true });
    new MutationObserver(sync).observe(list.querySelector(".ui-fold-b"), { childList: true });
  }
  wrap.sync = sync;
  return wrap;
}

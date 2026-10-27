// "Show all (N)" (2.42, docs/UI-RULES.md rule 7): a long list opens on its first few rows,
// with one quiet button under it that shows the rest, and "Show fewer" to go back. Tables
// have their own (table.js `limit`); this is for the short ranked lists (blist) and the like.
//
//   showAll(draw, total, { first })  -> <div class="ui-showall">
//     draw   (limit) -> the list drawn with at most `limit` rows
//     total  how many rows there are in all; no button when it is `first` or fewer

import { h, n } from "../ui.js";

export function showAll(draw, total, { first = 5, label = "" } = {}) {
  const box = h("div", { class: "ui-showall" });
  let all = false;
  const btn = h("button", { type: "button", class: "linkish ui-more", "aria-expanded": "false" });
  const paint = () => {
    btn.textContent = all ? "Show fewer" : `Show all (${n(total)})`;
    btn.setAttribute("aria-expanded", String(all));
    if (label) btn.setAttribute("aria-label", all ? `Show fewer ${label}` : `Show all ${n(total)} ${label}`);
    box.replaceChildren(...[draw(all ? total : first), total > first ? btn : null].filter(Boolean));
  };
  btn.addEventListener("click", () => { all = !all; paint(); btn.focus?.(); });
  paint();
  return box;
}

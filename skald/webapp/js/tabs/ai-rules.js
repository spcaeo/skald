// AI & bots > Crawler rules and llms.txt (2.7.0).
//
// Crawler rules: the policy editor that was Settings > AI crawlers (crawlers.js:
// let in, keep out, keep out training; admins save, viewers read; the helper checks
// too), then the site's robots.txt beside each crawler (robots.js, its own 30 days
// and today), open. The editor needs the helper, so the demo says so in its place
// and still shows robots.txt.
//
// llms.txt: the suggested llms.txt (llms_txt.json), to preview, copy or download.
// Skald never writes the site's robots.txt or llms.txt.

import { h } from "../ui.js";
import { DEMO, DEMO_SAYS } from "../demo.js";
import { editor as policyEditor, llmsBox } from "./crawlers.js";
import { robotsSection } from "./robots.js";

// The tab strip names the tab, so the title is for screen readers and print (shell.css); the lede shows.
const head1 = (title, lede) => [h("div", { class: "head" }, h("h1", null, title)), h("p", { class: "sub ai-lede" }, lede)];

export function rules(m, s) {
  const editor = DEMO.on
    ? [h("div", { class: "state demo-state", role: "status" }, h("div", null, h("strong", null, `${DEMO_SAYS} `),
      "Letting each AI company's crawlers in or keeping them out is saved through the helper on your own server."))]
    : policyEditor(m);
  const robots = robotsSection(m);
  if (robots?.tagName === "DETAILS") {
    robots.open = true;
    // The tab has no date range of its own, so the fold names only its period.
    const when = robots.querySelector("summary > span");
    if (when) when.textContent = "last 30 days and today";
    // Its pointer to the crawler rules leads to this very tab.
    robots.querySelector('a[href="#ai/rules"]')?.closest("p")?.remove();
  }
  return [...head1("Crawler rules", "Let each AI company's crawlers in, keep them out, or keep out only the ones that collect for training. Below: what the site's robots.txt says to each crawler, and whether it kept to it."),
    h("section", { class: "s ai-rules" }, ...editor),
    robots ? h("section", { class: "s" }, robots) : null];
}

export function llms(m) {
  const box = llmsBox(m);
  return [...head1("llms.txt", "A plain list of the site's best pages for AI assistants, built from what people and assistants read most. Preview it, copy it or download it, then publish it yourself."),
    h("section", { class: "s" }, box)];
}

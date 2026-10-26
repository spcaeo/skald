// "Search Console connected", the checklist's optional line (2.40, js/setup-items.js):
// its Set up dialog. Your AI agent, or by hand (agent-first.js, job "search"); by hand is
// This site > Leads & integrations > Search Console & Bing's own wizard
// (#settings/site/leads?sub=search, search-connect.js searchBox) in one step:
// the robot address to add in Search Console, the properties it can see, test and connect.
// The agent's way finds the property, gives the user the one click in Search Console, and
// reports the property; the watch's "Connect" then makes the same connect (agent-recs.js).

import { h } from "../ui.js";
import { wizard } from "./conn-ui.js";
import { searchBox } from "./search-connect.js";

export function searchDialog(site, { onClose = null, route = null, start = 0, wrap = null } = {}) {
  return wizard({ route, start, wrap, done: "Close",
    title: "Connect Google Search Console", subtitle: `For ${site}.`, key: "setup-search", onClose,
    steps: [{ name: "Connect",
      draw: () => [h("p", null, "Skald reads the searches that bring people here, read-only, through a robot address that you add once in Search Console. ",
        "The same is on ", h("a", { href: "#settings/site/leads?sub=search" }, "Leads & integrations › Search Console & Bing"), "."),
        searchBox(site)] }] });
}

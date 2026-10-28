// "Set up this site" > Script tag events: what the tag adds, the exact tag for
// this site with Copy (GET integrations' script.tag, as Settings > Data > Script tag & goals
// builds it: it loads from this Skald and posts its events here, so the site's
// own server needs no change), "Advanced: serve it from your own domain" with
// the nginx, Apache and Caddy lines and the first-party tag (conn-install.js),
// where it goes (from docs/help/tracking-script.md, docs/HOSTING.md and
// docs/VERCEL.md), a mail with the steps for the developer (the tag needs no
// token, so the mail holds everything) or a private page for them ("Share with
// your developer", conn-share.js), and the Test of Settings > Data > Send logs for
// method "script": GET sites/status?site= polled until the first event or page
// opening (conn-send.js testPanel and verdict); while nothing has arrived, a
// look at the site's home page that says what is wrong (conn-tagcheck.js).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { wizard, codeBlock, steps, answerBox, helpLink } from "./conn-ui.js";
import { sendState, testPanel } from "./conn-send.js";
import { proxyFold } from "./conn-install.js";
import { adminFold, mailButton, copyButton } from "./setup-common.js";
import { shareBox } from "./conn-share.js";
import { arrivedBox } from "../ui/live.js";

// Where the line goes, by how the site is made. Only what the guides say.
export const WHERE = [
  ["A site builder or plain HTML", "paste it into the <head> of every page. In most site builders this is a \"custom code\" or \"head code\" setting that applies to all pages."],
  ["WordPress", "add it to the theme's <head>: a child theme's header.php, or your theme's \"header scripts\" setting."],
  ["Next.js", "put it in the root layout, so every page has it."],
  ["Google Tag Manager", "a Custom HTML tag with the line, firing on All Pages, then publish the container."],
];

export const tagOf = (r, site) => r?.script?.tag || `<script src="${r?.script?.src || "/traffic-js/skald.js"}" data-site="${site}" defer></script>`;
// This Skald's address, from the tag's src (else this page's own).
export const skaldOf = (r) => { try { return new URL(r?.script?.src || "", location.href).origin; } catch { return location.origin; } };

// The mail to the developer: the tag and the steps. No secret: the tag needs none.
export function tagMail(site, tag, skald = "") {
  const where = skald ? skald.replace(/^https?:\/\//, "") : "the Skald server";
  return ["Hello,", "",
    `Please add this line to the <head> of every page of ${site}, then publish the site:`, "", tag, "",
    "Where it goes:", ...WHERE.map(([a, b]) => `- ${a}: ${b}`), "",
    `It needs no password and no token, and no change on the web server: the page loads the script from ${where} and sends its events there.`, "",
    "To check it: open a page of the site in a normal browser window, with Do Not Track and Global Privacy Control off. In the browser's developer tools, Network panel, a request to traffic-beacon answered 204 or 202 means it works. 403 means the page's host name is not one of the site's host names in Skald.",
    "", "Thank you."].join("\n");
}

export async function tagDialog(site, { item = null, onClose = null, route = null, start = 0, wrap = null } = {}) {
  const [r, data] = await Promise.all([call(`integrations?site=${encodeURIComponent(site)}`), call("sites")]);
  const tag = tagOf(r.ok ? r : null, site);
  const skald = skaldOf(r.ok ? r : null);
  const ts = sendState(site, data.ok ? data : {});
  ts.method = "script";
  const off = data.ok && data.beacon_on === false;
  const tech = item?.tech ? item.tech.split("\n").map((l) => h("p", null, l)) : null;
  return wizard({ route, start, wrap,
    title: "Add the script tag", subtitle: `For ${site}. Optional.`, key: "setup-script", onClose, state: ts,
    steps: [
      { name: "What it adds",
        draw: () => [h("p", null, "The script tag adds what a server log cannot see: forms started and sent, phone and email clicks, and bookings made in a Calendly, Cal.com or HubSpot embed."),
          h("p", { class: "note" }, `It is optional: Skald's figures from the log never depend on it. It sends events only to your Skald server (${skald.replace(/^https?:\/\//, "")}), never to a third party, and uses no cookies.`),
          off ? answerBox("bad", "The script tag is switched off on this Skald server.", h("p", null, "Ask whoever runs your Skald server to turn it on first. The next steps still show the tag."),
            adminFold("Set beacon.origins in Skald's config (Docker: SKALD_BEACON_ORIGINS) to the site's address, then restart Skald.")) : null,
          helpLink("tracking-script", "What it tracks, and what it never collects")] },
      { name: "Add it to your pages",
        draw: () => [h("p", null, `Copy this line. It is made for ${site}.`),
          codeBlock(tag, "the script tag"),
          steps("Paste it into the <head> of every page.", "Publish the site."),
          // 2.44: beside the tag, whether a page with it reached Skald yet, by itself, with Test.
          arrivedBox(site, "tag", { intro: "Waiting: no page with the tag has reached Skald yet." }),
          h("p", { class: "note" }, "Nothing changes on your web server: the page loads the script from Skald and sends its events there."),
          h("h4", null, "Where it goes"),
          h("ul", { class: "cn-list" }, WHERE.map(([a, b]) => h("li", null, h("b", null, `${a}: `), b))),
          proxyFold(skald, site),
          adminFold(tech)] },
      { name: "Send to your developer",
        draw: () => [h("p", null, "Does someone else edit your site? Send them the steps. The mail holds the line and where it goes; it needs no password or token."),
          h("div", { class: "acts" }, mailButton("Send these steps to your developer", { subject: `Add the Skald script tag to ${site}`, body: tagMail(site, tag, skald) }),
            copyButton("Copy the steps", tagMail(site, tag, skald), "the steps")),
          shareBox(site, "script"),
          h("p", { class: "note" }, "Your mail program opens with the mail written. Skald sends nothing itself.")] },
      { name: "Test",
        draw: () => [h("p", null, "Open a page of your site in a normal browser window. Then press Test connection: Skald waits up to 2 minutes for the first event. While nothing has arrived, it also looks at your home page and says what is wrong there."),
          testPanel(ts),
          h("p", { class: "note" }, "Your own office may be marked as internal traffic, and its events kept apart. If nothing shows, test from a phone on mobile data.")] },
    ],
  });
}

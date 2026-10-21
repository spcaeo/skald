// "Set up this site" > Pages opened inside the site (a Next.js site): the one line
// its web server's log format needs so Skald can tell a click inside the site
// from a prefetch (parse.Hit.soft_navigation, docs/INGEST.md "Next.js: pages
// opened inside the site"), with Copy, a mail with the steps for the developer
// or a private page for them ("Share with your developer", conn-share.js task
// "nextjs"), and a Test: GET integrations?site= polled until the doctor's
// Next.js line (doctor.next_pages, id "rsc") says OK. Skald never edits nginx.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { wizard, codeBlock, steps, answerBox, helpLink } from "./conn-ui.js";
import { adminFold, mailButton, copyButton } from "./setup-common.js";
import { shareBox } from "./conn-share.js";

// The field, as each web server writes it: "-" when the request did not send the header.
export const NGINX_LINE = " rsc_prefetch=$http_next_router_prefetch";
export const APACHE_LINE = " rsc_prefetch=%{Next-Router-Prefetch}i";
// A whole log_format (nginx's stock combined one) with the field appended at the very end.
export const NGINX_EXAMPLE = "log_format skald '$remote_addr - $remote_user [$time_local] \"$request\" $status $body_bytes_sent "
  + "\"$http_referer\" \"$http_user_agent\"" + NGINX_LINE + "';";

export const NEXT_STEPS = [
  "Open the web server's settings where the site's log_format line is (nginx: often /etc/nginx/nginx.conf or a file in /etc/nginx/conf.d/).",
  `Add${NGINX_LINE} at the very end of the log_format, inside its closing quote.`,
  "Check the settings: sudo nginx -t",
  "Reload nginx: sudo systemctl reload nginx",
];
export const APACHE_STEP = `Apache: add${APACHE_LINE} at the end of the site's LogFormat, then sudo apachectl configtest and reload Apache.`;
export const NEXT_NOTE = "Skald reads lines with and without the field. Lines written before the change stay as they were; pages opened inside the site count from the reload on.";

// The mail to the developer: the line, the steps, nothing secret.
export function nextMail(site) {
  return ["Hello,", "",
    `${site} is built with Next.js. A page opened by a link inside the site sends no page request, only Next.js's own data request, and Next.js sends the same request for links it prefetches. Skald can tell the two apart once the access log records the Next-Router-Prefetch request header.`, "",
    "Please add this at the very end of the site's nginx log_format, inside its closing quote:", "", NGINX_LINE.trim(), "",
    "For example:", NGINX_EXAMPLE, "",
    ...NEXT_STEPS.map((l, i) => `${i + 1}. ${l}`), "",
    APACHE_STEP, "",
    NEXT_NOTE, "", "Thank you."].join("\n");
}

// The steps as nodes: the dialog's second step and the shared page's.
export function nextStepsNodes() {
  return [h("p", null, "Add this at the very end of the site's nginx log_format, inside its closing quote:"),
    codeBlock(NGINX_LINE, "the line for nginx"),
    h("p", null, "For example, a whole log_format with it at the end:"),
    codeBlock(NGINX_EXAMPLE, "the example log_format"),
    steps(...NEXT_STEPS),
    h("p", null, "Apache instead: add this at the end of the site's LogFormat, then check and reload Apache:"),
    codeBlock(APACHE_LINE, "the line for Apache"),
    h("p", { class: "note" }, NEXT_NOTE)];
}

// The Test: `ask()` -> {state, says} of the doctor's Next.js line, polled every 5 s for 2 minutes.
export function nextTest(ask, { every = 5000, tries = 24 } = {}) {
  const out = h("div");
  const btn = h("button", { type: "button", class: "btn primary" }, "Test");
  let timer = null;
  const stop = () => { if (timer) clearTimeout(timer); timer = null; btn.disabled = false; };
  btn.addEventListener("click", () => {
    btn.disabled = true;
    let left = tries;
    const once = async () => {
      const got = await ask();
      if (got && got.error) { out.replaceChildren(answerBox("bad", "Could not check just now.", h("p", null, got.error))); stop(); return; }
      if (got && got.state === "OK") { out.replaceChildren(answerBox("ok", "It works: the log records the header. Pages opened inside the site count from now on.")); stop(); return; }
      left -= 1;
      if (left <= 0) {
        out.replaceChildren(answerBox("bad", "No line with the header yet.", h("p", null, "Check that the line is at the end of the log_format the site's access_log uses, that nginx -t passed and that nginx was reloaded. Then open a page and click a link to another page.")));
        stop(); return;
      }
      out.replaceChildren(answerBox("wait", "Waiting for a line with the header...", h("p", null, "Open the site in a browser and click a link to another page of it.")));
      timer = setTimeout(once, every);
    };
    once();
  });
  return h("div", null, h("div", { class: "acts" }, btn), out);
}

const rscOf = (r) => (r && r.ok ? (r.status || []).find((x) => x.id === "rsc") || { state: "", says: "" } : { error: (r && r.error) || "No answer." });

export function nextDialog(site, { item = null, onClose = null, route = null, start = 0 } = {}) {
  return wizard({ route, start,
    title: "Count pages opened inside the site", subtitle: `For ${site}.`, key: "setup-rsc", onClose,
    steps: [
      { name: "What is missing",
        draw: () => [h("p", null, "Your site is built with Next.js. When a visitor clicks a link inside it, the browser does not ask for the next page. It asks only for that page's data."),
          h("p", null, "Next.js also asks for the same data, ahead of time, for links in view (a prefetch). In the server's log the two look the same, unless the log records the header Next.js sends with each prefetch."),
          h("p", null, "Until it does, Skald counts only the first page of each visit, and a visit from a tab left open may not count as a person. Nothing is guessed."),
          helpLink("troubleshooting-connections", "Why is my visit not counted?")] },
      { name: "Add one line", draw: () => [...nextStepsNodes(), adminFold(item?.tech || null)] },
      { name: "Send to your developer",
        draw: () => [h("p", null, "Does someone else run the site's server? Send them the steps. They hold no password and no token."),
          h("div", { class: "acts" }, mailButton("Send these steps to your developer", { subject: `One line in the log format of ${site}`, body: nextMail(site) }),
            copyButton("Copy the steps", nextMail(site), "the steps")),
          shareBox(site, "nextjs"),
          h("p", { class: "note" }, "Your mail program opens with the mail written. Skald sends nothing itself, and never changes the web server.")] },
      { name: "Test",
        draw: () => [h("p", null, "After the reload, open the site in a browser and click a link to another page. Then press Test: Skald looks at the log's newest lines every 5 seconds, for up to 2 minutes."),
          nextTest(async () => rscOf(await call(`integrations?site=${encodeURIComponent(site)}`)))] },
    ],
  });
}

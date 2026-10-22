// The script tag's Test, when nothing has arrived yet: Skald looks at the
// site's home page from outside (POST <page>/sites/tagcheck, tag_check.py)
// and says what is wrong in plain words: no tag, a tag that posts to the
// site's own address which answers 308 or 405, a host the site does not
// have, a Content-Security-Policy that blocks it. Drawn by conn-send.js's
// testPanel under the waiting answer, once per press of Test connection.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { answerBox } from "./conn-ui.js";

/* sites/tagcheck's answer in the Test's terms: {kind: ok|wait|bad, head, fix}.
   No DOM, so tests/js/setup.mjs checks it directly. */
export function tagVerdict(r) {
  if (!r || !r.ok || !r.check) {
    return { kind: "wait", head: (r && r.error) || "Skald could not look at your page just now.", fix: "" };
  }
  const c = r.check;
  return { kind: c.state === "ok" ? "ok" : c.state === "problem" ? "bad" : "wait", head: c.words || "", fix: c.fix || "" };
}

export function tagCheckBox(site, { check = (s) => call("sites/tagcheck", { site: s }) } = {}) {
  const box = h("div", { class: "cn-tagcheck", "aria-live": "polite" }, h("p", { class: "empty" }, "Looking at your home page..."));
  Promise.resolve(check(site)).catch(() => null).then((r) => {
    const v = tagVerdict(r);
    box.replaceChildren(h("p", { class: "note" }, "What Skald found on your home page:"),
      answerBox(v.kind, v.head, v.fix ? h("p", null, v.kind === "bad" ? ["What to do: ", v.fix] : v.fix) : null));
  });
  return box;
}
